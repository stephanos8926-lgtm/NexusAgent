"""Session manager for interactive WebSocket sessions.

Provides:
- Session: a single conversation with message flow, event streaming, approval gates
- SessionManager: lifecycle/cache manager for Session instances
"""

from __future__ import annotations

from nexusagent.core.session.manager import (
    SessionManager,
    get_session_manager,
    session_manager,
    set_session_manager,
)
from nexusagent.core.session.session import Session

__all__ = [
    "Session",
    "SessionManager",
    "get_session_manager",
    "session_manager",
    "set_session_manager",
]
