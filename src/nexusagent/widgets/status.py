"""Status bar widget for NexusAgent TUI.

Single-line status bar docked at bottom of screen.
Shows: mode | status message | spinner | CWD | branch | tokens | model

Responsive behavior:
- Width > 120: show everything
- Width 80-120: hide branch
- Width 60-80: hide branch + CWD
- Width < 60: show only status + spinner

Design: Linear-inspired, uses $surface background, semantic colors.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.containers import Horizontal
from textual.content import Content
from textual.css.query import NoMatches
from textual.geometry import Size
from textual.reactive import reactive
from textual.widgets import Static

if TYPE_CHECKING:
    from textual import events
    from textual.app import ComposeResult, RenderResult

logger = logging.getLogger(__name__)


class ModelLabel(Static):
    """Model name label with smart truncation.

    When the full provider:model text doesn't fit:
    1. Drop the provider prefix
    2. Left-truncate the model name with leading ellipsis
    """

    DEFAULT_CSS = """
    ModelLabel {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._provider = ""
        self._model = ""

    def set_model(self, provider: str, model: str) -> None:
        self._provider = provider
        self._model = model
        self.refresh()

    def render(self) -> Content:
        if not self._model:
            return Content("")
        full = f"{self._provider}:{self._model}" if self._provider else self._model
        width = self.content_size.width
        if width <= 0:
            return Content(full)
        if len(full) <= width:
            return Content(full)
        # Drop provider, try model alone
        if len(self._model) <= width:
            return Content(self._model)
        # Left-truncate model
        if width > 1:
            return Content("…" + self._model[-(width - 1):])
        return Content("…")


class StatusBar(Horizontal):
    """Single-line status bar docked at bottom.

    Layout: [status_message.............................] [CWD] [branch] [tokens] [model]
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        background: $surface;
    }

    StatusBar .status-message {
        width: 1fr;
        padding: 0 1;
        color: $text-secondary;
    }

    StatusBar .status-cwd {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }

    StatusBar .status-branch {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }

    StatusBar .status-tokens {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }

    StatusBar .status-spinner {
        width: 2;
        padding: 0 0;
        color: $warning;
    }
    """

    # Spinner characters (braille dots)
    SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._status_message = "Ready"
        self._cwd = ""
        self._branch = ""
        self._tokens = 0
        self._model_provider = ""
        self._model_name = ""
        self._spinning = False
        self._spinner_idx = 0
        self._context_used = 0
        self._context_limit = 0

    def compose(self) -> ComposeResult:
        yield Static("", id="status-spinner")
        yield Static("Ready", id="status-message")
        yield Static("", id="status-cwd")
        yield Static("", id="status-branch")
        yield Static("", id="status-tokens")
        yield Static("", id="status-context")
        yield ModelLabel(id="status-model")

    def on_mount(self) -> None:
        self._update_widgets()
        # Drive spinner animation at 100ms intervals
        self.set_interval(0.1, self._animate_spinner)

    def _animate_spinner(self) -> None:
        """Advance the spinner on each timer tick."""
        if self._spinning:
            self._spinner_idx += 1
            try:
                self.query_one("#status-spinner", Static).update(
                    self.SPINNER_CHARS[self._spinner_idx % len(self.SPINNER_CHARS)]
                )
            except NoMatches:
                pass

    def _update_widgets(self) -> None:
        try:
            spinner = self.query_one("#status-spinner", Static)
            message = self.query_one("#status-message", Static)
            cwd = self.query_one("#status-cwd", Static)
            branch = self.query_one("#status-branch", Static)
            tokens = self.query_one("#status-tokens", Static)
            model = self.query_one("#status-model", ModelLabel)

            if self._spinning:
                spinner.update(self.SPINNER_CHARS[self._spinner_idx % len(self.SPINNER_CHARS)])
            else:
                spinner.update("")

            message.update(self._status_message)

            # Responsive: hide CWD/branch on narrow terminals
            term_width = self.content_size.width
            if self._cwd and term_width > 60:
                cwd.update(f"📁 {self._cwd}")
            else:
                cwd.update("")

            if self._branch and term_width > 80:
                branch.update(f"⎇ {self._branch}")
            else:
                branch.update("")

            if self._tokens > 0:
                tokens.update(f"⚡ {self._tokens:,}")
            else:
                tokens.update("")

            model.set_model(self._model_provider, self._model_name)

            # Context window bar
            try:
                ctx_widget = self.query_one("#status-context", Static)
                if self._context_limit > 0:
                    pct = min(100, int(self._context_used / self._context_limit * 100))
                    if pct >= 90:
                        ctx_color = "red"
                    elif pct >= 70:
                        ctx_color = "yellow"
                    else:
                        ctx_color = "green"
                    ctx_widget.update(f"[{ctx_color}]ctx {pct}%[/{ctx_color}]")
                else:
                    ctx_widget.update("")
            except NoMatches:
                pass

        except NoMatches:
            pass

    def set_status(self, msg: str) -> None:
        self._status_message = msg
        self._update_widgets()

    def set_cwd(self, cwd: str) -> None:
        self._cwd = cwd
        self._update_widgets()

    def set_branch(self, branch: str) -> None:
        self._branch = branch
        self._update_widgets()

    def set_tokens(self, count: int) -> None:
        self._tokens = count
        self._update_widgets()

    def set_model(self, provider: str, model: str) -> None:
        self._model_provider = provider
        self._model_name = model
        self._update_widgets()

    def set_context(self, used: int, total: int) -> None:
        """Update context window usage display."""
        self._context_used = used
        self._context_limit = total
        self._update_widgets()

    def set_spinner(self, spinning: bool) -> None:
        self._spinning = spinning
        if spinning:
            self._spinner_idx = 0
        self._update_widgets()

    def tick_spinner(self) -> None:
        """Advance spinner animation (call from timer)."""
        if self._spinning:
            self._spinner_idx += 1
            try:
                spinner = self.query_one("#status-spinner", Static)
                spinner.update(self.SPINNER_CHARS[self._spinner_idx % len(self.SPINNER_CHARS)])
            except NoMatches:
                pass


# ── NO_COLOR Detection ────────────────────────────────────────────────────

NO_COLOR: bool = bool(os.environ.get("NO_COLOR"))


# ── Git Status ────────────────────────────────────────────────────────────


def _run_git(*args: str) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


class GitStatus:
    """Detect and display git working tree status.

    States:
    - "clean"  — no changes
    - "dirty"  — unstaged or untracked changes
    - "staged" — staged changes (may also have dirty)
    - None     — not in a git repo
    """

    @staticmethod
    def detect() -> str | None:
        """Detect the current git status.
        Returns 'clean', 'dirty', 'staged', or None.
        """
        output = _run_git("status", "--porcelain")
        if output is None:
            return None
        if not output.strip():
            return "clean"
        # Check for staged changes (lines starting with [MADRC])
        has_staged = False
        has_dirty = False
        for line in output.splitlines():
            if len(line) >= 3:
                index_status = line[0]
                work_status = line[1]
                if index_status in "MADRC":
                    has_staged = True
                if work_status in "MADRC?":
                    has_dirty = True
        if has_staged:
            return "staged"
        if has_dirty:
            return "dirty"
        return "clean"

    @staticmethod
    def label(status: str | None) -> str:
        """Return a display label for the status."""
        if status is None:
            return ""
        labels = {
            "clean": "✓ clean",
            "dirty": "✗ dirty",
            "staged": "✔ staged",
        }
        return labels.get(status, "")


# ── Context Window Bar ─────────────────────────────────────────────────────


class ContextWindowBar:
    """Shows context window usage as a percentage with color coding.

    Color thresholds:
    - < 70%: success (green)
    - 70–90%: warning (amber)
    - > 90%: danger (red)
    """

    # Color thresholds (match the default theme's status colors)
    SAFE_COLOR = "#10B981"
    WARN_COLOR = "#EB8B46"
    DANGER_COLOR = "#F7768E"

    def __init__(self, used: int, total: int) -> None:
        self.used = used
        self.total = total

    @property
    def percentage(self) -> int:
        """Context usage as integer percentage (0–100)."""
        if self.total <= 0:
            return 0
        return min(100, int(self.used / self.total * 100))

    @property
    def color(self) -> str:
        """Color code based on usage level."""
        pct = self.percentage
        if pct > 90:
            return self.DANGER_COLOR
        elif pct >= 70:
            return self.WARN_COLOR
        return self.SAFE_COLOR

    def bar(self, width: int = 10) -> str:
        """Render a textual bar string showing usage."""
        pct = self.percentage
        filled = int(width * pct / 100)
        empty = width - filled
        bar_char = "█" * filled + "░" * empty
        return f"{bar_char} {pct}%"


# ── Braille Spinner ────────────────────────────────────────────────────────


class BrailleSpinner:
    """Braille dot spinner animation frames."""

    CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self) -> None:
        self.frame = 0

    def tick(self) -> None:
        """Advance to the next frame."""
        self.frame = (self.frame + 1) % len(self.CHARS)

    def current(self) -> str:
        """Return the current braille character."""
        return self.CHARS[self.frame]

    def reset(self) -> None:
        """Reset to the first frame."""
        self.frame = 0
