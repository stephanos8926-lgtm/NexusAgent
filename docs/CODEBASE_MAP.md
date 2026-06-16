# NexusAgent Codebase Map

> Generated: 2026-07-18
> Total source files: 82 (tests: 38)
> Total lines: ~13,400 (src), ~3,300 (tests)
> Last refactoring: Phases 1-7 complete + yolo config fix + TUI split + Phase 4D TUI bug fixes + version system
> Structure pattern: Domain-based subpackages with compat shims
> Test baseline: 528 pass / 15 fail (all pre-existing)

---

## Project Root

```
NexusAgent/
├── .hermes/               # Hermes Agent config
├── .env                   # API keys (GEMINI_API_KEY, OPENROUTER_API_KEY)
├── config/NEXUS.md        # Base system prompt
├── docs/                   # MkDocs documentation + research reports
│   ├── CODEBASE_MAP.md    # This file
│   ├── SEMANTIC_INDEX.md  # TUI semantic architecture index (917L)
│   └── research/          # Research reports
├── deployment/            # Deployment scripts
├── scripts/               # CLI tools (worktree-worker.py)
├── src/nexusagent/        # Main source package
└── tests/                 # 45 test files
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  CLI (click)                         │
│            nexus-client / nexus run                  │
├─────────────────────────────────────────────────────┤
│                Web UI (Gradio)                       │
├─────────────────────────────────────────────────────┤
│               FastAPI Server                         │
│        REST endpoints + WebSocket /ws               │
├──────────────┬──────────────┬───────────────────────┤
│   TUI        │   SDK        │   Worker Pool         │
│  (Textual)   │  (NexusSDK)  │  (NexusWorker)        │
├──────────────┴──────────────┴───────────────────────┤
│              Agent (deepagents wrapper)              │
│    Role-based tool access + policy enforcement       │
├──────────────────────────────────────────────────────┤
│              Tools Registry (35+ tools)              │
│  fs, git, shell, research, code_search, memory,      │
│  spawn_subagent, patch, test_runner, code_review    │
├──────────────────────────────────────────────────────┤
│   LLM Provider (Gemini + OpenRouter + Extensible)   │
│   NATS Bus · SQLite DB · Hybrid Memory              │
│   Auth (Fernet) · Session Manager · Compaction       │
└──────────────────────────────────────────────────────┘
```

---

## Source Package (`src/nexusagent/`)

### Directory Structure

