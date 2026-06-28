"""File editor — surgical line-range file editing.

Extracted from tools/fs.py to separate the complex edit_file logic
(~104 lines) from the simpler read/write/list operations.
"""

from __future__ import annotations

from nexusagent.tools.fs_base import _check_read, _resolve


def edit_file(
    path: str,
    old_text: str,
    new_text: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Perform a surgical edit on a file.

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
            preview = range_text[:500]
            return (
                f"Error: old_text not found in lines {s + 1}-{e} of '{path}'. "
                f"Content preview:\n{preview}"
            )

        # Verify old_text starts within the range (not just overlaps)
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
