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
    # Singleton getters/setters
    "get_db_manager",
    "set_db_manager",
    "get_task_repo",
    "set_task_repo",
    "get_session_repo",
    "set_session_repo",
    # Backward-compat lazy accessors (via __getattr__)
    "db_manager",
    "task_repo",
    "session_repo",
]

# Singleton instances — lazy init via get/set functions
_db_manager: DatabaseManager | None = None
_task_repo: TaskRepository | None = None
_session_repo: SessionRepository | None = None


def get_db_manager() -> DatabaseManager:
    """Return the global DatabaseManager singleton, creating it if needed.

    Returns:
        The shared DatabaseManager instance.
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def set_db_manager(instance: DatabaseManager) -> None:
    """Set the global DatabaseManager singleton (for testing/overrides).

    Args:
        instance: The DatabaseManager instance to use globally.
    """
    global _db_manager
    _db_manager = instance


def get_task_repo() -> TaskRepository:
    """Return the global TaskRepository singleton, creating it if needed.

    Returns:
        The shared TaskRepository instance.
    """
    global _task_repo
    if _task_repo is None:
        _task_repo = TaskRepository(get_db_manager())
    return _task_repo


def set_task_repo(instance: TaskRepository) -> None:
    """Set the global TaskRepository singleton (for testing/overrides).

    Args:
        instance: The TaskRepository instance to use globally.
    """
    global _task_repo
    _task_repo = instance


def get_session_repo() -> SessionRepository:
    """Return the global SessionRepository singleton, creating it if needed.

    Returns:
        The shared SessionRepository instance.
    """
    global _session_repo
    if _session_repo is None:
        _session_repo = SessionRepository(get_db_manager())
    return _session_repo


def set_session_repo(instance: SessionRepository) -> None:
    """Set the global SessionRepository singleton (for testing/overrides).

    Args:
        instance: The SessionRepository instance to use globally.
    """
    global _session_repo
    _session_repo = instance


def __getattr__(name: str):
    """Lazy module-level access to singletons for backward compatibility."""
    if name == "db_manager":
        return get_db_manager()
    if name == "task_repo":
        return get_task_repo()
    if name == "session_repo":
        return get_session_repo()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
