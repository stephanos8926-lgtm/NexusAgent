# Phase 3 — Event-Driven Core: Gap Analysis

**Assessment Date:** 2026-07-19  
**Assessed By:** Lucien (Lead Digital Architect)  
**Current Phase:** Phase 2 Core v1 Delivered (156 tests passing)  
**Target Phase:** Phase 3 — Event-Driven Core  
**Migration Directive:** `docs/architecture/migration/CHIEF-ARCHITECT-DIRECTIVE.md` (Phases 0-11)

---

## Executive Summary

| Metric | Status |
|--------|--------|
| **NATS Infrastructure** | ✅ **COMPLETE** — Full JetStream bus with KV store, durable consumers, pub/sub, health checks |
| **Task State Machine** | ✅ **COMPLETE** — 7-state machine, checkpoint persistence, recovery strategies |
| **Worker Pool** | ✅ **COMPLETE** — Concurrency-limited spawning, turn/wall-time bounds, cancellation |
| **Event Schema (SystemEvent)** | ❌ **MISSING** — No typed event definitions, no schema registry |
| **Event Publishing Integration** | ⚠️ **PARTIAL** — NATS publish exists but no typed event emission from Task/Worker transitions |
| **Event Persistence (Event Log)** | ❌ **MISSING** — No append-only event store (SQLite or NATS KV) |
| **Event Subscribers (POL, Memory, Dashboard)** | ❌ **MISSING** — No subscriber infrastructure |
| **Event Query API** | ❌ **MISSING** — No query-by-time-range/source/type |

**Readiness Score: ~35%** — Infrastructure foundation is solid; event *layer* needs to be built on top.

---

## 1. What EXISTS (Infrastructure Foundation)

### 1.1 NATS JetStream Bus — `src/nexusagent/infrastructure/bus.py` (491 lines)

| Capability | Implementation |
|------------|----------------|
| **Connection Management** | `AgentBus.connect()` — auto-reconnect, callbacks (`_on_disconnected`, `_on_reconnected`, `_on_closed`, `_on_error`), health tracking |
| **Health Monitoring** | `check_health()` → `{healthy, connected, degraded, reconnect_count, timestamps}` |
| **Pub/Sub** | `publish(subject, message)` — JSON + custom `NATSJSONEncoder` (datetime, bytes, set, Path, Exception) |
| **JetStream KV Store** | `put_result(task_id, result)` / `get_result(task_id)` — `nexus_results` bucket, retry + truncation |
| **Ephemeral Subscriptions** | `subscribe(subject, callback)` — dedup, retry/backoff, async lock-protected |
| **Durable Pull Consumers** | `subscribe_durable(subject, callback, stream="nexus_tasks", durable="nexus_worker", batch_size=10, batch_timeout=5s)` — stream creation, consumer creation, ack/nack, batch fetch loop |
| **Singleton Access** | `get_bus()` / `set_bus()` — DI-friendly module-level default |

**Subject Patterns Currently Used:**
- `tasks.submit` — task submission (SDK, routes)
- `tasks.cancel` — task cancellation (routes)
- `nexus_results` KV bucket — task results

**Config (from `config.py`):**
```python
nats_url: "nats://localhost:4222"
nats_reconnect_wait: 2
nats_max_reconnects: 60  # capped to 30 in bus.py
```

---

### 1.2 Task State Machine — `src/nexusagent/core/task/task_state.py` (148 lines)

| Component | Details |
|-----------|---------|
| **TaskState Enum** | `CREATED → PLANNING → EXECUTING → VERIFYING → COMPLETED` (terminal) / `FAILED → RECOVERING → EXECUTING/FAILED` |
| **Transition Validation** | `StateTransitionValidator.validate(from, to)` — raises `StateTransitionError` on illegal moves |
| **Task Dataclass** | `id, objective, owner, state, parent_task, child_tasks[], checkpoints[], artifacts{}, created_at, updated_at` |
| **Checkpoint** | `current_node, completed_actions[], files_changed[], tool_results[], next_action` |
| **Serialization** | `to_dict()` / `from_dict()` — full round-trip |

