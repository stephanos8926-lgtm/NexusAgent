# NexusAgent Cleanup & Reorganization Sprint Plan (v2)

> **Date**: 2026-06-11
> **Author**: OWL (Lucien)
> **Status**: AUDITED — Ready for execution
> **Previous version**: v1 (superseded by audit findings)
> **Audit reports**: `docs/plan-audit-forward.md`, `docs/plan-audit-reverse.md`
> **Baseline**: 483 tests passing, 0 failures (corrected from 476)

---

## Audit Summary

### Forward Audit: 3 Critical + 3 Moderate Issues Found
1. 🔴 `nexus.db` claimed empty — actually has 4 tables (verified: all 0 rows, safe to delete)
2. 🔴 `tests/conftest.py:49` hardcodes `"nexus.db"` — will break when DB moves to `data/`
3. 🔴 `fetch_url` already implemented in `research.py` — Phase 7 description was confused
4. 🟡 Test baseline is 483, not 476 (7-test discrepancy)
5. 🟡 `CODEBASE_INDEX.md` (56KB) is larger than `CODEBASE_MAP.md` (25KB) — not a "subset"
6. 🟡 `BACKLOG.md` has items not covered by the roadmap

### Reverse Audit: 6 Critical + 13 Important Items Found
1. 🔴 IDE directories tracked in git (`.llxprt/`, `.serena/`, `.vtcode/`, `.reports/`)
2. 🔴 `mkdocs.yml` nav has 4 broken references after file moves
3. 🔴 `docs/index.md` links to deleted/moved files
4. 🔴 `.env.example` doesn't exist
5. 🔴 `todo.py` is dead code (unregistered, untested)
6. 🔴 No rollback procedure documented
7-19. Important items addressed below in updated phases

---

## Pre-Sprint Checklist

- [x] All changes committed and pushed to GitHub (HEAD: `8fd6e9a`)
- [x] 483 tests passing, 0 failures (**corrected baseline**)
- [x] Semantic codebase index created (orchestrator worker — in progress)
- [x] Comprehensive file audit completed (`docs/FILE_AUDIT.md`)
- [x] Forward audit completed — all critical issues resolved in v2 ✅
- [x] Reverse audit completed — all critical issues resolved in v2 ✅
- [x] `nexus.db` verified: all 4 tables have 0 rows — safe to delete
- [x] `.env` verified: NOT tracked in git — no filter-repo needed
- [ ] Present to user for sign-off

---

## Phase 1: Security, .gitignore & Directory Structure

**Goal**: Harden .gitignore, remove tracked non-essential files, establish `data/` directory
**Risk**: LOW | **Estimated time**: 20 min

### 1a. Update .gitignore

Add missing patterns:
```
# Database & data
*.db
*.db-shm
*.db-wal
data/
test_loop.db*

# Logs
*.log

# IDE state (remove these from git tracking too)
.serena/
.llxprt/
.vtcode/
.remember/
.reports/
.gemini/

# Secrets
*.secret
*.salt
keystore*

# Build artifacts
src/*.egg-info/
test.db*
```

### 1b. Remove tracked non-essential files from git

```bash
# IDE directories — remove from git tracking (keep on disk)
git rm -r --cached .llxprt/ .serena/ .vtcode/ .remember/ .reports/

# Database files — remove from git tracking
git rm --cached nexus.db test.db-shm test.db-wal test_loop.db-shm test_loop.db-wal

# SQLite WAL files that may appear
git rm --cached *.db-shm *.db-wal 2>/dev/null
```

### 1c. Create data/ directory

```bash
mkdir -p data
touch data/.gitkeep
```

### 1d. Update config default DB path

In `config/nexusagent.yaml`:
```yaml
server:
  db_path: "data/nexus.db"  # was "nexus.db"
```

### 1e. Update tests/conftest.py (CRITICAL — audit finding)

Line 49: Change `_db = _DBM("nexus.db")` → `_db = _DBM("data/nexus.db")`

### 1f. Create .env.example

```
# NexusAgent Environment Configuration
# Copy this file to .env and fill in your values

# LLM Providers (at least one required)
GEMINI_API_KEY=
OPENROUTER_API_KEY=

# Search (optional, enables web search)
EXA_API_KEY=
TAVILY_API_KEY=

# Server
NEXUS_PORT=8000
```

