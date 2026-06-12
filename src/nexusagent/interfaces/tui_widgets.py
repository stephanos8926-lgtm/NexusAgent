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

import signal as _signal

logger = logging.getLogger(__name__)

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Static

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
        super().__init__(**kwargs)
        self._text = text
        self._timer: Timer | None = None
        self._spinning = False

    def compose(self) -> ComposeResult:
        yield Static("", id="spinner-icon")
        yield Static("", id="spinner-text")

    def on_mount(self) -> None:
        self.update_display()

    def set_text(self, text: str, spinning: bool = False):
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
        self.update_display()

    def update_display(self):
        try:
            spinner = ""
            if self._spinning:
                spinner = self.spinner_chars[int(self.tick) % len(self.spinner_chars)]
            self.query_one("#spinner-icon", Static).update(spinner)
            self.query_one("#spinner-text", Static).update(self._text)
        except Exception:
            pass

    def on_unmount(self):
        if self._timer:
            self._timer.stop()


# ═══════════════════════════════════════════════════════════════════════════
# Responsive breakpoints
# ═══════════════════════════════════════════════════════════════════════════


class Breakpoint(enum.Enum):
    """Terminal width breakpoints for responsive layout."""
    WIDE = "wide"           # > 120 cols
    STANDARD = "standard"   # 80-120 cols
    NARROW = "narrow"         # 60-79 cols
    TOO_SMALL = "too_small" # < 60 cols


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
    def __init__(self, tool_name: str, tool_args: dict, call_id: str = "") -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.call_id = call_id

    def compose(self) -> ComposeResult:
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
        if event.button.id == "approve":
            self.dismiss(True)
        else:
            self.dismiss(False)


# ═══════════════════════════════════════════════════════════════════════════
# ErrorModal — error display dialog
# ═══════════════════════════════════════════════════════════════════════════


class ErrorModal(ModalScreen[None]):
    """Modal dialog for displaying errors."""

    def __init__(self, error_message: str) -> None:
        super().__init__()
        self.error_message = error_message

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-dialog"):
            yield Static("⚠ Error", id="approval-title")
            yield Static(self.error_message, id="approval-args")
            with Horizontal(id="approval-buttons"):
                yield Button("OK", id="ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)
