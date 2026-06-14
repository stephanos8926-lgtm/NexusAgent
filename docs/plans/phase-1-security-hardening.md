# Phase 1: Security Hardening — Implementation Plan

> **Created:** 2026-07-19
> **Scope:** 8 critical/high security fixes from audit findings
> **Target:** Zero regressions, all tests pass (529 baseline)
> **Pre-requisite:** Forward + Reverse audit of this plan before implementation

---

## Issue Registry (from audits)

| # | Audit | ID | File | Issue | Severity | Effort |
|---|-------|----|------|-------|----------|--------|
| 1 | Adversarial | CRITICAL-01 | `test_runner.py:149` | `shell=True` with user input | Critical | S |
| 2 | Forward | CRITICAL | `server.py` / `sdk.py` | SDK NATS path has no auth | Critical | M |
| 3 | Forward | CRITICAL | `web_ui.py` | Web UI (Gradio on 0.0.0.0:7860) zero auth | Critical | S |
| 4 | Reverse | CRITICAL | `server.py` | Orphaned tasks (DB insert succeeds, NATS fails) | Critical | M |
| 5 | Reverse | CRITICAL | `server.py` | `retry_task` loses original description | Critical | S |
| 6 | Compliance | B039 | `policy.py:17` | Mutable ContextVar default | High | S |
| 7 | Compliance | RUF012 | `chat_input.py:93` | Mutable class attribute default | High | S |
| 8 | Adversarial | HIGH-02 | `server.py:274` | API key in WebSocket query param | High | S |
| 9 | Adversarial | HIGH-03 | `shell.py` | `run_shell()` no workspace path jail | High | M |
| 10 | Forward | HIGH | `session.py` | TOCTOU race in SessionManager | High | M |
| 11 | Forward | HIGH | `cli.py` | No path jail on CLI `working_dir` | High | S |
| 12 | Forward | HIGH | `server.py` | WebSocket messages crash on KeyError | High | S |
| 13 | Reverse | HIGH | `server.py` | Cancel sets DB to FAILED, says "cancelled" | High | S |
| 14 | Forward | HIGH | `server.py` | Add rate limiting to API endpoints | High | M |

---

## Detailed Task Breakdown

### Task 1: Fix `test_runner.py` shell injection
**File:** `src/nexusagent/tools/test_runner.py:149`
**Current:** `cmd += f" {test_path}"` → `subprocess.run(cmd, shell=True, ...)`
**Fix:** Use list args, `shell=False`, validate `test_path` against allowlist pattern

```python
# Before (vulnerable)
cmd = "pytest -v --tb=short -q"
cmd += f" {test_path}"
subprocess.run(cmd, shell=True, ...)

# After (safe)
cmd = ["pytest", "-v", "--tb=short", "-q", test_path]
subprocess.run(cmd, shell=False, ...)
```

**Validation:** `test_path` must match `^[a-zA-Z0-9/._-]+$` or be empty

---

### Task 2: Add auth to SDK NATS path
**Files:** `src/nexusagent/server/sdk.py`, `src/nexusagent/infrastructure/bus.py`
**Current:** `sdk.submit_task()` publishes directly to NATS without auth
**Fix:** 
1. Add `api_key` parameter to `submit_task()`
2. Include auth in NATS message headers
3. Server validates auth before processing

---

### Task 3: Add auth to Web UI (Gradio)
**File:** `src/nexusagent/interfaces/web_ui.py`
**Current:** Gradio runs on `0.0.0.0:7860` with zero authentication
**Fix:** 
1. Add auth middleware (simple token-based or integrate with existing auth)
2. Or bind to localhost only (`127.0.0.1:7860`) with reverse proxy for external access
3. Add config option `web_ui.auth_enabled` / `web_ui.bind_host`

---

### Task 4: Fix orphaned tasks (DB/NATS atomicity)
**File:** `src/nexusagent/server/server.py` (`POST /tasks`)
**Current:** DB insert → NATS publish (if NATS fails, task orphaned)
**Fix:** 
1. Use transactional outbox pattern: write to DB with `status="pending_nats"`
2. Separate process publishes to NATS and updates to `status="pending"`
3. Or: make NATS publish part of same transaction (if using NATS JetStream KV)
4. Add retry logic for NATS publish failures

---

### Task 5: Fix `retry_task` description loss
**File:** `src/nexusagent/server/server.py` (`POST /tasks/{id}/retry`)
**Current:** Hardcoded `"description": "retried"`
**Fix:** Fetch original task from DB, preserve original description

---

### Task 6: Fix B039 mutable ContextVar default
**File:** `src/nexusagent/tools/registry/policy.py:17`
**Current:** `policy_context: ContextVar[dict] = ContextVar("policy_context", default={})`
**Fix:** Use factory function to create new dict per context

```python
# Before (buggy - shared mutable default)
_policy_context: ContextVar[dict] = ContextVar("policy_context", default={})

# After (correct - new dict each time)
def _default_policy_context() -> dict:
    return {}
_policy_context: ContextVar[dict] = ContextVar("policy_context", default_factory=_default_policy_context)
```