---

### 1.3 Task Persistence — `src/nexusagent/core/task/task_store.py` (70 lines)

| Method | Status |
|--------|--------|
| `save_task(task)` | ✅ In-memory dict (placeholder for SQLAlchemy) |
| `load_task(id)` | ✅ |
| `list_tasks(state_filter?)` | ✅ |
| `save_checkpoint(task_id, checkpoint)` | ✅ |
| `load_latest_checkpoint(task_id)` | ✅ |
| `delete_task(id)` | ✅ |
| **Backend** | ⚠️ In-memory only — `infrastructure/db/` has SQLAlchemy models but not wired |

---

### 1.4 Recovery Manager — `src/nexusagent/core/task/recovery.py` (104 lines)

| Strategy | Logic |
|----------|-------|
| **RETRY** | Exponential backoff (base 2s × 2^retry), up to `max_retries` (default 3) |
| **ROLLBACK** | If retries exhausted AND checkpoint exists → transition to `EXECUTING` |
| **ESCALATE** | No checkpoint OR retries exhausted → call `on_escalate(task)` callback, log to POL |

---

### 1.5 Worker Pool — `src/nexusagent/core/worker/pool.py` (147 lines)

| Feature | Implementation |
|---------|----------------|
| **Concurrency Limit** | `asyncio.Semaphore(max_workers=4)` |
| **Spawning** | `spawn(contract, depth)` → `SubAgentHandle` + background task |
| **Execution Bounds** | Turn limit (`max_turns`), wall-time limit (`max_wall_time`), cancellation check |
| **Failure Modes** | `on_failure: "abort" | "retry" | "escalate"` |
| **Result Handling** | `_mark_completed(result)` / `_mark_failed(error)` on handle |

---

### 1.6 Server SDK Integration — `src/nexusagent/server/sdk.py` (235 lines)

| Method | Uses NATS |
|--------|-----------|
| `submit_task()` | `bus.publish("tasks.submit", task.model_dump())` |
| `get_result(task_id)` | `bus.get_result(task_id)` (KV) |
| `wait_for_result()` | Polls KV |
| `cancel_task()` | `bus.publish("tasks.cancel", {task_id})` |
| `retry_task()` | Re-publishes to `tasks.submit` |

---

## 2. What Phase 3 REQUIRES (Per Migration Spec)

### 2.1 Event Categories (from `03-event-driven-core.md` + `CHIEF-ARCHITECT-DIRECTIVE.md`)

| Category | Events Required |
|----------|-----------------|
| **Task** | `task.created`, `task.started`, `task.completed`, `task.failed` |
| **Worker** | `worker.started`, `worker.completed`, `worker.failed`, `worker.recovered` |
| **Tool** | `tool.requested`, `tool.completed`, `tool.denied` |
| **Policy** *(Chief Architect adds)* | `approval.required`, `policy.denied`, `intervention.created` |

### 2.2 SystemEvent Schema (Spec §34-46)

```json
{
  "id": "uuid",
  "timestamp": "ISO-8601",
  "source": "string — component identity",
  "type": "string — event.category",
  "payload": "object — type-specific data"
}
```

### 2.3 Implementation Steps (Spec §48-69)

| Step | Description | Status |
|------|-------------|--------|
| **1** | Create `SystemEvent` base type + typed subclasses | ❌ MISSING |
| **2** | Wire NATS JetStream as event backbone (subjects, publishing) | ⚠️ PARTIAL — bus exists, no typed event emission |
| **3** | Persist event history (append-only log: SQLite or NATS KV) | ❌ MISSING |
| **4** | Create subscribers: POL, Memory, Dashboard | ❌ MISSING |

### 2.4 Completion Criteria (Spec §70-74)

| Criterion | Current Status |
|-----------|----------------|
| System behavior reconstructible from event log | ❌ No event log |
| All state transitions produce observable events | ❌ Task/Worker transitions emit no events |
| Subscribers react without polling | ❌ No subscriber infrastructure |
| Event history queryable by time, source, type | ❌ No query API |

