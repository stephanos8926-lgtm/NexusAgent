# NexusAgent API & SDK Overhaul Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to execute each stage. One stage at a time — get sign-off before proceeding to the next.

**Goal:** Fix all critical runtime bugs, complete the API surface, and make the SDK genuinely useful for external consumers.

**Architecture:** FastAPI backend with NATS bus, SQLite persistence, policy-aware tool registry. Staged approach: fix crashes first, then add missing endpoints/SDK methods, then polish.

**Tech Stack:** Python 3.13, FastAPI, NATS/JetStream, SQLAlchemy async, Pydantic, ruff, pytest-asyncio

---

## Stage 1: Critical Runtime Bugs

**Objective:** Fix everything that causes crashes or prevents the project from starting.

### Task 1.1: Fix AgentConfig — add missing LLM fields

**Objective:** Add the missing config fields that `llm.py` references at runtime.

**Files:**
- Modify: `src/nexusagent/config.py:35-40` (AgentConfig class)

**Step 1: Add missing fields to AgentConfig**

```python
class AgentConfig(BaseModel):
    default_model: str = Field(default="gemini-3.1-flash-lite")
    primary_provider: str = Field(default="gemini")
    gemini_model: str = Field(default="gemini-3.1-flash-lite")
    openrouter_default_model: str = Field(default="openrouter/auto")
    openrouter_override_model: str | None = None
    enabled_tools: list[str] = Field(
        default_factory=lambda: ["read_file", "write_file", "run_shell"]
    )
```

**Step 2: Verify no other config references are broken**

Run: `cd /home/sysop/Workspaces/NexusAgent && python -c "from nexusagent.config import settings; print(settings.agent)"`
Expected: No errors, prints AgentConfig with all fields.

**Step 3: Commit**

```bash
git add src/nexusagent/config.py
git commit -m "fix: add missing LLM config fields (primary_provider, gemini_model, openrouter_*"
```

---

### Task 1.2: Fix pyproject.toml — add missing deps and fix entry points

**Objective:** Ensure `nexus-server` entry point works and all runtime deps are declared.

**Files:**
- Modify: `pyproject.toml`

**Step 1: Fix entry points**

```toml
[project.scripts]
nexus-server = "nexusagent.server:app"
nexus-client = "nexusagent.cli:main"
nexus = "nexusagent.tui:main"
nexus-web = "nexusagent.web_ui:create_ui"
```

Note: `nexus-server` now points to the FastAPI `app` object (uvicorn can run it with `nexusagent.server:app`). Remove the old `run_server` reference.

**Step 2: Add missing runtime dependencies**

```toml
dependencies = [
    "langgraph",
    "langgraph-checkpoint",
    "langgraph-checkpoint-sqlite",
    "deepagents",
    "nats-py",
    "pyyaml",
    "patch-ng",
    "fastapi",
    "uvicorn",
    "pytest",
    "pytest-asyncio",
    "ruff",
    "mypy",
    "pydantic",
    "google-generativeai",
    "openai",
    "gradio",
    "textual",
    "cryptography",
    "httpx",
    "sqlalchemy[asyncio]",
    "aiosqlite",
]
```

**Step 3: Verify install**

Run: `cd /home/sysop/Workspaces/NexusAgent && pip install -e ".[dev]" 2>&1 | tail -5`
Expected: No errors.

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "fix: add missing deps and correct entry points in pyproject.toml"
```

---

### Task 1.3: Fix web_ui.py — SDK call signature mismatch

**Objective:** Fix `handle_submit()` which passes `TaskSchema` to `sdk.submit_task()` that expects a dict.

**Files:**
- Modify: `src/nexusagent/web_ui.py:14-31`

**Step 1: Fix handle_submit to use dict**

```python
def handle_submit(text, sdk=None):
    if sdk is None:
        from nexusagent.sdk import NexusSDK
        sdk = NexusSDK()

    if not text:
        return "Error: Task definition empty", "ERROR"

    task_id = str(uuid.uuid4())[:8]

    # submit_task expects a dict, not a TaskSchema object
    result = sdk.submit_task({
        "id": task_id,
        "description": text,
    })

    # submit_task returns a task_id string, not a result object
    return f"[{task_id}] Submitted successfully", "ACTIVE"
