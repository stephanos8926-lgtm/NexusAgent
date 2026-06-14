# BIRDSEYE ARCHITECTURE AUDIT — NexusAgent

> **Date:** 2026-06-14
> **Auditor:** OWL (Lucien)
> **Scope:** Full codebase — `src/nexusagent/` (82 files, ~13.6K LOC), `tests/` (50 files, ~7.6K LOC)
> **Method:** AST-based structural analysis (ast-read, ast-grep, callers, callees) + full-file reading of 45+ critical modules

---

## Executive Summary

NexusAgent is a well-structured AI coding agent platform with clear module boundaries, a clean 7-phase refactoring history, and thoughtful engineering in critical paths (circuit breakers, retry logic, graduated compaction, hybrid memory). The codebase has **zero TODOs/FIXMEs**, uses modern Python 3.13+ patterns, and maintains a src layout with compat shims for safe incremental extraction.

**Top 3 risks:**
1. **NATS as single point of failure** — the entire task orchestration layer depends on NATS JetStream being alive
2. **5 global singletons** (`settings`, `auth_manager`, `worker`, `worker_pool`, `_default_bus`) make testing and multi-tenancy hard
3. **SQLite as storage backend** — the memory index, checkpoint DB, and task DB are all SQLite, creating a scalability ceiling

**Top 3 strengths:**
1. **Clean abstraction layers** — clear interface → service → repository separation in the server and DB layers
2. **Resilience patterns** — circuit breakers on NATS and agent calls, exponential backoff retry, task reaper for zombie tasks
3. **Extension-friendly** — tool registry with decorator-based registration, plugin-style hooks system, provider-agnostic LLM bridge

---

## 1. Module Dependency Graph

### Current State

**Import topology** (based on structural analysis of all 82 source files):

```
nexusagent/
├── infrastructure/          # Foundation layer (imported by almost everything)
│   ├── config.py           → settings (Pydantic, 3-tier: yaml → env → defaults)
│   │   └── Imported by: 20+ files (virtually every module)
│   ├── bus.py              → AgentBus (NATS JetStream), get_bus() singleton
│   │   └── Imported by: worker.py, server.py, cli.py, server/sdk.py
│   ├── auth.py             → AuthManager (Fernet keystore), auth_manager singleton
│   │   └── Imported by: api_auth.py, cli.py
│   ├── db/                 → DatabaseManager, TaskRepository, SessionRepository
│   │   ├── manager.py      ← config (settings.server.db_path)
│   │   ├── task_repo.py    ← llm/models (TaskStatus)
│   │   └── session_repo.py ← db/models
│   ├── prompt_loader.py    ← config (settings.prompt.*)
│   ├── api_auth.py         ← auth (auth_manager)
│   └── utils/              ← Pure utilities (no nexusagent imports)
│       ├── retry.py        ← functools, asyncio
│       └── circuit.py      ← asyncio, logging
│
├── core/                   # Agent orchestration layer
│   ├── agent.py            ← config, tools/register_all, tools/registry
│   ├── session.py          ← config, hooks, llm/models, prompt_loader, memory, tools/registry
│   ├── worker.py           ← agent, bus, db, llm/models, subagent, graph
│   ├── subagent.py         ← llm/models, config
│   ├── orchestration.py    ← llm (llm singleton), tools/research
│   └── graph.py            ← orchestration, config, sqlite3, langgraph
│
├── tools/                  # 25+ tools + registry subpackage
│   ├── register_all.py     ← ALL tool modules (centralized registration)
│   ├── registry/           ← core, policy, search, types
│   │   └── policy.py       ← registry/core (_REGISTRY)
│   ├── fs.py               ← pathlib (workspace jail via _WORKSPACE_ROOT global)
│   ├── shell.py            ← subprocess, shlex (shell=False, good)
│   ├── research.py         ← httpx, subprocess (multiple API keys)
│   └── git.py              ← subprocess, shlex
│
├── memory/                 # Hybrid memory system
│   ├── memory.py           ← sqlite_vec, llm/models, memory.index, memory_files
│   ├── memory_files.py     ← yaml, re (file-based canonical storage)
│   ├── index/              ← sqlite3, sqlite_vec, struct
│   │   ├── embeddings.py   ← config (settings.gemini_api_key)
│   │   └── index.py        ← embeddings, config
│   └── compaction.py       ← pure logic (no external deps)
│
├── llm/                    # Multi-provider LLM bridge
│   ├── llm.py              ← config, utils/retry (Gemini + OpenRouter)
│   └── models.py           ← pydantic (TaskSchema, ResultSchema, events)
│
├── interfaces/             # External interfaces
│   ├── tui.py              ← config, cli, version, *widgets, *interfaces
│   ├── cli.py              ← server/sdk, config, core/worker, llm/models, hooks
│   ├── web_ui.py           ← server/sdk (Gradio)
│   └── tui_widgets.py      ← config (NO_COLOR)
│
├── server/                 # FastAPI + WebSocket
│   ├── server.py           ← config, bus, version, server/sdk, worker, db, tools, agent
│   └── sdk.py              ← bus, llm/models, version
│
├── hooks/                  # Pre/post execution hooks
│   └── __init__.py          ← asyncio, enum (global _manager singleton)
│
└── widgets/                # TUI widgets (Textual)
    ├── messages/           ← Pure widget classes
    ├── theme/              ← Color registry
    ├── chat_input.py       ← asyncio
    └── status.py            ← Pure widget
```

