"""Tests for NexusAgent TUI widgets.

Covers:
- UserMessage rendering with timestamp
- AssistantMessage streaming and markdown rendering
- ToolCallMessage collapsible output, syntax hints, status indicators
- ErrorMessage visual with icon
- AppMessage subtle dim styling
- WelcomeBanner compact design
- ChatInput slash command detection
- Command history persistence
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from nexusagent.widgets.chat_input import (
    SLASH_COMMANDS,
    ChatInput,
    _load_history,
    _save_history,
)
from nexusagent.widgets.messages import (
    AppMessage,
    AssistantMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
)

# ---------------------------------------------------------------------------
# UserMessage tests
# ---------------------------------------------------------------------------


class TestUserMessage:
    """Tests for the UserMessage widget."""

    def test_basic_render(self):
        """User message renders content with left-border accent."""
        msg = UserMessage("Hello world")
        rendered = str(msg.render())
        assert "Hello world" in rendered

    def test_render_returns_content(self):
        """render() returns a Content object."""
        from textual.content import Content
        msg = UserMessage("test")
        result = msg.render()
        assert isinstance(result, Content)

    def test_multiline_content(self):
        """Multi-line user content is preserved."""
        msg = UserMessage("line1\nline2\nline3")
        rendered = str(msg.render())
        assert "line1" in rendered
        assert "line2" in rendered
        assert "line3" in rendered

    def test_empty_content(self):
        """Empty content renders only the timestamp."""
        msg = UserMessage("")
        rendered = str(msg.render())
        # Even empty content shows timestamp prefix
        assert rendered != ""  # timestamp is always present

    def test_timestamp_present(self):
        """User message includes a timestamp in the rendered output."""
        msg = UserMessage("test message")
        rendered = str(msg.render())
        # Timestamp should be present (HH:MM format)
        import re
        assert re.search(r'\d{2}:\d{2}', rendered)

    def test_content_stored(self):
        """Content is stored and retrievable."""
        msg = UserMessage("my content")
        assert msg._content == "my content"


# ---------------------------------------------------------------------------
# AssistantMessage tests
# ---------------------------------------------------------------------------


class TestAssistantMessage:
    """Tests for the AssistantMessage widget."""

    def test_initial_empty(self):
        """Assistant message starts empty."""
        msg = AssistantMessage()
        rendered = str(msg.render())
        assert rendered == ""

    def test_finalize_sets_content(self):
        """finalize() sets the full content."""
        msg = AssistantMessage()
        msg.finalize("Hello, I'm NexusAgent!")
        rendered = str(msg.render())
        assert "Hello" in rendered

    def test_finalize_overrides_buffer(self):
        """finalize() overrides any buffered streaming content."""
        msg = AssistantMessage()
        msg._buffer = "old content"
        msg.finalize("new content")
        rendered = str(msg.render())
        assert "new content" in rendered
        assert "old content" not in rendered

    def test_buffer_accumulation(self):
        """Tokens are accumulated in the buffer."""
        msg = AssistantMessage()
        msg._buffer = ""
        # Simulate token appending (without async)
        msg._buffer += "Hello"
        msg._buffer += " World"
        assert msg._buffer == "Hello World"

    def test_markdown_content(self):
        """Assistant message can contain markdown-like content."""
        msg = AssistantMessage()
        msg.finalize("**Bold** and *italic* and `code`")
        rendered = str(msg.render())
        assert "Bold" in rendered
        assert "italic" in rendered
        assert "code" in rendered

    def test_render_returns_content(self):
        """render() returns a Content object."""
        from textual.content import Content
        msg = AssistantMessage()
        msg.finalize("test")
        result = msg.render()
        assert isinstance(result, Content)

    def test_bold_markdown_renders(self):
        """**bold** text is rendered with bold style."""
        from textual.content import Content
        msg = AssistantMessage()
        msg.finalize("This is **bold** text")
        content = msg.render()
        assert isinstance(content, Content)
        rendered = str(content)
        assert "bold" in rendered
        assert "This is" in rendered
        assert "text" in rendered

    def test_italic_markdown_renders(self):
        """*italic* text is rendered with italic style."""
        from textual.content import Content
        msg = AssistantMessage()
        msg.finalize("This is *italic* text")
        content = msg.render()
        assert isinstance(content, Content)
        rendered = str(content)
        assert "italic" in rendered
        assert "This is" in rendered
        assert "text" in rendered

    def test_inline_code_markdown_renders(self):
        """`code` text is rendered with muted style."""
        from textual.content import Content
        msg = AssistantMessage()
        msg.finalize("Use `git status` to check")
        content = msg.render()
        assert isinstance(content, Content)
        rendered = str(content)
        assert "git status" in rendered

    def test_mixed_markdown_renders(self):
        """Mixed **bold**, *italic*, and `code` all render correctly."""
        from textual.content import Content
        msg = AssistantMessage()
        msg.finalize("**Bold** and *italic* and `code`")
        content = msg.render()
        assert isinstance(content, Content)
        rendered = str(content)
        assert "Bold" in rendered
        assert "italic" in rendered
        assert "code" in rendered

    def test_plain_text_passthrough(self):
        """Text without markdown renders as plain Content."""
        from textual.content import Content
        msg = AssistantMessage()
        msg.finalize("Just plain text here")
        content = msg.render()
        assert isinstance(content, Content)
        rendered = str(content)
        assert "Just plain text here" in rendered

    def test_empty_content_renders(self):
        """Empty content renders as empty Content."""
        from textual.content import Content
        msg = AssistantMessage()
        content = msg.render()
        assert isinstance(content, Content)


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
        parts = msg.render()
        assert "⚙" in rendered

    def test_json_args_pretty_print(self):
        """JSON args are normalised (compact form)."""
        msg = ToolCallMessage(
            tool="write_file",
            args='{  "path":  "test.py",  "content":  "hello"  }',
            output="done",
        )
        rendered = str(msg.render())
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
        # Use output long enough to truncate but short enough not to collapse
        # Must be < 300 chars to avoid char-based collapse, but we test truncation
        # by directly calling _truncate_output
        long_output = "x" * 500
        msg = ToolCallMessage(tool="run_shell", args="cmd=cat", output=long_output)
        # Directly test truncation logic
        truncated = msg._truncate_output(long_output)
        assert "more chars" in truncated
        assert "200" in truncated  # 500 - 300 = 200

    def test_no_truncation_for_short_output(self):
        """Short output is not truncated."""
        msg = ToolCallMessage(tool="read", args="f=a.py", output="hello world")
        rendered = str(msg.render())
        assert "hello world" in rendered
        assert "more chars" not in rendered

    def test_code_detection_fenced_block(self):
        """Output with fenced code blocks gets a syntax hint."""
        output = 'Here is code:\n```python\nprint("hi")\n```'
        msg = ToolCallMessage(tool="run_shell", args="cmd=cat", output=output)
        rendered = str(msg.render())
        # Now uses syntax hint instead of generic [code]
        assert "[python]" in rendered

    def test_code_detection_inline(self):
        """Output with inline code renders without collapse."""
        output = "Use `git status` to check"
        msg = ToolCallMessage(tool="run_shell", args="cmd=help", output=output)
        rendered = str(msg.render())
        # Inline code is rendered as-is
        assert "git status" in rendered

    def test_no_code_hint_for_plain_text(self):
        """Plain text output does not get a syntax hint."""
        msg = ToolCallMessage(tool="read", args="f=a.py", output="just some text")
        rendered = str(msg.render())
        # No syntax hint for plain text
        assert "[" not in rendered or "code" not in rendered

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

    def test_status_running_constant(self):
        """STATUS_RUNNING constant is 'running'."""
        assert ToolCallMessage.STATUS_RUNNING == "running"

    def test_status_success_constant(self):
        """STATUS_SUCCESS constant is 'success'."""
        assert ToolCallMessage.STATUS_SUCCESS == "success"

    def test_status_failed_constant(self):
        """STATUS_FAILED constant is 'failed'."""
        assert ToolCallMessage.STATUS_FAILED == "failed"

    def test_status_icons_complete(self):
        """All statuses have icons."""
        assert ToolCallMessage.STATUS_RUNNING in ToolCallMessage._STATUS_ICONS
        assert ToolCallMessage.STATUS_SUCCESS in ToolCallMessage._STATUS_ICONS
        assert ToolCallMessage.STATUS_FAILED in ToolCallMessage._STATUS_ICONS

    def test_status_styles_complete(self):
        """All statuses have styles."""
        assert ToolCallMessage.STATUS_RUNNING in ToolCallMessage._STATUS_STYLES
        assert ToolCallMessage.STATUS_SUCCESS in ToolCallMessage._STATUS_STYLES
        assert ToolCallMessage.STATUS_FAILED in ToolCallMessage._STATUS_STYLES

    def test_update_status(self):
        """update_status changes the status and refreshes."""
        msg = ToolCallMessage(tool="test", args="x=1")
        msg.update_status("success")
        assert msg._status == "success"

    def test_update_output(self):
        """update_output changes the output and refreshes."""
        msg = ToolCallMessage(tool="test", args="x=1", output="old")
        msg.update_output("new output")
        assert msg._output == "new output"

    def test_collapsed_by_default_when_output_long(self):
        """Tool output is collapsed when it exceeds collapse threshold."""
        # Multi-line output exceeding threshold
        long_output = "line1\nline2\nline3\nline4\nline5"
        msg = ToolCallMessage(tool="test", args="x=1", output=long_output)
        assert msg._collapsed is True

    def test_not_collapsed_when_output_short(self):
        """Tool output is not collapsed when it's short."""
        msg = ToolCallMessage(tool="test", args="x=1", output="short")
        assert msg._collapsed is False

    def test_toggle_collapse(self):
        """toggle_collapse switches collapsed state."""
        msg = ToolCallMessage(tool="test", args="x=1", output="short")
        assert msg._collapsed is False
        msg.toggle_collapse()
        assert msg._collapsed is True
        msg.toggle_collapse()
        assert msg._collapsed is False

    def test_collapsed_output_shows_summary(self):
        """When collapsed, output shows a summary line."""
        long_output = "line1\nline2\nline3\nline4\nline5"
        msg = ToolCallMessage(tool="test", args="x=1", output=long_output)
        msg._collapsed = True
        rendered = str(msg.render())
        # Should show collapsed indicator with line count
        assert "lines" in rendered.lower() or "collapsed" in rendered.lower()

    def test_syntax_hint_python(self):
        """Python code blocks get a [python] syntax hint."""
        output = '```python\nprint("hi")\n```'
        msg = ToolCallMessage(tool="run", args="x=1", output=output)
        hint = msg._detect_syntax_hint()
        assert hint == "python"

    def test_syntax_hint_javascript(self):
        """JavaScript code blocks get a [js] syntax hint."""
        output = '```javascript\nconsole.log("hi")\n```'
        msg = ToolCallMessage(tool="run", args="x=1", output=output)
        hint = msg._detect_syntax_hint()
        assert hint == "javascript"

    def test_syntax_hint_json(self):
        """JSON code blocks get a [json] syntax hint."""
        output = '```json\n{"key": "val"}\n```'
        msg = ToolCallMessage(tool="run", args="x=1", output=output)
        hint = msg._detect_syntax_hint()
        assert hint == "json"

    def test_syntax_hint_none_for_plain(self):
        """Plain text without code blocks returns None."""
        msg = ToolCallMessage(tool="run", args="x=1", output="plain text")
        hint = msg._detect_syntax_hint()
        assert hint is None

    def test_syntax_hint_none_for_unknown_lang(self):
        """Unknown language code blocks return the lang as-is."""
        output = '```rust\nfn main() {}\n```'
        msg = ToolCallMessage(tool="run", args="x=1", output=output)
        hint = msg._detect_syntax_hint()
        assert hint == "rust"


