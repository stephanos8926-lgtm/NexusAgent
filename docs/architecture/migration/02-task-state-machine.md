# Phase 2 — Task State Machine

## Objective

Make tasks durable and recoverable.

## Task Model

```python
Task:
    - id: str
    - objective: str
    - owner: str
    - state: TaskState
    - parent_task: str | None
    - child_tasks: list[str]
    - checkpoints: list[Checkpoint]
    - artifacts: dict[str, Any]
```

## States

```
CREATED
    ↓
PLANNING
    ↓
EXECUTING
    ↓
VERIFYING
    ↓
COMPLETED
```

### Failure Path

```
EXECUTING
    ↓
FAILED
    ↓
RECOVERING
```

## Implementation Steps

### Step 1 — Create Task entity

Define the `Task` dataclass with all required fields. The task is the fundamental unit of work — everything in the system operates on tasks.

### Step 2 — Create state transition validator

Enforce legal transitions. Invalid transitions are rejected:

| From | To | Valid? |
|------|----|--------|
| `EXECUTING` | `CREATED` | ❌ No |
| `FAILED` | `RECOVERING` | ✅ Yes |
| `COMPLETED` | `EXECUTING` | ❌ No |
| `CREATED` | `PLANNING` | ✅ Yes |

### Step 3 — Persist task state

Tasks are stored in a durable SQLite database. State changes are atomic — the task is either in one state or another, never partially transitioned.

### Step 4 — Add checkpoint mechanism

A checkpoint captures the full execution state at a point in time:

```python
Checkpoint:
    - current_node: str
    - completed_actions: list[str]
    - files_changed: list[str]
    - tool_results: list[dict]
    - next_action: str
```

## Completion Criteria

- [ ] A worker can be interrupted and restarted from its last checkpoint
- [ ] Task state transitions are validated and enforced
- [ ] Checkpoints are persisted durably
- [ ] Recovery path (FAILED → RECOVERING) is supported