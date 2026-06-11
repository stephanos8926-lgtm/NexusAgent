# NexusAgent Codebase Map

> Generated: 2026-07-16
> Total source files: 33 (excluding venv/tests)
> Total test files: 28
> Merged from: CODEBASE_MAP.md, CODEBASE_MAP_CORE.md, CODEBASE_MAP_TOOLS_API.md, CODEBASE_MAP_TUI.md

## Project Root

```
NexusAgent/
├── main.py                    # Stub entry point (prints "Hello from nexusagent!")
├── pyproject.toml             # Project metadata, deps, ruff config
├── Makefile                   # Lint, test, typecheck targets
├── nexus.db                   # SQLite main DB (sessions, tasks, results)
├── .env                       # API keys (GEMINI_API_KEY, OPENROUTER_API_KEY)
├── keystore.json              # Encrypted API key store (Fernet)
├── .master.secret             # Master secret for key encryption
├── .master.salt               # Salt for key derivation
├── config/
│   └── NEXUS.md               # Base system prompt
├── docs/                      # MkDocs documentation
├── deployment/                # Deployment scripts
├── tests/                     # 28 test files
└── src/nexusagent/           # Main source package
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    CLI (click)                      │
│              nexus-client / nexus run               │
├─────────────────────────────────────────────────────┤
│                   Web UI (Gradio)                   │
├─────────────────────────────────────────────────────┤
│                  FastAPI Server                     │
│         REST endpoints + WebSocket /ws              │
├──────────────┬──────────────┬───────────────────────┤
│   TUI        │   SDK        │   Worker Pool         │
│ (Textual)    │ (NexusSDK)   │ (NexusWorker)         │
├──────────────┴──────────────┴───────────────────────┤
│              Agent (deepagents)                      │
│   Role-based tool access + policy enforcement        │
├──────────────────────────────────────────────────────┤
│              Tools Registry (35+ tools)              │
│   fs, git, shell, research, code_search, memory,     │
│   spawn_subagent, patch, test_runner                 │
├──────────────────────────────────────────────────────┤
│   LLM Provider (Gemini + OpenRouter)                │
│   NEXUS.md Prompt Loader                            │
│   Hybrid Memory (files + vector index)              │
│   Session Manager + Compaction Pipeline             │
├──────────────────────────────────────────────────────┤
│   SQLite DB (sessions, tasks, results)             │
│   NATS Bus (event streaming)                        │
│   Auth Manager (Fernet-encrypted keystore)          │
└──────────────────────────────────────────────────────┘
```

## Data Flow

```
                         USER MESSAGE
                               │
                               ▼
                ┌──────────────────────────────┐
                │       SessionManager         │
                │  (get_or_create / cache)     │
                │  session.py:555              │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │          Session             │
                │  session.py:161              │
                │                              │
                │  1. Process @file injection  │
                │  2. Load system prompt       │
                │  3. Build context block      │
                │  4. Recall memory            │
                │  5. Check compaction         │
                └──────────────┬───────────────┘
                               │
                ┌──────────────▼───────────────┐
                │        Agent                 │
                │  agent.py:47                 │
                │                              │
                │  • Role-based tool filtering │
                │  • Policy enforcement        │
                │  • Model resolution          │
                │  • Wraps deepagents          │
                └──────────────┬───────────────┘
                               │
                ┌──────────────▼───────────────┐
                │     deepagents (inner)       │
                │                              │
                │  astream() → token stream    │
                │  ┌────────────────────────┐  │
                │  │  LLM (Gemini/etc.)    │  │
                │  │  ┌──────────────────┐  │  │
                │  │  │  Tool Calls      │──┼──┼──► Tool Execution
                │  │  │  Text Tokens     │  │  │    (file, shell, etc.)
                │  │  │  Thinking        │  │  │         │
                │  │  └──────────────────┘  │  │         │
                │  └────────────────────────┘  │         │
                └──────────────────────────────┘         │
                               │                         │
                               ▼                         │
                ┌──────────────────────────────┐         │
                │   Event Stream (Session)     │◄────────┘
                │                              │
                │  • thinking                  │
                │  • tool_call                 │
                │  • tool_result               │
                │  • response_chunk            │
                │  • response (final)          │
                │  • error                     │
                └──────────────┬───────────────┘
                               │
                ┌──────────────▼───────────────┐
                │   Persistence & Memory       │
                │                              │
                │  • DB (task_repo)            │
                │  • HybridMemoryManager       │
                │  • Conversation history      │
                └──────────────────────────────┘
```

## Source Package (`src/nexusagent/`)

