# Changelog

## 2026-07-19 — Phase 1 Runtime Foundation Delivered

### Runtime Foundation (Phase 1)
- **Runtime kernel** — `Runtime` class with 7-state lifecycle (created → initializing → running → pausing → paused → resuming → shutting_down → stopped)
- **Lifecycle model** — `LifecycleMixin` base class validating all state transitions
- **Dependency Injection** — `RuntimeContext` dataclass replacing 7 global ContextVars. Single container for config, tool_registry, tool_roles, session_id, workspace_root, policy_context, bus, db_manager, hook_manager, session_manager, worker_manager
- **ManagedSession** — Wraps existing sessions with lifecycle, health endpoint, ContextVar synchronization
- **ManagedWorker** — Wraps SubAgentHandle with lifecycle tracking, metadata, cancellation
- **ToolManager** — Runtime-backed tool initialization replacing module-level bools
- **Server lifespan adapter** — FastAPI lifespan integrating Runtime lifecycle with server startup/shutdown
- **CLI adapter** — `create_server_app()` wired into `__main__.py` with full settings, TLS config, uvloop
- **Backward compat shims** — All 7 global ContextVars preserved with runtime-first / fallback behavior
- **3 ADRs:** 0009 (lifecycle model), 0010 (dependency injection), 0011 (adapter strategy)
- **2 SPEC revisions:** SPEC-007 v1 → v2, synthesis v1 → v2
- **Dual audits:** Forward + reverse audit of spec before implementation
- **104 runtime tests** — 8 test files, all passing on Python 3.12+3.13

### Migration Framework
- Established 12-phase architectural migration plan ([Chief Architect Directive](docs/architecture/migration/CHIEF-ARCHITECT-DIRECTIVE.md))
- All 11 post-foundation phases specified: Task State Machine, Event-Driven Core, LangGraph Worker Runtime, Planner & Orchestrator, DAG Execution Engine, POL Control Plane, Capability Security, Memory Evolution, Observability, Production Readiness
- Phase 1 (Runtime Foundation) gating dependency cleared for all subsequent phases
- Migration tracking established in `docs/architecture/migration/TRACKING.md`

### Infrastructure
- **Worktree plugin** — Fixed 13 handler signatures (`args: dict` → `**kwargs`), added registration wrappers
- **Mistral/Vibe integration** — Rewrote `mistral.py` to use Vibe CLI programmatic mode (local + teleport)
- **Vibe Code Web** — Auth resolved (was 401), needs Vibe CLI API key to bypass rate limits
- **Jules dispatch** — Integrated PR #7 (CLI adapter), closed stale PRs #4, #6, #8, #9
- **SOUL.md** — Added Cloud Dispatch section (Jules/Mistral rules, worktree plugin reference)
- **Memory updates** — Jules limits (15/day, batch into 1), Vibe key requirements, worktree fix notes
- **`pytest-asyncio`** added to project dependencies (server install failed without it)

### Merged PRs
- **PR #7** — Wire Runtime-backed create_server_app into Server Entry Point (Jules)
- **PR #5** — ChatInput placeholder micro-UX + widget test modernization (Jules)

### Test Fixes
- ContextVar isolation fix — `test_global_migration.py` failures resolved with autouse reset fixture

## 2026-07-22 — Memory System v2 Complete

### Memory System v2
- **FileMemory** — Canonical file-based memory with YAML frontmatter, Git-backed auto-commits (`MemoryGitOps`)
- **HybridMemoryIndex** — SQLite FTS5 + sqlite-vec hybrid search with RRF fusion (70% vector / 30% keyword)
- **Auto-Extraction** — `MemoryExtractor`: regex-based fact extraction (decisions, preferences, errors, entities) after every turn
- **Dream Cycle** — `DreamCycle`: 4-phase background consolidation daemon (scan → patterns → consolidate → trim)
- **LLM Refinement** — `LLMRefinement`: optional LLM synthesis layer for higher-level insights from raw observations
- **SummaryDAG** — Hierarchical context compression (depth-0 leaf → depth-1 arc → depth-2 narrative)
- **ConsolidationEngine** — Duplicate detection, contradiction resolution, stale pruning
- **Bi-temporal Search** — `valid_from`/`valid_until` fields for time-based memory queries
- **TTL Enforcement** — Check-on-read + periodic `sweep_expired()` for automatic expiration
- **Provenance Tracking** — `source_session_id` and `derived_from` linking between memories
- **Memory Linking** — Auto-related field for linking related memories
- **Rate Limiter** — Token-bucket rate limiting (30 writes/min, 60 searches/min)
- **Self-Management Tools** — `memory_delete`, `memory_update`, `memory_list`, `memory_prune`
- **CLI Commands** — `memory health` and `memory stats` dashboard commands
- **Workspace-Scoped Memory** — Per-session memory directory, thread-local isolation
- **Session Integration** — `HybridMemoryManager` created on session init, `close()` on session end
- **17 new E2E tests** for memory system
- **Config fields** — `memory_extraction`, `memory_git`, `memory_compaction` sections added

