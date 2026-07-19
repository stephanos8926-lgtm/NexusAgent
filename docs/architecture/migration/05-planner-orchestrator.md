# Phase 5 — Planner and Orchestrator

## Objective

Separate reasoning from execution.

## Components

```
Planner:      "What needs to happen?"
Orchestrator: "Who does what and when?"
Worker:       "How do I execute?"
```

## DAG Model

```
Goal
 |
Task A
 |
 +-- Task B
 +-- Task C
 |
Task D
```

Each task is a node in the DAG. Edges represent dependencies. A task can only execute when all its parent tasks are complete.

## Implementation Steps

### Step 1 — Create planning schema

Define the structured output of the planner:

```python
class Plan:
    goal: str
    tasks: list[TaskNode]
    dependencies: list[tuple[str, str]]  # (child_id, parent_id)
    global_context: dict
```

### Step 2 — Generate task graphs

The planner receives a high-level objective and produces a DAG of tasks. Each task is independently executable and has clear acceptance criteria.

### Step 3 — Validate dependencies

Before execution, the system validates:
- No circular dependencies
- All dependencies reference existing tasks
- No orphaned tasks (every task is reachable from the goal)

### Step 4 — Schedule execution

The orchestrator reads the DAG and dispatches tasks to workers:
- Tasks with no dependencies execute immediately
- Tasks with dependencies wait for their parents to complete
- Completed tasks notify the orchestrator via events

## Completion Criteria

- [ ] Complex objectives decompose automatically into task DAGs
- [ ] Dependencies are validated before execution
- [ ] The orchestrator dispatches tasks in dependency order
- [ ] Completed tasks trigger downstream task execution