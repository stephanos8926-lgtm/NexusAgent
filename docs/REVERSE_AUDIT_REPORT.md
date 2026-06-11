# Reverse Audit Report: Codebase Cleanup Plan 2026-06-11
**Auditor**: Automated Reverse Audit  
**Date**: 2026-06-11  
**Scope**: Find everything the cleanup plan MISSES or gets WRONG

---

## 🔴 CRITICAL — Secrets, Security Issues, Data Loss Risks

### C1: `.env` file with REAL API keys is in the repo and NOT in `.gitignore`
- **File**: `.env` (542 bytes, committed to git)
- **Contents contain**: `GEMINI_API_KEY`, `EXA_API_KEY`, `TAVILY_API_KEY`, `OPENROUTER_API_KEY` (masked), `NEXUS_SERVER__DB_PATH`, `NEXUS_AGENT__DEFAULT_MODEL`
- **`.gitignore` does NOT list `.env`** — only lists `.env` under a generic pattern? No. The `.gitignore` lists `.env` explicitly. Let me re-check...
- **ACTUAL STATUS**: `.gitignore` line 8 has `.env` — BUT the file is ALREADY tracked by git (it was committed before the .gitignore was updated). `.gitignore` does NOT untrack files already in git history.
- **Risk**: API keys are in git history forever unless `git filter-branch` or `git filter-repo` is used.
- **Plan status**: ❌ NOT MENTIONED AT ALL in the cleanup plan

### C2: `.master.salt` and `.master.secret` — Binary/encrypted secrets in repo
- **Files**: `.master.salt` (16 bytes, binary), `.master.secret` (43 bytes, base64-encoded)
- **What they are**: Used by `auth.py` for key derivation (PBKDF2). These are the encryption keys for the auth keystore.
- **Plan says**: "DELETE" — ✅ Plan identifies these
- **BUT**: They are still tracked in git history. Plan does NOT mention `git filter-branch`/`git filter-repo` to purge from history.
- **Risk**: Even after deletion, secrets persist in `.git/`

### C3: `keystore.json` — Encrypted API keys in repo
- **File**: `keystore.json` (140 bytes, committed)
- **Contents**: `{"openai": "gAAAAA...EtQ="}` — Fernet-encrypted OpenAI API key
- **Plan says**: "DELETE" — ✅ Plan identifies this
- **BUT**: Same git history issue. API key material persists in history.

### C4: `tests/buggy_code.py` — Deliberately vulnerable code committed to repo
- **File**: `tests/buggy_code.py` (872 bytes, committed to git)
- **Contents**: Contains `API_KEY="***"` (hardcoded secret pattern), O(n²) intentional bug, None dereference bug, terrible variable naming (`a(b)`)
- **Purpose**: Appears to be a test fixture for code review tools
- **Risk**: The `API_KEY="***"` pattern looks like a real key to security scanners. Could trigger false positives in secret scanning. Worse, if code review tool test picks this up, it's testing against intentionally bad code.
- **Plan status**: ❌ NOT MENTIONED AT ALL

### C5: `nexusagent.service` references `main.py` which is a STUB
- **File**: `nexusagent.service` (systemd unit, committed)
- **ExecStart**: `/usr/bin/python3 /home/sysop/Workspaces/NexusAgent/main.py server`
- **But `main.py` is**: `def main(): print("Hello from nexusagent!")` — a 4-line STUB
- **Risk**: If someone deploys this service, it will not start the actual server. The real server entrypoint is `nexusagent.server`.
- **Plan status**: ❌ NOT MENTIONED

### C6: `.vtcode/tool-policy.json` contains tool allow/deny rules
- **File**: `.vtcode/tool-policy.json` (5KB, committed)
- **Contents**: Explicit deny rules for `rm *`, `sudo *`, `chmod *`, `kubectl *`, shell bombs. This is a security policy file.
- **Risk**: Not a secret per se, but reveals defensive strategies and tool names. Should be reviewed for whether it should be public.
- **Plan status**: ❌ NOT MENTIONED

