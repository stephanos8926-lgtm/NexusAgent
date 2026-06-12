# NexusAgent Codebase Map

> Generated: 2026-07-18
> Total source files: 81 (tests: 45)
> Total lines: ~13,400 (src), ~3,100 (tests)
> Last refactoring: Phases 1-7 complete + yolo config fix + TUI split
> Structure pattern: Domain-based subpackages with compat shims

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
├── core/                        # Agent core (session, agent, orchestration, graph)
│   ├── __init__.py (6L)         # Re-exports Session, SessionManager, SubAgentStatus, WorkerPool
│   ├── agent.py (134L)          # Agent wrapper (role-based, policy)
│   ├── worker.py (304L)         # NexusWorker + WorkerPool
│   ├── session.py (677L)        # Session + SessionManager ← MONOLITH
│   ├── orchestration.py (193L)  # DeepResearchOrchestrator
│   ├── graph.py (250L)          # LangGraph research graph
│   └── subagent.py (161L)       # SubAgentHandle tracking
│
├── tools/                       # Tool implementations
│   ├── registry.py (39L)        # Compat shim → registry/ subpackage
│   ├── register_all.py (728L)   # Registration calls ← MONOLITH
│   ├── fs.py (343L)             # Filesystem tools
│   ├── git.py (169L)            # Git tools
│   ├── shell.py (167L)          # Shell execution tools
│   ├── code_review.py (367L)    # Code review tools
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
├── memory/                      # Hybrid memory system
│   ├── __init__.py (4L)         # Re-exports HybridMemoryManager
│   ├── memory.py (436L)         # Memory, MemoryManager, HybridMemoryManager
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
│   ├── tui.py (953L)            # Textual TUI — NexusApp (split from 1433L)
│   ├── tui_widgets.py (231L)   # SpinnerLabel, modals, SIGWINCH ✅ EXTRACTED Phase 7
│   ├── tui_formatters.py (296L)# render_markdown, all formatters ✅ EXTRACTED Phase 7
│   ├── cli.py (248L)            # Click CLI
│   └── web_ui.py (90L)          # Gradio web UI
│
├── server/                      # Server layer
│   ├── __init__.py (1L)         # Server package init
│   ├── server.py (354L)         # FastAPI + WebSocket
│   └── sdk.py (210L)            # NexusSDK
│
├── infrastructure/              # Infrastructure
│   ├── __init__.py (1L)         # Infrastructure package init
│   ├── config.py (185L)         # Settings (3-tier loading)
│   ├── prompt_loader.py (240L)  # NEXUS.md + @file injection
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
| `server/server` | 354 | 0 | 3 | **MED** | FastAPI + WebSocket |
| `tools/fs` | 343 | 0 | 0 | **LOW** | Filesystem tools |
| `interfaces/tui_formatters` | 296 | 0 | 0 | **LOW** | All formatters, markdown renderers |
| `core/worker` | 304 | 0 | 3 | **MED** | NexusWorker + WorkerPool |
| `interfaces/tui_widgets` | 231 | 0 | 0 | **LOW** | SpinnerLabel, modals, SIGWINCH |
| `memory/compaction` | 233 | 0 | 0 | **LOW** | Compaction pipeline |
| `tools/research` | 204 | 0 | 0 | **LOW** | Research tools |
| `tools/test_runner` | 216 | 0 | 0 | **LOW** | Test runner |
| `widgets/chat_input` | 215 | 0 | 0 | **LOW** | ChatInput widget |
| `server/sdk` | 210 | 0 | 2 | **LOW** | NexusSDK |
| `memory/memory_files` | 264 | 0 | 0 | **LOW** | FileMemory |
| `core/graph` | 250 | 0 | 0 | **LOW** | LangGraph state machine |
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

### Config Fix: `yolo` field added ✅
- Added missing `yolo` field to `AgentConfig`
- Commit: `a290c93`

---

## Refactoring Pattern (Established)

For each extraction:
1. Read target file completely (all lines)
2. Create `subpackage/` directory with `__init__.py`
3. Split into focused modules by concern (max 500L per module)
4. Old file becomes compat shim: `from nexusagent.X import *`
5. No behavior changes — all existing imports preserved
6. Test gate: 453+ pass / 20 fail baseline unchanged
7. Commit: `refactor: extract X into Y/ subpackage`
8. Update CODEBASE_MAP.md
