# src/nexusagent/sdk.py
import logging
import asyncio
import uuid
from typing import Optional, Any

from nexusagent.bus import bus
from nexusagent.models import TaskSchema, ResultSchema, TaskStatus
from nexusagent.config import settings

logger = logging.getLogger(__name__)

class NexusSDK:
    """
    High-level SDK for interacting with the NexusAgent system.
    This can be used by both the FastAPI server and external clients.
    """
    def __init__(self):
        self.bus = bus

    async def connect(self):
        """Ensure NATS connection is established."""
        if not self.bus.nc:
            await self.bus.connect()

    async def submit_task(self, task_data: dict) -> str:
        """
        Submits a task to the NATS bus.
        Returns the task ID.
        """
        await self.connect()
        
        # Assign ID if not provided
        task_id = task_data.get("id", str(uuid.uuid4()))
        task = TaskSchema(id=task_id, **task_data)
        
        logger.info(f"Submitting task {task_id}: {task.description}")
        await self.bus.publish("tasks.submit", task.model_dump())
        return task_id

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        Query the current status of a task from the database.
        """
        from nexusagent.db import task_repo
        status_str = await task_repo.get_task_status(task_id)
        if status_str:
            return TaskStatus(status_str)
        return None

    async def get_result(self, task_id: str) -> Optional[ResultSchema]:
        """
        Retrieve the result of a specific task from the JetStream KV store.
        This replaces the ephemeral subscription model to prevent resource leaks.
        """
        await self.connect()
        
        # We simply fetch the result from the KV store.
        # If the result isn't there yet, the caller can poll or use a watch.
        result_data = await self.bus.get_result(task_id)
        
        if not result_data:
            return None
            
        return ResultSchema(**result_data)

# Global SDK instance
sdk = NexusSDK()