---

### Task 7: Fix RUF012 mutable class attribute
**File:** `src/nexusagent/widgets/chat_input.py:93`
**Current:** Mutable default for class attribute
**Fix:** Use `field(default_factory=list)` or initialize in `__init__`

---

### Task 8: Fix API key in WebSocket query param
**File:** `src/nexusagent/server/server.py:274`
**Current:** WebSocket reads API key from query param `?api_key=xxx`
**Fix:** 
1. Require `Authorization: Bearer <token>` header
2. Reject query param auth (or support both but prefer header)
3. Update TUI client to send header (already does via `extra_headers`)

---

### Task 9: Add path jail to `run_shell()`
**File:** `src/nexusagent/tools/shell.py`
**Current:** `run_shell()` has no workspace jail (unlike `fs.py`)
**Fix:** Apply same `_WORKSPACE_ROOT` validation pattern from `fs.py`

---

### Task 10: Fix TOCTOU race in SessionManager
**File:** `src/nexusagent/core/session.py`
**Current:** Check-then-act pattern with global lock contention
**Fix:** Use atomic operations, finer-grained locks, or asyncio.Lock per-session

---

### Task 11: Add path jail to CLI `working_dir`
**File:** `src/nexusagent/interfaces/cli.py`
**Current:** `working_dir` default `"."` no validation
**Fix:** Validate against workspace root, resolve and check containment

---

### Task 12: Fix WebSocket KeyError crashes
**File:** `src/nexusagent/server/server.py` WebSocket handler
**Current:** Missing field access crashes connection
**Fix:** Use `.get()` with defaults, validate message schema before processing

---

### Task 13: Fix cancel status inconsistency
**File:** `src/nexusagent/server/server.py` (`POST /tasks/{id}/cancel`)
**Current:** Sets DB to `FAILED`, returns `"cancelled"` to client
**Fix:** Use proper `CANCELLED` status in DB, return consistent status

---

### Task 14: Add rate limiting to API endpoints
**Files:** `src/nexusagent/server/server.py`, new `src/nexusagent/infrastructure/rate_limit.py`
**Current:** No rate limiting
**Fix:** 
1. Add token bucket or sliding window rate limiter
2. Apply to `/tasks`, `/tasks/{id}/result`, WebSocket connections
3. Configurable limits per endpoint

---

## Test Strategy

| Task | Test Approach |
|------|---------------|
| 1 | Unit test: inject malicious `test_path`, verify rejection |
| 2 | Integration test: submit via SDK without auth → 401 |
| 3 | Integration test: access Web UI without auth → 401/redirect |
| 4 | Unit test: mock NATS failure, verify task status = `pending_nats` |
| 5 | Unit test: retry task, verify description preserved |
| 6 | Unit test: concurrent policy contexts don't share state |
| 7 | Unit test: multiple ChatInput instances don't share state |
| 8 | Integration test: WebSocket with query param → 401; with header → 200 |
| 9 | Unit test: shell command outside workspace → rejected |
| 10 | Stress test: concurrent session creation, verify no corruption |
| 11 | Unit test: CLI with `working_dir` outside workspace → error |
| 12 | Unit test: malformed WebSocket messages → graceful error |
| 13 | Unit test: cancel task → DB status = CANCELLED |
| 14 | Load test: exceed rate limit → 429 responses |

---

## Implementation Order (Dependencies)

1. **Tasks 6, 7** — Pure code fixes, no dependencies (do first, verify tests pass)
2. **Tasks 1, 9, 11** — Tool-level fixes, isolated (can parallelize)
3. **Tasks 8, 12, 13** — Server/WebSocket fixes (require server restart)
4. **Tasks 2, 3, 4, 5, 14** — Cross-cutting auth/NATS/rate-limit (most complex)

---

## Rollback Plan

Each task = 1 commit. If any task breaks tests:
```bash
git revert <commit-hash>
```
Baseline: 529 pass / 14 fail / 1 error (all pre-existing). Zero new failures allowed.

---

## Forward Audit of This Plan (Required Before Implementation)

> **STOP** — This plan must pass forward audit before any code changes.

**Forward Audit Questions:**
1. Does any fix introduce new attack surface?
2. Does auth on SDK break existing CLI/TUI flows?
3. Does Web UI auth break local development workflow?
4. Does orphaned task fix add latency to task submission?
5. Does rate limiting affect legitimate high-throughput use?
6. Are all error messages still informative (no info leakage)?
7. Do path jails break legitimate cross-workspace operations?

**Reverse Audit Questions:**
1. Can we trace every auth decision back to a policy?
2. Are all error paths covered by tests?
3. Is there any path where a task can be lost silently?
4. Can a malicious user bypass any of the new validations?

---

*Plan saved to `docs/plans/phase-1-security-hardening.md`*
*Next: Forward + Reverse audit of this plan, then implementation*