### C7: 20+ MB of `.mypy_cache/*.db` SQLite files committed
- **Files**: `.mypy_cache/3.14/cache.0.db` through `.mypy_cache/3.14/cache.15.db`
- **Risk**: These are build artifacts that may contain cached analysis of the full codebase. Could be large and bloat the repo.
- **Plan status**: ❌ NOT MENTIONED — `.gitignore` doesn't have `.mypy_cache/`

---

## 🟠 HIGH — Dead Code, Broken Imports, Missing .gitignore

### H1: Missing `.gitignore` entries
Current `.gitignore`:
```
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info
.venv
site/
.env
.hermes/worktrees/
```

**Missing entries**:
| Pattern | Files affected | Why |
|---------|---------------|-----|
| `*.db` | `nexus.db`, `nexus.db-shm`, `nexus.db-wal` (all committed!) | Database files |
| `*.log` | `server.log`, `.remember/logs/*.log` | Runtime logs |
| `.mypy_cache/` | 16 `.db` files in `.mypy_cache/3.14/` | Type-checker cache |
| `.remember/` | 3 log files + tmp dir + autonomous dir | Runtime state |
| `.vtcode/` | 7 files (history, logs, state, config) | IDE/tool state |
| `.gemini/` | `settings.json` | Tool config |
| `*.pem` | `cacert.pem` in venv | Certificates (covered by `.venv` though) |
| `.llxprt/` | 5+ files (review specs, cache, scripts) | Internal tool artifacts |
| `tests/buggy_code.py` | Test fixture that should be gitignored or removed | Test artifact |
| `tests/__pycache__/` already covered by `__pycache__/` | — | — |

### H2: 238 files committed to repo (plan says 98 source + 46 test + 90 docs = ~234)
- Actual count: 238 tracked files (excluding worktrees)
- The plan's file counts are slightly off but roughly accurate. Not a major issue.

### H3: `main.py` is a stub that doesn't do anything useful
- **File**: `main.py` (4 lines)
- **Content**: Just prints "Hello from nexusagent!"
- But `nexusagent.service` references it as the production entrypoint
- **Plan status**: ❌ NOT MENTIONED

### H4: `.gemini/settings.json` — MCP server config committed
- Commits MCP server configuration (serena)
- Not necessarily a secret, but tool-specific config that shouldn't be in the repo
- **Plan status**: ❌ NOT MENTIONED

### H5: `vtcode.toml` — Full agent config committed
- 60+ lines of agent configuration including `api_key_env = "GEMINI_API_KEY"`, provider settings, tool policies
- Reveals internal tool names, security policies, MCP server configuration
- **Plan status**: ❌ NOT MENTIONED

### H6: `.remember/` directory (3 log files) tracked by `.remember/.gitignore` but no `.gitignore` parent
- `.remember/.gitignore` contains just `*` which should ignore everything inside
- But `.remember/logs/hook-errors.log` (0 bytes), `.remember/logs/memory-2026-06-02.log` (38KB), `.remember/logs/memory-2026-06-05.log` (448 bytes) — these are tracked gitignored files?
- Actually, since `.remember/.gitignore` has `*`, these should be ignored by git. But they exist on disk.
- **Plan status**: ❌ NOT MENTIONED

---

## 🟡 MEDIUM — Duplicates, Inconsistencies, Oversized Files

### M1: `auth.py` + `api_auth.py` — Duplicate auth functionality
- `auth.py` (129 lines): Full `AuthManager` class with PBKDF2 key derivation, Fernet encryption, key storage
- `api_auth.py` (53 lines): FastAPI middleware that ALSO imports from `auth.py` and does key verification
- **Not truly duplicates** — `api_auth.py` depends on `auth.py`. But their purposes could be clearer.
- Plan mentions them only obliquely in Phase 6 (utils/ grouping).
- **Plan status**: ⚠️ Indirectly addressed by Phase 6a (deferred)

