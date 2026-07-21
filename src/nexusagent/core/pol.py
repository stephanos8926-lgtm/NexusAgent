# src/nexusagent/core/pol.py
"""Phase 7: POL Control Plane for NexusAgent.

Enforces rules, manages system interventions, escalations, and overrides.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from nexusagent.tools.registry.policy import get_manifest

logger = logging.getLogger(__name__)


class PolicyEvaluator:
    """Rules-based policy evaluator to determine if actions are permitted."""

    def __init__(
        self,
        allowlisted_endpoints: list[str] | None = None,
        workspace_root: str | None = None,
    ) -> None:
        self.allowlisted_endpoints = allowlisted_endpoints or [
            "localhost",
            "127.0.0.1",
            "api.github.com",
            "api.openai.com",
            "api.anthropic.com",
        ]
        self.workspace_root = os.path.abspath(workspace_root or os.getcwd())

    def lookup_capabilities(self, role: str) -> set[str]:
        """Look up tool capabilities for a specific role."""
        return get_manifest(role)

    def evaluate_execution(self, command: str, current_dir: str | None = None) -> tuple[bool, str]:
        """Evaluate shell commands. 'No shell commands outside workspace'."""
        # Simple check for absolute paths or relative path escapes going out of workspace root
        cmd_words = command.strip().split()
        for word in cmd_words:
            # Check if any word resembles an absolute path outside workspace or contains parent directory navigation
            if ".." in word:
                target_path = os.path.abspath(
                    os.path.join(current_dir or self.workspace_root, word)
                )
                if not target_path.startswith(self.workspace_root):
                    return (
                        False,
                        f"Rule Violation: Path {word} attempts to navigate outside workspace root",
                    )
            if word.startswith("/") and not word.startswith(self.workspace_root):
                # Only check if it's a file path that exists, or is commonly restricted
                # E.g., accessing standard system paths outside workspace root is blocked
                for sensitive_prefix in ["/etc", "/var", "/bin", "/usr", "/home"]:
                    if word.startswith(sensitive_prefix):
                        return (
                            False,
                            f"Rule Violation: Attempt to access sensitive system path '{word}'",
                        )
        return True, ""

    def evaluate_network(self, url: str) -> tuple[bool, str]:
        """Evaluate network access. 'Only allowlisted endpoints'."""
        try:
            parsed = urlparse(url)
            host = parsed.netloc or parsed.path
            if ":" in host:
                host = host.split(":")[0]
            if not host:
                return False, f"Rule Violation: Invalid URL or empty host parsed from '{url}'"
            if host in self.allowlisted_endpoints:
                return True, ""
            return False, f"Rule Violation: End point '{host}' is not on the network allowlist"
        except Exception as e:
            return False, f"Rule Violation: Error parsing endpoint URL: {e}"

    def evaluate_memory(self, action: str, key: str | None = None) -> tuple[bool, str]:
        """Evaluate memory access. 'No deletion of semantic memories'."""
        if "delete" in action.lower() or "clear" in action.lower() or "remove" in action.lower():
            return False, "Rule Violation: Deletion of semantic memories is strictly prohibited"
        return True, ""

    def evaluate_tools(self, tool_name: str, trust_level: str | None = None) -> tuple[bool, str]:
        """Evaluate tools. 'MCP tools require TOOL_EXTERNAL trust level'."""
        # If tool name matches MCP external pattern or is specified as external, verify trust level
        is_mcp = tool_name.startswith("mcp_") or tool_name.startswith("external_")
        if is_mcp and trust_level != "TOOL_EXTERNAL":
            return (
                False,
                f"Rule Violation: MCP tool '{tool_name}' requires TOOL_EXTERNAL trust level",
            )
        return True, ""


class POLControlPlane:
    """Platform Orchestration Layer Control Plane daemon/service.

    Subscribes to NATS event streams, handles interventions, escalations,
    and exposes status interfaces.
    """

    def __init__(self, persistence_path: str | None = None) -> None:
        self.persistence_path = persistence_path or os.path.join(
            os.path.expanduser("~"), ".nexusagent", "pol_interventions.json"
        )
        self.evaluator = PolicyEvaluator()
        self.interventions: dict[str, dict[str, Any]] = {}
        self._websocket_subscribers: set[Callable[[dict[str, Any]], Any]] = set()
        self._load_interventions()

    def _load_interventions(self) -> None:
        """Load persistent interventions from JSON file."""
        if os.path.exists(self.persistence_path):
            try:
                with open(self.persistence_path) as f:
                    data = json.load(f)
                    self.interventions = data
                logger.info(
                    f"Loaded {len(self.interventions)} interventions from {self.persistence_path}"
                )
            except Exception as e:
                logger.warning(f"Failed to load interventions from {self.persistence_path}: {e}")

    def _save_interventions(self) -> None:
        """Save persistent interventions to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
            with open(self.persistence_path, "w") as f:
                json.dump(self.interventions, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save interventions to {self.persistence_path}: {e}")

    async def create_intervention(
        self,
        task_id: str | None,
        reason: str,
        guidance: str,
        priority: str = "high",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and store a system intervention, notifying clients."""
        import uuid

        intervention_id = f"intv-{str(uuid.uuid4())[:8]}"
        intervention = {
            "id": intervention_id,
            "task_id": task_id,
            "type": "system_intervention",
            "source": "POL",
            "priority": priority,
            "reason": reason,
            "guidance": guidance,
            "status": "pending",
            "action": None,
            "payload": payload or {},
            "created_at": datetime.now(UTC).isoformat(),
            "resolved_at": None,
        }
        self.interventions[intervention_id] = intervention
        self._save_interventions()

        # Emit system event synchronously
        try:
            from nexusagent.core.events import PolicyEvent, emit_event_sync

            emit_event_sync(
                PolicyEvent.violation(
                    source="POL",
                    action="system_intervention",
                    details=f"Intervention created: {reason}. Guidance: {guidance}",
                )
            )
        except Exception as e:
            logger.warning(f"Could not emit PolicyEvent for intervention: {e}")

        # Notify websocket clients asynchronously
        await self._broadcast_change(intervention)
        return intervention

    async def resolve_intervention(
        self,
        intervention_id: str,
        action: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve a pending intervention and apply specified corrective action."""
        intervention = self.interventions.get(intervention_id)
        if not intervention:
            return None

        intervention["status"] = "resolved"
        intervention["action"] = action
        intervention["resolved_at"] = datetime.now(UTC).isoformat()
        self._save_interventions()

        # Execute the resolved corrective action
        task_id = intervention.get("task_id")
        if task_id and action:
            if action == "cancel":
                await self.cancel_task(task_id)
            elif action == "retry":
                await self.retry_task(task_id)
            elif action == "escalate":
                await self.escalate_task(task_id, intervention["reason"])

        await self._broadcast_change(intervention)
        return intervention

    async def cancel_task(self, task_id: str) -> None:
        """Intervene and cancel a task."""
        from nexusagent.core.task.task_state import TaskState
        from nexusagent.core.task.task_store import get_task_store

        store = get_task_store()
        durable_task = await store.load_task(task_id)
        if durable_task:
            try:
                # Force state transition to FAILED or cancelled state
                durable_task.transition_to(TaskState.FAILED)
                await store.save_task(durable_task)
            except Exception:
                durable_task.state = TaskState.FAILED
                await store.save_task(durable_task)
            logger.info(f"[POL] Intervened and cancelled task '{task_id}'")

    async def retry_task(self, task_id: str) -> None:
        """Intervene and trigger a retry for a failed task."""
        from nexusagent.core.task.task_state import TaskState
        from nexusagent.core.task.task_store import get_task_store

        store = get_task_store()
        durable_task = await store.load_task(task_id)
        if durable_task:
            try:
                # Set back to EXECUTING or planning to resume
                durable_task.transition_to(TaskState.RECOVERING)
                await store.save_task(durable_task)
                durable_task.transition_to(TaskState.EXECUTING)
                await store.save_task(durable_task)
            except Exception:
                durable_task.state = TaskState.EXECUTING
                await store.save_task(durable_task)
            logger.info(f"[POL] Intervened and triggered retry for task '{task_id}'")

    async def escalate_task(self, task_id: str, reason: str) -> None:
        """Escalate failure from worker to high-level orchestrator or user."""
        logger.warning(f"[POL Escalation] Escalate task '{task_id}' due to: {reason}")
        # Mark intervention as escalated
        for intv in self.interventions.values():
            if intv.get("task_id") == task_id and intv["status"] == "pending":
                intv["status"] = "escalated"
                intv["resolved_at"] = datetime.now(UTC).isoformat()
                self._save_interventions()
                await self._broadcast_change(intv)

    def list_interventions(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        """List active and history interventions."""
        if status_filter:
            return [v for v in self.interventions.values() if v["status"] == status_filter]
        return list(self.interventions.values())

    def get_intervention(self, intervention_id: str) -> dict[str, Any] | None:
        """Get details of a specific intervention."""
        return self.interventions.get(intervention_id)

    # WebSocket connection helpers
    def register_websocket_callback(self, callback: Callable[[dict[str, Any]], Any]) -> None:
        """Register a callback for websocket broadcasting."""
        self._websocket_subscribers.add(callback)

    def unregister_websocket_callback(self, callback: Callable[[dict[str, Any]], Any]) -> None:
        """Unregister a callback."""
        self._websocket_subscribers.discard(callback)

    async def _broadcast_change(self, intervention: dict[str, Any]) -> None:
        """Broadcast intervention state change to all web socket clients."""
        for callback in list(self._websocket_subscribers):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(intervention)
                else:
                    callback(intervention)
            except Exception as e:
                logger.warning(f"Error calling websocket broadcast callback: {e}")


# Global POL control plane instance (lazy, injectable singleton)
_pol_control_plane_instance: POLControlPlane | None = None


def get_pol_control_plane() -> POLControlPlane:
    """Get the global POLControlPlane instance."""
    global _pol_control_plane_instance
    if _pol_control_plane_instance is None:
        _pol_control_plane_instance = POLControlPlane()
    return _pol_control_plane_instance


def set_pol_control_plane(instance: POLControlPlane) -> None:
    """Override the global POLControlPlane instance (for testing)."""
    global _pol_control_plane_instance
    _pol_control_plane_instance = instance
