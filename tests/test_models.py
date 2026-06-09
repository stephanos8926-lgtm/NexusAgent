"""Tests for TaskContract and MemoryScope models."""

from nexusagent.models import MemoryScope, TaskContract


class TestTaskContractDefaults:
    """Verify default field values."""

    def test_task_contract_defaults(self):
        tc = TaskContract(task_id="t1", title="Test task")
        assert tc.task_id == "t1"
        assert tc.title == "Test task"
        assert tc.working_dir == "."
        assert tc.allowed_tools is None
        assert tc.denied_tools == []
        assert tc.max_turns == 20
        assert tc.max_wall_time == 1800.0
        assert tc.max_tokens is None
        assert tc.acceptance_criteria == []
        assert tc.memory_scope == MemoryScope.ISOLATED
        assert tc.parent_memory_id is None
        assert tc.human_in_the_loop is False
        assert tc.on_failure == "escalate"
        assert tc.expected_outputs == []
        assert tc.description == ""
        assert tc.priority == 1
        assert tc.metadata == {}


class TestTaskContractCustomBounds:
    """Verify custom values, including boundary constraints."""

    def test_task_contract_custom_bounds(self):
        tc = TaskContract(
            task_id="t2",
            title="Custom",
            working_dir="/tmp/work",
            allowed_tools=["bash", "editor"],
            denied_tools=["dangerous"],
            max_turns=50,
            max_wall_time=3600.0,
            max_tokens=4096,
            acceptance_criteria=["output matches spec"],
            memory_scope=MemoryScope.SHARED,
            parent_memory_id="mem-123",
            human_in_the_loop=True,
            on_failure="retry",
            expected_outputs=["result.json"],
            description="A detailed task",
            priority=5,
            metadata={"team": "alpha"},
        )
        assert tc.max_turns == 50
        assert tc.max_wall_time == 3600.0
        assert tc.max_tokens == 4096
        assert tc.allowed_tools == ["bash", "editor"]
        assert tc.denied_tools == ["dangerous"]
        assert tc.memory_scope == MemoryScope.SHARED
        assert tc.parent_memory_id == "mem-123"
        assert tc.human_in_the_loop is True
        assert tc.on_failure == "retry"
        assert tc.expected_outputs == ["result.json"]
        assert tc.description == "A detailed task"
        assert tc.priority == 5
        assert tc.metadata == {"team": "alpha"}

    def test_priority_lower_bound(self):
        from pydantic import ValidationError

        try:
            TaskContract(task_id="t", title="x", priority=0)
            raise AssertionError("Should have raised ValidationError")
        except ValidationError:
            pass

    def test_priority_upper_bound(self):
        from pydantic import ValidationError

        try:
            TaskContract(task_id="t", title="x", priority=6)
            raise AssertionError("Should have raised ValidationError")
        except ValidationError:
            pass

    def test_max_turns_lower_bound(self):
        from pydantic import ValidationError

        try:
            TaskContract(task_id="t", title="x", max_turns=0)
            raise AssertionError("Should have raised ValidationError")
        except ValidationError:
            pass

    def test_max_turns_upper_bound(self):
        from pydantic import ValidationError

        try:
            TaskContract(task_id="t", title="x", max_turns=101)
            raise AssertionError("Should have raised ValidationError")
        except ValidationError:
            pass

    def test_max_wall_time_lower_bound(self):
        from pydantic import ValidationError

        try:
            TaskContract(task_id="t", title="x", max_wall_time=9.0)
            raise AssertionError("Should have raised ValidationError")
        except ValidationError:
            pass


class TestMemoryScopeValues:
    """Verify all three enum values."""

    def test_memory_scope_values(self):
        assert MemoryScope.SHARED == "shared"
        assert MemoryScope.ISOLATED == "isolated"
        assert MemoryScope.SCOPED == "scoped"