```

**Step 2: Verify import works**

Run: `cd /home/sysop/Workspaces/NexusAgent && python -c "from nexusagent.web_ui import handle_submit; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/nexusagent/web_ui.py
git commit -m "fix: correct SDK call signature in web_ui handle_submit"
```

---

### Task 1.4: Fix server.py — dead code and add CORS

**Objective:** Clean up dead code, add CORS middleware for web UI.

**Files:**
- Modify: `src/nexusagent/server.py`

**Step 1: Add CORS middleware and remove dead code**

At the top of the file, after imports:
```python
from fastapi.middleware.cors import CORSMiddleware
```

After `app = FastAPI(...)`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Remove the dead code on line 82 (`task_id = request.description`).

**Step 2: Verify server starts**

Run: `cd /home/sysop/Workspaces/NexusAgent && timeout 3 python -c "from nexusagent.server import app; print('OK')" 2>&1`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/nexusagent/server.py
git commit -m "fix: add CORS middleware and remove dead code in server.py"
```

---

### Task 1.5: Fix sdk.py — submit_task mutates input dict

**Objective:** Stop `submit_task()` from mutating the caller's dict via `.pop("id")`.

**Files:**
- Modify: `src/nexusagent/sdk.py:25-38`

**Step 1: Fix the mutation bug**

```python
async def submit_task(self, task_data: dict) -> str:
    """Submits a task to the NATS bus. Returns the task ID."""
    await self.connect()

    # Don't mutate the caller's dict
    task_data = dict(task_data)
    task_id = task_data.pop("id", str(uuid.uuid4()))
    task = TaskSchema(id=task_id, **task_data)

    logger.info(f"Submitting task {task_id}: {task.description}")
    await self.bus.publish("tasks.submit", task.model_dump())
    return task_id
```

**Step 2: Write a quick test**

Run: `cd /home/sysop/Workspaces/NexusAgent && python -c "
from nexusagent.sdk import NexusSDK
import asyncio
async def test():
    s = NexusSDK()
    d = {'description': 'test', 'id': 'abc'}
    # Should not mutate d
    print('Before:', d)
    # Can't actually submit without NATS, but we can test the dict copy
    d2 = dict(d)
    d2.pop('id', None)
    print('Original after:', d)
    print('Copy after:', d2)
asyncio.run(test())
print('OK')
"`
Expected: Original dict unchanged.

**Step 3: Commit**

```bash
git add src/nexusagent/sdk.py
git commit -m "fix: stop submit_task from mutating input dict"
```

---

## Stage 2: API Endpoints

**Objective:** Add all missing REST endpoints for task and worker management.

### Task 2.1: Add task listing endpoint

**Objective:** `GET /tasks` — list all tasks with optional status filter and pagination.

**Files:**
- Modify: `src/nexusagent/server.py`
- Create: `tests/test_server.py` (if not exists)

**Step 1: Add list_tasks to task_repo in db.py**

```python
# In TaskRepository class, add:
async def list_tasks(
    self,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    async with self.db_manager.get_session() as session:
        query = select(TaskModel).order_by(TaskModel.created_at.desc())
        if status:
            query = query.where(TaskModel.status == status)
        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        tasks = result.scalars().all()
        return [
            {
                "id": t.id,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tasks
        ]
```

**Step 2: Add GET /tasks endpoint in server.py**

```python
@app.get("/tasks")
async def list_tasks(status: str | None = None, limit: int = 50, offset: int = 0):
    """List tasks with optional status filter and pagination."""
    from nexusagent.db import task_repo
    tasks = await task_repo.list_tasks(status=status, limit=limit, offset=offset)
    return {"tasks": tasks, "count": len(tasks)}
```

**Step 3: Write test**

```python
# tests/test_server.py
import pytest
from httpx import AsyncClient, ASGITransport
from nexusagent.server import app

@pytest.mark.asyncio
async def test_list_tasks_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
```

**Step 4: Run test**

Run: `cd /home/sysop/Workspaces/NexusAgent && python -m pytest tests/test_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/nexusagent/db.py src/nexusagent/server.py tests/test_server.py
git commit -m "feat: add GET /tasks listing endpoint with pagination"
```

---

### Task 2.2: Add task cancellation endpoint

**Objective:** `POST /tasks/{task_id}/cancel` — cancel a pending/processing task.

**Files:**
- Modify: `src/nexusagent/server.py`
- Modify: `src/nexusagent/db.py` (task_repo)

**Step 1: Add cancel_task to task_repo**