```
nexusagent/
├── __init__.py                  # Package init (0L)
├── skills.py (127L)             # Skill system — load/inject skills from .hermes/skills/
├── task_reaper.py (59L)         # Stale task cleanup
│
│   ├── core/                        # Agent core
│   │   ├── __init__.py (6L)         # Re-exports from subpackages
│   │   ├── agent.py (134L)          # Agent wrapper (role-based, policy)
│   │   ├── orchestration.py (193L)  # DeepResearchOrchestrator
│   │   ├── graph.py (250L)          # LangGraph research graph
│   │   ├── subagent.py (161L)       # SubAgentHandle tracking
│   │   ├── session/                 # Session subpackage ✅ EXTRACTED
│   │   │   ├── __init__.py (10L)    # Re-exports Session, SessionManager
│   │   │   ├── session.py (391L)    # Session class (streaming, events, compaction)
│   │   │   ├── manager.py (154L)    # SessionManager (lifecycle, cache)
│   │   │   └── helpers.py (173L)    # _extract_agent_response, env context, git info
│   │   ├── session.py (6L)          # Compat shim → session/
│   │   ├── worker/                  # Worker subpackage ✅ EXTRACTED
│   │   │   ├── __init__.py (33L)    # Re-exports NexusWorker, WorkerPool, circuit breakers
│   │   │   ├── worker.py (330L)     # NexusWorker (NATS, health loop, handle_task)
│   │   │   ├── pool.py (177L)       # WorkerPool (concurrency, sub-agent spawning)
│   │   │   └── handler.py (83L)     # _run_agent_task, _run_research_workflow, circuit breakers
│   │   └── worker.py (6L)           # Compat shim → worker/
│
│   ├── tools/                       # Tool implementations
│   │   ├── registry.py (39L)        # Compat shim → registry/ subpackage
│   │   ├── register_all.py (494L)   # Static tool registration + MCP loader ✅ EXTRACTED
│   │   ├── tool_specs.py (465L)     # TOOL_SPECS data (30 static tool definitions)
│   │   ├── fs.py (188L)             # Filesystem tools (read/write/list) ✅ EXTRACTED
│   │   ├── fs_base.py (82L)         # Shared fs utilities (_resolve, _check_read, etc.)
│   │   ├── editor.py (113L)         # edit_file() — surgical line-range editing
│   │   ├── git.py (169L)            # Git tools
│   │   ├── shell.py (167L)          # Shell execution tools
│   │   ├── code_review/             # Code review subpackage ✅ EXTRACTED
│   │   │   ├── __init__.py (42L)    # Re-exports review_code, Issue, ReviewResult
│   │   │   ├── models.py (130L)     # Issue, ReviewResult, severity constants
│   │   │   ├── review_code.py (46L) # review_code() orchestrator
│   │   │   └── checks/              # Individual check modules
│   │   │       ├── security.py (73L)
│   │   │       ├── bugs.py (66L)
│   │   │       ├── style.py (51L)
│   │   │       ├── performance.py (31L)
│   │   │       └── ast_check.py (39L)
│   │   ├── code_review.py (6L)      # Compat shim → code_review/
│   │   ├── code_search.py (158L)    # Code search (ast-grep)
│   │   ├── research.py (204L)       # Web research
│   │   ├── test_runner.py (216L)    # Test execution
│   │   ├── patch.py (17L)           # File patching
│   │   ├── write_todos.py (118L)    # Todo write tool
│   │   └── registry/                # Registry subpackage ✅ EXTRACTED Phase 5
│       ├── __init__.py (62L)    # Re-exports from types, core, policy, search
│       ├── types.py (35L)       # ToolInfo dataclass
│       ├── core.py (113L)       # register_tool, get_tool_info, list_all_tools, auto_correct
│       ├── policy.py (285L)     # ROLE_MANIFESTS, policy enforcement
│       └── search.py (181L)     # tool_search, _format_tool_list
│
├── memory/                      # Hybrid memory system
│   ├── __init__.py (4L)         # Re-exports HybridMemoryManager
│   ├── memory.py (14L)          # Compat shim → submodules
│   ├── memory_item.py (50L)     # MemoryItem model + _hash_embed
│   ├── memory_bank.py (210L)    # Memory class (scoped SQLite bank)
│   ├── memory_manager.py (130L) # MemoryManager (lifecycle)
│   ├── hybrid_memory.py (120L)  # HybridMemoryManager (file + index)
│   ├── memory_index.py (34L)    # Compat shim → index/ subpackage
│   ├── memory_files.py (264L)   # File-based canonical memory
│   ├── compaction.py (233L)     # Context compaction pipeline
│   └── index/                   # Memory index subpackage ✅ EXTRACTED Phase 6
│       ├── __init__.py (32L)    # Re-exports EmbeddingProvider, HybridMemoryIndex
│       ├── embeddings.py (133L) # EmbeddingProvider + helpers
│       └── index.py (613L)      # HybridMemoryIndex (FTS5 + sqlite-vec)
│
├── widgets/                     # UI widgets
│   ├── __init__.py (32L)        # Widgets package init
│   ├── messages.py (25L)        # Compat shim → messages/ subpackage
│   ├── chat_input.py (215L)     # ChatInput widget
│   ├── status.py (367L)         # StatusBar + helpers
│   ├── theme.py (38L)           # Compat shim → theme/ subpackage
│   ├── messages/                # Messages subpackage ✅ EXTRACTED Phase 4
│   │   ├── __init__.py (25L)    # Re-exports all message classes
│   │   ├── user.py (41L)        # UserMessage
│   │   ├── assistant.py (130L)  # AssistantMessage (streaming, markdown)
│   │   ├── tool.py (192L)       # ToolCallMessage (collapsible, status)
│   │   ├── app.py (34L)         # AppMessage (system messages)
│   │   ├── error.py (34L)       # ErrorMessage
│   │   └── welcome.py (47L)     # WelcomeBanner
│   └── theme/                   # Theme subpackage ✅ EXTRACTED Phase 2
│       ├── __init__.py (43L)    # Re-exports ThemeColors, register_themes
│       ├── colors.py (273L)    # 7 themes, ThemeColors
│       └── registry.py (68L)   # CSS vars, register_themes
│
├── interfaces/                  # External interfaces
│   ├── __init__.py (4L)         # Interfaces package init
│   ├── tui/                      # TUI subpackage ✅ EXTRACTED
│   │   ├── __init__.py (46L)     # Re-exports NexusApp, main, widgets
│   │   ├── app.py (315L)         # NexusApp class (lifecycle, compose, actions)
│   │   ├── websocket.py (194L)   # ws_loop, version check, approval relay
│   │   ├── streaming.py (437L)   # handle_event, slash commands, theme/help
│   │   ├── input.py (47L)        # Chat input handling
│   │   └── formatters.py (12L)   # Re-exports from tui_formatters
│   ├── tui.py (40L)              # Compat shim → tui/
│   ├── tui_widgets.py (231L)   # SpinnerLabel, modals, SIGWINCH ✅ EXTRACTED Phase 7
│   ├── tui_formatters.py (296L)# render_markdown, all formatters ✅ EXTRACTED Phase 7
│   ├── cli.py (332L)            # Click CLI (--check-server, --skip-version-check)
│   └── web_ui.py (90L)          # Gradio web UI
│
│   ├── server/              # Server layer
│   ├── __init__.py (1L)         # Server package init
│   ├── __main__.py (12L)        # Entry point for `python3 -m nexusagent.server`
│   ├── server.py (100L)         # App factory (create_app) + lifespan + run()
│   ├── routes.py (230L)         # REST endpoints (register_routes pattern)
│   ├── websocket.py (160L)      # session_websocket handler
│   ├── sdk.py (210L)            # NexusSDK (SERVER_VERSION, MIN_CLIENT_VERSION)
│   └── version.py (42L)         # Single source of truth via importlib.metadata
│
├── infrastructure/              # Infrastructure
│   ├── __init__.py (1L)         # Infrastructure package init
│   ├── config.py (185L)         # Settings (3-tier loading)
│   ├── prompt_loader.py (139L)  # NEXUS.md loading (delegates to template_includes)
│   ├── template_includes.py (125L)  # @file chain resolution, circular detection
│   ├── bus.py (172L)            # NATS event bus
│   ├── auth.py (129L)           # Fernet keystore
│   ├── telemetry.py (160L)      # Telemetry
│   ├── api_auth.py (53L)        # FastAPI security
│   ├── db.py (35L)              # Compat shim → db/ subpackage
│   ├── utils.py (23L)           # Compat shim → utils/ subpackage
│   ├── db/                      # Database subpackage ✅ EXTRACTED Phase 3
│   │   ├── __init__.py (31L)    # Re-exports Base, models, repos
│   │   ├── base.py (9L)         # DeclarativeBase
│   │   ├── models.py (58L)      # TaskModel, ResultModel, SessionModel, MessageModel
│   │   ├── manager.py (98L)     # DatabaseManager (engine + session factory)
│   │   ├── task_repo.py (128L)  # TaskRepository (task/result CRUD)
│   │   └── session_repo.py (199L) # SessionRepository (session/message CRUD)
│   └── utils/                   # Utils subpackage ✅ EXTRACTED Phase 1
│       ├── __init__.py (16L)    # Re-exports retry, circuit
│       ├── retry.py (231L)      # retry_with_backoff, retry_on_false
│       └── circuit.py (140L)    # Circuit breaker
│
├── llm/                         # LLM abstraction
│   ├── __init__.py (1L)         # LLM package init
│   ├── llm.py (129L)            # LLMProvider (Gemini + OpenRouter)
│   └── models.py (175L)         # LLM request/response models
│
└── hooks/                       # Pre/post execution hooks
    ├── __init__.py (176L)       # HookManager, HookEvent, register_hook
    └── builtins.py (224L)       # Built-in hook functions
```

