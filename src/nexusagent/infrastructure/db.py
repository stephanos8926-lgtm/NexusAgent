"""Compat shim  imports from db/ subpackage.

All existing ``from nexusagent.infrastructure.db import ...`` usage continues
to work. New code should import from ``nexusagent.infrastructure.db`` (the
subpackage) directly.
"""

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
    get_db_manager,
    get_session_repo,
    get_task_repo,
    session_repo,
    set_db_manager,
    set_session_repo,
    set_task_repo,
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
    "get_db_manager",
    "get_session_repo",
    "get_task_repo",
    "session_repo",
    "set_db_manager",
    "set_session_repo",
    "set_task_repo",
    "task_repo",
]
