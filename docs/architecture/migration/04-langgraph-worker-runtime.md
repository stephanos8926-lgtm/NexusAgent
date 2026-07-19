# Phase 4 — LangGraph Worker Runtime

## Objective

Create durable autonomous workers.

## Worker Responsibilities

Workers:

- execute assigned tasks
- update state
- emit events
- checkpoint progress

Workers do **NOT**:

- manage global policy
- approve dangerous actions
- coordinate other workers

## Architecture

```
Worker Graph
    |
    +-- Planner Node
    |       ↓
    +-- Execution Node
    |       ↓
    +-- Verification Node
```

## Implementation Steps

### Step 1 — Create worker graph abstraction

Define a LangGraph-based `WorkerGraph` that wraps the task lifecycle. Each worker is a LangGraph state machine with typed nodes and edges.

### Step 2 — Define worker nodes

Three core nodes:

| Node | Responsibility |
|------|---------------|
| **Planner Node** | Breaks the task into subtasks, generates execution plan |
| **Execution Node** | Carries out tool calls, modifies workspace, tracks progress |
| **Verification Node** | Validates results, checks acceptance criteria, reports completion |

### Step 3 — Add checkpoint persistence

Checkpoints are stored in the task's durable state. The worker serializes its current node, completed actions, and intermediate results before each tool call.

### Step 4 — Add recovery

On failure, the worker follows a priority chain:

1. **Retry** — re-execute the failing node with exponential backoff
2. **Rollback** — revert to the last checkpoint, discard partial work
3. **Escalate** — mark task as FAILED, emit `worker.failed` event for POL

## Completion Criteria

- [ ] Workers survive interruption and resume from the last checkpoint
- [ ] Worker lifecycle is observable via events
- [ ] Failure modes are handled gracefully (retry → rollback → escalate)
- [ ] Workers are isolated from each other (no shared state)