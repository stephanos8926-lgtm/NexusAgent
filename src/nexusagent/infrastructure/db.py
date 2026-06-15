"""Compat shim — imports from db/ subpackage.

All existing ``from nexusagent.infrastructure.db import ...`` usage continues
to work. New code should import from ``nexusagent.infrastructure.db`` (the
subpackage) directly.
"""

from nexusagent.infrastructure.db import *
from nexusagent.infrastructure.db import (
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