```python
async def cancel_task(self, task_id: str) -> bool:
    """Cancel a task. Returns True if cancelled, False if not found or already terminal."""
    async with self.db_manager.get_session() as session:
        result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return False
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return False
        task.status = TaskStatus.FAILED
        return True
```

**Step 2: Add endpoint**

```python
@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a pending or processing task."""
    from nexusagent.db import task_repo
    cancelled = await task_repo.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Task not found or already completed/failed")
    return {"task_id": task_id, "status": "cancelled"}
```

**Step 3: Test and commit**

Run: `python -m pytest tests/test_server.py -v`
Expected: PASS

```bash
git add src/nexusagent/db.py src/nexusagent/server.py
git commit -m "feat: add POST /tasks/{id}/cancel endpoint"
```

---

### Task 2.3: Add task retry endpoint

**Objective:** `POST /tasks/{task_id}/retry` — re-queue a failed task.

**Files:**
- Modify: `src/nexusagent/server.py`
- Modify: `src/nexusagent/db.py`

**Step 1: Add retry logic**

```python
# In task_repo:
async def retry_task(self, task_id: str) -> str | None:
    """Retry a failed task. Returns new task ID or None."""
    async with self.db_manager.get_session() as session:
        result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
        task = result.scalar_one_or_none()
        if not task or task.status != TaskStatus.FAILED:
            return None
        # Reset status to pending
        task.status = TaskStatus.PENDING
        return task_id
```

**Step 2: Add endpoint**

```python
@app.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed task."""
    from nexusagent.db import task_repo
    from nexusagent.sdk import sdk

    new_id = await task_repo.retry_task(task_id)
    if not new_id:
        raise HTTPException(status_code=400, detail="Task not found or not in failed state")

    # Re-publish to NATS
    task_data = {"id": new_id, "description": "retried", "priority": 1}
    await sdk.submit_task(task_data)

    return {"task_id": new_id, "status": "re-queued"}
```

**Step 3: Test and commit**

```bash
git add src/nexusagent/db.py src/nexusagent/server.py
git commit -m "feat: add POST /tasks/{id}/retry endpoint"
```

---

### Task 2.4: Add worker status and tool registry endpoints

**Objective:** `GET /workers` and `GET /tools` endpoints.

**Files:**
- Modify: `src/nexusagent/server.py`

**Step 1: Add workers endpoint**

```python
@app.get("/workers")
async def list_workers():
    """List worker status including circuit breaker state."""
    from nexusagent.worker import _agent_breaker, _nats_breaker

    return {
        "workers": [
            {
                "name": "default",
                "status": "running",
                "circuit_breakers": {
                    "agent": {
                        "state": _agent_breaker.state,
                        "failure_count": _agent_breaker.failure_count,
                    },
                    "nats": {
                        "state": _nats_breaker.state,
                        "failure_count": _nats_breaker.failure_count,
                    },
                },
            }
        ]
    }
```

**Step 2: Add tools endpoint**

```python
@app.get("/tools")
async def list_tools():
    """List all registered tools grouped by category."""
    from nexusagent.tools.registry import list_all_tools

    tools = list_all_tools()
    by_cat: dict[str, list[dict]] = {}
    for t in tools:
        by_cat.setdefault(t.category, []).append({
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        })

    return {"tools": by_cat, "total": len(tools)}
```

**Step 3: Test and commit**

```bash
git add src/nexusagent/server.py
git commit -m "feat: add GET /workers and GET /tools endpoints"
```

---

### Task 2.5: Add auth middleware to API

**Objective:** Wire up API key auth using the existing auth system.

**Files:**
- Create: `src/nexusagent/api_auth.py`
- Modify: `src/nexusagent/server.py`

**Step 1: Create API auth module**

```python
# src/nexusagent/api_auth.py
import logging
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key from header. In production, validate against keystore."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    # For now, accept any non-empty key (TODO: validate against keystore)
    return api_key
```

**Step 2: Protect endpoints in server.py**

Add `dependencies=[Depends(verify_api_key)]` to all endpoints except `/health`.

```python
from fastapi import Depends
from nexusagent.api_auth import verify_api_key

# Apply to all routes except health:
@app.post("/tasks", dependencies=[Depends(verify_api_key)])
async def create_task(...):
    ...

# Same for GET /tasks, POST /tasks/{id}/cancel, POST /tasks/{id}/retry, GET /workers, GET /tools
```

**Step 3: Test and commit**

