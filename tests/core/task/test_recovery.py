"""Tests for RecoveryManager retry, backoff, and rollback logic."""

import time

import pytest

from nexusagent.core.task.checkpoint import Checkpoint
from nexusagent.core.task.recovery import PermanentFailureError, RecoveryManager
from nexusagent.core.task.task_state import Task, TaskState
from nexusagent.core.task.task_store import TaskStore
from nexusagent.infrastructure.db.manager import DatabaseManager


@pytest.fixture
async def temp_db_store():
    """Create a temporary in-memory SQLite database manager and TaskStore."""
    db_manager = DatabaseManager(db_url="sqlite+aiosqlite:///:memory:")
    await db_manager.init_db()
    store = TaskStore(db_manager=db_manager)
    await store.init_tables()
    yield store
    await db_manager.close()


@pytest.mark.anyio
async def test_recovery_success_on_first_retry(temp_db_store):
    """Verify recovery transitions and successful resume on the first retry attempt."""
    task = Task(id="task-rec-1", objective="Retry goal", owner="Tester", state=TaskState.FAILED)
    await temp_db_store.save_task(task)

    checkpoint = Checkpoint(current_node="node-checkpoint", next_action="resume-action")
    await temp_db_store.save_checkpoint("task-rec-1", checkpoint)

    calls = []

    async def mock_execute(t, cp):
        calls.append((t.state, cp))
        return "Success result"

    recovery_mgr = RecoveryManager(temp_db_store)
    result = await recovery_mgr.recover_task(
        task_id="task-rec-1",
        execute_fn=mock_execute,
        max_attempts=1,
        delays=[0.01],
    )

    assert result == "Success result"
    assert len(calls) == 1
    assert calls[0][0] == TaskState.EXECUTING
    assert calls[0][1].current_node == "node-checkpoint"

    # Verify task state is now COMPLETED
    loaded_task = await temp_db_store.load_task("task-rec-1")
    assert loaded_task.state == TaskState.COMPLETED


@pytest.mark.anyio
async def test_recovery_permanent_failure_and_escalate(temp_db_store):
    """Verify permanent failure and escalation on hitting retry limit."""
    task = Task(id="task-rec-2", objective="Retry goal", owner="Tester", state=TaskState.FAILED)
    await temp_db_store.save_task(task)

    async def mock_execute_fail(t, cp):
        raise RuntimeError("Persistent crash")

    emitted_events = []

    async def mock_failed_event(task_id, error):
        emitted_events.append((task_id, error))

    recovery_mgr = RecoveryManager(temp_db_store)

    with pytest.raises(PermanentFailureError, match="permanently failed after 3 recovery attempts"):
        await recovery_mgr.recover_task(
            task_id="task-rec-2",
            execute_fn=mock_execute_fail,
            max_attempts=3,
            delays=[0.01, 0.01, 0.01],
            on_failed_event=mock_failed_event,
        )

    # Verify task state remained FAILED
    loaded_task = await temp_db_store.load_task("task-rec-2")
    assert loaded_task.state == TaskState.FAILED

    # Verify escalation event was emitted
    assert len(emitted_events) == 1
    assert emitted_events[0][0] == "task-rec-2"
    assert "permanently failed" in emitted_events[0][1]


@pytest.mark.anyio
async def test_recovery_backoff_retry_delay_order(temp_db_store):
    """Verify that recovery manager waits with exponential delays."""
    task = Task(id="task-rec-3", objective="Retry goal", owner="Tester", state=TaskState.FAILED)
    await temp_db_store.save_task(task)

    call_count = 0

    async def mock_execute(t, cp):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Temporary error")
        return "Recovered on attempt 3"

    start_time = time.time()

    recovery_mgr = RecoveryManager(temp_db_store)
    result = await recovery_mgr.recover_task(
        task_id="task-rec-3",
        execute_fn=mock_execute,
        max_attempts=3,
        delays=[0.05, 0.1, 0.2],
    )

    elapsed = time.time() - start_time
    assert result == "Recovered on attempt 3"
    assert call_count == 3
    # Sum of delays = 0.05 + 0.1 = 0.15s, so total elapsed should be at least 0.15s
    assert elapsed >= 0.15
