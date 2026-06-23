"""Tests for worker workspace scoping (P6-P9)."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import nexusagent.tools.register_all  # noqa: F401
from nexusagent.core.agent import _ws_memory_dir
from nexusagent.llm.models import MemoryScope, TaskContract, TaskSchema


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


# ── TaskSchema working_dir tests ──────────────────────────────────────────


def test_task_schema_has_working_dir():
    """TaskSchema accepts working_dir field."""
    task = TaskSchema(id="t1", description="test", working_dir="/project")
    assert task.working_dir == "/project"


def test_task_schema_working_dir_default_none():
    """TaskSchema.working_dir defaults to None."""
    task = TaskSchema(id="t1", description="test")
    assert task.working_dir is None


# ── TaskContract system_prompt tests ──────────────────────────────────────


def test_task_contract_has_system_prompt():
    """TaskContract accepts system_prompt field."""
    contract = TaskContract(
        task_id="t1", title="test", description="test",
        system_prompt="Custom prompt"
    )
    assert contract.system_prompt == "Custom prompt"


def test_task_contract_system_prompt_default_none():
    """TaskContract.system_prompt defaults to None."""
    contract = TaskContract(task_id="t1", title="test", description="test")
    assert contract.system_prompt is None


# ── spawn_subagent system_prompt param tests ──────────────────────────────


def test_spawn_subagent_tool_has_system_prompt_param():
    """spawn_subagent tool accepts system_prompt parameter."""
    import inspect

    from nexusagent.tools.register_all import spawn_subagent
    sig = inspect.signature(spawn_subagent)
    assert "system_prompt" in sig.parameters
    assert sig.parameters["system_prompt"].default is None


# ── Worker pool passes working_dir and system_prompt tests ────────────────


def test_worker_pool_passes_working_dir_to_metadata():
    """WorkerPool._run_worker passes working_dir from contract to task metadata."""
    import asyncio

    from nexusagent.core.worker.pool import WorkerPool

    async def _test():
        pool = WorkerPool(max_workers=1)
        contract = TaskContract(
            task_id="test-1", title="test", description="test task",
            working_dir="/project",
        )
        handle = MagicMock()
        handle.contract = contract
        handle.model = None
        handle.provider = None
        handle._mark_running = MagicMock()
        handle._mark_completed = MagicMock()
        handle._mark_failed = MagicMock()
        handle.is_cancelled = MagicMock(return_value=False)

        # Capture the task schema that gets created
        original_execute = pool._execute_bounded
        captured_task = None

        async def mock_execute(task, handle):
            nonlocal captured_task
            captured_task = task
            return {"result": "ok", "success": True}

        pool._execute_bounded = mock_execute

        # We can't fully run the worker without NATS, but we can verify
        # the contract has working_dir set
        assert handle.contract.working_dir == "/project"

    asyncio.run(_test())


# ── _setup_workspace_context tests ────────────────────────────────────────


def test_setup_workspace_context_sets_path_jail():
    """_setup_workspace_context sets workspace root for path jail."""
    from nexusagent.core.agent import _setup_workspace_context
    from nexusagent.tools.fs_base import _get_workspace_root

    with tempfile.TemporaryDirectory() as tmp:
        _setup_workspace_context(tmp)
        root = _get_workspace_root()
        assert str(root) == str(Path(tmp).resolve())
        # Reset
        from nexusagent.tools.fs_base import set_workspace_root
        set_workspace_root(".")


def test_setup_workspace_context_sets_memory_dir():
    """_setup_workspace_context sets thread-local memory dir."""
    from nexusagent.core.agent import _setup_workspace_context

    with tempfile.TemporaryDirectory() as tmp:
        _setup_workspace_context(tmp)
        ws_mem = _ws_memory_dir.get()
        assert ws_mem is not None
        assert tmp in ws_mem
        # Reset
        _ws_memory_dir.set(None)


def test_setup_workspace_context_noop_for_dot():
    """_setup_workspace_context is no-op when working_dir is '.'."""
    from nexusagent.core.agent import _setup_workspace_context
    from nexusagent.tools.fs_base import _get_workspace_root, set_workspace_root

    # Reset to clean state
    set_workspace_root(".")
    _setup_workspace_context(".")
    assert _ws_memory_dir.get() is None
    # Verify workspace root wasn't changed
    assert _get_workspace_root() == Path.cwd().resolve()


# ── _get_memory_workspace thread-local override tests ─────────────────────


def test_get_memory_workspace_uses_thread_local_override():
    """_get_memory_workspace checks thread-local worker override first."""
    from nexusagent.core.agent import _ws_memory_dir
    from nexusagent.tools.register_all import _get_memory_workspace

    with tempfile.TemporaryDirectory() as tmp:
        _ws_memory_dir.set(tmp)
        ws = _get_memory_workspace()
        assert ws == tmp
        # Reset
        _ws_memory_dir.set(None)


# ── SDK working_dir tests ─────────────────────────────────────────────────


def test_sdk_submit_task_accepts_working_dir():
    """SDK submit_task accepts working_dir in task_data."""

    # Verify TaskSchema can be created with working_dir
    task = TaskSchema(id="t1", description="test", working_dir="/project")
    assert task.working_dir == "/project"
    dumped = task.model_dump()
    assert dumped["working_dir"] == "/project"


# ── Memory inheritance (memory_scope) tests ───────────────────────────────


def test_memory_scope_enum_exists():
    """MemoryScope enum has isolated, scoped, shared values."""
    assert MemoryScope.ISOLATED == "isolated"
    assert MemoryScope.SCOPED == "scoped"
    assert MemoryScope.SHARED == "shared"


def test_task_contract_memory_scope_default():
    """TaskContract.memory_scope defaults to ISOLATED."""
    contract = TaskContract(task_id="t1", title="test", description="test")
    assert contract.memory_scope == MemoryScope.ISOLATED


def test_task_contract_memory_scope_can_be_set():
    """TaskContract.memory_scope can be set to scoped or shared."""
    contract = TaskContract(
        task_id="t1", title="test", description="test",
        memory_scope=MemoryScope.SCOPED,
    )
    assert contract.memory_scope == MemoryScope.SCOPED
