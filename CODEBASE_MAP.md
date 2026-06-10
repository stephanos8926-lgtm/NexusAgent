# NexusAgent Codebase Map

> Generated: 2026-07-16
> Total source files: 33 (excluding venv/tests)
> Total test files: 28

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
├── codemaps/                  # Previous codemaps
├── tests/                     # 28 test files
└── src/nexusagent/           # Main source package
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

### TUI Layer

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `tui.py` | 824 | 4 | 1 | **Textual TUI**: NexusApp (824 lines, monolithic), SpinnerLabel, ApprovalModal, ErrorModal. WebSocket event loop, slash commands, tool output formatting. `_write_response_chunk()` and `_finalize_response()` added for streaming. |

### Data Layer

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `db.py` | 408 | 8 | 4 | **SQLAlchemy async ORM**: TaskModel, ResultModel, SessionModel, MessageModel. DatabaseManager, TaskRepository, SessionRepository (CRUD + fork + rename + delete). `db_manager`, `task_repo`, `session_repo` singletons. |
| `memory.py` | 442 | 4 | 2 | **HybridMemoryManager**: Memory (vector recall via embeddings), MemoryManager (SQLite + sqlite-vec), HybridMemoryManager (file canonical + index derived). Hash embeddings as fallback. |
| `memory_index.py` | ~350 | 2 | — | **HybridMemoryIndex**: FTS5 + sqlite-vec union merge search. Async embedding chain (Gemini→local→hash). |
| `memory_files.py` | 264 | 2 | — | **FileMemory**: File-based canonical memory. Topic-based entries with YAML frontmatter. Entity tracking, daily logs, MEMORY.md index. |

### Tools Layer (`tools/`)

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `registry.py` | 623 | 1 | 16 | **Tool registry**: ToolInfo dataclass, `@register_tool` decorator, policy enforcement (`require_policy`, `check_tool_access`), `tool_search()` with fuzzy matching + auto-correct. Role manifests. Thread-local policy context. |
| `register_all.py` | 613 | 0 | 5 | **Tool registration**: Registers all tools (fs, git, shell, test, patch, code_search, research, memory+, meta). `spawn_subagent`, `memory_search`, `memory_get`, `memory_write` as registered tools. |
| `fs.py` | 346 | 0 | 12 | **Filesystem tools**: read_file, write_file, edit_file (surgical), list_directory, read_multiple_files, write_multiple_files. Path jail (workspace root). Session-based read tracking (can't edit files you haven't read). |
| `shell.py` | 167 | 0 | 4 | **Shell tools**: run_shell, run_shell_streaming. shlex.split() for injection prevention. 1MB output truncation. Timeout support. |
| `git.py` | ~200 | 0 | 9 | **Git tools**: git_status, git_log, git_diff, git_show, git_branch, git_checkout_branch, git_commit, git_stash_push/pop/list. |
| `research.py` | 107 | 0 | 4 | **Research tools**: search_web (Exa primary + Tavily fallback), search_local_docs (ctx7 via subprocess). Requires API keys. |
| `patch.py` | ~100 | 0 | 1 | **Patch tool**: apply_patch for file patching. |
| `code_search.py` | ~100 | 0 | 3 | **Code search**: search_code, find_symbol, find_references. Uses ast-grep. |
| `test_runner.py` | ~100 | 0 | 2 | **Test tools**: run_tests, run_single_test. |

### Auth & Security

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `auth.py` | 129 | 1 | 0 | **AuthManager**: Fernet encryption for API keys. PBKDF2 key derivation. Keystore with encrypted service keys. |
| `api_auth.py` | 53 | 0 | 1 | **API auth**: FastAPI Security dependency via X-API-Key header. |

### CLI & SDK

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `cli.py` | 194 | 0 | 5 | **Click CLI**: `nexus-client` submit, `nexus run` (spawn worker), `nexus session` (list/resume/fork/rename/delete). |
| `sdk.py` | 206 | 1 | 0 | **NexusSDK**: High-level async SDK. submit_task, get_result, submit_and_wait, batch submit, list_tools. Uses NATS bus. |
| `web_ui.py` | 86 | 0 | 3 | **Gradio web UI**: Dark theme (#1A1A1A). create_ui(), handle_submit(). |

### Workers & Background

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `worker.py` | 311 | 2 | 2 | **NexusWorker + WorkerPool**: NATS subscriber with circuit breaker. Research→LangGraph, Code→deepagents routing. WorkerPool with SubAgentHandle, depth limiting. |
| `subagent.py` | 161 | 2 | 0 | **SubAgentHandle**: Status tracking (pending→running→completed/failed/cancelled). wait(), cancel(), result/summary properties. |
| `task_reaper.py` | 59 | 1 | 0 | **TaskReaper**: Background loop to mark stale PROCESSING tasks as FAILED. |

### Utilities & Misc

| File | Lines | Classes | Functions | Purpose |
|------|-------|---------|-----------|---------|
| `utils.py` | 354 | 3 | 2 | **Utils**: retry_with_backoff, retry_on_false decorators. CircuitBreaker (CLOSED/OPEN/HALF_OPEN). |
| `prompt_loader.py` | 242 | 2 | 5 | **Prompt loader**: NEXUS.md loading with @file chaining. Circular detection. Depth limits. inject_file_at_reference(). |
| `cli.py` | 194 | 0 | 5 | **Click CLI**: submit, run, session subcommands. |
| `memory_index.py` | ~350 | — | — | HybridMemoryIndex: FTS5 + sqlite-vec search |

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
