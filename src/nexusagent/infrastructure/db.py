"""Compat shim — imports from db/ subpackage.

All existing ``from nexusagent.infrastructure.db import ...`` usage continues
to work. New code should import from ``nexusagent.infrastructure.db`` (the
subpackage) directly.
"""

from nexusagent.infrastructure.db import *  # noqa: F401,F403
from nexusagent.infrastructure.db import (  # noqa: E401
    Base,
    DatabaseManager,
    MessageModel,
    ResultModel,
    SessionModel,
    SessionRepository,
    TaskModel,
    TaskRepository,
    db_manager,
    session_repo,
    task_repo,
)

__all__ = [
    "Base",
    "DatabaseManager",
    "MessageModel",
    "ResultModel",
    "SessionModel",
    "SessionRepository",
    "TaskModel",
    "TaskRepository",
    "db_manager",
    "session_repo",
    "task_repo",
]