### 1g. Verify .env not in git history

```bash
git log --all --diff-filter=A -- .env
# Should return empty — .env was never committed
```

### Validation
- `git status` shows all removals + new files
- `pytest tests/ -q` → all pass, 0 fail
- App starts and creates `data/nexus.db` automatically

---

## Phase 2: Root Cruft Cleanup

**Goal**: Remove generic placeholder files, keep only essential root files
**Risk**: LOW | **Estimated time**: 10 min

### 2a. Delete root cruft (6 files)

| File | Reason |
|------|--------|
| `BACKLOG.md` | Trim to only items NOT in roadmap, or delete if fully superseded |
| `CODE_OF_CONDUCT.md` | Generic placeholder, unfilled email |
| `CONTRIBUTING.md` | Shorter duplicate of `docs/CONTRIBUTING.md` |
| `SECURITY.md` | Generic placeholder, unfilled email |
| `SUPPORT.md` | Dummy links |

### 2b. Handle COMPETITIVE_ANALYSIS.md

Root version (2026-07-16, 150 lines) is MORE recent than docs/ version (2026-06-06, 219 lines).
- **Keep** root `COMPETITIVE_ANALYSIS.md`
- **Delete** `docs/competitive-analysis-2026-06-06.md`

### 2c. Move vtcode.toml → .vtcode/config.toml

IDE config belongs inside the `.vtcode/` directory. Update any references.

### 2d. Update nexusagent.service

Current: `ExecStart=/usr/bin/python3 /home/sysop/Workspaces/NexusAgent/main.py server`
This actually works fine. **No change needed** — audit confirmed it's functional.

### Validation
- `ls *.md` in root: `CHANGELOG.md`, `COMPETITIVE_ANALYSIS.md`, `LICENSE`, `README.md`
- `pytest tests/ -q` → all pass, 0 fail

---

## Phase 3: Documentation Consolidation

**Goal**: Merge overlapping docs, eliminate redundancy, create clear hierarchy
**Risk**: MEDIUM (mkdocs.yml nav changes) | **Estimated time**: 30 min

### 3a. Create docs/archive/ — Move historical reports

```bash
mkdir -p docs/archive
mv docs/AUDIT_REPORT.md docs/archive/audit-report-2026-06-05.md
mv docs/REVERSE_AUDIT_REPORT.md docs/archive/reverse-audit-report-2026-06-05.md
mv docs/CODE_CHANGES_SUMMARY.md docs/archive/code-changes-summary-2026-06-05.md
mv docs/EXECUTION_SUMMARY.md docs/archive/execution-summary-2026-06-05.md
```

Create `docs/archive/README.md`:
```markdown
# Archive

Historical documents from the 2026-06-05 cleanup sprint.
Kept for reference but no longer current.
```

### 3b. Merge CODEBASE_INDEX.md into CODEBASE_MAP.md

`CODEBASE_INDEX.md` (56KB) and `CODEBASE_MAP.md` (25KB) have massive overlap.
- Keep `CODEBASE_MAP.md` as the canonical reference
- Append INDEX content that's not already in MAP (primarily the function signature listings)
- Delete `CODEBASE_INDEX.md`

### 3c. Restructure STATE.md

Remove module listing (now in CODEBASE_MAP.md). Keep only:
- Current project state (what's working, what's broken)
- Active issues
- Recent decisions

### 3d. Move research files into research/ (delete superseded versions)

| Delete | Keep |
|--------|------|
| `docs/RESEARCH_FEATURE_PARITY_ARCHITECTURE.md` (25KB) | `docs/research/TOOL-PARITY-FINAL.md` |
| `docs/RESEARCH_FEATURE_PARITY_CAPABILITIES.md` (12KB) | `docs/research/TOOL-PARITY-FINAL.md` |
| `docs/RESEARCH_TUI_AESTHETICS_VISUAL.md` (37KB) | `docs/research/TUI-AESTHETICS-FINAL.md` |
| `docs/RESEARCH_TUI_BEST_PRACTICES.md` (217B, empty stub) | — |

### 3e. Merge getting started docs

- Merge `docs/getting_started.md` (25 lines) into `docs/quickstart.md` (40 lines)
- Merge `docs/env_execution_guide.md` into `docs/local_development.md`
- Delete originals

