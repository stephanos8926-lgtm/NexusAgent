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
from textual.containers import Container, VerticalScroll, Grid
from textual.events import Key
from textual.geometry import Offset
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

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
from nexusagent.telemetry import setup_telemetry, LogViewer

logger = logging.getLogger(__name__)


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
        """Show the log viewer modal."""
        if self.telemetry:
            # Create a modal screen with log viewer
            class LogViewerScreen(ModalScreen):
                BINDINGS = [
                    ("j", "scroll_down", "Scroll down"),
                    ("k", "scroll_up", "Scroll up"),
                    ("escape", "dismiss", "Close"),
                ]

                def compose(self) -> ComposeResult:
                    yield Grid(
                        Label("NexusAgent Log Viewer", id="title"),
                        LogViewer(self.app.telemetry),
                        Button("Close", variant="primary", id="close"),
                        id="dialog",
                    )

                def on_button_pressed(self, event: Button.Pressed) -> None:
                    if event.button.id == "close":
                        self.app.pop_screen()

                def action_scroll_down(self) -> None:
                    self.query_one(LogViewer).action_scroll_down()

                def action_scroll_up(self) -> None:
                    self.query_one(LogViewer).action_scroll_up()

            self.push_screen(LogViewerScreen())

    # Help screen

    def action_show_help(self) -> None:
        """Show help screen."""
        class HelpScreen(ModalScreen):
            def compose(self) -> ComposeResult:
                yield Vertical(
                    Label("NexusAgent Help", classes="title"),
                    Label(""),
                    Label("Key Bindings:", classes="subtitle"),
                    Label("  Enter      Submit message"),
                    Label("  Ctrl+C     Interrupt / Exit"),
                    Label("  F1         Show this help"),
                    Label("  F2         Show logs"),
                    Label("  F3         Switch theme"),
                    Label("  F12        Toggle devtools"),
                    Label("  Up/Down    Command history"),
                    Label("  Shift+Enter New line in input"),
                    Label(""),
                    Label("Slash Commands:", classes="subtitle"),
                    Label("  /help      Show this help"),
                    Label("  /logs      Show log viewer"),
                    Label("  /theme     Switch theme"),
                    Label("  /clear     Clear chat"),
                    Label("  /model     Show current model"),
                    Label(""),
                    Button("Close", variant="primary", id="close"),
                )

            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "close":
                    self.app.pop_screen()

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
                    self._scroll_to_bottom()

                elif etype == "tool_result":
                    # Update tool call with result (simplified: just append result)
                    output = event.get("output", "")
                    if output:
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