### M2: Three memory modules with overlapping purpose
- `memory.py` (440L): `HybridMemoryManager` — semantic + vector memory
- `memory_files.py` (264L): `FileMemory` — file-backed memory entries
- `memory_index.py` (717L): `HybridMemoryIndex` — SQLite-based vector index
- Plus `compaction.py` (233L): Memory summarization/compaction
- Total: 1,654 lines across 4 files for memory management
- These work together but the boundaries are blurry
- **Plan status**: ⚠️ Indirectly addressed by Phase 6a (memory/ grouping, deferred)

### M3: Oversized source files (>500 lines in src/)
| File | Lines | Issue |
|------|-------|-------|
| `tui_legacy.py` | 1,195 | Plan says DELETE ✅ |
| `tools/register_all.py` | 728 | Registered everything; could be split into per-domain registration |
| `memory_index.py` | 717 | Largest active source file |
| `session.py` | 705 | Complex session management + context building |
| `tui.py` | 630 | Main TUI app (complex by nature) |
| `tools/registry.py` | 623 | Large tool registry |

### M4: Oversized test files (>400 lines)
| File | Lines |
|------|-------|
| `test_tui_widgets.py` | 704 |
| `test_orchestration.py` | 582 |
| `test_tui_theme.py` | 443 |
| `test_hooks.py` | 415 |
| `test_tui_responsive.py` | 406 |

### M5: Oversized doc files (>500 lines)
| File | Lines |
|------|-------|
| `docs/plans/2026-07-12-three-topology-execution-model.md` | 2,251 |
| `docs/plans/2026-07-12-hybrid-memory-system.md` | 1,015 |
| `docs/plans/2026-06-07-api-sdk-overhaul.md` | 909 |
| `docs/RESEARCH_TUI_AESTHETICS_VISUAL.md` | 844 |
| `docs/CODEBASE_MAP_CORE.md` | 630 |
| `docs/specs/0001-telemetry-system.md` | 612 |
| `config/NEXUS.md` | 315 (19KB — large system prompt) |

### M6: Naming inconsistency — `hooks/` vs `hook/`
- Plan Phase 6b says "Move `src/nexusagent/hooks/` to `src/nexusagent/hook/` for naming consistency"
- BUT: TUI code still references `nexusagent.hooks` in multiple places:
  - `src/nexusagent/tui.py` line 31: `from nexusagent.hooks import HookEvent, get_hook_manager`
  - Wait, actually let me verify this is consistent...
  - Actually the session.py uses `from nexusagent.hooks import ...` — so the current name is `hooks`
- Plan says to rename to `hook` — this is a separate concern. The plan DOES address this in 6b ✅

### M7: `orchestration.py` uses `TODO: implement` in production code
- Line 99: `"""Fetch content from a URL. TODO: implement with httpx or similar."""`
- The `fetch_url()` method is a stub that just returns a TODO string
- This module is imported by `graph.py` which is imported by `worker.py` — it's in the critical path
- **Plan status**: ❌ NOT MENTIONED

### M8: `tests/test_graph_nodes.py` has hardcoded `sys.path.insert`
- Line: `sys.path.insert(0, "/home/sysop/Workspaces/NexusAgent/src")`
- This is an absolute path that only works on the original developer's machine
- **Plan status**: ❌ NOT MENTIONED

### M9: `.llxprt/` directory committed — LLM review tool artifacts
- Contains review specs, review plans, review cache, scripts, tmp
- These are artifacts from an internal review process
- **Plan status**: ❌ NOT MENTIONED

### M10: `.vtcode/` directory committed — full IDE agent history
- Contains session memory, trajectory logs, terminal index, tool policy, background subagents state
- 7 tracked files with history of agent interactions
- **Plan status**: ❌ NOT MENTIONED