### Workspace Scoping (P2-5 + P6-9)
- All agents (TUI/CLI/SDK/graph) now workspace-scoped
- `_setup_workspace_context()` sets path jail, thread-local `_ws_memory_dir`
- Worker pool passes `working_dir` + system prompt from `TaskContract`
- `NEXUS.md` loaded per-workspace
- `memory_dir` column added to sessions table
- `find_sessions_by_working_dir` query method

### Version System
- `version.py` — Single source of truth via `importlib.metadata`
- `/version` endpoint on FastAPI server
- `SERVER_VERSION` and `MIN_CLIENT_VERSION` in SDK
- `--check-server` and `--skip-version-check` CLI flags
- TUI preflight version check before WebSocket connect
- 13 new version tests

### Security Hardening (Phase 1)
- Fixed `test_runner.py` shell=True → shell=False
- Added auth to SDK NATS path
- Added auth to Web UI (Gradio)
- Fixed B039 mutable ContextVar default
- Fixed RUF012 mutable class attribute
- Added path jail to CLI working_dir
- Fixed WebSocket KeyError crashes
- Added rate limiting to API endpoints
- Security score: 7.2→8.5, Overall: 6.8→7.2

### Refactoring (Phases 1-7, 16-17)
- `infrastructure/utils.py` → `utils/` (retry, circuit)
- `widgets/theme.py` → `theme/` (colors, registry)
- `infrastructure/db.py` → `db/` (base, models, manager, repos)
- `widgets/messages.py` → `messages/` (user, assistant, tool, app, error, welcome)
- `tools/registry.py` → `registry/` (types, core, policy, search)
- `memory/memory_index.py` → `index/` (embeddings, index)
- `interfaces/tui.py` → `tui/` (app, websocket, streaming, input, formatters)
- `server/server.py` → `server/` (routes, websocket, __main__)
- `memory/memory.py` → `memory/` submodules (memory_item, memory_bank, memory_manager, hybrid_memory)
- `interfaces/tui.py` split: `tui_widgets.py`, `tui_formatters.py`

### Database
- `memory_dir` column added to sessions table
- `find_sessions_by_working_dir` query method
- `reinit()` now recreates engine + session (was silently using old engine)

### Config
- `yolo` field added to `AgentConfig`
- `memory_workspace` field added
- `memory_extraction`, `memory_git`, `memory_compaction` sections
- Default `db_path` corrected to match actual location

### Documentation
- `CODEBASE_MAP.md` — Complete source inventory updated
- `SEMANTIC_INDEX.md` — Data flows, state management, extension points updated
- `README.md` — Features, architecture, memory system v2
- `docs/ROADMAP/index.html` — Interactive audit dashboard
- ADRs 0001-0008
- Specs SPEC-001 to SPEC-006 (memory system)
- Memory system v2 plan, audit synthesis, comprehensive analysis

---

## 2026-06-11 — Codebase Cleanup & Security Hardening

### Security
- Scrubbed `.master.salt`, `.master.secret`, `keystore.json`, `tests/buggy_code.py` from git history via `git filter-repo`
- Added `.gitignore` patterns: `*.db`, `*.log`, `*.secret`, `*.salt`, `keystore*`, `tests/buggy_code.py`
- Force-pushed all branches to propagate rewritten history

### Cleanup
- Removed 10 root-level cruft files (spam, logs, stale TODOs, LLM exports)
- Deleted `tui_legacy.py` (1195L monolithic TUI, replaced by `widgets/` modular system)
- Removed `venv_fix/` (legacy venv, 286MB)
- Removed `docs/superpowers/`, `docs/collab/`, `docs/development/`, `docs/specs/`
- Consolidated `docs/guides/` into `docs/` root
- Pruned `docs/plans/` from 10 files to 2 (latest roadmap + recent sprint)
- Merged 4 CODEBASE_MAP files into single `docs/CODEBASE_MAP.md`
- Deleted `codemaps/`, `docs/api/`, `docs/api_reference/`
- Removed 7 worktrees + 10 feature branches (freed ~17MB)
- Fixed `main.py` entrypoint (was 4-line stub, now delegates to CLI)
- Removed empty `__init__.py` files (3)
- Fixed hardcoded `sys.path` in tests (2 files)

### Features
- Skills system — load custom skills from `~/.hermes/skills/` with YAML frontmatter
- Todo tools — `write_todos`/`read_todos` for multi-step task tracking
- Responsive TUI — `Breakpoint` enum, `NO_COLOR` detection, SIGWINCH handler
- Hooks system — `HookManager` with session-init, post-tool, error, subagent events
- Code review tool — static analysis (security, bugs, style, performance, AST)

### Test Fixes
- Fixed 14 pre-existing test failures
- Added DB init to `conftest.py` for server tests

### Documentation
- Updated `README.md` with current feature set and doc structure
- Updated `mkdocs.yml` nav to match consolidated layout
- Updated `docs/index.md` with new hierarchy