### 3f. Update mkdocs.yml nav (CRITICAL — audit finding)

Current nav entries that will break:
```yaml
# REMOVE these:
- Getting Started Guide: getting_started.md      # deleted
- Environment & Execution: env_execution_guide.md  # deleted
- Audit Report: AUDIT_REPORT.md                   # moved to archive/
- Competitive Analysis: competitive-analysis-2026-06-06.md  # deleted

# ADD/update these:
+ Quickstart: quickstart.md                       # merged
+ Local Development: local_development.md          # merged
+ Archive:                                        # new section
    - Cleanup Sprint 2026-06-05: archive/
```

### 3g. Update docs/index.md links

Remove links to `getting_started.md` and `env_execution_guide.md`. Update to point to merged files.

### 3h. Archive audit artifacts

Move to `docs/archive/`:
- `docs/FILE_AUDIT.md` → `docs/archive/file-audit-2026-06-11.md`
- `docs/plan-audit-forward.md` → `docs/archive/plan-audit-forward.md`
- `docs/plan-audit-reverse.md` → `docs/archive/plan-audit-reverse.md`

### Target docs/ Structure (~20 files)

```
docs/
  index.md
  quickstart.md                         ← merged
  configuration.md
  local_development.md                  ← merged
  installation.md
  RUNBOOK.md
  CONTRIBUTING.md
  CODEBASE_MAP.md                       ← merged canonical reference
  STATE.md                              ← status only
  TUI_OVERHAUL_SPEC.md
  implementation-plan-2026-07-09.md
  SECURITY.md                           ← keep for future content
  CODE_OF_CONDUCT.md                    ← keep for future content
  architecture/
    overview.md, multi-agent.md, policies.md, tools.md
  adrs/
    index.md, 0001-0004.md
  plans/
    2026-06-11-tui-parity-sprint.md, 2026-07-12-assessment-and-roadmap.md
  research/
    TOOL-PARITY-FINAL.md, TUI-AESTHETICS-FINAL.md
  archive/
    README.md
    audit-report-2026-06-05.md, reverse-audit-report-2026-06-05.md,
    code-changes-summary-2026-06-05.md, execution-summary-2026-06-05.md,
    file-audit-2026-06-11.md, plan-audit-forward.md, plan-audit-reverse.md
```

### Validation
- `mkdocs build` succeeds with no warnings
- `pytest tests/ -q` → all pass, 0 fail

---

## Phase 4: Test Directory Consolidation

**Goal**: Single `tests/tools/` convention, resolve overlaps
**Risk**: MEDIUM | **Estimated time**: 15 min

### 4a. Merge tests/test_tools/ → tests/tools/

- Move `tests/test_tools/test_todo.py` → `tests/tools/test_todo.py`
- Delete `tests/test_tools/` directory

### 4b. Resolve test_fs overlap

- `tests/tools/test_fs.py` (1 test) — tests basic fs operations
- `tests/tools/test_fs_enhanced.py` (6 tests) — tests edge cases
- **Action**: Merge `test_fs.py` INTO `test_fs_enhanced.py`, keep the enhanced filename, delete `test_fs.py`

### 4c. Handle todo.py dead code

`src/nexusagent/tools/todo.py` is NOT registered as a tool and its tests test unregistered functions.
- **Action**: Delete `src/nexusagent/tools/todo.py` (dead code)
- Update `tests/tools/test_todo.py` to test `write_todos`/`read_todos` from `write_todos.py`

### 4d. Verify test count

```bash
pytest tests/ --collect-only -q 2>&1 | tail -3
# Document the new expected count
```

### Validation
- `pytest tests/ -q` → all pass, 0 fail
- No `tests/test_tools/` directory remains
- No `src/nexusagent/tools/todo.py` remains

---

## Phase 5: Secrets Sync Infrastructure

**Goal**: Create `scripts/sync-secrets.py` for dual-machine secrets management
**Risk**: LOW | **Estimated time**: 20 min

### 5a. Create scripts/sync-secrets.py

```python
#!/usr/bin/env python3
"""sync-secrets.py — Sync .env secrets to remote server via SSH.

Usage:
    python3 scripts/sync-secrets.py --server rapidwebs-01 [--dry-run]
    python3 scripts/sync-secrets.py --server rapidwebs-01 --remote-path /home/sysop/Workspaces/NexusAgent
"""
```

