"""File system tools for NexusAgent.

Provides read, write, edit, and directory listing with safety constraints:
- read_file: tracks files read in session, supports line ranges
- write_file: full file replacement, requires read-first for existing files
- edit_file: surgical line-range edit (re-exported from tools.editor)
- list_directory: recursive tree with depth limit and glob filtering
"""

from __future__ import annotations

from pathlib import Path

from nexusagent.tools import fs_base as _fs_base

# Re-export edit_file from the editor subpackage for backward compatibility
# Shared utilities from fs_base (single source of truth)
from nexusagent.tools.fs_base import (
    _DEFAULT_DIR_EXCLUDES,
    _check_read,
    _get_read_files,
    _resolve,
    get_read_files,
    reset_read_tracking,
)


def __getattr__(name: str):
    """PEP 562 re-export of _WORKSPACE_ROOT — see fs_base.__getattr__.

    Not a static import: _WORKSPACE_ROOT now lives in a per-task
    ContextVar, so this must delegate live rather than freeze a
    snapshot taken at fs.py's import time.
    """
    if name == "_WORKSPACE_ROOT":
        return _fs_base._workspace_root_var.get()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def read_file(path: str, offset: int = 1, limit: int | None = None) -> str:
    """Read a file's contents with optional line-range selection.

    Args:
        path: File path (absolute or relative)
        offset: Starting line number (1-indexed, default: 1 = beginning)
        limit: Maximum number of lines to read (None = read to end)

    Returns:
        File content as string. When reading the full file (default), returns
        raw content for backward compatibility. When using line-range selection,
        returns content with line numbers prepended for reference.

    Side effect: Marks file as read in session tracking.
    """
    p = _resolve(path)

    if not p.exists():
        return f"Error: File '{path}' does not exist"
    if not p.is_file():
        return f"Error: '{path}' is not a file"

    # Mark as read
    _get_read_files().add(str(p))

    content = p.read_text(encoding="utf-8", errors="replace")

    # If reading the full file (default), return raw content
    if offset == 1 and limit is None:
        return content

    # Line-range mode: return with line numbers
    lines = content.splitlines()
    total_lines = len(lines)

    start = max(1, offset) - 1  # convert to 0-indexed
    end = start + limit if limit is not None else total_lines

    selected = lines[start:end]

    result_lines = []
    for i, line in enumerate(selected):
        line_num = start + i + 1  # 1-indexed
        result_lines.append(f"{line_num}|{line}")

    header = f"File: {p} (lines {start + 1}-{start + len(selected)} of {total_lines})\n"
    return header + "\n".join(result_lines)


def read_multiple_files(paths: list[str]) -> dict[str, str]:
    """Read multiple files. Each file is marked as read."""
    results = {}
    for path in paths:
        results[path] = read_file(path)
    return results


def write_file(path: str, content: str) -> str:
    """Write content to a file (full replacement).

    Safety: If the file already exists, it MUST have been read in this session first.
    New files can be created without prior read.

    Args:
        path: File path
        content: Full file content to write

    Returns:
        Success message
    """
    p = _resolve(path)

    if p.exists():
        _check_read(path)

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

    # Mark as read since we just wrote it
    _get_read_files().add(str(p))

    return f"Successfully wrote {len(content)} bytes to {path}"


def list_directory(
    path: str,
    recursive: bool = False,
    max_depth: int = 2,
    pattern: str | None = None,
    exclude: list[str] | None = None,
) -> dict:
    """List directory contents as a nested tree.

    Args:
        path: Directory path
        recursive: Whether to recurse into subdirectories
        max_depth: Maximum recursion depth (default: 2)
        pattern: Optional glob pattern to filter files (e.g., "*.py", "*.md")
        exclude: List of directory names to exclude (default: ['.git', '__pycache__', 'node_modules', '.venv', 'venv'])

    Returns:
        Nested dict: {"dirname": {"subdir": {...}, "file.py": "file"}, "file.txt": "file"}
    """
    p = _resolve(path)
    if not p.exists() or not p.is_dir():
        return {}

    excludes = set(exclude) if exclude else _DEFAULT_DIR_EXCLUDES

    def _should_exclude(name: str) -> bool:
        return name in excludes

    def _build_tree(current: Path, depth: int) -> dict:
        tree = {}
        if depth > max_depth:
            return tree

        try:
            items = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return {"<permission denied>": "directory"}

        for item in items:
            if _should_exclude(item.name):
                continue

            if item.is_dir():
                if recursive:
                    subtree = _build_tree(item, depth + 1)
                    if subtree:
                        tree[item.name] = subtree
                else:
                    tree[item.name] = "directory"
            else:
                if pattern is None or item.match(pattern):
                    tree[item.name] = "file"

        return tree

    return _build_tree(p, 0)


def write_multiple_files(files: dict[str, str]) -> str:
    """Writes multiple files with a safety check."""
    for path, content in files.items():
        write_file(path, content)
    return f"Successfully wrote {len(files)} files"

