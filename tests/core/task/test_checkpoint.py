"""Tests for checkpoint dataclass serialization and deserialization."""

from nexusagent.core.task.checkpoint import Checkpoint


def test_checkpoint_initialization():
    """Verify Checkpoint attributes initialization."""
    cp = Checkpoint(
        current_node="node-1",
        completed_actions=["action-1", "action-2"],
        files_changed=["file1.txt"],
        tool_results=[{"tool": "read_file", "output": "content"}],
        next_action="action-3",
    )
    assert cp.current_node == "node-1"
    assert cp.completed_actions == ["action-1", "action-2"]
    assert cp.files_changed == ["file1.txt"]
    assert cp.tool_results == [{"tool": "read_file", "output": "content"}]
    assert cp.next_action == "action-3"


def test_checkpoint_dict_roundtrip():
    """Verify dictionary conversion roundtrip of Checkpoint."""
    cp1 = Checkpoint(
        current_node="node-2",
        completed_actions=["action-a"],
        files_changed=["f1.py"],
        tool_results=[{"foo": "bar"}],
        next_action="action-b",
    )
    data = cp1.to_dict()
    cp2 = Checkpoint.from_dict(data)
    assert cp1 == cp2


def test_checkpoint_json_serialization_roundtrip():
    """Verify JSON string serialization/deserialization roundtrip."""
    cp1 = Checkpoint(
        current_node="node-3",
        completed_actions=["action-x"],
        files_changed=["f2.py", "f3.py"],
        tool_results=[{"abc": 123}],
        next_action="action-y",
    )
    json_str = cp1.serialize()
    cp2 = Checkpoint.deserialize(json_str)
    assert cp1 == cp2