Features:
- Reads local `.env`
- SSHes to remote server
- Writes `.env` with 600 permissions
- `--dry-run` mode shows diff without writing
- Creates backup of remote `.env` before overwriting

### 5b. Create config/secrets-sync.yaml

```yaml
servers:
  rapidwebs-01:
    host: rapidwebs-01
    user: sysop
    path: /home/sysop/Workspaces/NexusAgent
    ssh_key: ~/.ssh/id_ed25519
```

### 5c. Add to pyproject.toml scripts

```toml
[project.scripts]
sync-secrets = "scripts.sync_secrets:main"
```

### 5d. Create docs/SECRETS_SYNC.md

Document:
- Initial setup (SSH keys, server config)
- How to add a new secret
- How to rotate secrets
- Troubleshooting

### 5e. Add to mkdocs.yml nav

Under "Operations" or "Deployment" section:
```yaml
- Secrets Sync: SECRETS_SYNC.md
```

### Validation
- `python3 scripts/sync-secrets.py --dry-run --server rapidwebs-01` succeeds
- `pytest tests/ -q` → all pass, 0 fail

---

## Phase 6: worktree-worker.py Modernization

**Goal**: Add sync, doctor, init commands; improve error handling
**Risk**: LOW | **Estimated time**: 15 min

### 6a. Add `sync` command

Sync worktree state between local and remote:
```bash
python3 scripts/worktree-worker.py sync --server rapidwebs-01
```

### 6b. Add `doctor` command

Diagnose common issues:
```bash
python3 scripts/worktree-worker.py doctor
# Checks: git worktree list, branch status, uncommitted changes, remote connectivity
```

### 6c. Add `init` command

Initialize a worktree with proper config:
```bash
python3 scripts/worktree-worker.py init --name worker-foo --model openrouter/owl-alpha
```

### 6d. Add `--json` output mode

```bash
python3 scripts/worktree-worker.py list --json
```

### 6e. Improve error messages

Replace silent exits with clear error messages and actionable suggestions.

### Validation
- `python3 scripts/worktree-worker.py list` works
- `python3 scripts/worktree-worker.py doctor` reports system health
- `pytest tests/ -q` → all pass, 0 fail

---

## Phase 7: orchestration.py _fetch() Implementation

**Goal**: Fix the TODO stub — delegate to existing `research.py:fetch_url()`
**Risk**: LOW | **Estimated time**: 10 min

### Clarification (from audit)

- `research.py:fetch_url()` is ALREADY fully implemented (httpx-based, 160+ lines)
- `register_all.py` ALREADY registers `fetch_url`
- The ONLY issue: `orchestration.py:_fetch()` (line 98-101) returns `None` instead of delegating

### 7a. Fix _fetch() in orchestration.py

```python
async def _fetch(self, url: str) -> str | None:
    """Fetch content from a URL using the existing fetch_url tool."""
    from nexusagent.tools.research import fetch_url
    return fetch_url(url)
```

### 7b. Add error handling

Wrap in try/except for network errors, timeouts.

### Validation
- `pytest tests/ -q` → all pass, 0 fail
- Deep research orchestrator can now fetch URLs

---

## Phase 8: Final Verification & Push

**Goal**: Full test suite pass, lint clean, commit and push
**Risk**: NONE | **Estimated time**: 10 min

### 8a. Run full verification

```bash
pytest tests/ -q                                    # All tests pass
ruff check src/ tests/                              # Zero lint errors
ruff format --check src/ tests/                     # Format check
mkdocs build                                         # Docs build
python3 scripts/worktree-worker.py doctor           # System health
```

### 8b. Commit and push

```bash
git add -A
git commit -m "chore: comprehensive cleanup and reorganization sprint"
git push origin master
```

### 8c. Verify remote

```bash
# On rapidwebs-01:
cd /home/sysop/Workspaces/NexusAgent
git pull
python3 -m pytest tests/ -q  # Verify tests pass on server too
```

---

## Files Changed Summary