---

## Coupling Analysis

### Fan-In (imported by N files) — Higher = Riskier to Refactor

| Module | Fan-In | Notes |
|--------|--------|-------|
| `infrastructure` | 14 | Root package — imported by everyone |
| `llm` | 6 | Core dependency |
| `core` | 3 | Core domain |
| `widgets` | 3 | UI layer |
| `tools` | 2 | Tool system |
| `server` | 2 | Server layer |

### Extraction Candidates (large + low fan-in = safe)

| File | Lines | Fan-In | Fan-Out | Risk | Contains |
|------|-------|--------|---------|------|----------|
| `tools/register_all` | 728 | 0 | 1 | **LOW** | Tool registration calls |
| `memory/index/index` | 613 | 0 | 1 | **LOW** | FTS5+sqlite-vec index |
| `core/session` | 677 | 0 | 3 | **MED** | Session + SessionManager |
| `tools/code_review` | 367 | 0 | 0 | **LOW** | Code review tools |
| `widgets/status` | 367 | 0 | 0 | **LOW** | StatusBar + helpers |
| `server/server` | 354 | 0 | 3 | **MED** | Server is tightly coupled |
| `server/sdk` | 210 | 0 | 2 | **LOW** | NexusSDK (SERVER_VERSION, MIN_CLIENT_VERSION) |
| `server/version` | 10 | 0 | 0 | **LOW** | Version via importlib.metadata |
| `interfaces/tui` | 787 | 0 | 0 | **LOW** | TUI with widget-based arch + version preflight |
| `interfaces/cli` | 332 | 0 | 0 | **LOW** | CLI with --check-server flag |
| `memory/memory_files` | 264 | 0 | 0 | **LOW** | FileMemory |
| `core/graph` | 250 | 0 | 0 | **LOW** | LangGraph state machine |
| `tools/fs` | 343 | 0 | 0 | **LOW** | Filesystem tools |
| `infrastructure/prompt_loader` | 240 | 0 | 0 | **LOW** | Prompt loading |
| `infrastructure/db/session_repo` | 199 | 0 | 0 | **LOW** | SessionRepository |
| `tools/registry/policy` | 285 | 0 | 0 | **LOW** | Policy enforcement |
| `hooks/builtins` | 224 | 0 | 0 | **LOW** | Built-in hooks |
| `hooks/__init__` | 176 | 0 | 1 | **LOW** | HookManager, HookEvent |
| `llm/models` | 175 | 0 | 0 | **LOW** | Pydantic models |
| `core/subagent` | 161 | 0 | 0 | **LOW** | SubAgentHandle |
| `infrastructure/telemetry` | 160 | 0 | 0 | **LOW** | TelemetryManager |
| `tools/code_search` | 158 | 0 | 0 | **LOW** | Code search |
| `infrastructure/utils/circuit` | 140 | 0 | 0 | **LOW** | Circuit breaker |
| `core/agent` | 134 | 0 | 2 | **MED** | Agent wrapper |
| `llm/llm` | 129 | 0 | 0 | **LOW** | LLMProvider |
| `tools/write_todos` | 118 | 0 | 0 | **LOW** | Todo tools |
| `tools/registry/core` | 113 | 0 | 0 | **LOW** | register_tool, list_all_tools |

