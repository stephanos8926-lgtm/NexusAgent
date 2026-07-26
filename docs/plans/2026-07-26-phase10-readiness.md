# Phase 10 Observability & Reliability — Readiness Analysis

> **Generated:** 2026-07-26
> **Context:** Pre-implementation analysis for Phase 10. Phase 8 (Capability Security Model) just merged. Phase 9 pending. Phase 10 work cannot start until Phase 9 lands.

---

## Current State

### Existing Observability Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| **Event System** | ✅ **Complete** | Structured `SystemEvent` base class with UUID, ISO-8601 timestamp, source, type, payload. NATS subjects: `nexus.{category}.{type}`. EventStore persists to SQLite with query/replay. Factory methods for typed events (TaskEvent, WorkerEvent, ToolEvent, PolicyEvent). |
| **Event Emitter** | ✅ **Complete** | `EventEmitter` with async `emit()` and sync `emit_sync()`. Auto-persists to EventStore before NATS publish. Background queue for fire-and-forget. |
| **Structured Logging** | 🟡 **Partial** | Standard `logging` module used throughout. Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`. **Missing:** trace_id, task_id, worker_id, component, event_type, severity as structured fields. No JSON output. |
| **Distributed Tracing** | ❌ **Not Implemented** | No trace_id propagation, no span concept, no OpenTelemetry integration. Task/worker IDs exist in events but not linked as trace context. |
| **Metrics Collection** | ❌ **Not Implemented** | No Prometheus client, no counters/histograms/gauges. No `/metrics` endpoint. Budget guard tracks spend but not exposed as metrics. |
| **Health Endpoints** | 🟡 **Partial** | `/health` returns NATS + JetStream status. `/version` returns version + uptime. **Missing:** per-subsystem health (Runtime, Worker Manager, Event Bus, Memory, POL, Database, External Providers). No DEGRADED/FAILED/RECOVERING states. |
| **Failure Classification** | 🟡 **Partial** | Circuit breaker has OPEN/HALF_OPEN/CLOSED states. Budget guard has QUOTA_EXHAUSTED state. **Missing:** formal Transient/Deterministic/Security classification. No retry policies with classification. |
| **Recovery Workflows** | 🟡 **Partial** | Worker has `recovered` event with checkpoint. Runtime lifecycle has FAILED→TERMINATED. **Missing:** graph/DAG checkpoint restore, session workspace preservation, reassignment logic. |
| **Chaos Testing** | ❌ **Not Implemented** | No framework for injecting failures (kill worker, disconnect bus, corrupt checkpoint). |
| **Structured Audit** | ✅ **Complete** | `audit_grant`/`audit_denial` (async + sync) emit PolicyEvent to EventStore with full context. |
| **Budget Guard** | ✅ **Complete** | `LLMBudgetGuard` tracks daily/monthly spend, alerts at thresholds, trips on quota exhaustion, persists state. Integrates with circuit breaker. |
| **Circuit Breaker** | ✅ **Complete** | `CircuitBreaker` with CLOSED/OPEN/HALF_OPEN, configurable thresholds, quota-error immediate trip, budget guard notification. |
| **Retry Logic** | ✅ **Complete** | `retry_with_backoff` / `retry_on_false` decorators with exponential backoff, jitter, sync+async support. |
| **Runtime Lifecycle** | ✅ **Complete** | 7-state machine (CREATED→INITIALIZING→RUNNING→PAUSED/FAILED→TERMINATED/COMPLETED). HealthStatus with healthy/degraded/failed. All managed components implement `LifecycleMixin`. |

### Codebase Architecture for Observability

```
Event Backbone (NATS + EventStore)
       │
       ├── TaskEvent (created/started/completed/failed)
       ├── WorkerEvent (started/failed/recovered)
       ├── ToolEvent (requested/completed/denied)
       └── PolicyEvent (denied/allowed/updated/violation)
              │
       ┌──────┴──────┐
       ▼             ▼
  EventStore     EventEmitter
  (SQLite)       (NATS publish)
       │             │
       └──────┬──────┘
              ▼
       Observability Layer (TO BE BUILT)
       ├── Structured Logging (JSON + trace fields)
       ├── Distributed Tracing (trace_id propagation)
       ├── Metrics (Prometheus /metrics)
       ├── Health Monitoring (per-subsystem)
       ├── Failure Classification
       ├── Recovery Orchestration
       └── Chaos Testing Framework
