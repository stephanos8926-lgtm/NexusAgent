"""TUI widgets, modals, and responsive layout utilities.

Extracted from interfaces/tui.py to reduce the 1433L monolith.
Contains: SpinnerLabel, Breakpoint, ApprovalModal, ErrorModal,
NO_COLOR detection, SIGWINCH handling, terminal size utilities.
"""

import enum
import logging
import os
import shutil
import time
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Static

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# SpinnerLabel — animated spinner + text
# ═══════════════════════════════════════════════════════════════════════════

# Canonical spinner characters — single source of truth
SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class SpinnerLabel(Horizontal):
    """Label with an animated spinner prefix."""

    spinner_chars = SPINNER_CHARS
    tick = reactive(0)

    def __init__(self, text: str = "Ready", **kwargs):
        """Initialize the SpinnerLabel.

        Args:
            text: The label text to display.
            **kwargs: Additional keyword arguments passed to the Horizontal container.
        """
        super().__init__(**kwargs)
        self._text = text
        self._timer: Timer | None = None
        self._spinning = False

    def compose(self) -> ComposeResult:
        """Compose the spinner icon and text widgets."""
        yield Static("", id="spinner-icon")
        yield Static("", id="spinner-text")

    def on_mount(self) -> None:
        """Update the display on initial mount."""
        self.update_display()

    def set_text(self, text: str, spinning: bool = False):
        """Set the label text and spinner state.

        Args:
            text: The label text to display.
            spinning: If True, animate the spinner.
        """
        self._text = text
        if spinning and not self._spinning:
            self._spinning = True
            self._timer = self.set_interval(0.1, self._tick_spinner)
        elif not spinning and self._spinning:
            self._spinning = False
            if self._timer:
                self._timer.stop()
                self._timer = None
        self.update_display()

    def _tick_spinner(self):
        self.tick += 1

    def watch_tick(self):
        """React to tick changes by updating the display."""
        self.update_display()

    def update_display(self):
        """Update the spinner icon and text on the next animation tick."""
        try:
            spinner = ""
            if self._spinning:
                spinner = self.spinner_chars[int(self.tick) % len(self.spinner_chars)]
            self.query_one("#spinner-icon", Static).update(spinner)
            self.query_one("#spinner-text", Static).update(self._text)
        except Exception:
            pass  # Spinner update is best-effort, never crash the UI

    def on_unmount(self):
        """Stop the spinner timer when the widget is unmounted from the DOM."""
        if self._timer:
            self._timer.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Responsive breakpoints
# ═══════════════════════════════════════════════════════════════════════════


class Breakpoint(enum.Enum):
    """Terminal width breakpoints for responsive layout."""

    WIDE = "wide"  # > 120 cols
    STANDARD = "standard"  # 80-120 cols
    NARROW = "narrow"  # 60-79 cols
    TOO_SMALL = "too_small"  # < 60 cols


# Width thresholds
_WIDE_THRESHOLD = 120
_STANDARD_THRESHOLD = 80
_NARROW_THRESHOLD = 60


def classify_breakpoint(width: int) -> Breakpoint:
    """Classify a terminal width into a responsive breakpoint."""
    if width > _WIDE_THRESHOLD:
        return Breakpoint.WIDE
    if width >= _STANDARD_THRESHOLD:
        return Breakpoint.STANDARD
    if width >= _NARROW_THRESHOLD:
        return Breakpoint.NARROW
    return Breakpoint.TOO_SMALL


# ── Accessibility: NO_COLOR + monochrome fallback ─────────────────────────

# https://no-color.org — check at module load time
NO_COLOR: bool = "NO_COLOR" in os.environ


def is_no_color() -> bool:
    """Check if NO_COLOR is set (respects https://no-color.org spec)."""
    return "NO_COLOR" in os.environ


# ── Debounced resize (SIGWINCH) ──────────────────────────────────────────

_DEFAULT_DEBOUNCE_SECONDS = 0.2


