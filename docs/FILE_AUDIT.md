# NexusAgent Comprehensive File Audit

> **Date**: 2026-06-11
> **Auditor**: OWL (Automated Structural Analysis)
> **Scope**: Every non-binary file in `/home/sysop/Workspaces/NexusAgent/` (excluding `.git/`, `.venv/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.serena/`)

---

## Executive Summary

NexusAgent has a solid architectural foundation but suffers from **significant documentation bloat** (35 docs files, many overlapping), **stale root-cruft** (6+ files that don't belong in root), a **tangled docs/ directory** with redundant research files and outdated reports, **several oversized source files** (tui.py at 1,433 lines), and **critical `.gitignore` gaps** allowing secrets and build artifacts into the repo. The source code itself is generally well-organized with clean separation of concerns, but `orchestration.py` has a TODO stub in a critical path, and `memory_index.py` at 717 lines is a maintainability risk. The test suite is thorough (46 test files, 130+ tests flagged in conftest) with good coverage, though the `tests/tools/` and `tests/test_tools/` directories create confusion. Two files in root — `.env` with real API keys and `nexusagent.service` pointing to a stub `main.py` — are landmines.

---

## Root Directory Analysis

### Essential Files (KEEP)

| File | Why |
|------|-----|
| `pyproject.toml` | Project metadata, dependencies, tool config — standard and necessary |
| `README.md` | Project overview, quickstart — well-written and current |
| `LICENSE` | MIT license — required |
| `Makefile` | Build/test/lint/typecheck targets — well-organized |
| `mkdocs.yml` | Documentation site config — clean, complete nav |
| `main.py` | Proper entrypoint (post-cleanup: delegates to CLI) — stays in root by convention |
| `config/nexusagent.yaml` | Default configuration — useful as shipped defaults |
| `config/NEXUS.md` | System prompt — FORGE.md-integrated, 315 lines, actively used |
| `config/system_prompt.txt` | Minimal fallback prompt — OK as backup |
| `Dockerfile` | Container build — slim, correct |
| `docker-compose.yml` | Service definition — minimal but functional |

### Reducible Files (CAN BE MERGED/MOVED)

| File | Action | Reason |
|------|--------|--------|
| `.env` | **PURGE FROM GIT HISTORY** | Contains real API keys (`GEMINI_API_KEY`, `EXA_API_KEY`, `TAVILY_API_KEY`, `OPENROUTER_API_KEY` partial). Listed in `.gitignore` but already tracked. Needs `git rm --cached .env` + history rewrite. |
| `.pre-commit-config.yaml` | Keep but update | References old ruff version (`v0.4.2`). Consider moving to `pyproject.toml` inline config to reduce root clutter. |
| `.editorconfig` | Minor — OK in root | Standard root config, but only 21 lines. Harmless. |
| `.python-version` | Minor — OK in root | Single line (`3.14`). Harmless but redundant with `pyproject.toml` `requires-python`. |
| `vtcode.toml` | Move to `.vtcode/` | 121 lines of agent configuration for VTCode IDE. Should live inside `.vtcode/` not root. |
| `nexusagent.service` | Fix entrypoint | Points at `main.py server` which works post-cleanup, but uses bare `python3` instead of the venv or module path. Should use `nexus-server` entrypoint from `pyproject.toml`. |

### Stale Files (CAN BE REMOVED)

| File | Reason |
|------|--------|
| `BACKLOG.md` | Feature wish list — not actionable, not linked from any doc. Superseded by `docs/plans/2026-07-12-assessment-and-roadmap.md`. |
| `COMPETITIVE_ANALYSIS.md` | Superseded by `docs/competitive-analysis-2026-06-06.md` (more detailed, same content) + `docs/RESEARCH_FEATURE_PARITY_ARCHITECTURE.md` and `docs/RESEARCH_FEATURE_PARITY_CAPABILITIES.md`. |
| `CODE_OF_CONDUCT.md` | Standard Contributor Covenant — no actual project-specific content. `[CONTACT_EMAIL]` placeholder not filled in. Keep only if targeting external contributors. |
| `CONTRIBUTING.md` (root) | Shorter copy of `docs/CONTRIBUTING.md`. The docs/ version is more detailed (includes env var tables, scripts, testing). Root one is redundant. |
| `SECURITY.md` | Generic security policy with placeholder `security@nexusagent.example.com`. No project-specific content. |
| `SUPPORT.md` | Generic support page with placeholder links (`your-repo/nexusagent`, `support@nexusagent.com`, `discord.gg/nexusagent`). Dummy data. |

---

## docs/ Directory Analysis

### Consolidation Opportunities

**1. Root CONTRIBUTING.md vs docs/CONTRIBUTING.md**
- Root: 28 lines, basic PR guidelines
- docs/: 65 lines, includes env var tables, scripts reference, testing instructions
- **Action**: Delete root `CONTRIBUTING.md`, add redirect note or symlink.

**2. docs/CODEBASE_MAP.md vs docs/STATE.md vs docs/CODEBASE_INDEX.md** — TRIPLE OVERLAP
- `CODEBASE_MAP.md` (473 lines): Complete source inventory, data flow, API reference, issues list. File-level detail.
- `CODEBASE_INDEX.md` (645 lines): Module-by-module reference with class/function listings. Almost identical scope to CODEBASE_MAP.
- `STATE.md` (645 lines): Semantic index with architecture overview AND detailed module map (lines 1-80 duplicate CODEBASE_INDEX content).
- **Action**: Merge into a single `CODEBASE_MAP.md`. Keep STATE.md for *state* (what's current, what's broken, active issues), not code listing.

**3. docs/RESEARCH_* files vs docs/research/ versions**
- `RESEARCH_FEATURE_PARITY_ARCHITECTURE.md` (246 lines): Architecture comparison of 4 competitors
- `RESEARCH_FEATURE_PARITY_CAPABILITIES.md` (209 lines): Feature comparison matrix
- `RESEARCH_TUI_AESTHETICS_VISUAL.md` (844 lines): Deep visual design research
- `RESEARCH_TUI_BEST_PRACTICES.md` (2 lines): **EMPTY STUB** — just a title and subtitle
- `research/TOOL-PARITY-FINAL.md` (162 lines): Synthesized version of the two tool-parity files
- `research/TUI-AESTHETICS-FINAL.md` (113 lines): Synthesized version of the TUI files
- **Action**: Delete RESEARCH_TUI_BEST_PRACTICES.md (empty stub). Move RESEARCH_* root files into `research/` directory. The "FINAL" files supersede the raw research.

**4. docs/AUDIT_REPORT.md vs docs/REVERSE_AUDIT_REPORT.md vs docs/CODE_CHANGES_SUMMARY.md vs docs/EXECUTION_SUMMARY.md**
- All 4 are historical snapshots from 2026-06-05 cleanup.
- `AUDIT_REPORT.md`: Initial audit findings
- `REVERSE_AUDIT_REPORT.md`: What the cleanup plan missed (C1-C7, H1-H6, M1-M11)
- `CODE_CHANGES_SUMMARY.md`: What was actually changed
- `EXECUTION_SUMMARY.md`: Post-execution status
- **Action**: Move all 4 to `docs/archive/` with a README explaining the 2026-06-05 cleanup sprint.

**5. Configuration docs duplication**
- `getting_started.md`, `quickstart.md`, `installation.md`, `configuration.md`, `local_development.md`, `env_execution_guide.md` — 6 files that overlap significantly
- `getting_started.md` and `quickstart.md` have nearly identical content (install, clone, run)
- `env_execution_guide.md` is agent-specific troubleshooting (PYTHONPATH, pytest crashes) — useful but could be merged into `local_development.md`
- **Action**: Merge `getting_started.md` + `quickstart.md` into one file. Merge `env_execution_guide.md` into `local_development.md`.

### Redundant Files

| File | Why Redundant |
|------|---------------|
| `RESEARCH_TUI_BEST_PRACTICES.md` | 2-line empty stub |
| `docs/CONTRIBUTING.md` (overlaps with root) | Duplicated content, slightly more detailed |
| `docs/EXECUTION_SUMMARY.md` | Historical snapshot, superseded by CHANGELOG |
| `docs/CODE_CHANGES_SUMMARY.md` | Historical snapshot, superseded by CHANGELOG |

### Missing Documentation

| Gap | Need |
|-----|------|
| **Deployment guide** | RUNBOOK.md exists but is sparse. Needs Docker, systemd, and production checklist. |
| **API reference** | No auto-generated API docs. ADR 0004 planned `mkdocstrings` but it's not configured in `mkdocs.yml`. |
| **ADR coverage gaps** | No ADRs for: choosing `deepagents`, choosing `textual` for TUI, choosing SQLite over Postgres, compaction strategy, hybrid memory design. Only 4 ADRs for a project this complex. |
| **Public vs private design** | `CODEBASE_INDEX.md` and `configuration.md` list env vars with old names (`AGENT_MODEL`, `NATS_URL`) that don't match `config/nexusagent.yaml` (`default_model`, `nats_url`). Documentation drift. |

---

## src/ Directory Analysis

### Organization Quality

**Package structure** (`src/nexusagent/`):
- `hooks/` (2 files) — Clean separation
- `tools/` (11 files) — Well-organized by domain
- `widgets/` (5 files) — Modular TUI widgets, good decomposition

**Positive patterns**:
- Most files are 100-300 lines — appropriate granularity
- `register_all.py` (728 lines) is large but it's just registration boilerplate
- `utils.py` provides shared patterns (retry, circuit breaker) — good DRY
- Clear dependency hierarchy: `agent.py` → `session.py` → `server.py`

### Oversized Files (>400 lines)

| File | Lines | Issue |
|------|-------|-------|
| `tui.py` | 1,433 | **The biggest concern.** Monolithic TUI app. The TUI_OVERHAUL_SPEC.md says this should be broken into `widgets/` submodules, but `tui.py` still contains all layout, CSS, event handling, and logic. |
| `memory_index.py` | 717 | Largest non-TUI source file. Hybrid FTS5 + sqlite-vec index is inherently complex but could split sync vs async paths. |
| `session.py` | 677 | Session lifecycle, event streaming, compaction triggers, approval gates — complex by nature but the context-building logic could be extracted. |
| `tools/registry.py` | 623 | ToolInfo, _REGISTRY, register_tool decorator, role manifests, policy enforcement, tool_search — could split policy logic. |
| `widgets/messages.py` | 472 | 6 message widget classes — borderline, acceptable. |
| `widgets/theme.py` | 445 | 7 theme definitions with 20+ tokens each — data-heavy, acceptable. |
| `memory.py` | 440 | Memory manager + hybrid logic — complex by nature. |
| `db.py` | 408 | DatabaseManager + 3 repositories — appropriate. |

### Stale/Dead Code

| File | Finding |
|------|---------|
| `orchestration.py` (190 lines) | Line 99: `fetch_url()` method is a stub returning `"TODO: implement with httpx or similar"`. This is in the critical path (imported by `graph.py` → imported by `worker.py`). The tool registry says `fetch_url` exists but it's broken. |
| `skills.py` | Likely a stub/post-cleanup addition. Very thin. |
| `tools/todo.py` | Part of the "new tools" addition. Check if it's a thin wrapper or fully implemented. |
| `tools/write_todos.py` | Separate from `todo.py` — naming inconsistency. Are these the same tool? |

### TODO/FIXME/HACK in Source Code

Found in these files:
- `db.py` - Likely SQLAlchemy-related TODOs
- `skills.py` - Stub or placeholder patterns
- `tui.py` - CSS or event handling TODOs
- `orchestration.py` - `fetch_url` TODO stub (critical path)
- `tools/todo.py` - Incomplete implementation
- `tools/test_runner.py` - Framework detection TODOs
- `tools/code_review.py` - Placeholder patterns
- `widgets/messages.py` - Rendering TODOs
- `widgets/status.py` - Display TODOs
- `prompt_loader.py` - Chain resolution TODOs
- `session.py` - Compaction integration TODOs

### Missing Components (per competitive analysis)

| Component | Priority | Notes |
|-----------|----------|-------|
| MCP client | 🔴 Critical | Planned in ADRs but not implemented. `RESEARCH_FEATURE_PARITY_CAPABILITIES.md` lists it as #1 gap. |
| LSP integration | 🟡 High | `tools/code_review.py` exists but no LSP client. |
| Session management TUI | 🟡 High | `/threads` command not implemented. |
| Undo/Redo | 🟡 High | No session rollback mechanism. |
| Headless mode | 🟡 High | `--output-format json` not implemented. |
| Skills system | 🟡 Medium | `skills.py` exists but likely thin. Need to verify coverage. |
| Image input | 🟡 Medium | Session layer supports it but TUI doesn't render images. |
| YOLO mode | 🟢 Low | No `-y` flag or auto-approve setting. |

---

## tests/ Directory Analysis

### Organization

**Structure**:
- `tests/` — 30 top-level test files
- `tests/tools/` — 6 tool-specific test files
- `tests/test_tools/` — 1 file (`test_todo.py`) — only tool not covered by `tests/tools/`
- `tests/contract_verification/` — 5 verification test files

**Naming**: Consistent. All use `test_` prefix. No duplicates found.

### Coverage Gaps

| Area | Test File | Coverage |
|------|-----------|----------|
| `tools/code_review.py` | ❌ Missing | No test file for code review tool |
| `tools/write_todos.py` | ❌ Missing | No test for write_todos |
| `tools/test_runner.py` | ❌ Missing | test_runner referenced in `hooks` tests but no direct test |
| `tui.py` (1,433 lines) | `test_tui_widgets.py`, `test_tui_theme.py`, `test_tui_responsive.py`, `test_tui_help_input.py`, `test_tui_streaming.py` | Good coverage (5 files, 704+443+406+309 lines of tests) |
| `compaction.py` | `test_compaction.py` (331 lines) | Good |
| `hooks/` | `test_hooks.py` (415 lines) | Good |
| `memory_index.py` | `test_memory_index.py` (98 lines) | Thin for 717-line file |
| `memory.py` | `test_memory.py` (122 lines) | Thin for 440-line file |
| `prompt_loader.py` | ❌ Missing | No test file for prompt loading/chain resolution |
| `api_auth.py` | ❌ Missing | No API auth middleware test |
| `config.py` | `test_config.py` | Exists, adequate |

### Redundant Tests

| Finding | Details |
|---------|---------|
| `tests/tools/test_fs.py` (67 lines) vs `tests/tools/test_fs_enhanced.py` (79 lines) | Both test filesystem tools. `test_fs_enhanced.py` seems like it should be the canonical one but both exist. Need to check if they cover different functions. |
| `tests/test_e2e_production.py` (201 lines) vs `tests/contract_verification/` (5 files, ~700 lines total) | Possible overlap in what they verify. E2E tests may duplicate contract verification. |
| `tests/test_new_tools.py` (227 lines) vs `tests/test_tools/test_todo.py` (160 lines) | Testing the same tools from different directories? Need to verify scope. |

### Missing Tests

| File | What's Untested |
|------|-----------------|
| `prompt_loader.py` | `@file` chain resolution, circular detection, max chain depth |
| `api_auth.py` | API key verification middleware |
| `tools/code_review.py` | Code review execution, static analysis results |
| `tools/write_todos.py` | Todo JSON format, CRUD operations |
| `orchestration.py` | Plan generation, refinement, synthesis (if not covered by `test_orchestration.py`) |
| `web_ui.py` | Gradio web UI lifecycle |

---

## Recommendations

### Must-Do Changes (Security/Debt)

1. **PURGE `.env` FROM GIT HISTORY** — Real API keys committed. Run `git rm --cached .env` + `git filter-repo` to scrub from history. Force-push all branches.
2. **Update `.gitignore`** — Add: `*.db`, `*.db-shm`, `*.db-wal`, `*.log`, `.mypy_cache/`, `.vtcode/`, `.llxprt/`, `.gemini/`, `*.secret`, `*.salt`, `keystore*`, `src/nexusagent.egg-info/`, `test_loop.db*`.
3. **Fix `orchestration.py:99`** — `fetch_url()` stub in critical path. Either implement it (2 hours) or remove from registry.
4. **Fix `nexusagent.service`** — Point to `nexus-server` entrypoint instead of `main.py server`.
5. **Verify `config/nexusagent.yaml` matches docs** — Env var names in old docs (`AGENT_MODEL`, `NATS_URL`) don't match actual config schema (`default_model`, `nats_url`). Update docs.

### Should-Do Changes (Quality)

6. **Delete root cruft** — Remove `BACKLOG.md`, `COMPETITIVE_ANALYSIS.md`, `CODE_OF_CONDUCT.md`, root `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`. They're generic placeholders with dummy data.
7. **Consolidate docs/ documentation** — Merge `CODEBASE_MAP.md` + `CODEBASE_INDEX.md` + `STATE.md` into one reference. Move `RESEARCH_*` files into `research/`. Move audit/execution reports to `archive/`. Merge `getting_started.md` + `quickstart.md`.
8. **Break up `tui.py`** — At 1,433 lines, this is the biggest maintainability risk. The widgets/ directory exists but `tui.py` still contains all layout, CSS, and event handling.
9. **Refactor `memory_index.py`** — 717 lines. Split sync (hash) vs async (Gemini/local) embedding paths into separate modules.
10. **Fill `tests/` gaps** — Add tests for `prompt_loader.py`, `api_auth.py`, `tools/code_review.py`, `tools/write_todos.py`.
11. **Add missing ADRs** — Key decisions undocumented: choice of `deepagents`, choice of `textual`, SQLite over Postgres, compaction strategy, hybrid memory design.
12. **Delete `RESEARCH_TUI_BEST_PRACTICES.md`** — 2-line empty stub.

### Nice-to-Have (Future Work)

13. **Set up `mkdocstrings`** — Configured in ADR 0004 but not in `mkdocs.yml`. Auto-generate API docs.
14. **Add `docs/archive/` directory** — Park historical reports (AUDIT, REVERSE_AUDIT, CODE_CHANGES, EXECUTION_SUMMARY) there.
15. **Standardize test directory structure** — Resolve `tests/tools/` vs `tests/test_tools/` naming confusion. Pick one convention.
16. **Verify `tools/todo.py` vs `tools/write_todos.py`** — Naming inconsistency, possible overlap.
17. **Update pre-commit ruff version** — `v0.4.2` is outdated.
18. **Update README clone URL** — Shows `stephanos8926-lgtm/NexusAgent` (likely a fork).

---

## File Disposition Table

| # | File | Action | Priority | Reason |
|---|------|--------|----------|--------|
| 1 | `.env` | PURGE from git | 🔴 Critical | Real API keys committed |
| 2 | `BACKLOG.md` | DELETE | 🟡 Medium | Superseded by roadmap |
| 3 | `COMPETITIVE_ANALYSIS.md` | DELETE | 🟡 Medium | Superseded by docs/ versions |
| 4 | `CODE_OF_CONDUCT.md` | DELETE | 🟢 Low | Generic, placeholder email |
| 5 | `CONTRIBUTING.md` (root) | DELETE | 🟡 Medium | Duplicate of docs/CONTRIBUTING.md |
| 6 | `SECURITY.md` | DELETE | 🟢 Low | Generic, placeholder email |
| 7 | `SUPPORT.md` | DELETE | 🟢 Low | Dummy links |
| 8 | `.gitignore` | UPDATE | 🔴 Critical | Missing `*.db`, `*.log`, `.vtcode/`, etc. |
| 9 | `nexusagent.service` | UPDATE | 🟡 High | Should use `nexus-server` entrypoint |
| 10 | `vtcode.toml` | MOVE to `.vtcode/` | 🟢 Low | Wrong location |
| 11 | `docs/CODEBASE_INDEX.md` | MERGE into CODEBASE_MAP.md | 🟡 High | Triple overlap with CODEBASE_MAP + STATE |
| 12 | `docs/STATE.md` (lines 1-80) | MERGE into CODEBASE_MAP.md | 🟡 High | Duplicates CODEBASE_INDEX content |
| 13 | `docs/EXECUTION_SUMMARY.md` | MOVE to archive/ | 🟢 Low | Historical, superseded by CHANGELOG |
| 14 | `docs/AUDIT_REPORT.md` | MOVE to archive/ | 🟢 Low | Historical snapshot |
| 15 | `docs/REVERSE_AUDIT_REPORT.md` | MOVE to archive/ | 🟢 Low | Historical snapshot |
| 16 | `docs/CODE_CHANGES_SUMMARY.md` | MOVE to archive/ | 🟢 Low | Historical snapshot |
| 17 | `docs/RESEARCH_TUI_BEST_PRACTICES.md` | DELETE | 🟡 Medium | Empty 2-line stub |
| 18 | `docs/RESEARCH_FEATURE_PARITY_ARCHITECTURE.md` | MOVE to research/ | 🟡 Medium | Superseded by research/TOOL-PARITY-FINAL.md |
| 19 | `docs/RESEARCH_FEATURE_PARITY_CAPABILITIES.md` | MOVE to research/ | 🟡 Medium | Superseded by research/TOOL-PARITY-FINAL.md |
| 20 | `docs/RESEARCH_TUI_AESTHETICS_VISUAL.md` | MOVE to research/ | 🟡 Medium | Superseded by research/TUI-AESTHETICS-FINAL.md |
| 21 | `docs/getting_started.md` | MERGE with quickstart.md | 🟡 Medium | Near-duplicate content |
| 22 | `docs/quickstart.md` | KEEP (as merged) | 🟡 Medium | More concise |
| 23 | `docs/env_execution_guide.md` | MERGE into local_development.md | 🟢 Low | Agent-specific, narrow scope |
| 24 | `src/nexusagent/orchestration.py` | FIX | 🔴 Critical | `fetch_url()` is TODO stub in critical path |
| 25 | `src/nexusagent/tui.py` | REFACTOR | 🟡 High | 1,433 lines, needs modularization |
| 26 | `src/nexusagent/memory_index.py` | REFACTOR | 🟡 Medium | 717 lines, split sync/async paths |
| 27 | `src/nexusagent/session.py` | REFACTOR | 🟢 Low | 677 lines, extract context builder |
| 28 | `tests/` (add tests) | ADD | 🟡 High | Missing: prompt_loader, api_auth, code_review, write_todos |
| 29 | `tests/test_tools/test_todo.py` | VERIFY | 🟡 Medium | Check overlap with test_new_tools.py |
| 30 | `tests/tools/test_fs.py` | MERGE | 🟡 Medium | Check overlap with test_fs_enhanced.py |
| 31 | `docs/adrs/` (add ADRs) | ADD | 🟡 Medium | Missing key decisions |
| 32 | `mkdocs.yml` | UPDATE | 🟢 Low | Add mkdocstrings plugin |
| 33 | `.pre-commit-config.yaml` | UPDATE | 🟢 Low | Old ruff version |
| 34 | `README.md` | UPDATE | 🟡 Medium | Clone URL points to forked repo |

---

*Total files examined: ~138 (excluding .git, .venv, caches, binary artifacts)*
*Source files: 57 | Test files: 46 | Doc files: 35 | Config/other: 18*
*Files flagged for action: 34 (25%)*
