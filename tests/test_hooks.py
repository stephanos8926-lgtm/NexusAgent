# tests/test_hooks.py
"""Tests for the NexusAgent hooks system."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.hooks import (
    HookEvent,
    HookManager,
    HookRegistration,
    get_hook_manager,
    register_hook,
    run_hooks,
    reset_hook_manager,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_hooks():
    """Reset the global hook manager before each test."""
    reset_hook_manager()
    yield
    reset_hook_manager()


@pytest.fixture
def manager():
    """Return a fresh HookManager instance."""
    return HookManager()


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with NEXUS.md and .nexusagent/hooks."""
    nexus_md = tmp_path / "NEXUS.md"
    nexus_md.write_text("# Project Context\nTest project context.\n")
    hooks_dir = tmp_path / ".nexusagent" / "hooks"
    hooks_dir.mkdir(parents=True)
    return tmp_path


# ── HookEvent enum ──────────────────────────────────────────────────────────


class TestHookEvent:
    def test_all_event_types_exist(self):
        assert HookEvent.SESSION_INIT.value == "session_init"
        assert HookEvent.POST_TOOL_USE.value == "post_tool_use"
        assert HookEvent.SUBAGENT_START.value == "subagent_start"
        assert HookEvent.SUBAGENT_STOP.value == "subagent_stop"
        assert HookEvent.ERROR.value == "error"
        assert HookEvent.USER_PROMPT_SUBMIT.value == "user_prompt_submit"

    def test_all_events_count(self):
        assert len(HookEvent) == 6


# ── HookRegistration ────────────────────────────────────────────────────────


class TestHookRegistration:
    def test_create_registration(self):
        reg = HookRegistration(
            event=HookEvent.SESSION_INIT,
            callback=lambda ctx: None,
            name="test_hook",
        )
        assert reg.event == HookEvent.SESSION_INIT
        assert reg.name == "test_hook"
        assert reg.enabled is True

    def test_disable_enable(self):
        reg = HookRegistration(
            event=HookEvent.ERROR,
            callback=lambda ctx: None,
            name="err_hook",
        )
        reg.disable()
        assert reg.enabled is False
        reg.enable()
        assert reg.enabled is True


# ── HookManager: registration ───────────────────────────────────────────────


class TestHookManager:
    def test_register_hook(self, manager):
        callback = lambda ctx: None
        manager.register_hook(HookEvent.SESSION_INIT, callback, name="init")
        assert len(manager.get_hooks(HookEvent.SESSION_INIT)) == 1

    def test_register_multiple_hooks_same_event(self, manager):
        manager.register_hook(HookEvent.ERROR, lambda ctx: None, name="err1")
        manager.register_hook(HookEvent.ERROR, lambda ctx: None, name="err2")
        hooks = manager.get_hooks(HookEvent.ERROR)
        assert len(hooks) == 2

    def test_register_hook_returns_registration(self, manager):
        reg = manager.register_hook(HookEvent.POST_TOOL_USE, lambda ctx: None, name="post")
        assert isinstance(reg, HookRegistration)
        assert reg.name == "post"

    def test_disable_hook_by_name(self, manager):
        manager.register_hook(HookEvent.ERROR, lambda ctx: None, name="err1")
        manager.register_hook(HookEvent.ERROR, lambda ctx: None, name="err2")
        manager.disable_hook("err1")
        hooks = manager.get_hooks(HookEvent.ERROR)
        assert hooks[0].enabled is False
        assert hooks[1].enabled is True

    def test_enable_hook_by_name(self, manager):
        manager.register_hook(HookEvent.ERROR, lambda ctx: None, name="err1")
        manager.disable_hook("err1")
        manager.enable_hook("err1")
        hooks = manager.get_hooks(HookEvent.ERROR)
        assert hooks[0].enabled is True

    def test_list_all_hooks(self, manager):
        manager.register_hook(HookEvent.SESSION_INIT, lambda ctx: None, name="init")
        manager.register_hook(HookEvent.ERROR, lambda ctx: None, name="err")
        all_hooks = manager.list_hooks()
        names = [h.name for h in all_hooks]
        assert "init" in names
        assert "err" in names

    def test_clear_hooks(self, manager):
        manager.register_hook(HookEvent.SESSION_INIT, lambda ctx: None, name="init")
        manager.clear()
        assert len(manager.list_hooks()) == 0

    def test_get_hooks_empty_event(self, manager):
        assert manager.get_hooks(HookEvent.ERROR) == []

    def test_disable_nonexistent_hook_raises(self, manager):
        with pytest.raises(KeyError):
            manager.disable_hook("nonexistent")

    def test_enable_nonexistent_hook_raises(self, manager):
        with pytest.raises(KeyError):
            manager.enable_hook("nonexistent")


