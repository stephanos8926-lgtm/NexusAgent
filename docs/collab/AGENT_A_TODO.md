# Agent A TODO: Core Engine Hardening (State-Complete)

**Context**: This document serves as the primary state-restore point for Agent A. We are in **Phase 3 (Implementation)** of the production-grade refactor for NexusAgent. The foundation (Config, Auth, DB, NATS KV) is functionally complete but requires strict type-hardening and linting to reach "PR-Ready" status.

## 🛠️ Technical Stack Reference
- **Backend**: FastAPI + NATS Worker (co-located).
- **Messaging**: NATS Core (Requests) + NATS JetStream KV (Results). 
    - Result Bucket: `nexus_results`.
- **State**: SQLAlchemy + aiosqlite.
- **Config**: Pydantic Settings (YAML + Env overrides).
- **Auth**: PBKDF2HMAC $\rightarrow$ AES-GCM. Salt stored in `.master.salt`.
- **Tooling**: `uv` (Package Mgr), `mypy` (Typing), `ruff` (Linting), `pytest` (Tests).

## 🎯 Goals
- Zero Mypy type errors.
- Zero Ruff linting errors (specifically E501 line length and I001 import order).
- Verified functional integrity of the Core Engine.

## 📋 Task List (Ordered by Priority)

### 1. Critical Type System Restoration (The Mypy Sweep)
- [ ] **SQLAlchemy Base Fix**: Fix `Invalid base class "Base"` errors in `src/nexusagent/db.py`. Use `class Base(DeclarativeBase): pass` from `sqlalchemy.orm`.
- [ ] **Missing Annotations**: Add return type annotations (`-> None`, `-> Optional[str]`, etc.) to ALL functions in:
    - `src/nexusagent/config.py`
    - `src/nexusagent/auth.py`
    - `src/nexusagent/sdk.py`
    - `src/nexusagent/server.py`
    - `src/nexusagent/bus.py`
- [ ] **Variable Typing**: Resolve `var-annotated` errors:
    - `raw_data` in `config.py`.
    - `tree` in `tools/fs.py`.
- [ ] **Correct Coroutines**: Fix `attr-defined` errors in `db.py` where `async with` is called on a coroutine instead of an awaited session.

### 2. Linting & Logic Polish (The Ruff Sweep)
- [ ] **Import Hygiene**:
    - Remove all unused imports (`asyncio`, `Path`, `settings`, `Symmetry`).
    - Run `ruff check --select I --fix` to organize imports.
- [ ] **Style Compliance**:
    - Fix E501 (Line too long > 88 chars) in `auth.py`, `config.py`, and `db.py` by breaking strings and signatures.
- [ ] **Dead Code**: 
    - Remove unused `agent` variable in `src/nexusagent/agent.py`.
    - Remove redundant `sdk` assignment in `web_ui.py` (if touched).

### 3. Security & Stability Final Check
- [ ] **Error Handling**: Ensure no bare `except:` remains in `worker.py` or `server.py`.
- [ ] **Path Resolution**: Verify all `Path` operations in `auth.py` and `config.py` use `get_project_root()` consistently.

## 📁 File Ownership
Agent A exclusively owns and modifies:
- `src/nexusagent/db.py`
- `src/nexusagent/config.py`
- `src/nexusagent/auth.py`
- `src/nexusagent/sdk.py`
- `src/nexusagent/server.py`
- `src/nexusagent/bus.py`
- `src/nexusagent/agent.py`
- `src/nexusagent/tools/fs.py`

## ✅ Success Criteria
1. `uv run mypy src/nexusagent --ignore-missing-imports` $\rightarrow$ **Success (0 errors)**.
2. `uv run ruff check src/nexusagent` $\rightarrow$ **Success (0 issues)**.
3. No critical logic regressions in core backend.

---
**CONFLICT AVOIDANCE**: Do NOT modify `tests/`, `tui.py`, or `web_ui.py`. Coordination with Agent B happens via the SDK interface.
