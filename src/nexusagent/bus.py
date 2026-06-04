# src/nexusagent/bus.py
import json
import logging
from typing import Any, Callable, Awaitable, Optional

import nats
from nats.aio.client import Client as NATSClient
from nats.errors import Error as NATSError
from nats.js.api import JetStreamContext, KeyValue

from nexusagent.config import settings

logger = logging.getLogger(__name__)

class NATSBus:
    def __init__(self) -> None:
        self.url = settings.server.nats_url
        self.nc: Optional[NATSClient] = None
        self.js: Optional[JetStreamContext] = None
        self.kv: Optional[KeyValue] = None

    async def connect(self) -> None:
        """
        Connect to the NATS server with automatic reconnection and initialize JetStream KV.
        """
        try:
            self.nc = await nats.connect(
                self.url, 
                reconnect_time_wait=settings.server.nats_reconnect_wait, 
                max_reconnect_attempts=settings.server.nats_max_reconnects,
                allow_reconnect_attempts=True
            )
            logger.info(f"Connected to NATS at {self.url}")
            
            self.js = self.nc.jetstream()
            self.kv = await self.js.create_key_value(bucket="nexus_results")
            logger.info("JetStream KV bucket 'nexus_results' initialized.")
            
        except NATSError as e:
            logger.error(f"Could not connect to NATS: {e}")
            raise

    async def publish(self, subject: str, message: Any) -> None:
        """
        Publish a JSON-encoded message to a NATS subject.
        """
        if not self.nc:
            raise RuntimeError("NATSBus not connected. Call connect() first.")
        
        try:
            payload = json.dumps(message).encode()
            await self.nc.publish(subject, payload)
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            raise

    async def subscribe(self, subject: str, callback: Callable[[str, bytes], Awaitable[None]]) -> None:
        """
        Subscribe to a NATS subject with a provided async callback.
        """
        if not self.nc:
            raise RuntimeError("NATSBus not connected. Call connect() first.")
        
        await self.nc.subscribe(subject, cb=callback)
        logger.info(f"Subscribed to {subject}")

    async def put_result(self, key: str, value: Any) -> None:
        """
        Store a result in the JetStream KV store.
        """
        if not self.kv:
            raise RuntimeError("KV store not initialized. Call connect() first.")
        
        try:
            payload = json.dumps(value).encode()
            await self.kv.put(key, payload)
        except Exception as e:
            logger.error(f"Failed to put key {key} into KV store: {e}")
            raise

    async def get_result(self, key: str) -> Optional[Any]:
        """
        Retrieve a result from the JetStream KV store.
        """
        if not self.kv:
            raise RuntimeError("KV store not initialized. Call connect() first.")
        
        try:
            entry = await self.kv.get(key)
            if entry:
                return json.loads(entry.value.decode())
            return None
        except Exception as e:
            logger.error(f"Failed to get key {key} from KV store: {e}")
            return None

    async def close(self) -> None:
        if self.nc:
            await self.nc.close()
        logger.info("NATS connection closed.")

# Global singleton bus instance
bus = NATSBus()
