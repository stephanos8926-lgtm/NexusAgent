# Codebase Cleanup & Reorganization Plan
**Created**: 2026-06-11  
**Status**: DRAFT — pending audit

---

## Current State Summary

- **98 source files**, ~20,271 lines of Python
- **46 test files** (~5,800 lines)
- **~90 docs/markup files** across `docs/`, `codemaps/`, root
- **8 worktree dirs** (~22MB of duplicated source)
- **14 pre-existing test failures** (6 fs permission, 5 session/memory, 2 collection, 1 compaction)

---

## Phase 1: Root-Level Cruft Removal

**Goal**: Remove files that serve no purpose in the repo.

| Action | File | Reason |
|--------|------|--------|
| DELETE | `visual_companion_offer.txt` (279B) | Spam/ad, not project-related |
| DELETE | `server.log` (137B) | Runtime log, should be in `.gitignore` |
| DELETE | `test_nats.py` (165B) | Leftover from worktree, no content |
| DELETE | `test.txt` (5B) / `test_file.txt` (55B) | Test artifacts |
| DELETE | `agent_test_sequence.txt` (80B) | Debug artifact |
| DELETE | `rapidforge-emmc-luks-passphrase.txt` (65B) | Security-related personal note — DANGEROUS to keep in repo |
| DELETE | `.master.salt` (16B) / `.master.secret` (43B) | Secrets — should NOT be in git |
| DELETE | `keystore.json` (140B) | More secrets |
| DELETE | `LLXPRT.md` (2.9KB) | LLM export format — internal tool artifact |
| DELETE | `reverse_audit_findings.md` (6.8KB) | Superseded by `docs/AUDIT_REPORT.md` |
| DELETE | `findings.md` (8.2KB) | Superseded by `docs/AUDIT_REPORT.md` |
| DELETE | `progress.md` (1.6KB) | Superseded by `docs/STATE.md` |
| DELETE | `review.md` (2.3KB) | Superseded by `docs/AUDIT_REPORT.md` |
| DELETE | `task_plan.md` (800B) | Old TODO — stale |

**Check first**: Verify `.master.salt`, `.master.secret`, `keystore.json`, `rapidforge-emmc-luks-passphrase.txt` are in `.gitignore` or are not real secrets before deleting. If they're real secrets, they need to be removed from git history entirely.

**Check first**: Verify `nexus.db`, `test.db-shm`, `test.db-wal`, `test_loop.db-shm`, `test_loop.db-wal` are in `.gitignore`.

---

## Phase 2: Stale Source Files

| Action | File | Reason |
|--------|------|--------|
| DELETE | `src/nexusagent/tui_legacy.py` (1195L, 49KB) | Old monolithic TUI, fully replaced by `widgets/` modular system |
| DELETE | `docs/state.md` (1.4KB) | Superseded by `docs/STATE.md` |
| DELETE | `docs/research/*` (old 2026-06-05 reports) | Superseded by `docs/RESEARCH_*-FINAL.md` |
| DELETE | `docs/research/master_report_interactive.html` | Generated HTML — should not be in repo |

---

## Phase 3: Documentation Consolidation

**Goal**: Merge overlapping docs, reduce ~90 files to a clean hierarchy.

### 3a: CODEBASE_MAP merge
- `docs/CODEBASE_MAP_CORE.md` (36KB) + `docs/CODEBASE_MAP_TOOLS_API.md` (29KB) + `docs/CODEBASE_MAP_TUI.md` (31KB) + root `CODEBASE_MAP.md` (12KB)
- **Action**: Merge into single `docs/CODEBASE_MAP.md` (chronological, deduplicated)
- Delete the 4 source files

### 3b: Guides consolidation
- `docs/guides/` has 6 files overlapping with `docs/plans/` and `docs/architecture/`
- `docs/guides/quickstart.md` + `docs/guides/getting_started.md` have ~50% overlap
- **Action**: Merge into 3 files: `docs/guides/setup.md`, `docs/guides/usage.md`, `docs/guides/architecture.md`
- Delete the 6 source files

### 3c: Plans consolidation
- `docs/plans/` has 13 files spanning ~150KB, many superseded
- **Action**: Keep only `docs/plans/2026-07-12-assessment-and-roadmap.md` (the latest roadmap) and `docs/plans/2026-07-11-tui-parity-sprint.md` (recent for reference)
- Merge key decisions from old plans into the latest roadmap
- Delete the other 11 plan files

### 3d: Specs/ADRs consolidation
- `docs/specs/` (5 files, ~65KB) overlaps with `docs/adrs/` (5 files)
- `docs/superpowers/specs/` and `docs/superpowers/plans/` are definitely stale (June 2 prototypes)
- **Action**: Delete `docs/superpowers/` entirely
- Merge `docs/specs/` content into `docs/adrs/` where relevant, then delete `docs/specs/`
- Update `docs/adrs/index.md` to reference ADRs accurately

### 3e: Old one-off dirs
- `docs/collab/` (AGENT_A_TODO.md, AGENT_B_TODO.md) — multi-agent collab artifacts, stale
- `docs/development/` (changelog.md, contributing.md) — duplicates of root files
- **Action**: Delete these directories

