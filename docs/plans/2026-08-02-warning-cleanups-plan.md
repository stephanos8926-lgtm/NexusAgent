# Audited Plan: Warning Cleanups & Python 3.16 Future-Proofing

## 1. Context & Motivation
During the execution of the 1053+ test suite for NexusAgent, two prominent categories of warnings were identified:
1. `RuntimeWarning: coroutine 'HybridMemoryManager.close' was never awaited` from `tests/test_memory_e2e.py:69`. This occurs because `HybridMemoryManager.close()` was refactored in Phase 9 to be an asynchronous method, but the legacy test still calls it synchronously.
2. `DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead`. This is raised across several files in the codebase where decorators and callbacks are checked for coroutine function status.

Addressing these warnings improves the project's hygiene, eliminates resource leaks (unawaited coroutines can keep database connections or file locks open), and future-proofs NexusAgent against Python 3.16 removals.

---

## 2. Seven-Dimension Completeness Audit

### 2.1 Forward Audit
- **Direct Alignment:** The proposed solution targets exactly the locations raising these warnings.
- **Python Compatibility:** `inspect.iscoroutinefunction` is the modern standard and fully supported in Python 3.12, 3.13, 3.14, and beyond.
- **Dependencies:** Standard library `inspect` module is built-in; no external packages needed.

### 2.2 Reverse Audit
- **Alias Equivalence:** Under Python 3.12+, `asyncio.iscoroutinefunction` is an alias to `inspect.iscoroutinefunction`. Replacing it does not change logic or fail to identify any valid coroutine functions.
- **Awaiting `close`:** `HybridMemoryManager.close()` is verified async. Awaiting it correctly executes the cleanup and resolves the `RuntimeWarning`.

### 2.3 Adversarial Audit
- **Isolation:** The changes have no impact on network-isolated environments or active NATS connections.
- **Edge Cases:** Decorated functions wrapped with `functools.wraps` are resolved correctly by `inspect.iscoroutinefunction`.

### 2.4 Red-Team Audit
- **Security Impact:** No security parameters, access control checks, or data boundaries are modified. No elevation or privilege bypass risks are introduced.

### 2.5 Top-Down Audit
- **Architecture Fit:** Ensures correct cleanup of system resources (database handles, files) on memory shutdown. Keeps logs clean and diagnostic outputs reliable.

### 2.6 Bottom-Up Audit
- **Imports:** Adds clean imports of the standard `inspect` module in each targeted module.
- **Precision:** Edits only the relevant line structures without introducing side effects.

### 2.7 Completeness Audit
- **Scope:** Covers all occurrences of `asyncio.iscoroutinefunction` inside the source tree. Ensures the `test_memory_e2e.py` warning is completely resolved.

---

## 3. Architecture Decision Record (ADR-0024)

### Title: Deprecating `asyncio.iscoroutinefunction` in favor of `inspect.iscoroutinefunction`

### Status
Accepted

### Context
In Python 3.12+, `asyncio.iscoroutinefunction` was deprecated and slated for complete removal in Python 3.16. The warning is explicitly raised in modern Python runtimes (such as Python 3.14 used in this sandbox environment).

### Decision
We will transition all checks for coroutine function status from `asyncio.iscoroutinefunction` to the standard library's `inspect.iscoroutinefunction`.

### Consequences
- Eliminates `DeprecationWarning` logs during test and production execution.
- Retains absolute compatibility with all existing sync and async decoration layers.
- Avoids code breakage when migrating to future Python runtimes (>= 3.16).

---

## 4. Micro-Step Implementation Plan

### Step 1: Fix E2E Memory Test
- Target file: `tests/test_memory_e2e.py`
- Change: In `test_session_close_cleans_up_hybrid_memory`, replace `session.hybrid_memory.close()` with `await session.hybrid_memory.close()`.

### Step 2: Fix Retry Utility
- Target file: `src/nexusagent/infrastructure/utils/retry.py`
- Change: Import `inspect` and replace both instances of `asyncio.iscoroutinefunction` with `inspect.iscoroutinefunction`.

### Step 3: Fix Tool Registry
- Target file: `src/nexusagent/tools/registry/core.py`
- Change: Import `inspect` and replace `asyncio.iscoroutinefunction` with `inspect.iscoroutinefunction`.

### Step 4: Fix POL Control Plane
- Target file: `src/nexusagent/core/pol.py`
- Change: Import `inspect` and replace `asyncio.iscoroutinefunction` with `inspect.iscoroutinefunction`.

### Step 5: Verification
- Execute: `PYTHONPATH=src:. python3 -m pytest tests/ -q --ignore=tests/api_e2e_project --ignore=tests/test_e2e_production.py --ignore=tests/test_graph_nodes.py --ignore=tests/test_bus.py`
- Verify that E2E memory and deprecation warnings are completely resolved.
