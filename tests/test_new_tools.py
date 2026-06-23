"""Tests for new tools: code_review, write_todos, read_todos.

TDD: tests written first, then tool implementations.
"""

import json
import os

import pytest

# ─── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_todos_file(tmp_path):
    """Provide a temporary todos file path."""
    return str(tmp_path / "todos.json")


@pytest.fixture
def sample_python_code():
    """Provide sample Python code with intentional issues for testing review."""
    return (
        "import os\n"
        "import pickle\n"
        "\n"
        "def process_data(user_input):\n"
        "    # TODO: validate input\n"
        "    result = eval(user_input)\n"
        "    return result\n"
        "\n"
        "class DataStore:\n"
        "    def __init__(self):\n"
        "        self.data = []\n"
        "\n"
        "    def save(self, path, obj):\n"
        "        with open(path, 'w') as f:\n"
        "            pickle.dump(obj, f)\n"
    )


# ─── Code Review Tests ──────────────────────────────────────────────────

class TestReviewCode:
    """Tests for the review_code tool."""

    def test_review_code_returns_string(self):
        """review_code should return a string."""
        from nexusagent.tools.code_review import review_code
        result = review_code(code="x = 1")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_review_code_with_syntax_error(self):
        """review_code should detect syntax errors."""
        from nexusagent.tools.code_review import review_code
        bad_code = "def broken(\n    pass\n"
        result = review_code(code=bad_code)
        assert isinstance(result, str)
        # Should mention the issue
        assert "error" in result.lower() or "syntax" in result.lower() or "issue" in result.lower()

    def test_review_code_detects_eval_usage(self):
        """review_code should flag dangerous eval usage."""
        from nexusagent.tools.code_review import review_code
        dangerous = "result = eval(user_input)"
        result = review_code(code=dangerous)
        assert isinstance(result, str)
        # Should flag security concern
        result_lower = result.lower()
        assert "security" in result_lower or "dangerous" in result_lower or "eval" in result_lower or "⚠" in result or "!" in result

    def test_review_code_detects_pickle_usage(self):
        """review_code should flag unsafe pickle usage."""
        from nexusagent.tools.code_review import review_code
        unsafe = "import pickle\npickle.loads(data)"
        result = review_code(code=unsafe)
        assert isinstance(result, str)
        result_lower = result.lower()
        assert "security" in result_lower or "unsafe" in result_lower or "pickle" in result_lower or "⚠" in result

    def test_review_code_empty_code(self):
        """review_code should handle empty code gracefully."""
        from nexusagent.tools.code_review import review_code
        result = review_code(code="")
        assert isinstance(result, str)

    def test_review_code_clean_code(self):
        """review_code should report minimal issues for clean code."""
        from nexusagent.tools.code_review import review_code
        clean = "def add(a, b):\n    return a + b\n"
        result = review_code(code=clean)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_review_code_returns_severity_levels(self):
        """review_code output should include severity indicators."""
        from nexusagent.tools.code_review import review_code
        buggy = "eval(input())"
        result = review_code(code=buggy)
        assert isinstance(result, str)
        # Should contain some form of severity marker
        has_severity = any(marker in result for marker in ["HIGH", "MEDIUM", "LOW", "CRITICAL", "⚠", "🔴", "🟡", "ℹ"])  # noqa: RUF001
        assert has_severity, f"Expected severity markers in output: {result}"


# ─── Write Todos Tests ──────────────────────────────────────────────────

class TestWriteTodos:
    """Tests for the write_todos tool."""

    def test_write_todos_creates_file(self, tmp_todos_file):
        """write_todos should create the todos file."""
        from nexusagent.tools.write_todos import write_todos
        todos = [
            {"task": "Fix the auth bug", "status": "pending"},
            {"task": "Add tests", "status": "pending"},
        ]
        result = write_todos(todos=todos, path=tmp_todos_file)
        assert os.path.exists(tmp_todos_file)
        assert "2" in result or "success" in result.lower() or "written" in result.lower()

    def test_write_todos_overwrites_existing(self, tmp_todos_file):
        """write_todos should overwrite an existing todos file."""
        from nexusagent.tools.write_todos import write_todos

        # Write initial todos
        initial = [{"task": "Old task", "status": "done"}]
        write_todos(todos=initial, path=tmp_todos_file)

        # Overwrite with new todos
        new = [{"task": "New task", "status": "in_progress"}]
        result = write_todos(todos=new, path=tmp_todos_file)

        with open(tmp_todos_file) as f:
            data = json.load(f)
        assert "todos" in data
        assert len(data["todos"]) == 1
        assert data["todos"][0]["task"] == "New task"

    def test_write_todos_stores_json(self, tmp_todos_file):
        """write_todos should store todos as JSON."""
        from nexusagent.tools.write_todos import write_todos
        todos = [
            {"task": "Task 1", "status": "pending", "priority": "high"},
        ]
        write_todos(todos=todos, path=tmp_todos_file)

        with open(tmp_todos_file) as f:
            data = json.load(f)
        assert "todos" in data
        assert data["todos"] == todos

    def test_write_todos_empty_list(self, tmp_todos_file):
        """write_todos should handle empty todos list."""
        from nexusagent.tools.write_todos import write_todos
        result = write_todos(todos=[], path=tmp_todos_file)
        assert os.path.exists(tmp_todos_file)

        with open(tmp_todos_file) as f:
            data = json.load(f)
        assert "todos" in data
        assert data["todos"] == []

    def test_write_todos_creates_directories(self, tmp_path):
        """write_todos should create parent directories if needed."""
        from nexusagent.tools.write_todos import write_todos
        nested_path = str(tmp_path / "sub" / "dir" / "todos.json")
        result = write_todos(todos=[{"task": "Test", "status": "pending"}], path=nested_path)
        assert os.path.exists(nested_path)


# ─── Read Todos Tests ──────────────────────────────────────────────────

class TestReadTodos:
    """Tests for the read_todos tool."""

    def test_read_todos_returns_list(self, tmp_todos_file):
        """read_todos should return the stored todos."""
        from nexusagent.tools.write_todos import read_todos, write_todos

        todos = [
            {"task": "Fix bug", "status": "pending"},
            {"task": "Write docs", "status": "done"},
        ]
        write_todos(todos=todos, path=tmp_todos_file)
        result = read_todos(path=tmp_todos_file)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["task"] == "Fix bug"

    def test_read_todos_nonexistent_file(self):
        """read_todos should handle missing file gracefully."""
        from nexusagent.tools.write_todos import read_todos
        result = read_todos(path="/nonexistent/path/todos.json")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_read_todos_preserves_status(self, tmp_todos_file):
        """read_todos should preserve all todo fields."""
        from nexusagent.tools.write_todos import read_todos, write_todos

        todos = [
            {"task": "Task A", "status": "in_progress", "priority": "high"},
            {"task": "Task B", "status": "done", "priority": "low"},
        ]
        write_todos(todos=todos, path=tmp_todos_file)
        result = read_todos(path=tmp_todos_file)
        assert result[0]["status"] == "in_progress"
        assert result[0]["priority"] == "high"
        assert result[1]["status"] == "done"

    def test_read_todos_invalid_json(self, tmp_todos_file):
        """read_todos should handle corrupted JSON gracefully."""
        from nexusagent.tools.write_todos import read_todos
        # Write invalid JSON
        with open(tmp_todos_file, "w") as f:
            f.write("not valid json{{{")
        result = read_todos(path=tmp_todos_file)
        assert isinstance(result, list)
        assert len(result) == 0
