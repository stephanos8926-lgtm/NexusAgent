"""File system base — shared utilities for fs.py and editor.py."""

from __future__ import annotations

from pathlib import Path

# Track files read in the current session (context-local for session isolation)
import contextvars

_read_files_var: contextvars.ContextVar[set[str]] = contextvars.ContextVar(
    "read_files", default=set()
)


def _get_read_files() -> set[str]:
    """Get the read-files set for the current context."""
    return _read_files_var.get()

# Default directory excludes for list_directory
_DEFAULT_DIR_EXCLUDES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".eggs",
        "*.egg-info",
    }
)

# Workspace root — all file operations are jailed to this directory.
#
# MUST be a ContextVar, not a plain global. WorkerPool runs up to
# `max_workers` subagents concurrently in the same process via
# asyncio.create_task() (see core/worker/pool.py). A plain global here
# means whichever concurrent worker calls set_workspace_root() last wins
# for *every* task in the process — including the main interactive
# session — causing ls/glob to silently jail to the wrong directory and
# legitimate paths to trip the traversal guard. ContextVar is copied at
# task-creation boundaries, so each asyncio task gets its own isolated
# value and writes never leak across concurrent workers.
_workspace_root_var: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "workspace_root", default=None
)


def set_workspace_root(path: str) -> None:
    """Set the workspace root directory for path jail (current task only)."""
    _workspace_root_var.set(Path(path).resolve())


def _get_workspace_root() -> Path:
    """Get the workspace root for the current task, defaulting to CWD if unset."""
    root = _workspace_root_var.get()
    if root is not None:
        return root
    return Path.cwd().resolve()


def _resolve(path: str) -> Path:
    """Resolve a path and return absolute Path, ensuring it's within workspace jail."""
    raw = Path(path)
    resolved = raw.resolve() if raw.is_absolute() else (_get_workspace_root() / raw).resolve()

    # Path jail: ensure the resolved path is within the workspace root
    workspace = _get_workspace_root()
    try:
        resolved.relative_to(workspace)
    except ValueError as e:
        raise PermissionError(
            f"SAFETY: Path '{path}' resolves to '{resolved}' which is outside "
            f"the workspace root '{workspace}'. File operations are jailed to "
            f"the workspace directory."
        ) from e
    return resolved


def _check_read(path: str) -> None:
    """Raise if the file hasn't been read in this session."""
    resolved = str(_resolve(path))
    if resolved not in _get_read_files():
        raise PermissionError(
            f"SAFETY: File '{path}' has not been read in this session. "
            f"Call read_file() first to understand the file's contents before modifying it."
        )


def _mark_read(path: str) -> None:
    """Mark a file as read in session tracking."""
    _get_read_files().add(str(path))


def get_read_files() -> list[str]:
    """Return list of files that have been read in this session."""
    return sorted(_get_read_files())


def reset_read_tracking() -> None:
    """Reset the read-file tracking. Use when starting a new task/session."""
    _get_read_files().clear()


def __getattr__(name: str):
    """PEP 562 module-level dynamic attribute access.

    Preserves backward compatibility for ``from fs_base import _WORKSPACE_ROOT``
    (and the re-export in fs.py) now that the value lives in a ContextVar
    rather than a plain global. Always returns the *current* task's value
    instead of a stale snapshot.
    """
    if name == "_WORKSPACE_ROOT":
        return _workspace_root_var.get()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