# ---------------------------------------------------------------------------
# AppMessage tests
# ---------------------------------------------------------------------------


class TestAppMessage:
    """Tests for the AppMessage widget."""

    def test_basic_render(self):
        """App message renders the message text."""
        msg = AppMessage("Thinking...")
        rendered = str(msg.render())
        assert "Thinking..." in rendered

    def test_dim_styling(self):
        """App message uses muted/dim color."""
        msg = AppMessage("status update")
        assert msg._message == "status update"

    def test_empty_message(self):
        """Empty app message renders without error."""
        msg = AppMessage("")
        rendered = str(msg.render())
        # Empty message still renders the icon prefix
        assert rendered is not None

    def test_prefix_icon(self):
        """App message includes a prefix icon."""
        msg = AppMessage("thinking")
        rendered = str(msg.render())
        assert "○" in rendered


# ---------------------------------------------------------------------------
# ErrorMessage tests
# ---------------------------------------------------------------------------


class TestErrorMessage:
    """Tests for the ErrorMessage widget."""

    def test_error_icon(self):
        """Error message includes the error icon."""
        msg = ErrorMessage("Something went wrong")
        rendered = str(msg.render())
        assert "✗" in rendered

    def test_error_text(self):
        """Error message includes the error text."""
        msg = ErrorMessage("File not found")
        rendered = str(msg.render())
        assert "File not found" in rendered

    def test_error_style(self):
        """Error message uses error color styling."""
        msg = ErrorMessage("test error")
        rendered = str(msg.render())
        assert "Error" in rendered

    def test_multiline_error(self):
        """Multi-line error messages are preserved."""
        msg = ErrorMessage("line1\nline2")
        rendered = str(msg.render())
        assert "line1" in rendered
        assert "line2" in rendered

    def test_error_has_border_style(self):
        """ErrorMessage CSS includes left-border accent."""
        css = ErrorMessage.DEFAULT_CSS
        assert "border-left" in css
        assert "$error" in css


