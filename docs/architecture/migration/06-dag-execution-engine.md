# Phase 6 — DAG Execution Engine

## Objective

Create a dedicated execution graph subsystem responsible for transforming validated task plans into executable dependency graphs.

The DAG Execution Engine is responsible for **execution coordination**.

It is **not** responsible for:

- deciding the overall objective
- generating high-level plans
- implementing worker logic
- enforcing global security policy

Those responsibilities belong to other subsystems.

The architecture separation is:

| Component | Question |
|-----------|----------|
| **Planner** | What needs to happen? |
| **DAG Engine** | In what order can these things happen and how should they execute? |
| **Orchestrator** | Which workers execute each graph node? |
| **Workers** | How do I complete my assigned operation? |

---

## Architectural Position

The DAG Execution Engine exists between planning and execution.

```
Objective
    ↓
Planner
    ↓
Task Plan
    ↓
DAG Generator
    ↓
DAG Validation
    ↓
DAG Scheduler
    ↓
Worker Assignment
    ↓
Worker Execution
    ↓
Verification
    ↓
Completion / Recovery
```

---

## Design Goals

The DAG Execution Engine must provide:

- dependency-aware execution
- parallel execution where possible
- deterministic task ordering
- execution visibility
- failure propagation
- checkpoint compatibility
- resumability
- resource awareness

---

## Core Concepts

### Graph

A graph represents the complete execution plan.

A graph contains:

- nodes
- edges
- dependencies
- metadata
- execution state

**Example — Authentication Feature:**

```
Node A: Analyze existing authentication system
Node B: Design authentication model
Node C: Implement backend changes
Node D: Create tests
Node E: Update documentation
```

Execution dependency: `A → B → C → D` and `A → E`

The graph determines:

- what can execute
- what must wait
- what can run concurrently

---

## DAG Definition

DAG means: **Directed Acyclic Graph.**

| Property | Meaning | Invalid |
|----------|---------|---------|
| **Directed** | Dependencies have a direction | "Database migration must happen before deployment" is valid |
| **Acyclic** | The graph cannot contain loops | Task A depends on B, and B depends on A — **invalid** |

The DAG validator **must** reject cycles.

---

## Responsibilities

### DAG Generator

**Input:** Validated planner output.
**Output:** Executable graph.

Responsibilities:

- create nodes
- create dependencies
- define execution requirements
- assign metadata

The DAG Generator does **not** execute tasks.

---

### DAG Validator

Responsibilities: Validate graph correctness.

Checks:

- no cycles
- all dependencies exist
- no orphan nodes
- valid worker requirements
- valid capabilities

A graph must pass validation before execution.

---

### DAG Scheduler

Responsibilities: Determine execution order.

The scheduler manages:

| Queue | Description |
|-------|-------------|
| **Ready** | Nodes with all dependencies satisfied |
| **Blocked** | Nodes waiting on dependencies |
| **Running** | Nodes currently assigned to workers |
| **Completed** | Nodes finished successfully |
| **Failed** | Nodes terminated with error |

**Example:**

- Ready: Task A, Task B
- Blocked: Task C (requires A and B)
- After A completes: Task C remains blocked until B completes.

---

## DAG Node Model

Each node represents a unit of execution.

| Property | Description |
|----------|-------------|
| `node_id` | Unique identifier |
| `task_id` | Parent task reference |
| `objective` | Description of required work |
| `dependencies` | Required previous nodes |
| `worker_type` | Required worker capability |
| `capabilities_required` | Permissions needed |
| `priority` | Execution importance |
| `timeout` | Maximum execution duration |
| `retry_policy` | Failure handling strategy |
| `verification_requirements` | How success is measured |

---

## DAG Node Lifecycle

```
PENDING
    ↓
 READY
    ↓
 RUNNING
    ↓
 VERIFYING
    ↓
 COMPLETED
```

### Failure Path

```
 RUNNING
    ↓
 FAILED
    ↓
 RECOVERING
    ↓
 RETRYING
```

### Permanent Failure

```
 FAILED
    ↓
 ESCALATED
```

---

## Execution Model

The DAG engine operates as a scheduler. It does **not** directly perform work.

Execution flow:

1. Identify nodes with satisfied dependencies
2. Mark nodes **READY**
3. Request appropriate workers
4. Assign execution
5. Monitor worker events
6. Update graph state
7. Unlock dependent nodes
8. Continue until completion

---

## Event Integration

The DAG Engine communicates through events.

### Graph Events

