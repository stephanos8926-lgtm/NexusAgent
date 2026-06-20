# NexusAgent Refactoring Plan

**Date:** 2026-07-22
**Baseline:** 680 passing, 11 failed (all pre-existing), 0 errors

---

## Status: Phases 1-7 ✅ Complete | Phases 8-17 In Progress/Complete

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
- `tui.py` → `tui/` subpackage with `app.py`, `websocket.py`, `streaming.py`, `input.py`, `formatters.py`

### Phase 16: `server/server.py` → `server/` subpackage ✅
- Extracted: `routes.py`, `websocket.py`, `__main__.py`
- `server.py`: Reduced to app factory + lifespan

### Phase 17: `memory/memory.py` → `memory/` submodules ✅
- Extracted: `memory_item.py`, `memory_bank.py`, `memory_manager.py`, `hybrid_memory.py`

---

## Remaining Candidates

### Tier 1 — HIGH (structural problems causing bugs)

#### 1. TUI App Class: `interfaces/tui/app.py` (354L)
**Status:** Partially split (Phase 7). Still handles event dispatch + display formatting.
**Remaining:** Extract screens (main, settings), slash commands into separate modules.

#### 2. Session Class: `core/session/session.py` (391L)
**Status:** Split from monolith. `send()` is still ~120 lines.
**Remaining:** Extract prompt building, approval flow, compaction callbacks.

### Tier 2 — MEDIUM (significant complexity)

#### 3. Memory Files: `memory/memory_files.py` (638L)
**Status:** Large but self-contained. Contains file I/O, YAML frontmatter parsing, entity extraction.
**Remaining:** Could split into `frontmatter.py`, `entity_ops.py`, `daily_log.py`.

#### 4. Dream Cycle: `memory/dream.py` (848L)
**Status:** Largest memory module. 4-phase consolidation with file locking, LLM refinement.
**Remaining:** Could split phases into separate modules.

#### 5. Tool Registration: `tools/register_all.py` (494L)
**Status:** All tool registration in one file.
**Remaining:** Self-describing tools pattern (metadata in each tool module).

### Tier 3 — LOW (cleanliness improvements)

#### 6. Memory Refinement: `memory/refinement.py` (375L)
**Status:** LLM synthesis layer. Self-contained, low coupling.
**Remaining:** Low priority.

#### 7. Memory DAG: `memory/dag.py` (442L)
**Status:** Hierarchical compression. Self-contained.
**Remaining:** Low priority.

#### 8. Consolidation Engine: `memory/consolidation.py` (158L)
**Status:** Duplicate/contradiction detection. Self-contained.
**Remaining:** Low priority.

---

## Priority Order (remaining work)

| # | Module | Lines | Risk | Est. Phase | Rationale |
|---|--------|-------|------|------------|-----------|
| 1 | `tui/app.py` | 354 | Med | 1 | Complete the TUI split |
| 2 | `session/session.py` | 391 | Med | 1 | Core logic, needs isolation |
| 3 | `memory/memory_files.py` | 638 | Low | 2 | Large but self-contained |
| 4 | `memory/dream.py` | 848 | Low | 2 | Complex but isolated |
| 5 | `tools/register_all.py` | 494 | Low | 2 | Self-describing pattern |

---

## Execution Methodology (per phase)

For each refactoring phase:

### A. Implementation Plan (written before touching code)
1. Identify the exact code blocks to extract
2. Define the new module/file structure
3. Map all import paths that need updating
4. Identify tests that need updates

### B. Skills & Tools
- `ast-tools`: Read structure before modifying
- `ast-edit`: Surgical edits where possible
- `patch`: Targeted find-and-replace for import updates
- `git mv`: File renames that preserve history

### C. Forward Audit (main agent)
1. Read the target file completely
2. Map all internal dependencies (imports, function calls)
3. Identify the extraction boundaries
4. Verify test coverage for the target

### D. Reverse Audit (subagent, parallel)
1. Dispatch subagent to independently analyze the same file
2. Compare findings with forward audit
3. Identify blind spots (dead code, hidden coupling, missing tests)

### E. Plan Reconciliation
1. Merge forward + reverse audit findings
2. Update the implementation plan
3. Present changes for sign-off

### F. Execution
1. Create new module directory + `__init__.py`
2. `git mv` or copy extracted code to new file
3. Update all import paths (internal + tests)
4. Run full test suite after EACH file move

### G. Regression Testing
1. `PYTHONPATH=src python3 -m pytest tests/ -q`
2. Compare pass/fail counts with baseline
3. Any regression → fix immediately, do not proceed

### H. Documentation Update
1. Update `CODEBASE_MAP.md` with new structure
2. Update `SEMANTIC_INDEX.md` with new data flows
3. Update any module docstrings

### I. Commit & Proceed
1. Commit with descriptive message: `refactor: extract X from Y into Z`
2. Push to GitHub
3. Move to next phase

---

## Constraints

- **Zero breaking changes** — all public APIs must remain accessible from their original import paths
- **No behavior changes** — refactoring only, no feature changes
- **Test gate mandatory** — every extraction must pass the full test suite
- **One phase at a time** — complete and verify before starting next
- **Git history preserved** — use `git mv` for renames