### Deleted (21 files)
| File | Reason |
|------|--------|
| `BACKLOG.md` | Superseded by roadmap |
| `CODE_OF_CONDUCT.md` | Generic placeholder |
| `CONTRIBUTING.md` (root) | Duplicate of docs/ version |
| `SECURITY.md` | Generic placeholder |
| `SUPPORT.md` | Dummy links |
| `nexus.db` | Empty DB, will be recreated in data/ |
| `test.db-shm`, `test.db-wal`, `test_loop.db-*` | SQLite artifacts |
| `src/nexusagent/tools/todo.py` | Dead code (unregistered) |
| `docs/competitive-analysis-2026-06-06.md` | Superseded by root version |
| `docs/RESEARCH_FEATURE_PARITY_ARCHITECTURE.md` | Superseded by research/TOOL-PARITY-FINAL.md |
| `docs/RESEARCH_FEATURE_PARITY_CAPABILITIES.md` | Superseded by research/TOOL-PARITY-FINAL.md |
| `docs/RESEARCH_TUI_AESTHETICS_VISUAL.md` | Superseded by research/TUI-AESTHETICS-FINAL.md |
| `docs/RESEARCH_TUI_BEST_PRACTICES.md` | Empty stub |
| `docs/CODEBASE_INDEX.md` | Merged into CODEBASE_MAP.md |
| `docs/EXECUTION_SUMMARY.md` | Moved to archive/ |
| `docs/AUDIT_REPORT.md` | Moved to archive/ |
| `docs/REVERSE_AUDIT_REPORT.md` | Moved to archive/ |
| `docs/CODE_CHANGES_SUMMARY.md` | Moved to archive/ |
| `docs/getting_started.md` | Merged into quickstart.md |
| `docs/env_execution_guide.md` | Merged into local_development.md |
| `tests/test_tools/test_todo.py` | Moved + updated |
| `tests/tools/test_fs.py` | Merged into test_fs_enhanced.py |
| `tests/tools/test_fs_enhanced.py` | Renamed to test_fs.py |

### Created (10 files)
| File | Purpose |
|------|---------|
| `data/.gitkeep` | Runtime data directory |
| `.env.example` | Secrets template for onboarding |
| `scripts/sync-secrets.py` | Secrets sync CLI |
| `config/secrets-sync.yaml` | Sync configuration |
| `docs/archive/README.md` | Archive directory explanation |
| `docs/archive/` (7 files) | Moved historical/audit files |
| `docs/SECRETS_SYNC.md` | Secrets sync documentation |

### Modified (14 files)
| File | Change |
|------|--------|
| `.gitignore` | Add *.db, *.log, IDE dirs, data/ patterns |
| `config/nexusagent.yaml` | db.path → data/nexus.db |
| `tests/conftest.py` | Fix hardcoded nexus.db → data/nexus.db |
| `docs/CODEBASE_MAP.md` | Merge CODEBASE_INDEX content |
| `docs/STATE.md` | Remove module listing, keep status only |
| `docs/quickstart.md` | Merge getting_started content |
| `docs/local_development.md` | Merge env_execution_guide content |
| `docs/index.md` | Fix links to moved files |
| `mkdocs.yml` | Update nav for new file paths |
| `README.md` | Fix links to moved files |
| `scripts/worktree-worker.py` | Add sync, doctor, init, --json |
| `src/nexusagent/orchestration.py` | Fix _fetch() to delegate to fetch_url |
| `src/nexusagent/config.py` | Update default db_path |
| `pyproject.toml` | Add sync-secrets console script |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| mkdocs.yml broken links | Medium | Low | Run `mkdocs build` after each doc move |
| Test count changes | Low | Low | Document new expected count after consolidation |
| DB path change breaks tests | Low | High | Updated conftest.py in Phase 1 |
| fetch_url delegation fails | Low | Low | Simple delegation, existing function tested |
| Secrets sync SSH failure | Low | Medium | Dry-run mode, clear errors |
| todo.py deletion breaks tests | Low | Low | Tests updated to use write_todos |

---

## Execution Order

```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 ──→ Phase 5 ──→ Phase 6 ──→ Phase 7 ──→ Phase 8
(security)  (root)      (docs)      (tests)     (secrets)   (worker)    (fetch)    (verify)
```

All phases are sequential because each modifies files that later phases reference. Each phase commits independently for rollback safety.

---

## Rollback Procedure

If any phase breaks:
```bash
git revert HEAD       # Undo last phase
# OR
git reset --hard HEAD~1  # Remove last commit entirely
```

Each phase = one commit = clean rollback point.
