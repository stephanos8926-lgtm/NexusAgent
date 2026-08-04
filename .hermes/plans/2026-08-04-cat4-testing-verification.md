# Category 4: Testing & Verification — Implementation Plan

## Goal
Stabilize the test suite, close verification gaps, and ensure every claimed fix is backed by runnable evidence before completion.

## Current Context
- Full `pytest tests/` runs show 226 passed, 9 skipped
- One flaky/dependent failure: `test_dream_cycle_four_phases_e2e` fails in full suite but passes in isolation
- Code review surfaced missing verification evidence patterns in commit workflow
- Some high-severity findings remain without regression coverage

## Proposed Approach
Stabilize verification in 3 waves:
1. **Wave 1 — Flaky Test Fix**: isolate and fix event-loop teardown pollution causing suite-order failure
2. **Wave 2 — Regression Coverage**: add targeted tests for security/auth/logging fixes
3. **Wave 3 — Verification Gates**: enforce pre-completion verification in workflow/tests

## Step-by-Step Plan

### Wave 1: Flaky Test Fix
- [ ] **W1.1** `tests/memory/test_dream_cycle.py`
  - Isolate `test_dream_cycle_four_phases_e2e` dependencies
  - Add explicit async cleanup or event-loop fixture boundaries
- [ ] **W1.2** Test infrastructure
  - Verify no shared mutable state across memory/dream tests
  - Add isolation fixtures if needed

### Wave 2: Regression Coverage
- [ ] **W2.1** Add auth regression tests
  - Unauthenticated `delete_task` must fail
  - Unauthenticated `delete_by_file` must fail
- [ ] **W2.2** Add injection regression tests
  - Malicious task input must not alter worker query behavior
  - Malicious entity input must not alter refinement prompt execution
- [ ] **W2.3** Add logging hygiene regression tests
  - Assert no LLM/user secrets appear in captured log output for critical paths
- [ ] **W2.4** Add loop-backstop tests
  - Cancellation/timeout causes graceful exit in worker + websocket paths

### Wave 3: Verification Gates
- [ ] **W3.1** Enforce verification evidence requirement in commit workflow
  - Update commit message template/checklist to require test output
- [ ] **W3.2** Add CI-style verification script
  - Run targeted pytest + ruff + rw_codegate on changed files
  - Output structured pass/fail evidence
- [ ] **W3.3** Add pre-completion checklist automation
  - Block completion claims without fresh verification evidence

## Files Likely to Change
- `tests/memory/test_dream_cycle.py`
- `tests/` additions for security/auth/logging/loop regression coverage
- `.github/workflows/*` or local verification scripts as needed
- Commit/tooling config if present

## Tests / Validation
- Run targeted pytest for dream cycle and new regression tests
- Run `ruff check src/ tests/`
- Run `rw_codegate` on changed files
- Verify full-suite stability after flaky fix

## Risks, Tradeoffs, and Open Questions
- **Risk**: Adding async cleanup fixtures may change test timing.
  - *Mitigation*: Keep timeouts conservative and assert behavior, not exact timing.
- **Risk**: Regression tests for logging may be brittle across environments.
  - *Mitigation*: Use captured log fixtures with explicit assertions on sensitive substrings.
- **Open Question**: Do we want verification automation enforced at pre-commit, CI, or both?
