# NexusAgent Codebase Map

> Generated: 2026-07-22
> Total source files: 106 Python modules (tests: 52)
> Total lines: ~18,500 (src), ~9,500 (tests)
> Last refactoring: Phases 1-7 complete + memory system v2 + workspace scoping + version system
> Structure pattern: Domain-based subpackages with compat shims
> Test baseline: 680 pass / 11 pre-existing fail

---

## Project Root

```
NexusAgent/
├── .hermes/               # Hermes Agent config
├── .env                   # API keys (GEMINI_API_KEY, OPENROUTER_API_KEY)
├── config/NEXUS.md        # Base system prompt
├── docs/                  # Documentation
│   ├── CODEBASE_MAP.md   # This file
│   ├── SEMANTIC_INDEX.md # Data flows, state management, extension points
│   └── research/         # Research reports
├── deployment/            # Deployment scripts
├── scripts/               # CLI tools (worktree-worker.py)
├── src/nexusagent/        # Main source package
└── tests/                 # 52 test files
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
│              Tools Registry (30+ tools)              │
│  fs, git, shell, research, code_search, memory,      │
│  spawn_subagent, patch, test_runner, code_review    │
├──────────────────────────────────────────────────────┤
│   LLM Provider (Gemini + OpenRouter + Extensible)   │
│   NATS Bus · SQLite DB · Hybrid Memory v2           │
│   Auth (Fernet) · Session Manager · Compaction       │
└──────────────────────────────────────────────────────┘
```

---

## Source Package (`src/nexusagent/`)

### Directory Structure