### M11: `tests/contract_verification/` directory has no `__init__.py`
- Directory exists with conftest + verification tests
- Missing `__init__.py` is fine for pytest convention, but inconsistent with other dirs
- Plan Phase 3d mentions deleting `docs/superpowers/` but not this
- **Plan status**: ❌ Not directly relevant to the plan, but missing `__init__.py` if it's meant to be a package

---

## 🟢 LOW — Naming, Style, Minor Cleanup Items

### L1: Root-level root cruft the plan MISSES
| File | Size | Reason |
|------|------|--------|
| `main.py` | 4 lines | Stub file, not a real entrypoint |
| `tests/buggy_code.py` | 872B | Intentionally bad code test fixture |
| `.llxprt/` | ~8KB | LLM review artifacts |
| `.vtcode/` | ~12KB | IDE agent history/state |
| `.gemini/settings.json` | 149B | Tool-specific MCP config |

### L2: `nexusagent.service` points to wrong entrypoint
- References `main.py` (stub) instead of `nexusagent.server` or `nexusagent.cli`
- **Plan status**: ❌ NOT MENTIONED

### L3: `SESSION_STATE.md` and `BACKLOG.md` in root
- `SESSION_STATE.md` (55 lines) — documented state tracking
- `BACKLOG.md` (28 lines) — task backlog
- These are active working files, not archive files
- **Plan status**: ⚠️ `SESSION_STATE.md` is indirectly superseded by `docs/STATE.md` per plan Phase 1

### L4: `config/nexusagent.yaml` committed
- Configuration file with defaults
- Not necessarily bad, but committed config can drift from actual runtime config
- **Plan status**: ❌ NOT MENTIONED

### L5: `test_new_tools.py` has a TODO comment
- Line 32: `"    # TODO: validate input\\n"` — This is a test data string containing a TODO
- **Plan status**: ❌ NOT MENTIONED — intentional test data

### L6: Multiple `__pycache__` directories for source (excluding venv/worktree)
- `./__pycache__/` (root level — suggests someone ran python from root)
- `./src/__pycache__/`
- `./src/nexusagent/__pycache__/`
- `./src/nexusagent/hooks/__pycache__/`
- `./src/nexusagent/tools/__pycache__/`
- `./src/nexusagent/widgets/__pycache__/`
- `./tests/__pycache__/`
- `./tests/contract_verification/__pycache__/`
- `./tests/tools/__pycache__/`
- **Plan status**: Partially covered by `__pycache__/` in `.gitignore`

### L7: `src/nexusagent.egg-info/` directory in tree
- This is a build artifact from `pip install -e .` or similar
- Should be in `.gitignore`
- **Plan status**: ❌ NOT MENTIONED

### L8: Orphan modules — lower-confidence dead code
- `graph.py` (250L): Imported lazily by `worker.py` and `graph.py` itself — technically used but the `create_research_graph()` function may need review
- `subagent.py` (103L): Used by `worker.py` — active, not dead
- `compaction.py` (233L): Used by `memory.py` — active, not dead

---

## 📋 FULL LIST: Every File the Plan Misses

### Files NOT mentioned anywhere in the plan:

