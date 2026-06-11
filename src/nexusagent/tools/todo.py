"""
Todo/Plan tools for NexusAgent.

Provides todowrite and todoread for multi-step task tracking:
- todowrite: Creates/updates a task list stored in TODO.md
- todoread: Returns the current TODO.md contents as formatted text

The agent uses these to track multi-step task progress across sessions.
Todos persist via file storage (TODO.md in the project root).
"""

import os
from pathlib import Path

# Status marker mapping
_STATUS_MARKERS = {
    "completed": "[x]",
    "in_progress": "[~]",
    "pending": "[ ]",
}

# Valid statuses
_VALID_STATUSES = frozenset(_STATUS_MARKERS.keys())


def _status_marker(status: str) -> str:
    """Return the markdown checkbox marker for a given status."""
    return _STATUS_MARKERS.get(status, "[ ]")


def _format_todos(todos: list[dict]) -> str:
    """Format a list of todo dicts into markdown content."""
    lines = ["# TODO", ""]

    if not todos:
        lines.append("_No tasks yet._")
        lines.append("")
        return "\n".join(lines)

    for todo in todos:
        content = todo.get("content", "")
        status = todo.get("status", "pending")
        marker = _status_marker(status)
        lines.append(f"- {marker} {content}")

    lines.append("")
    return "\n".join(lines)


def todowrite(
    todos: list[dict],
    todo_path: str | None = None,
) -> str:
    """
    Create or update the TODO.md file with the given task list.

    Args:
        todos: List of dicts with 'content' (str) and 'status' (str).
               Status must be one of: 'pending', 'in_progress', 'completed'.
        todo_path: Path to TODO.md file. Defaults to TODO.md in current directory.

    Returns:
        Success message confirming the write.

    Example:
        todowrite([
            {"content": "Write tests", "status": "completed"},
            {"content": "Implement feature", "status": "in_progress"},
            {"content": "Review code", "status": "pending"},
        ])
    """
    if todo_path is None:
        todo_path = "TODO.md"

    path = Path(todo_path)

    # Validate todos
    validated = []
    for todo in todos:
        content = todo.get("content", "")
        status = todo.get("status", "pending")
        if status not in _VALID_STATUSES:
            status = "pending"
        validated.append({"content": content, "status": status})

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write the file
    content = _format_todos(validated)
    path.write_text(content)

    task_count = len(validated)
    return f"TODO.md updated with {task_count} task(s)."


def todoread(
    todo_path: str | None = None,
) -> str:
    """
    Read and return the current TODO.md contents.

    Args:
        todo_path: Path to TODO.md file. Defaults to TODO.md in current directory.

    Returns:
        Formatted TODO.md content, or a message if the file doesn't exist.

    Example:
        todoread()
    """
    if todo_path is None:
        todo_path = "TODO.md"

    path = Path(todo_path)

    if not path.exists():
        return "No TODO.md found. Use todowrite() to create one."

    return path.read_text()
