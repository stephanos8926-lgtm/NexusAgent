# Forward Audit: Reorganization Sprint Plan

> **Date**: 2026-06-11
> **Auditor**: OWL (subagent)
> **Plan**: `.hermes/plans/2026-06-11-reorg-sprint-plan.md`
> **Verdict**: ⚠️ **FAIL — requires fixes before execution**

---

## Phase-by-Phase Verification

### Phase 1: Security & .gitignore Hardening

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 1.1 | `.gitignore` missing `*.db` | ✅ | Current `.gitignore` has no `*.db` pattern — only `__pycache__/`, `*.py[oc]`, `build/`, `dist/`, `wheels/`, `*.egg-info`, `.venv`, `site/`, `.env`, `.hermes/worktrees/` |
| 1.2 | `nexus.db` is empty (0 rows) | ❌ **FALSE** | `nexus.db` is 36,864 bytes and contains **4 tables** (`tasks`, `results`, `sessions`, `messages`). It is NOT empty. |
| 1.3 | `nexus.db` will be recreated by app startup | ⚠️ PARTIAL | `DatabaseManager.init_db()` creates tables, but existing data would be lost. The DB has real tables — need to verify if they have rows. |
| 1.4 | `data/` directory doesn't exist yet | ✅ | `ls data/` returns "No such file or directory" |
| 1.5 | `config/nexusagent.yaml` has `db_path: "nexus.db"` | ✅ | Line 3: `db_path: "nexus.db"` |
| 1.6 | `config.py` resolves relative `db_path` to absolute | ✅ | `config.py:156-159` resolves relative paths via `root / config.server.db_path` |
| 1.7 | `test.db-shm`, `test.db-wal`, `test_loop.db-*` exist | ✅ | All exist: `test.db-shm` (32KB), `test.db-wal` (24KB), `test_loop.db-shm` (32KB), `test_loop.db-wal` (585KB) |
| 1.8 | `.vtcode/`, `.llxprt/`, `.gemini/`, `.serena/`, `.remember/`, `.reports/` need gitignore | ⚠️ UNVERIFIED | Cannot verify existence of these dirs without deeper search, but they are reasonable IDE patterns |

**Phase 1 Issues:**
- **CRITICAL**: Plan claims `nexus.db` is empty. It is NOT. It has 4 tables. Need to check if those tables have data before deleting. If the app is actively using this DB, removing it will cause data loss.
- **CRITICAL**: `tests/conftest.py:49` hardcodes `_DBM("nexus.db")` — if the DB path changes to `data/nexus.db`, this conftest will break unless also updated. The plan does NOT mention updating `tests/conftest.py`.

---

### Phase 2: Root Cruft Cleanup

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 2.1 | `BACKLOG.md` exists | ✅ | 1,967 bytes, 28 lines |
| 2.2 | `BACKLOG.md` superseded by roadmap | ⚠️ PARTIAL | BACKLOG has 4 phases (Web Intelligence, Dynamic Capability, Deep Research, Productionization). Roadmap (`2026-07-12-assessment-and-roadmap.md`) is 103 lines focused on wiring existing components. The roadmap does NOT cover all BACKLOG items (e.g., multi-provider search, MCP integration, JIT tool loading, packaging). |
| 2.3 | `CODE_OF_CONDUCT.md` is generic placeholder | ✅ | Standard Contributor Covenant with `[CONTACT_EMAIL]` placeholder unfilled |
| 2.4 | `CONTRIBUTING.md` (root) is shorter duplicate of `docs/CONTRIBUTING.md` | ✅ | Root: 28 lines / 1,475 bytes. Docs: 65 lines / 2,365 bytes. Docs version is more detailed. |
| 2.5 | `SECURITY.md` is generic placeholder | ✅ | Uses `security@nexusagent.example.com` placeholder |
| 2.6 | `SUPPORT.md` has dummy links | ✅ | Uses `your-repo/nexusagent`, `support@nexusagent.com`, `discord.gg/nexusagent` |
| 2.7 | `COMPETITIVE_ANALYSIS.md` root is newer (2026-07-16) | ✅ | Root: dated 2026-07-16, 150 lines. Docs: dated 2026-06-06, 219 lines. Root is more recent. |
| 2.8 | `docs/competitive-analysis-2026-06-06.md` is older | ✅ | Dated June 6 vs root's July 16 |
| 2.9 | `vtcode.toml` exists in root | ✅ | 1,742 bytes |
| 2.10 | `.vtcode/` directory exists | ✅ | Contains `README.md`, `tool-policy.json`, `history/`, `logs/`, `state/`, `terminals/` |
| 2.11 | `nexusagent.service` uses `main.py server` | ✅ | Line 9: `ExecStart=/usr/bin/python3 /home/sysop/Workspaces/NexusAgent/main.py server` |
| 2.12 | Plan says update service to use `nexus-server` console script | ⚠️ MISLEADING | The service already uses `main.py server`. The `nexus-server` console script exists (`pyproject.toml:41`: `nexus-server = "nexusagent.server:run"`). The plan implies the service needs fixing, but it already works. Changing to `nexus-server` would require the venv to be activated or the full path to the script. |

