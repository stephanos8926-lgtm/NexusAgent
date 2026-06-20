# NexusAgent Codebase — Semantic Index

> Auto-generated on 2026-07-22. Updated after memory system v2 completion + refactoring phases 1-7 + security hardening.
> Read-only analysis of `src/nexusagent/`.

---

## 1. Architecture Overview

**NexusAgent** is a production-grade AI coding agent platform. It combines an LLM-powered agent (via `deepagents` / LangGraph) with a NATS-backed task orchestration system, a Textual TUI, a FastAPI WebSocket server, and a hybrid file+vector memory system (v2).

### Core Components

| Layer | Component | File |
|-------|-----------|------|
| **CLI** | Click-based CLI (`run`, `session`, `memory`, version flags) | `interfaces/cli.py` |
| **TUI** | Textual terminal UI with themes, streaming, widgets | `interfaces/tui/` |
| **API** | FastAPI server with WebSocket sessions | `server/` |
| **Agent** | LLM agent with policy-aware tool access via `deepagents` | `core/agent.py` |
| **Session** | Interactive conversation lifecycle, event streaming | `core/session/` |
| **Worker** | NATS-subscribed task processor with circuit breakers | `core/worker/` |
| **Sub-Agent** | Spawnable isolated workers with depth-bounded nesting | `core/subagent.py` |
| **Orchestration** | LangGraph research workflow (plan→refine→execute→synthesize) | `core/graph.py` + `core/orchestration.py` |
| **Memory v2** | Hybrid file+vector memory with dream cycle, DAG, auto-extraction | `memory/` |
| **Compaction** | Graduated context window compaction with DAG | `memory/compaction.py` |
| **Bus** | NATS JetStream messaging + KV result store | `infrastructure/bus.py` |
| **DB** | Async SQLite via SQLAlchemy (tasks, results, sessions, messages) | `infrastructure/db/` |
| **SDK** | High-level client for task submit/status/result | `server/sdk.py` |
| **Version** | Single source of truth via `importlib.metadata` | `version.py`, `server/version.py` |
| **Auth** | Fernet-encrypted keystore with PBKDF2 master secret | `infrastructure/auth.py` + `infrastructure/api_auth.py` |
| **LLM** | Multi-provider bridge (Gemini, OpenRouter) with retry | `llm/llm.py` |
| **Tools** | 30+ registered tools across 7 categories | `tools/` |
| **Config** | Pydantic settings with YAML + env var overrides | `infrastructure/config.py` |
| **Models** | Pydantic schemas for tasks, results, events, contracts | `llm/models.py` |
| **Telemetry** | Structured logging + in-app log viewer | `infrastructure/telemetry.py` |
| **Web UI** | Gradios-based control center | `interfaces/web_ui.py` |
| **Rate Limit** | Token-bucket rate limiting middleware | `infrastructure/rate_limit.py` |

---

## 2. Module Map — Every `.py` in `src/nexusagent/`

