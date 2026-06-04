# Agent B TODO: Testing, Tooling & UI Prep

This set of tasks focuses on the verification, testing, and front-end integration. Agent B is the "Verifier/Frontend Engineer".

## 📖 Essential Technical Context (Read First)
Before starting, you must understand the recent architectural shift to avoid "fixing" code that was intentionally changed:

### 1. Messaging Evolution (Core NATS $\rightarrow$ JetStream KV)
- **OLD**: We used ephemeral subscriptions to wait for results (`tasks.results.{task_id}`).
- **NEW**: We now use **NATS JetStream Key-Value (KV) Store**.
- **Impact**: The SDK no longer "subscribes" to a result. It performs a `kv.get(task_id)` lookup. Any tests that expect a `nats.subscribe` call for results must be updated.

### 2. Bus Refactor (`AgentBus` $\rightarrow$ `NATSBus`)
- **Change**: The `AgentBus` class was renamed to `NATSBus` and upgraded to handle JetStream contexts.
- **Impact**: Update any imports or references in the `tests/` directory that still point to `AgentBus`.

### 3. Model Expansion
- **Models**: `TaskSchema` and `ResultSchema` in `src/nexusagent/models.py` have been expanded with `TaskStatus` (Enum), `created_at`, `updated_at`, and `duration`.
- **Impact**: UI components and tests must account for these new fields.

### 4. Environment Execution
- **Critical**: The project uses `uv`. All tests and tools must be run using `uv run <command>` to ensure the correct virtual environment and dependencies are used.

---

## 🎯 Goals
- Ensure the codebase is functionally verified through a complete test suite.
- Prepare the UI layers for the la lmost final implementation.
- Validate that all Agent A's changes are functionally sound.

## 🛠️ Tasks

### 1. Test Suite Restoration
- [ ] **Fix Environment Issues**: Resolve `ModuleNotFoundError` when running `pytest`. Ensure `PYTHONPATH` includes `src` and dependencies are loaded via `uv`.
- [ ] **Update Test Logic**: 
    - Refactor `tests/test_bus.py` to use `NATSBus` and KV lookups instead of the old subject-based logic.
    - Update `tests/contract_verification/` to reflect the updated SDK method signatures.
- [ ] **Full Suite Pass**: Ensure all 11+ tests pass using `uv run pytest`.

### 2. UI Layer Pre-flight
- [ ] **Interface Alignment**: Verify that `src/nexusagent/tui.py` and `src/nexusagent/web_ui.py` correctly call the updated `NexusSDK` methods.
- [ ] **Mocking for UI**: Create a simple "Mock SDK" in `tests/mocks.py` (or similar) to allow UI development and testing without a live NATS server.
- [ ] **Consistency Check**: Ensure the Web UI and TUI use consistent terminology and data structures as defined in `models.py`.

### 3. Final Verification
- [ ] **Run /verify full**: After Agent A completes the hardening, execute the full verification suite.
- [ ] **Sign-off**: Provide the final verification report stating that the codebase is ready for PR.

## 📁 Files Touched
- `tests/` (All files in the directory)
- `tests/contract_verification/`
- `src/nexusagent/tui.py`
- `src/nexusagent/web_ui.py`

---
**CONFLICT AVOIDANCE**: Agent B will NOT touch the core engine logic in `db.py`, `bus.py`, `auth.py`, or `config.py`. They will only consume the SDK and interact with the server.