**Coupling metrics** (based on `settings` import analysis):
- `settings` is imported directly by **20 unique files** across 6 packages
- `get_bus()` / `AgentBus` is imported by **4 files** (worker, server, cli, sdk)
- `db` (db_manager, task_repo, session_repo) is imported by **8 files**

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 1.1 | **Wide `settings` fan-in** — 20 files import `settings` directly, creating implicit coupling to the config schema. Changes to config structure ripple across the entire codebase. | Medium |
| 1.2 | **No dependency injection** — `settings`, `get_bus()`, `auth_manager`, `db_manager` are all module-level singletons. Hard to test in isolation, impossible to run multiple instances in one process. | High |
| 1.3 | **Circular import risk in tools/registry** — `policy.py` imports from `core.py` with a delayed import to avoid circular dependency. This is documented but fragile. | Medium |
| 1.4 | **TUI imports deep into core** — `tui.py` imports from `core/session.py`, `core/agent.py`, `core/worker.py`, `llm/models.py`, `tools/*`, `widgets/*`, `skills.py`. It's a "god import" that ties the interface to everything. | Medium |
| 1.5 | **No unused modules detected** — all 82 source files have at least one external consumer. Good hygiene. | — |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Introduce a `Container` / DI protocol — replace direct `settings` imports with injected config objects in new code. Keep `settings` for backward compat. | M |
| P2 | Add `get_db()`, `get_auth()` factory functions alongside existing singletons for test injection. | S |
| P3 | Split `tui.py` imports — move session management into an interface-specific controller module. | M |
| P4 | Document the `tools/registry` circular import pattern with a sequence diagram in `docs/adrs/`. | S |

---

## 2. Coupling & Cohesion

### Current State

**Well-separated modules (good cohesion):**
- `infrastructure/utils/` — pure functions, zero nexusagent imports
- `memory/compaction.py` — stateless pipeline, no external deps
- `tools/registry/types.py` — single dataclass, no imports
- `llm/models.py` — pure Pydantic schemas, no business logic
- `hooks/__init__.py` — self-contained event system

**Tightly coupled modules (needs attention):**
- `core/session.py` — imports from 23 different modules across 6 packages. It's the "spider in the web" connecting config, hooks, LLM, memory, tools, prompt loading, and DB.
- `server/server.py` — imports from 28 different modules. The FastAPI app is a god object that creates the agent, manages sessions, handles WebSockets, and serves 13 endpoints.
- `tools/register_all.py` — imports ALL 25+ tools. This is a 728-line file that grows with every new tool.

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 2.1 | **`core/session.py` is overloaded** — handles message flow, event streaming, approval gates, memory recall, context compaction, image encoding, git info, environment context, and tool listing. At 597 lines, it's doing too much. | High |
| 2.2 | **`server/server.py` is a god object** — 389 lines mixing HTTP endpoints, WebSocket handling, lifespan management, and direct agent creation. | High |
| 2.3 | **`tools/register_all.py` grows unbounded** — every new tool adds ~20 lines. At 728 lines already, this will become unmanageable. | Medium |
| 2.4 | **Memory system has two coexisting implementations** — old SQLite `Memory` class and new `HybridMemoryManager` both in `memory.py`. The old one is still imported by `memory_index.py` compat shim. | Medium |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Extract `Session.send()` into a `SessionRunner` class — separate the streaming/event logic from the state management. | M |
| P2 | Split `server/server.py` into `server/routes/` (HTTP), `server/websocket.py` (WS), `server/lifespan.py` (startup/shutdown). | M |
| P3 | Convert `register_all.py` to auto-discovery — scan `tools/` for `@register_tool` decorators instead of manual imports. | S |
| P4 | Deprecate and remove the old `Memory` class — migrate any remaining consumers to `HybridMemoryManager`. | M |

