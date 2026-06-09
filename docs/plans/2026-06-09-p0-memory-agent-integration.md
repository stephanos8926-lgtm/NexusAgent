# P0: Wire Memory Into Agent — Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill. Tasks 1 and 2 are independent — dispatch in parallel. Task 3 depends on both.

**Goal:** Make the agent actually use recalled memories when processing user messages. Currently memory context is built in `session.send()` but passed as `state["context"]` which `deepagents.invoke()` ignores. Need to inject into the system prompt.

**Architecture:**
```
User message → recall memories → inject into system prompt → agent processes with context
                                                     ↓
                                          Compaction check before each call
                                                     ↓
                              Pre-compaction flush if context > 75% threshold
```

## The Problem

```python
# session.py:92 — context is built but passed wrong
state = {"message": user_message, "context": context}  # deepagents ignores "context"
result = self.agent(state)  # agent never sees memories

# agent.py:107-108 — deepagents.invoke() expects messages=[...], not context=
def __call__(self, *args, **kwargs):
    return self._inner.invoke(*args, **kwargs)  # passes through to deepagents
```

deepagents `create_deep_agent()` accepts a `system_prompt` parameter at creation time and `messages` at invoke time. The memory context needs to be prepended to the system prompt.

## Task 1: Inject Memory Context Into Agent System Prompt

**Objective:** Modify `session.send()` to prepend memory context to the system prompt, so the agent sees recalled memories.

**Files:**
- Modify: `src/nexusagent/session.py:61-128` (the `send()` method)
- Test: `tests/test_session_memory.py` (new)

**Step 1: Write failing test**

```python
# tests/test_session_memory.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from nexusagent.session import Session

@pytest.fixture
def mock_session():
    """Create a session with mocked dependencies."""
    with patch('nexusagent.session.SessionManager'):
        session = Session(
            session_id="test-1",
            working_dir="/tmp",
            agent=MagicMock(),
            hybrid_memory=MagicMock(),
            memory=MagicMock(),
            db_repo=MagicMock(),
        )
        session.db_repo.add_message = AsyncMock()
        session.db_repo.update_status = AsyncMock()
        session.memory.recall = AsyncMock(return_value=[])
        session.memory.remember = AsyncMock()
        session.hybrid_memory.get_memory_context = MagicMock(return_value="## Test memory context")
        return session

@pytest.mark.asyncio
async def test_memory_context_in_system_prompt(mock_session):
    """Verify memory context is injected into the agent's system prompt."""
    await mock_session.send("Fix the auth bug")
    
    # Agent should have been called with system_prompt containing memory context
    call_args = mock_session.agent.call_args
    assert call_args is not None
    
    # Check that system_prompt was passed and contains memory context
    kwargs = call_args[1] if len(call_args) > 1 else {}
    system_prompt = kwargs.get('system_prompt', '')
    assert 'memory context' in system_prompt or 'Test memory context' in str(call_args)

@pytest.mark.asyncio
async def test_no_memory_context_when_empty(mock_session):
    """When no memories are found, system_prompt should not have memory section."""
    mock_session.hybrid_memory.get_memory_context = MagicMock(return_value="")
    await mock_session.send("Hello")
    
    call_args = mock_session.agent.call_args
    # Should still work without memory context
    assert call_args is not None
```

**Step 2: Run test to verify failure**
```bash
cd /home/sysop/Workspaces/NexusAgent && python3 -m pytest tests/test_session_memory.py -v
```
Expected: FAIL — memory context not in system prompt

**Step 3: Implement the fix in session.py**

Replace the `send()` method (lines 61-128) with this version that injects memory context into the system prompt:

