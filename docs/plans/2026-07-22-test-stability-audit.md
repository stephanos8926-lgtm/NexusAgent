# 7-Audit Stability Report & Implementation Plan

This document contains the step-by-step plan, the 7 audits, and the micro-steps for implementation to resolve the unit test failures in the NexusAgent codebase.

## Approved Plan

1. **Fix CLI memory health duplicate detection test in `tests/test_cli_memory.py`**:
   - Use `os.utime` to set the mtime of `orig.md` to be older than `copy.md` to guarantee stable deduplication order.
2. **Fix API Server Operator Key read authorization unit test in `tests/test_server.py`**:
   - Patch `nexusagent.server.routes.sdk` with `unittest.mock.AsyncMock` to isolate authorization check testing from the NATS message bus.
3. **Run the targeted and full test suite to verify the fixes**:
   - Run pytest and confirm 100% test success with no regressions.
4. **Complete pre-commit steps**:
   - Run Ruff formatting and other required checks.
5. **Submit the change**:
   - Branch, commit, and submit the changes.

---

## 7-Audit Comprehensive Analysis

### 1. Forward Audit
- **Path**: Test Execution → File/API Boundary → Assertion.
- **Deduplication Test**: Writes two identical content files. Click runner runs the command, and `DreamCycle` scans them, sorting by modification time (`st_mtime`). Lacking explicit times, filesystem clock resolution occasionally causes the files to sort out of expected order, failing the assertion. Explicitly calling `os.utime` ensures deterministic ordering.
- **Auth Read Test**: Requests `GET /tasks/{id}/result` and `GET /tasks/{id}/status`. Handlers invoke `sdk.get_result` and `sdk.get_task_status`, initiating NATS connectivity which fails due to the lack of a live NATS broker in unit test runs. Mocking the SDK methods with `AsyncMock` resolves this entirely.

### 2. Reverse Audit
- **Path**: Failed Assertion/Exception → System/Test Design.
- **Deduplication Test**: The deduplication logic itself is correct and behaves as designed (oldest file is kept as original). The test's setup is too optimistic about filesystem clocks. Forcing the files' mtime solves this without altering the underlying code.
- **Auth Read Test**: The endpoint code correctly delegates work to the SDK. The unit test incorrectly executes real broker network routines instead of testing the HTTP authorization layer in isolation. Mocking the NATS calls preserves the separation of concerns.

### 3. Adversarial Audit
- **Deduplication Test**: Could multiple files still resolve to identical mtime? No, because a 10-second offset is set using `os.utime`, which far exceeds standard filesystem tick resolutions.
- **Auth Read Test**: What if other endpoints in the same test block call NATS? We mock both `get_task_status` and `get_result` which are the only NATS-connecting SDK endpoints called under the Operator Read-Only suite.

### 4. Red-team Audit
- **Security Check**: Mocking the NATS connection does not bypass the authorization layer (FastAPI dependency injection `verify_api_key`). The dependency injection completes successfully, verifying the operator key before reaching the mocked route handler body. This ensures security logic is fully tested.
- **Environment Check**: No file-system traversal risks. Temp directory paths are scoped.

### 5. Top-down Audit
- Maintains fast, offline, and hermetic developer environment tests, which is a core architectural requirement for continuous integration (CI).

### 6. Bottom-up Audit
- Uses Python standard library primitives: `os.utime` for file manipulation and `unittest.mock.AsyncMock` for coroutine mocking. These have no external dependencies or compatibility issues.

### 7. Completeness Audit
- Covers both failing tests. No other failures are active in the core suite.

---

## Micro-step Implementation Plan

### Step 1: Fix `tests/test_cli_memory.py`
1. Read `tests/test_cli_memory.py` to target `test_health_shows_duplicates`.
2. Apply `os.utime` on `orig.md` with an epoch offset 10 seconds prior to current time.
3. Apply `os.utime` on `copy.md` with current time.
4. Verify using `git diff`.

### Step 2: Fix `tests/test_server.py`
1. Read `tests/test_server.py` to target `test_operator_key_allowed_on_read_endpoints`.
2. Import `patch` and `AsyncMock` from `unittest.mock`.
3. Wrap the test client calls with `with patch("nexusagent.server.routes.sdk") as mock_sdk:`.
4. Define `mock_sdk.get_task_status` and `mock_sdk.get_result` as `AsyncMock` returning mock values.
5. Verify using `git diff`.

### Step 3: Local Test Execution
1. Run `PYTHONPATH=src:. pytest tests/test_cli_memory.py -k test_health_shows_duplicates`
2. Run `PYTHONPATH=src:. pytest tests/test_server.py -k test_operator_key_allowed_on_read_endpoints`
3. Run the full core test suite.