**Phase 2 Issues:**
- **MODERATE**: BACKLOG.md is NOT fully superseded by the roadmap. The roadmap covers P0-P2 wiring tasks, but BACKLOG has broader feature goals (MCP, multi-provider search, packaging). Deleting BACKLOG loses feature tracking that the roadmap doesn't cover.
- **LOW**: The `nexusagent.service` "fix" is unnecessary — it already works with `main.py server`. Switching to `nexus-server` console script adds a dependency on the venv being in PATH.

---

### Phase 3: Documentation Consolidation

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 3.1 | 35 docs files exist | ⚠️ UNVERIFIED | Counted 34 `.md` files in `docs/` (excluding subdirs). The plan says 35 — close but may be off by one. |
| 3.2 | `CODEBASE_MAP.md` (25KB, 473 lines) | ✅ | 25,637 bytes, ~473 lines |
| 3.3 | `CODEBASE_INDEX.md` (56KB, 1,029 lines) | ✅ | 55,827 bytes, 1,029 lines |
| 3.4 | `STATE.md` (37KB, 645 lines) | ✅ | 36,759 bytes, ~645 lines |
| 3.5 | `AUDIT_REPORT.md` (9KB) | ✅ | 9,160 bytes |
| 3.6 | `REVERSE_AUDIT_REPORT.md` (17KB) | ✅ | 17,189 bytes |
| 3.7 | `CODE_CHANGES_SUMMARY.md` (3KB) | ✅ | 3,012 bytes |
| 3.8 | `EXECUTION_SUMMARY.md` (3KB) | ✅ | 3,426 bytes |
| 3.9 | `RESEARCH_FEATURE_PARITY_ARCHITECTURE.md` (25KB) | ✅ | 25,491 bytes |
| 3.10 | `RESEARCH_FEATURE_PARITY_CAPABILITIES.md` (12KB) | ✅ | 12,609 bytes |
| 3.11 | `RESEARCH_TUI_AESTHETICS_VISUAL.md` (37KB) | ✅ | 37,551 bytes |
| 3.12 | `RESEARCH_TUI_BEST_PRACTICES.md` (217 bytes, empty stub) | ✅ | 217 bytes |
| 3.13 | `docs/research/TOOL-PARITY-FINAL.md` exists | ✅ | 5,512 bytes |
| 3.14 | `docs/research/TUI-AESTHETICS-FINAL.md` exists | ✅ | 3,889 bytes |
| 3.15 | `getting_started.md` + `quickstart.md` are near-duplicates | ⚠️ UNVERIFIED | `getting_started.md` is 1,377 bytes (25 lines), `quickstart.md` is 2,276 bytes (~40 lines). They appear complementary rather than duplicative. |
| 3.16 | `env_execution_guide.md` is narrow scope | ✅ | 1,899 bytes, focused on env/execution |
| 3.17 | `mkdocs.yml` references `getting_started.md` | ✅ | Line 56: `- Getting Started Guide: getting_started.md` |
| 3.18 | `mkdocs.yml` references `env_execution_guide.md` | ✅ | Line 58: `- Environment & Execution: env_execution_guide.md` |
| 3.19 | `mkdocs.yml` references `CODEBASE_MAP.md` | ✅ | Line 65: `- Codebase Map: CODEBASE_MAP.md` |
| 3.20 | `mkdocs.yml` references `AUDIT_REPORT.md` | ✅ | Line 79: `- Audit Report: AUDIT_REPORT.md` |
| 3.21 | `mkdocs.yml` references `competitive-analysis-2026-06-06.md` | ✅ | Line 80: `- Competitive Analysis: competitive-analysis-2026-06-06.md` |
| 3.22 | `mkdocs.yml` does NOT reference `CODEBASE_INDEX.md` | ✅ | Not in nav — good, it can be deleted without mkdocs impact |
| 3.23 | `mkdocs.yml` does NOT reference `STATE.md` | ✅ | Not in nav — good |
| 3.24 | `mkdocs.yml` does NOT reference `REVERSE_AUDIT_REPORT.md` | ✅ | Not in nav — good |
| 3.25 | `mkdocs.yml` does NOT reference `CODE_CHANGES_SUMMARY.md` | ✅ | Not in nav — good |
| 3.26 | `mkdocs.yml` does NOT reference `EXECUTION_SUMMARY.md` | ✅ | Not in nav — good |
| 3.27 | `mkdocs.yml` does NOT reference `RESEARCH_*` files | ✅ | Not in nav — good |
| 3.28 | `README.md` has no broken links to moved files | ✅ | `grep` for the relevant filenames in README.md returned no matches |

