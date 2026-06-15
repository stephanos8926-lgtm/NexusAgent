"""Telemetry and logging system for NexusAgent.

Provides structured logging to file, session metrics, and an in-app log viewer.
"""

from __future__ import annotations

import logging
import logging.handlers
import time
from pathlib import Path
from typing import Any

from textual.app import App
from textual.widgets import Static

logger = logging.getLogger("nexusagent.telemetry")


class TelemetryManager:
    """Manages telemetry collection and structured logging."""

    def __init__(self, app: App) -> None:
        """Initialize telemetry collection for the given app.

        Args:
            app: The Textual app instance to attach telemetry to.
        """
        self.app = app
        self.session_start = time.time()
        self.tool_calls: list[dict] = []
        self.errors: list[dict] = []
        self.messages_sent = 0
        self.tokens_used = 0
        self.log_file = self._setup_logging()

    def _setup_logging(self) -> Path:
        """Set up rotating file logging."""
        log_dir = Path.home() / ".nexusagent" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "tui.log"

        # Rotating file handler: 5MB x 3 files
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        # Add to our logger
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Also capture warnings from other modules
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.WARNING)

        logger.info(f"Telemetry initialized - logging to {log_file}")
        return log_file

    def log_tool_call(self, tool: str, args: dict, result: Any = None, error: str | None = None) -> None:
        """Log a tool call for telemetry."""
        entry = {
            "timestamp": time.time(),
            "tool": tool,
            "args": args,
            "result": str(result)[:200] if result else None,
            "error": error,
        }
        self.tool_calls.append(entry)
        logger.info(f"Tool call: {tool}", extra={"tool_call": entry})

        if error:
            self.log_error(f"Tool {tool} failed: {error}")

    def log_error(self, message: str, exc_info: bool = False) -> None:
        """Log an error."""
        entry = {
            "timestamp": time.time(),
            "message": message,
        }
        self.errors.append(entry)
        logger.error(message, exc_info=exc_info)

    def log_message(self, content: str, is_user: bool = True) -> None:
        """Log a message sent/received."""
        self.messages_sent += 1
        logger.debug(
            f"Message {'sent' if is_user else 'received'}: {content[:100]}..."
        )

    def log_tokens(self, count: int) -> None:
        """Log token usage."""
        self.tokens_used += count
        logger.debug(f"Tokens used: {count} (total: {self.tokens_used})")

    def get_metrics(self) -> dict[str, Any]:
        """Get current telemetry metrics."""
        uptime = time.time() - self.session_start
        return {
            "uptime_seconds": uptime,
            "messages_sent": self.messages_sent,
            "tool_calls_count": len(self.tool_calls),
            "errors_count": len(self.errors),
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls[-10:],  # last 10
            "errors": self.errors[-5:],  # last 5
        }

    def get_recent_logs(self, lines: int = 50) -> list[str]:
        """Get recent log lines from the log file."""
        return self.get_recent_lines(lines)

    def get_recent_lines(self, lines: int = 50) -> list[str]:
        """Get recent log lines from the log file (alias for get_recent_logs)."""
        if not self.log_file.exists():
            return ["No log file yet"]

        try:
            with open(self.log_file, encoding="utf-8") as f:
                all_lines = f.readlines()
                return [line.rstrip() for line in all_lines[-lines:]]
        except Exception as e:
            return [f"Error reading logs: {e}"]


class LogViewer(Static):
    """Widget to display recent log entries."""

    def __init__(self, telemetry: TelemetryManager, **kwargs: Any) -> None:
        """Initialize the log viewer widget.

        Args:
            telemetry: The telemetry manager to read logs from.
            **kwargs: Additional keyword arguments passed to ``Static``.
        """
        super().__init__("", **kwargs)
        self.telemetry = telemetry
        self._lines = 100

    def on_mount(self) -> None:
        """Refresh logs when the widget is mounted."""
        self.update_logs()

    def update_logs(self) -> None:
        """Update the displayed logs."""
        logs = self.telemetry.get_recent_logs(self._lines)
        self.update("\n".join(logs))

    def action_scroll_down(self) -> None:
        """Scroll down to show older logs."""
        self._lines += 50
        self.update_logs()

    def action_scroll_up(self) -> None:
        """Scroll up to show newer logs."""
        self._lines = max(20, self._lines - 50)
        self.update_logs()


def setup_telemetry(app: App) -> TelemetryManager:
    """Set up telemetry for the app."""
    return TelemetryManager(app)