---

## 3. Abstraction Layers

### Current State

The system has **clear layering in some areas** and **missing layers in others**:

**Well-layered:**
```
Interface Layer:    tui.py / cli.py / web_ui.py / server.py
                        ↓
Service Layer:      Session / SessionManager / NexusWorker / WorkerPool
                        ↓
Domain Layer:       Agent / SubAgentHandle / DeepResearchOrchestrator
                        ↓
Repository Layer:   TaskRepository / SessionRepository / FileMemory / HybridMemoryIndex
                        ↓
Infrastructure:     DatabaseManager / AgentBus / AuthManager / LLMProvider
```

**Missing layers:**
- **No service layer between TUI and Session** — `tui.py` directly creates and manages `Session` instances, handles WebSocket events, and manipulates session state.
- **No abstraction for LLM providers** — `llm.py` has a single `LLMProvider` class with if/else branching for Gemini vs OpenRouter. No `BaseProvider` interface.
- **No abstraction for memory backends** — `HybridMemoryManager` and old `Memory` are both concrete classes with no shared interface.

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 3.1 | **No LLM provider interface** — adding a new provider (Anthropic, local model) requires modifying `LLMProvider.generate()` with more if/else branches. | High |
| 3.2 | **No memory backend interface** — `HybridMemoryManager` and `Memory` have completely different APIs. Switching backends requires changing all callers. | Medium |
| 3.3 | **TUI bypasses service layer** — `NexusApp` directly accesses `session_manager`, `Session.send()`, and `worker_pool`. No controller or presenter layer. | Medium |
| 3.4 | **Server creates agents directly** — `server_websocket()` instantiates `Agent()` and `Session()` directly instead of using a factory or service. | Medium |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Define `BaseLLMProvider` protocol with `async generate()` — refactor `LLMProvider` into `GeminiProvider`, `OpenRouterProvider`. | M |
| P2 | Define `BaseMemoryBackend` protocol — unify `HybridMemoryManager` and `Memory` behind a common interface. | M |
| P3 | Create a `SessionController` in `interfaces/` — move session lifecycle management out of `tui.py`. | L |
| P4 | Add a `WorkerFactory` — encapsulate agent + session creation for both server and CLI. | M |

---

## 4. Technical Debt Inventory

### Current State

**Zero TODOs/FIXMEs/HACKs in source code** — this is excellent. The codebase is clean.

**Documented debt (from code analysis):**

