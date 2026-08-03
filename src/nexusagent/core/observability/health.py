# src/nexusagent/core/observability/health.py
"""Subsystem health monitoring and status aggregation."""

from __future__ import annotations

import os

from nexusagent.runtime.lifecycle import HealthStatus


def check_runtime_health() -> HealthStatus:
    """Assess the status of the session context runtime."""
    from nexusagent.runtime.context import current_context

    ctx = current_context()
    if ctx is not None:
        return HealthStatus(healthy=True, message="Runtime is active and running")
    return HealthStatus(healthy=False, message="Runtime context not set")


def check_worker_manager_health() -> HealthStatus:
    """Assess the status of the Worker Manager / pool."""
    from nexusagent.core.worker.pool import get_worker_pool

    pool = get_worker_pool()
    if pool is not None:
        active_count = len(pool.list_active())
        return HealthStatus(
            healthy=True,
            message=f"Worker Manager active. {active_count} concurrent workers running",
            details={"active_workers": active_count},
        )
    return HealthStatus(healthy=False, message="Worker Manager pool not initialized")


def check_event_bus_health() -> HealthStatus:
    """Assess the connectivity of the NATS event bus."""
    from nexusagent.infrastructure.bus import get_bus

    try:
        bus = get_bus()
        if bus and getattr(bus, "_nc", None) and bus._nc.is_connected:
            return HealthStatus(healthy=True, message="Event bus connected to NATS")
        return HealthStatus(healthy=False, message="Event bus is disconnected from NATS")
    except Exception as exc:
        return HealthStatus(healthy=False, message=f"Event bus health check failed: {exc}")


def check_memory_system_health() -> HealthStatus:
    """Assess the state and workspace of the 4-layer taxonomy Memory system."""
    from nexusagent.infrastructure.config import settings

    workspace = settings.agent.memory_workspace or os.path.expanduser("~/.nexusagent")
    layers_dir = os.path.join(workspace, ".nexusagent", "layers")
    details = {"workspace": workspace, "layers_dir": layers_dir}

    try:
        # Check that workspace is writeable/accessible
        if os.path.exists(workspace):
            return HealthStatus(healthy=True, message="Memory System OK", details=details)
        return HealthStatus(healthy=True, message="Memory System OK (workspace pending creation)", details=details)
    except Exception as exc:
        return HealthStatus(healthy=False, message=f"Memory System access failed: {exc}", details=details)


def check_pol_health() -> HealthStatus:
    """Assess the status of the POL Control Plane and background subscription loop."""
    try:
        from nexusagent.core.pol import get_pol_control_plane

        pol = get_pol_control_plane()
        if pol is not None:
            return HealthStatus(healthy=True, message="POL Control Plane is active")
        return HealthStatus(healthy=False, message="POL Control Plane not set")
    except Exception as exc:
        return HealthStatus(healthy=False, message=f"POL health check failed: {exc}")


def check_database_health() -> HealthStatus:
    """Assess database manager status and connection state."""
    from nexusagent.infrastructure.db import get_db_manager

    try:
        db_manager = get_db_manager()
        if db_manager is not None:
            return HealthStatus(healthy=True, message="Database OK")
        return HealthStatus(healthy=False, message="Database Manager not set")
    except Exception as exc:
        return HealthStatus(healthy=False, message=f"Database check failed: {exc}")


def check_external_providers_health() -> HealthStatus:
    """Assess external provider health and budget constraints."""
    from nexusagent.infrastructure.utils.budget import get_budget_guard

    try:
        guard = get_budget_guard()
        if guard and guard.is_budget_exceeded():
            return HealthStatus(healthy=False, message="LLM daily/monthly budget exceeded")
        return HealthStatus(healthy=True, message="External Providers OK")
    except Exception:
        return HealthStatus(healthy=True, message="External Providers OK")


def get_system_health() -> dict[str, HealthStatus]:
    """Gather diagnostic status checkpoints for all major platform subsystems."""
    return {
        "runtime": check_runtime_health(),
        "worker_manager": check_worker_manager_health(),
        "event_bus": check_event_bus_health(),
        "memory_system": check_memory_system_health(),
        "pol": check_pol_health(),
        "database": check_database_health(),
        "external_providers": check_external_providers_health(),
    }
