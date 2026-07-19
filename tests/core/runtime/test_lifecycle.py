"""Tests for the lifecycle state machine."""

from __future__ import annotations

import pytest

from nexusagent.runtime.lifecycle import (
    HealthStatus,
    LifecycleMixin,
    LifecycleState,
)


class TestLifecycleState:
    """LifecycleState enum validity."""

    def test_all_states_defined(self):
        """All 7 states must exist."""
        assert len(LifecycleState) == 7
        assert LifecycleState.CREATED.value == "created"
        assert LifecycleState.INITIALIZING.value == "initializing"
        assert LifecycleState.RUNNING.value == "running"
        assert LifecycleState.PAUSED.value == "paused"
        assert LifecycleState.FAILED.value == "failed"
        assert LifecycleState.COMPLETED.value == "completed"
        assert LifecycleState.TERMINATED.value == "terminated"

    def test_valid_transitions(self):
        """Valid transitions should pass."""
        # CREATED → INITIALIZING
        LifecycleState.CREATED.transition_to(LifecycleState.INITIALIZING)

        # INITIALIZING → RUNNING
        LifecycleState.INITIALIZING.transition_to(LifecycleState.RUNNING)

        # INITIALIZING → FAILED
        # Reset: re-create the check from CREATED
        LifecycleState.INITIALIZING.transition_to(LifecycleState.FAILED)

    def test_invalid_transitions_raise(self):
        """Invalid transitions should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            LifecycleState.CREATED.transition_to(LifecycleState.TERMINATED)

        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            LifecycleState.RUNNING.transition_to(LifecycleState.CREATED)

        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            LifecycleState.TERMINATED.transition_to(LifecycleState.RUNNING)

        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            LifecycleState.CREATED.transition_to(LifecycleState.COMPLETED)

    def test_running_pause_resume(self):
        """RUNNING → PAUSED → RUNNING should work."""
        LifecycleState.RUNNING.transition_to(LifecycleState.PAUSED)
        LifecycleState.PAUSED.transition_to(LifecycleState.RUNNING)

    def test_running_terminated(self):
        """RUNNING → TERMINATED direct shutdown should work."""
        LifecycleState.RUNNING.transition_to(LifecycleState.TERMINATED)

    def test_running_failed_terminated(self):
        """RUNNING → FAILED → TERMINATED should work."""
        LifecycleState.RUNNING.transition_to(LifecycleState.FAILED)
        LifecycleState.FAILED.transition_to(LifecycleState.TERMINATED)

    def test_can_transition_to(self):
        """can_transition_to returns correct booleans."""
        assert LifecycleState.RUNNING.can_transition_to(LifecycleState.PAUSED)
        assert LifecycleState.RUNNING.can_transition_to(LifecycleState.FAILED)
        assert not LifecycleState.RUNNING.can_transition_to(LifecycleState.CREATED)
        assert not LifecycleState.TERMINATED.can_transition_to(LifecycleState.RUNNING)

    def test_terminal_state(self):
        """TERMINATED has no valid transitions."""
        assert not LifecycleState.TERMINATED.can_transition_to(LifecycleState.CREATED)
        assert not LifecycleState.TERMINATED.can_transition_to(LifecycleState.RUNNING)
        assert not LifecycleState.TERMINATED.can_transition_to(LifecycleState.INITIALIZING)


class TestHealthStatus:
    """HealthStatus dataclass."""

    def test_default_healthy(self):
        h = HealthStatus()
        assert h.healthy is True
        assert h.degraded is False
        assert h.failed is False
        assert h.status == "healthy"

    def test_degraded_status(self):
        h = HealthStatus(healthy=False, degraded=True)
        assert h.status == "degraded"

    def test_failed_status(self):
        h = HealthStatus(healthy=False, failed=True)
        assert h.status == "failed"

    def test_unknown_when_none(self):
        h = HealthStatus(healthy=False)
        assert h.status == "unknown"


class TestLifecycleMixin:
    """LifecycleMixin ABC enforcement."""

    def test_cannot_instantiate_abc(self):
        """Abstract class cannot be instantiated."""
        with pytest.raises(TypeError):
            LifecycleMixin()  # type: ignore

    def test_minimal_implementation(self):
        """A class implementing all abstract members can be instantiated."""

        class MinimalComponent(LifecycleMixin):
            def __init__(self):
                self._state = LifecycleState.CREATED

            @property
            def state(self) -> LifecycleState:
                return self._state

            async def initialize(self):
                self._state = LifecycleState.RUNNING

            async def shutdown(self):
                self._state = LifecycleState.TERMINATED

            def health(self) -> HealthStatus:
                return HealthStatus(
                    healthy=self._state == LifecycleState.RUNNING,
                    details={"state": self._state.value},
                )

        comp = MinimalComponent()
        assert comp.state == LifecycleState.CREATED
        assert comp.health().healthy is False
