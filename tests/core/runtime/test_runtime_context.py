"""Tests for the RuntimeContext DI container."""

from __future__ import annotations

from pathlib import Path

from nexusagent.runtime.context import (
    RuntimeContext,
    current_context,
    set_current_context,
)


class TestRuntimeContext:
    """RuntimeContext creation and field access."""

    def test_create_minimal(self):
        """A RuntimeContext can be created with just a config."""
        ctx = RuntimeContext(config={"dummy": True})
        assert ctx.config == {"dummy": True}

    def test_create_with_all_fields(self):
        """A RuntimeContext can be created with all fields set."""
        ctx = RuntimeContext(
            config={"test": True},
            tool_initialized=True,
            current_session_id="sess-001",
            workspace_memory_dir="/tmp/mem",
            workspace_root=Path("/tmp/ws"),
            policy_context={"role": "admin"},
        )
        assert ctx.tool_initialized is True
        assert ctx.current_session_id == "sess-001"
        assert ctx.workspace_memory_dir == "/tmp/mem"
        assert ctx.workspace_root == Path("/tmp/ws")
        assert ctx.policy_context == {"role": "admin"}

    def test_defaults(self):
        """Unset fields should have their default values."""
        ctx = RuntimeContext(config={})
        assert ctx.tool_initialized is False
        assert ctx.current_session_id is None
        assert ctx.workspace_memory_dir is None
        assert ctx.workspace_root is None
        assert ctx.policy_context is None
        assert ctx.bus is None
        assert ctx.db_manager is None
        assert ctx.hook_manager is None
        assert ctx.session_manager is None
        assert ctx.worker_manager is None
        assert ctx.extra == {}

    def test_extra_dict(self):
        """Extra state dict works for extensions."""
        ctx = RuntimeContext(config={}, extra={"custom_flag": True})
        assert ctx.extra["custom_flag"] is True

    def test_context_var_current_context(self):
        """current_context() returns None when no context is set."""
        assert current_context() is None

    def test_context_var_set_and_get(self):
        """set_current_context / current_context round-trip."""
        ctx = RuntimeContext(config={"roundtrip": True})
        set_current_context(ctx)
        try:
            assert current_context() is ctx
            assert current_context().config["roundtrip"] is True
        finally:
            set_current_context(None)

    def test_context_var_clear(self):
        """Setting context to None clears it."""
        ctx = RuntimeContext(config={})
        set_current_context(ctx)
        set_current_context(None)
        assert current_context() is None

    def test_context_var_isolation(self):
        """ContextVar provides task-local isolation (not shared across tasks)."""
        ctx1 = RuntimeContext(config={"id": 1})
        ctx2 = RuntimeContext(config={"id": 2})

        set_current_context(ctx1)
        assert current_context().config["id"] == 1

        # Simulate task switch by setting different context
        set_current_context(ctx2)
        assert current_context().config["id"] == 2

        set_current_context(None)
