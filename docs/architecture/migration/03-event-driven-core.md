# Phase 3 — Event-Driven Core

## Objective

Make events the source of truth for all system behavior.

## Event Categories

### Task Events

| Event | When |
|-------|------|
| `task.created` | A new task is submitted |
| `task.started` | A worker begins executing |
| `task.completed` | Execution finishes successfully |
| `task.failed` | Execution terminates with error |

### Worker Events

| Event | When |
|-------|------|
| `worker.started` | Worker process begins |
| `worker.failed` | Worker encounters unrecoverable error |
| `worker.recovered` | Worker resumes from checkpoint |

### Tool Events

| Event | When |
|-------|------|
| `tool.requested` | Agent requests tool execution |
| `tool.completed` | Tool returns result |
| `tool.denied` | Policy rejects tool execution |

## Event Schema

Every event requires:

```json
{
    "id": "uuid",
    "timestamp": "ISO-8601",
    "source": "string — component identity",
    "type": "string — event.category",
    "payload": "object — type-specific data"
}
```

## Implementation Steps

### Step 1 — Create event schema

Define a `SystemEvent` base type with the required fields, plus typed subclasses for each event category.

### Step 2 — Integrate message bus

Wire the existing NATS JetStream infrastructure as the event backbone. Events are published to NATS subjects; subscribers filter by subject pattern.

### Step 3 — Persist event history

Store all events in an append-only event log (SQLite or NATS KV). The event log becomes the source of truth for system state reconstruction.

### Step 4 — Create event subscribers

| Subscriber | Listens For | Reacts With |
|------------|-------------|-------------|
| POL | `worker.failed`, `tool.denied`, `task.failed` | Intervention, policy updates |
| Memory | `task.completed`, `tool.completed` | Memory extraction, consolidation |
| Dashboard | All events | Real-time system visualization |

## Completion Criteria

- [ ] System behavior can be fully reconstructed from the event log
- [ ] All state transitions produce observable events
- [ ] Subscribers react to relevant events without polling
- [ ] Event history is queryable by time range, source, and type