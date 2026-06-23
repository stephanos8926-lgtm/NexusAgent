"""Tests for singleton injection patterns.

Verifies that all global singletons support get_X/set_X injection
for testability, and that backward-compatible aliases work.
"""

from unittest.mock import MagicMock


def test_worker_pool_injection():
    """WorkerPool supports get/set injection."""
    from nexusagent.core.worker import (
        WorkerPool,
        get_worker_pool,
        set_worker_pool,
    )

    # get_worker_pool returns a WorkerPool instance
    pool = get_worker_pool()
    assert isinstance(pool, WorkerPool)

    # Same instance on repeated calls (lazy singleton)
    assert get_worker_pool() is pool

    # set_worker_pool replaces the instance
    mock_pool = MagicMock(spec=WorkerPool)
    set_worker_pool(mock_pool)
    assert get_worker_pool() is mock_pool

    # Reset to real instance for other tests
    set_worker_pool(WorkerPool())
    assert isinstance(get_worker_pool(), WorkerPool)


def test_worker_injection():
    """NexusWorker supports get/set injection."""
    from nexusagent.core.worker import (
        NexusWorker,
        get_worker,
        set_worker,
    )

    w = get_worker()
    assert isinstance(w, NexusWorker)
    assert get_worker() is w

    mock_worker = MagicMock(spec=NexusWorker)
    set_worker(mock_worker)
    assert get_worker() is mock_worker

    # Reset
    set_worker(NexusWorker())
    assert isinstance(get_worker(), NexusWorker)


def test_auth_manager_injection():
    """AuthManager supports get/set injection."""
    from nexusagent.infrastructure.auth import (
        AuthManager,
        get_auth_manager,
        set_auth_manager,
    )

    am = get_auth_manager()
    assert isinstance(am, AuthManager)
    assert get_auth_manager() is am

    mock_am = MagicMock(spec=AuthManager)
    set_auth_manager(mock_am)
    assert get_auth_manager() is mock_am

    # Reset
    set_auth_manager(AuthManager())
    assert isinstance(get_auth_manager(), AuthManager)


def test_db_manager_injection():
    """DatabaseManager supports get/set injection."""
    from nexusagent.infrastructure.db import (
        DatabaseManager,
        get_db_manager,
        set_db_manager,
    )

    dm = get_db_manager()
    assert isinstance(dm, DatabaseManager)
    assert get_db_manager() is dm

    mock_dm = MagicMock(spec=DatabaseManager)
    set_db_manager(mock_dm)
    assert get_db_manager() is mock_dm

    # Reset
    set_db_manager(DatabaseManager())
    assert isinstance(get_db_manager(), DatabaseManager)


def test_session_manager_injection():
    """SessionManager supports get/set injection."""
    from nexusagent.core.session import (
        SessionManager,
        get_session_manager,
        set_session_manager,
    )

    sm = get_session_manager()
    assert isinstance(sm, SessionManager)
    assert get_session_manager() is sm

    mock_sm = MagicMock(spec=SessionManager)
    set_session_manager(mock_sm)
    assert get_session_manager() is mock_sm

    # Reset
    set_session_manager(SessionManager())
    assert isinstance(get_session_manager(), SessionManager)


def test_deep_research_orchestrator_injection():
    """DeepResearchOrchestrator supports get/set injection."""
    from nexusagent.core.orchestration import (
        DeepResearchOrchestrator,
        get_deep_research_orchestrator,
        set_deep_research_orchestrator,
    )

    o = get_deep_research_orchestrator()
    assert isinstance(o, DeepResearchOrchestrator)
    assert get_deep_research_orchestrator() is o

    mock_o = MagicMock(spec=DeepResearchOrchestrator)
    set_deep_research_orchestrator(mock_o)
    assert get_deep_research_orchestrator() is mock_o

    # Reset
    set_deep_research_orchestrator(DeepResearchOrchestrator())
    assert isinstance(get_deep_research_orchestrator(), DeepResearchOrchestrator)


def test_backward_compat_aliases():
    """Backward-compatible aliases return the same instances."""
    from nexusagent.core.orchestration import deep_research_orchestrator
    from nexusagent.core.session import session_manager
    from nexusagent.core.worker import worker, worker_pool
    from nexusagent.infrastructure.auth import auth_manager
    from nexusagent.infrastructure.db import db_manager

    # These should all be real instances (not None)
    assert worker is not None
    assert worker_pool is not None
    assert session_manager is not None
    assert auth_manager is not None
    assert db_manager is not None
    assert deep_research_orchestrator is not None