# ── HookManager: run_hooks ──────────────────────────────────────────────────


class TestRunHooks:
    @pytest.mark.asyncio
    async def test_run_single_hook(self, manager):
        results = []

        async def my_hook(ctx):
            results.append(ctx)

        manager.register_hook(HookEvent.SESSION_INIT, my_hook, name="test")
        await manager.run_hooks(HookEvent.SESSION_INIT, {"key": "value"})
        assert len(results) == 1
        assert results[0]["key"] == "value"

    @pytest.mark.asyncio
    async def test_run_multiple_hooks_sequential(self, manager):
        order = []

        async def hook_a(ctx):
            order.append("a")

        async def hook_b(ctx):
            order.append("b")

        manager.register_hook(HookEvent.ERROR, hook_a, name="a")
        manager.register_hook(HookEvent.ERROR, hook_b, name="b")
        await manager.run_hooks(HookEvent.ERROR, {})
        assert order == ["a", "b"]

    @pytest.mark.asyncio
    async def test_disabled_hook_not_run(self, manager):
        results = []

        async def my_hook(ctx):
            results.append("ran")

        manager.register_hook(HookEvent.SESSION_INIT, my_hook, name="test")
        manager.disable_hook("test")
        await manager.run_hooks(HookEvent.SESSION_INIT, {})
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_sync_callback_works(self, manager):
        results = []

        def sync_hook(ctx):
            results.append(ctx["val"])

        manager.register_hook(HookEvent.POST_TOOL_USE, sync_hook, name="sync")
        await manager.run_hooks(HookEvent.POST_TOOL_USE, {"val": 42})
        assert results == [42]

    @pytest.mark.asyncio
    async def test_hook_error_does_not_propagate(self, manager):
        logged = []

        async def failing_hook(ctx):
            raise RuntimeError("hook failed")

        async def ok_hook(ctx):
            logged.append("ok")

        manager.register_hook(HookEvent.ERROR, failing_hook, name="bad")
        manager.register_hook(HookEvent.ERROR, ok_hook, name="good")
        # Should not raise
        await manager.run_hooks(HookEvent.ERROR, {})
        # The ok hook should still run after the failing one
        assert "ok" in logged

    @pytest.mark.asyncio
    async def test_run_no_hooks_for_event(self, manager):
        # Should not raise when no hooks registered for event
        await manager.run_hooks(HookEvent.SESSION_INIT, {})


# ── Global functions ───────────────────────────────────────────────────────


class TestGlobalFunctions:
    def test_get_hook_manager_singleton(self):
        m1 = get_hook_manager()
        m2 = get_hook_manager()
        assert m1 is m2

    def test_reset_hook_manager(self):
        m1 = get_hook_manager()
        reset_hook_manager()
        m2 = get_hook_manager()
        assert m1 is not m2

    def test_register_hook_global(self):
        reset_hook_manager()
        reg = register_hook(HookEvent.SESSION_INIT, lambda ctx: None, name="g_init")
        assert isinstance(reg, HookRegistration)

    @pytest.mark.asyncio
    async def test_run_hooks_global(self):
        reset_hook_manager()
        results = []

        async def my_hook(ctx):
            results.append(ctx["x"])

        register_hook(HookEvent.ERROR, my_hook, name="g_err")
        await run_hooks(HookEvent.ERROR, {"x": 99})
        assert results == [99]


# ── Built-in hooks ──────────────────────────────────────────────────────────


