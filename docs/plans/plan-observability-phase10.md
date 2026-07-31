# Phase 10 — Observability and Reliability: 7-Way Audit & Implementation Plan

This document outlines the step-by-step implementation plan for **Phase 10: Observability and Reliability**, along with a comprehensive **7-way completeness audit** conducted to ensure stability, performance, security, and exception resilience.

---

## Part 1: The 7-Way Completeness Audit

### 1. Forward Audit (Happy Path Flow)
- **Data Flow**: System operations (e.g., task execution, tool calls, policy evaluations) run under the `trace_context` context manager.
- **Context Generation**: Any nested block or runtime operation propagates correlation IDs (`trace_id`, `task_id`, `worker_id`, `component`, etc.) down the execution scope via Python's thread/asyncio-safe `ContextVars`.
- **Log Emission**: Standard python log calls are captured by the `StructuredLoggingFormatter` when structured logging is enabled. The output format is a serialized JSON dictionary containing: `timestamp`, `trace_id`, `task_id`, `worker_id`, `component`, `event_type`, `severity`, `message`, and `metadata`.
- **Metric Collection**: Callers invoke the global metrics collector (via `get_metrics()`). Counters, gauges, and histograms are thread-safely recorded.
- **API Exposition**: The newly registered `/metrics` FastAPI REST endpoint returns a complete snapshot of all active counters, gauges, and histograms.

### 2. Reverse Audit (Error Paths & Resiliency)
- **Log Formatting Errors**: If JSON serialization fails during formatting (e.g., due to non-serializable elements in log metadata), the formatter gracefully captures the string representation of those fields or falls back to standard message output without raising an exception that crashes the host process.
- **Missing Context Variables**: When log entries are emitted outside of an active tracing context, all tracing variables default safely to empty strings `""` instead of throwing a `LookupError` or key error.
- **Metrics Failure Resiliency**: If any metrics operation raises an unexpected error or resource limit is encountered, operations fail silently or log a non-fatal warning so that execution flows are never blocked by metric telemetry.

### 3. Adversarial Audit (Input Exploitations & Hardening)
- **Label Manipulation**: An attacker submitting tasks or tool names with specialized formatting characters (e.g., curly braces `{}`, commas `,`, equal signs `=`) could attempt to corrupt the metrics label key parser.
- **Hardening**: `MetricsCollector._label_key` sanitizes labels by sorted order and strictly builds key strings dynamically without relying on unsafe evaluations. JSON serialization at the `/metrics` endpoint guarantees valid syntax output regardless of label content.
- **Log Injection**: Formatting strings or control characters in log messages will be treated as plain string values within the JSON `message` attribute, neutralizing traditional ANSI escape or log injection attacks.

### 4. Red-Team Audit (Information Leaks & Secrets Protection)
- **Token Scrubbing**: To prevent exposure of private credentials, API keys, or JWT tokens in logs or metrics:
  - High-risk headers (like `X-API-Key`, `Authorization`) are excluded from structured log metadata.
  - The metrics collection system solely collects metadata aggregates (e.g., counters, durations, counts) and never includes raw query bodies, prompt variables, or secrets.
- **Access Vectors**: The `/metrics` endpoint is read-only and restricted to system administrators or trusted internal aggregators in production topologies.

### 5. Top-Down Audit (System-Level Integration)
- **Client/CLI Tracing**: When a user runs `nexus-client submit`, a fresh tracing ID is generated. The request reaches the server's API route, where a `SystemEvent` is created and stored.
- **Lifecycle Correlation**: The event automatically extracts tracing context from active `ContextVars`.
- **Orchestration**: The `DAGEngine` runs node executions within a nested `trace_context`, propagating the same correlation IDs. Any sub-logs or tool invocation records show the exact same `trace_id` and `task_id`, allowing a developer to query the entire workflow sequence in the event log database or structured logs using a single identifier.

### 6. Bottom-Up Audit (Concurrency & Async Safety)
- **Async/Await Boundaries**: Since NexusAgent utilizes multi-worker concurrent execution pipelines, multiple threads and asyncio tasks write to logging/metrics simultaneously.
- **ContextVars Thread-Safety**: ContextVars are natively isolated per coroutine and propagate across tasks cleanly.
- **Collector Thread-Safety**: `MetricsCollector` implements a thread-safe `threading.Lock` across all increment, gauge, and histogram write operations and during `get_snapshot()` to eliminate race conditions, preventing dictionary mutation during iteration.

### 7. Completeness Audit (Requirements Verification)
- **All Required Logs Fields**: Verified. The JSON payload includes `timestamp`, `trace_id`, `task_id`, `worker_id`, `component`, `event_type`, `severity`, `message`, and `metadata`.
- **Tracing Identifiers**: Verified. Context propagation handles `request_id`, `task_id`, `graph_id`, `node_id`, and `worker_id` cleanly.
- **Four Categories of Metrics**:
  - *Runtime*: `active_sessions`, `active_workers`, `task_duration_seconds`, `queue_depth`, `memory_usage_bytes` are fully supported.
  - *Agent*: `tasks_total`, `interventions_total`, `verification_failures_total` are supported.
  - *LLM*: `llm_tokens_total`, `llm_latency_seconds`, `llm_cost_usd_total`, `llm_failures_total` are supported.
  - *Tool*: `tool_executions_total`, `tool_duration_seconds`, `permission_denials_total` are supported.
- **Health Subsystems**: Verified. `get_system_health()` checks all required subsystems: Runtime, Worker Manager, Event Bus, Memory System, POL, Database, and External Providers.
- **Failure Classification**: Verified. `FailureClassifier.classify` successfully maps errors to TRANSIENT, DETERMINISTIC, and SECURITY categories.

---

## Part 2: Step-by-Step Implementation Plan

### Step 1: Configuration Option
- Add a `structured: bool` field to the `LoggingConfig` class in `src/nexusagent/infrastructure/config.py`.

### Step 2: Global Integration of Structured Logging
- Integrate structured logging startup in `src/nexusagent/server/server.py` and `src/nexusagent/interfaces/cli.py` to call `setup_structured_logging` when structured logging is enabled.

### Step 3: Wire `/metrics` Endpoint
- Register the `/metrics` endpoint in `src/nexusagent/server/routes.py` to retrieve and return a snapshot of current system metrics from the `MetricsCollector`.

### Step 4: Write Integration & Validation Tests
- Write test cases in `tests/test_observability.py` to verify:
  1. The new config parameter behaves correctly.
  2. The `/metrics` endpoint is registered and successfully returns metrics snapshots.
  3. Structured logging behaves correctly under custom configuration.

### Step 5: Mark Delivered
- Update `docs/devboard/README.md` and `docs/.jules/TASK.md` to mark Phase 10 as COMPLETED / DELIVERED.
