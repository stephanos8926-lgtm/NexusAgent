# NexusAgent Codebase — Semantic Index

> Auto-generated on 2026-06-11. Read-only analysis of `src/nexusagent/`.

---

## 1. Architecture Overview

**NexusAgent** is a production-grade AI coding agent platform. It combines an LLM-powered agent (via `deepagents` / LangGraph) with a NATS-backed task orchestration system, a Textual TUI, a FastAPI WebSocket server, and a hybrid file+vector memory system.

### Core Components

| Layer | Component | File |
|-------|-----------|------|
| **CLI** | Click-based CLI (`submit`, `run`, `session`) | `cli.py` |
| **TUI** | Textual terminal UI with themes, streaming, widgets | `tui.py` + `widgets/` |
| **API** | FastAPI server with WebSocket sessions | `server.py` |
| **Agent** | LLM agent with policy-aware tool access via `deepagents` | `agent.py` |
| **Session** | Interactive conversation lifecycle, event streaming | `session.py` |
| **Worker** | NATS-subscribed task processor with circuit breakers | `worker.py` |
| **Sub-Agent** | Spawnable isolated workers with depth-bounded nesting | `subagent.py` |
| **Orchestration** | LangGraph research workflow (plan→refine→execute→synthesize) | `graph.py` + `orchestration.py` |
| **Memory** | Hybrid file-based + SQLite FTS5/vec memory system | `memory.py`, `memory_files.py`, `memory_index.py` |
| **Compaction** | Graduated context window compaction pipeline | `compaction.py` |
| **Bus** | NATS JetStream messaging + KV result store | `bus.py` |
| **DB** | Async SQLite via SQLAlchemy (tasks, results, sessions, messages) | `db.py` |
| **SDK** | High-level client for task submit/status/result | `sdk.py` |
| **Auth** | Fernet-encrypted keystore with PBKDF2 master secret | `auth.py` + `api_auth.py` |
| **LLM** | Multi-provider bridge (Gemini, OpenRouter) with retry | `llm.py` |
| **Tools** | 25+ registered tools across 7 categories | `tools/` |
| **Config** | Pydantic settings with YAML + env var overrides | `config.py` |
| **Models** | Pydantic schemas for tasks, results, events, contracts | `models.py` |
| **Telemetry** | Structured logging + in-app log viewer | `telemetry.py` |
| **Web UI** | Gradio-based control center (alternative to TUI) | `web_ui.py` |

---

## 2. Module Map — Every `.py` in `src/nexusagent/`