---

## 3. Gap Analysis — What Must Be Built

### 3.1 Missing: Event Schema Layer (New Files)

| File | Purpose | Est. Lines |
|------|---------|------------|
| `src/nexusagent/core/events/schema.py` | `SystemEvent` base + `TaskEvent`, `WorkerEvent`, `ToolEvent`, `PolicyEvent` typed subclasses with `payload` TypedDicts | ~150 |
| `src/nexusagent/core/events/subjects.py` | NATS subject naming conventions: `nexus.task.{created\|started\|completed\|failed}`, `nexus.worker.{started\|completed\|failed\|recovered}`, `nexus.tool.{requested\|completed\|denied}`, `nexus.policy.{approval_required\|denied\|intervention}` | ~50 |
| `src/nexusagent/core/events/__init__.py` | Exports | ~10 |

---

### 3.2 Missing: Event Emission Integration (Modify Existing)

| File | Change Required |
|------|-----------------|
| `src/nexusagent/core/task/task_state.py` | `Task.transition_to()` → emit `task.{created\|started\|completed\|failed}` after successful transition |
| `src/nexusagent/core/worker/pool.py` | `WorkerPool._run_worker()` → emit `worker.started` on spawn, `worker.completed`/`worker.failed` on terminal, `worker.recovered` on recovery transition |
| `src/nexusagent/core/task/recovery.py` | `RecoveryManager.attempt_recovery()` → emit `worker.recovered` on rollback/retry success |
| `src/nexusagent/tools/registry/core.py` | Tool execution entry/exit → emit `tool.requested` / `tool.completed` / `tool.denied` (policy check) |
| `src/nexusagent/server/sdk.py` | `submit_task()` → emit `task.created` (already publishes to `tasks.submit` but no typed event) |

---

### 3.3 Missing: Event Persistence Layer (New Files)

| File | Purpose | Est. Lines |
|------|---------|------------|
| `src/nexusagent/infrastructure/event_store.py` | Append-only event log: `append(event)`, `query(time_range?, source?, type?)`, `replay(from_id?)` — backend: SQLite (via existing `infrastructure/db/`) or NATS KV (`nexus_events` bucket) | ~200 |
| `src/nexusagent/infrastructure/db/models.py` | Add `EventLog` SQLAlchemy model (id, timestamp, source, type, payload_json) | ~50 |
| `src/nexusagent/infrastructure/db/task_repo.py` | Add event query methods | ~50 |

---

### 3.4 Missing: Subscriber Infrastructure (New Files)

| File | Purpose | Est. Lines |
|------|---------|------------|
| `src/nexusagent/core/events/subscribers.py` | Base `EventSubscriber` class + `SubscriberRegistry` — manages durable consumers, handles ack/nack, retries | ~150 |
| `src/nexusagent/core/events/pol_subscriber.py` | POL subscriber: listens to `worker.failed`, `tool.denied`, `task.failed` → triggers intervention/escalation | ~100 |
| `src/nexusagent/core/events/memory_subscriber.py` | Memory subscriber: listens to `task.completed`, `tool.completed` → extracts/consolidates memories | ~100 |
| `src/nexusagent/core/events/dashboard_subscriber.py` | Dashboard subscriber: listens to all → pushes to WebSocket / Web UI | ~100 |

---

### 3.5 Missing: Event Query API (New/Modify)

| File | Change |
|------|--------|
| `src/nexusagent/server/routes.py` | Add `GET /events` with query params: `since`, `until`, `source`, `type`, `limit` |
| `src/nexusagent/server/sdk.py` | Add `list_events()`, `stream_events()` methods |

---

## 4. File/Test Estimates