| # | Item | Location | Type |
|---|------|----------|------|
| 4.1 | Old `Memory` class coexists with `HybridMemoryManager` | `memory/memory.py` | Legacy code |
| 4.2 | Compat shims still exist for 6 refactored modules | `tools/registry.py`, `widgets/theme.py`, `widgets/messages.py`, `infrastructure/db.py`, `infrastructure/utils.py`, `memory/memory_index.py` | Migration debt |
| 4.3 | `task_repo.py` imports `TaskStatus` from `llm/models.py` with `# noqa: E402 — avoid circular import` | `infrastructure/db/task_repo.py:102` | Circular dependency workaround |
| 4.4 | `session_repo.py` imports `TaskStatus` from `llm/models.py` with `# noqa: E402 — avoid circular import` | `infrastructure/db/session_repo.py:118` | Circular dependency workaround |
| 4.5 | `tools/registry/policy.py` imports from `core.py` with delayed import | `tools/registry/policy.py:66` | Circular dependency workaround |
| 4.6 | `tui.py` has 29 import statements | `interfaces/tui.py` | God object |
| 4.7 | `register_all.py` is 728 lines of repetitive registrations | `tools/register_all.py` | Boilerplate |
| 4.8 | `server.py` lifespan creates singletons inline | `server/server.py:29-59` | Missing DI |
| 4.9 | `DeepResearchOrchestrator` is a singleton (`deep_research_orchestrator`) | `core/orchestration.py:193` | Global state |
| 4.10 | `NexusSDK` is a global singleton (`sdk`) | `server/sdk.py:220` | Global state |
| 4.11 | `TelemetryManager` uses `logging.getLogger()` which captures all module logs | `infrastructure/telemetry.py:59` | Side effect |
| 4.12 | `CompactionPipeline._summarize_old_messages` uses heuristic summary, not LLM | `memory/compaction.py:152` | Incomplete feature |
| 4.13 | `HybridMemoryIndex` opens a new SQLite connection on every search/index call | `memory/index/index.py:146,241,389,414` | Performance |

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 4.1 | **6 compat shims** add confusion — new developers may import from the wrong location. | Low |
| 4.2 | **3 documented circular import workarounds** indicate the module graph has cycles. | Medium |
| 4.3 | **Heuristic summarization** in compaction means context recovery is lossy at level 3. | Medium |
| 4.4 | **SQLite connection per operation** in memory index — no connection pooling. | Medium |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Remove all 6 compat shims — update imports to use new subpackage paths. | S |
| P2 | Fix circular imports: move `TaskStatus` to a shared `core/types.py` module. | S |
| P3 | Replace heuristic summarization with LLM-based summarization (behind a flag). | M |
| P4 | Add connection pooling to `HybridMemoryIndex` — reuse a single connection per operation batch. | S |

---

## 5. Scalability Bottlenecks

### Current State

| Component | Current Limit | At 10x | At 100x |
|-----------|--------------|--------|---------|
| **SQLite (tasks)** | Single file, WAL mode | Write contention on task status updates | Connection pool exhaustion |
| **SQLite (memory index)** | Single file, FTS5 + sqlite-vec | Brute-force vector search becomes slow | Index rebuild takes minutes |
| **NATS JetStream** | Single server | JetStream memory usage grows with pending tasks | Partitioning needed |
| **LLM API** | Rate-limited by provider | Need request queuing + token budget management | Need multi-provider load balancing |
| **WebSocket** | Single server process | Connection limit (~10K per process) | Need horizontal scaling + sticky sessions |
| **Worker pool** | In-process asyncio | CPU-bound tasks block event loop | Need multiprocessing or external workers |
| **Memory system** | Embedding API rate limits | Embedding queue with batching needed | Need dedicated embedding service |

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 5.1 | **SQLite write contention** — all task status updates go through a single SQLite file. With concurrent workers, this becomes a bottleneck. | High |
| 5.2 | **No LLM rate limiting** — `LLMProvider.generate()` has retry but no rate limit. Burst requests can hit provider quotas. | High |
| 5.3 | **In-process worker pool** — `WorkerPool` runs asyncio tasks in the same process. CPU-bound work (code review, AST analysis) blocks the event loop. | Medium |
| 5.4 | **No WebSocket horizontal scaling** — sessions are bound to a single server process. No Redis/pub-sub for cross-process events. | Medium |
| 5.5 | **Memory index brute-force fallback** — when sqlite-vec fails, loads all embeddings into memory with an OOM guard. At 100K+ chunks, this is impractical. | Medium |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Add LLM rate limiter — token bucket per provider, configurable in settings. | M |
| P2 | Migrate task DB to PostgreSQL for concurrent write support (or use WAL mode with connection pooling). | L |
| P3 | Add WebSocket horizontal scaling via Redis pub-sub for cross-process session events. | L |
| P4 | Move CPU-bound work to a process pool (already partially done with `run_in_executor`). | M |
| P5 | Add embedding batching — collect multiple texts and call `embed_batch()` instead of individual `embed()`. | S |

---

## 6. Single Points of Failure

### Current State

```
                    ┌──────────────┐
                    │   CLI / TUI  │
                    └──────┬───────┘
                           │ WebSocket / HTTP
                    ┌──────▼───────┐
                    │  FastAPI     │ ← SPOF: process crash kills all sessions
                    │  Server      │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼───┐ ┌─────▼─────┐
       │   NATS      │ │ DB   │ │ LLM API   │
       │  JetStream  │ │SQLite│ │ Gemini/OR │
       └─────────────┘ └──────┘ └───────────┘
              │                        │
       ┌──────▼──────┐          ┌─────▼─────┐
       │   Worker    │          │  External  │
       │   Pool      │          │  APIs      │
       └─────────────┘          └───────────┘
```