| Event | When |
|-------|------|
| `graph.created` | A new graph is created from a plan |
| `graph.validated` | Graph passes validation |
| `graph.started` | Execution begins |
| `graph.completed` | All nodes complete |
| `graph.failed` | Unrecoverable graph failure |

### Node Events

| Event | When |
|-------|------|
| `node.ready` | Dependencies satisfied, awaiting worker |
| `node.started` | Worker begins execution |
| `node.completed` | Worker finishes successfully |
| `node.failed` | Worker terminates with error |
| `node.recovered` | Node resumes from checkpoint |

### Scheduling Events

| Event | When |
|-------|------|
| `worker.assignment.requested` | Worker is requested for a node |
| `worker.assignment.completed` | Worker assigned to node |
| `execution.blocked` | Node blocked by dependency |

---

## Checkpoint Integration

The DAG Engine must support recovery.

### Checkpoint State

| Domain | Contains |
|--------|----------|
| **Graph** | graph_id, graph version, graph state |
| **Nodes** | completed, active, failed, pending nodes |
| **Execution** | worker assignments, tool results, verification results |

### Recovery Process

```
Load checkpoint
    ↓
Restore graph state
    ↓
Identify incomplete nodes
    ↓
Validate dependencies
    ↓
Resume execution
```

---

## Parallel Execution

The DAG Engine should maximize safe parallelism.

| Scenario | Behavior |
|----------|----------|
| **Independent tasks** | Execute simultaneously (Research API + Analyze Database) |
| **Dependent tasks** | Execute sequentially (Modify Backend → Run Tests) |

The scheduler should optimize:

- execution speed
- resource usage
- worker availability

---

## Resource Management

Each node should define resource requirements:

- token budget
- runtime estimate
- worker class
- memory requirements
- tool requirements

The scheduler should consider:

- worker availability
- system load
- priority
- cost limits

---

## Failure Handling

Failures must be classified:

| Type | Examples | Action |
|------|----------|--------|
| **Recoverable** | Network timeout, temporary API failure, dependency download failure | Retry |
| **Logical** | Incorrect implementation, failed tests, invalid output | Return to planner or request remediation |
| **Policy** | Unauthorized capability, security violation | Escalate to POL |

---

## Integration With POL

POL observes DAG execution. POL does **not** directly manage normal scheduling.

| Scenario | POL Role |
|----------|----------|
| Stalled graphs | Intervene |
| Dangerous nodes | Require approval |
| Unsafe execution | Override |
| Persistent failures | Request remediation |

**Example:** DAG Node "Deploy production" → POL requires approval → Execution pauses → POL resolves policy decision → Execution resumes or terminates.

---

## Integration With Memory

The DAG Engine should emit execution history. Memory systems may consume:

| Data | Use |
|------|-----|
| Successful workflows | Reusable patterns |
| Failures | Known failure modes |
| Decisions | Architectural choices |

The DAG Engine should **not** directly write semantic memory. It should emit events.

---

## Implementation Roadmap

### Step 1 — Define Graph Schema

- graph model
- node model
- dependency model
- execution state model

**Completion:** Graphs can be represented and serialized.

### Step 2 — Build DAG Validator

- cycle detection
- dependency validation
- schema validation

**Completion:** Invalid graphs are rejected.

### Step 3 — Create Scheduler

- ready queue
- dependency tracking
- node transitions

**Completion:** Simple graphs execute correctly.

### Step 4 — Integrate Worker Runtime

Connect DAG nodes to Worker assignments.

**Completion:** Workers can execute graph nodes.

### Step 5 — Add Persistence

- graph state
- node state
- execution history

**Completion:** Graphs survive restart.

### Step 6 — Add Recovery

- retries
- remediation paths
- failed node handling

**Completion:** Failed workflows recover predictably.

---

## Success Criteria

The DAG Execution Engine is complete when:

- [ ] Complex objectives can become execution graphs
- [ ] Independent work executes concurrently
- [ ] Dependencies are enforced
- [ ] Failures are recoverable
- [ ] Execution can resume after interruption
- [ ] Workers remain independent from orchestration logic
- [ ] POL can observe and intervene safely
- [ ] Complete execution history is available

---

## Architectural Principle

The DAG Execution Engine is the bridge between intelligence and execution.

- The **Planner** creates intent.
- The **DAG Engine** creates executable structure.
- **Workers** perform operations.
- **POL** provides governance.

Keeping these boundaries clear is essential for NexusAgent to scale into a reliable autonomous agent platform.