| # | File/Dir | Category | Severity |
|---|----------|----------|----------|
| 1 | `.env` (with real API keys) | Secret in git | 🔴 CRITICAL |
| 2 | `tests/buggy_code.py` | Test fixture / security | 🔴 CRITICAL |
| 3 | `.mypy_cache/3.14/*.db` (16 files) | Build artifact | 🟠 HIGH |
| 4 | `.vtcode/` (7 files) | IDE agent history | 🟠 HIGH |
| 5 | `.llxprt/` (5+ files) | Review tool artifacts | 🟠 HIGH |
| 6 | `.gemini/settings.json` | Tool config | 🟠 HIGH |
| 7 | `main.py` | Stub entrypoint | 🟠 HIGH |
| 8 | `nexusagent.service` | Wrong entrypoint | 🔴 CRITICAL |
| 9 | `vtcode.toml` | Full agent config | 🟠 HIGH |
| 10 | `.remember/logs/*.log` (3 files) | Runtime logs | 🟡 MEDIUM |
| 11 | `src/nexusagent.egg-info/` | Build artifact | 🟡 MEDIUM |
| 12 | `config/nexusagent.yaml` | Committed config | 🟢 LOW |
| 13 | `orchestration.py` line 99 TODO stub | Incomplete code | 🟡 MEDIUM |
| 14 | `tests/test_graph_nodes.py` sys.path hack | Hardcoded path | 🟡 MEDIUM |
| 15 | `src/nexusagent/templates/academic.md` | Prompt template (review) | 🟢 LOW |
| 16 | `src/nexusagent/templates/basic.md` | Prompt template (review) | 🟢 LOW |
| 17 | `src/nexusagent/templates/professional.md` | Prompt template (review) | 🟢 LOW |

### Missing .gitignore entries:
| Pattern | Files affected |
|---------|---------------|
| `.mypy_cache/` | 16 SQLite cache files |
| `.vtcode/` | 7 files (session memory, logs, state) |
| `.llxprt/` | Review tool artifacts |
| `.gemini/` | MCP server config |
| `*.db` / `*.db-shm` / `*.db-wal` | Database files |
| `*.log` | Runtime logs |
| `src/nexusagent.egg-info/` | Build artifact |
| `tests/buggy_code.py` | (Or delete it instead) |

### Plan inaccuracies:
| Plan claim | Reality |
|-----------|---------|
| "98 source files" | Actually 51 files under `src/` (45 in nexusagent + tools + widgets + hooks) |
| "13 plans files in docs/plans/" in Phase 3c | Only ~5 files listed in Phase 3c; actual count may differ |
| "rapidforge-emmc-luks-passphrase.txt" — listed for deletion | File DOES NOT EXIST (already deleted) |
| "rapidforge-emmc-luks-passphrase.txt" — listed as security risk | Was never committed to git (no git history) |
| `.env` in `.gitignore` | `.env` IS in `.gitignore` but already tracked — needs `git rm --cached .env` + history purge |
| Phase 4: "All worktree branches are already merged to master" | Branches exist but need local checkout of `master` to verify merge status |
| `web_ui.py` listed as "never imported" by dead code analysis | Actually imported by `tests/contract_verification/verify_web_ui.py` |

---

## Summary

**The cleanup plan is solid for root-level cruft and documentation consolidation but has significant blind spots:**

1. **🔴 CRITICAL**: The `.env` file with real API keys is tracked in git history. The plan never mentions this. Even though `.gitignore` lists `.env`, the file is already committed. It needs `git rm --cached .env` and history rewriting.

2. **🔴 CRITICAL**: `main.py` is a stub but `nexusagent.service` (systemd unit) references it as the production entrypoint. Nobody would notice until deployment fails.

3. **🟠 HIGH**: `.mypy_cache/`, `.vtcode/`, `.llxprt/`, `.gemini/` directories are committed and untracked — the plan never mentions any of them. These total ~20-30KB of unnecessary data.

4. **🟠 HIGH**: `tests/buggy_code.py` contains a hardcoded API key pattern and terrible code — it's either a useful test fixture that should be moved/kept intentionally, or dead code that should go.

5. **🟡 MEDIUM**: `orchestration.py` has a TODO stub in production-critical code path (`fetch_url` method). `test_graph_nodes.py` has a hardcoded absolute path.

6. **🟡 MEDIUM**: Multiple missing `.gitignore` patterns for `.mypy_cache/`, `.vtcode/`, `.llxprt/`, `.gemini/`, `*.db`, `*.log`.

7. **🟢 LOW**: Prompt templates in `src/nexusagent/templates/` are tracked but may be intentional.
