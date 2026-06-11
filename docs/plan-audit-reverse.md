# Reverse Audit: Reorganization Sprint Plan

> **Date**: 2026-06-11
> **Auditor**: OWL (subagent — reverse/left side)
> **Plan**: `.hermes/plans/2026-06-11-reorg-sprint-plan.md`
> **Method**: Prove the plan is incomplete by finding everything it misses.

---

## Items the Plan Misses

### Critical (should be in the plan)

1. **`.env` contains real API keys and is tracked in git**
   - `.env` has 11 lines with real keys: `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `EXA_API_KEY`, `TAVILY_API_KEY`
   - `.gitignore` already lists `.env` — meaning it was *intended* to be ignored, but the file is not currently tracked (`git ls-files .env` returns empty). However the forward audit claims it IS tracked. This must be verified.
   - **The plan says "verify no secrets in git history" but never mentions verifying `.env` itself or creating `.env.example`.** The secrets verification commands only scan `.secret` and `keystore*` patterns — they miss `.env` entirely.
   - **Missing action**: Create `.env.example` with placeholder values for onboarding.

2. **`nexus.db` is NOT empty — the plan's core assumption is false**
   - Plan claims: "nexus.db is empty (0 rows), will be recreated by app startup"
   - Reality: `nexus.db` is 36,864 bytes with 4 tables: `tasks`, `results`, `sessions`, `messages`
   - The plan says `git rm --cached nexus.db` without checking if it has data
   - **Missing**: A data preservation step. Either export the data first, or accept data loss explicitly with a warning.

3. **`tests/conftest.py:49` hardcodes `nexus.db` — Phase 1 will break tests**
   - `_db = _DBM("nexus.db")` — if the DB path changes to `data/nexus.db`, this conftest breaks
   - The plan updates `config/nexusagent.yaml` but never mentions updating `tests/conftest.py`
   - **Missing**: Add `tests/conftest.py` to the Modified files list.

4. **`fetch_url` is already implemented and already registered — Phase 7 is confused**
   - `research.py:fetch_url()` is already fully implemented (160+ lines, httpx-based, with HTML-to-text conversion)
   - `register_all.py` already registers `fetch_url` from `nexusagent.tools.research`
   - The plan conflates `orchestration.py:_fetch()` (the TODO stub) with `research.py:fetch_url()` (already done)
   - **The plan says "Add to tool registry — Register fetch_url as a tool in register_all.py" — this already exists**
   - **Missing**: Clarification that only `_fetch()` in orchestration.py needs implementing (and it can delegate to the existing `fetch_url`). Remove the register_all.py step.

5. **`.serena/`, `.llxprt/`, `.vtcode/`, `.remember/`, `.reports/` are in git — plan doesn't mention removing them**
   - These IDE state directories are tracked: `.serena/project.yml`, `.llxprt/LLXPRT.md`, `.vtcode/README.md`, etc.
   - The plan adds them to `.gitignore` but never runs `git rm --cached` on the existing tracked files
   - **Missing**: `git rm -r --cached .serena/ .llxprt/ .vtcode/ .remember/ .reports/` commands.

6. **`mkdocs.yml` references files the plan deletes — Phase 3 will break `mkdocs build`**
   - `getting_started.md` is in nav at line 56 → plan deletes it
   - `env_execution_guide.md` is in nav at line 58 → plan deletes it
   - `AUDIT_REPORT.md` is in nav at line 79 → plan moves it to archive/
   - `competitive-analysis-2026-06-06.md` is in nav at line 80 → plan deletes it
   - The plan says "Update mkdocs.yml" but doesn't specify which nav entries to change
   - **Missing**: Explicit nav entry remappings in the plan's action items.

### Important (quality improvement)

7. **`tui.py` at 1,433 lines is deferred without analysis**
   - The plan says "defer" but doesn't explain why or set acceptance criteria for when it gets addressed
   - `tui.py` is the single largest source file — it likely contains extractable submodules (widgets are already separate, but the main app class is monolithic)
   - **Missing**: A note in the plan explaining the deferral rationale and a ticket/link for follow-up.

8. **`memory_index.py` at 717 lines and `session.py` at 677 lines are unmentioned**
   - The plan claims to address "code organization issues" but skips two of the largest source files
   - `memory_index.py` (717 lines) is nearly as large as `tui.py` and likely has extractable concerns
   - `session.py` (677 lines) manages conversation lifecycle — a complex domain that may benefit from decomposition
   - **Missing**: Explicit decision (defer + rationale or include in plan).

9. **Duplicate tool files: `todo.py` (120 lines) vs `write_todos.py` (118 lines)**
   - `todo.py` exports `todowrite()` and `todoread()` — operates on TODO.md in markdown format
   - `write_todos.py` exports `write_todos()` and `read_todos()` — operates on todos.json in JSON format
   - `register_all.py` only registers `write_todos`/`read_todos` (from `write_todos.py`)
   - `todo.py` functions are NOT registered as tools — they're dead code (used only by `tests/test_tools/test_todo.py`)
   - The plan mentions consolidating test files but never addresses the duplicate implementation
   - **Missing**: Decision to either (a) delete `todo.py` and update tests to use `write_todos`, or (b) register `todowrite`/`todoread` and deprecate `write_todos`.

10. **`test_fs.py` vs `test_fs_enhanced.py` merge will be lossy**
    - `test_fs.py` has 1 test function (`test_fs_tools`)
    - `test_fs_enhanced.py` has 6 test functions covering edge cases (recursive listing, write_multiple, read_multiple, etc.)
    - The plan says "merge into single `tests/tools/test_fs.py`" but the merge direction matters — merging into `test_fs.py` loses the enhanced test names/function structure
    - **Missing**: Direction specification (merge `test_fs.py` INTO `test_fs_enhanced.py` would preserve more tests, then rename).

11. **`.env.example` does not exist**
    - No template file for environment variables
    - The plan creates `sync-secrets.py` but doesn't create a bootstrap `.env.example`
    - **Missing**: Create `.env.example` with all required env vars (GEMINI_API_KEY, OPENROUTER_API_KEY, EXA_API_KEY, TAVILY_API_KEY) and placeholder values.

12. **`nexusagent.service` fix is described incorrectly**
    - Plan says "Fix entrypoint to use `nexus-server` console script"
    - The service already works with `main.py server`. Switching to `nexus-server` requires the venv to be in PATH or using the full path to the script
    - The service also uses bare `python3` instead of the venv Python
    - **Missing**: Accurate description of what the fix should be, or remove this action if it's unnecessary.

13. **`docs/SECRETS_SYNC.md` doesn't exist yet — the plan never creates it properly**
    - The plan lists `docs/SECRETS_SYNC.md` in "Created" files but the mkdocs.yml nav doesn't include it
    - The plan creates `scripts/sync-secrets.py` but doesn't add a console script entry in `pyproject.toml`
    - **Missing**: Add `sync-secrets` entry to `pyproject.toml` scripts section; add `SECRETS_SYNC.md` to mkdocs nav.

14. **Path inconsistency in Phase 5**
    - Plan says create `scripts/sync-secrets-config.yaml` in the Created files list
    - But the config section shows `config/secrets-sync.yaml`
    - **Missing**: Resolve the path discrepancy.

15. **`FILE_AUDIT.md` (305 lines) and `plan-audit-forward.md` (in docs/) are not addressed**
    - `FILE_AUDIT.md` is a large audit document — should it be archived?
    - `plan-audit-forward.md` is the forward audit output — should it be moved to `.hermes/plans/` or archived?
    - These are artifacts of the audit process, not permanent documentation
    - **Missing**: Decision on where these audit artifacts belong.

### Nice-to-Have (future work)

16. **`.pre-commit-config.yaml` references old ruff version (v0.4.2)**
    - Plan doesn't mention updating or removing this file
    - Modern ruff config can live in `pyproject.toml`

17. **`.python-version` is redundant with `pyproject.toml` `requires-python`**
    - Single-line file (`3.14`) that duplicates `pyproject.toml` config

18. **`COMPETITIVE_ANALYSIS.md` in root is more recent (2026-07-16) but `docs/CODEBASE_MAP.md` was also dated 2026-07-16 and claims to be the merged version**
    - The plan says keep root `COMPETITIVE_ANALYSIS.md` and delete the docs/ version
    - But `CODEBASE_MAP.md`'s header says "Generated: 2026-07-16" — suspicious timing

19. **`.remember/` directory has files with restrictive permissions (`drwx------`)**
    - Contains logs and memory files with owner-only access
    - Not blocking, but unusual for a project directory

20. **No CI/CD pipeline exists**
    - No `.github/` directory means no automated testing on push/PR
    - The plan doesn't mention creating one (acceptable for a solo project, but worth noting)

---

## Phase Gaps

### Phase 1: Security & .gitignore Hardening
- **Misses**: `.env` secret management (no `.env.example`, no history scan for `.env`)
- **Misses**: IDE directories tracked in git (`.serena/`, `.llxprt/`, etc.) — need `git rm -r --cached`
- **Misses**: `tests/conftest.py` references `nexus.db` directly — must be updated alongside config
- **Wrong claim**: `nexus.db` is "empty (0 rows)" — it has 4 tables; data loss risk unassessed
- **Missing validation**: After removing `nexus.db`, verify the app still starts (conftest may fail first)

### Phase 2: Root Cruft Cleanup
- **Misses**: `vtcode.toml` move to `.vtcode/config.toml` — doesn't mention that `.vtcode/README.md` already exists there (potential conflict)
- **Misses**: `nexusagent.service` fix description is inaccurate (see item 12)
- **Misses**: `BACKLOG.md` deletion loses feature tracking not covered by the roadmap
- **No gap** in the actual deletion list — files are correctly identified as cruft

### Phase 3: Documentation Consolidation
- **Misses**: `mkdocs.yml` nav entries for `getting_started.md`, `env_execution_guide.md`, `AUDIT_REPORT.md`, `competitive-analysis-2026-06-06.md` — all will become broken links after deletion
- **Misses**: `docs/index.md` links to `getting_started.md` and `env_execution_guide.md` — must be updated
- **Misses**: `plan-audit-forward.md` and `FILE_AUDIT.md` not addressed
- **Misses**: No mention of `CONTRIBUTINGS.md` link updates (the plan says update `CONTRIBUTING.md` but it's the root version being deleted, not the docs/ version)
- **Wrong**: Plan says `SECURITY.md` and `CODE_OF_CONDUCT.md` are "keep (if we add real content)" in the target state — but Phase 2 already deletes them. Contradiction in the plan.

### Phase 4: Test Directory Consolidation
- **Misses**: `test_fs.py` has only 1 test, `test_fs_enhanced.py` has 6 — merge direction matters
- **Misses**: `tests/test_tools/test_todo.py` tests `todo.py` (unregistered), while `test_new_tools.py` tests `write_todos.py` (registered). After consolidation, the `todo.py` tests become orphaned.
- **Misses**: `contract_verification/` directory — not mentioned at all. Has 5 test files (251 lines) that may overlap with other tests
- **Baseline discrepancy**: Plan says 476 tests baseline. Forward audit counts 483. Plan doesn't explain the discrepancy.

### Phase 5: Secrets Sync Infrastructure
- **Misses**: `.env.example` creation (needed for onboarding)
- **Misses**: Secret rotation strategy (what happens when a key changes?)
- **Misses**: Initial bootstrap (how do secrets get onto the workstation the first time?)
- **Misses**: `pyproject.toml` console script entry for `sync-secrets`
- **Misses**: `docs/SECRETS_SYNC.md` not in mkdocs nav
- **Path inconsistency**: `scripts/sync-secrets-config.yaml` vs `config/secrets-sync.yaml`

### Phase 6: worktree-worker.py Modernization
- **Misses**: No mention of testing the new commands
- **Misses**: The script's existing 438 lines aren't analyzed for current issues
- **Low risk**: This phase is well-scoped and isolated

### Phase 7: orchestration.py fetch_url Implementation
- **CRITICAL confusion**: `fetch_url` is already implemented in `research.py` and registered in `register_all.py`
- The plan says "Add to tool registry" — this is already done
- The actual TODO is `_fetch()` in `orchestration.py` — a private method that could delegate to the existing `fetch_url`
- **Missing**: Clarification of the distinction between `research.py:fetch_url` (done) and `orchestration.py:_fetch` (TODO)

### Phase 8: Final Verification & Push
- **Misses**: `mypy` type checking (the Makefile has a `typecheck` target but Phase 8 doesn't mention it)
- **Misses**: `ruff format --check` (the Makefile `check` target includes format checking)
- **Misses**: Verification that `mkdocs build` succeeds (Phase 3 validates this, but Phase 8 should re-validate after all phases)
- **Misses**: Push to research branches is mentioned but not verified (are those branches still needed?)

---

## File Gaps

### Files the plan should touch but doesn't

| File | Why It Should Be Touched |
|------|--------------------------|
| `tests/conftest.py` | Hardcodes `nexus.db` — breaks when DB path changes to `data/nexus.db` |
| `docs/index.md` | Links to `getting_started.md` and `env_execution_guide.md` which are deleted |
| `mkdocs.yml` | Nav references 4 files that are deleted/moved: `getting_started.md`, `env_execution_guide.md`, `AUDIT_REPORT.md`, `competitive-analysis-2026-06-06.md` |
| `.env` | Contains real API keys — needs history verification and `.env.example` creation |
| `src/nexusagent/tools/todo.py` | Dead code (not registered, superseded by `write_todos.py`) |
| `src/nexusagent/config.py` | `db_path` default is `"nexus.db"` — should be `"data/nexus.db"` to match the new structure |
| `pyproject.toml` | Should add `sync-secrets` console script entry |
| `docs/SECRETS_SYNC.md` | Listed as created but not added to mkdocs nav |
| `docs/FILE_AUDIT.md` | Audit artifact — should be archived or deleted |
| `docs/plan-audit-forward.md` | Audit artifact — should be moved to `.hermes/plans/` or archived |

### Files the plan deletes that have dependencies

| File | Dependent Files |
|------|-----------------|
| `docs/getting_started.md` | `mkdocs.yml` (nav), `docs/index.md` (link) |
| `docs/env_execution_guide.md` | `mkdocs.yml` (nav), `docs/index.md` (link) |
| `docs/AUDIT_REPORT.md` | `mkdocs.yml` (nav) |
| `docs/competitive-analysis-2026-06-06.md` | `mkdocs.yml` (nav) |
| `tests/test_tools/test_todo.py` | Tests `todo.py` which is unregistered — orphaned tests |
| `tests/tools/test_fs_enhanced.py` | 6 tests that must be preserved in merge |

### Files that exist but aren't in the plan at all

| File | Status |
|------|--------|
| `.serena/project.yml` | Tracked in git, should be removed |
| `.llxprt/LLXPRT.md` | Tracked in git, should be removed |
| `.vtcode/README.md` | Tracked in git, should be removed |
| `.reports/codemap-diff.txt` | Tracked in git, should be removed |
| `src/nexusagent.egg-info/` | Directory exists on disk (not tracked but generated) |
| `.remember/logs/` | Contains memory logs, tracked in git |
| `tests/contract_verification/` | 5 test files, not mentioned in plan |

---

## Risk Gaps

### Risks the plan doesn't address

1. **Data loss from `nexus.db` removal**
   - Risk: The DB has 4 tables with unknown row counts
   - Plan says it's "empty" — this is unverified
   - No rollback procedure if the app fails to start after removal
   - **Mitigation needed**: Check row counts before removal, backup the file, document the expected state

2. **Test baseline mismatch**
   - Plan claims 476 tests; forward audit counts 483
   - After consolidation, the count may change further
   - **Mitigation needed**: Establish the actual baseline before starting, document expected count changes

3. **`mkdocs build` failure after doc moves**
   - 4 nav entries will break after Phase 3
   - Internal links in `docs/index.md` will break
   - **Mitigation needed**: Run `mkdocs build` after each doc move, not just at phase end

4. **Orphaned `todo.py` tests**
   - `tests/test_tools/test_todo.py` tests `nexusagent.tools.todo` (unregistered)
   - After moving to `tests/tools/`, these tests still test dead code
   - **Mitigation needed**: Either delete `todo.py` and its tests, or register `todowrite`/`todoread`

5. **`.env` secret leak in git history**
   - Plan scans for `.secret` and `keystore*` but not `.env`
   - If `.env` was ever committed (even if now ignored), secrets are in history
   - **Mitigation needed**: Scan `git log --all -- .env` and use `git-filter-repo` or BFG if found

6. **No rollback procedure**
   - The plan has no rollback steps if a phase fails
   - If Phase 3 breaks `mkdocs build`, there's no guidance on how to recover
   - **Mitigation needed**: Commit after each phase, document `git revert` procedure

7. **Secrets sync chicken-and-egg problem**
   - `sync-secrets.py` requires SSH access and a configured server
   - The plan doesn't document initial setup (how secrets get onto the workstation)
   - No secret rotation procedure
   - **Mitigation needed**: Document initial bootstrap and rotation in `SECRETS_SYNC.md`

8. **`config/nexusagent.yaml` change affects all environments**
   - Changing `db_path` from `nexus.db` to `data/nexus.db` affects the remote server too
   - The plan doesn't mention updating the remote server's config
   - **Mitigation needed**: Include remote server config update in Phase 1 or Phase 5

---

## Recommended Additions

### Must-Have (before execution)

1. **Verify `nexus.db` data before deletion**
   ```bash
   python3 -c "import sqlite3; conn=sqlite3.connect('nexus.db'); [print(t[0], conn.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]) for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]; conn.close()"
   ```

2. **Add `tests/conftest.py` to Phase 1 Modified files**
   - Update `_db = _DBM("nexus.db")` to `_db = _DBM("data/nexus.db")`

3. **Add `.env` verification to Phase 1**
   - Scan `git log --all -- .env` for accidental commits
   - Create `.env.example` with placeholder values

4. **Fix Phase 7 description**
   - Remove "Register fetch_url in register_all.py" (already done)
   - Clarify that `_fetch()` in `orchestration.py` should delegate to existing `research.py:fetch_url()`

5. **Add `git rm -r --cached` for IDE directories in Phase 1**
   - `.serena/`, `.llxprt/`, `.vtcode/`, `.remember/`, `.reports/`

6. **Add explicit mkdocs nav updates to Phase 3**
   - Remove `getting_started.md`, `env_execution_guide.md`, `AUDIT_REPORT.md`, `competitive-analysis-2026-06-06.md` from nav
   - Add `archive/` entries if desired

7. **Add `docs/index.md` link updates to Phase 3**
   - Remove links to `getting_started.md` and `env_execution_guide.md`

8. **Resolve `todo.py` vs `write_todos.py` duplication**
   - Either delete `todo.py` and its tests, or register `todowrite`/`todoread` and deprecate `write_todos`

### Should-Have (during execution)

9. **Commit after each phase**
   - Enables `git revert` if a phase breaks something
   - Provides clear audit trail

10. **Run `mkdocs build` after each doc move in Phase 3**
    - Don't wait until end of phase to discover broken links

11. **Add `sync-secrets` to `pyproject.toml` scripts**
    - `sync-secrets = "nexusagent.scripts.sync_secrets:main"` (or similar)

12. **Add `docs/SECRETS_SYNC.md` to mkdocs nav**
    - Under a new "Operations" or "Deployment" section

### Nice-Have (future work)

13. **Create GitHub Actions CI workflow**
    - Run tests, lint, typecheck on push/PR
    - Build mkdocs to catch broken links

14. **Add `mypy` to Phase 8 verification**
    - The Makefile has a `typecheck` target

15. **Archive `FILE_AUDIT.md` and `plan-audit-forward.md`**
    - Move to `docs/archive/` or delete

16. **Update `.pre-commit-config.yaml`**
    - Modernize ruff version or move config to `pyproject.toml`

17. **Consider splitting `tui.py`**
    - 1,433 lines is a maintainability risk
    - Extract: theme management, key bindings, screen layouts

18. **Consider splitting `memory_index.py`**
    - 717 lines with likely extractable concerns (vector search, FTS5 indexing, embedding management)

---

## Summary

The plan is **well-structured and mostly complete** but has several critical gaps:

- **3 critical factual errors**: `nexus.db` is not empty, `fetch_url` is already implemented, `tests/conftest.py` references old DB path
- **5 missing files from modification list**: `tests/conftest.py`, `docs/index.md`, `mkdocs.yml` (nav details), `config.py` (default db_path), `pyproject.toml` (console script)
- **2 missing files from deletion list**: `.serena/`, `.llxprt/`, `.vtcode/`, `.remember/`, `.reports/` (tracked in git, need `git rm --cached`)
- **1 unresolved duplication**: `todo.py` vs `write_todos.py`
- **1 missing creation**: `.env.example`
- **No rollback procedure** documented
- **No remote server config update** for DB path change

The plan should be updated with these findings before execution.