| File | Description |
|------|-------------|
| `__init__.py` | Package init |
| `agent.py` | `Agent` class wrapping `create_deep_agent` with role-based tool access and policy enforcement |
| `api_auth.py` | FastAPI API key verification middleware (X-API-Key header → keystore) |
| `auth.py` | `AuthManager` — Fernet-encrypted keystore, PBKDF2 master key derivation |
| `bus.py` | `AgentBus` — NATS JetStream client with pub/sub, KV store, retry logic |
| `cli.py` | Click CLI: `submit`, `run`, `session` (list/resume/fork/rename/delete) commands |
| `compaction.py` | `CompactionPipeline` — 4-level graduated compaction (clear→microcompact→summarize→truncate) |
| `config.py` | `ConfigSchema` — Pydantic settings from YAML + `NEXUS_*` env vars, singleton `settings` |
| `db.py` | `DatabaseManager`, `TaskRepository`, `SessionRepository` — async SQLite via SQLAlchemy |
| `graph.py` | `create_research_graph()` — LangGraph state machine for deep research (plan→refine→execute→synthesize) |
| `llm.py` | `LLMProvider` — multi-provider bridge (Gemini SDK, OpenRouter via OpenAI client) with retry |
| `memory.py` | `Memory` (SQLite+sqlite-vec scoped memory), `MemoryManager`, `HybridMemoryManager` |
| `memory_files.py` | `FileMemory` — file-based canonical memory (MEMORY.md index, daily logs, bank/ entities/) |
| `memory_index.py` | `HybridMemoryIndex` — SQLite FTS5 + sqlite-vec hybrid search with tiered embeddings |
| `models.py` | Pydantic models: `TaskSchema`, `TaskContract`, `ResultSchema`, `AgentEvent` subclasses, `ImageAttachment` |
| `orchestration.py` | `DeepResearchOrchestrator` — multi-phase research workflow with LLM plan/refine/synthesize |
| `prompt_loader.py` | NEXUS.md loader with `@file` chain resolution, circular detection, chat-time injection |
| `sdk.py` | `NexusSDK` — high-level client: submit_task, get_result, wait_for_result, batch, health |
| `server.py` | FastAPI app: REST endpoints (`/tasks`, `/health`, `/workers`, `/tools`) + WebSocket `/sessions/{id}/ws` |
| `session.py` | `Session` (interactive conversation lifecycle, event streaming, compaction, approval gates) + `SessionManager` |
| `subagent.py` | `SubAgentHandle` — control interface for spawned workers (status, cancel, wait, depth tracking) |
| `task_reaper.py` | `TaskReaper` — background loop that marks stale PROCESSING tasks as FAILED |
| `telemetry.py` | `TelemetryManager` — structured logging to rotating file + `LogViewer` widget |
| `tui.py` | `NexusApp` — main Textual TUI application (compose, key bindings, theme switching, help, logs) |
| `utils.py` | `retry_with_backoff`, `retry_on_false`, `CircuitBreaker` (async context manager + decorator) |
| `web_ui.py` | Gradio-based web control center (alternative to TUI) |
| `worker.py` | `NexusWorker` (NATS task subscriber) + `WorkerPool` (semaphore-bounded concurrent workers) |
| `tools/__init__.py` | Tools package init |
| `tools/code_search.py` | `search_code`, `find_symbol`, `find_references` — ripgrep-based code search |
| `tools/fs.py` | `read_file`, `write_file`, `edit_file`, `list_directory`, `read_multiple_files`, `write_multiple_files` |
| `tools/git.py` | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_show`, `git_commit`, `git_checkout_branch`, stash ops |
| `tools/patch.py` | `apply_patch` — unified diff application |
| `tools/register_all.py` | Registers all 25+ tools in the global registry (including `spawn_subagent` orchestration tool) |
| `tools/registry.py` | `ToolInfo`, `_REGISTRY`, `register_tool` decorator, role manifests, policy enforcement, `tool_search` |
| `tools/research.py` | `search_web`, `search_local_docs`, `fetch_url` — web research tools |
| `tools/shell.py` | `run_shell`, `run_shell_streaming` — command execution |
| `tools/test_runner.py` | `run_tests`, `run_single_test` — auto-detect test framework and run |
| `widgets/__init__.py` | Widgets package init |
| `widgets/chat_input.py` | `ChatInput` — multiline TextArea with submit/history/image extraction |
| `widgets/messages.py` | `UserMessage`, `AssistantMessage`, `ToolCallMessage`, `AppMessage`, `ErrorMessage`, `WelcomeBanner` |
| `widgets/status.py` | `StatusBar` — responsive bottom bar (status, CWD, branch, tokens, model, spinner) |
| `widgets/theme.py` | `ThemeColors`, `register_themes` — 4 themes: nexus-dark, catppuccin-mocha, gruvbox-dark, nord |

---

## 3. Data Flow — User Message Through the System

### Path A: Interactive TUI Session (WebSocket)

```
User types message in TUI
  → ChatInput.action_submit()                     [widgets/chat_input.py:62]
  → NexusApp.on_chat_input_submitted()            [tui.py:296]
  → NexusApp.UserInput event posted               [tui.py:309]
  → (external handler) → session.send(content)    [session.py:302]

Session.send():
  1. @file injection (if enabled)                 [session.py:318, prompt_loader.py]
  2. Emit ThinkingEvent                           [session.py:321]
  3. Store user message in DB                     [session.py:324, db.py:269]
  4. Build messages list:
     a. System prompt from NEXUS.md              [session.py:333, prompt_loader.py:134]
     b. Environment context (cwd, git, tools)     [session.py:337, session.py:99]
     c. Hybrid memory context                     [session.py:342, memory.py:409]
     d. Conversation history (last N turns)       [session.py:350]
     e. New HumanMessage (text + images)          [session.py:353, models.py:266]
  5. Compaction check (if enabled)                [session.py:357, compaction.py:64]
     → pre_compaction_flush → memory              [session.py:363, compaction.py:222]
     → CompactionPipeline.compact()               [compaction.py:70]
  6. Stream via agent._inner.astream()            [session.py:389]
     → deepagents LangGraph execution
     → LLM calls (Gemini/OpenRouter)              [llm.py:62]
     → Tool execution (policy-checked)            [tools/registry.py:295]
  7. Handle streamed chunks:
     → AIMessageChunk tokens → accumulate         [session.py:488]
     → tool_call_chunks → tool_call events         [session.py:463]
     → ToolMessage → tool_result events            [session.py:476]
     → response_chunk events (real-time)           [session.py:501]
  8. Final response:
     → ResponseEvent emitted                       [session.py:422]
     → Update conversation history                 [session.py:425]
     → Store assistant message in DB               [session.py:433]
     → Remember in hybrid memory                   [session.py:439]
  9. Errors → ErrorEvent                          [session.py:449]

