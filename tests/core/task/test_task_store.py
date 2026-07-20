"""Tests for SQLite database TaskStore persistence operations."""

import pytest

from nexusagent.core.task.checkpoint import Checkpoint
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
async def test_save_and_load_task(temp_db_store):
    """Verify task can be saved and loaded from the database."""
    task = Task(id="task-123", objective="Compile app", owner="Tester")
    await temp_db_store.save_task(task)

    loaded = await temp_db_store.load_task("task-123")
    assert loaded is not None
    assert loaded.id == "task-123"
    assert loaded.objective == "Compile app"
    assert loaded.owner == "Tester"
    assert loaded.state == TaskState.CREATED
    assert loaded.checkpoints == []


@pytest.mark.anyio
async def test_update_task_state(temp_db_store):
    """Verify task state changes are persisted successfully."""
    task = Task(id="task-456", objective="Compile app", owner="Tester")
    await temp_db_store.save_task(task)

    task.transition_to(TaskState.PLANNING)
    await temp_db_store.save_task(task)

    loaded = await temp_db_store.load_task("task-456")
    assert loaded.state == TaskState.PLANNING


@pytest.mark.anyio
async def test_list_tasks(temp_db_store):
    """Verify list_tasks filtering by state works correctly."""
    task1 = Task(id="task-a", objective="Obj A", owner="O", state=TaskState.CREATED)
    task2 = Task(id="task-b", objective="Obj B", owner="O", state=TaskState.EXECUTING)
    await temp_db_store.save_task(task1)
    await temp_db_store.save_task(task2)

    all_tasks = await temp_db_store.list_tasks()
    assert len(all_tasks) == 2

    executing_tasks = await temp_db_store.list_tasks(TaskState.EXECUTING)
    assert len(executing_tasks) == 1
    assert executing_tasks[0].id == "task-b"


@pytest.mark.anyio
async def test_save_and_load_latest_checkpoint(temp_db_store):
    """Verify checkpoint persistence operations work correctly."""
    task = Task(id="task-789", objective="Verify DB", owner="Tester")
    await temp_db_store.save_task(task)

    cp1 = Checkpoint(
        current_node="node-1",
        completed_actions=["act-1"],
        files_changed=["a.txt"],
        tool_results=[],
        next_action="act-2",
    )
    await temp_db_store.save_checkpoint("task-789", cp1)

    cp2 = Checkpoint(
        current_node="node-2",
        completed_actions=["act-1", "act-2"],
        files_changed=["a.txt", "b.txt"],
        tool_results=[{"success": True}],
        next_action="act-3",
    )
    await temp_db_store.save_checkpoint("task-789", cp2)

    loaded_cp = await temp_db_store.load_latest_checkpoint("task-789")
    assert loaded_cp is not None
    assert loaded_cp.current_node == "node-2"
    assert loaded_cp.completed_actions == ["act-1", "act-2"]
    assert loaded_cp.files_changed == ["a.txt", "b.txt"]
    assert loaded_cp.tool_results == [{"success": True}]
    assert loaded_cp.next_action == "act-3"

    # Verify task's internal checkpoints list got updated in DB as well
    loaded_task = await temp_db_store.load_task("task-789")
    assert len(loaded_task.checkpoints) == 2
    assert loaded_task.checkpoints[1].current_node == "node-2"