```
nexusagent/
├── __init__.py                  # Package init
├── version.py (10L)             # Single source of truth via importlib.metadata
├── skills.py (127L)             # Skill system — load/inject skills from .hermes/skills/
├── task_reaper.py (59L)         # Stale task cleanup
│
├── core/                        # Agent core
│   ├── __init__.py (6L)         # Re-exports from subpackages
│   ├── agent.py (134L)          # Agent wrapper (role-based, policy)
│   ├── orchestration.py (193L)  # DeepResearchOrchestrator
│   ├── graph.py (250L)          # LangGraph research graph
│   ├── subagent.py (161L)       # SubAgentHandle tracking
│   ├── session/                 # Session subpackage ✅ EXTRACTED
│   │   ├── __init__.py (10L)    # Re-exports Session, SessionManager
│   │   ├── session.py (391L)    # Session class (streaming, events, compaction)
│   │   ├── manager.py (154L)    # SessionManager (lifecycle, cache, memory_dir)
│   │   └── helpers.py (173L)    # _extract_agent_response, env context, git info
│   ├── session.py (6L)          # Compat shim → session/
│   ├── worker/                  # Worker subpackage ✅ EXTRACTED
│   │   ├── __init__.py (33L)    # Re-exports NexusWorker, WorkerPool, circuit breakers
│   │   ├── worker.py (330L)     # NexusWorker (NATS, health loop, handle_task)
│   │   ├── pool.py (177L)       # WorkerPool (concurrency, sub-agent spawning)
│   │   └── handler.py (83L)     # _run_agent_task, _run_research_workflow, circuit breakers
│   └── worker.py (6L)           # Compat shim → worker/
│
├── tools/                       # Tool implementations
│   ├── registry.py (39L)        # Compat shim → registry/ subpackage
│   ├── register_all.py (494L)   # Static tool registration + MCP loader ✅ EXTRACTED
│   ├── tool_specs.py (469L)     # TOOL_SPECS data (30+ static tool definitions)
│   ├── fs.py (188L)             # Filesystem tools (read/write/list) ✅ EXTRACTED
│   ├── fs_base.py (91L)         # Shared fs utilities (_resolve, _check_read, etc.)
│   ├── editor.py (113L)         # edit_file() — surgical line-range editing
│   ├── git.py (169L)            # Git tools
│   ├── shell.py (167L)          # Shell execution tools
│   ├── code_review/             # Code review subpackage ✅ EXTRACTED
│   │   ├── __init__.py (42L)    # Re-exports review_code, Issue, ReviewResult
│   │   ├── models.py (130L)     # Issue, ReviewResult, severity constants
│   │   ├── review_code.py (46L) # review_code() orchestrator
│   │   └── checks/              # Individual check modules
│   │       ├── security.py (73L)
│   │       ├── bugs.py (66L)
│   │       ├── style.py (51L)
│   │       ├── performance.py (31L)
│   │       └── ast_check.py (39L)
│   ├── code_review.py (6L)      # Compat shim → code_review/
│   ├── code_search.py (158L)    # Code search (ast-grep)
│   ├── research.py (204L)       # Web research
│   ├── test_runner.py (216L)    # Test execution
│   ├── patch.py (17L)           # File patching
│   ├── write_todos.py (118L)    # Todo write tool
│   └── registry/                # Registry subpackage ✅ EXTRACTED Phase 5
│       ├── __init__.py (62L)    # Re-exports from types, core, policy, search
│       ├── types.py (35L)       # ToolInfo dataclass
│       ├── core.py (113L)       # register_tool, get_tool_info, list_all_tools, auto_correct
│       ├── policy.py (285L)     # ROLE_MANIFESTS, policy enforcement
│       └── search.py (181L)     # tool_search, _format_tool_list
│
├── memory/                      # Hybrid memory system v2
│   ├── __init__.py (4L)         # Re-exports HybridMemoryManager
│   ├── memory.py (31L)          # Compat shim → submodules
│   ├── memory_item.py (48L)     # MemoryItem model + _hash_embed
│   ├── memory_bank.py (203L)    # Memory class (scoped SQLite bank)
│   ├── memory_manager.py (119L) # MemoryManager (lifecycle)
│   ├── hybrid_memory.py (236L)  # HybridMemoryManager (file + index)
│   ├── memory_files.py (638L)   # FileMemory (canonical, git-backed)
│   ├── memory_index.py (34L)    # Compat shim → index/ subpackage
│   ├── compaction.py (309L)     # CompactionPipeline (graduated + DAG)
│   ├── dag.py (442L)            # SummaryDAG (hierarchical compression) ✅ NEW
│   ├── dream.py (848L)          # DreamCycle (4-phase consolidation) ✅ NEW
│   ├── extraction.py (201L)     # MemoryExtractor (regex-based auto-extraction) ✅ NEW
│   ├── git_ops.py (146L)        # MemoryGitOps (auto-commit after writes) ✅ NEW
│   ├── rate_limiter.py (108L)   # MemoryRateLimiter (token-bucket) ✅ NEW
│   ├── consolidation.py (158L)  # ConsolidationEngine (duplicate/contradiction detection) ✅ NEW
│   ├── refinement.py (375L)     # LLMRefinement (LLM synthesis of observations) ✅ NEW
│   └── index/                   # Memory index subpackage ✅ EXTRACTED Phase 6
│       ├── __init__.py (32L)    # Re-exports EmbeddingProvider, HybridMemoryIndex
│       ├── embeddings.py (164L) # EmbeddingProvider + helpers
│       └── index.py (692L)      # HybridMemoryIndex (FTS5 + sqlite-vec)
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
│   ├── tui/                     # TUI subpackage ✅ EXTRACTED
│   │   ├── __init__.py (46L)     # Re-exports NexusApp, main, widgets
│   │   ├── app.py (354L)         # NexusApp class (lifecycle, compose, actions)
│   │   ├── websocket.py (198L)   # ws_loop, version check, approval relay
│   │   ├── streaming.py (456L)   # handle_event, slash commands, theme/help
│   │   ├── input.py (50L)        # Chat input handling
│   │   └── formatters.py (12L)   # Re-exports from tui_formatters
│   ├── tui.py (40L)              # Compat shim → tui/
│   ├── tui_widgets.py (231L)   # SpinnerLabel, modals, SIGWINCH ✅ EXTRACTED Phase 7
│   ├── tui_formatters.py (296L)# render_markdown, all formatters ✅ EXTRACTED Phase 7
│   ├── cli.py (332L)            # Click CLI (--check-server, --skip-version-check)
│   └── web_ui.py (90L)          # Gradio web UI
│
├── server/                      # Server layer
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
│   ├── config.py (185L)         # ConfigSchema (Pydantic settings)
│   ├── prompt_loader.py (139L)  # NEXUS.md loading (delegates to template_includes)
│   ├── template_includes.py (125L)  # @file chain resolution, circular detection
│   ├── bus.py (172L)            # NATS event bus
│   ├── auth.py (129L)           # Fernet keystore
│   ├── api_auth.py (53L)        # FastAPI security
│   ├── rate_limit.py (122L)     # Rate limiting middleware ✅ NEW
│   ├── telemetry.py (160L)      # Telemetry
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
| `infrastructure/config` | 14 | Root package — imported by everyone |
| `llm/models` | 6 | Core dependency |
| `core/agent` | 3 | Core domain |
| `memory/hybrid_memory` | 3 | Memory system v2 core |
| `widgets` | 3 | UI layer |
| `tools` | 2 | Tool system |
| `server` | 2 | Server layer |

### Remaining Extraction Candidates

| File | Lines | Fan-In | Fan-Out | Risk | Contains |
|------|-------|--------|---------|------|----------|
| `memory/memory_files` | 638 | 0 | 1 | **MED** | FileMemory — large but self-contained |
| `memory/dream` | 848 | 0 | 2 | **MED** | DreamCycle — 4-phase consolidation |
| `memory/dag` | 442 | 0 | 0 | **LOW** | SummaryDAG — hierarchical compression |
| `memory/refinement` | 375 | 0 | 0 | **LOW** | LLMRefinement |
| `widgets/status` | 367 | 0 | 0 | **LOW** | StatusBar + helpers |
| `interfaces/cli` | 332 | 0 | 0 | **LOW** | CLI with --check-server flag |
| `tools/registry/policy` | 285 | 0 | 0 | **LOW** | Policy enforcement |
| `hooks/builtins` | 224 | 0 | 0 | **LOW** | Built-in hooks |
| `llm/models` | 175 | 0 | 0 | **LOW** | Pydantic models |

---

## Completed Refactoring

### Phase 1: `infrastructure/utils.py` → `infrastructure/utils/` ✅
- Extracted: `retry.py` (231L), `circuit.py` (140L)
- Old file: Compat shim (23L)

### Phase 2: `widgets/theme.py` → `widgets/theme/` ✅
- Extracted: `colors.py` (273L), `registry.py` (68L)
- Old file: Compat shim (38L)

### Phase 3: `infrastructure/db.py` → `infrastructure/db/` ✅
- Extracted: `base.py`, `models.py`, `manager.py`, `task_repo.py`, `session_repo.py`
- Old file: Compat shim (35L)

### Phase 4: `widgets/messages.py` → `widgets/messages/` ✅
- Extracted: `user.py`, `assistant.py`, `tool.py`, `app.py`, `error.py`, `welcome.py`

### Phase 5: `tools/registry.py` → `tools/registry/` ✅
- Extracted: `types.py`, `core.py`, `policy.py`, `search.py`

### Phase 6: `memory/memory_index.py` → `memory/index/` ✅
- Extracted: `embeddings.py`, `index.py`

### Phase 7: `interfaces/tui.py` split ✅
- Extracted: `tui_widgets.py` (231L), `tui_formatters.py` (296L)
- Old file: Reduced from 1433L → compat shim

### Phase 16: `server/server.py` → `server/` subpackage ✅
- Extracted: `routes.py`, `websocket.py`, `__main__.py`
- `server.py`: Reduced to app factory + lifespan

### Phase 17: `memory/memory.py` → `memory/` submodules ✅
- Extracted: `memory_item.py`, `memory_bank.py`, `memory_manager.py`, `hybrid_memory.py`

### Memory System v2 — New Modules ✅
- `memory/dag.py` — SummaryDAG (hierarchical compression)
- `memory/dream.py` — DreamCycle (4-phase consolidation daemon)
- `memory/extraction.py` — MemoryExtractor (regex-based auto-extraction)
- `memory/git_ops.py` — MemoryGitOps (auto-commit after writes)
- `memory/rate_limiter.py` — MemoryRateLimiter (token-bucket)
- `memory/consolidation.py` — ConsolidationEngine (duplicate/contradiction detection)
- `memory/refinement.py` — LLMRefinement (LLM synthesis of observations)

### Version System ✅
- `version.py` — Single source of truth via `importlib.metadata`
- `/version` endpoint, `SERVER_VERSION` + `MIN_CLIENT_VERSION` in SDK
- `--check-server` and `--skip-version-check` CLI flags

### Workspace Scoping (P2-5 + P6-9) ✅
- All agents (TUI/CLI/SDK/graph) now workspace-scoped
- `_setup_workspace_context()` sets path jail, thread-local `_ws_memory_dir`
- Worker pool passes `working_dir` + system prompt from TaskContract

### Security Hardening ✅
- 13 critical/high fixes across 4 waves
- Fixed: shell=True, mutable defaults, path jail, WebSocket KeyError, API key in URL
- Security score: 7.2→8.5, Overall: 6.8→7.2

---

## Refactoring Pattern (Established)

For each extraction:
1. Read target file completely (all lines)
2. Create `subpackage/` directory with `__init__.py`
3. Split into focused modules by concern (max 500L per module)
4. Old file becomes compat shim: `from nexusagent.X import *`
5. No behavior changes — all existing imports preserved
6. Test gate: 680+ pass / 11 fail baseline unchanged
7. Commit: `refactor: extract X into Y/ subpackage`
8. Update CODEBASE_MAP.md