```

---

## Gap Analysis

### Phase 10 Spec Items vs. Current Implementation

| Spec Item | Status | Gap Details |
|-----------|--------|-------------|
| **Structured Logging** (required fields: timestamp, trace_id, task_id, worker_id, component, event_type, severity, message, metadata) | 🟡 **Partial** | Current logging uses standard format. Missing: trace_id propagation, task/worker/component fields, JSON output, structured metadata. Need to wrap logger or add structlog. |
| **Distributed Tracing** (request_id, task_id, graph_id, node_id, worker_id) | ❌ **Not Implemented** | No trace context propagation. Events have task_id/worker_id but no shared trace_id. No span creation/parent-child linkage. No OpenTelemetry. |
| **Metrics Collection** (Runtime, Agent, LLM, Tool categories) | ❌ **Not Implemented** | No Prometheus client in deps. No counter/histogram/gauge instrumentation. Budget guard tracks spend internally but not exposed. |
| **Health Monitoring** (Runtime, Worker Manager, Event Bus, Memory, POL, DB, External Providers) | 🟡 **Partial** | `/health` only checks NATS/JS. Runtime has `health()` returning `HealthStatus`. Worker/Session/Tools have health(). **Missing:** unified health endpoint aggregating all subsystems with HEALTHY/DEGRADED/FAILED/RECOVERING states. |
| **Failure Classification** (Transient, Deterministic, Security) | 🟡 **Partial** | Circuit breaker distinguishes quota errors. **Missing:** formal classification enum, retry policies per classification, escalation thresholds. |
| **Recovery Requirements** (Worker state, Graph checkpoint, Session workspace) | 🟡 **Partial** | Worker emits `recovered` event with checkpoint. Runtime lifecycle has FAILED state. **Missing:** automatic reassignment, DAG node resume logic, session artifact preservation. |
| **Reliability Patterns** (Retry Policies, Circuit Breakers, Backpressure) | 🟡 **Partial** | Circuit breaker ✅. Retry decorators ✅. **Missing:** backpressure (queue depth limits, worker pool saturation, API rate limits). Retry policies not tied to failure classification. |
| **Chaos Testing** (kill worker, disconnect bus, corrupt checkpoint) | ❌ **Not Implemented** | No chaos framework. No test scenarios for failure injection. |

---

## Implementation Plan

### Step 1: Unified Event Schema Enhancement
**Files to modify:**
- `src/nexusagent/core/events/base.py` — Add `trace_id`, `span_id`, `parent_span_id` fields to `SystemEvent`
- `src/nexusagent/core/events/*.py` — Propagate trace context in factory methods

**Tasks:**
- [ ] Add trace_id/span_id to SystemEvent dataclass (optional, defaults to new UUID)
- [ ] Add `with_trace_context(trace_id, span_id)` method to create child events
- [ ] Update all event factory methods to accept/propagate trace context
- [ ] Ensure EventStore schema includes trace fields (migration)

### Step 2: Structured Logging with Trace Context
**Files to modify:**
- `src/nexusagent/infrastructure/config.py` — Add `LoggingConfig` structured output option
- `src/nexusagent/infrastructure/utils/logging.py` (new) — Structured logger wrapper
- All modules using `logging.getLogger(__name__)` — Migrate to structured logger

**Tasks:**
- [ ] Add `structured: bool` and `format: str` (json/text) to LoggingConfig
- [ ] Create `StructuredLogger` class that injects trace_id/task_id/worker_id from contextvars
- [ ] Add contextvars for trace_id, task_id, worker_id, component
- [ ] Update config loading to support JSON format
- [ ] Provide `get_logger(__name__)` helper returning StructuredLogger

### Step 3: Distributed Tracing (OpenTelemetry)
**Files to modify:**
- `src/nexusagent/infrastructure/utils/tracing.py` (new) — OpenTelemetry setup
- `src/nexusagent/core/events/emitter.py` — Inject trace context on emit
- `src/nexusagent/server/routes.py` — Extract trace context from headers
- `pyproject.toml` — Add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-prometheus`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-nats`

**Tasks:**
- [ ] Add OpenTelemetry dependencies
- [ ] Create `TracingManager` for provider setup (OTLP/Console/Jaeger)
- [ ] Add FastAPI middleware to extract/continue trace context from headers
- [ ] Add NATS instrumentation (propagate trace context in message headers)
- [ ] Create span helpers for task/worker/tool operations
- [ ] Export traces to configured backend

### Step 4: Metrics Collection (Prometheus)
**Files to modify:**
- `src/nexusagent/infrastructure/utils/metrics.py` (new) — Prometheus metrics definitions
- `src/nexusagent/server/routes.py` — Add `/metrics` endpoint
- `pyproject.toml` — Add `prometheus-client`, `prometheus-fastapi-instrumentator`

**Tasks:**
- [ ] Add Prometheus dependencies
- [ ] Define metrics per spec categories:
  - **Runtime:** `active_sessions`, `active_workers`, `task_duration_seconds`, `queue_depth`, `memory_usage_bytes`
  - **Agent:** `tasks_total{status="success|failed|retry"}`, `interventions_total`, `verification_failures_total`
  - **LLM:** `llm_tokens_total{provider,model,type="input|output"}`, `llm_latency_seconds`, `llm_cost_usd_total`, `llm_failures_total`
  - **Tool:** `tool_executions_total{tool,status="success|failed|denied"}`, `tool_duration_seconds`, `permission_denials_total`
- [ ] Instrument key paths: task submit/start/complete/fail, worker start/fail/recover, tool requested/completed/denied, LLM calls
- [ ] Add `/metrics` endpoint with `prometheus-fastapi-instrumentator`
- [ ] Export budget guard state as metrics

### Step 5: Health Monitoring Enhancement
**Files to modify:**
- `src/nexusagent/server/routes.py` — Enhance `/health` endpoint
- `src/nexusagent/runtime/runtime.py` — Aggregate subsystem health
- `src/nexusagent/infrastructure/bus.py` — Already has `check_health()`
- `src/nexusagent/memory/hybrid_memory.py` — Add health check
- `src/nexusagent/core/pol.py` — Add health check

**Tasks:**
- [ ] Define `SubsystemHealth` enum: HEALTHY, DEGRADED, FAILED, RECOVERING
- [ ] Add `health()` method to each major subsystem returning structured health
- [ ] Create `HealthAggregator` in runtime that collects all subsystem health
- [ ] Enhance `/health` to return per-subsystem status + overall
- [ ] Add readiness (`/ready`) vs liveness (`/health`) distinction
- [ ] Include dependency health (NATS, DB, external providers)

### Step 6: Failure Classification & Retry Policies
**Files to modify:**
- `src/nexusagent/infrastructure/utils/failure.py` (new) — Classification + policies
- `src/nexusagent/infrastructure/utils/circuit.py` — Integrate classification
- `src/nexusagent/infrastructure/utils/retry.py` — Add classification-aware retry
- `src/nexusagent/core/worker/worker.py` — Use classified retries

**Tasks:**
- [ ] Define `FailureClass` enum: TRANSIENT, DETERMINISTIC, SECURITY
- [ ] Create `classify_failure(exception)` function mapping exception types
- [ ] Define `RetryPolicy` dataclass: max_attempts, base_delay, classification, escalation_threshold
- [ ] Map failure classes to retry policies (TRANSIENT→retry with backoff, DETERMINISTIC→no retry, SECURITY→escalate to POL)
- [ ] Update circuit breaker to accept failure classification
- [ ] Add backpressure: queue depth limits, worker pool saturation detection, API rate limit awareness

### Step 7: Recovery Workflows
**Files to modify:**
- `src/nexusagent/core/worker/worker.py` — Enhance recovery logic
- `src/nexusagent/core/dag_engine.py` — Checkpoint/restore for graph nodes
- `src/nexusagent/runtime/session.py` — Session workspace preservation
- `src/nexusagent/runtime/runtime.py` — Orchestration

**Tasks:**
- [ ] Worker: persist checkpoints on each state transition, implement reassignment on failure
- [ ] DAG Engine: save node checkpoints, identify incomplete nodes on resume, safe restart
- [ ] Session: preserve workspace state, artifacts, reconnect logic
- [ ] Add `RecoveryManager` coordinating worker/graph/session recovery
- [ ] Emit `recovery.started`/`recovery.completed`/`recovery.failed` events

### Step 8: Chaos Testing Framework
**Files to modify:**
- `src/nexusagent/testing/chaos.py` (new) — Chaos injection framework
- `tests/chaos/` (new) — Chaos test scenarios

**Tasks:**
- [ ] Create `ChaosEngine` with fault injection: kill_worker, disconnect_bus, corrupt_checkpoint, latency_injection, error_injection
- [ ] Implement scenario runner with setup/teardown
- [ ] Define test scenarios from spec:
  - Kill worker during execution → task resumes
  - Disconnect event bus → system reconnects safely
  - Corrupt checkpoint → recovery failure detected
- [ ] Add CI integration (optional: run in staging)

---

## Estimated Effort

| Deliverable | Complexity | Est. Effort | Key Files to Modify |
|-------------|------------|-------------|---------------------|
| **1. Unified Event Schema (trace context)** | Low | 2-3 days | `core/events/base.py`, `core/events/*.py`, `infrastructure/db/models.py` (migration) |
| **2. Structured Logging** | Low | 2-3 days | `infrastructure/config.py`, `infrastructure/utils/logging.py` (new), all modules |
| **3. Distributed Tracing (OpenTelemetry)** | High | 5-7 days | `infrastructure/utils/tracing.py` (new), `server/routes.py`, `core/events/emitter.py`, `pyproject.toml` |
| **4. Metrics Collection (Prometheus)** | Medium | 3-4 days | `infrastructure/utils/metrics.py` (new), `server/routes.py`, `pyproject.toml`, instrument 15+ call sites |
| **5. Health Monitoring** | Medium | 2-3 days | `server/routes.py`, `runtime/runtime.py`, `infrastructure/bus.py`, `memory/hybrid_memory.py`, `core/pol.py` |
| **6. Failure Classification & Retry Policies** | Medium | 3-4 days | `infrastructure/utils/failure.py` (new), `infrastructure/utils/circuit.py`, `infrastructure/utils/retry.py`, `core/worker/worker.py` |
| **7. Recovery Workflows** | High | 5-7 days | `core/worker/worker.py`, `core/dag_engine.py`, `runtime/session.py`, `runtime/runtime.py` |
| **8. Chaos Testing Framework** | Medium | 3-4 days | `testing/chaos.py` (new), `tests/chaos/` (new) |

### Total Estimated Effort: **25-35 days** (single engineer)

### Top 5 Files Requiring Most Modification

1. **`src/nexusagent/server/routes.py`** — Add `/metrics`, enhance `/health`, add tracing middleware, wire all observability endpoints
2. **`src/nexusagent/core/events/base.py`** — Add trace_id/span_id to SystemEvent, propagate through all event types
3. **`src/nexusagent/infrastructure/utils/logging.py`** (new) — Structured logger with contextvars, used everywhere
4. **`src/nexusagent/runtime/runtime.py`** — Health aggregation, recovery orchestration, backpressure coordination
5. **`src/nexusagent/infrastructure/utils/metrics.py`** (new) — All Prometheus metric definitions, instrumentation helpers

### Dependencies to Add (pyproject.toml)
```toml
# Observability
"opentelemetry-api",
"opentelemetry-sdk",
"opentelemetry-exporter-otlp",
"opentelemetry-instrumentation-fastapi",
"opentelemetry-instrumentation-nats",
"prometheus-client",
"prometheus-fastapi-instrumentator",
# Optional: structured logging
"structlog",
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenTelemetry integration complexity | High | Medium | Start with console exporter, add OTLP later. Use auto-instrumentation where possible. |
| Metrics cardinality explosion | Medium | High | Use bounded label sets (no unbounded task_id/worker_id as labels). Use histograms for durations. |
| Event schema migration (SQLite) | Low | Medium | Add columns with defaults, backfill trace_id from task_id/worker_id where possible. |
| Performance overhead | Medium | Medium | Batch metric updates, sample traces (10%), async logging. Benchmark before/after. |
| Phase 9 dependency | High | Blocker | Cannot start until Phase 9 lands. Use this time for design docs and spike prototypes. |

---

## Recommended Implementation Order

1. **Week 1:** Event schema + Structured logging (foundation for everything else)
2. **Week 2:** Health monitoring + Metrics (immediate operational value)
3. **Week 3-4:** Distributed tracing (OpenTelemetry) — highest complexity
4. **Week 5:** Failure classification + Retry policies + Backpressure
5. **Week 6:** Recovery workflows
6. **Week 7:** Chaos testing framework
7. **Week 8:** Integration testing, documentation, runbooks

---

## Success Criteria Mapping

| Spec Criterion | Implementation Target |
|----------------|----------------------|
| Every major action is traceable | Steps 1, 3 (trace context + OpenTelemetry) |
| Failures are classified | Step 6 (FailureClass + classification) |
| Recovery is predictable | Step 7 (RecoveryManager + workflows) |
| System state is explainable | Steps 4, 5 (metrics + health) |
| Operational metrics exist | Step 4 (Prometheus /metrics) |
| Autonomous workers can run unattended safely | Steps 6, 7, 8 (classification + recovery + chaos validation) |

---

## Next Steps

1. **Wait for Phase 9 to land** — Phase 10 cannot start until then
2. **Create spike branch** — Prototype OpenTelemetry + structured logging in isolation
3. **Design review** — Validate metric names, trace semantics, health state machine with team
4. **Write detailed task breakdown** — Use `writing-plans` skill to create bite-sized tasks per step above
5. **Set up CI for observability** — Metrics endpoint tests, trace sampling validation, chaos test pipeline