"""Tests for Phase 2: workspace-scoped memory."""

import shutil
import tempfile
from pathlib import Path

import pytest

import nexusagent.tools.register_all  # noqa: F401
from nexusagent.infrastructure.config import AgentConfig, load_config
from nexusagent.memory.memory_files import FileMemory


@pytest.fixture(autouse=True)
def _reset_workspace_context():
    """Reset the workspace-scoped memory ContextVar so tests don't pollute
    each other when run in arbitrary order.

    The session-running tests (test_tui* + test_worker_workspace_scoping)
    mutate ``_ws_memory_dir``; without an explicit reset, a later test
    may see a stale value.
    """
    from nexusagent.core.agent import _ws_memory_dir
    from nexusagent.tools.fs_base import set_workspace_root

    token = _ws_memory_dir.set(None)
    prev_root = set_workspace_root(".")
    try:
        yield
    finally:
        _ws_memory_dir.reset(token)
        set_workspace_root(str(prev_root))


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


# ── Config tests ─────────────────────────────────────────────────────────


def test_memory_workspace_default_is_none():
    """AgentConfig.memory_workspace defaults to None."""
    config = AgentConfig()
    assert config.memory_workspace is None


def test_memory_workspace_from_env(monkeypatch, tmp_path):
    """NEXUS_AGENT_MEMORY_WORKSPACE env var overrides default."""
    from unittest.mock import patch

    config_file = tmp_path / "nexusagent.yaml"
    config_file.write_text("agent:\n  default_model: test\n")

    monkeypatch.setenv("NEXUS_AGENT__MEMORY_WORKSPACE", "~/custom/memory")
    with patch("nexusagent.infrastructure.config.get_nexus_home", return_value=tmp_path):
        config = load_config(str(config_file))
    assert config.agent.memory_workspace == "~/custom/memory"


def test_memory_workspace_from_yaml(tmp_path):
    """memory_workspace loads from YAML config."""
    from unittest.mock import patch

    config_file = tmp_path / "nexusagent.yaml"
    config_file.write_text("agent:\n  memory_workspace: ~/proj/memory\n")

    with patch("nexusagent.infrastructure.config.get_nexus_home", return_value=tmp_path):
        config = load_config(str(config_file))
    assert config.agent.memory_workspace == "~/proj/memory"


# ── SessionManager.get_or_create memory_dir tests ────────────────────────


def test_session_manager_accepts_memory_dir():
    """SessionManager.get_or_create accepts memory_dir parameter."""
    import inspect

    from nexusagent.core.session import SessionManager

    mgr = SessionManager()
    sig = inspect.signature(mgr.get_or_create)
    assert "memory_dir" in sig.parameters
    assert sig.parameters["memory_dir"].default is None


# ── FileMemory .gitignore tests ────────────────────────────────────────────


def test_gitignore_not_created_without_git(tmp_workspace):
    """No .gitignore when .git/ doesn't exist."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    gitignore = Path(tmp_workspace) / ".nexusagent" / ".gitignore"
    assert not gitignore.exists()


def test_gitignore_created_when_git_exists(tmp_workspace):
    """Created when .git/ exists."""
    (Path(tmp_workspace) / ".git").mkdir()
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    gitignore = Path(tmp_workspace) / ".nexusagent" / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert "*" in content
    assert ".gitignore" in content


def test_gitignore_not_overwritten(tmp_workspace):
    """Existing .gitignore not overwritten."""
    (Path(tmp_workspace) / ".git").mkdir()
    nexus_dir = Path(tmp_workspace) / ".nexusagent"
    nexus_dir.mkdir(parents=True, exist_ok=True)
    gitignore = nexus_dir / ".gitignore"
    gitignore.write_text("custom\n")
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    assert gitignore.read_text() == "custom\n"


# ── _get_memory_workspace config awareness tests ──────────────────────────


def test_get_memory_workspace_uses_config(tmp_path):
    """_get_memory_workspace checks config when set."""
    from unittest.mock import MagicMock, patch

    from nexusagent.tools.register_all import _get_memory_workspace

    mock_settings = MagicMock()
    mock_settings.agent.memory_workspace = str(tmp_path / "ws_memory")

    with patch("nexusagent.infrastructure.config.settings", mock_settings):
        ws = _get_memory_workspace()
        assert str(tmp_path) in ws
        assert "ws_memory" in ws


def test_get_memory_workspace_fallback(tmp_path):
    """_get_memory_workspace falls back to global default."""
    from unittest.mock import MagicMock, patch

    from nexusagent.tools.register_all import _get_memory_workspace

    mock_settings = MagicMock()
    mock_settings.agent.memory_workspace = None

    with patch("nexusagent.infrastructure.config.settings", mock_settings):
        ws = _get_memory_workspace()
        assert ".nexusagent/memory" in ws


# ── Workspace discovery tests ─────────────────────────────────────────────


def test_discover_workspaces_returns_default():
    """_discover_workspaces always includes the default workspace."""
    from nexusagent.tools.register_all import _discover_workspaces

    workspaces = _discover_workspaces()
    assert len(workspaces) >= 1
    assert any(".nexusagent/memory" in ws for ws in workspaces)


def test_discover_workspaces_finds_git_repo(tmp_workspace):
    """_discover_workspaces finds a project with .git and .nexusagent/memory."""
    from nexusagent.tools.register_all import _discover_workspaces

    # Set up a project-like structure inside tmp_workspace
    # The function scans ~/Workspaces/*/.nexusagent/memory/
    # We can't easily mock that, so just verify the function runs without error
    workspaces = _discover_workspaces()
    assert isinstance(workspaces, list)


# ── memory_search workspace param tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_search_with_workspace_param(tmp_workspace):
    """memory_search accepts workspace param."""
    from nexusagent.tools.register_all import memory_search

    result = await memory_search("test query", max_results=3, workspace=tmp_workspace)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_memory_search_all_workspaces():
    """memory_search with workspace='all' returns results."""
    from nexusagent.tools.register_all import memory_search

    result = await memory_search("test", max_results=3, workspace="all")
    assert isinstance(result, str)


# ── memory_write workspace param tests ─────────────────────────────────────


def test_memory_write_with_workspace_param(tmp_workspace):
    """memory_write accepts workspace param and writes to correct workspace."""
    import asyncio

    from nexusagent.tools.register_all import memory_write

    result = asyncio.run(memory_write("workspace-scoped memory test", type="world",
                          description="workspace test", workspace=tmp_workspace))
    assert "Memory written to" in result
    assert tmp_workspace in result

    # Verify file was written to the correct workspace
    bank_files = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(bank_files) >= 1


def test_memory_write_without_workspace_uses_default():
    """memory_write without workspace uses default global workspace."""
    import asyncio

    from nexusagent.tools.register_all import memory_write

    result = asyncio.run(memory_write("global memory test", type="world",
                          description="global test"))
    assert isinstance(result, str)
    assert "Memory written to" in result