### Core Layer

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `config.py` | 164 | 7 | 2 | **Config system**: ServerConfig, ClientConfig, AuthConfig, AgentConfig, PromptConfig, LoggingConfig, ConfigSchema. 3-tier loading (default→yaml→env). Singleton `settings`. |
| `models.py` | 108 | 12 | 0 | **Data models**: TaskStatus, TaskSchema, MemoryScope, TaskContract, ResultSchema, AgentEvent (+ ThinkingEvent, ToolCallEvent, ToolResultEvent, ApprovalRequestEvent, ResponseEvent, ErrorEvent). All Pydantic BaseModels. |
| `llm.py` | 129 | 2 | 0 | **LLM provider bridge**: LLMProvider with Gemini + OpenRouter support. Retry with backoff. `llm` singleton. |
| `agent.py` | 135 | 1 | 2 | **Agent**: Role-based tool access (minimal→full), 3 policy levels (permissive/restricted/strict). Uses deepagents' `create_deep_agent`. `Agent`, `run_agent_task()`. |
| `session.py` | 633 | 2 | 4 | **Session + SessionManager**: Interactive session lifecycle. NEXUS.md loading, context injection, memory recall, deepagents streaming via `astream()`. Event queue via `_enqueue()`/`event_stream()`. |
| `server.py` | 314 | 1 | 12 | **FastAPI server**: REST endpoints (tasks, workers, tools) + WebSocket endpoint `/sessions/{id}/ws` for real-time TUI. NATS integration via `AgentBus`. Lifespan manages startup/shutdown. |
| `bus.py` | 172 | 2 | 2 | **NATS event bus**: AgentBus with JetStream. Subscribe, publish, put_result, get_result with retry. `get_bus()` singleton. |
| `orchestration.py` | 190 | 4 | 0 | **DeepResearchOrchestrator**: plan→refine→execute→synthesize workflow. ResearchPlan, ResearchState, SearchResult. Uses `search_web` tool. |
| `graph.py` | 250 | 1 | 6 | **LangGraph research graph**: 4-node state machine (plan→refine→execute→synthesize). ResearchGraphState TypedDict. Conditional looping via `route_after_execute`. SqliteSaver checkpointing. |
| `prompt_loader.py` | 242 | 2 | 5 | **Prompt loader**: NEXUS.md loading with @file chaining. Circular detection. Depth limits. `load_nexus_prompt()`, `inject_file_at_reference()`. |
| `db.py` | 408 | 8 | 4 | **SQLAlchemy async ORM**: TaskModel, ResultModel, SessionModel, MessageModel. DatabaseManager, TaskRepository, SessionRepository (CRUD + fork + rename + delete). |
| `memory.py` | 442 | 4 | 2 | **HybridMemoryManager**: Memory (vector recall via embeddings), MemoryManager (SQLite + sqlite-vec), HybridMemoryManager (file canonical + index derived). Hash embeddings as fallback. |
| `memory_index.py` | ~350 | 2 | — | **HybridMemoryIndex**: FTS5 + sqlite-vec union merge search. Async embedding chain (Gemini→local→hash). |
| `memory_files.py` | 264 | 2 | — | **FileMemory**: File-based canonical memory. Topic-based entries with YAML frontmatter. Entity tracking, daily logs, MEMORY.md index. |

### TUI Layer

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `tui.py` | 1168 | 4 | 1 | **Textual TUI**: NexusApp (monolithic), SpinnerLabel, ApprovalModal, ErrorModal. WebSocket event loop, slash commands, tool output formatting. Real-time streaming chat with 5 color themes. |

### Tools Layer (`tools/`)

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `registry.py` | 623 | 1 | 16 | **Tool registry**: ToolInfo dataclass, `@register_tool` decorator, policy enforcement, `tool_search()` with fuzzy matching. Role manifests (9 roles). |
| `register_all.py` | 613 | 0 | 5 | **Tool registration**: Registers all tools (fs, git, shell, test, patch, code_search, research, memory+, meta). |
| `fs.py` | 346 | 0 | 12 | **Filesystem tools**: read_file, write_file, edit_file, list_directory, read_multiple_files, write_multiple_files. Path jail. |
| `shell.py` | 167 | 0 | 4 | **Shell tools**: run_shell, run_shell_streaming. shlex.split() for injection prevention. |
| `git.py` | ~200 | 0 | 9 | **Git tools**: git_status, git_log, git_diff, git_show, git_branch, git_checkout_branch, git_commit, git_stash_push/pop/list. |
| `research.py` | 107 | 0 | 4 | **Research tools**: search_web (Exa + Tavily fallback), search_local_docs (ctx7). |
| `patch.py` | ~100 | 0 | 1 | **Patch tool**: apply_patch for file patching. |
| `code_search.py` | ~100 | 0 | 3 | **Code search**: search_code, find_symbol, find_references. Uses ast-grep. |
| `test_runner.py` | ~100 | 0 | 2 | **Test tools**: run_tests, run_single_test. Auto-detects framework. |

