"""Pytest fixtures for WorkerGraph tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_task_store():
    """Create a mock TaskStore for testing WorkerGraph."""
    store = MagicMock()
    store.save_task = AsyncMock()
    store.save_checkpoint = AsyncMock()
    store.load_latest_checkpoint = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_event_emitter():
    """Create a mock event emitter for testing WorkerGraph."""
    emitter = MagicMock()
    emitter.emit_sync = MagicMock()
    return emitter


@pytest.fixture
def sample_worker_state():
    """Create a sample WorkerState dict for testing."""
    return {
        "task_id": "test-task-001",
        "objective": "Write a test function",
        "plan": None,
        "steps_completed": [],
        "step_results": [],
        "errors": [],
        "checkpoints": [],
        "metadata": {"turns": 0},
        "is_complete": False,
    }


@pytest.fixture
def sample_completed_state(sample_worker_state):
    """Create a completed WorkerState for testing."""
    state = dict(sample_worker_state)
    state["plan"] = ["Research API", "Implement function", "Write tests"]
    state["steps_completed"] = ["Research API", "Implement function", "Write tests"]
    state["step_results"] = ["Docs found", "Function written", "Tests passing"]
    state["is_complete"] = True
    state["metadata"]["turns"] = 3
    return state
