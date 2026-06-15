"""File system base — shared utilities for fs.py and editor.py."""

from __future__ import annotations

from pathlib import Path

# Track files read in the current session (module-level state)
_read_files: set[str] = set()

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

# Workspace root — all file operations are jailed to this directory
_WORKSPACE_ROOT: Path | None = None


def set_workspace_root(path: str) -> None:
    """Set the workspace root directory for path jail."""
    global _WORKSPACE_ROOT
    _WORKSPACE_ROOT = Path(path).resolve()


def _get_workspace_root() -> Path:
    """Get the workspace root, defaulting to CWD if not set."""
    if _WORKSPACE_ROOT is not None:
        return _WORKSPACE_ROOT
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
    if resolved not in _read_files:
        raise PermissionError(
            f"SAFETY: File '{path}' has not been read in this session. "
            f"Call read_file() first to understand the file's contents before modifying it."
        )


def _mark_read(path: str) -> None:
    """Mark a file as read in session tracking."""
    _read_files.add(str(path))


def get_read_files() -> list[str]:
    """Return list of files that have been read in this session."""
    return sorted(_read_files)


def reset_read_tracking() -> None:
    """Reset the read-file tracking. Use when starting a new task/session."""
    _read_files.clear()
