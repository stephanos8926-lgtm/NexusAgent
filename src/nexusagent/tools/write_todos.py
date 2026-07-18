"""Todo management tools for NexusAgent.

Enables the agent to read and write task lists/todos from/to a JSON file.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from nexusagent.tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    name="write_todos",
    description="Write task lists or todos to a JSON file.",
    parameters={
        "todos": "list[dict] — list of todo dictionaries with keys like task, status, etc.",
        "path": "str — file path to write to (defaults to 'todos.json')",
    },
    example='write_todos(todos=[{"task": "Implement feature", "status": "pending"}], path="todos.json")',
    category="todos",
    returns="str — confirmation message",
)
def write_todos(todos: list[dict[str, Any]], path: str = "todos.json") -> str:
    """Write task lists or todos to a JSON file."""
    try:
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        data = {"todos": todos}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return f"Successfully wrote {len(todos)} todos to {path}"
    except Exception as e:
        logger.error("Failed to write todos: %s", e)
        return f"Error writing todos: {e}"


@register_tool(
    name="read_todos",
    description="Read task lists or todos from a JSON file.",
    parameters={
        "path": "str — file path to read from (defaults to 'todos.json')",
    },
    example='read_todos(path="todos.json")',
    category="todos",
    returns="list — list of todo dictionaries",
)
def read_todos(path: str = "todos.json") -> list[dict[str, Any]]:
    """Read task lists or todos from a JSON file."""
    if not os.path.exists(path):
        logger.debug("Todos file %s does not exist, returning empty list", path)
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "todos" in data:
                return data["todos"]
            elif isinstance(data, list):
                return data
            return []
    except Exception as e:
        logger.warning("Failed to read todos from %s: %s, returning empty list", path, e)
        return []
