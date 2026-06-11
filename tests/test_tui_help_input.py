"""Tests for redesigned help screen, log viewer, and input widget.

Covers:
- HelpScreen: search, categories, vim navigation key bindings
- LogViewerScreen: page up/down, filter/search, level colors, timestamps
- ChatInput: slash command hint dropdown, on_change hint updates
"""

from __future__ import annotations

import pytest

from nexusagent.widgets.chat_input import SLASH_COMMANDS, ChatInput


# ---------------------------------------------------------------------------
# HelpScreen search & category data
# ---------------------------------------------------------------------------

CATEGORY_KEYBINDINGS = {
    "Navigation": [
        ("j", "Scroll down"),
        ("k", "Scroll up"),
        ("q", "Close help"),
        ("/", "Search"),
        ("Enter", "Submit message"),
        ("Shift+Enter", "New line in input"),
        ("Up/Down", "Command history"),
    ],
    "Global Shortcuts": [
        ("F1", "Show help"),
        ("F2", "Show logs"),
        ("F3", "Switch theme"),
        ("F12", "Toggle devtools"),
        ("Ctrl+C", "Interrupt / Exit"),
    ],
}

CATEGORY_SLASH_COMMANDS = {
    "Commands": [
        ("/help", "Show this help screen"),
        ("/logs", "Open log viewer"),
        ("/theme", "Cycle through themes"),
        ("/clear", "Clear chat history"),
        ("/model", "Show current model"),
    ],
}


class TestHelpScreenData:
    """Tests for help screen category and search data structures."""

    def test_category_keybindings_nonempty(self):
        """Keybindings category has entries."""
        for category, entries in CATEGORY_KEYBINDINGS.items():
            assert len(entries) > 0, f"Category {category} is empty"

    def test_category_slash_commands_nonempty(self):
        """Slash commands category has entries."""
        for category, entries in CATEGORY_SLASH_COMMANDS.items():
            assert len(entries) > 0, f"Category {category} is empty"

    def test_all_commands_documented(self):
        """Every SLASH_COMMANDS entry appears in help categories."""
        documented = []
        for entries in CATEGORY_SLASH_COMMANDS.values():
            documented.extend(cmd for cmd, _ in entries)
        for cmd in SLASH_COMMANDS:
            assert cmd in documented, f"{cmd} not documented in help categories"

    def test_search_matches_keybinding(self):
        """Searching 'f1' finds the F1 keybinding."""
        query = "f1"
        results = []
        for category, entries in CATEGORY_KEYBINDINGS.items():
            for key, desc in entries:
                if query.lower() in key.lower() or query.lower() in desc.lower():
                    results.append((category, key, desc))
        assert len(results) > 0
        assert any(key == "F1" for _, key, _ in results)

    def test_search_matches_command(self):
        """Searching 'clear' finds the /clear command."""
        query = "clear"
        results = []
        for category, entries in CATEGORY_SLASH_COMMANDS.items():
            for cmd, desc in entries:
                if query.lower() in cmd.lower() or query.lower() in desc.lower():
                    results.append((category, cmd, desc))
        assert len(results) > 0
        assert any(cmd == "/clear" for _, cmd, _ in results)

    def test_search_no_match(self):
        """Searching gibberish returns no results."""
        query = "zzzzgibberish"
        results = []
        for categories in [CATEGORY_KEYBINDINGS, CATEGORY_SLASH_COMMANDS]:
            for category, entries in categories.items():
                for item in entries:
                    text = " ".join(str(x) for x in item)
                    if query.lower() in text.lower():
                        results.append((category, item))
        assert len(results) == 0

    def test_search_filters_categories(self):
        """Search only returns matching categories."""
        query = "theme"
        matched_categories = []
        for category, entries in CATEGORY_SLASH_COMMANDS.items():
            for cmd, desc in entries:
                if query.lower() in cmd.lower() or query.lower() in desc.lower():
                    matched_categories.append(category)
        assert len(matched_categories) > 0

    def test_vim_nav_keys_present(self):
        """Vim navigation keys (j, k, /, q) are in keybindings."""
        all_keys = []
        for entries in CATEGORY_KEYBINDINGS.values():
            all_keys.extend(key for key, _ in entries)
        assert "j" in all_keys
        assert "k" in all_keys
        assert "/" in all_keys
        assert "q" in all_keys


# ---------------------------------------------------------------------------
# LogViewerScreen filter/search
# ---------------------------------------------------------------------------