### 3f: Duplicate ADR specs
- `docs/specs/0001-telemetry-system.md` duplicates `docs/adrs/0001-telemetry-system-design.md`
- **Action**: Delete the spec version (ADR is canonical)

---

## Phase 4: Worktree Cleanup

| Action | What | Size |
|--------|------|------|
| Remove | `.hermes/worktrees/track-a-features/` | 2.8MB |
| Remove | `.hermes/worktrees/track-b-tui/` | 2.7MB |
| Remove | `.hermes/worktrees/worker-help-input/` | 2.5MB |
| Remove | `.hermes/worktrees/worker-msg-redesign/` | 2.5MB |
| Remove | `.hermes/worktrees/worker-responsive/` | 2.5MB |
| Remove | `.hermes/worktrees/worker-theme-status/` | 2.6MB |
| Remove | `.gemini/worktrees/gemini-dev/` | 1.1MB |
| Prune | `.hermes/worktrees/` (keep only if actively in use) | 16.8MB total |
| Remove | `venv_fix/` (legacy venv) | ~1.2MB |
| `git worktree prune` | Clean up stale worktree registrations | — |

**NOTE**: All worktree branches are already merged to master. No code loss.

---

## Phase 5: Config & Build File Cleanup

| Action | File | Reason |
|--------|------|--------|
| Move | `docker-compose.yml`, `Dockerfile` → `deployment/` | Consolidate deployment configs |
| Update | `.gitignore` | Add `*.db*`, `*.log`, `*.secret`, `*.salt`, `*.txt` (non-docs) |
| Review | `Dockerfile` | May be stale — check if it references current project structure |

---

## Phase 6: Source Code Reorganization

### 6a: `src/nexusagent/` structure audit
Current flat structure has ~40 files at the top level. Propose:

```
src/nexusagent/
  core/           # agent, session, config, models, cli
  memory/         # memory, memory_files, memory_index, compaction, hybrid
  tools/          # all tools/ + registry + register_all
  tui/            # tui.py → app.py, widgets/ (already exists)
  services/       # server, sdk, bus, worker, task_reaper, web_ui
  hook/           # already exists
  utils/          # utils, auth, api_auth, prompt_loader, llm
```

**Risk**: HIGH — this requires updating all import paths across the entire codebase + all tests.
**Recommendation**: DEFER to a separate sprint. Too risky to combine with cleanup.

### 6b: Immediate source fixes (low risk)
- Remove `src/nexusagent/__init__.py` (empty — unnecessary)
- Remove `src/nexusagent/tools/__init__.py` (empty — unnecessary)
- Remove `tests/__init__.py` and `tests/tools/__init__.py` (empty — unnecessary)
- Move `src/nexusagent/hooks/` to `src/nexusagent/hook/` for naming consistency

### 6c: `tools/git.py` missing from `register_all.py`
- `tools/git.py` exists (169L) but is it wired into the tool registry?
- Check if `register_all.py` imports it — if not, it's dead code OR a missing registration

---

## Phase 7: Docs Update

| Task | Description |
|------|-------------|
| Update `README.md` | Current state, features, build/test instructions |
| Update `CONTRIBUTING.md` | Reflect new structure, FORGE.md integration |
| Update `CHANGELOG.md` | Add all sprint work since last update |
| Update `docs/STATE.md` | Consolidate from all sources, remove stale entries |
| Update `docs/architecture/overview.md` | Reflect new widget-based TUI |
| Create `docs/MIGRATION.md` | Document tui.py → widgets/ split for users |
| Update `mkdocs.yml` | Clean up nav structure to match new doc layout |
| Update `docs/index.md` | Reflect new doc structure |

---

## Phase 8: Pre-Existing Test Failure Fixes

| Category | Count | Issue | Fix |
|----------|-------|-------|-----|
| fs permission | 6 | Permission jail in test env | Fix test setup/teardown |
| session/memory | 5 | Missing psutil + embedding dim mismatch | Install psutil, fix mock embedding |
| collection | 2 | test_tui_streaming.py and test_e2e_production.py | Fix import errors |
| compaction | 1 | Same memory embedding issue | Fix mock embedding |

---

## Execution Order

1. **Phase 1** — Root cruft (safe, immediate)
2. **Phase 4** — Worktree removal (safe, immediate, frees 16+ MB)
3. **Phase 2** — Stale sources (safe after Phase 1)
4. **Phase 8** — Fix test failures (needed before refactoring)
5. **Phase 3** — Doc consolidation (after cruft removed)
6. **Phase 5** — Config cleanup
7. **Phase 6b** — Low-risk source fixes
8. **Phase 7** — Docs update
9. **Phase 6a** — Full source reorg (SEPARATE SPRINT — too risky here)

---

## What We're NOT Touching (This Sprint)

- Source directory reorg (Phase 6a) — too risky, needs dedicated sprint
- New features or feature parity work
- TUI code changes (already done in previous sprint)
- `config/NEXUS.md` (19KB system prompt — large but functional)
- `docs/superpowers/` content review (just delete — it's all prototype)