class TestBuiltinHooks:
    def test_session_init_loads_nexus_md(self, tmp_project):
        """Session init hook should find NEXUS.md content."""
        from nexusagent.hooks.builtins import session_init_load_context

        ctx = {"working_dir": str(tmp_project), "config": MagicMock()}
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(session_init_load_context(ctx))
        finally:
            loop.close()
        assert result is not None
        assert result.get("nexus_md_found") is True

    def test_post_tool_use_logs_telemetry(self):
        """Post-tool hook should log tool usage."""
        from nexusagent.hooks.builtins import post_tool_use_telemetry

        ctx = {
            "tool_name": "read_file",
            "tool_args": {"path": "test.py"},
            "tool_result": "file content",
            "session_id": "sess-1",
        }
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(post_tool_use_telemetry(ctx))
        finally:
            loop.close()
        assert result is not None
        assert result["tool_name"] == "read_file"
        assert result["logged"] is True

    def test_error_hook_logs_to_file(self, tmp_path):
        """Error hook should write error details to a log file."""
        from nexusagent.hooks.builtins import error_log_to_file

        ctx = {
            "error_message": "test error",
            "session_id": "sess-1",
            "tool_name": "read_file",
        }
        log_dir = str(tmp_path / "hook_errors")
        ctx_with_dir = {**ctx, "log_dir": log_dir}

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(error_log_to_file(ctx_with_dir))
        finally:
            loop.close()
        assert result is not None
        assert result["logged"] is True
        # Check that error log directory was created
        assert os.path.isdir(log_dir)

    def test_subagent_start_hook(self):
        """Sub-agent start hook should log lifecycle event."""
        from nexusagent.hooks.builtins import subagent_start_log

        ctx = {
            "subagent_id": "worker-1",
            "subagent_type": "explore",
            "parent_session_id": "parent-1",
            "task_description": "Explore the codebase",
        }
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(subagent_start_log(ctx))
        finally:
            loop.close()
        assert result is not None
        assert result["subagent_id"] == "worker-1"
        assert result["logged"] is True

    def test_subagent_stop_hook(self):
        """Sub-agent stop hook should log lifecycle event."""
        from nexusagent.hooks.builtins import subagent_stop_log

        ctx = {
            "subagent_id": "worker-1",
            "subagent_type": "explore",
            "parent_session_id": "parent-1",
            "status": "completed",
            "duration": 5.2,
        }
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(subagent_stop_log(ctx))
        finally:
            loop.close()
        assert result is not None
        assert result["subagent_id"] == "worker-1"
        assert result["status"] == "completed"
        assert result["logged"] is True


# ── ConfigSchema: hooks fields ──────────────────────────────────────────────


class TestHooksConfig:
    def test_hooks_config_defaults(self):
        from nexusagent.infrastructure.config import ConfigSchema

        schema = ConfigSchema()
        assert schema.hooks.hooks_enabled is True
        assert schema.hooks.hooks_dir == ".nexusagent/hooks"

    def test_hooks_config_custom(self):
        from nexusagent.infrastructure.config import ConfigSchema

        schema = ConfigSchema(hooks={"hooks_enabled": False, "hooks_dir": "custom/hooks"})
        assert schema.hooks.hooks_enabled is False
        assert schema.hooks.hooks_dir == "custom/hooks"


# ── CLI: hooks commands ────────────────────────────────────────────────────


class TestHooksCLI:
    def test_hooks_list_command(self):
        """nexus hooks list should show registered hooks."""
        from click.testing import CliRunner

        from nexusagent.interfaces.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["hooks", "list"])
        assert result.exit_code == 0
        # Should produce some output (table or list of hooks)
        assert len(result.output.strip()) > 0

    def test_hooks_enable_command(self):
        from click.testing import CliRunner

        from nexusagent.interfaces.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["hooks", "enable", "my_hook"])
        assert result.exit_code == 0
        assert "my_hook" in result.output

    def test_hooks_disable_command(self):
        from click.testing import CliRunner

        from nexusagent.interfaces.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["hooks", "disable", "my_hook"])
        assert result.exit_code == 0
        assert "my_hook" in result.output