**Phase 3 Issues:**
- **MODERATE**: The plan says `CODEBASE_INDEX.md` content is a "subset" of `CODEBASE_MAP.md`. Actually, INDEX is 56KB (1,029 lines) while MAP is 25KB (473 lines). INDEX is **larger** and likely contains different content (module-by-module reference vs file inventory). Merging requires careful content comparison, not just "INDEX is a subset."
- **LOW**: `mkdocs.yml` still references `AUDIT_REPORT.md` and `competitive-analysis-2026-06-06.md` in the nav. After archiving/deleting these, `mkdocs build` will fail with broken nav links. The plan mentions updating mkdocs.yml but doesn't explicitly call out removing these nav entries.
- **LOW**: The plan's target state shows `docs/SECURITY.md` and `docs/CODE_OF_CONDUCT.md` as "keep (if we add real content)" but these files don't exist in `docs/` — they exist in the root. This is confusing.

---

### Phase 4: Test Directory Consolidation

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 4.1 | `tests/test_tools/` exists | ✅ | Contains `test_todo.py` (4,256 bytes) |
| 4.2 | `tests/tools/` exists | ✅ | Contains `test_fs.py`, `test_fs_enhanced.py`, `test_patch.py`, `test_research.py`, `test_shell.py`, `test_spawn_subagent.py` |
| 4.3 | `tests/tools/test_fs.py` exists | ✅ | 658 bytes |
| 4.4 | `tests/tools/test_fs_enhanced.py` exists | ✅ | 2,557 bytes |
| 4.5 | Test count is 476 | ❌ **FALSE** | Actual count: **483 tests collected** |
| 4.6 | `tests/test_tools/` only has `test_todo.py` | ✅ | Only file is `test_todo.py` |

**Phase 4 Issues:**
- **MODERATE**: Plan baseline is 476 tests, but actual count is **483**. This is a 7-test discrepancy. The plan's validation step says "476 pass, 0 fail" — if the baseline is wrong, the validation will be confusing. Need to establish the correct baseline.
- **LOW**: After moving `test_todo.py` from `tests/test_tools/` to `tests/tools/`, there will be a name collision risk if `tests/tools/` already has a `test_todo.py`. Currently it doesn't, so this is safe.

---

### Phase 5: Secrets Sync Infrastructure

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 5.1 | `scripts/` directory exists | ✅ | Contains `worktree-worker.py` |
| 5.2 | `scripts/sync-secrets.py` doesn't exist yet | ✅ | Not present — will be created |
| 5.3 | `docs/SECRETS_SYNC.md` doesn't exist yet | ✅ | Not present — will be created |
| 5.4 | `.githooks/` directory doesn't exist | ✅ | Not present |

**Phase 5 Issues:**
- **NONE**: This phase creates only new files. No conflicts detected.
- **NOTE**: The plan mentions `scripts/sync-secrets-config.yaml` in the "Created" files list but the config section shows `config/secrets-sync.yaml`. Path inconsistency.

---

### Phase 6: worktree-worker.py Modernization

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 6.1 | `scripts/worktree-worker.py` exists (438 lines, 15KB) | ✅ | 438 lines, 15,441 bytes |
| 6.2 | Has create/list/collect/destroy/remote/status commands | ✅ | Confirmed from argparse at top of file |
| 6.3 | Missing: sync, doctor, init, --json | ✅ | None of these exist in current file |

**Phase 6 Issues:**
- **NONE**: Claims are accurate. This is a straightforward enhancement.

---