def debounce_resize(
    state: dict[str, float],
    current_time: float,
    debounce_seconds: float = _DEFAULT_DEBOUNCE_SECONDS,
) -> bool:
    """Debounce resize events to avoid excessive re-renders."""
    last = state.get("last_resize_time")
    if last is None:
        state["last_resize_time"] = current_time
        return True
    if current_time - last >= debounce_seconds:
        state["last_resize_time"] = current_time
        return True
    return False


def _get_terminal_size() -> tuple[int, int]:
    """Get terminal size as (columns, rows). Falls back to (80, 24)."""
    try:
        size = shutil.get_terminal_size()
        return (size.columns, size.lines)
    except OSError:
        return (80, 24)


def _sigwinch_handler(app: Any) -> None:
    """Handle SIGWINCH (window resize signal) with debounce."""
    try:
        now = time.monotonic()
        if not debounce_resize(app._resize_state, now):
            return

        cols, _ = _get_terminal_size()
        new_bp = classify_breakpoint(cols)
        old_bp = app._breakpoint
        app._breakpoint = new_bp

        if new_bp != old_bp:
            logger.debug(f"Breakpoint changed: {old_bp.value} -> {new_bp.value} ({cols} cols)")

        if new_bp == Breakpoint.TOO_SMALL:
            app.notify(
                f"Terminal too small ({cols} cols). Minimum 60 cols recommended.",
                severity="warning",
                timeout=3,
            )
    except Exception as exc:
        logger.debug(f"SIGWINCH handler error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# ApprovalModal — tool call approval dialog
# ═══════════════════════════════════════════════════════════════════════════


class ApprovalModal(ModalScreen[bool]):
    """Modal dialog for approving or rejecting a tool call before execution."""

    DEFAULT_CSS = """
    ApprovalModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #approval-dialog {
        width: 70;
        height: 18;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
        layout: vertical;
    }
    #approval-title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    #approval-scroll {
        height: 10;
        overflow-y: scroll;
        margin-bottom: 1;
        border: solid $border-subtle;
        padding: 1;
    }
    #approval-buttons {
        align: center middle;
    }
    """

    def __init__(self, tool_name: str, tool_args: dict, call_id: str = "") -> None:
        """Initialize the approval modal.

        Args:
            tool_name: Name of the tool to be approved.
            tool_args: Arguments the tool will be called with.
            call_id: Unique identifier for this tool call request.
        """
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.call_id = call_id

    def compose(self) -> ComposeResult:
        """Build the approval dialog UI with scrollable args and action buttons."""
        with Vertical(id="approval-dialog"):
            yield Static(f"⚡ Approval Required: {self.tool_name}", id="approval-title")
            with ScrollableContainer(id="approval-scroll"):
                args_str = "\n".join(f"  {k}: {v}" for k, v in self.tool_args.items())
                yield Static(args_str, id="approval-args")
            with Horizontal(id="approval-buttons"):
                yield Button("✓ Approve", id="approve", variant="success")
                yield Button("✗ Reject", id="reject", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Approve/Reject/Cancel button presses."""
        if event.button.id == "approve":
            self.dismiss(True)
        else:
            self.dismiss(False)


# ═══════════════════════════════════════════════════════════════════════════
# ErrorModal — error display dialog
# ═══════════════════════════════════════════════════════════════════════════


class ErrorModal(ModalScreen[None]):
    """Modal dialog for displaying errors."""

    DEFAULT_CSS = """
    ErrorModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #error-dialog {
        width: 60;
        height: 14;
        border: thick $error;
        background: $surface;
        padding: 1 2;
        layout: vertical;
    }
    #error-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    #error-scroll {
        height: 6;
        overflow-y: scroll;
        margin-bottom: 1;
        border: solid $border-subtle;
        padding: 1;
    }
    #error-buttons {
        align: center middle;
    }
    """

    # Let's override compose to use error-dialog and error-scroll classes
    def compose(self) -> ComposeResult:
        with Vertical(id="error-dialog"):
            yield Static("⚠ Error", id="error-title")
            with ScrollableContainer(id="error-scroll"):
                yield Static(self.error_message, id="error-args")
            with Horizontal(id="error-buttons"):
                yield Button("OK", id="ok", variant="primary")


    def __init__(self, error_message: str) -> None:
        """Initialize the error modal with the message to display."""
        super().__init__()
        self.error_message = error_message



    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss the error dialog when OK is pressed."""