| # | Component | Impact if Failed | Recovery |
|---|-----------|-----------------|----------|
| 6.1 | **NATS JetStream** | All task orchestration stops. Workers can't receive tasks, results can't be stored. | Manual restart. Tasks in-flight are lost. |
| 6.2 | **FastAPI Server** | All WebSocket connections drop. CLI/TUI can't connect. | Auto-reconnect in TUI (exponential backoff, 6 retries). |
| 6.3 | **SQLite (tasks)** | Task status can't be read/written. | File-based, can be backed up. No replication. |
| 6.4 | **SQLite (memory index)** | Memory recall fails. | Can be rebuilt from files (design is correct). |
| 6.5 | **LLM API (Gemini)** | Agent can't generate responses. | OpenRouter fallback exists. No local fallback. |
| 6.6 | **Auth keystore** | API endpoints reject all requests. | Manual key re-initialization. |

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 6.1 | **NATS is the critical SPOF** — no clustering, no failover. If NATS goes down, the entire task pipeline stops. | Critical |
| 6.2 | **No LLM fallback to local model** — if both Gemini and OpenRouter fail, the agent is dead. The embedding system has a hash fallback, but the main LLM doesn't. | High |
| 6.3 | **Server process is not supervised** — no systemd unit, no Docker health check, no process manager mentioned. | Medium |
| 6.4 | **No data replication** — SQLite files are local. No backup strategy documented. | Medium |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Add a local LLM fallback (e.g., Ollama) — `LLMProvider` should have a 3-tier fallback: Gemini → OpenRouter → local. | L |
| P2 | Document NATS high-availability setup (clustered mode) or add a file-based fallback for single-node deployments. | M |
| P3 | Add a systemd unit file and Docker health check for the server process. | S |
| P4 | Add SQLite WAL mode + periodic backup to `~/.nexusagent/backups/`. | S |

---

## 7. Data Flow Patterns

### Current State

**Primary data flow (unidirectional, good):**

```
User Input (CLI/TUI/Web)
    ↓
Session.send()
    ↓
[Memory Recall] → HybridMemoryManager → context injection
    ↓
Agent.run_agent_task()
    ↓
LLMProvider.generate() → streaming tokens
    ↓
Tool Execution (if tool_calls)
    ↓
Tool Results → Session._handle_update()
    ↓
Event Stream → WebSocket → TUI
    ↓
[Memory Write] → HybridMemoryManager.flush()
```

**NATS task flow (bidirectional, potential feedback loop):**

```
Server.create_task() → bus.publish("tasks.submit")
    ↓
NATS JetStream → NexusWorker.handle_task()
    ↓
WorkerPool.spawn() → SubAgentHandle
    ↓
run_agent_task() → bus.put_result(task_id, result)
    ↓
Server.get_task_result() → bus.get_result(task_id)
```

**Potential feedback loops:**
1. **Sub-agent spawning** — `spawn_subagent` tool creates a `SubAgentHandle` which runs `run_agent_task()` which can call `spawn_subagent` again (bounded by `max_depth`). This is correctly bounded but could create deep call stacks.
2. **Memory flush on compaction** — `pre_compaction_flush` writes to memory, which triggers re-indexing, which reads from memory. The async embedding chain could race with the sync flush.
3. **NATS worker → agent → NATS** — a worker processes a task via NATS, the agent calls tools, and the result goes back through NATS. If the agent spawns sub-agents that also use NATS, this creates a fan-out pattern that could overwhelm NATS.

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 7.1 | **No backpressure on NATS** — if tasks arrive faster than workers can process them, JetStream memory grows unbounded. | High |
| 7.2 | **Sub-agent depth is bounded but not monitored** — `max_depth=3` is the limit, but there's no warning when approaching it. | Low |
| 7.3 | **Memory flush race condition** — `pre_compaction_flush` is async but `CompactionPipeline.compact()` is sync. The flush could still be running when compaction completes. | Medium |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Add NATS JetStream max-age and max-bytes limits to prevent unbounded memory growth. | S |
| P2 | Add a `CompactionCoordinator` — make the entire flush→compact→re-index sequence atomic. | M |
| P3 | Add sub-agent depth metrics to the status bar / telemetry. | S |

