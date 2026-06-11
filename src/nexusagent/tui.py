"""NexusAgent Terminal User Interface (TUI).

A clean, professional terminal chat interface built with Textual.
Features:
- Individual message widgets in Container(layout="stream") for O(1) append
- Semantic color system with Linear-inspired dark theme
- VerticalScroll for chat area with smart auto-scroll
- Compact status bar with responsive behavior
- Chat input with history and image detection
- Streaming token-by-token updates
- Welcome banner that doesn't scroll away
- Structured logging and telemetry
- Multiple themes (nexus-dark, catppuccin-mocha, gruvbox-dark, nord)
- ASCII fallback detection
- iTerm2 cursor guide workaround
- gc.freeze() before first paint for performance
- Panic handler for terminal state restoration
- Responsive design
- Log viewer (/logs command)
- Help screen (/help command)
- Theme switching (/theme command)
- Chat clearing (/clear command)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import termios
from pathlib import Path
from typing import Any

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Grid, Horizontal, Vertical
from textual.events import Key
from textual.geometry import Offset
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Button, Label, Static, Input, RichLog

from nexusagent.widgets.messages import (
    UserMessage,
    AssistantMessage,
    ToolCallMessage,
    AppMessage,
    ErrorMessage,
    WelcomeBanner,
)
from nexusagent.widgets.status import StatusBar
from nexusagent.widgets.chat_input import ChatInput
from nexusagent.widgets.theme import get_css_variable_defaults, register_themes
from nexusagent.telemetry import setup_telemetry

logger = logging.getLogger(__name__)


# ── Help screen -------------------------------------------------------------

_HELP_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "Navigation": [
        ("j / ↓", "Scroll down"),
        ("k / ↑", "Scroll up"),
        ("q / Esc", "Close help"),
        ("/", "Search"),
        ("Enter", "Submit message"),
        ("Shift+Enter", "New line in input"),
        ("PgUp/PgDn", "Page up/down"),
    ],
    "Global Shortcuts": [
        ("F1", "Show help"),
        ("F2", "Show logs"),
        ("F3", "Switch theme"),
        ("F12", "Toggle devtools"),
        ("Ctrl+C", "Interrupt / Exit"),
    ],
    "Commands": [
        ("/help", "Show this help screen"),
        ("/logs", "Open log viewer"),
        ("/theme", "Cycle through themes"),
        ("/clear", "Clear chat history"),
        ("/model", "Show current model"),
    ],
}

# Semantic style for each category header
_HELP_CATEGORY_STYLES = {
    "Navigation": "bold accent",
    "Global Shortcuts": "bold warning",
    "Commands": "bold success",
}

# Log level → color style mapping
_LOG_LEVEL_COLORS = {
    "DEBUG": "dim",
    "INFO": "",
    "WARNING": "warning",
    "ERROR": "bold error",
    "CRITICAL": "bold error reverse",
}


class HelpScreen(ModalScreen[None]):
    """Searchable help modal with categories and vim-style navigation.

    Features:
    - Categories: Navigation, Global Shortcuts, Commands
    - Search: press '/', type query, Enter to clear
    - Vim nav: j/k to scroll, q/Esc to close
    - Color-coded log levels and command types
    """

    BINDINGS = [
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("q", "dismiss", "Close", show=True),
        Binding("escape", "dismiss", "Close", show=True),
        Binding("/", "start_search", "Search", show=True),
        Binding("enter", "clear_search", "Clear search", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: middle middle;
        width: 70;
        height: 30;
        min-width: 50;
        min-height: 20;
        background: $surface;
        border: solid $primary;
    }

    HelpScreen #title-row {
        height: 2;
        padding: 0 2;
        content-align: left middle;
    }

    HelpScreen #title {
        width: 1fr;
        style: bold primary;
    }

    HelpScreen #search-input {
        height: 3;
        margin: 0 1;
        border: solid $accent;
        display: none;
    }

    HelpScreen #search-input.-active {
        display: block;
    }

    HelpScreen #help-content {
        height: 1fr;
        padding: 0 2;
        overflow-y: auto;
    }

    HelpScreen .help-category {
        margin: 1 0 0 0;
        text-style: bold;
    }

    HelpScreen .help-entry {
        padding-left: 2;
        height: 1;
    }

    HelpScreen .help-key {
        width: 18;
        color: $accent;
    }

    HelpScreen .help-desc {
        color: $text-secondary;
    }

    HelpScreen .no-results {
        color: $text-muted;
        text-style: italic;
        padding: 2;
    }

    HelpScreen #footer {
        height: 2;
        padding: 0 2;
        content-align: left middle;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._search_mode = False
        self._search_query = ""

    def compose(self) -> ComposeResult:
        # Title row
        with Horizontal(id="title-row"):
            yield Label("NexusAgent Help", id="title")
        # Search input (hidden by default)
        yield Input(placeholder="Type to search...", id="search-input")
        # Help content area
        yield VerticalScroll(id="help-content")
        # Footer
        with Horizontal(id="footer"):
            yield Label("j/k: scroll  /: search  q: close")

    def _render_help(self) -> list[tuple[str, str]]:
        """Generate help content lines, filtered by search query if active.

        Returns list of (text, style) tuples for rendering.
        """
        lines: list[tuple[str, str]] = []
        for category, entries in _HELP_CATEGORIES.items():
            filtered_entries = entries
            if self._search_query:
                q = self._search_query.lower()
                filtered_entries = [
                    (key, desc) for key, desc in entries
                    if q in key.lower() or q in desc.lower()
                ]
                if not filtered_entries:
                    continue

            style = _HELP_CATEGORY_STYLES.get(category, "bold")
            lines.append((f"▸ {category}", style))
            for key, desc in filtered_entries:
                lines.append((f"  {key:<18} {desc}", "text-secondary"))
            lines.append(("", ""))  # blank line between categories
        return lines

    def _refresh_content(self) -> None:
        """Refresh the help content area."""
        scroller = self.query_one("#help-content", VerticalScroll)
        # Remove existing children
        for child in list(scroller.children):
            child.remove()

        lines = self._render_help()
        if not lines:
            scroller.mount(Label("No results", classes="no-results"))
        else:
            for text, style in lines:
                if text:
                    label = Label(text)
                    if style:
                        label.add_class(style.replace(" ", "-"))
                    scroller.mount(label)
                else:
                    scroller.mount(Label(""))  # spacer

        # Scroll to top
        scroller.scroll_home(animate=False)

    def on_mount(self) -> None:
        self._refresh_content()

    def action_start_search(self) -> None:
        """Activate search mode."""
        self._search_mode = True
        search_input = self.query_one("#search-input", Input)
        search_input.add_class("-active")
        search_input.focus()

    def action_clear_search(self) -> None:
        """Exit search mode and clear query."""
        self._search_mode = False
        self._search_query = ""
        search_input = self.query_one("#search-input", Input)
        search_input.remove_class("-active")
        search_input.value = ""
        # Return focus to the scroller for vim nav
        self.query_one("#help-content", VerticalScroll).focus()
        self._refresh_content()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update search results as user types."""
        if event.control.id == "search-input":
            self._search_query = event.value.strip()
            self._refresh_content()

    def action_page_up(self) -> None:
        scroller = self.query_one("#help-content", VerticalScroll)
        scroller.scroll_page_up()

    def action_page_down(self) -> None:
        scroller = self.query_one("#help-content", VerticalScroll)
        scroller.scroll_page_down()


