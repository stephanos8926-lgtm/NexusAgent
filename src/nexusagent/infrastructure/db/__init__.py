"""Database infrastructure — ORM models, manager, and repositories."""

from .base import Base
from .manager import DatabaseManager
from .models import MessageModel, ResultModel, SessionModel, TaskModel
from .session_repo import SessionRepository
from .task_repo import TaskRepository

__all__ = [
    # Base
    "Base",
    # Models
    "TaskModel",
    "ResultModel",
    "SessionModel",
    "MessageModel",
    # Manager
    "DatabaseManager",
    # Repositories
    "TaskRepository",
    "SessionRepository",
    # Singletons
    "db_manager",
    "task_repo",
    "session_repo",
]

# Singleton instances — created at first import (same as old db.py)
db_manager = DatabaseManager()
task_repo = TaskRepository(db_manager)
session_repo = SessionRepository(db_manager)
