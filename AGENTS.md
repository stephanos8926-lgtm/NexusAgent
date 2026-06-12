# AGENTS.md — NexusAgent Project Knowledge Base

> Last updated: 2026-07-18
> Maintained by: OWL (Lucien)
> Purpose: Critical project knowledge for any agent working on this codebase

---

## Project Overview

NexusAgent is a production-grade AI coding agent platform. It combines an LLM-powered agent (via `deepagents` / LangGraph) with a NATS-backed task orchestration system, a Textual TUI, a FastAPI WebSocket server, and a hybrid file+vector memory system.

**Language:** Python 3.13+ | **Package:** `nexusagent` (src layout) | **Tests:** pytest (475 pass / 19 pre-existing fail)

---

## Critical Reference Documents

| Document | Location | Purpose |
|----------|----------|---------|
| **Codebase Map** | `docs/CODEBASE_MAP.md` | Module structure, fan-in/fan-out, extraction candidates |
| **Semantic Index** | `docs/SEMANTIC_INDEX.md` | Data flows, state management, extension points, tech debt |
| **Refactoring Plan** | `docs/REFACTORING_PLAN.md` | 14-item prioritized refactoring roadmap |
| **State** | `docs/STATE.md` | Module-by-module inventory (⚠️ partially outdated) |
| **Compliance** | `docs/DOC_COMPLIANCE.md` | Documentation audit and gap analysis |
| **ADRs** | `docs/adrs/` | Architecture decision records (0001-0005) |
| **Config** | `config/nexusagent.yaml` | Runtime configuration |

---

## Repository Structure

```
NexusAgent/
├── src/nexusagent/          # Main source (src layout)
│   ├── core/                # Agent, session, worker, subagent, graph
│   ├── tools/               # 25+ tools + registry subpackage
│   │   └── registry/        # types, core, policy, search (extracted Phase 5)
│   ├── memory/              # Hybrid memory system
│   │   ├── memory.py       # Memory, MemoryManager, HybridMemoryManager
│   │   ├── memory_files.py  # FileMemory (canonical)
│   │   ├── memory_index.py  # Compat shim → memory/index/
│   │   ├── index/           # embeddings.py, index.py (extracted Phase 6)
│   │   └── compaction.py    # CompactionPipeline
│   ├── widgets/             # TUI widgets
│   │   ├── messages/        # 6 message widget classes (extracted Phase 4)
│   │   ├── theme/           # colors.py, registry.py (extracted Phase 2)
│   │   ├── chat_input.py    # ChatInput widget
│   │   └── status.py        # StatusBar, ModelLabel
│   ├── interfaces/          # External interfaces
│   │   ├── tui.py           # NexusApp (953L, refactored 2026-07-18)
│   │   ├── tui_widgets.py   # SpinnerLabel, modals, SIGWINCH (extracted)
│   │   ├── tui_formatters.py # render_markdown, all formatters (extracted)
│   │   ├── cli.py           # Click CLI
│   │   └── web_ui.py        # Gradio web UI
│   ├── infrastructure/      # Config, DB, bus, auth, utilities
│   │   ├── config.py        # ConfigSchema (Pydantic settings)
│   │   ├── db/              # SQLAlchemy async DB (extracted Phase 3)
│   │   ├── utils/           # retry.py, circuit.py (extracted Phase 1)
│   │   ├── bus.py           # NATS JetStream
│   │   ├── auth.py          # Fernet keystore
│   │   └── prompt_loader.py # NEXUS.md loader
│   ├── server/              # FastAPI + WebSocket
│   ├── llm/                 # Multi-provider LLM bridge
│   └── hooks/               # Pre/post execution hooks
├── tests/                   # 31 test files
├── docs/                    # Documentation (see reference docs above)
├── scripts/                 # CLI tools (worktree-worker.py)
├── config/
│   └── NEXUS.md             # Base system prompt
└── pyproject.toml           # Project metadata + dependencies
```

---

## Refactoring History (2026-07-18)

Phases 1-7 completed the initial structural refactoring:

| Phase | What | Commit | Pattern |
|-------|------|--------|---------|
| 1 | `infrastructure/utils.py` → `utils/` | `f260eee` | retry.py + circuit.py |
| 2 | `widgets/theme.py` → `theme/` | `bfe2723` | colors.py + registry.py |
| 3 | `infrastructure/db.py` → `db/` | `83aef0f` | 5 files (base, models, manager, repos) |
| 4 | `widgets/messages.py` → `messages/` | `10e76dc` | 6 message widget classes |
| 5 | `tools/registry.py` → `registry/` | `a076952` | types, core, policy, search |
| 6 | `memory/memory_index.py` → `index/` | `db21f4c` | embeddings.py + index.py |
| 7 | `memory/memory.py` DRY fix | `7bdb142` | Import shared constants from memory.index |
| — | `interfaces/tui.py` split | `74fe4f9` | tui.py + tui_widgets.py + tui_formatters.py |
| — | `yolo` field added to AgentConfig | `a290c93` | Fix missing config field |

**Established pattern:** Extract to subpackage → old file becomes compat shim → test → commit → update CODEBASE_MAP.md

---

## Known Quirks & Gotchas

### Import System
- **Src layout**: Package is in `src/nexusagent/`. Always use `PYTHONPATH=src` or run from repo root.
- **Compat shims**: Old files (utils.py, theme.py, db.py, messages.py, registry.py, memory_index.py) still exist as re-export shims. New code should import from subpackages directly.
- **Circular imports**: `tools/registry/core.py` imports `policy.py` with delayed import to avoid circular dependency. Don't restructure without understanding the import order.

