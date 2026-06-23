"""NexusAgent Terminal User Interface (TUI) — compat shim.

This file is a backward-compatible re-export of the tui/ subpackage.
New code should import directly from nexusagent.interfaces.tui app.
"""

# Re-export everything from the tui subpackage
from nexusagent.interfaces.tui import *

# ── Formatters ──
# ── Message widgets (needed by tests and external imports) ──
