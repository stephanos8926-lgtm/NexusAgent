"""Task reaper — detects and marks stale PROCESSING tasks as FAILED."""
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from nexusagent.db import TaskModel, db_manager

logger = logging.getLogger(__name__)


class TaskReaper:
    """Reaps tasks stuck in PROCESSING beyond max_age."""

    def __init__(self, max_age_seconds: float = 3600, check_interval: float = 60.0):
        self.max_age = max_age_seconds
        self.check_interval = check_interval
        self._running = False

    async def start(self):
        """Start background reaper loop."""
        self._running = True
        logger.info(
            "Task reaper started (max_age=%.0fs, interval=%.0fs)",
            self.max_age,
            self.check_interval,
        )
        while self._running:
            try:
                await self._reap_once()
            except Exception as e:
                logger.error("Reaper error: %s", e)
            await asyncio.sleep(self.check_interval)

    def stop(self):
        """Stop the background reaper loop."""
        self._running = False

    async def _reap_once(self):
        """Find and mark stale PROCESSING tasks as FAILED."""
        cutoff = datetime.now(UTC) - timedelta(seconds=self.max_age)

        async with db_manager.get_session() as session:
            result = await session.execute(
                select(TaskModel).where(
                    TaskModel.status == "processing",
                    TaskModel.updated_at < cutoff,
                )
            )
            stale = result.scalars().all()

            for task in stale:
                logger.warning(
                    "Reaping zombie task %s (stale since %s)",
                    task.id,
                    task.updated_at,
                )
                task.status = "failed"