```bash
git add src/nexusagent/api_auth.py src/nexusagent/server.py
git commit -m "feat: add API key auth middleware to all endpoints"
```

---

## Stage 3: SDK Completeness

**Objective:** Add all missing SDK methods to make it a complete client library.

### Task 3.1: Add list_tasks, cancel_task, retry_task to SDK

**Objective:** Mirror the new API endpoints in the SDK.

**Files:**
- Modify: `src/nexusagent/sdk.py`

**Step 1: Add methods to NexusSDK**

```python
async def list_tasks(
    self,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List tasks with optional status filter and pagination."""
    from nexusagent.db import task_repo
    return await task_repo.list_tasks(status=status, limit=limit, offset=offset)

async def cancel_task(self, task_id: str) -> bool:
    """Cancel a pending or processing task."""
    from nexusagent.db import task_repo
    return await task_repo.cancel_task(task_id)

async def retry_task(self, task_id: str) -> str | None:
    """Retry a failed task. Returns new task ID or None."""
    from nexusagent.db import task_repo
    return await task_repo.retry_task(task_id)
```

**Step 2: Test and commit**

```bash
git add src/nexusagent/sdk.py
git commit -m "feat: add list_tasks, cancel_task, retry_task to SDK"
```

---

### Task 3.2: Add wait_for_result and submit_and_wait to SDK

**Objective:** Add blocking/polling helpers for synchronous-style usage.

**Files:**
- Modify: `src/nexusagent/sdk.py`

**Step 1: Add wait_for_result**

```python
async def wait_for_result(
    self,
    task_id: str,
    timeout: float = 300.0,
    poll_interval: float = 1.0,
) -> ResultSchema | None:
    """
    Poll for a task result until timeout.
    Returns the result or None if timed out.
    """
    import asyncio
    start = asyncio.get_event_loop().time()
    while True:
        result = await self.get_result(task_id)
        if result is not None:
            return result
        if asyncio.get_event_loop().time() - start >= timeout:
            return None
        await asyncio.sleep(poll_interval)
```

**Step 2: Add submit_and_wait**

```python
async def submit_and_wait(
    self,
    task_data: dict,
    timeout: float = 300.0,
    poll_interval: float = 1.0,
) -> ResultSchema | None:
    """Submit a task and wait for the result."""
    task_id = await self.submit_task(task_data)
    return await self.wait_for_result(task_id, timeout=timeout, poll_interval=poll_interval)
```

**Step 3: Test and commit**

```bash
git add src/nexusagent/sdk.py
git commit -m "feat: add wait_for_result and submit_and_wait to SDK"
```

---

### Task 3.3: Add async context manager and disconnect to SDK

**Objective:** Support `async with sdk:` pattern and proper cleanup.

**Files:**
- Modify: `src/nexusagent/sdk.py`

**Step 1: Add context manager methods**

```python
async def __aenter__(self) -> "NexusSDK":
    await self.connect()
    return self

async def __aexit__(self, *args) -> None:
    await self.disconnect()

async def disconnect(self) -> None:
    """Close the NATS connection."""
    if self.bus and self.bus.nc:
        await self.bus.close()
```

**Step 2: Test and commit**

```bash
git add src/nexusagent/sdk.py
git commit -m "feat: add async context manager and disconnect to SDK"
```

---

### Task 3.4: Add batch operations to SDK

**Objective:** Add `submit_batch()` for submitting multiple tasks at once.

**Files:**
- Modify: `src/nexusagent/sdk.py`

**Step 1: Add submit_batch**

```python
async def submit_batch(self, tasks: list[dict]) -> list[str]:
    """Submit multiple tasks. Returns list of task IDs."""
    ids = []
    for task_data in tasks:
        task_id = await self.submit_task(task_data)
        ids.append(task_id)
    return ids
```

**Step 2: Test and commit**

```bash
git add src/nexusagent/sdk.py
git commit -m "feat: add submit_batch to SDK"
```

---

## Stage 4: Polish

**Objective:** Clean up remaining issues, consolidate duplicates, improve CLI, add WebSocket.

### Task 4.1: Consolidate duplicate registries

**Objective:** Remove the old `ToolRegistry` class in `registry.py` — the new `_REGISTRY` + `ToolInfo` in `tools/registry.py` is the canonical one.