### Higher Risk (fan-out > 3 — many modules depend on these)

| File | Lines | Fan-In | Fan-Out | Risk |
|------|-------|--------|---------|------|
| core/session | 677 | 0 | 3 | Session is core to TUI + Server + Worker |
| core/worker | 304 | 0 | 3 | Worker is used by multiple consumers |
| server/server | 354 | 0 | 3 | Server is tightly coupled |
| core/agent | 134 | 0 | 2 | Agent is used by Worker + Orchestration |

---

## Completed Refactoring

### Phase 1: `infrastructure/utils.py` → `infrastructure/utils/` ✅
- Extracted: `retry.py` (231L), `circuit.py` (140L)
- Old file: Compat shim (23L)
- Commit: `f260eee`

### Phase 2: `widgets/theme.py` → `widgets/theme/` ✅
- Extracted: `colors.py` (273L), `registry.py` (68L)
- Old file: Compat shim (38L)
- Commit: `bfe2723`

### Phase 3: `infrastructure/db.py` → `infrastructure/db/` ✅
- Extracted: `base.py` (9L), `models.py` (58L), `manager.py` (98L), `task_repo.py` (128L), `session_repo.py` (199L)
- Old file: Compat shim (35L)
- Commit: `83aef0f`
- Fixes: `reinit()` now recreates engine + session (was silently using old engine)

