# tests/test_subagent.py
"""Tests for SubAgentHandle control interface."""

from __future__ import annotations

import asyncio

import pytest

from nexusagent.llm.models import TaskContract
from nexusagent.core.subagent import SubAgentHandle, SubAgentStatus

# -- helpers ----------------------------------------------------------------


def _make_contract(**overrides: object) -> TaskContract:
    defaults = {"task_id": "t-1", "title": "test task"}
    defaults.update(overrides)
    return TaskContract(**defaults)


def _make_handle(**contract_overrides: object) -> SubAgentHandle:
    return SubAgentHandle(worker_id="w-1", contract=_make_contract(**contract_overrides))


# -- test_handle_creation ----------------------------------------------------


def test_handle_creation() -> None:
    handle = _make_handle()

    assert handle.worker_id == "w-1"
    assert handle.status == SubAgentStatus.PENDING
    assert handle.result is None
    assert handle.error is None
    assert handle.completed_at is None
    assert not handle.is_done()
    assert not handle.is_cancelled()
    assert handle.created_at is not None


# -- test_handle_status_transitions ------------------------------------------


def test_handle_status_transitions() -> None:
    handle = _make_handle()

    # PENDING → RUNNING
    handle._mark_running()
    assert handle.status == SubAgentStatus.RUNNING
    assert not handle.is_done()

    # RUNNING → COMPLETED
    handle._mark_completed(result={"files": ["a.py"]})
    assert handle.status == SubAgentStatus.COMPLETED
    assert handle.result == {"files": ["a.py"]}
    assert handle.completed_at is not None
    assert handle.is_done()

    # Verify _mark_running rejects invalid transition
    handle2 = _make_handle()
    handle2._mark_running()
    with pytest.raises(RuntimeError, match="Cannot mark RUNNING"):
        handle2._mark_running()


# -- test_handle_is_done -----------------------------------------------------


def test_handle_is_done() -> None:
    handle = _make_handle()

    # Non-terminal states
    handle._status = SubAgentStatus.PENDING
    assert not handle.is_done()
    handle._status = SubAgentStatus.RUNNING
    assert not handle.is_done()

    # Terminal states
    handle._status = SubAgentStatus.COMPLETED
    assert handle.is_done()
    handle._status = SubAgentStatus.FAILED
    assert handle.is_done()
    handle._status = SubAgentStatus.CANCELLED
    assert handle.is_done()


# -- test_cancel -------------------------------------------------------------


def test_cancel() -> None:
    handle = _make_handle()

    assert handle.cancel() is True
    assert handle.status == SubAgentStatus.CANCELLED
    assert handle.is_cancelled()
    assert handle.is_done()
    assert handle.completed_at is not None

    # Second cancel should return False (already terminal)
    assert handle.cancel() is False


# -- test_wait_success -------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_success() -> None:
    handle = _make_handle()
    handle._mark_running()
    handle._mark_completed(result="done!")

    result = await handle.wait()
    assert result == "done!"


# -- test_wait_failure -------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_failure() -> None:
    handle = _make_handle()
    handle._mark_running()
    handle._mark_failed(error="boom")

    with pytest.raises(RuntimeError, match="boom"):
        await handle.wait()


# -- test_wait_cancelled -----------------------------------------------------


@pytest.mark.asyncio
async def test_wait_cancelled() -> None:
    handle = _make_handle()
    handle.cancel()

    with pytest.raises(asyncio.CancelledError):
        await handle.wait()


# -- test_wait_timeout -------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_timeout() -> None:
    handle = _make_handle()

    with pytest.raises(asyncio.TimeoutError):
        await handle.wait(timeout=0.05)


# -- test_mark_failed --------------------------------------------------------


def test_mark_failed() -> None:
    handle = _make_handle()
    handle._mark_running()
    handle._mark_failed(error="segfault")

    assert handle.status == SubAgentStatus.FAILED
    assert handle.error == "segfault"
    assert handle.completed_at is not None
    assert handle.is_done()
