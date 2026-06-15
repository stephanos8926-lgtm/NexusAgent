import asyncio
import base64
import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.subscription import Subscription
from nats.errors import Error as NATSError

from nexusagent.infrastructure.config import settings

logger = logging.getLogger(__name__)

# NATS max message size is 1MB by default
NATS_MAX_MESSAGE_SIZE = 1024 * 1024


class NATSJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8", errors="replace")
            except Exception:
                return base64.b64encode(obj).decode("ascii")
        if isinstance(obj, set):
            return sorted(obj)
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, Exception):
            return f"{type(obj).__name__}: {obj}"
        return super().default(obj)


class AgentBus:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or settings.server.nats_url
        self.nc: NATSClient | None = None
        self.js: Any = None
        self.kv: Any = None
        self._subscriptions: list[Subscription] = []

    async def connect(self) -> None:
        if self.nc:
            logger.debug("NATS already connected, skipping reconnect")
            return
        try:
            self.nc = await nats.connect(
                self.url,
                reconnect_time_wait=settings.server.nats_reconnect_wait,
                max_reconnect_attempts=settings.server.nats_max_reconnects,
            )
            logger.info(f"Connected to NATS at {self.url}")
            self.js = self.nc.jetstream()
            # Try to create the KV bucket, but don't fail if it already exists
            try:
                self.kv = await self.js.create_key_value(bucket="nexus_results")
                logger.info("JetStream KV bucket 'nexus_results' created.")
            except nats.errors.Error:
                # Bucket already exist - attach to it
                self.kv = await self.js.key_value(bucket="nexus_results")
                logger.info("JetStream KV bucket 'nexus_results' attached.")
        except NATSError as e:
            logger.error(f"Could not connect to NATS: {e}")
            raise

    async def subscribe(self, subject: str, callback: Callable) -> None:
        """Subscribe to a NATS subject with automatic retry."""
        if not self.nc:
            raise RuntimeError("NATSBus not connected. Call connect() first.")

        async def _do_subscribe() -> Subscription:
            sub = await self.nc.subscribe(subject, cb=callback)
            self._subscriptions.append(sub)
            logger.info(f"Subscribed to NATS subject '{subject}'")
            return sub

        # Retry subscription up to 3 times with backoff
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                await _do_subscribe()
                return
            except NATSError as e:
                last_err = e
                if attempt < 2:
                    delay = 0.5 * (2**attempt)
                    logger.warning(
                        f"Subscribe to '{subject}' failed (attempt {attempt + 1}/3): {e}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
        raise last_err  # type: ignore[misc]

    async def subscribe_durable(
        self,
        subject: str,
        callback: Callable,
        *,
        stream: str = "nexus_tasks",
        durable: str = "nexus_worker",
        batch_size: int = 10,
        batch_timeout: float = 5.0,
    ) -> None:
        """Subscribe via JetStream pull consumer with durable delivery.

        Creates the JetStream stream and durable consumer on first use, then
        fetches messages in batches, invoking *callback* for each one and
        acknowledging (ack) on success or negatively acknowledging (nack) on
        failure.

        Args:
            subject: NATS subject pattern to consume (e.g. "nexus.task.>").
            callback: Async callable that receives a NATS message per item.
            stream: JetStream stream name (default ``"nexus_tasks"``).
            durable: Durable consumer name (default ``"nexus_worker"``).
            batch_size: Max messages per pull batch.
            batch_timeout: Seconds to wait for a full batch before processing
                           whatever has arrived.
        """
        if not self.nc or not self.js:
            raise RuntimeError("NATSBus not connected. Call connect() first.")

        # ── 1. Ensure stream exists ──────────────────────────────────────
        try:
            await self.js.add_stream(
                name=stream,
                subjects=[subject],
            )
            logger.info(f"JetStream stream '{stream}' created (subjects={subject})")
        except nats.errors.Error:
            logger.debug(f"JetStream stream '{stream}' already exists, attaching")

        # ── 2. Ensure durable consumer exists ────────────────────────────
        try:
            await self.js.add_consumer(
                stream_name=stream,
                durable_name=durable,
                ack_policy="explicit",
                deliver_policy="all",
                max_deliver=-1,
                ack_wait=30,
            )
            logger.info(
                f"JetStream durable consumer '{durable}' created on '{stream}'"
            )
        except nats.errors.Error:
            logger.debug(
                f"JetStream durable consumer '{durable}' already exists on '{stream}'"
            )

        # ── 3. Pull-subscribe and batch-fetch loop ───────────────────────
        psub = await self.js.pull_subscribe(subject, durable=durable, stream=stream)
        self._subscriptions.append(psub)  # type: ignore[arg-type]
        logger.info(
            f"JetStream pull consumer active: stream='{stream}', "
            f"durable='{durable}', subject='{subject}'"
        )

        async def _consume_loop() -> None:
            while True:
                try:
                    msgs = await psub.fetch(
                        batch=batch_size,
                        timeout=batch_timeout,
                    )
                    batch_total = len(msgs)
                    batch_ack = 0
                    batch_nack = 0

                    for msg in msgs:
                        try:
                            await callback(msg)
                            await msg.ack()
                            batch_ack += 1
                        except Exception as exc:
                            logger.error(
                                f"Durable consumer error on '{subject}': {exc}",
                                exc_info=True,
                            )
                            await msg.nack()
                            batch_nack += 1

                    if batch_total:
                        logger.info(
                            f"Durable batch complete: received={batch_total}, "
                            f"ack={batch_ack}, nack={batch_nack}"
                        )
                except nats.errors.TimeoutError:
                    # No messages available — loop and retry
                    pass
                except asyncio.CancelledError:
                    logger.info(
                        f"JetStream durable consumer '{durable}' cancelled"
                    )
                    break
                except Exception as exc:
                    logger.error(
                        f"JetStream durable fetch error: {exc}", exc_info=True
                    )
                    await asyncio.sleep(1.0)

        # Fire-and-forget: return immediately; loop runs as background task
        loop_task = asyncio.create_task(_consume_loop())
        # Keep a strong reference so the GC doesn't reap it
        self._subscriptions.append(loop_task)  # type: ignore[arg-type]

    async def publish(self, subject: str, message: Any) -> None:
        if not self.nc:
            raise RuntimeError("NATSBus not connected. Call connect() first.")
        try:
            payload = json.dumps(message, cls=NATSJSONEncoder).encode()
            if len(payload) > NATS_MAX_MESSAGE_SIZE:
                logger.warning(
                    f"Publish to '{subject}': payload exceeds NATS max size "
                    f"({len(payload)} > {NATS_MAX_MESSAGE_SIZE} bytes)."
                )
            await self.nc.publish(subject, payload)
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            raise

    async def put_result(self, task_id: str, result: Any) -> None:
        """Store a task result in the JetStream KV store with retry."""
        if not self.kv:
            raise RuntimeError("KV store not connected. Call connect() first.")

        async def _do_put() -> None:
            payload = json.dumps(result, cls=NATSJSONEncoder).encode()
            if len(payload) > NATS_MAX_MESSAGE_SIZE:
                logger.warning(
                    f"Result for task {task_id} exceeds NATS max message size "
                    f"({len(payload)} > {NATS_MAX_MESSAGE_SIZE} bytes). "
                    f"Truncating data field."
                )
                # Try to truncate the 'data' field if present
                if isinstance(result, dict) and "data" in result:
                    truncated = {
                        **result,
                        "data": str(result["data"])[:NATS_MAX_MESSAGE_SIZE // 2]
                        + "\n... [TRUNCATED: exceeded NATS 1MB limit]",
                    }
                    payload = json.dumps(truncated, cls=NATSJSONEncoder).encode()
                if len(payload) > NATS_MAX_MESSAGE_SIZE:
                    raise ValueError(
                        f"Result for task {task_id} is too large for NATS "
                        f"({len(payload)} bytes > {NATS_MAX_MESSAGE_SIZE} limit)"
                    )
            await self.kv.put(task_id, payload)

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                await _do_put()
                logger.debug(f"Stored result for task {task_id} in KV")
                return
            except Exception as e:
                last_err = e
                if attempt < 2:
                    delay = 0.5 * (2**attempt)
                    logger.warning(
                        f"KV put for '{task_id}' failed (attempt {attempt + 1}/3): {e}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
        raise last_err  # type: ignore[misc]

    async def get_result(self, task_id: str) -> Any | None:
        """Retrieve a task result from the JetStream KV store."""
        if not self.kv:
            raise RuntimeError("KV store not connected. Call connect() first.")

        try:
            entry = await asyncio.wait_for(self.kv.get(task_id), timeout=5.0)
            if entry and entry.value:
                return json.loads(entry.value.decode())
            return None
        except TimeoutError:
            logger.warning(f"KV get for '{task_id}' timed out")
            return None
        except nats.errors.Error as e:
            err_str = str(e).lower()
            if "not found" in err_str or "key" in err_str:
                return None
            logger.warning(f"KV get for '{task_id}' failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"KV get for '{task_id}' failed: {e}")
            return None

    async def close(self) -> None:
        import contextlib

        for sub in self._subscriptions:
            with contextlib.suppress(Exception):
                await sub.unsubscribe()
        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None
            self.kv = None
            self._subscriptions.clear()
            logger.info("NATS connection closed.")


# Module-level default bus (lazy-created, overridable)
_default_bus: AgentBus | None = None


def get_bus() -> AgentBus:
    """Get or create the default bus instance."""
    global _default_bus
    if _default_bus is None:
        _default_bus = AgentBus()
    return _default_bus


def set_bus(bus: AgentBus) -> None:
    """Override the default bus (for testing/dependency injection)."""
    global _default_bus
    _default_bus = bus
