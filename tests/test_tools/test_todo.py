# tests/test_tools/test_todo.py
"""Tests for todowrite and todoread tools."""

import os
import sys

# Ensure worktree src is in path BEFORE importing nexusagent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

import tempfile
from pathlib import Path

import pytest


def test_todowrite_creates_todo_md():
    """todowrite should create TODO.md with correct markdown format."""
    from nexusagent.tools.todo import todowrite

    with tempfile.TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"
        todos = [
            {"content": "Write tests", "status": "completed"},
            {"content": "Implement feature", "status": "in_progress"},
            {"content": "Review code", "status": "pending"},
        ]
        result = todowrite(todos, todo_path=str(todo_path))
        assert "TODO.md" in result or "todo" in result.lower()
        assert todo_path.exists()

        content = todo_path.read_text()
        assert "# TODO" in content
        assert "[x]" in content  # completed
        assert "[~]" in content  # in_progress
        assert "[ ]" in content  # pending
        assert "Write tests" in content
        assert "Implement feature" in content
        assert "Review code" in content


def test_todoread_returns_formatted_todos():
    """todoread should return the current TODO.md contents."""
    from nexusagent.tools.todo import todoread, todowrite

    with tempfile.TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"
        todos = [
            {"content": "Task one", "status": "pending"},
            {"content": "Task two", "status": "completed"},
        ]
        todowrite(todos, todo_path=str(todo_path))

        result = todoread(todo_path=str(todo_path))
        assert "Task one" in result
        assert "Task two" in result


def test_todo_persists_across_calls():
    """Multiple todowrite calls should overwrite; todoread should reflect latest."""
    from nexusagent.tools.todo import todoread, todowrite

    with tempfile.TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"

        # First write
        todowrite(
            [{"content": "First batch", "status": "completed"}],
            todo_path=str(todo_path),
        )

        # Second write — should replace
        todowrite(
            [{"content": "Second batch", "status": "in_progress"}],
            todo_path=str(todo_path),
        )

        content = todo_path.read_text()
        assert "Second batch" in content
        assert "First batch" not in content


def test_todowrite_empty_list():
    """todowrite with empty list should produce empty TODO.md."""
    from nexusagent.tools.todo import todoread, todowrite

    with tempfile.TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"
        result = todowrite([], todo_path=str(todo_path))
        assert todo_path.exists()

        content = todo_path.read_text()
        # Should have header but no tasks
        assert "# TODO" in content


def test_todoread_missing_file():
    """todoread should handle missing TODO.md gracefully."""
    from nexusagent.tools.todo import todoread

    with tempfile.TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"
        result = todoread(todo_path=str(todo_path))
        assert "not found" in result.lower() or "no todo" in result.lower()


def test_todowrite_status_markers():
    """Verify correct status markers for each status type."""
    from nexusagent.tools.todo import todowrite

    with tempfile.TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"
        todos = [
            {"content": "Done task", "status": "completed"},
            {"content": "Active task", "status": "in_progress"},
            {"content": "Waiting task", "status": "pending"},
        ]
        todowrite(todos, todo_path=str(todo_path))

        lines = todo_path.read_text().splitlines()
        task_lines = [l for l in lines if l.startswith("- [")]

        assert len(task_lines) == 3
        assert "[x]" in task_lines[0]  # completed
        assert "[~]" in task_lines[1]  # in_progress
        assert "[ ]" in task_lines[2]  # pending