### Phase 4: `widgets/messages.py` → `widgets/messages/` ✅
- Extracted: `user.py` (41L), `assistant.py` (130L), `tool.py` (192L), `app.py` (34L), `error.py` (34L), `welcome.py` (47L)
- Old file: Compat shim (25L)
- Commit: `10e76dc`
- Cleaned: Removed 3 dead regex constants, dead Vertical import, redundant datetime import

### Phase 5: `tools/registry.py` → `tools/registry/` ✅
- Extracted: `types.py` (35L), `core.py` (113L), `policy.py` (285L), `search.py` (181L)
- Old file: Compat shim (39L)
- Commit: `a076952`

### Phase 6: `memory/memory_index.py` → `memory/index/` ✅
- Extracted: `embeddings.py` (133L), `index.py` (613L)
- Old file: Compat shim (34L)
- Commit: `db21f4c`

### Phase 7: `interfaces/tui.py` split ✅
- Extracted: `tui_widgets.py` (231L), `tui_formatters.py` (296L)
- Old file: Reduced from 1433L → 953L
- Commit: `74fe4f9`

### Phase 16: `server/server.py` → `server/` subpackage ✅
- Extracted: `routes.py` (230L), `websocket.py` (160L), `__main__.py` (12L)
- `server.py`: Reduced from 508L → 100L (app factory + lifespan)
- Commit: `b9ef9e6`

### Phase 17: `memory/memory.py` → `memory/` submodules ✅
- Extracted: `memory_item.py` (50L), `memory_bank.py` (210L), `memory_manager.py` (130L), `hybrid_memory.py` (120L)
- `memory.py`: Reduced from 474L → 14L (compat shim)
- Commit: `086afba`

### Config Fix: `yolo` field added ✅
- Added missing `yolo` field to `AgentConfig`
- Commit: `a290c93`

### Phase 4D: TUI bug fixes ✅
- Refactored to widget-based architecture (tui.py: 953L → 787L)
- Fixed Enter key handling in ChatInput
- Added httpx-based async version preflight check before WebSocket connect
- Commit: TBD

### Version System ✅
- Added `server/version.py` — single source of truth via `importlib.metadata`
- Added `/version` endpoint to FastAPI server
- Added `SERVER_VERSION` and `MIN_CLIENT_VERSION` to SDK
- Added `--check-server` and `--skip-version-check` flags to CLI
- Added 43 new tests: `test_version.py` (8), `test_server_version.py` (5)
- Test baseline: 528 pass / 15 fail

---

## Refactoring Pattern (Established)

For each extraction:
1. Read target file completely (all lines)
2. Create `subpackage/` directory with `__init__.py`
3. Split into focused modules by concern (max 500L per module)
4. Old file becomes compat shim: `from nexusagent.X import *`
5. No behavior changes — all existing imports preserved
6. Test gate: 528+ pass / 15 fail baseline unchanged
7. Commit: `refactor: extract X into Y/ subpackage`
8. Update CODEBASE_MAP.md