# ── Log viewer screen --------------------------------------------------------


class LogViewerScreen(ModalScreen[None]):
    """Enhanced log viewer modal with page controls, search, and level colours.

    Features:
    - Page up/down (PgUp/PgDn) to load more/fewer log lines
    - Level-based colouring (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    - Timestamps on every line
    - Vim nav: j/k to scroll, q/Esc to close
    - Status bar showing line count and filter state
    """

    BINDINGS = [
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("q", "dismiss", "Close", show=True),
        Binding("escape", "dismiss", "Close", show=True),
        Binding("pageup", "page_up", "PgUp", show=True),
        Binding("pagedown", "page_down", "PgDn", show=True),
        Binding("/", "start_search", "Filter", show=True),
    ]

    DEFAULT_CSS = """
    LogViewerScreen {
        align: middle middle;
        width: 80%;
        height: 80%;
        min-width: 50;
        min-height: 15;
        background: $surface;
        border: solid $border;
    }

    LogViewerScreen #log-header {
        height: 2;
        padding: 0 2;
        content-align: left middle;
        border-bottom: solid $border;
    }

    LogViewerScreen #log-title {
        width: 1fr;
        style: bold text;
    }

    LogViewerScreen #log-search {
        height: 3;
        margin: 0 1;
        border: solid $accent;
        display: none;
    }

    LogViewerScreen #log-search.-active {
        display: block;
    }

    LogViewerScreen #log-content {
        height: 1fr;
        padding: 0 1;
    }

    LogViewerScreen #log-footer {
        height: 2;
        padding: 0 2;
        content-align: left middle;
        border-top: solid $border;
        color: $text-muted;
    }
    """

    def __init__(self, telemetry: Any) -> None:
        super().__init__()
        self._telemetry = telemetry
        self._line_count = 50
        self._page_size = 50
        self._min_lines = 10
        self._filter_query = ""
        self._search_mode = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="log-header"):
            yield Label("Log Viewer", id="log-title")
        yield Input(placeholder="Filter logs...", id="log-search")
        yield RichLog(id="log-content", highlight=True, markup=True)
        with Horizontal(id="log-footer"):
            yield Label("j/k: scroll  /: filter  PgUp/PgDn: more/fewer  q: close")

    def _apply_log_colours(self, line: str) -> str:
        """Return markup-wrapped line with colour based on log level."""
        for level, style in _LOG_LEVEL_COLORS.items():
            tag = f"[{level}]"
            if tag in line:
                if style:
                    return f"[{style}]{line}[/]"
                # INFO gets default (no wrapping)
                return line
        return line

    def _load_lines(self) -> list[str]:
        """Load and filter log lines from telemetry."""
        all_lines = self._telemetry.get_recent_lines(self._line_count * 4)
        if self._filter_query:
            q = self._filter_query.lower()
            all_lines = [line for line in all_lines if q in line.lower()]
        return all_lines[-self._line_count:]

    def _refresh(self) -> None:
        """Reload and display filtered, coloured log lines."""
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.clear()
        for line in self._load_lines():
            coloured = self._apply_log_colours(line)
            log_widget.write(coloured)

    def on_mount(self) -> None:
        self._refresh()

    def action_page_down(self) -> None:
        """Load more log lines."""
        self._line_count += self._page_size
        self._refresh()

    def action_page_up(self) -> None:
        """Show fewer log lines."""
        self._line_count = max(self._min_lines, self._line_count - self._page_size)
        self._refresh()

    def action_start_search(self) -> None:
        """Activate filter mode."""
        self._search_mode = True
        search_input = self.query_one("#log-search", Input)
        search_input.add_class("-active")
        search_input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update filter results as user types."""
        if event.control.id == "log-search":
            self._filter_query = event.value.strip()
            self._refresh()

    def action_scroll_down(self) -> None:
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.scroll_down()

    def action_scroll_up(self) -> None:
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.scroll_up()


class NexusApp(App):
    """Main NexusAgent TUI application."""

    TITLE = "NexusAgent"
    SUB_TITLE = "AI Coding Agent"

    # Telemetry instance
    telemetry: TelemetryManager | None = None

    def __init__(self, session_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.session_id = session_id
        self._busy = False
        self._pending_inputs: list[str] = []
        self._current_assistant: AssistantMessage | None = None
        self._current_tool: ToolCallMessage | None = None
        self._theme_name = "nexus-dark"
        self._gc_frozen = False
        self._is_ascii_mode = False

    def _get_theme(self) -> str:
        """Determine which theme to use."""
        # Check for theme preference in environment or config
        # For now, use the stored theme name
        return self._theme_name

    def _is_ascii_terminal(self) -> bool:
        """Detect if we're in an ASCII-only terminal (no color support)."""
        # Check common indicators
        if os.environ.get("TERM") == "dumb":
            return True
        if os.environ.get("COLORTERM") == "":
            return True
        # Check if NO_COLOR is set
        if os.environ.get("NO_COLOR"):
            return True
        return False

    def compose(self) -> ComposeResult:
        """Create child widgets for the TUI."""
        # Register themes
        register_themes(self)

        # Main layout: VerticalScroll for chat, then input, then status bar
        # NO HEADER WIDGET - saves 1 line of real estate
        with VerticalScroll(id="chat"):
            yield Container(id="messages", layout="stream")
        yield ChatInput(id="input-area")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Enable garbage collection freeze before first paint (performance)
        if not self._gc_frozen:
            try:
                import gc
                gc.freeze()
                self._gc_frozen = True
                logger.debug("Garbage collection frozen")
            except Exception:
                pass

        # Detect ASCII mode
        self._is_ascii_mode = self._is_ascii_terminal()
        if self._is_ascii_mode:
            logger.info("ASCII terminal detected - disabling colors")

        # Set theme (will be overridden if ASCII mode)
        if not self._is_ascii_mode:
            self.theme = self._get_theme()
        else:
            # In ASCII mode, use a minimal theme
            self.theme = "textual"

        # Setup telemetry
        self.telemetry = setup_telemetry(self)
        logger.info(f"NexusAgent TUI started - session {self.session_id}")
        logger.info(f"Theme: {self._theme_name}, ASCII mode: {self._is_ascii_mode}")

        # Show welcome banner
        messages = self.query_one("#messages", Container)
        welcome = WelcomeBanner(session_id=self.session_id)
        messages.mount(welcome)

        # Focus input
        self.query_one("#input-area", ChatInput).focus()

    def on_unmount(self) -> None:
        """Called when app is unmounted."""
        # Restore garbage collection
        if self._gc_frozen:
            try:
                import gc
                gc.unfreeze()
                self._gc_frozen = False
                logger.debug("Garbage collection unfrozen")
            except Exception:
                pass

        # Log final metrics
        if self.telemetry:
            metrics = self.telemetry.get_metrics()
            logger.info(f"Session ended - metrics: {metrics}")

    def on_key(self, event: Key) -> None:
        """Handle global key presses."""
        if event.key == "ctrl+c":
            self._handle_interrupt()
            event.prevent_default()
            event.stop()
        elif event.key == "f1":
            # F1 to show help
            self.action_show_help()
            event.prevent_default()
            event.stop()
        elif event.key == "f2":
            # F2 to show logs
            self.action_show_logs()
            event.prevent_default()
            event.stop()
        elif event.key == "f3":
            # F3 to switch theme
            self.action_switch_theme()
            event.prevent_default()
            event.stop()
        elif event.key == "f12":
            # F12 to toggle devtools (if enabled)
            self.action_toggle_devtools()
            event.prevent_default()
            event.stop()

    def _handle_interrupt(self) -> None:
        """Handle Ctrl+C interrupt."""
        if self._busy:
            self.notify("Interrupting...", timeout=2)
            self.post_message(self.InterruptRequested())
        else:
            self.exit()

    # Theme switching

    def action_switch_theme(self) -> None:
        """Cycle through available themes."""
        themes = ["nexus-dark", "catppuccin-mocha", "gruvbox-dark", "nord"]
        current_idx = themes.index(self._theme_name) if self._theme_name in themes else 0
        next_idx = (current_idx + 1) % len(themes)
        self._theme_name = themes[next_idx]
        if not self._is_ascii_mode:
            self.theme = self._theme_name
        self.notify(f"Theme: {self._theme_name}", timeout=1.5)
        logger.info(f"Switched to theme: {self._theme_name}")

    # Log viewer

    def action_show_logs(self) -> None:
        """Show the log viewer modal with search, filter, and page controls."""
        if self.telemetry:
            self.push_screen(LogViewerScreen(self.telemetry))

    # Help screen

    def action_show_help(self) -> None:
        """Show the searchable help screen with categories and vim nav."""
        self.push_screen(HelpScreen())

    # Clear chat

    def action_clear_chat(self) -> None:
        """Clear the chat history."""
        messages = self.query_one("#messages", Container)
        # Remove all messages
        for child in list(messages.children):
            child.remove()
        # Add welcome banner back
        welcome = WelcomeBanner(session_id=self.session_id)
        messages.mount(welcome)
        self.notify("Chat cleared", timeout=1)
        logger.info("Chat cleared by user")

    def action_show_model(self) -> None:
        """Show current model information."""
        try:
            from nexusagent.config import settings
            model_name = getattr(settings.agent, 'default_model', 'unknown')
        except Exception:
            model_name = "unknown"
        self.notify(f"Model: {model_name}", timeout=3)
        logger.info(f"Model info requested: {model_name}")

    # Event stream consumer

    async def consume_event_stream(self, session) -> None:
        """Consume events from the session's event stream and update the TUI.

        This runs as a background task, processing events from the session's
        async queue and updating the message widgets in real-time.
        """
        messages = self.query_one("#messages", Container)
        try:
            async for event in session.event_stream():
                etype = event.get("type", "")

                if etype == "thinking":
                    # Show thinking indicator
                    thinking_msg = AppMessage(event.get("content", "Thinking..."))
                    messages.mount(thinking_msg)
                    self._scroll_to_bottom()

                elif etype == "response_chunk":
                    # Streaming token — append to current assistant message
                    content = event.get("content", "")
                    if content:
                        if self._current_assistant is None:
                            # Remove welcome banner on first response
                            self._remove_welcome_banner(messages)
                            self._current_assistant = AssistantMessage()
                            messages.mount(self._current_assistant)
                        await self._current_assistant.append_token(content)
                        self._scroll_to_bottom()

                elif etype == "response":
                    # Final response — finalize the assistant message
                    if self._current_assistant is not None:
                        self._current_assistant.finalize(event.get("content", ""))
                        self._current_assistant = None
                    self._busy = False
                    self._scroll_to_bottom()

                elif etype == "tool_call":
                    # Show tool call
                    tool = event.get("tool", "unknown")
                    args = event.get("args", {})
                    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items()) if isinstance(args, dict) else str(args)
                    tool_msg = ToolCallMessage(tool=tool, args=args_str)
                    messages.mount(tool_msg)
                    self._current_tool = tool_msg
                    self._scroll_to_bottom()

                elif etype == "tool_result":
                    # Update the current tool call with result
                    output = event.get("output", "")
                    status = event.get("status", "success")
                    if self._current_tool is not None:
                        self._current_tool.update_output(output)
                        self._current_tool.update_status(status)
                        self._current_tool = None
                    elif output:
                        # Fallback: show as app message if no tool is tracked
                        result_msg = AppMessage(f"  ↳ {output[:200]}")
                        messages.mount(result_msg)
                    self._scroll_to_bottom()

                elif etype == "error":
                    error_msg = ErrorMessage(event.get("message", "Unknown error"))
                    messages.mount(error_msg)
                    self._current_assistant = None
                    self._busy = False
                    self._scroll_to_bottom()

                elif etype == "session_closed":
                    break

        except Exception as exc:
            logger.error(f"Event stream consumer error: {exc}", exc_info=True)

    def _remove_welcome_banner(self, messages: Container) -> None:
        """Remove the welcome banner if it exists."""
        for child in list(messages.children):
            if isinstance(child, WelcomeBanner):
                child.remove()

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat area to the bottom."""
        try:
            chat = self.query_one("#chat", VerticalScroll)
            chat.scroll_end(animate=False)
        except Exception:
            pass

    # Input handling

    def on_chat_input_submitted(self, message: ChatInput.Submitted) -> None:
        """Handle chat input submission."""
        text = message.text.strip()

        # Slash command dispatch
        if text.startswith("/"):
            command = text.split()[0].lower()
            if command == "/help":
                self.action_show_help()
                return
            elif command == "/logs":
                self.action_show_logs()
                return
            elif command == "/theme":
                self.action_switch_theme()
                return
            elif command == "/clear":
                self.action_clear_chat()
                return
            elif command == "/model":
                self.action_show_model()
                return
            else:
                self.notify(f"Unknown command: {command}. Type /help for available commands.", timeout=3)
                return

        if self._busy:
            # Queue the input
            self._pending_inputs.append(text)
            self.notify("Message queued", timeout=1)
            return

        # Log the message
        if self.telemetry:
            self.telemetry.log_message(text, is_user=True)

        # Send to session via custom event (handled by main app)
        self.post_message(
            self.UserInput(
                content=text,
                images=message.images,
            )
        )

    # Custom messages

    class UserInput:
        """Message sent when user submits input."""

        def __init__(self, content: str, images: list[str] | None = None) -> None:
            self.content = content
            self.images = images or []

    class InterruptRequested:
        """Message sent when user requests interrupt (Ctrl+C)."""

        pass