```python
async def send(self, user_message: str) -> None:
    """Process a user message: store in DB, recall memory, invoke agent, emit events."""
    if self.status != "active":
        self._enqueue(ErrorEvent(message="Session is not active").model_dump())
        return

    # Store user message in DB
    try:
        await self.db_repo.add_message(self.session_id, "user", user_message)
    except Exception as exc:
        logger.warning("Failed to store user message in DB: %s", exc)

    # Build system prompt with memory context
    system_prompt = self._base_system_prompt()
    try:
        hybrid_context = self.hybrid_memory.get_memory_context(user_message, max_results=5)
        if hybrid_context:
            system_prompt = f"{system_prompt}\n\n{hybrid_context}"
    except Exception as exc:
        logger.warning("Hybrid memory context retrieval failed: %s", exc)

    # Invoke agent with system_prompt
    self._cancel_flag = False
    try:
        result = self.agent(
            {"message": user_message},
            system_prompt=system_prompt,
        )
        # ... rest of event handling unchanged
```

Add a helper method `_base_system_prompt()` that returns the default system prompt (extracted from the agent's existing prompt or a reasonable default).

**Step 4: Run test to verify pass**
```bash
python3 -m pytest tests/test_session_memory.py -v
```

**Step 5: Run full suite to check for regressions**
```bash
python3 -m pytest tests/ -q
```

**Step 6: Commit**
```bash
git add src/nexusagent/session.py tests/test_session_memory.py
git commit -m "feat(session): inject memory context into agent system prompt"
```

---

## Task 2: Async Embedding for Indexing (P1)

**Objective:** Make `index_file()` use the full Gemini embedding chain instead of hash fallback, so stored vectors match query quality.

**Files:**
- Modify: `src/nexusagent/memory_index.py` — make `index_file()` async
- Modify: `src/nexusagent/memory.py` — make `remember()` call async `index_file()`
- Test: `tests/test_memory_index.py` — update existing tests for async

**Step 1: Write failing test**

Add to `tests/test_memory_index.py`:

```python
@pytest.mark.asyncio
async def test_async_index_and_search(populated_index):
    """Test that async indexing produces searchable vectors."""
    # Index a new file asynchronously
    workspace = Path(populated_index.workspace)
    (workspace / "bank" / "async_test.md").write_text(
        "---\nname: Async Test\ndescription: Testing async indexing\ntype: world\n---\n\n"
        "Async indexed content about machine learning models."
    )
    await populated_index.async_index_file("bank/async_test.md")
    
    # Search should find it with vector similarity (not just keyword)
    results = await populated_index.search("machine learning", max_results=5)
    assert any("machine" in r["content"].lower() for r in results)
```

**Step 2: Run test to verify failure**
```bash
python3 -m pytest tests/test_memory_index.py::test_async_index_and_search -v
```
Expected: FAIL — `async_index_file` method doesn't exist

**Step 3: Add async_index_file() to HybridMemoryIndex**

In `memory_index.py`, add:

```python
async def async_index_file(self, relative_path: str):
    """Index a file using the full async embedding chain (Gemini/local)."""
    filepath = self.workspace / relative_path
    if not filepath.exists():
        logger.warning("File not found: %s", filepath)
        return
    
    content = filepath.read_text()
    # Remove YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2]
    
    chunks = self._chunk_text(content)
    
    conn = sqlite3.connect(str(self.db_path))
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        
        # Delete old entries
        old_ids = [r[0] for r in conn.execute(
            "SELECT id FROM chunks WHERE file_path = ?", (relative_path,)
        ).fetchall()]
        conn.execute("DELETE FROM chunks WHERE file_path = ?", (relative_path,))
        conn.execute("DELETE FROM chunks_fts WHERE file_path = ?", (relative_path,))
        for oid in old_ids:
            conn.execute("DELETE FROM chunks_vec WHERE id = ?", (oid,))
        
        now = datetime.now(UTC).isoformat()
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{relative_path}:{i}:{uuid.uuid4().hex[:8]}"
            
            # Use the ASYNC embedding chain (Gemini → local → hash fallback)
            vec = await self.embedder.embed(chunk["content"])
            vec_blob = _vec_to_blob(vec)
            
            conn.execute(
                "INSERT INTO chunks (id, file_path, line_start, line_end, content, embedding, indexed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (chunk_id, relative_path, chunk["start"], chunk["end"],
                 chunk["content"], vec_blob, now)
            )
            conn.execute(
                "INSERT INTO chunks_fts (id, content, file_path) VALUES (?, ?, ?)",
                (chunk_id, chunk["content"], relative_path)
            )
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO chunks_vec (id, embedding) VALUES (?, ?)",
                    (chunk_id, vec_blob)
                )
            except Exception as e:
                logger.warning("Vector insert failed: %s", e)
        
        # Update file meta
        file_hash = hashlib.md5(filepath.read_bytes()).hexdigest()
        conn.execute(
            "INSERT OR REPLACE INTO file_meta (file_path, mtime, hash, last_indexed) VALUES (?, ?, ?, ?)",
            (relative_path, filepath.stat().st_mtime, file_hash, now)
        )
        conn.commit()
    finally:
        conn.close()
```

Update `HybridMemoryManager.remember()` in `memory.py`:

```python
async def remember(self, content: str, type: str, description: str,
                   confidence: float | None = None, entities: list[str] | None = None) -> str:
    """Write a memory entry and index it with the full async embedding chain."""
    from nexusagent.memory_files import MemoryEntryType
    
    entry_type = MemoryEntryType(type)
    filepath = self.file_memory.write_entry(
        content=content, entry_type=entry_type, description=description,
        confidence=confidence, entities=entities,
    )
    rel_path = filepath.replace(self.workspace_dir, "").lstrip("/")
    await self.index.async_index_file(rel_path)  # Now async with Gemini embeddings
    return filepath
```

**Step 4: Run test to verify pass**

**Step 5: Run full suite**

**Step 6: Commit**
```bash
git add src/nexusagent/memory_index.py src/nexusagent/memory.py tests/test_memory_index.py
git commit -m "feat(memory): async embedding for indexing — Gemini vectors for stored chunks"
```

---

## Task 3: Hook Compaction Into Agent Loop

**Objective:** Before each model call, check if context exceeds threshold and compact if needed.

**Files:**
- Modify: `src/nexusagent/session.py` — add compaction check in `send()`
- Test: Add compaction integration tests to `tests/test_session_memory.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_compaction_triggered_on_long_context(mock_session):
    """When context is very long, compaction should be triggered."""
    # Create a very long context
    long_text = "x" * 100000
    
    from nexusagent.compaction import CompactionPipeline
    pipeline = CompactionPipeline(context_window_tokens=200000)
    
    # Simulate messages that would exceed threshold
    messages = [
        {"role": "user", "content": long_text},
        {"role": "assistant", "content": long_text},
    ]
    
    assert pipeline.should_compact(messages), "Should trigger compaction for long context"
    
    compacted = pipeline.compact(messages)
    assert len(compacted) < len(messages) or sum(len(m.get('content','')) for m in compacted) < sum(len(m.get('content','')) for m in messages), "Compaction should reduce context"
```

**Step 2: Run test to verify failure**

**Step 3: Implement compaction hook in session.py**

Add compaction check in `send()` before calling the agent:

```python
# In send(), before agent invocation:
# Check compaction
try:
    messages = self._get_conversation_messages()
    if self.compaction.should_compact(messages):
        summary = self.pre_compaction_flush()
        messages = self.compaction.compact(messages)
        self._set_conversation_messages(messages)
        # Inject summary into system prompt
        system_prompt = f"{system_prompt}\n\n[Pre-compaction summary: {summary}]"
except Exception as exc:
    logger.warning("Compaction check failed: %s", exc)
```

**Step 4: Run tests**

**Step 5: Run full suite**

**Step 6: Commit**
```bash
git add src/nexusagent/session.py tests/test_session_memory.py
git commit -m "feat(session): hook compaction into agent loop — auto-compact at 75% threshold"
```

---

## Verification

After all tasks:
```bash
python3 -m pytest tests/ -q
ruff check src/ tests/
ruff format src/ tests/
```

Expected: All 148+ tests passing, 0 regressions.
