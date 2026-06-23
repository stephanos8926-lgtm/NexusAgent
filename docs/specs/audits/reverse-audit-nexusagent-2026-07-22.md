# Reverse Audit — NexusAgent 2026-07-22

**Auditor:** OWL (plan-and-audit high mode)
**Scope:** Find everything current plans/specs MISS

---

## 🔴 Critical

### 1. 6 Critical Issues from 2026-06-16 UNFIXED
All 6 critical findings from comprehensive code review remain open:
- `refine_node` silent approval
- API key in URL query param
- Sync SQLite in async event loop
- SessionManager spin loop no timeout
- sanitize_tool_output always marks untrusted
- No TLS/SSL

**Impact:** Security and correctness regressions persist. No plan addresses these.

---

### 2. Circular Import Pairs
| Pair | Files | Risk |
|------|-------|------|
| `core.agent` ↔ `tools.register_all` | Agent imports register_all; register_all imports tools that import Agent | Runtime import failures possible |
| `interfaces.tui.streaming` ↔ `interfaces.tui.websocket` | Mutual imports via app reference | Refactoring either breaks the other |

---

## 🟠 High

### 3. Module-Level Mutable State Leaks Across Sessions
| File | Variable | Leak Type |
|------|----------|-----------|
| `tools/fs_base.py:16` | `_read_files: set[str] = set()` | Read-before-write tracking |
| `infrastructure/rate_limit.py:17` | `_RATE_LIMIT_PER_CLIENT` | Unbounded growth, cleanup never implemented |
| `infrastructure/bus.py` | `_subscriptions` list | Never cleaned on unsubscribe |

**Impact:** State pollution between unrelated agent sessions.

---

### 4. No Authorization Model
Authentication exists (API key) but **zero authorization**. Every authenticated user = full access to all endpoints, sessions, tools.

---

### 5. WebSocket Security Gaps
- No `Origin` header validation (CSRF)
- Message size unbounded (64KB config not enforced)
- API key accepted in query parameter

---

### 6. MCP Tool Hijacking
`register_all.py` loads MCP tools with no validation. Rogue server can override built-ins or inject malicious descriptions.

---

### 7. SQLite Connection Leaks
- `graph.py:230-248`: `conn` not closed on `workflow.compile()` failure
- `memory/index/index.py`: New connection per operation (no pool)

---

### 8. No Foreign Key Constraints
DB models have no FK between messages↔sessions, results↔tasks. Referential integrity application-only.

---

## 🟡 Medium

### 9. 17 Never-Imported Modules (Star-Imported Only)
These modules are only reachable via `from X import *` in compat shims:
```
nexusagent.hooks.builtins
nexusagent.infrastructure.db.base
nexusagent.infrastructure.db.manager
nexusagent.infrastructure.db.models
nexusagent.infrastructure.db.session_repo
nexusagent.infrastructure.db.task_repo
nexusagent.infrastructure.telemetry
nexusagent.infrastructure.utils
nexusagent.memory.index.embeddings
nexusagent.memory.nats_bus
nexusagent.server.__main__
nexusagent.task_reaper
nexusagent.tools.registry.core
nexusagent.tools.registry.policy
nexusagent.tools.registry.search
nexusagent.tools.registry.types
nexusagent.tools.write_todos
```

**Risk:** If compat shims removed, these become dead code. Hard to analyze true usage.

---

### 10. 8 Oversized Files (>500 lines)
| File | Lines | Should Split |
|------|-------|--------------|
| `tools/register_all.py` | 1,210 | By tool category |
| `memory/dream.py` | 847 | By consolidation phase |
| `memory/index/index.py` | 716 | FTS5 vs vector search |
| `memory/memory_files.py` | 638 | Git ops, TTL sweep |
| `interfaces/cli.py` | 594 | Command groups |
| `interfaces/tui/streaming.py` | 529 | Formatters, handlers |
| `infrastructure/bus.py` | 500 | Connection vs pub/sub |
| `widgets/status.py` | 472 | Status bar components |

---

### 11. Test Collection Errors (5 test files)
Root cause: Compat shims missing exports:
- `tui/formatters.py` doesn't re-export `format_arg_value`
- `tools/fs.py` doesn't re-export `edit_file` from `tools.editor`

---

### 12. 2 Failing Tests
- `test_tui_widgets.py::test_json_args_pretty_print`
- `test_worker_workspace_scoping.py::test_setup_workspace_context_noop_for_dot`

---

### 13. Missing Type Annotations (200+ mypy errors)
- `no-untyped-def`: ~80 functions
- `no-any-return`: ~40
- `type-arg` (dict/tuple/Callable): ~50
- `assignment`: ~20

---

## 🔵 Low

### 14. .gitignore Gaps
Files in repo that should be gitignored:
- `__pycache__/` (some present)
- `*.pyc` (some present)
- `.pytest_cache/` (present)
- `data/nexus.db` (present but config expects it)
- `.nexusagent/` (session data)

---

### 15. Duplicate Functionality
| Area | Overlap |
|------|---------|
| `memory/memory.py` vs `memory/hybrid_memory.py` | Two memory systems coexist |
| `memory/memory_files.py` vs `memory/memory_bank.py` | `memory_bank.py` is dead code (0 imports) |
| `llm/models.py` + `llm/llm.py` | God object + LLM bridge |

---

### 16. Inconsistent Naming
- `Memory` class (dead) vs `HybridMemoryManager` (active) vs `FileMemory` (canonical)
- `memory_bank.py` (dead) vs `memory_files.py` (active)
- `llm/models.py` contains non-LLM models

---

### 17. Missing `__init__.py` in Package Dirs
All packages have `__init__.py` ✅

---

### 18. Secrets in Repo
**None found** in source code. Search for `api_key`, `SECRET`, `token`, `password` in `src/` returned only legitimate usage (config loading, auth verification).

---

### 19. Uncommitted Work / Worktree State
No active worktrees. `git status` clean.

---

## 📋 Full List Summary

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| Unfixed 2026-06-16 issues | 6 | 6 | - | - | - |
| Circular imports | 2 | 2 | - | - | - |
| Mutable state leaks | 3 | - | 3 | - | - |
| AuthZ missing | 1 | - | 1 | - | - |
| WebSocket security | 3 | - | 3 | - | - |
| MCP hijacking | 1 | - | 1 | - | - |
| SQLite leaks | 2 | - | 2 | - | - |
| No FK constraints | 1 | - | 1 | - | - |
| Never-imported modules | 17 | - | - | 17 | - |
| Oversized files | 8 | - | - | 8 | - |
| Test collection errors | 5 | - | - | 5 | - |
| Failing tests | 2 | - | - | 2 | - |
| Missing type annotations | 200+ | - | - | 200+ | - |
| .gitignore gaps | 5 | - | - | - | 5 |
| Duplicate functionality | 3 | - | - | - | 3 |
| Inconsistent naming | 3 | - | - | - | 3 |

**Total Findings: ~260** (mostly type annotations)

---

## Recommendations

1. **IMMEDIATE**: Fix the 6 unfixed critical issues from 2026-06-16
2. **HIGH**: Resolve circular imports, mutable state leaks, add AuthZ, fix WebSocket security
3. **MEDIUM**: Split oversized files, fix compat shim exports, add type annotations
4. **LOW**: Clean up dead code (`memory_bank.py`), deduplicate memory systems, fix naming