---

## 8. Configuration Complexity

### Current State

**Config schema** (from `config.py` — 8 Pydantic models):

```python
ConfigSchema
├── ServerConfig      (api_port, api_host, reload, db_path, nats_url, ...)
├── ClientConfig      (api_key, ...)
├── AuthConfig        (master_secret_path, keystore_path, salt_path, kdf_iterations)
├── AgentConfig       (primary_provider, default_model, gemini_model, openrouter_*,
│                      max_conversation_history, compaction_enabled, yolo, ...)
├── PromptConfig      (max_chain_depth, chat_file_injection, ...)
├── LoggingConfig     (log_level)
└── HooksConfig       (hooks_enabled)
```

**Total config fields:** ~30+ options across 7 sections.

**Loading:** 3-tier (yaml → env vars → Pydantic defaults). Env var format: `NEXUS_AGENT__DEFAULT_MODEL=...` (double underscore = nested).

**Documentation:** Config schema is well-documented with Pydantic docstrings. The `config/nexusagent.yaml` file provides a reference template.

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 8.1 | **Config is a global singleton** — `settings = load_config()` at module level. Can't have different configs for different components in the same process. | Medium |
| 8.2 | **No config validation on startup** — invalid config values (e.g., non-existent model name) are only caught when the value is first used. | Medium |
| 8.3 | **Env var naming is confusing** — `NEXUS_AGENT__DEFAULT_MODEL` uses double underscore for nesting, but `NEXUS` prefix doesn't match the `nexusagent` package name. | Low |
| 8.4 | **No config hot-reload** — changing the YAML file requires server restart. | Low |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Add startup validation — check that the configured model name is valid for the configured provider. | S |
| P2 | Add config file watching — auto-reload on YAML change (with debounce). | M |
| P3 | Document the env var naming convention in `docs/adrs/`. | S |

---

## 9. Error Recovery

### Current State

**Well-handled:**
- **LLM calls** — `retry_with_backoff` decorator with 3 attempts, exponential backoff, jitter
- **NATS operations** — retry in `put_result()` and `subscribe()`
- **Circuit breakers** — `_agent_breaker` and `_nats_breaker` in worker.py protect against cascading failures
- **Task reaper** — `TaskReaper` detects zombie PROCESSING tasks and marks them FAILED
- **WebSocket reconnection** — TUI has exponential backoff retry (6 attempts)
- **Auth failures** — fail-closed with clear error messages
- **Memory flush failures** — caught and logged, don't crash compaction

**Poorly handled:**
- **SQLite errors** — no retry, no circuit breaker. A locked DB will raise `OperationalError`.
- **Tool execution** — errors are returned as strings (e.g., `"Error: ..."`), not structured. The agent can't distinguish between "tool failed" and "tool returned error text".
- **Memory index corruption** — no integrity check or auto-rebuild on corruption.

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 9.1 | **No SQLite retry** — `OperationalError: database is locked` will propagate up and crash the request. | High |
| 9.2 | **Tool errors are strings** — the agent can't programmatically distinguish tool failures from normal output. | Medium |
| 9.3 | **No graceful degradation for memory** — if the embedding API is down, new memory entries are indexed with hash embeddings (low quality), but there's no warning to the user. | Low |
| 9.4 | **Worker crash recovery** — if `NexusWorker.handle_task()` raises an unhandled exception, the task stays PROCESSING forever (only reaped after 1 hour). | Medium |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Add `retry_with_backoff` to all SQLite operations in repositories. | S |
| P2 | Reduce task reaper interval from 60s to 10s, or add a heartbeat mechanism for active tasks. | S |
| P3 | Create a `ToolResult` dataclass with `success: bool, output: str, error: str | None` — replace string-based error returns. | M |
| P4 | Add SQLite integrity check on startup (`PRAGMA integrity_check`). | S |

---

## 10. Extension Points

### Current State

**Easy to extend:**

| Extension Point | How | Example |
|----------------|-----|---------|
| **New tool** | Create function + `@register_tool` decorator | `tools/git.py` — 10 git tools added this way |
| **New hook** | `register_hook(event, callback)` | Pre/post execution hooks |
| **New skill** | Drop a directory with `SKILL.md` in `~/.nexusagent/skills/` | Plugin system |
| **New theme** | Add entry to `ALL_THEMES` dict | 7 themes already |
| **New TUI widget** | Extend Textual's `Static` or `Container` | 6 message widget types |
| **New LLM provider** | Add elif branch in `LLMProvider.get_active_model()` | Gemini + OpenRouter |