Events flow back via:
  Session.event_stream() → asyncio.Queue          [session.py:580]
  → WebSocket send_json()                         [server.py:282]
  → TUI receives and renders widgets              [widgets/messages.py]
```

### Path B: CLI Task Submission (NATS)

```
nexus-client submit "task"
  → cli.py:submit() → sdk.submit_task()            [sdk.py:57]
  → AgentBus.publish("tasks.submit")               [bus.py:84]
  → NexusWorker.handle_task()                      [worker.py:120]
  → _run_agent_task()                              [worker.py:26]
  → Agent.__call__() → deepagents                  [agent.py:113]
  → Result stored in DB + NATS KV                  [worker.py:164]
  → SDK polls KV for result                        [sdk.py:79]
```

### Path C: CLI Run (Isolated Worker)

```
nexus run "task" --model X --max-depth 3
  → cli.py:run() → TaskContract                   [cli.py:81]
  → worker_pool.spawn(contract, depth=0)           [worker.py:216]
  → WorkerPool._run_worker()                       [worker.py:236]
  → _execute_bounded() with turn/wall limits       [worker.py:258]
  → _run_agent_task() per turn                     [worker.py:286]
  → SubAgentHandle._mark_completed()               [subagent.py:137]
  → Result returned to CLI                         [cli.py:101]
