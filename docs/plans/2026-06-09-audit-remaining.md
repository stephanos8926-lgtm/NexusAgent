# Remaining Audit Items — Implementation Plan

> **For Hermes:** 4 independent tasks. Dispatch all in parallel.

---

## Task A: LLM API Timeouts (M2)

**Objective:** Add explicit timeouts to all LLM API calls in `llm.py`.

**File:** `src/nexusagent/llm.py`

**Changes:**
1. Add `timeout: float = 120.0` parameter to `generate()`, `_call_gemini()`, `_call_openrouter()`
2. Pass `timeout` to `model.generate_content_async()` and `client.chat.completions.create()`
3. Wrap in try/except for `asyncio.TimeoutError` with clear error message

**Test:** Add to `tests/test_config.py`:
```python
def test_llm_timeout_config():
    from nexusagent.llm import LLMProvider
    p = LLMProvider()
    # Verify timeout parameter exists
    import inspect
    sig = inspect.signature(p.generate)
    assert 'timeout' in sig.parameters
    assert sig.parameters['timeout'].default == 120.0
```

---

## Task B: Zombie Task Reaper (M3)

**Objective:** Add heartbeat + reaper for tasks stuck in PROCESSING state.

**Files:**
- Modify: `src/nexusagent/worker.py` — add heartbeat update in handle_task
- Create: `src/nexusagent/task_reaper.py` — background service that reaps stale tasks
- Test: `tests/test_task_reaper.py`

**Implementation:**
```python
# task_reaper.py
class TaskReaper:
    """Reaps tasks stuck in PROCESSING for too long."""
    
    def __init__(self, db_manager, max_age_seconds: float = 3600):
        self.db_manager = db_manager
        self.max_age = max_age_seconds
        self._interval = 60.0  # check every 60s
    
    async def start(self):
        """Start background reaper loop."""
        while True:
            await self._reap_once()
            await asyncio.sleep(self._interval)
    
    async def _reap_once(self):
        """Find and mark stale PROCESSING tasks as FAILED."""
        cutoff = datetime.now(UTC) - timedelta(seconds=self.max_age)
        async with self.db_manager.get_session() as session:
            # Find tasks in PROCESSING older than cutoff
            result = await session.execute(
                select(TaskModel).where(
                    TaskModel.status == "processing",
                    TaskModel.updated_at < cutoff.isoformat()
                )
            )
            stale = result.scalars().all()
            for task in stale:
                logger.warning(f"Reaping zombie task {task.id} (stale since {task.updated_at})")
                task.status = "failed"
```

Add heartbeat in worker.py handle_task — periodically update `updated_at` during long-running tasks.

---

## Task C: SQLite Connection Leak in Memory.fork() (M1)

**Objective:** Fix connection leak when forking Memory.

**File:** `src/nexusagent/memory.py` (lines 203-211)

**Current code:**
```python
async def fork(self, scope: MemoryScope = MemoryScope.SCOPED) -> "Memory":
    child_id = str(uuid.uuid4())
    mgr = MemoryManager(db_path=self.db_path)
    child = await mgr.create(child_id, scope, parent_memory_id=self.memory_id)
    child._conn = self._get_connection()  # LEAK: creates new connection, old one not closed
    return child
```

**Fix:** Don't create a new connection for the child. Share the parent's connection:
```python
async def fork(self, scope: MemoryScope = MemoryScope.SCOPED) -> "Memory":
    child_id = str(uuid.uuid4())
    child = Memory(
        memory_id=child_id,
        scope=scope,
        db_path=self.db_path,
        parent_memory_id=self.memory_id,
        conn=self._conn,  # Share parent's connection
    )
    return child
```

**Test:** Add to existing memory tests:
```python
@pytest.mark.asyncio
async def test_fork_does_not_leak_connection(mem_mgr):
    parent = await mem_mgr.create("parent-1", MemoryScope.ISOLATED)
    child = await parent.fork(MemoryScope.ISCOPED)
    # Both should share the same DB path
    assert child.db_path == parent.db_path
    # Child should be able to remember
    await child.remember("Child memory", {})
    # Parent should not see child's memories (isolated scope)
    parent_results = await parent.recall("memory", limit=10)
    child_results = await child.recall("memory", limit=10)
    assert len(child_results) > len(parent_results)
```

---

## Task D: Standardize Worker vs WorkerPool (M4)

**Objective:** Remove duplicate execution logic. WorkerPool is the newer, better implementation.

**File:** `src/nexusagent/worker.py`

**Changes:**
1. Remove the old `NexusWorker._execute_agent_logic()` method (lines 38-62) — it's superseded by WorkerPool
2. Keep `NexusWorker.handle_task()` for NATS message handling but delegate execution to WorkerPool
3. Remove the `finally: asyncio.sleep(0.1)` in start() — it's a race condition waiting to happen

**Test:** Update existing worker tests to use WorkerPool instead of NexusWorker for execution tests.

---

## Execution Order

All 4 tasks are independent — dispatch in parallel:
- Task A: llm.py (add timeouts)
- Task B: task_reaper.py (new file) + worker.py (heartbeat)
- Task C: memory.py (fix fork connection leak)
- Task D: worker.py (standardize execution)

After all complete:
```bash
python3 -m pytest tests/ -q
ruff check src/ tests/
git add -A && git commit -m "fix(audit): LLM timeouts + zombie reaper + connection leak + worker standardization"
```