| Category | New Files | Modified Files | Est. Total Lines | Est. Tests |
|----------|-----------|----------------|------------------|------------|
| Event Schema | 3 | 0 | ~210 | 20 |
| Event Emission | 0 | 5 | ~150 | 15 |
| Event Persistence | 3 | 2 | ~300 | 25 |
| Subscribers | 4 | 0 | ~450 | 30 |
| Query API | 0 | 2 | ~100 | 10 |
| **TOTAL** | **10** | **9** | **~1,210** | **~100** |

---

## 5. Dependencies & Ordering

```
Phase 3 Dependency Graph:

  [Event Schema] ──┐
                   ├─→ [Event Emission] ──┐
  [Event Store] ←──┤                       ├─→ [Subscribers] ──→ [Query API]
                   └─→ [Event Store] ──────┘
```

**Critical Path:**
1. **Event Schema** (no deps) — 1-2 days
2. **Event Store** (needs schema, DB models) — 2-3 days
3. **Event Emission** (needs schema, bus, store) — 2-3 days
4. **Subscribers** (needs schema, store, bus durable consumers) — 3-4 days
5. **Query API** (needs store) — 1 day

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| NATS subject design conflicts with existing `tasks.submit` | Medium | High | Define subject taxonomy upfront in `subjects.py`; prefix all Phase 3 subjects with `nexus.` |
| In-memory `TaskStore` not swapped for SQLAlchemy before Phase 3 | High | Medium | Wire SQLAlchemy `TaskRepo` (exists in `infrastructure/db/task_repo.py`) before event persistence |
| Event volume overwhelms NATS KV (1MB limit) | Low | Medium | Use NATS *streams* for event log (not KV); KV only for latest task results |
| Subscriber crash loses events | Medium | High | Use JetStream durable consumers with `ack_policy=explicit`, `deliver_policy=all`, `max_deliver=-1` |
| Phase 4 (LangGraph Workers) blocked on events | High | Critical | Phase 3 completion criteria must include: `worker.started/completed/failed/recovered` events emitted |

---

## 7. Recommended Next Steps

1. **Create Event Schema** (`schema.py`, `subjects.py`) — Foundation for all downstream work
2. **Wire SQLAlchemy TaskRepo** — Replace in-memory `TaskStore` so events have durable backing
3. **Implement EventStore** — Append-only log with query API (SQLite or NATS stream)
4. **Instrument Task/Worker Transitions** — Emit typed events from existing state machines
5. **Build Subscriber Framework** — Base class + POL/Memory/Dashboard implementations
6. **Add Event Query REST/WebSocket Event APIs** — For dashboard and external consumers

---

## 8. Mapping to Chief Architect Directive (Phase 3)

| Directive Requirement | Current State | Gap |
|-----------------------|---------------|-----|
| "Events produce state. Avoid hidden state without history." | Task state exists but no event log | Build event store + emission |
| "Task events: created, started, completed, failed" | Task states exist, no events | Emit on every transition |
| "Worker events: started, completed, failed, recovered" | WorkerPool exists, no events | Emit from `WorkerPool._run_worker()` |
| "Tool events: requested, completed, denied" | Tools execute via registry, no events | Emit from tool registry executor |
| "Policy events: approval.required, policy.denied, intervention.created" | POL not yet implemented (Phase 7) | Defer to Phase 7, but define schema now |
| "Events available to: POL, Memory, UI, Monitoring, Recovery" | No subscriber infra | Build subscriber framework |

---

## 9. Appendix: Current NATS Subject Usage (Audit)

| Subject | Publisher | Consumer | Purpose |
|---------|-----------|----------|---------|
| `tasks.submit` | `sdk.submit_task()`, `routes.create_task()` | WorkerPool (via `subscribe_durable("nexus.task.>", durable="nexus_worker")`) | Task queue |
| `tasks.cancel` | `routes.cancel_task()` | WorkerPool (same durable consumer) | Cancellation signal |
| `nexus_results` (KV) | Worker result storage | SDK `get_result()`, routes | Task results |

**No event subjects exist yet.** All Phase 3 subjects will be new.

---

*Gap Analysis complete. Ready for Phase 3 implementation planning.*