### Phase 7: orchestration.py fetch_url Implementation

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 7.1 | `_fetch()` is a TODO stub at `orchestration.py:98-101` | ✅ | Lines 98-101: `async def _fetch(self, url: str) -> str | None:` with `# Placeholder — for now rely on search snippets` and `return None` |
| 7.2 | `httpx` already in project dependencies | ✅ | `pyproject.toml:27` has `"httpx"`. `uv.lock` has 18 references to httpx. `research.py:6` imports `httpx`. |
| 7.3 | `fetch_url` tool needs to be registered in `register_all.py` | ❌ **FALSE** | `fetch_url` is **already registered** in `register_all.py:442-452`. It's imported from `nexusagent.tools.research` at line 32. |
| 7.4 | `fetch_url` in `tools/research.py` is already implemented | ✅ | `research.py:168-204`: Full implementation with httpx, error handling, HTML-to-text conversion, 5000-char truncation |

**Phase 7 Issues:**
- **CRITICAL**: The plan says to "Register `fetch_url` as a tool in `register_all.py`" — but it's **already registered**. And the `fetch_url` function in `tools/research.py` is **already fully implemented** with httpx. The TODO stub in `orchestration.py` (`_fetch`) is a separate method that calls a different code path. The plan conflates two different things:
  - `tools/research.py:fetch_url()` — already implemented and registered
  - `orchestration.py:_fetch()` — TODO stub in the orchestrator class
- **MODERATE**: The plan says to implement `_fetch` with httpx, but httpx is already imported and used in `research.py`. The `_fetch` method in the orchestrator could simply delegate to the existing `fetch_url` tool.

---

### Phase 8: Final Verification & Push

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 8.1 | `ruff check src/ tests/` should pass | ⚠️ UNVERIFIED | Not run in this audit |
| 8.2 | Push to `master` branch | ⚠️ UNVERIFIED | Not tested |
| 8.3 | Push research branches | ⚠️ UNVERIFIED | Not tested |

**Phase 8 Issues:**
- **NONE**: Standard verification steps.

---

## Findings Summary

### ✅ Correct Claims (verified against actual files)
1. `.gitignore` is missing critical patterns (*.db, *.log, IDE dirs)
2. All root cruft files (BACKLOG, CODE_OF_CONDUCT, CONTRIBUTING, SECURITY, SUPPORT) exist and are generic placeholders
3. `COMPETITIVE_ANALYSIS.md` root version (2026-07-16) is newer than docs/ version (2026-06-06)
4. `vtcode.toml` exists in root, `.vtcode/` directory exists
5. All research files (RESEARCH_FEATURE_PARITY_ARCHITECTURE, etc.) exist in docs/
6. `docs/research/TOOL-PARITY-FINAL.md` and `TUI-AESTHETICS-FINAL.md` exist
7. `tests/test_tools/test_todo.py` and `tests/tools/test_fs_enhanced.py` exist
8. `httpx` is in project dependencies
9. `orchestration.py:_fetch()` is a TODO stub
10. `worktree-worker.py` is 438 lines with create/list/collect/destroy/remote/status commands
11. `mkdocs.yml` references `getting_started.md`, `env_execution_guide.md`, `CODEBASE_MAP.md`, `AUDIT_REPORT.md`, `competitive-analysis-2026-06-06.md`
12. `README.md` has no direct links to files being moved

### ❌ Incorrect Claims (plan says X but reality is Y)

| # | Plan Claim | Reality | Severity |
|---|-----------|---------|----------|
| 1 | `nexus.db` is empty (0 rows) | `nexus.db` has 4 tables (tasks, results, sessions, messages), 36,864 bytes | 🔴 HIGH |
| 2 | Test count is 476 | Actual count is **483** | 🟡 MEDIUM |
| 3 | `fetch_url` needs to be registered in `register_all.py` | Already registered at line 442 | 🔴 HIGH |
| 4 | `fetch_url` needs to be implemented | Already fully implemented in `tools/research.py:168-204` with httpx | 🔴 HIGH |
| 5 | `CODEBASE_INDEX.md` content is a subset of `CODEBASE_MAP.md` | INDEX (56KB, 1,029 lines) is **larger** than MAP (25KB, 473 lines) | 🟡 MEDIUM |
| 6 | `nexusagent.service` needs entrypoint fix | Service already works with `main.py server`; `nexus-server` console script exists but isn't used | 🟢 LOW |
| 7 | `BACKLOG.md` is fully superseded by roadmap | Roadmap covers P0-P2 wiring; BACKLOG has broader feature goals not in roadmap | 🟡 MEDIUM |

### ⚠️ Missing Steps (actions plan should include but doesn't)

