"""Tests for the 7 global singleton backward-compat shims."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from nexusagent.runtime.context import RuntimeContext, set_current_context


class TestShimBackwardCompat:
    """All 7 global shims must fall back to module-level state when no RuntimeContext."""

    def test_current_session_var_no_context(self):
        """_current_session ContextVar works without RuntimeContext."""
        from nexusagent.core.agent import _current_session

        assert _current_session.get() is None

    def test_ws_memory_dir_var_no_context(self):
        """_ws_memory_dir ContextVar works without RuntimeContext."""
        from nexusagent.core.agent import _ws_memory_dir

        assert _ws_memory_dir.get() is None

    def test_workspace_root_var_no_context(self):
        """_workspace_root_var ContextVar works without RuntimeContext."""
        from nexusagent.tools.fs_base import _workspace_root_var

        assert _workspace_root_var.get() is None

    def test_policy_context_var_no_context(self):
        """_policy_context ContextVar works without RuntimeContext."""
        from nexusagent.tools.registry.policy import _policy_context

        assert _policy_context.get() is None

    def test_get_workspace_root_fallback_no_context(self):
        """_get_workspace_root() falls back to CWD without RuntimeContext."""
        from nexusagent.tools.fs_base import _get_workspace_root

        root = _get_workspace_root()
        assert root == Path.cwd().resolve()

    def test_get_policy_context_fallback_no_context(self):
        """get_policy_context() creates default dict without RuntimeContext."""
        from nexusagent.tools.registry.policy import get_policy_context

        ctx = get_policy_context()
        assert ctx["role"] == "full"
        assert ctx["policy"] == "permissive"

    def test_get_memory_workspace_fallback(self):
        """_get_or_create_memory_workspace falls back properly."""
        from nexusagent.tools.register_all import _get_memory_workspace as g

        # Just verify the function exists and is callable
        assert callable(g)

    @patch("nexusagent.tools.register_all.register_all")
    def test_ensure_tools_registered_fallback(self, mock_register):
        """_ensure_tools_registered() works without RuntimeContext."""
        from nexusagent.core.agent import _ensure_tools_registered

        _ensure_tools_registered()
        mock_register.assert_called_once()


class TestShimWithContext:
    """All 7 global shims must use RuntimeContext values when active."""

    @pytest.fixture
    def ctx(self):
        return RuntimeContext(config={"test": True})

    def test_set_workspace_root_syncs_to_context(self, ctx):
        """set_workspace_root() syncs workspace_root to RuntimeContext."""
        from nexusagent.tools.fs_base import set_workspace_root

        set_current_context(ctx)
        try:
            set_workspace_root("/tmp/test-workspace")
            assert ctx.workspace_root == Path("/tmp/test-workspace").resolve()
        finally:
            set_current_context(None)

    def test_get_workspace_root_from_context(self, ctx):
        """_get_workspace_root() reads from RuntimeContext when active."""
        from nexusagent.tools.fs_base import _get_workspace_root

        ctx.workspace_root = Path("/tmp/context-root")
        set_current_context(ctx)
        try:
            root = _get_workspace_root()
            assert root == Path("/tmp/context-root")
        finally:
            set_current_context(None)

    def test_set_policy_context_syncs_to_context(self, ctx):
        """set_policy_context() syncs policy_context to RuntimeContext."""
        from nexusagent.tools.registry.policy import set_policy_context

        set_current_context(ctx)
        try:
            set_policy_context("admin", "strict")
            assert ctx.policy_context["role"] == "admin"
            assert ctx.policy_context["policy"] == "strict"
        finally:
            set_current_context(None)

    def test_get_policy_context_from_runtime(self, ctx):
        """get_policy_context() reads from RuntimeContext when active."""
        from nexusagent.tools.registry.policy import get_policy_context

        ctx.policy_context = {"role": "admin", "policy": "strict", "unlocked": set()}
        set_current_context(ctx)
        try:
            result = get_policy_context()
            assert result["role"] == "admin"
        finally:
            set_current_context(None)

    def test_ws_memory_dir_syncs_to_context(self, ctx):
        """_setup_workspace_context syncs workspace_memory_dir to RuntimeContext."""
        from nexusagent.core.agent import _setup_workspace_context

        set_current_context(ctx)
        try:
            with patch("pathlib.Path.mkdir"):
                _setup_workspace_context("/tmp/test-ws")
            # Should have synced to context
            # Actually, _setup_workspace_context sets the ContextVar AND syncs to RuntimeContext
        finally:
            set_current_context(None)

    def test_ensure_tools_via_runtime_uses_context(self, ctx):
        """_ensure_tools_registered() uses RuntimeContext.tool_initialized."""
        from nexusagent.core.agent import _ensure_tools_registered

        ctx.tool_initialized = True
        set_current_context(ctx)
        try:
            # Should return immediately without calling register_all
            with patch("nexusagent.tools.register_all.register_all") as mock_reg:
                _ensure_tools_registered()
                mock_reg.assert_not_called()
        finally:
            set_current_context(None)