```

---

## 4. Key Classes and Functions

### `agent.py`
- **`Agent`** (line 47): Wraps `create_deep_agent`. Constructor takes `role` (tool manifest) and `policy` (permissive/restricted/strict). Auto-prefixes `google_genai:` for Gemini models.
- **`_ROLE_TOOLS`** (line 38): Pre-built dict mapping role → tool function list.
- **`run_agent_task(state)`** (line 117): Standalone function for worker pool execution.

### `session.py`
- **`Session`** (line 161): Manages a single conversation. Key methods:
  - `send(user_message, images)` (line 302): Full message processing pipeline.
  - `_load_system_prompt()` (line 205): Loads NEXUS.md with caching.
  - `_build_context_injection()` (line 225): Environment + git + tool list.
  - `_handle_message_token()` (line 452): Processes streamed tokens, tool calls, tool results.
  - `event_stream()` (line 580): Async generator yielding events.
  - `approve(call_id, approved)` (line 547): Approval gate for tool calls.
  - `interrupt()` (line 562): Cancellation flag.
- **`SessionManager`** (line 595): Cache with double-checked locking for session creation.
- **`_extract_agent_response(result)`** (line 29): Normalizes various LLM response formats.

### `models.py`
- **`TaskSchema`** (line 16): id, description, priority, status, timestamps, metadata.
- **`TaskContract`** (line 32): Full task configuration (model override, max_depth, summary_only, etc.).
- **`ResultSchema`** (line 56): task_id, success, data, error, duration.
- **`AgentEvent`** subclasses (line 68): `ThinkingEvent`, `ToolCallEvent`, `ToolResultEvent`, `ApprovalRequestEvent`, `ResponseEvent`, `ErrorEvent`.
- **`ImageAttachment`** (line 112): Base64 image encoding for multimodal input.

### `config.py`
- **`ConfigSchema`** (line 81): Top-level config with sections: `server`, `client`, `auth`, `agent`, `prompt`, `logging`.
- **`load_config()`** (line 97): Loads YAML, applies `NEXUS_*__` env var overrides, resolves relative paths.
- **`settings`** (line 169): Module-level singleton.

### `llm.py`
- **`LLMProvider`** (line 21): Multi-provider bridge.
  - `generate(prompt, system_prompt, timeout)` (line 62): Routes to Gemini or OpenRouter.
  - `_call_gemini()` (line 83): Uses `google.generativeai` SDK.
  - `_call_openrouter()` (line 104): Uses `AsyncOpenAI` with OpenRouter base URL.
  - All methods decorated with `@retry_with_backoff(max_attempts=3)`.

### `server.py`
- **FastAPI app** (line 57): Lifespan manages DB init, NATS connect, worker start.
- **REST endpoints**: `POST /tasks`, `GET /tasks/{id}/status`, `GET /tasks/{id}/result`, `GET /tasks`, `POST /tasks/{id}/cancel`, `POST /tasks/{id}/retry`, `GET /workers`, `GET /tools`, `GET /health`.
- **WebSocket** (line 239): `/sessions/{session_id}/ws` — real-time bidirectional session.

### `worker.py`
- **`NexusWorker`** (line 79): NATS subscriber for `tasks.submit`. Handles task lifecycle: DB update → agent execution → result storage.
- **`WorkerPool`** (line 207): Semaphore-bounded pool for isolated workers. `spawn()` returns `SubAgentHandle`.
- **`_run_agent_task(task)`** (line 26): Routes research tasks to LangGraph, coding tasks to deepagents.
- **Circuit breakers**: `_nats_breaker` (threshold=3, timeout=15s), `_agent_breaker` (threshold=5, timeout=30s).

### `subagent.py`
- **`SubAgentHandle`** (line 25): Control interface with states PENDING→RUNNING→COMPLETED/FAILED/CANCELLED.
  - `wait(timeout)` (line 113): Async wait for completion.
  - `cancel()` (line 96): Signal cancellation.
  - `can_spawn_child()` (line 90): Depth check for nested spawning.
  - `_generate_summary(result)` (line 154): Truncates to 500 chars for summary-only mode.

### `bus.py`
- **`AgentBus`** (line 25): NATS client wrapper.
  - `connect()` (line 33): Connects to NATS, creates/attaches to JetStream KV bucket `nexus_results`.
  - `subscribe(subject, callback)` (line 57): With 3x retry and backoff.
  - `publish(subject, message)` (line 84): JSON-serialized with custom encoder.
  - `put_result(task_id, result)` (line 94): KV store write with retry.
  - `get_result(task_id)` (line 119): KV store read with 5s timeout.

### `compaction.py`
- **`CompactionPipeline`** (line 25): 4-level graduated compaction.
  1. `_clear_tool_results()` (line 99): Blanks old tool results (>5 turns).
  2. `_microcompact()` (line 124): Clears tool results (>3 turns).
  3. `_summarize_old_messages()` (line 147): Heuristic summary of old messages.
  4. `_emergency_truncate()` (line 204): Keeps last 5 messages.
- **`pre_compaction_flush(session, summary)`** (line 222): Saves to memory before compaction.

### `memory.py`
- **`Memory`** (line 76): SQLite+sqlite-vec scoped memory with `remember()`, `recall()`, `reflect()`, `fork()`, `merge()`.
- **`MemoryManager`** (line 259): Lifecycle manager for Memory instances.
- **`HybridMemoryManager`** (line 356): Top-level interface combining `FileMemory` + `HybridMemoryIndex`.
  - `remember(content, type, description, ...)` (line 375): Writes file entry + async index.
  - `recall(query, max_results)` (line 402): Hybrid search.
  - `get_memory_context(query, max_results)` (line 409): Formats results for prompt injection.
  - `flush(session_summary)` (line 428): Daily log + re-index.

### `memory_files.py`
- **`FileMemory`** (line 49): Canonical file-based memory.
  - `write_entry()` (line 73): Creates topic files with YAML frontmatter in `bank/`.
  - `append_daily_log()` (line 185): Appends to `memory/YYYY-MM-DD.md`.
  - `get_index_entries()` (line 199): Parses MEMORY.md pointers.
  - `list_all_files()` (line 257): All bank/ + memory/ files.

### `memory_index.py`
- **`EmbeddingProvider`** (line 45): Tiered embedding → Gemini → local sentence-transformers → hash fallback.
- **`HybridMemoryIndex`** (line 147): SQLite FTS5 + sqlite-vec hybrid search.
  - `index_file(relative_path)` (line 232): Sync indexing with hash embeddings.
  - `async_index_file(relative_path)` (line 323): Async with full embedding chain.
  - `search(query, max_results)` (line 460): Async hybrid search (70% vector + 30% keyword).
  - `search_sync(query, max_results)` (line 483): Sync search with hash fallback.
  - `rebuild()` (line 688): Full index rebuild from workspace files.

### `graph.py`
- **`ResearchGraphState`** (line 38): TypedDict for LangGraph state.
- **Nodes**: `plan_node` (line 61), `refine_node` (line 82), `execute_node` (line 106), `synthesize_node` (line 160).
- **`route_after_execute(state)`** (line 193): Conditional edge — loop or synthesize.
- **`create_research_graph(db_path)`** (line 208): Builds and compiles the LangGraph with SqliteSaver checkpointing.

### `orchestration.py`
- **`DeepResearchOrchestrator`** (line 47): Multi-phase research: intent → plan → refine → execute → synthesize.
- **`ResearchPlan`** (line 28): thesis, objective, steps, expected_outcomes.
- **`SearchResult`** (line 19): url, title, snippet, content.

### `tools/registry.py`
- **`ToolInfo`** (line 48): Dataclass with name, func, description, parameters, example, category, returns.
- **`_REGISTRY`** (line 79): Global dict of all registered tools.
- **`register_tool()`** (line 82): Decorator for tool registration.
- **`ROLE_MANIFESTS`** (line 166): 9 roles (minimal, reader, writer, coder, tester, reviewer, debugger, researcher, full).
- **`tool_search()`** (line 397): Policy-aware tool discovery with exact/fuzzy/category search.
- **`_is_tool_allowed(tool_name)`** (line 295): Policy enforcement (permissive auto-unlocks, restricted enforces manifest, strict locks).

### `telemetry.py`
- **`TelemetryManager`** (line 23): Rotating file logging (5MB × 3), metrics collection.
- **`LogViewer`** (line 127): Textual Static widget for in-app log viewing.

### `db.py`
- **`DatabaseManager`** (line 77): Async SQLite engine with `get_session()` context manager.
- **`TaskRepository`** (line 129): CRUD for tasks + cancel/retry/list.
- **`SessionRepository`** (line 232): CRUD for sessions + messages + fork/rename/delete.

### `sdk.py`
- **`NexusSDK`** (line 12): High-level client with `submit_task`, `get_result`, `wait_for_result`, `submit_and_wait`, `submit_batch`.

### `cli.py`
- **`main()`** (line 22): Click group with version option.
- **`submit` command** (line 28): Submit task via SDK.
- **`run` command** (line 71): Spawn isolated worker with TaskContract.
- **`session` command** (line 111): List/resume/fork/rename/delete sessions.

### `tui.py`
- **`NexusApp`** (line 60): Main Textual App.
  - `compose()` (line 98): VerticalScroll(chat) + ChatInput + StatusBar.
  - `on_mount()` (line 110): gc.freeze(), theme setup, telemetry, welcome banner.
  - `on_key()` (line 164): Ctrl+C (interrupt/exit), F1 (help), F2 (logs), F3 (theme), F12 (devtools).
  - `on_chat_input_submitted()` (line 296): Posts UserInput event.
  - Custom messages: `UserInput` (line 318), `InterruptRequested` (line 325).

### `widgets/messages.py`
- **`UserMessage`** (line 27): Static with `$primary` left border.
- **`AssistantMessage`** (line 54): Static with `append_token()` streaming + `finalize()`.
- **`ToolCallMessage`** (line 87): Static with `$warning` left border, tool name + args + truncated output.
- **`AppMessage`** (line 132): Dim italic system messages.
- **`ErrorMessage`** (line 154): `$error` colored with ✗ icon.
- **`WelcomeBanner`** (line 178): Session info with box-drawing characters.

### `widgets/chat_input.py`
- **`ChatInput`** (line 25): TextArea with Enter→submit, history, image path extraction.

### `widgets/status.py`
- **`StatusBar`** (line 79): Horizontal bar with spinner, message, CWD, branch, tokens, model. Responsive hiding at narrow widths.
- **`ModelLabel`** (line 35): Smart truncation (drop provider → left-truncate model).

### `widgets/theme.py`
- **`ThemeColors`** (line 57): Frozen dataclass with 16 semantic color tokens.
- **`register_themes(app)`** (line 148): Registers 4 themes: nexus-dark, catppuccin-mocha, gruvbox-dark, nord.

---

## 5. Dependency Graph (High-Level)

```
cli.py ──→ sdk.py ──→ bus.py ──→ (NATS)
  │           │          │
  │           ↓          ↓
  │         db.py ←──────┘
  │           │
  ↓           ↓