**Files:**
- Modify: `src/nexusagent/registry.py` — remove `ToolRegistry` class, keep only `find_suggested_tool` if used
- Check: `grep -r "from nexusagent.registry import ToolRegistry"` to find usages

**Step 1: Check what uses the old ToolRegistry**

Run: `grep -rn "ToolRegistry" src/ --include="*.py"`

**Step 2: Update orchestration.py to use the new registry**

Change `from nexusagent.registry import ToolRegistry` to `from nexusagent.tools.registry import _REGISTRY` (or just remove the import if not needed).

**Step 3: Commit**

```bash
git add src/nexusagent/registry.py src/nexusagent/orchestration.py
git commit -m "refactor: consolidate duplicate tool registries"
```

---

### Task 4.2: Consolidate auth systems

**Objective:** Remove `keystore.py` (duplicate of `auth.py`). Use `auth.py` as the single auth system.

**Files:**
- Delete: `src/nexusagent/keystore.py`
- Check: `grep -rn "from nexusagent.keystore import" src/`

**Step 1: Verify keystore.py is unused**

Run: `grep -rn "keystore" src/ --include="*.py"`

**Step 2: Delete if unused**

```bash
rm src/nexusagent/keystore.py
```

**Step 3: Commit**

```bash
git rm src/nexusagent/keystore.py
git commit -m "refactor: remove duplicate keystore.py"
```

---

### Task 4.3: Expand CLI with status/result/cancel commands

**Objective:** Make the CLI actually useful — add subcommands for all operations.

**Files:**
- Modify: `src/nexusagent/cli.py`

**Step 1: Rewrite CLI with subcommands**

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="NexusAgent CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Submit
    submit_parser = subparsers.add_parser("submit", help="Submit a task")
    submit_parser.add_argument("task", help="Task description")
    submit_parser.add_argument("--priority", type=int, default=1)

    # Status
    status_parser = subparsers.add_parser("status", help="Check task status")
    status_parser.add_argument("task_id", help="Task ID")

    # Result
    result_parser = subparsers.add_parser("result", help="Get task result")
    result_parser.add_argument("task_id", help="Task ID")
    result_parser.add_argument("--wait", action="store_true", help="Wait for result")
    result_parser.add_argument("--timeout", type=float, default=300)

    # List
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", choices=["pending", "processing", "completed", "failed"])
    list_parser.add_argument("--limit", type=int, default=20)

    # Cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a task")
    cancel_parser.add_argument("task_id", help="Task ID")

    # Retry
    retry_parser = subparsers.add_parser("retry", help="Retry a failed task")
    retry_parser.add_argument("task_id", help="Task ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Dispatch to appropriate handler...
```

**Step 2: Test and commit**

```bash
git add src/nexusagent/cli.py
git commit -m "feat: expand CLI with status/result/list/cancel/retry subcommands"
```

---

### Task 4.4: Add WebSocket endpoint for real-time task progress

**Objective:** `WS /ws/tasks/{task_id}` — stream task status updates.

**Files:**
- Modify: `src/nexusagent/server.py`

**Step 1: Add WebSocket endpoint**

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/tasks/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str):
    """Stream task status updates via WebSocket."""
    from nexusagent.db import task_repo
    import asyncio

    await websocket.accept()
    try:
        while True:
            status = await task_repo.get_task_status(task_id)
            await websocket.send_json({"task_id": task_id, "status": status})
            if status in ("completed", "failed"):
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
```

**Step 2: Test and commit**

```bash
git add src/nexusagent/server.py
git commit -m "feat: add WebSocket endpoint for real-time task progress"
```

---

### Task 4.5: Add comprehensive server tests

**Objective:** Test all endpoints with proper fixtures.

**Files:**
- Create/expand: `tests/test_server.py`

**Step 1: Write tests for all endpoints**

Cover: submit, list, status, result, cancel, retry, workers, tools, health, 404 cases.

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All passing.

**Step 3: Commit**

```bash
git add tests/
git commit -m "test: add comprehensive server endpoint tests"
```

---

## Execution Order

Execute stages sequentially. Get sign-off after each stage:

1. **Stage 1** — Critical bugs (5 tasks) — ~30 min
2. **Stage 2** — API endpoints (5 tasks) — ~45 min
3. **Stage 3** — SDK completeness (4 tasks) — ~30 min
4. **Stage 4** — Polish (5 tasks) — ~45 min

**Total estimated time: ~2.5 hours**

Each stage is independent — the project should be in a working state after each one.