**Hard to extend:**

| Extension Point | Why |
|----------------|-----|
| **New interface** (Slack, Discord) | No interface abstraction — must reimplement session management |
| **New memory backend** | No `BaseMemoryBackend` interface |
| **New task queue** (Redis, SQS) | NATS is hardcoded in `AgentBus` |
| **New auth method** (OAuth, JWT) | Fernet keystore is the only option |

### Problems

| # | Problem | Severity |
|---|---------|----------|
| 10.1 | **NATS is not swappable** — `AgentBus` is a concrete class with no interface. Replacing it requires changing all callers. | Medium |
| 10.2 | **Tool registration is centralized** — `register_all.py` must be edited for every new tool. Auto-discovery would be better. | Low |
| 10.3 | **No plugin manifest** — skills are discovered by directory scanning, but there's no version compatibility check or dependency resolution. | Low |

### Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| P1 | Define `BaseTaskBus` protocol — extract the NATS implementation behind an interface. | M |
| P2 | Add auto-discovery to `register_all.py` — scan `tools/` for decorated functions. | S |
| P3 | Add a plugin manifest format — `plugin.yaml` with version, dependencies, and compatibility. | M |

---

## Summary Scorecard

| Area | Score | Notes |
|------|-------|-------|
| **Module Dependencies** | 7/10 | Clean topology, but wide `settings` fan-in and 5 global singletons |
| **Coupling & Cohesion** | 6/10 | Good separation in infrastructure, but `session.py` and `server.py` are god objects |
| **Abstraction Layers** | 6/10 | Clear 3-tier architecture in server, but missing LLM provider and memory interfaces |
| **Technical Debt** | 8/10 | Zero TODOs, clean code, but 6 compat shims and 3 circular import workarounds |
| **Scalability** | 5/10 | SQLite + single-process + no rate limiting = limited headroom |
| **Single Points of Failure** | 4/10 | NATS is critical SPOF, no LLM fallback to local, no HA |
| **Data Flow** | 7/10 | Unidirectional primary flow, bounded sub-agents, but no backpressure |
| **Configuration** | 7/10 | Well-structured Pydantic schema, 3-tier loading, but global singleton |
| **Error Recovery** | 7/10 | Good retry/circuit breaker coverage, but no SQLite retry |
| **Extension Points** | 7/10 | Easy tool/hook/skill addition, but hard to swap core infrastructure |

**Overall: 6.6/10** — A well-engineered system with clean architecture in the areas that matter most for correctness (memory, compaction, tool policy, resilience). The primary gaps are in scalability (SQLite, single-process) and infrastructure flexibility (NATS coupling, no DI). These are acceptable tradeoffs for a single-node AI agent platform but would need addressing for multi-tenant or high-throughput deployments.

---

## Priority Roadmap

### Phase 1 — Critical Fixes (1-2 weeks)
1. Add SQLite retry to all repository operations (§9, P1)
2. Add LLM rate limiter per provider (§5, P1)
3. Add local LLM fallback (Ollama) (§6, P1)
4. Remove 6 compat shims (§4, P1)

### Phase 2 — Architecture Improvements (2-4 weeks)
5. Define `BaseLLMProvider` protocol, split providers (§3, P1)
6. Define `BaseMemoryBackend` protocol (§3, P2)
7. Extract `SessionRunner` from `session.py` (§2, P1)
8. Split `server/server.py` into routes + websocket + lifespan (§2, P2)
9. Add `BaseTaskBus` protocol for NATS (§10, P1)

### Phase 3 — Scalability (4-8 weeks)
10. Migrate task DB to PostgreSQL or add connection pooling (§5, P2)
11. Add WebSocket horizontal scaling via Redis (§5, P3)
12. Add NATS JetStream backpressure limits (§7, P1)
13. Add embedding batching (§5, P5)

### Phase 4 — Polish (1-2 weeks)
14. Auto-discover tools in `register_all.py` (§10, P2)
15. Add startup config validation (§8, P1)
16. Add systemd unit + Docker health check (§6, P3)
17. Replace heuristic summarization with LLM-based (§4, P3)