### Config
- **Three-tier loading**: `config/nexusagent.yaml` → `NEXUS_*` env vars → Pydantic defaults
- **Env var format**: `NEXUS_AGENT__DEFAULT_MODEL=...` (double underscore = nested key)
- **`yolo` field**: Added 2026-07-18. `settings.agent.yolo` controls auto-approve default in TUI.

### TUI
- **Textual framework**: Uses Textual (not Rich directly). Widgets extend `Static`, `Horizontal`, etc.
- **CSS variables**: Theme colors use `$surface`, `$text`, `$primary` etc. defined by `register_themes()`.
- **NO_COLOR**: Respects https://no-color.org. Check `NO_COLOR` env var before adding color.
- **SIGWINCH**: Resize handler installed in `on_mount()`. Uses debounce (0.2s) to avoid excessive re-renders.
- **Streaming**: `_write_response_chunk()` accumulates tokens in `_streaming_response` string. `_finalize_response()` writes to log and clears widget.

### Memory System
- **Two systems coexist**: Old SQLite `Memory` class (in `memory.py`) and new file-based `HybridMemoryManager` (also in `memory.py`). Session uses the hybrid system.
- **Embedding fallback chain**: Gemini API → local sentence-transformers → SHA256 hash (deterministic, low quality)
- **sqlite-vec**: Virtual table for vector search. Requires `sqlite_vec.load(conn)` at startup.

### Testing
- **Baseline**: 475 pass / 19 fail (all pre-existing). Zero regressions allowed.
- **Run command**: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=short`
- **Timeout**: Full suite takes ~100s. Use `timeout 120` for safety.
- **Pre-existing failures**: `test_orchestration.py` (module path issues), `test_tui_responsive.py` (wrong mock paths), `test_e2e_production.py` (WebSocket dependency)

### Build & Deploy
- **No pyproject.toml build config**: Uses setuptools with `src/` layout.
- **Dependencies**: See `pyproject.toml`. Key: `textual`, `fastapi`, `sqlalchemy[asyncio]`, `sqlite-vec`, `nats-py`, `deepagents`, `langgraph`.
- **No CI/CD**: No GitHub Actions or similar. Tests run manually.

---

## Conventions

### Code Style
- **Python 3.13+**: Uses `type X | Y` union syntax (no `Optional`/`Union`).
- **Pydantic**: All config via Pydantic `BaseModel` with `Field()`.
- **Type hints**: Required on all public functions. `TYPE_CHECKING` guards for circular imports.
- **Docstrings**: Google style (Args/Returns sections).
- **Logging**: `logger = logging.getLogger(__name__)` at module level.

### Commit Messages
- **Format**: `type(scope): description` (conventional commits)
- **Types**: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`
- **Examples**:
  - `refactor: split interfaces/tui.py into focused modules`
  - `fix(config): add missing yolo field to AgentConfig`
  - `docs: update CODEBASE_MAP after Phase 6`

### Branch Naming
- `feature/<name>` — New features
- `fix/<name>` — Bug fixes
- `refactor/<name>` — Structural changes
- `docs/<name>` — Documentation updates

### Testing
- **TDD default**: Write failing test first for business logic/API handlers.
- **Test location**: `tests/` mirrors `src/nexusagent/` structure.
- **Async tests**: Use `@pytest.mark.asyncio` or `asyncio.run()`.
- **Mocking**: `unittest.mock.patch` for external dependencies (WebSocket, DB, NATS).

---

## Agent Workflow Rules

### Before Making Changes
1. Read `docs/CODEBASE_MAP.md` for module structure
2. Read `docs/SEMANTIC_INDEX.md` for data flows and state management
3. Check `docs/adrs/` for relevant architectural decisions
4. Run baseline tests: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=no`

### During Changes
5. Follow the established extraction pattern (if refactoring)
6. Preserve all public import paths (compat shims or re-exports)
7. Run tests after every file change (not just at the end)
8. Zero breaking changes — all existing tests must keep passing

### After Changes
9. Update `docs/CODEBASE_MAP.md` if module structure changed
10. Update `docs/SEMANTIC_INDEX.md` if data flows changed
11. Create ADR if the change is architecturally significant
12. Commit with descriptive message
13. Push to GitHub

---

## Tool-Specific Notes

### AST Tools (ast-tools MCP)
- Use `ast_read` before modifying unfamiliar code
- Use `ast_grep` for structural search (not text grep)
- Use `ast_edit` for surgical edits preserving formatting
- Use `structural_analysis` for call graphs and references

### TokRepo (MCP)
- Search before building: `tokrepo_search(query)` for existing assets
- Install: `tokrepo_codex_install(uuid)` for vetted assets
- Harvest after tasks: `tokrepo_harvest(paths)` to contribute back

### Sequential Thinking (MCP)
- Use for complex multi-step tasks to avoid missing steps
- Break down into micro-steps, verify each before proceeding

### Worktree Worker (`scripts/worktree-worker.py`)
- Create isolated worktrees for parallel tasks
- `create --name <name> --task <description>` — create worktree + branch
- `list` — show active worktrees
- `collect --name <name>` — get results
- `destroy --name <name>` — cleanup
- `remote --name <name> --server <server> --task <task>` — dispatch to server

---

## Environment

- **OS**: Debian 13 Trixie (Linux 6.12.86+deb13-amd64)
- **Python**: 3.13.5
- **Hardware**: Dell Optiplex i3-3110M, 3.7GB RAM (constrained)
- **Server**: rapidwebs-01 (Debian, 5.7GB+ free RAM) — use for heavy compute
- **Package manager**: pip (no conda/poetry)
- **Venv**: `python3 -m venv .venv && source .venv/bin/activate`

---

*This file is the living knowledge base for the NexusAgent project. Update it after every significant discovery, refactoring, or architectural decision. When in doubt, point to the reference documents rather than duplicating information.*
