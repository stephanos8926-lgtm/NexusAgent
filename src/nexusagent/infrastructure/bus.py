"""NATS JetStream message bus for task distribution and result storage.

Provides ``AgentBus`` (a NATS client wrapper with JetStream KV, automatic
reconnection, health monitoring, and JSON encoding for complex types) and
``NATSJSONEncoder`` (a custom JSON encoder that handles datetime, bytes,
sets, and Path objects).
"""

import asyncio
import base64
import json
import logging
import time
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

# Hard cap on reconnection attempts to prevent infinite hangs.
# If settings.request -1 (infinite), we cap this at a safe maximum.
_NATS_HARD_RECONNECT_CAP = 30  # ~2 minutes at 4s backoff


def _effective_max_reconnects(requested: int) -> int:
    """Return a safe maximum reconnect count.

    -1 means "infinite" in NATS client — we cap that to avoid workers
    hanging forever when NATS is permanently down.
    """
    if requested < 0:
        return _NATS_HARD_RECONNECT_CAP
    return min(requested, _NATS_HARD_RECONNECT_CAP)


class NATSJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for NATS message payloads.

    Handles ``datetime``, ``date``, ``bytes``, ``set``, ``Path``, and
    ``Exception`` objects that the default encoder cannot serialize.
    """

    def default(self, obj):
        """Serialize objects that the default JSON encoder cannot handle.

        Args:
            obj: The object to serialize. Supports ``datetime``, ``date``,
                ``bytes``, ``set``, ``Path``, and ``Exception`` types.

        Returns:
            A JSON-serializable representation of *obj*.

        Raises:
            TypeError: If *obj* is not one of the handled types.
        """
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
    """NATS JetStream message bus for task distribution and result storage.

    Wraps an async NATS client with automatic reconnection, health tracking,
    JetStream key-value storage, and subject-based pub/sub subscriptions.
    """

    def __init__(self, url: str | None = None) -> None:
        """Initialize the bus with an optional NATS server URL.

        Args:
            url: NATS server URL (e.g. ``"nats://localhost:4222"``). If None,
                uses ``settings.server.nats_url``.
        """
        self.url = url or settings.server.nats_url
        self.nc: NATSClient | None = None
        self.js: Any = None
        self.kv: Any = None
        self._subscriptions: set[Any] = set()  # Changed to set for thread-safety
        self._subscriptions_lock = asyncio.Lock()  # Lock for concurrent access
        # Health tracking
        self._connected_event = asyncio.Event()
        self._disconnected_event = asyncio.Event()
        self._last_connect_time: float | None = None
        self._last_disconnect_time: float | None = None
        self._reconnect_count: int = 0
        self._max_reconnects: int = _effective_max_reconnects(settings.server.nats_max_reconnects)

    @property
    def is_connected(self) -> bool:
        """Return True if NATS client exists and is connected."""
        return self.nc is not None and not self.nc.is_closed

    @property
    def is_degraded(self) -> bool:
        """Return True if the bus was once connected but is now disconnected."""
        return (
            self._last_connect_time is not None
            and self._last_disconnect_time is not None
            and self._last_disconnect_time > self._last_connect_time
        )

    @property
    def reconnect_count(self) -> int:
        """Return the number of times the NATS client has reconnected."""
        return self._reconnect_count

    async def wait_for_connection(self, timeout: float = 30.0) -> bool:
        """Wait up to *timeout* seconds for NATS connection.

        Returns True if connected, False on timeout.
        """
        if self.is_connected:
            return True
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    async def connect(self) -> None:
        """Connect to NATS and initialize JetStream KV store.

        Skips reconnection if already connected. Creates the ``nexus_results``
        KV bucket on first use or attaches to an existing one.
        """
        if self.nc:
            logger.debug("NATS already connected, skipping reconnect")
            return
        try:
            max_reconnects = self._max_reconnects
            logger.info(f"Connecting to NATS at {self.url} (max_reconnects={max_reconnects})")
            self.nc = await nats.connect(
                self.url,
                reconnect_time_wait=settings.server.nats_reconnect_wait,
                max_reconnect_attempts=max_reconnects,
                disconnected_cb=self._on_disconnected,
                reconnected_cb=self._on_reconnected,
                closed_cb=self._on_closed,
                error_cb=self._on_error,
            )
            self._last_connect_time = time.time()
            self._connected_event.set()
            self._disconnected_event.clear()
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
            self._last_disconnect_time = time.time()
            self._disconnected_event.set()
            raise

    # ── NATS client callbacks ──────────────────────────────────────────

    async def _on_disconnected(self) -> None:
        self._last_disconnect_time = time.time()
        self._disconnected_event.set()
        self._connected_event.clear()
        logger.warning("NATS disconnected")

    async def _on_reconnected(self) -> None:
        self._reconnect_count += 1
        self._last_connect_time = time.time()
        self._connected_event.set()
        self._disconnected_event.clear()
        logger.info(f"NATS reconnected (attempt #{self._reconnect_count})")

    async def _on_closed(self) -> None:
        self._last_disconnect_time = time.time()
        self._disconnected_event.set()
        self._connected_event.clear()
        logger.info("NATS connection closed permanently")

    async def _on_error(self, err: Exception) -> None:
        logger.error(f"NATS client error: {err}")

    # ── Health probe ────────────────────────────────────────────────────

    async def check_health(self) -> dict[str, Any]:
        """Return a health snapshot dict for monitoring."""
        healthy = self.is_connected
        # Try a quick ping to verify actual connectivity
        if healthy and self.nc is not None:
            try:
                # NATS client doesn't have a native ping, but is_closed checks socket state
                if self.nc.is_closed:
                    healthy = False
            except Exception:
                healthy = False
        return {
            "healthy": healthy,
            "connected": self.is_connected,
            "degraded": self.is_degraded,
            "reconnect_count": self._reconnect_count,
            "max_reconnects": self._max_reconnects,
            "last_connect_time": self._last_connect_time,
            "last_disconnect_time": self._last_disconnect_time,
        }

    async def subscribe(self, subject: str, callback: Callable) -> None:
        """Subscribe to a NATS subject with automatic retry."""
        if not self.nc:
            raise RuntimeError("NATSBus not connected. Call connect() first.")

        # Deduplicate: don't re-subscribe to the same subject with the same callback
        async with self._subscriptions_lock:
            for existing_sub in self._subscriptions:
                if getattr(existing_sub, "subject", None) == subject:
                    logger.debug("Already subscribed to '%s' — skipping", subject)
                    return

        async def _do_subscribe() -> Subscription:
            sub = await self.nc.subscribe(subject, cb=callback)
            async with self._subscriptions_lock:
                self._subscriptions.add(sub)
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
            logger.info(f"JetStream durable consumer '{durable}' created on '{stream}'")
        except nats.errors.Error:
            logger.debug(f"JetStream durable consumer '{durable}' already exists on '{stream}'")

        # ── 3. Pull-subscribe and batch-fetch loop ───────────────────────
        psub = await self.js.pull_subscribe(subject, durable=durable, stream=stream)
        async with self._subscriptions_lock:
            self._subscriptions.add(psub)
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
                    logger.info(f"JetStream durable consumer '{durable}' cancelled")
                    break
                except Exception as exc:
                    logger.error(f"JetStream durable fetch error: {exc}", exc_info=True)
                    await asyncio.sleep(1.0)

        # Fire-and-forget: return immediately; loop runs as background task
        loop_task = asyncio.create_task(_consume_loop())
        # Keep a strong reference so the GC doesn't reap it
        self._subscriptions.add(loop_task)

    async def publish(self, subject: str, message: Any) -> None:
        """Publish a JSON-serialized message to a NATS subject.

        Args:
            subject: The NATS subject to publish to.
            message: The payload to serialize and send.
        """
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
                        "data": str(result["data"])[: NATS_MAX_MESSAGE_SIZE // 2]
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
        """Unsubscribe from all subjects and close the NATS connection."""
        import contextlib

        async with self._subscriptions_lock:
            for sub in list(self._subscriptions):
                with contextlib.suppress(Exception):
                    await sub.unsubscribe()
            self._subscriptions.clear()
        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None
            self.kv = None
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