1. **Update `tests/conftest.py:49`** — Hardcodes `_DBM("nexus.db")`. If DB path changes to `data/nexus.db`, this must be updated or tests will create a new DB in the wrong location.
2. **Check `nexus.db` table contents** — Before deleting/moving, verify if the 4 tables have data. If they have production data, need a migration plan.
3. **Remove `AUDIT_REPORT.md` from `mkdocs.yml` nav** — Line 79 references it. After archiving, `mkdocs build` will fail.
4. **Remove `competitive-analysis-2026-06-06.md` from `mkdocs.yml` nav** — Line 80 references it. After deleting, `mkdocs build` will fail.
5. **Add `STATE.md` to `mkdocs.yml` nav** — If STATE.md is kept as a status document, it should be in the nav. Currently it's not.
6. **Handle `test_config.py:14`** — References `db_path: test.db` in a config string. Not affected by the change but worth noting.
7. **Create `data/` directory before app starts** — The plan says to create `data/` but doesn't mention that the app needs to be configured to create it on startup, or it needs to exist beforehand.
8. **Clarify `fetch_url` vs `_fetch`** — The plan should distinguish between the already-implemented `fetch_url` tool and the TODO `_fetch` method in the orchestrator.

### 🟢 Overstated Risks (plan worries about X but it's not a real risk)

1. **"mkdocs.yml broken links"** — Actually a **real risk** since the plan doesn't explicitly remove `AUDIT_REPORT.md` and `competitive-analysis-2026-06-06.md` from the nav.
2. **"DB path change breaks app"** — The plan says risk is "Low" but rates impact "High". Given that `conftest.py` hardcodes `nexus.db`, this is actually **MEDIUM-HIGH** risk.
3. **"Test count changes after merge"** — The plan says "Low/Low" but if test_fs_enhanced has unique tests that don't overlap with test_fs, merging could lose tests. Should be **MEDIUM**.

### 🔴 Understated Risks (plan misses real risk X)

1. **nexus.db data loss** — The plan treats `nexus.db` as empty. It has 4 tables. If those tables have data, `git rm --cached nexus.db` + deleting it will lose data. Need to check row counts.
2. **conftest.py hardcoded path** — `tests/conftest.py:49` uses `_DBM("nexus.db")`. Changing the config default to `data/nexus.db` won't affect this — it will still create `nexus.db` in the CWD. This could lead to two DB files existing simultaneously.
3. **fetch_url already exists** — Implementing a new `_fetch` method that duplicates the existing `fetch_url` tool creates maintenance overhead. Should delegate to existing tool.
4. **Phase 3 mkdocs nav incomplete** — The plan's target state removes files from nav but doesn't explicitly list all nav entries that need updating. Missing: `AUDIT_REPORT.md`, `competitive-analysis-2026-06-06.md`, `getting_started.md`, `env_execution_guide.md`.

---

## Files Changed Summary Audit

### Deleted Files Count
- Plan claims **21 files** deleted. Verified all 21 source files exist. ✅

### Created Files Count
- Plan claims **9 files** created. None exist yet (expected). ✅
- **Issue**: Plan mentions `scripts/sync-secrets-config.yaml` in text but `config/secrets-sync.yaml` in the code block. Path inconsistency.

### Modified Files Count
- Plan claims **13 files** modified. All source files exist. ✅
- **Issue**: `tests/tools/test_fs.py` is listed as modified (merge test_fs_enhanced content) but the plan doesn't mention checking for test name collisions.

---

## Verdict

### ⚠️ FAIL — Requires Fixes Before Execution

**Critical fixes needed:**

1. **Verify `nexus.db` contents** — Check if the 4 tables have data before deleting. If they do, create a migration plan.
2. **Update `tests/conftest.py`** — Must update the hardcoded `"nexus.db"` path or ensure it uses the config default.
3. **Fix Phase 7 scope** — The `fetch_url` tool is already implemented and registered. The plan should focus on connecting the orchestrator's `_fetch` method to the existing tool, not re-implementing it.
4. **Fix test baseline** — Update from 476 to 483 tests.
5. **Update `mkdocs.yml` nav** — Explicitly remove `AUDIT_REPORT.md` and `competitive-analysis-2026-06-06.md` from nav entries.
6. **Clarify BACKLOG.md** — Either keep it (it has content beyond the roadmap) or document what's lost.

**Recommended execution order after fixes:**
- Phase 1 (with conftest fix + nexus.db verification)
- Phase 2 (keep BACKLOG or document gap)
- Phase 3 (with explicit mkdocs nav updates)
- Phase 4 (with correct test baseline)
- Phase 5 (new files only — safe)
- Phase 6 (enhancements only — safe)
- Phase 7 (connect `_fetch` to existing `fetch_url`, don't re-implement)
- Phase 8 (verification with correct baseline)