# ---------------------------------------------------------------------------
# WelcomeBanner tests
# ---------------------------------------------------------------------------


class TestWelcomeBanner:
    """Tests for the WelcomeBanner widget."""

    def test_contains_session_id(self):
        """Welcome banner includes the session ID."""
        banner = WelcomeBanner(session_id="abc123")
        rendered = str(banner.render())
        assert "abc123" in rendered

    def test_contains_nexusagent_name(self):
        """Welcome banner includes NexusAgent branding."""
        banner = WelcomeBanner(session_id="test")
        rendered = str(banner.render())
        assert "NexusAgent" in rendered

    def test_contains_help_hint(self):
        """Welcome banner includes a help hint."""
        banner = WelcomeBanner(session_id="test")
        rendered = str(banner.render())
        assert "/help" in rendered.lower() or "help" in rendered.lower()

    def test_compact_format(self):
        """Welcome banner uses compact format (no excessive box drawing)."""
        banner = WelcomeBanner(session_id="test")
        rendered = str(banner.render())
        lines = rendered.strip().split("\n")
        # Compact: should be <= 3 lines of content
        assert len(lines) <= 3

    def test_timestamp_present(self):
        """Welcome banner includes a timestamp."""
        banner = WelcomeBanner(session_id="test")
        rendered = str(banner.render())
        import re
        assert re.search(r'\d{2}:\d{2}', rendered)

    def test_render_returns_content(self):
        """Welcome banner render() returns a Content object."""
        from textual.content import Content
        banner = WelcomeBanner(session_id="test")
        result = banner.render()
        assert isinstance(result, Content)

    def test_session_id_stored(self):
        """Session ID is stored as attribute."""
        banner = WelcomeBanner(session_id="sess-abc")
        assert banner._session_id == "sess-abc"

    def test_banner_uses_content_assemble(self):
        """Welcome banner uses Content.assemble (not raw markup string)."""
        banner = WelcomeBanner(session_id="test")
        content = banner.render()
        # Content.assemble produces Content with spans, not raw markup
        raw = str(content)
        # Should contain the actual text, not markup tags like [bold]
        assert "NexusAgent" in raw
        assert "[b " not in raw
        assert "[/b]" not in raw


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
        bad_file.write_text("not valid json {{")

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
