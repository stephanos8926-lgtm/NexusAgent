"""Tests for NexusAgent TUI widgets.

Covers:
- ToolCallMessage rendering with various tool outputs
- ChatInput slash command detection
- Command history persistence
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nexusagent.widgets.chat_input import (
    SLASH_COMMANDS,
    ChatInput,
    _load_history,
    _save_history,
)
from nexusagent.widgets.messages import ToolCallMessage


# ---------------------------------------------------------------------------
# ToolCallMessage tests
# ---------------------------------------------------------------------------


class TestToolCallMessage:
    """Tests for the enhanced ToolCallMessage widget."""

    def test_basic_render_running(self):
        """Default status is 'running' with gear icon."""
        msg = ToolCallMessage(tool="read_file", args="path=/tmp/foo.py")
        rendered = str(msg.render())
        assert "⚙" in rendered
        assert "read_file" in rendered

    def test_success_status(self):
        """Success status shows checkmark and success style."""
        msg = ToolCallMessage(
            tool="write_file",
            args='{"path": "test.py"}',
            output="OK",
            status="success",
        )
        rendered = str(msg.render())
        assert "✔" in rendered
        assert "write_file" in rendered

    def test_failed_status(self):
        """Failed status shows cross and error style."""
        msg = ToolCallMessage(
            tool="run_shell",
            args="cmd=ls",
            output="File not found",
            status="failed",
        )
        rendered = str(msg.render())
        assert "✘" in rendered
        assert "run_shell" in rendered

    def test_no_output(self):
        """When no output, only the header is rendered."""
        msg = ToolCallMessage(tool="search", args="query=test")
        rendered = str(msg.render())
        assert "search" in rendered
        # Should not have a newline from output
        parts = msg.render()
        # Content.assemble with just one tuple = no newline
        assert "⚙" in rendered

    def test_json_args_pretty_print(self):
        """JSON args are normalised (compact form)."""
        msg = ToolCallMessage(
            tool="write_file",
            args='{  "path":  "test.py",  "content":  "hello"  }',
            output="done",
        )
        rendered = str(msg.render())
        # The JSON should be compacted (no extra spaces)
        assert '"path"' in rendered
        assert '"content"' in rendered

    def test_non_json_args_unchanged(self):
        """Non-JSON args are passed through as-is."""
        msg = ToolCallMessage(
            tool="grep",
            args="pattern=foo, path=src/",
            output="match",
        )
        rendered = str(msg.render())
        assert "pattern=foo, path=src/" in rendered

    def test_truncation_indicator(self):
        """Long output is truncated with a char count indicator."""
        long_output = "x" * 500
        msg = ToolCallMessage(tool="run_shell", args="cmd=cat", output=long_output)
        rendered = str(msg.render())
        assert "more chars" in rendered
        # Should show remaining count (500 - 300 = 200)
        assert "200" in rendered

    def test_no_truncation_for_short_output(self):
        """Short output is not truncated."""
        msg = ToolCallMessage(tool="read", args="f=a.py", output="hello world")
        rendered = str(msg.render())
        assert "hello world" in rendered
        assert "more chars" not in rendered

    def test_code_detection_fenced_block(self):
        """Output with fenced code blocks gets a [code] hint."""
        output = 'Here is code:\n```python\nprint("hi")\n```'
        msg = ToolCallMessage(tool="run_shell", args="cmd=cat", output=output)
        rendered = str(msg.render())
        assert "[code]" in rendered

    def test_code_detection_inline(self):
        """Output with inline code gets a [code] hint."""
        output = "Use `git status` to check"
        msg = ToolCallMessage(tool="run_shell", args="cmd=help", output=output)
        rendered = str(msg.render())
        assert "[code]" in rendered

    def test_no_code_hint_for_plain_text(self):
        """Plain text output does not get a [code] hint."""
        msg = ToolCallMessage(tool="read", args="f=a.py", output="just some text")
        rendered = str(msg.render())
        assert "[code]" not in rendered

    def test_empty_args(self):
        """Empty args render cleanly."""
        msg = ToolCallMessage(tool="help", args="", output="available commands")
        rendered = str(msg.render())
        assert "help" in rendered

    def test_json_array_args(self):
        """JSON array args are also normalised."""
        msg = ToolCallMessage(
            tool="batch",
            args='[  "a",  "b",  "c"  ]',
            output="done",
        )
        rendered = str(msg.render())
        assert '"a"' in rendered


# ---------------------------------------------------------------------------
# ChatInput slash command tests
# ---------------------------------------------------------------------------


class TestSlashCommands:
    """Tests for slash command autocomplete."""

    def test_known_commands_list(self):
        """SLASH_COMMANDS contains the expected commands."""
        assert "/help" in SLASH_COMMANDS
        assert "/logs" in SLASH_COMMANDS
        assert "/theme" in SLASH_COMMANDS
        assert "/clear" in SLASH_COMMANDS
        assert "/model" in SLASH_COMMANDS

    def test_slash_prefix_matches_all(self):
        """Typing '/' matches all commands."""
        text = "/"
        matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
        assert len(matches) == len(SLASH_COMMANDS)

    def test_partial_match(self):
        """Typing '/he' matches only '/help'."""
        text = "/he"
        matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
        assert matches == ["/help"]

    def test_partial_match_multi(self):
        """Typing '/m' matches '/model'."""
        text = "/m"
        matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
        assert matches == ["/model"]

    def test_no_match(self):
        """Typing '/xyz' matches nothing."""
        text = "/xyz"
        matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
        assert matches == []

    def test_get_slash_hint_all(self):
        """_get_slash_hint returns all commands when text is '/'."""
        widget = ChatInput()
        widget.text = "/"
        hint = widget._get_slash_hint()
        assert hint is not None
        for cmd in SLASH_COMMANDS:
            assert cmd in hint

    def test_get_slash_hint_filtered(self):
        """_get_slash_hint returns filtered commands for partial input."""
        widget = ChatInput()
        widget.text = "/cl"
        hint = widget._get_slash_hint()
        assert hint is not None
        assert "/clear" in hint
        assert "/help" not in hint

    def test_get_slash_hint_none(self):
        """_get_slash_hint returns None for non-slash input."""
        widget = ChatInput()
        widget.text = "hello"
        assert widget._get_slash_hint() is None

    def test_get_slash_hint_no_match(self):
        """_get_slash_hint returns None when no commands match."""
        widget = ChatInput()
        widget.text = "/zzz"
        assert widget._get_slash_hint() is None


# ---------------------------------------------------------------------------
# Command history persistence tests
# ---------------------------------------------------------------------------


class TestHistoryPersistence:
    """Tests for command history save/load."""

    def test_save_and_load(self, tmp_path: Path):
        """History saved to disk can be loaded back."""
        history = ["first message", "second message", "/help"]

        with patch("nexusagent.widgets.chat_input._HISTORY_FILE", tmp_path / "history.json"):
            _save_history(history)
            loaded = _load_history()

        assert loaded == history

    def test_load_nonexistent_file(self, tmp_path: Path):
        """Loading from a nonexistent file returns empty list."""
        with patch(
            "nexusagent.widgets.chat_input._HISTORY_FILE",
            tmp_path / "does_not_exist.json",
        ):
            loaded = _load_history()
        assert loaded == []

    def test_load_corrupt_file(self, tmp_path: Path):
        """Loading a corrupt JSON file returns empty list."""
        bad_file = tmp_path / "history.json"
        bad_file.write_text("not valid json {{{")

        with patch("nexusagent.widgets.chat_input._HISTORY_FILE", bad_file):
            loaded = _load_history()
        assert loaded == []

    def test_save_creates_directory(self, tmp_path: Path):
        """_save_history creates the parent directory if needed."""
        nested_dir = tmp_path / "deep" / "nested"
        nested_file = nested_dir / "history.json"

        with patch("nexusagent.widgets.chat_input._HISTORY_DIR", nested_dir), \
             patch("nexusagent.widgets.chat_input._HISTORY_FILE", nested_file):
            _save_history(["test"])

        assert nested_file.exists()

    def test_max_history_limit(self, tmp_path: Path):
        """History is capped at _MAX_HISTORY entries."""
        from nexusagent.widgets.chat_input import _MAX_HISTORY

        big_history = [f"msg-{i}" for i in range(_MAX_HISTORY + 50)]

        with patch("nexusagent.widgets.chat_input._HISTORY_FILE", tmp_path / "history.json"):
            _save_history(big_history)
            loaded = _load_history()

        assert len(loaded) == _MAX_HISTORY
        # Should keep the most recent entries
        assert loaded[-1] == f"msg-{_MAX_HISTORY + 49}"
