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

    def compose(self) -> ComposeResult:
        yield Static("", id="status-spinner")
        yield Static("Ready", id="status-message")
        yield Static("", id="status-cwd")
        yield Static("", id="status-branch")
        yield Static("", id="status-tokens")
        yield ModelLabel(id="status-model")

    def on_mount(self) -> None:
        self._update_widgets()

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