# ═══════════════════════════════════════════════════════════════════════════
# ThreadsModal — interactive session switcher
# ═══════════════════════════════════════════════════════════════════════════

class ThreadsModal(ModalScreen[str | None]):
    """Modal dialog for browsing and switching between previous sessions."""

    DEFAULT_CSS = """
    ThreadsModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #threads-dialog {
        width: 70;
        height: 22;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
        layout: vertical;
    }
    #threads-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    #threads-scroll {
        height: 12;
        overflow-y: scroll;
        margin-bottom: 1;
        border: solid $border-subtle;
        padding: 1;
    }
    .thread-button {
        width: 100%;
        margin-bottom: 1;
        text-align: left;
    }
    #threads-buttons {
        align: center middle;
    }
    """

    def __init__(self, sessions: list[dict]) -> None:
        """Initialize the ThreadsModal with session list."""
        super().__init__()
        self.sessions = sessions

    def compose(self) -> ComposeResult:
        """Compose the interactive session switcher UI."""
        with Vertical(id="threads-dialog"):
            yield Static("📑 Switch Active Session", id="threads-title")
            with ScrollableContainer(id="threads-scroll"):
                if not self.sessions:
                    yield Static("No other sessions found.", id="no-sessions")
                else:
                    for s in self.sessions:
                        sid = s.get("id", "unknown")
                        wdir = s.get("working_dir", "")
                        status = s.get("status", "unknown")
                        label = f"{sid[:12]}...  [{status.upper()}]  Dir: {wdir}"
                        yield Button(label, id=f"sess_{sid}", classes="thread-button")
            with Horizontal(id="threads-buttons"):
                yield Button("Cancel", id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle session selection or cancel."""
        btn_id = event.button.id or ""
        if btn_id == "cancel":
            self.dismiss(None)
        elif btn_id.startswith("sess_"):
            selected_id = btn_id[5:]  # Strip 'sess_'
            self.dismiss(selected_id)


# ═══════════════════════════════════════════════════════════════════════════
# ModelModal — interactive model switcher
# ═══════════════════════════════════════════════════════════════════════════

class ModelModal(ModalScreen[tuple[str, str] | None]):
    """Modal dialog for switching active LLM models mid-session."""

    DEFAULT_CSS = """
    ModelModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #model-dialog {
        width: 60;
        height: 18;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
        layout: vertical;
    }
    #model-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    #model-scroll {
        height: 8;
        overflow-y: scroll;
        margin-bottom: 1;
        border: solid $border-subtle;
        padding: 1;
    }
    .model-button {
        width: 100%;
        margin-bottom: 1;
    }
    #model-buttons {
        align: center middle;
    }
    """

    MODELS: ClassVar[list[tuple[str, str, str]]] = [
        ("gemini-2.5-flash", "gemini", "Gemini 2.5 Flash (Fast, default)"),
        ("gemini-2.5-pro", "gemini", "Gemini 2.5 Pro (Powerful, reasoning)"),
        ("anthropic/claude-3.5-sonnet", "openrouter", "Claude 3.5 Sonnet (State-of-the-art)"),
        ("openai/gpt-4o", "openrouter", "GPT-4o (High capability)"),
        ("google/gemini-2.5-pro", "openrouter", "Gemini 2.5 Pro via OpenRouter"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the interactive model switcher UI."""
        with Vertical(id="model-dialog"):
            yield Static("🤖 Switch LLM Model", id="model-title")
            with ScrollableContainer(id="model-scroll"):
                for i, (_model, _provider, desc) in enumerate(self.MODELS):
                    yield Button(desc, id=f"model_{i}", classes="model-button")
            with Horizontal(id="model-buttons"):
                yield Button("Cancel", id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle model selection or cancel."""
        btn_id = event.button.id or ""
        if btn_id == "cancel":
            self.dismiss(None)
        elif btn_id.startswith("model_"):
            idx = int(btn_id[6:])  # Strip 'model_'
            model, provider, _ = self.MODELS[idx]
            self.dismiss((model, provider))
