"""Event-driven core for NexusAgent.

Provides SystemEvent base class and typed subclasses for each event category:
- TaskEvent: task.created, task.started, task.completed, task.failed
- WorkerEvent: worker.started, worker.failed, worker.recovered
- ToolEvent: tool.requested, tool.completed, tool.denied
- PolicyEvent: policy events for access control

Events are published to NATS subjects following the pattern:
- nexus.task.* - Task lifecycle events
- nexus.worker.* - Worker lifecycle events
- nexus.tool.* - Tool execution events
- nexus.policy.* - Policy enforcement events
"""

from nexusagent.core.events.base import SystemEvent, EventType
from nexusagent.core.events.task_events import TaskEvent, TaskEventType
from nexusagent.core.events.worker_events import WorkerEvent, WorkerEventType
from nexusagent.core.events.tool_events import ToolEvent, ToolEventType
from nexusagent.core.events.policy_events import PolicyEvent, PolicyEventType
from nexusagent.core.events.emitter import EventEmitter, get_emitter, set_emitter, emit_event, emit_event_sync

__all__ = [
    "SystemEvent",
    "EventType",
    "TaskEvent",
    "TaskEventType",
    "WorkerEvent",
    "WorkerEventType",
    "ToolEvent",
    "ToolEventType",
    "PolicyEvent",
    "PolicyEventType",
    "EventEmitter",
    "get_emitter",
    "set_emitter",
    "emit_event",
    "emit_event_sync",
]
