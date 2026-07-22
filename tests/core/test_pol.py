# tests/core/test_pol.py
"""Unit tests for the Platform Orchestration Layer (POL) control plane and PolicyEvaluator."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from nexusagent.core.pol import PolicyEvaluator, POLControlPlane, get_pol_control_plane
from nexusagent.core.task.task_state import Task, TaskState
from nexusagent.core.task.task_store import TaskStore, set_task_store


def test_policy_evaluator_execution():
    """Test PolicyEvaluator execution rules."""
    evaluator = PolicyEvaluator(workspace_root="/app/workspace")

    # Inside workspace is allowed
    allowed, msg = evaluator.evaluate_execution("ls -la", current_dir="/app/workspace")
    assert allowed

    # Path escape attempts are blocked
    allowed, msg = evaluator.evaluate_execution("cat ../../etc/passwd", current_dir="/app/workspace")
    assert not allowed
    assert "navigate outside workspace root" in msg

    # Sensitive paths are blocked
    allowed, msg = evaluator.evaluate_execution("cat /etc/passwd", current_dir="/app/workspace")
    assert not allowed
    assert "Attempt to access sensitive system path" in msg


def test_policy_evaluator_network():
    """Test PolicyEvaluator network rules."""
    evaluator = PolicyEvaluator(allowlisted_endpoints=["localhost", "api.github.com"])

    # Allowlisted endpoints are allowed
    allowed, msg = evaluator.evaluate_network("https://api.github.com/repos")
    assert allowed

    # Non-allowlisted endpoints are blocked
    allowed, msg = evaluator.evaluate_network("https://malicious-site.com")
    assert not allowed
    assert "not on the network allowlist" in msg


def test_policy_evaluator_memory():
    """Test PolicyEvaluator memory rules."""
    evaluator = PolicyEvaluator()

    # Read/write is allowed
    allowed, msg = evaluator.evaluate_memory("read", "some_key")
    assert allowed

    # Deletions are blocked
    allowed, msg = evaluator.evaluate_memory("delete", "some_key")
    assert not allowed
    assert "Deletion of semantic memories is strictly prohibited" in msg


def test_policy_evaluator_tools():
    """Test PolicyEvaluator tools rules."""
    evaluator = PolicyEvaluator()

    # Standard tools are allowed
    allowed, msg = evaluator.evaluate_tools("read_file")
    assert allowed

    # MCP tools without TOOL_EXTERNAL trust are blocked
    allowed, msg = evaluator.evaluate_tools("mcp_custom_tool", trust_level="NONE")
    assert not allowed
    assert "requires TOOL_EXTERNAL trust level" in msg

    # MCP tools with TOOL_EXTERNAL trust are allowed
    allowed, msg = evaluator.evaluate_tools("mcp_custom_tool", trust_level="TOOL_EXTERNAL")
    assert allowed


@pytest.mark.asyncio
async def test_pol_control_plane_interventions(tmp_path):
    """Test creating, listing, and resolving interventions in POLControlPlane."""
    persistence_file = str(tmp_path / "pol_interventions.json")
    pol = POLControlPlane(persistence_path=persistence_file)

    # Initially empty
    assert len(pol.list_interventions()) == 0

    # Create an intervention
    intv = await pol.create_intervention(
        task_id="task-123",
        reason="unauthorized_file_access",
        guidance="Request admin approval",
        priority="high"
    )
    assert intv["task_id"] == "task-123"
    assert intv["status"] == "pending"

    # List interventions
    all_intvs = pol.list_interventions()
    assert len(all_intvs) == 1
    assert pol.get_intervention(intv["id"]) == intv

    # Resolve intervention
    resolved = await pol.resolve_intervention(intv["id"], action="override")
    assert resolved["status"] == "resolved"
    assert resolved["action"] == "override"


@pytest.mark.asyncio
async def test_pol_control_plane_actions(tmp_path):
    """Test POL Control Plane execution of cancel and retry actions on TaskStore."""
    persistence_file = str(tmp_path / "pol_interventions.json")
    pol = POLControlPlane(persistence_path=persistence_file)

    # Create a mock TaskStore and register a task
    mock_store = TaskStore()
    set_task_store(mock_store)

    task = Task(id="task-abc", objective="test task", state=TaskState.EXECUTING)
    await mock_store.save_task(task)

    # Intervene and cancel
    await pol.cancel_task("task-abc")
    updated_task = await mock_store.load_task("task-abc")
    assert updated_task.state == TaskState.FAILED

    # Intervene and retry
    await pol.retry_task("task-abc")
    updated_task = await mock_store.load_task("task-abc")
    assert updated_task.state == TaskState.EXECUTING