| File | Description |
|------|-------------|
| `__init__.py` | Package init |
| `version.py` | `get_version()`, `parse_version()`, `is_compatible()` — single source of truth |
| `skills.py` | Skill loading from `~/.hermes/skills/` with YAML frontmatter |
| `task_reaper.py` | `TaskReaper` — background loop for stale PROCESSING tasks |
| **core/** | |
| `core/__init__.py` | Re-exports from subpackages |
| `core/agent.py` | `Agent` class wrapping `create_deep_agent` with role-based tool access |
| `core/orchestration.py` | `DeepResearchOrchestrator` — multi-phase research |
| `core/graph.py` | LangGraph research graph (plan→refine→execute→synthesize) |
| `core/subagent.py` | `SubAgentHandle` — control interface for spawned workers |
| `core/session/session.py` | `Session` — interactive conversation lifecycle, events, compaction, approvals |
| `core/session/manager.py` | `SessionManager` — cache with memory_dir support |
| `core/session/helpers.py` | `_extract_agent_response`, env context, git info |
| `core/worker/worker.py` | `NexusWorker` — NATS subscriber, task lifecycle |
| `core/worker/pool.py` | `WorkerPool` — semaphore-bounded concurrent workers |
| `core/worker/handler.py` | `_run_agent_task`, `_run_research_workflow`, circuit breakers |
| **tools/** | |
| `tools/register_all.py` | Registers all 30+ tools |
| `tools/tool_specs.py` | TOOL_SPECS data (30+ tool definitions) |
| `tools/fs.py` | Filesystem tools (read/write/list) |
| `tools/fs_base.py` | Shared fs utilities (path resolution, workspace jail) |
| `tools/editor.py` | `edit_file()` — surgical line-range editing |
| `tools/git.py` | Git tools (status/diff/log/commit/branch) |
| `tools/shell.py` | Shell execution tools |
| `tools/research.py` | Web research tools |
| `tools/code_search.py` | Code search (ast-grep) |
| `tools/test_runner.py` | Test execution |
| `tools/patch.py` | Unified diff application |
| `tools/write_todos.py` | Todo management |
| `tools/registry/core.py` | `register_tool`, `get_tool_info`, `list_all_tools` |
| `tools/registry/policy.py` | `ROLE_MANIFESTS`, policy enforcement |
| `tools/registry/search.py` | `tool_search`, fuzzy/category search |
| `tools/registry/types.py` | `ToolInfo` dataclass |
| `tools/code_review/review_code.py` | Code review orchestrator |
| `tools/code_review/models.py` | `Issue`, `ReviewResult` |
| `tools/code_review/checks/*.py` | Security, bugs, style, performance, AST checks |
| **memory/** | |
| `memory/hybrid_memory.py` | `HybridMemoryManager` — top-level file + index interface |
| `memory/memory_files.py` | `FileMemory` — canonical file-based memory with YAML frontmatter |
| `memory/memory_index.py` | Compat shim → `index/` subpackage |
| `memory/compaction.py` | `CompactionPipeline` — 4-level graduated compaction + DAG |
| `memory/dag.py` | `SummaryDAG` — hierarchical context compression (depth-0→1→2) |
| `memory/dream.py` | `DreamCycle` — 4-phase background consolidation daemon |
| `memory/extraction.py` | `MemoryExtractor` — regex-based auto-extraction |
| `memory/git_ops.py` | `MemoryGitOps` — auto-commit after memory writes |
| `memory/rate_limiter.py` | `MemoryRateLimiter` — token-bucket rate limiting |
| `memory/consolidation.py` | `ConsolidationEngine` — duplicate/contradiction detection |
| `memory/refinement.py` | `LLMRefinement` — LLM synthesis of observations |
| `memory/memory_item.py` | `MemoryItem` model |
| `memory/memory_bank.py` | `Memory` — scoped SQLite bank (legacy) |
| `memory/memory_manager.py` | `MemoryManager` — lifecycle manager (legacy) |
| `memory/index/index.py` | `HybridMemoryIndex` — FTS5 + sqlite-vec hybrid search |
| `memory/index/embeddings.py` | `EmbeddingProvider` — Gemini → local → hash fallback |
| **interfaces/** | |
| `interfaces/cli.py` | Click CLI: `run`, `session`, `memory`, version flags |
| `interfaces/web_ui.py` | Gradio web UI |
| `interfaces/tui/app.py` | `NexusApp` — main Textual TUI application |
| `interfaces/tui/websocket.py` | WebSocket loop, version check, approval relay |
| `interfaces/tui/streaming.py` | Event handling, slash commands, help |
| `interfaces/tui/input.py` | Chat input handling |
| `interfaces/tui/formatters.py` | Re-exports from `tui_formatters.py` |
| `interfaces/tui_widgets.py` | SpinnerLabel, modals, SIGWINCH |
| `interfaces/tui_formatters.py` | `render_markdown`, all formatters |
| **server/** | |
| `server/server.py` | `create_app()` + lifespan + `run()` |
| `server/routes.py` | REST endpoints (`/tasks`, `/health`, `/version`, etc.) |
| `server/websocket.py` | `session_websocket()` handler |
| `server/sdk.py` | `NexusSDK` — `SERVER_VERSION`, `MIN_CLIENT_VERSION` |
| `server/version.py` | Server version via `importlib.metadata` |
| `server/__main__.py` | Entry point for `python3 -m nexusagent.server` |
| **infrastructure/** | |
| `infrastructure/config.py` | `ConfigSchema` — Pydantic settings, 3-tier loading |
| `infrastructure/bus.py` | `AgentBus` — NATS JetStream client |
| `infrastructure/auth.py` | `AuthManager` — Fernet keystore, PBKDF2 |
| `infrastructure/api_auth.py` | FastAPI API key verification |
| `infrastructure/rate_limit.py` | Rate limiting middleware |
| `infrastructure/prompt_loader.py` | NEXUS.md loader with `@file` chain resolution |
| `infrastructure/template_includes.py` | `@file` chain resolution, circular detection |
| `infrastructure/telemetry.py` | `TelemetryManager` — rotating file logging |
| `infrastructure/db/base.py` | DeclarativeBase |
| `infrastructure/db/models.py` | TaskModel, ResultModel, SessionModel, MessageModel |
| `infrastructure/db/manager.py` | `DatabaseManager` — engine + session factory |
| `infrastructure/db/task_repo.py` | `TaskRepository` — CRUD + cancel/retry/list |
| `infrastructure/db/session_repo.py` | `SessionRepository` — CRUD + fork/rename/delete |
| `infrastructure/utils/retry.py` | `retry_with_backoff`, `retry_on_false` |
| `infrastructure/utils/circuit.py` | `CircuitBreaker` — async context manager + decorator |
| **llm/** | |
| `llm/llm.py` | `LLMProvider` — multi-provider bridge |
| `llm/models.py` | Pydantic models: `TaskSchema`, `TaskContract`, `ResultSchema`, `AgentEvent`, `ImageAttachment` |
| **hooks/** | |
| `hooks/__init__.py` | `HookManager`, `HookEvent`, `register_hook` |
| `hooks/builtins.py` | Built-in hooks: session_init, post_tool, error, subagent |
| **widgets/** | |
| `widgets/chat_input.py` | `ChatInput` — multiline TextArea with submit/history |
| `widgets/status.py` | `StatusBar` — responsive bottom bar |
| `widgets/messages/user.py` | `UserMessage` widget |
| `widgets/messages/assistant.py` | `AssistantMessage` — streaming + markdown |
| `widgets/messages/tool.py` | `ToolCallMessage` — collapsible |
| `widgets/messages/app.py` | `AppMessage` — system messages |
| `widgets/messages/error.py` | `ErrorMessage` |
| `widgets/messages/welcome.py` | `WelcomeBanner` |
| `widgets/theme/colors.py` | `ThemeColors` — 7 themes |
| `widgets/theme/registry.py` | CSS vars, `register_themes` |

---

## 3. Data Flow — User Message Through the System

### Path A: Interactive TUI Session (WebSocket)

```
User types message in TUI
  → ChatInput.action_submit()                     [interfaces/tui/input.py]
  → NexusApp.on_chat_input_submitted()            [interfaces/tui/streaming.py]
  → ws_loop → WebSocket send                      [interfaces/tui/websocket.py]
  → server/websocket.py: session_websocket()
      → create Agent(role="full")
      → session_manager.get_or_create()           [core/session/manager.py]
      → asyncio.gather(send_events, receive_messages)

Session.send():                                     [core/session/session.py]
  1. Fire session_init hooks
  2. @file injection
  3. Emit ThinkingEvent
  4. Store user message in DB
  5. Build messages: [System(prompt+context+memory), ..., HumanMessage]
  6. Compaction check → CompactionPipeline
  7. agent({"messages": messages})
  8. Handle streamed chunks (tokens, tool_calls, tool_results)
  9. ResponseEvent + store assistant msg in DB
  10. hybrid_memory.remember()                    [memory/hybrid_memory.py]
  11. Schedule _run_extraction()                  [memory/extraction.py]

Events flow back via session._event_queue → WebSocket → TUI _handle_event()
```

### Path B: CLI Task Submission (NATS)

```
nexus-client submit "task"
  → cli.py → sdk.submit_task()                    [server/sdk.py]
  → AgentBus.publish("tasks.submit")              [infrastructure/bus.py]
  → NexusWorker.handle_task()                     [core/worker/worker.py]
  → _execute_agent_logic()                        [core/worker/handler.py]
      ├─ research → create_research_graph()       [core/graph.py]
      └─ code → Agent.__call__()                  [core/agent.py]
  → Result stored in DB + NATS KV
  → SDK polls KV for result
```

### Path C: Memory v2 Flow

```
Write (after each turn):
  Session.send() → hybrid_memory.remember()
    → MemoryRateLimiter.acquire()
    → FileMemory.write_entry() → bank/slug-timestamp.md
    → MemoryGitOps.auto_commit() → git add + commit
    → HybridMemoryIndex.async_index_file()
    → Fire-and-forget: MemoryExtractor.extract()

Recall (before agent call):
  Session.send() → hybrid_memory.get_memory_context(query)
    → HybridMemoryIndex.search(query)
    → FTS5 + sqlite-vec → RRF fusion
    → Formatted as SystemMessage

Background (DreamCycle):
  Every N turns → DreamCycle.run()
    → Phase 1: Scan all memory files
    → Phase 2: LLMRefinement.synthesize() → insights
    → Phase 3: Consolidate (dedup, prune, resolve contradictions)
    → Phase 4: Trim index, trim MEMORY.md
```

---

## 4. Key Classes and Functions

### Session (`core/session/session.py`)
- `Session` — conversation lifecycle, event streaming, compaction, approval gates
  - `send(user_message, images)` — full message processing pipeline
  - `event_stream()` — async generator yielding events
  - `approve(call_id, approved)` — approval gate
  - `interrupt()` — cancellation flag

### HybridMemoryManager (`memory/hybrid_memory.py`)
- `remember(content, type, description)` — write + index
- `get_memory_context(query)` — search + format for prompt injection
- `flush(session_summary)` — pre-compaction save
- `close()` — resource cleanup

### FileMemory (`memory/memory_files.py`)
- `write_entry()` — creates topic files with YAML frontmatter
- `append_daily_log()` — appends to `memory/YYYY-MM-DD.md`

### DreamCycle (`memory/dream.py`)
- `run()` — 4-phase consolidation (scan → patterns → consolidate → trim)

### SummaryDAG (`memory/dag.py`)
- `add_leaf()` — add conversation message
- `compress()` — promote depth-0 → depth-1 → depth-2

### CompactionPipeline (`memory/compaction.py`)
- `should_compact()` — token threshold check
- `compact()` — 4-level graduated compaction with DAG

### AgentBus (`infrastructure/bus.py`)
- `publish(subject, message)` — JSON-serialized
- `subscribe(subject, callback)` — with 3x retry

### NexusWorker (`core/worker/worker.py`)
- `handle_task()` — parse, DB update, execute, result storage
- `_execute_agent_logic()` — routes research vs coding

### NexusApp (`interfaces/tui/app.py`)
- `compose()` — TUI layout
- `on_mount()` — theme setup, WebSocket preflight version check

---

## 5. Test Coverage

### Test Files (52 total)

| Test File | Covers |
|-----------|--------|
| `test_agent_events.py` | `llm/models.py` — AgentEvent serialization |
| `test_bus.py` | `infrastructure/bus.py` |
| `test_cli_run.py` | `interfaces/cli.py` — `run` command |
| `test_cli_preflight.py` | CLI version preflight |
| `test_cli_memory.py` | CLI memory commands |
| `test_compaction.py` | `memory/compaction.py` |
| `test_config.py` | `infrastructure/config.py` |
| `test_db_sessions.py` | `infrastructure/db/` — SessionRepository |
| `test_e2e_production.py` | End-to-end production flow |
| `test_graph.py` | `core/graph.py` — Research graph structure |
| `test_graph_nodes.py` | `core/graph.py` — Individual node execution |
| `test_hooks.py` | `hooks/__init__.py` |
| `test_image_input.py` | `llm/models.py` — ImageAttachment |
| `test_memory.py` | `memory/` — Memory/MemoryManager |
| `test_memory_files.py` | `memory/memory_files.py` |
| `test_memory_index.py` | `memory/index/` — HybridMemoryIndex |
| `test_memory_tools.py` | Memory-related tools |
| `test_memory_e2e.py` | Memory system E2E (17 tests) |
| `test_memory_dream.py` | `memory/dream.py` — DreamCycle |
| `test_memory_extraction.py` | `memory/extraction.py` |
| `test_memory_ttl.py` | Memory TTL enforcement |
| `test_memory_linking.py` | Memory linking |
| `test_memory_provenance.py` | Memory provenance tracking |
| `test_memory_contradiction.py` | Contradiction detection |
| `test_memory_rate_limit.py` | `memory/rate_limiter.py` |
| `test_memory_workspace_scoped.py` | Workspace-scoped memory |
| `test_memory_self_management.py` | Memory delete/update/list/prune |
| `test_models.py` | `llm/models.py` — Pydantic schemas |
| `test_orchestration.py` | `core/orchestration.py` |
| `test_sdk.py` | `server/sdk.py` |
| `test_sdk_version.py` | SDK version |
| `test_server.py` | `server/` — FastAPI endpoints |
| `test_server_version.py` | `/version` endpoint |
| `test_session.py` | `core/session/` — Session lifecycle |
| `test_session_memory.py` | Session + memory integration |
| `test_session_manager.py` | `core/session/manager.py` |
| `test_session_streaming.py` | Session streaming |
| `test_subagent.py` | `core/subagent.py` |
| `test_task_reaper.py` | `task_reaper.py` |
| `test_nats_durable.py` | NATS durability |
| `test_nats_spof.py` | NATS single point of failure |
| `test_singletons.py` | Global singleton pattern |
| `test_skills.py` | `skills.py` |
| `test_version.py` | `version.py` |
| `test_new_tools.py` | New tool registration |
| `tools/test_fs.py` | `tools/fs.py` |
| `tools/test_patch.py` | `tools/patch.py` |
| `tools/test_research.py` | `tools/research.py` |
| `tools/test_shell.py` | `tools/shell.py` |

### Modules with NO test coverage:
- `llm/llm.py` — LLMProvider
- `infrastructure/auth.py` — AuthManager
- `interfaces/tui/app.py` — NexusApp (TUI is hard to test)
- `interfaces/web_ui.py` — Gradio UI
- `memory/refinement.py` — LLMRefinement
- `memory/consolidation.py` — ConsolidationEngine

---

## 6. Known Issues / TODOs

| Location | Issue |
|----------|-------|
| `memory/memory_bank.py` | Legacy SQLite `Memory` class — dead code, only `HybridMemoryManager` is used |
| `memory/memory_manager.py` | Legacy `MemoryManager` — dead code |
| `memory/memory_index.py` | Compat shim — can be cleaned up |
| `tools/registry.py` | Compat shim — can be cleaned up |
| `infrastructure/db.py` | Compat shim — can be cleaned up |
| `infrastructure/utils.py` | Compat shim — can be cleaned up |
| Multiple | Global mutable singletons (settings, sdk, worker_pool, llm, db_manager, etc.) |
| `interfaces/tui/` | No connection retry in TUI WebSocket |
| `core/orchestration.py` | `_fetch()` is a stub — returns None |
| `server/server.py` | No rate limiting on WebSocket message types |
| `infrastructure/bus.py` | KV bucket creation error silently swallowed |
| `llm/llm.py` | No tests for LLM provider |

### Fixed (2026-07-19-22)

| Issue | Resolution |
|-------|-----------|
| Security hardening | 13 critical/high fixes across 4 waves |
| Refactoring | Phases 1-7, 16-17 complete (11 extractions) |
| Memory system v2 | Complete rewrite with file+vector+background consolidation |
| Workspace scoping | Per-session path jail, thread-local memory isolation |
| Version system | `version.py`, `/version` endpoint, CLI preflight |
| Documentation | CODEBASE_MAP, SEMANTIC_INDEX, README, CHANGELOG all updated |
