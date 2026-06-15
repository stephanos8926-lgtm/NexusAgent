"""Todo management tools for NexusAgent.

Provides write_todos and read_todos for tracking multi-step work.
Todos are stored as JSON files for easy parsing and human readability.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone


def write_todos(todos: list[dict], path: str = "./todos.json") -> str:
    """Write a task list (todos) to a JSON file.

    Each todo is a dict with at minimum a "task" key. Common keys:
        - task: str — description of the task
        - status: str — "pending", "in_progress", "done", "blocked"
        - priority: str — "high", "medium", "low" (optional)
        - notes: str — additional context (optional)

    Args:
        todos: List of todo dicts to write
        path: File path for the todos JSON file (default: "./todos.json")

    Returns:
        Success message with count of todos written.

    Example:
        write_todos(
            todos=[
                {"task": "Fix auth bug", "status": "in_progress", "priority": "high"},
                {"task": "Add tests", "status": "pending", "priority": "medium"},
            ],
            path="./work/todos.json"
        )
    """
    p = Path(path)

    # Create parent directories if needed
    p.parent.mkdir(parents=True, exist_ok=True)

    # Build the output structure
    output = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "todos": todos,
    }

    # Write atomically: write to temp file, then rename
    tmp_path = str(p) + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            f.write("\n")  # trailing newline
        os.replace(tmp_path, str(p))
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    count = len(todos)
    done = sum(1 for t in todos if t.get("status") == "done")
    in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
    pending = sum(1 for t in todos if t.get("status") == "pending")

    parts = [f"Wrote {count} todos to {path}"]
    if count > 0:
        status_parts = []
        if done:
            status_parts.append(f"{done} done")
        if in_progress:
            status_parts.append(f"{in_progress} in progress")
        if pending:
            status_parts.append(f"{pending} pending")
        remaining = count - done - in_progress - pending
        if remaining:
            status_parts.append(f"{remaining} other")
        parts.append(f"({', '.join(status_parts)})")

    return ". ".join(parts) + "."


def read_todos(path: str = "./todos.json") -> list[dict]:
    """Read a task list (todos) from a JSON file.

    Args:
        path: File path for the todos JSON file (default: "./todos.json")

    Returns:
        List of todo dicts. Returns empty list if file doesn't exist or is invalid.

    Example:
        todos = read_todos("./work/todos.json")
        for todo in todos:
            print(f"{todo['status']:12s} {todo['task']}")
    """
    p = Path(path)

    if not p.exists():
        return []

    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    # Support both wrapped format {"version": 1, "todos": [...]} and raw list
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "todos" in data:
        return data["todos"]
    return []