### Auth & Security

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `auth.py` | 129 | 1 | 0 | **AuthManager**: Fernet encryption for API keys. PBKDF2 key derivation. |
| `api_auth.py` | 53 | 0 | 1 | **API auth**: FastAPI Security dependency via X-API-Key header. |

### CLI & SDK

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `cli.py` | 194 | 0 | 5 | **Click CLI**: `nexus-client` submit, `nexus run`, `nexus session`. |
| `sdk.py` | 206 | 1 | 0 | **NexusSDK**: High-level async SDK. submit_task, get_result, submit_and_wait, batch submit, list_tools. |
| `web_ui.py` | 86 | 0 | 3 | **Gradio web UI**: Dark theme (#1A1A1A). Task submission dashboard on port 7860. |

### Workers & Background

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `worker.py` | 311 | 2 | 2 | **NexusWorker + WorkerPool**: NATS subscriber with circuit breaker. WorkerPool with SubAgentHandle, depth limiting. |
| `subagent.py` | 161 | 2 | 0 | **SubAgentHandle**: Status tracking (pending→running→completed/failed/cancelled). |
| `task_reaper.py` | 59 | 1 | 0 | **TaskReaper**: Background loop to mark stale PROCESSING tasks as FAILED. |

### Utilities

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `utils.py` | 354 | 3 | 2 | **Utils**: retry_with_backoff, retry_on_false decorators. CircuitBreaker (CLOSED/OPEN/HALF_OPEN). |

## Complete Tool Inventory (33 tools)

### Tool Registry (`registry.py`)

- **Global `_REGISTRY`** dict, policy enforcement (permissive/restricted/strict), role-based manifests, tool search with fuzzy matching.
- **9 roles**: minimal, reader, writer, coder, tester, reviewer, debugger, researcher, full
- **Policy levels**: permissive (auto-unlock), restricted (enforced boundaries), strict (locked to manifest)

### Tool Table

#### Core Tools (2)
- `tool_search` — Policy-aware tool search with exact/fuzzy/category filtering
- `auto_correct` — Tool name correction and validation

#### File System Tools (7)
- `read_file`, `read_multiple_files`, `write_file`, `write_multiple_files`, `edit_file`, `list_directory`, `apply_patch`

#### Shell Tools (2)
- `run_shell`, `run_shell_streaming`

#### Git Tools (10)
- `git_status`, `git_diff`, `git_log`, `git_branch`, `git_show`, `git_stash_push`, `git_stash_pop`, `git_stash_list`, `git_commit`, `git_checkout_branch`

#### Test Runner Tools (2)
- `run_tests`, `run_single_test`

#### Code Search Tools (3)
- `search_code`, `find_symbol`, `find_references`

#### Research / Web Tools (3)
- `search_web`, `search_local_docs`, `fetch_url`

#### Orchestration Tools (1)
- `spawn_subagent`

#### Interaction Tools (1)
- `ask_user`

#### Memory Tools (3)
- `memory_search`, `memory_get`, `memory_write`

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check; reports NATS connection state |
| `POST` | `/tasks` | Yes | Submit new task; saves to DB + publishes to NATS |
| `GET` | `/tasks` | Yes | List tasks with status filter + pagination |
| `GET` | `/tasks/{task_id}/status` | Yes | Get task status from DB |
| `GET` | `/tasks/{task_id}/result` | Yes | Get task result; 404 if not found |
| `POST` | `/tasks/{task_id}/cancel` | Yes | Cancel pending/processing task |
| `POST` | `/tasks/{task_id}/retry` | Yes | Retry failed task; re-publishes to NATS |
| `GET` | `/workers` | Yes | Worker status + circuit breaker states |
| `GET` | `/tools` | Yes | All registered tools grouped by category |

## WebSocket Handlers

**Path:** `ws://host:port/sessions/{session_id}/ws?api_key=***`

- **Server → Client**: session_status, thinking, tool_call, tool_result, approval_request, response_chunk, response, error, session_closed
- **Client → Server**: user_input, approval, interrupt, close

## SDK Reference (`NexusSDK`)

- **Lifecycle**: `connect()`, `disconnect()`, `__aenter__`/`__aexit__`
- **Task operations**: `submit_task()`, `get_task_status()`, `get_result()`, `list_tasks()`, `cancel_task()`, `retry_task()`, `submit_batch()`
- **Polling**: `wait_for_result()`, `submit_and_wait()`
- **Utility**: `health_check()`, `list_workers()`, `list_tools()`

## NATS Bus (`AgentBus`)

- **Subjects**: `tasks.submit` (SDK publish → Worker subscribe)
- **KV Store**: `nexus_results` bucket for result storage
- **Retry**: Subscribe 3 attempts with exponential backoff; KV put 3 attempts; KV get single attempt with 5s timeout

## Database Schema

### Tables

**tasks**: id (PK), description, priority, status, created_at, updated_at, metadata_json

**results**: task_id (PK), success, data, error, completed_at, duration

**sessions**: id (PK), working_dir, memory_id, status, created_at, updated_at

**messages**: id (PK), session_id, role, content, tool_name, tool_args, created_at

### Repositories

**TaskRepository**: create_task, update_task_status, get_task_status, save_result, list_tasks, cancel_task, retry_task

**SessionRepository**: create_session, get_session, update_status, add_message, get_messages, list_sessions, rename_session, delete_session, fork_session

## Authentication System

- **API Key Auth** (`api_auth.py`): X-API-Key header → Fernet-encrypted keystore
- **AuthManager** (`auth.py`): PBKDF2-HMAC-SHA256 + Fernet (AES-128-CBC + HMAC-SHA256)
- **Keystore**: JSON dict of `{service: encrypted_key}`, mode 0o600

## TUI Component Inventory (`tui.py`)

### Widget Classes
- **SpinnerLabel**: Animated spinner + text label for status bar (10 FPS braille dots)
- **ApprovalModal**: Tool call approval dialog (Approve/Reject/Cancel)
- **ErrorModal**: Error display dialog (OK button) — *defined but never auto-triggered*
- **NexusApp**: Main TUI application (1168 lines)

### Keyboard Bindings
- `q`/`escape`: Quit
- `c`: Clear
- `ctrl+c`/`ctrl+u`: Interrupt
- `e`: Expand all
- `a`: Collapse all
- `ctrl+underscore`: Toggle auto-approve

### Slash Commands
`/help`, `/new`, `/clear`, `/expand`, `/collapse`, `/quit`, `/sessions`, `/status`, `/interrupt`, `/compact`, `/copy`, `/version`, `/tokens`, `/model`, `/threads`, `/theme`

### Color Themes (5)
midnight (emerald), ocean (sky), forest (green), sunset (orange), lavender (violet)

## CLI Command Reference (`cli.py`)

- `submit <task>` — Submit a task via SDK
- `run <task>` — Spawn isolated worker (--working-dir, --max-turns, --wall-time, --memory-mode, --acceptance, --model, --max-depth, --summary-only)
- `session <action> [id]` — Manage sessions (list/resume/fork/rename/delete)

## Web UI (`web_ui.py`)

- **Framework**: Gradio Blocks
- **Port**: 7860
- **Theme**: Industrial dark (orange-red #FF4B2B on charcoal #1A1A1A)
- **Components**: Task input, TRANSMIT TASK button, SDK status, system output
- **Limitation**: No streaming, no conversation history — simple submit-and-wait form

## Key Dependencies

| Category | Packages |
|----------|----------|
| **Agent** | deepagents, langchain-core, langgraph |
| **LLM** | google-generativeai, openai |
| **TUI** | textual, websockets |
| **API** | fastapi, uvicorn |
| **DB** | sqlalchemy (async), sqlite-vec |
| **Bus** | nats-py |
| **Auth** | cryptography (Fernet, PBKDF2) |
| **CLI** | click |
| **Web UI** | gradio |
| **Tools** | exa-py, tavily |
| **Utils** | pydantic, yaml |

## Test Coverage

| Test File | Scope |
|-----------|-------|
| test_agent_events.py | Agent event emission |
| test_agent_tools.py | Tool registration + policy |
| test_bus.py | NATS bus integration |
| test_cli_run.py | CLI commands |
| test_compaction.py | Context compaction pipeline |
| test_config.py | Configuration loading |
| test_db_sessions.py | Database session CRUD |
| test_e2e_production.py | End-to-end production tests |
| test_graph.py | LangGraph research workflow |
| test_graph_nodes.py | Individual graph nodes |
| test_memory.py | Memory operations |
| test_memory_files.py | File memory |
| test_memory_index.py | Vector/hybrid search |
| test_memory_tools.py | Memory tools |
| test_models.py | Data model validation |
| test_orchestration.py | Deep research orchestrator |
| test_server.py | FastAPI endpoints |
| test_session.py | Session lifecycle |
| test_session_memory.py | Session + memory integration |
| test_subagent.py | Sub-agent lifecycle |
| test_task_reaper.py | Task reaper |
| test_tui_streaming.py | TUI streaming |
| test_websocket.py | WebSocket endpoint |
| test_worker_pool.py | Worker pool |
| test_sdk.py | SDK operations |
| test_nats.py | NATS connectivity |
| contract_verification/ | Property-based contract tests |
| tools/ | Tool-specific tests |

## Cross-Module Dependency Map

```
config.py ◄──── settings singleton ────► agent.py, session.py, worker.py
    │                                        │
models.py ◄──── TaskSchema, TaskContract ──► worker.py, subagent.py
    │           ┌────────────────────────────┘
    │           │
    │           ▼
    │    session.py ◄──── Session, SessionManager
    │           │ uses
    │           ▼
    │    prompt_loader.py ◄──── load_nexus_prompt, inject_file_at_reference
    │           │ uses
    │           ▼
    │    agent.py ◄──── Agent, run_agent_task
    │           │ wraps
    │           ▼
    │    deepagents (external library)
    │
    ├──────────────────────────────────────────┐
    │                                          │
    ▼                                          ▼
orchestration.py ◄──── DeepResearchOrchestrator
    │                      │
    │                      │ uses
    │                      ▼
    │              nexusagent.llm.llm
    │              nexusagent.tools.research
    │
    │ called by
    ▼
graph.py ◄──── ResearchGraphState, create_research_graph
    │
    │ called by
    ▼
worker.py ◄──── NexusWorker, WorkerPool
    │
    │ uses
    ▼
subagent.py ◄──── SubAgentHandle
```

## Issues Summary

### Critical Issues

| # | File | Line | Issue |
|---|---|---|---|
| 1 | `worker.py` | 288 | Turn loop checks `result.get("status") == "complete"` but `run_agent_task` never returns a `"status"` key — loop always runs to `max_turns` |
| 2 | `graph.py` | 242-245 | Default checkpoint DB is `:memory:` — crash recovery is never active because `worker.py` never passes `db_path` |
| 3 | `orchestration.py` | 98-101 | `_fetch()` is a stub — research workflow has no actual page content, only snippets |

### Design Issues

| # | File | Line | Issue |
|---|---|---|---|
| 4 | `config.py` | 129 | Global `NEXUS_` env override can write to wrong nesting level |
| 5 | `config.py` | 164 | Singleton loaded at import time — untestable without monkeypatching |
| 6 | `agent.py` | 38-41 | `_ROLE_TOOLS` built at import time — late-registered tools are invisible |
| 7 | `agent.py` | 89-90 | Google model auto-prefix is a brittle string heuristic |
| 8 | `session.py` | 145-158 | `_build_session_history_context()` is a stub — no cross-session continuity |
| 9 | `subagent.py` | 154-161 | `_generate_summary()` is naive truncation, not real summarization |
| 10 | `worker.py` | 26-53 | Double-wrapped retry/circuit-breaker when `WorkerPool` calls `_run_agent_task` |
| 11 | `worker.py` | 41-44 | Research task detection uses hardcoded keywords |
| 12 | `prompt_loader.py` | 21 | `MAX_FILE_SIZE` hardcoded, config setting is dead code |
| 13 | `registry.py` | — | `_read_files` tracking is module-level global state, not thread-local |
| 14 | `sdk.py` / `server.py` | — | `submit_task()` duplicated in SDK and server |

### Security Issues

| # | Severity | Location | Issue |
|---|---|---|---|
| 1 | **High** | `git.py` | Shell injection: `_run_git()` uses `shell=True` with string interpolation |
| 2 | **Medium** | `git.py` | Commit message and file paths interpolated without escaping |
| 3 | **Medium** | `server.py` | CORS `allow_origins=["*"]` with `allow_credentials=True` |

### TUI-Specific Issues

| # | Issue |
|---|---|
| 1 | ErrorModal is never used — defined but never pushed |
| 2 | Theme cycling incomplete — CSS string is static |
| 3 | No reconnection logic on WS disconnect |
| 4 | No message persistence — conversation log is in-memory only |
| 5 | Queue uses `asyncio.Queue` for send but `list` for pending — two separate mechanisms |

---

*Auto-generated from source analysis. Merged from 4 CODEBASE_MAP files. 33 source files, 28 test files, 33+ tools cataloged, 9 API endpoints, 1 WebSocket handler, 15 SDK methods, 4 DB tables.*