worker.py → agent.py → tools/registry.py → tools/*.py
  │           │              │
  │           ↓              ↓
  │       llm.py         config.py
  │           │
  ↓           ↓
subagent.py  graph.py → orchestration.py → llm.py
              │
              ↓
server.py → session.py → agent.py
  │           │
  │           ↓
  │       compaction.py
  │           │
  │           ↓
  │       memory.py → memory_files.py + memory_index.py
  │           │
  │           ↓
  │       prompt_loader.py
  │           │
  │           ↓
  │       models.py
  │           │
  ↓           ↓
tui.py ← widgets/theme.py
  │         widgets/messages.py
  │         widgets/chat_input.py
  │         widgets/status.py
  ↓
telemetry.py

auth.py → api_auth.py → server.py
config.py ← (all modules)
utils.py ← (llm.py, worker.py, bus.py)
```

---

## 6. Test Coverage

| Test File | Covers |
|-----------|--------|
| `tests/test_agent_events.py` | `models.py` — AgentEvent serialization |
| `tests/test_bus.py` | `bus.py` — NATS bus (likely mocked) |
| `tests/test_cli_run.py` | `cli.py` — `run` command |
| `tests/test_compaction.py` | `compaction.py` — CompactionPipeline |
| `tests/test_config.py` | `config.py` — ConfigSchema loading |
| `tests/test_db_sessions.py` | `db.py` — SessionRepository |
| `tests/test_e2e_production.py` | End-to-end production flow |
| `tests/test_graph.py` | `graph.py` — Research graph structure |
| `tests/test_graph_nodes.py` | `graph.py` — Individual node execution |
| `tests/test_image_input.py` | `models.py` — ImageAttachment encoding |
| `tests/test_memory.py` | `memory.py` — Memory/MemoryManager |
| `tests/test_memory_files.py` | `memory_files.py` — FileMemory |
| `tests/test_memory_index.py` | `memory_index.py` — HybridMemoryIndex |
| `tests/test_memory_tools.py` | Memory-related tools |
| `tests/test_models.py` | `models.py` — Pydantic schemas |
| `tests/test_orchestration.py` | `orchestration.py` — DeepResearchOrchestrator |
| `tests/test_sdk.py` | `sdk.py` — NexusSDK |
| `tests/test_server.py` | `server.py` — FastAPI endpoints |
| `tests/test_session.py` | `session.py` — Session lifecycle |
| `tests/test_session_memory.py` | `session.py` + memory integration |
| `tests/test_subagent.py` | `subagent.py` — SubAgentHandle |
| `tests/test_task_reaper.py` | `task_reaper.py` — TaskReaper |
| `tests/test_tui_streaming.py` | `tui.py` — Streaming token display |
| `tests/test_websocket.py` | `server.py` — WebSocket session |
| `tests/test_worker_pool.py` | `worker.py` — WorkerPool |
| `tests/tools/test_fs.py` | `tools/fs.py` — File system tools |
| `tests/tools/test_fs_enhanced.py` | `tools/fs.py` — Enhanced file operations |
| `tests/tools/test_patch.py` | `tools/patch.py` — Patch application |
| `tests/tools/test_research.py` | `tools/research.py` — Web search tools |
| `tests/tools/test_shell.py` | `tools/shell.py` — Shell execution |
| `tests/tools/test_spawn_subagent.py` | `tools/register_all.py` — spawn_subagent tool |
| `tests/contract_verification/test_fixture.py` | Contract verification fixtures |

### Modules with NO test coverage:
- `llm.py` — LLMProvider (no tests)
- `prompt_loader.py` — NEXUS.md loading (no tests)
- `auth.py` — AuthManager (no tests)
- `api_auth.py` — API key verification (no tests)
- `telemetry.py` — TelemetryManager (no tests)
- `tui.py` — NexusApp (only streaming tested in `test_tui_streaming.py`)
- `widgets/*.py` — Widget tests only via `test_tui_streaming.py`
- `web_ui.py` — Gradio UI (no tests)
- `tui_legacy.py` — Legacy TUI (no tests)

---

## 7. Known Issues / TODOs

| Location | Issue |
|----------|-------|
| `orchestration.py:99` | `_fetch()` is a stub — returns `None` with "TODO: implement with httpx or similar" |
| `docs/specs/0001-telemetry-system.md:575` | TODO: Implement authentication and authorization for telemetry endpoint |
| `docs/plans/2026-06-07-api-sdk-overhaul.md:531` | `api_auth.py:verify_api_key` has TODO to validate against keystore but doesn't fully use it |
| `docs/plans/2026-07-11-audit-report.md:72` | Audit finding: `verify_api_key` doesn't properly validate against keystore |
| `memory.py:25-26` | `_hash_embed()` is a placeholder — "should be replaced with a real embedding model in production" |
| `memory_index.py:123` | `_embed_hash()` is the lowest-quality fallback — "low quality, always works" |
| `session.py:145-158` | `_build_session_history_context()` is a stub — returns empty string with comment "simplified version" |
| `graph.py:242-245` | Checkpoint DB uses in-memory SQLite by default (`:memory:`) — checkpoints lost on restart |
| `worker.py:288` | `_execute_bounded` checks `result.get("status") == "complete"` but agent results may not have this field |
| `server.py:84-86` | Comment notes "In a production system, we would save the task to DB here before publishing to NATS" — partially addressed but noted |
| `tui.py:249` | `HelpScreen` uses `Vertical` container but doesn't import it (only `VerticalScroll` is imported) — **potential runtime error** |
| `tui.py:218` | `LogViewerScreen` uses `Grid` container but doesn't import it — **potential runtime error** |
| `config.py:46` | `max_tool_output_chars` default is 400 — very low, may truncate useful output |
| `config.py:38` | `default_model` is `gemini-3.1-flash-lite` — may not exist (Gemini naming convention uses `gemini-2.0-flash` etc.) |
| `models.py:51` | `TaskContract.max_depth` default is 3 — limits sub-agent nesting |
| `bus.py:47-49` | KV bucket creation error silently swallowed — assumes "already exists" for all errors |
| `db.py:47-48` | `TaskModel` uses `metadata_json` column name but `TaskSchema` uses `metadata` — naming mismatch |

---

## 8. TUI Details

### Architecture (`tui.py`)

The TUI is built on **Textual** (a modern Python terminal UI framework). The main class `NexusApp` extends `App`:

**Layout** (composed in `compose()`, line 98):
```
┌─────────────────────────────────────────┐
│  VerticalScroll (#chat)                 │
│    └── Container (#messages, stream)    │
│         ├── WelcomeBanner               │
│         ├── UserMessage                 │
│         ├── AssistantMessage (streaming)│
│         ├── ToolCallMessage             │
│         ├── AppMessage                  │
│         └── ErrorMessage                │
├─────────────────────────────────────────┤
│  ChatInput (#input-area)                │
├─────────────────────────────────────────┤
│  StatusBar (#status-bar) [docked bottom]│
└─────────────────────────────────────────┘
```

**Key Design Decisions:**
- **Stream layout** (`layout="stream"`) on the messages container for O(1) append — no re-layout of existing widgets.
- **Individual message widgets** (not RichLog) — each message is a separate `Static` widget, enabling per-message styling and removal.
- **`gc.freeze()`** before first paint (line 114) — prevents GC pauses during rendering.
- **ASCII fallback** — detects `TERM=dumb`, `COLORTERM=""`, or `NO_COLOR` env var (line 86).
- **Panic handler** — restores terminal state on crash.

**Key Bindings** (`on_key()`, line 164):
| Key | Action |
|-----|--------|
| Ctrl+C | Interrupt (if busy) or Exit |
| F1 | Show help modal |
| F2 | Show log viewer modal |
| F3 | Cycle theme (nexus-dark → catppuccin → gruvbox → nord) |
| F12 | Toggle devtools |

**Slash Commands** (handled by `ChatInput` → `NexusApp`):
| Command | Action |
|---------|--------|
| `/help` | Show help screen |
| `/logs` | Show log viewer |
| `/theme` | Switch theme |
| `/clear` | Clear chat (remove all widgets, re-add welcome) |
| `/model` | Show current model |

**Custom Events:**
- `NexusApp.UserInput` (line 318) — posted when user submits text. Carries `content` and `images`.
- `NexusApp.InterruptRequested` (line 325) — posted on Ctrl+C during busy state.

**Known Bug:** `tui.py:218` and `tui.py:249` reference `Grid` and `Vertical` containers that are **not imported** — only `VerticalScroll` is imported from `textual.containers`. This will cause `NameError` at runtime when opening the log viewer or help screen.

### Widget Details

**`widgets/messages.py`:**
- `UserMessage` (line 27): `$primary` left border, `height: auto`, `text-wrap: wrap`.
- `AssistantMessage` (line 54): Streaming via `append_token(token)` → updates Content. `finalize(content)` sets final text.
- `ToolCallMessage` (line 87): `$warning` left border. Shows `⚙ tool_name(args)` header + truncated output (300 char limit). Hover highlights with `$accent-light`.
- `AppMessage` (line 132): `$text-muted`, italic — for thinking/status messages.
- `ErrorMessage` (line 154): `$error` color, `✗ Error:` prefix.
- `WelcomeBanner` (line 178): Box-drawing banner with session ID and timestamp. Uses Rich markup for styling.

**`widgets/chat_input.py`:**
- `ChatInput` (line 25): Extends `TextArea`. Enter submits, Shift+Enter for newline (TextArea default). Maintains command history list. Extracts image paths/URLs via regex.

**`widgets/status.py`:**
- `StatusBar` (line 79): `dock: bottom`, height 1. Composed of: spinner, message, CWD, branch, tokens, model. Responsive: hides CWD at ≤60 cols, hides branch at ≤80 cols.
- `ModelLabel` (line 35): Smart truncation — drops provider prefix, then left-truncates with ellipsis.

**`widgets/theme.py`:**
- 4 themes registered: `nexus-dark` (default, Linear-inspired indigo), `catppuccin-mocha`, `gruvbox-dark`, `nord`.
- Each theme maps 16 semantic CSS variables (`$background`, `$primary`, `$text-muted`, etc.).

---

## 9. Tools

### Tool Registry (`tools/registry.py`)

**27 tools** registered across **8 categories**:

| Category | Tools |
|----------|-------|
| **core** (2) | `tool_search`, `auto_correct` |
| **fs** (7) | `read_file`, `read_multiple_files`, `write_file`, `write_multiple_files`, `edit_file`, `list_directory`, `apply_patch` |
| **shell** (2) | `run_shell`, `run_shell_streaming` |
| **git** (10) | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_show`, `git_commit`, `git_checkout_branch`, `git_stash_push`, `git_stash_pop`, `git_stash_list` |
| **test** (2) | `run_tests`, `run_single_test` |
| **search** (3) | `search_code`, `find_symbol`, `find_references` |
| **web** (3) | `search_web`, `search_local_docs`, `fetch_url` |
| **orchestration** (1) | `spawn_subagent` |

### Role Manifests

| Role | Tool Count | Key Tools |
|------|-----------|-----------|
| `minimal` | 1 | `tool_search` only |
| `reader` | 8 | read + search + web search |
| `writer` | 5 | read + write + edit + list |
| `coder` | 18 | full dev tooling (fs, shell, git, test, search) |
| `tester` | 11 | test + read + edit + git diff/status |
| `reviewer` | 10 | read + search + git history + test |
| `debugger` | 11 | read + edit + test + shell + git |
| `researcher` | 8 | search + read + web + shell |
| `full` | all | All registered tools |

### Policy Enforcement

Three levels (enforced in `agent.py` + `tools/registry.py`):
1. **permissive** (default): `tool_search` shows role manifest, but any tool auto-unlocks on first call.
2. **restricted**: Tools outside manifest denied at call time. `tool_search` only shows in-manifest.
3. **strict**: Locked to manifest forever. No unlocking.

Thread-local storage (`threading.local()`) ensures parent and sub-agents can run concurrently with different policies.

### Tool Search (`tool_search()`, line 397)

- Policy-aware: only shows tools the current role/policy allows.
- Supports exact name match, fuzzy match (difflib), category filter, and use-case search.
- Returns formatted tool descriptions with parameters and examples.

---

## 10. Configuration

### Config File (`config.py`)

**Default config file:** `config/nexusagent.yaml` (relative to project root)

**Environment variable override pattern:** `NEXUS_{SECTION}__{KEY}=value`
- Example: `NEXUS_SERVER__API_PORT=9000` → `settings.server.api_port = 9000`
- Example: `NEXUS_AGENT__DEFAULT_MODEL=gemini-2.0-flash` → `settings.agent.default_model`
- Back-compat: `NEXUS_LOG_LEVEL` → `settings.logging.level`

**Config Sections:**

| Section | Model | Key Defaults |
|---------|-------|-------------|
| `server` | `ServerConfig` | nats_url=`nats://localhost:4222`, db_path=`nexus.db`, api_port=8000, worker_threads=4 |
| `client` | `ClientConfig` | tui_theme=`textual-dark`, timeout=30, retry_limit=3, result_timeout=300 |
| `auth` | `AuthConfig` | master_secret_path=`.master.secret`, keystore_path=`keystore.json`, kdf_iterations=100000 |
| `agent` | `AgentConfig` | default_model=`gemini-3.1-flash-lite`, primary_provider=`gemini`, compaction_enabled=True, max_conversation_history=40 |
| `prompt` | `PromptConfig` | base_prompt_file=`config/NEXUS.md`, max_chain_depth=8, chat_file_injection=True |
| `logging` | `LoggingConfig` | level=`INFO` |

**Path Resolution:** Relative paths in config (db_path, master_secret_path, keystore_path, salt_path) are resolved to absolute paths relative to the project root (`src/nexusagent/` → project root via `Path(__file__).parent.parent.parent`).

**Singleton:** `settings = load_config()` at module level (line 169).

### LLM Providers (`llm.py`)

**Gemini** (primary):
- Uses `google.generativeai` SDK.
- Model from `settings.agent.gemini_model` (default: `gemini-3.1-flash-lite`).
- API key from `GEMINI_API_KEY` env var.

**OpenRouter** (alternative):
- Uses `AsyncOpenAI` with `base_url=https://openrouter.ai/api/v1`.
- Model from `settings.agent.openrouter_override_model` or `openrouter_default_model` (`openrouter/auto`).
- API key from `OPENROUTER_API_KEY` env var.

**Provider selection:** `settings.agent.primary_provider` (`gemini` or `openrouter`).

**Auto-prefixing:** In `agent.py:89`, models starting with `gemini` or `gemma` without a `:` prefix get `google_genai:` prepended to avoid VertexAI routing.

**Retry:** All LLM calls use `@retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=10.0, jitter=True)`.

### Prompt System (`prompt_loader.py`)

**NEXUS.md loading order:**
1. `config/NEXUS.md` (package base prompt)
2. `CWD/NEXUS.md` (project-specific overrides)
3. `@file` chains resolved recursively (max depth 8, max file size 256KB)

**Chat-time injection:** Users can type `@/path/to/file` on its own line in chat to inline file content. Circular chains detected via visited-path tracking.

**System prompt caching:** `Session._cached_prompt` (line 212) caches the loaded prompt for the session lifetime.
