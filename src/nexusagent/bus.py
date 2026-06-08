import asyncio
import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.subscription import Subscription
from nats.errors import Error as NATSError

from nexusagent.config import settings

logger = logging.getLogger(__name__)


class NATSJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
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

    async def publish(self, subject: str, message: Any) -> None:
        if not self.nc:
            raise RuntimeError("NATSBus not connected. Call connect() first.")
        try:
            payload = json.dumps(message, cls=NATSJSONEncoder).encode()
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


# Singleton instance for the project
bus = AgentBus()