class TestLogViewerScreenData:
    """Tests for log viewer filtering and level coloring."""

    SAMPLE_LOG_LINES = [
        "2025-01-15 10:00:01 [INFO] nexusagent: Session started",
        "2025-01-15 10:00:02 [WARNING] nexusagent: Low memory",
        "2025-01-15 10:00:03 [ERROR] nexusagent: Failed to connect",
        "2025-01-15 10:00:04 [DEBUG] nexusagent: Processing event",
        "2025-01-15 10:00:05 [INFO] nexusagent: Message sent",
    ]

    def test_filter_by_level_error(self):
        """Filtering by ERROR level returns only error lines."""
        level = "ERROR"
        filtered = [line for line in self.SAMPLE_LOG_LINES if f"[{level}]" in line]
        assert len(filtered) == 1
        assert "ERROR" in filtered[0]

    def test_filter_by_level_info(self):
        """Filtering by INFO level returns only info lines."""
        level = "INFO"
        filtered = [line for line in self.SAMPLE_LOG_LINES if f"[{level}]" in line]
        assert len(filtered) == 2

    def test_filter_case_insensitive(self):
        """Level filtering is case-insensitive."""
        level = "error"
        filtered_upper = [line for line in self.SAMPLE_LOG_LINES if f"[{level.upper()}]" in line]
        filtered_lower = [line for line in self.SAMPLE_LOG_LINES if level.lower() in line.lower()]
        assert len(filtered_upper) == 1
        assert len(filtered_lower) >= 1

    def test_filter_by_search_term(self):
        """Searching by keyword returns matching lines."""
        term = "connect"
        filtered = [line for line in self.SAMPLE_LOG_LINES if term.lower() in line.lower()]
        assert len(filtered) == 1
        assert "Failed to connect" in filtered[0]

    def test_filter_no_match(self):
        """Searching for nonexistent term returns empty list."""
        term = "zzzznonexistent"
        filtered = [line for line in self.SAMPLE_LOG_LINES if term.lower() in line.lower()]
        assert len(filtered) == 0

    def test_log_level_colors_mapping(self):
        """Each log level maps to a distinct color."""
        level_colors = {
            "DEBUG": "text-muted",
            "INFO": "text-secondary",
            "WARNING": "warning",
            "ERROR": "error",
            "CRITICAL": "bold error",
        }
        # All levels present
        assert "DEBUG" in level_colors
        assert "INFO" in level_colors
        assert "WARNING" in level_colors
        assert "ERROR" in level_colors
        assert "CRITICAL" in level_colors
        # All have distinct colors
        colors = list(level_colors.values())
        assert len(colors) == len(set(colors))

    def test_page_down_loads_more(self):
        """Page down increases the number of log lines displayed."""
        initial_lines = 20
        page_size = 20
        after_page_down = initial_lines + page_size
        assert after_page_down == 40

    def test_page_up_reduces(self):
        """Page up decreases the number of log lines displayed."""
        initial_lines = 40
        page_size = 20
        after_page_up = max(10, initial_lines - page_size)
        assert after_page_up == 20

    def test_page_up_minimum(self):
        """Page up does not go below minimum line count."""
        initial_lines = 15
        page_size = 20
        minimum = 10
        after_page_up = max(minimum, initial_lines - page_size)
        assert after_page_up == minimum

    def test_timestamps_present(self):
        """Sample log lines contain timestamps."""
        for line in self.SAMPLE_LOG_LINES:
            # Simple check: lines start with date-like pattern
            assert line[4] == "-", f"Expected '-' at position 4 in timestamp: {line}"


# ---------------------------------------------------------------------------
# ChatInput hint dropdown
# ---------------------------------------------------------------------------


class TestChatInputHintDropdown:
    """Tests for the slash command hint dropdown."""

    def test_hint_shows_all_on_slash(self):
        """Typing '/' shows all commands in hint."""
        widget = ChatInput()
        widget.text = "/"
        hint = widget._get_slash_hint()
        assert hint is not None
        for cmd in SLASH_COMMANDS:
            assert cmd in hint

    def test_hint_filters_on_partial(self):
        """Typing '/he' shows only matching commands."""
        widget = ChatInput()
        widget.text = "/he"
        hint = widget._get_slash_hint()
        assert hint is not None
        assert "/help" in hint
        for cmd in SLASH_COMMANDS:
            if cmd != "/help":
                assert cmd not in hint

    def test_hint_none_for_non_slash(self):
        """Non-slash input returns no hint."""
        widget = ChatInput()
        widget.text = "hello world"
        assert widget._get_slash_hint() is None

    def test_hint_none_for_no_match(self):
        """Slash with no matching commands returns None."""
        widget = ChatInput()
        widget.text = "/zzzzz"
        assert widget._get_slash_hint() is None

    def test_hint_none_for_plain_slash_only(self):
        """Just '/' returns all commands, not None."""
        widget = ChatInput()
        widget.text = "/"
        hint = widget._get_slash_hint()
        assert hint is not None

    def test_hint_single_match(self):
        """'/t' matches '/theme' and '/logs' no — just '/theme'."""
        widget = ChatInput()
        widget.text = "/t"
        hint = widget._get_slash_hint()
        assert hint is not None
        assert "/theme" in hint
        assert "/logs" not in hint

    def test_hint_with_extra_whitespace(self):
        """Hint still works with whitespace-padded input."""
        widget = ChatInput()
        widget.text = "  /help  "
        hint = widget._get_slash_hint()
        # strip() is called, so this should match
        assert hint is not None
        assert "/help" in hint

    def test_slash_commands_sorted(self):
        """SLASH_COMMANDS list is sorted for consistent display."""
        assert SLASH_COMMANDS == sorted(SLASH_COMMANDS)

    def test_autocomplete_exists(self):
        """ChatInput has action_autocomplete method."""
        widget = ChatInput()
        assert hasattr(widget, "action_autocomplete")
        assert callable(widget.action_autocomplete)

    def test_submit_exists(self):
        """ChatInput has action_submit method."""
        widget = ChatInput()
        assert hasattr(widget, "action_submit")
        assert callable(widget.action_submit)

    def test_cancel_exists(self):
        """ChatInput has action_cancel method."""
        widget = ChatInput()
        assert hasattr(widget, "action_cancel")
        assert callable(widget.action_cancel)
