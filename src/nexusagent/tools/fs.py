"""
File system tools for NexusAgent.

Provides read, write, edit, and directory listing with safety constraints:
- read_file: tracks files read in session, supports line ranges
- write_file: full file replacement, requires read-first for existing files
- edit_file: surgical line-range edit, requires read-first + validates old_text location
- list_directory: recursive tree with depth limit and glob filtering
"""

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
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        resolved = (_get_workspace_root() / raw).resolve()

    # Path jail: ensure the resolved path is within the workspace root
    workspace = _get_workspace_root()
    try:
        resolved.relative_to(workspace)
    except ValueError:
        raise PermissionError(
            f"SAFETY: Path '{path}' resolves to '{resolved}' which is outside "
            f"the workspace root '{workspace}'. File operations are jailed to "
            f"the workspace directory."
        )
    return resolved


def _check_read(path: str) -> None:
    """Raise if the file hasn't been read in this session."""
    resolved = str(_resolve(path))
    if resolved not in _read_files:
        raise PermissionError(
            f"SAFETY: File '{path}' has not been read in this session. "
            f"Call read_file() first to understand the file's contents before modifying it."
        )


def read_file(path: str, offset: int = 1, limit: int | None = None) -> str:
    """
    Read a file's contents with optional line-range selection.

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
    _read_files.add(str(p))

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
    """
    Write content to a file (full replacement).

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
    _read_files.add(str(p))

    return f"Successfully wrote {len(content)} bytes to {path}"


def edit_file(
    path: str,
    old_text: str,
    new_text: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """
    Perform a surgical edit on a file.

    Replaces `old_text` with `new_text` in the specified line range.
    If no line range is specified, searches the entire file.

    Safety requirements:
    1. File MUST have been read in this session
    2. `old_text` MUST exist in the specified range (or entire file if no range)
    3. If line range is specified, `old_text` MUST start within that range

    This prevents hallucinated edits — the agent must have read the file
    and must specify exactly what it's replacing.

    Args:
        path: File path
        old_text: Exact text to find and replace (must match exactly)
        new_text: Replacement text
        start_line: Optional start line (1-indexed) to constrain search
        end_line: Optional end line (1-indexed) to constrain search

    Returns:
        Success message with details of the edit
    """
    p = _resolve(path)

    if not p.exists():
        return f"Error: File '{path}' does not exist"

    _check_read(path)

    content = p.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Determine search range
    if start_line is not None or end_line is not None:
        s = (start_line or 1) - 1  # 0-indexed
        e = end_line or len(lines)  # exclusive
        s = max(0, s)
        e = min(len(lines), e)

        # Build the search text from the specified range
        range_text = "\n".join(lines[s:e])

        if old_text not in range_text:
            # Provide helpful context: show what's actually in the range
            preview = range_text[:500]
            return (
                f"Error: old_text not found in lines {s + 1}-{e} of '{path}'. "
                f"Content preview:\n{preview}"
            )

        # Verify old_text starts within the range (not just overlaps)
        # Find the position of old_text in the full content
        range_start_offset = sum(len(line) + 1 for line in lines[:s])  # +1 for newlines
        pos = content.find(old_text, range_start_offset)

        if pos == -1:
            return f"Error: Could not locate old_text in '{path}'"

        # Check that the found position is within the range
        line_at_pos = content[:pos].count("\n")
        if line_at_pos < s or line_at_pos >= e:
            return (
                f"Error: old_text found at line {line_at_pos + 1}, "
                f"which is outside the specified range {s + 1}-{e}"
            )

        # Perform the replacement
        new_content = content[:pos] + new_text + content[pos + len(old_text) :]
    else:
        # Search entire file
        if old_text not in content:
            preview = content[:500]
            return f"Error: old_text not found in '{path}'. Content preview:\n{preview}"

        # Count occurrences
        count = content.count(old_text)
        if count > 1:
            return (
                f"Error: old_text appears {count} times in '{path}'. "
                f"Please specify start_line and end_line to disambiguate."
            )

        new_content = content.replace(old_text, new_text, 1)

    # Write the result
    p.write_text(new_content, encoding="utf-8")

    # Count lines changed
    old_lines = old_text.count("\n")
    new_lines = new_text.count("\n")

    return (
        f"Successfully edited '{path}': "
        f"replaced {old_lines + 1} lines with {new_lines + 1} lines "
        f"(net change: {new_lines - old_lines:+d} lines)"
    )


def list_directory(
    path: str,
    recursive: bool = False,
    max_depth: int = 2,
    pattern: str | None = None,
    exclude: list[str] | None = None,
) -> dict:
    """
    List directory contents as a nested tree.

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


def get_read_files() -> list[str]:
    """Return list of files that have been read in this session. Useful for debugging."""
    return sorted(_read_files)


def reset_read_tracking() -> None:
    """Reset the read-file tracking. Use when starting a new task/session."""
    _read_files.clear()
