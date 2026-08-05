# SPDX-License-Identifier: MIT

# src/nexusagent/core/observability/chaos.py
"""Chaos testing framework for introducing system failures and verifying resilience."""

from __future__ import annotations

import logging

from nexusagent.core.task.task_store import get_task_store
from nexusagent.core.worker.pool import get_worker_pool
from nexusagent.infrastructure.bus import get_bus

logger = logging.getLogger(__name__)


class ChaosTestFramework:
    """Intentionally injects and simulates system failures to test recovery and resilience.

    Scenarios:
    - Kill worker during execution
    - Disconnect event bus
    - Corrupt checkpoint
    """

    @staticmethod
    def kill_worker(worker_id: str) -> bool:
        """Simulate a worker crash by cancelling its execution task.

        Expected Behavior: Task resumes on next iteration or gets recovered.
        """
        pool = get_worker_pool()
        logger.warning("CHAOS: Requesting termination of worker %s", worker_id)
        if worker_id in pool._active:
            handle = pool._active[worker_id]
            handle.cancel()
            return True
        return False

    @staticmethod
    async def disconnect_event_bus() -> None:
        """Simulate event bus disconnect by closing NATS connection.

        Expected Behavior: System reconnects safely or handles failures gracefully.
        """
        logger.warning("CHAOS: Disconnecting event bus NATS")
        bus = get_bus()
        if bus:
            await bus.close()

    @staticmethod
    async def corrupt_checkpoint(task_id: str) -> None:
        """Corrupt stored task checkpoint to trigger recovery failure.

        Expected Behavior: Recovery failure is detected by RecoveryManager.
        """
        logger.warning("CHAOS: Corrupting checkpoint for task %s", task_id)
        store = get_task_store()
        task = await store.load_task(task_id)
        if task:
            # Replace checkpoints with corrupted entries
            from nexusagent.core.task.task_state import Checkpoint

            corrupt_cp = Checkpoint(
                current_node="CORRUPTED_BY_CHAOS",
                completed_actions=["invalid"],
                tool_results=[{"corrupted": True}],
                next_action="invalid",
            )
            task.checkpoints = [corrupt_cp]
            await store.save_task(task)
