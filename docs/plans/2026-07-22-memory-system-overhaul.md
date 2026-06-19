# Memory System Overhaul — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Wire memory into the session loop, add cross-session continuity, auto-extraction, consolidation daemon, and hierarchical context compression.

**Architecture:** Session owns HybridMemoryManager → auto-recall at start → auto-extract after each turn → flush before compaction → background dream cycle for maintenance.

**Tech Stack:** Python 3.13, asyncio, aiohttp (for embedding API), sqlite-vec, pytest

---

## Phase 0: Fix Config Path Bug (5 min)

**Objective:** Fix the `nexus.db` path mismatch.

**Files:**
- Modify: `src/nexusagent/infrastructure/config.py:71` (or wherever `db_path` is)

**Step 1: Verify actual DB location**
```bash
ls -la ~/.nexusagent/nexus.db ~/.nexusagent/data/nexus.db 2>&1
```

**Step 2: Update config default**
```python
# If nexus.db is at root level:
db_path: str = str(nexus_home / "nexus.db")  # NOT "data/nexus.db"
```

**Step 3: Commit**
```bash
git add src/nexusagent/infrastructure/config.py
git commit -m "fix(config): correct default db_path to match actual nexus.db location"
```

---

## Phase 1: Session-Memory Integration (2-3 days)

### Task 1.1: Add memory_dir to Session constructor

**Objective:** Session creates and owns a HybridMemoryManager.

**Files:**
- Modify: `src/nexusagent/core/session/session.py`
- Modify: `src/nexusagent/core/session/manager.py`

**Step 1: Write failing test**
```python
# tests/test_session_memory.py
async def test_session_creates_hybrid_memory():
    session = Session(session_id="test", working_dir="/tmp/test", agent=mock_agent)
    assert session.hybrid_memory is not None
    assert session.hybrid_memory.memory_dir.exists()
```

**Step 2: Run test to verify failure**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_session_creates_hybrid_memory -v
Expected: FAIL — "HybridMemoryManager not found" or similar
```

**Step 3: Implement**
```python
# session.py
from nexusagent.memory.hybrid_memory import HybridMemoryManager

class Session:
    def __init__(self, ..., memory_dir: str | None = None):
        self.memory_dir = memory_dir or self._default_memory_dir()
        self.hybrid_memory = HybridMemoryManager(self.memory_dir)
        self.hybrid_memory.initialize()
    
    def _default_memory_dir(self) -> str:
        # Priority: config → workspace → legacy
        from nexusagent.infrastructure.config import load_config
        settings = load_config()
        if settings.agent.memory_workspace:
            return str(Path(settings.agent.memory_workspace).expanduser())
        if self.working_dir:
            return str(Path(self.working_dir) / ".nexusagent" / "memory")
        return str(Path.home() / ".nexusagent" / "sessions" / self.session_id / "memory")
```

**Step 4: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_session_creates_hybrid_memory -v
Expected: PASS
```

**Step 5: Commit**
```bash
git add src/nexusagent/core/session/session.py tests/test_session_memory.py
git commit -m "feat(session): wire HybridMemoryManager into Session constructor"
```

### Task 1.2: Auto-recall at session start

**Objective:** Session injects memory context as SystemMessage before agent invocation.

**Files:**
- Modify: `src/nexusagent/core/session/session.py` (`send()` method)

**Step 1: Write failing test**
```python
async def test_session_injects_memory_context():
    session = Session(..., memory_dir=tmp_memory_dir)
    # Pre-populate a memory
    session.hybrid_memory.remember("Test fact about auth", type="world", description="Auth fact")
    # Send message
    await session.send("Tell me about auth")
    # Verify SystemMessage with memory context was injected
    messages = session._last_messages
    assert any("Test fact about auth" in str(m.content) for m in messages if isinstance(m, SystemMessage))
```

**Step 2: Run test to verify failure**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_session_injects_memory_context -v
Expected: FAIL
```

**Step 3: Implement in `send()`**
```python
# In send(), after building base messages:
if self.hybrid_memory:
    memory_context = self.hybrid_memory.get_memory_context(user_message, max_results=5)
    if memory_context:
        # Insert after system prompt, before history
        messages.insert(1, SystemMessage(content=f"[Memory Context]\n{memory_context}\n[/Memory Context]"))
```

**Step 4: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_session_injects_memory_context -v
Expected: PASS
```

**Step 5: Commit**
```bash
git add src/nexusagent/core/session/session.py tests/test_session_memory.py
git commit -m "feat(session): auto-recall memory context at session start"
```

### Task 1.3: Auto-extract after each turn

**Objective:** After agent response, extract and store observations.

**Files:**
- Modify: `src/nexusagent/core/session/session.py`
- Create: `src/nexusagent/memory/extraction.py`

**Step 1: Write failing test**
```python
async def test_session_auto_extracts_memories():
    session = Session(..., memory_dir=tmp_memory_dir)
    await session.send("I prefer using pytest over unittest")
    # Wait for async extraction
    await asyncio.sleep(1)
    # Check memory was created
    results = session.hybrid_memory.recall("pytest preference", max_results=3)
    assert len(results) > 0
    assert any("pytest" in r.get("content", "") for r in results)
```

**Step 2: Run test to verify failure**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_session_auto_extracts_memories -v
Expected: FAIL
```

**Step 3: Implement extraction module**
```python
# src/nexusagent/memory/extraction.py
class MemoryExtractor:
    """Extract memorable facts from conversation turns."""
    
    def __init__(self, model=None):
        self.model = model  # LLM for extraction, None = skip
    
    async def extract(self, user_message: str, agent_response: str) -> list[dict]:
        """Extract memory entries from a conversation turn."""
        if not self.model:
            return []
        
        prompt = f"""Extract memorable facts from this conversation turn.
Return JSON array of objects with: content, type (world/experience/opinion/observation), description, confidence, entities.

User: {user_message[:500]}
Agent: {agent_response[:500]}

JSON:"""
        
        try:
            response = await self.model.ainvoke(prompt)
            entries = json.loads(response.content)
            return entries
        except Exception:
            return []  # Fail silently — extraction is best-effort
```

**Step 4: Wire into Session.send()**
```python
# In send(), after agent response:
if self.hybrid_memory and self.memory_extractor:
    asyncio.create_task(
        self._auto_extract(user_message, agent_response)
    )

async def _auto_extract(self, user_message: str, agent_response: str):
    entries = await self.memory_extractor.extract(user_message, agent_response)
    for entry in entries:
        try:
            self.hybrid_memory.remember(**entry)
        except Exception:
            pass  # Best-effort
```

**Step 5: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_session_auto_extracts_memories -v
Expected: PASS
```

**Step 6: Commit**
```bash
git add src/nexusagent/core/session/session.py src/nexusagent/memory/extraction.py tests/test_session_memory.py
git commit -m "feat(session): auto-extract memories after each turn"
```

### Task 1.4: Pre-compaction flush

**Objective:** Save session summary to memory before context compaction.

**Files:**
- Modify: `src/nexusagent/core/session/session.py` (`pre_compaction_flush()`)

**Step 1: Write failing test**
```python
async def test_pre_compaction_flush():
    session = Session(..., memory_dir=tmp_memory_dir)
    await session.send("Test message")
    summary = await session.pre_compaction_flush()
    assert summary is not None
    # Check daily log was created
    daily_logs = session.hybrid_memory.get_daily_logs(1)
    assert len(daily_logs) > 0
```

**Step 2: Run test to verify failure**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_pre_compaction_flush -v
Expected: FAIL
```

**Step 3: Implement**
```python
async def pre_compaction_flush(self) -> str:
    """Flush session state to daily log before compaction."""
    if not self.hybrid_memory:
        return ""
    
    summary = self._build_session_summary()
    await self.hybrid_memory.flush(summary)
    return summary

def _build_session_summary(self) -> str:
    """Build a summary of the current session."""
    # Extract key info from recent messages
    recent = self._messages[-10:] if hasattr(self, '_messages') else []
    summary_parts = []
    for msg in recent:
        if hasattr(msg, 'content') and msg.content:
            content = msg.content[:200]
            summary_parts.append(f"- {content}")
    return "\n".join(summary_parts) if summary_parts else "Session activity"
```

**Step 4: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_pre_compaction_flush -v
Expected: PASS
```

**Step 5: Commit**
```bash
git add src/nexusagent/core/session/session.py tests/test_session_memory.py
git commit -m "feat(session): pre-compaction flush saves session summary to memory"
```

### Task 1.5: Cross-session memory discovery

**Objective:** SessionManager finds relevant memories from previous sessions.

**Files:**
- Modify: `src/nexusagent/core/session/manager.py`
- Modify: `src/nexusagent/infrastructure/db/session_repo.py` (add query)

**Step 1: Write failing test**
```python
async def test_cross_session_discovery():
    # Create two sessions for same workspace
    session1 = await manager.get_or_create("s1", "/tmp/workspace", agent, repo)
    session1.hybrid_memory.remember("Important fact from session 1", type="world", description="S1 fact")
    
    session2 = await manager.get_or_create("s2", "/tmp/workspace", agent, repo)
    # Should find session1's memory
    prev_memories = manager._discover_previous_memories("/tmp/workspace", "s2")
    assert len(prev_memories) > 0
    assert any("Important fact" in str(m) for m in prev_memories)
```

**Step 2: Run test to verify failure**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_cross_session_discovery -v
Expected: FAIL
```

**Step 3: Implement**
```python
# manager.py
def _discover_previous_memories(self, working_dir: str, current_session_id: str, limit: int = 3) -> list[dict]:
    """Find relevant memories from previous sessions in the same workspace."""
    # Query DB for previous sessions with same working_dir
    prev_sessions = self.db_repo.find_sessions_by_working_dir(
        working_dir, exclude=current_session_id, limit=5
    )
    
    all_memories = []
    for prev in prev_sessions:
        memory_dir = Path(prev.memory_dir) if prev.memory_dir else None
        if memory_dir and memory_dir.exists():
            idx_path = memory_dir / ".memory" / "index.sqlite"
            if idx_path.exists():
                idx = HybridMemoryIndex(str(idx_path))
                results = idx.search_sync(f"recent activity in {working_dir}", max_results=limit)
                all_memories.extend(results)
    
    all_memories.sort(key=lambda m: m.get("score", 0), reverse=True)
    return all_memories[:limit]
```

**Step 4: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py::test_cross_session_discovery -v
Expected: PASS
```

**Step 5: Commit**
```bash
git add src/nexusagent/core/session/manager.py tests/test_session_memory.py
git commit -m "feat(session): cross-session memory discovery from previous sessions"
```

### Task 1.6: Wire memory_dir through server and agent

**Objective:** Ensure memory_dir flows from config → server → agent → session.

**Files:**
- Modify: `src/nexusagent/server/websocket.py`
- Modify: `src/nexusagent/core/agent.py`
- Modify: `src/nexusagent/interfaces/cli.py`

**Step 1: Write failing test**
```python
async def test_memory_dir_flows_through_stack():
    # Config has memory_workspace set
    settings = AgentConfig(agent=AgentConfig.AgentConfig(memory_workspace="/tmp/test_memory"))
    # Server resolves memory_dir from config
    memory_dir = resolve_memory_dir(settings, working_dir="/tmp/workspace")
    assert memory_dir == str(Path("/tmp/test_memory").expanduser())
```

**Step 2: Implement**
```python
# websocket.py — already partially done (memory_workspace check exists)
# agent.py — pass memory_dir from state
# cli.py — pass --memory-dir flag
```

**Step 3: Run all Phase 1 tests**
```bash
PYTHONPATH=src python3 -m pytest tests/test_session_memory.py -v
Expected: All pass
```

**Step 4: Run full test suite**
```bash
PYTHONPATH=src python3 -m pytest tests/ -q --tb=short
Expected: No regressions
```

**Step 5: Commit**
```bash
git add -A
git commit -m "feat: wire memory_dir through server → agent → session stack"
```

---

## Phase 2: Consolidation Daemon (2-3 days)

### Task 2.1: Dream cycle engine

**Objective:** Implement `DreamCycle` class with 4-phase consolidation.

**Files:**
- Create: `src/nexusagent/memory/dream.py`

**Step 1: Write failing test**
```python
async def test_dream_cycle_removes_duplicates():
    # Create memory dir with duplicate entries
    fm = FileMemory(tmp_dir)
    fm.initialize()
    fm.write_entry("Same fact", "world", "Fact A")
    fm.write_entry("Same fact", "world", "Fact A duplicate")  # Near-duplicate
    
    dream = DreamCycle()
    report = await dream.run(tmp_dir, dry_run=False)
    assert report["actions"]["duplicates_removed"] >= 1
```

**Step 2: Implement DreamCycle**
```python
# src/nexusagent/memory/dream.py
class DreamCycle:
    def __init__(self, consolidation_engine: ConsolidationEngine | None = None):
        self.engine = consolidation_engine or ConsolidationEngine()
    
    async def run(self, memory_dir: str, dry_run: bool = False) -> dict:
        scan = self.engine.scan(memory_dir)
        patterns = await self._find_patterns(memory_dir)
        actions = self.engine.consolidate(scan) if not dry_run else self._preview(scan, patterns)
        return {"scan": scan, "patterns": patterns, "actions": actions}
```

**Step 3: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_dream_cycle.py::test_dream_cycle_removes_duplicates -v
Expected: PASS
```

**Step 4: Commit**
```bash
git add src/nexusagent/memory/dream.py tests/test_dream_cycle.py
git commit -m "feat(memory): dream cycle engine for background consolidation"
```

### Task 2.2: Cron integration

**Objective:** Add `memory_dream` tool and cron config.

**Files:**
- Modify: `src/nexusagent/tools/register_all.py`
- Modify: `src/nexusagent/infrastructure/config.py`

**Step 1: Add config fields**
```python
# config.py
dream_enabled: bool = True
dream_interval_hours: int = 24
dream_after_sessions: int = 5
dream_dry_run: bool = False
```

**Step 2: Add memory_dream tool to register_all.py**
```python
@register_tool(name="memory_dream", ...)
async def memory_dream(dry_run: bool = True) -> str:
    """Run consolidation dream cycle."""
    # ... implementation
```

**Step 3: Commit**
```bash
git add src/nexusagent/tools/register_all.py src/nexusagent/infrastructure/config.py
git commit -m "feat: add memory_dream tool and cron config"
```

---

## Phase 3: Hierarchical Context Compression (3-5 days)

### Task 3.1: LCM-style summary DAG

**Objective:** Implement hierarchical summary DAG for session history.

**Files:**
- Create: `src/nexusagent/memory/dag.py`

**Step 1: Write failing test**
```python
def test_dag_compression():
    dag = SummaryDAG()
    # Add 20 leaf messages
    for i in range(20):
        dag.add_leaf(f"Message {i}: detailed technical content")
    # Compress
    dag.compress()
    # Should have depth-1 summaries
    assert len(dag.depth_1) > 0
    # Can still recover original via expand
    original = dag.expand(dag.depth_1[0].id)
    assert len(original) > 0
```

**Step 2: Implement SummaryDAG**
```python
# src/nexusagent/memory/dag.py
class SummaryDAG:
    """Hierarchical summary DAG for session history."""
    
    def __init__(self, fresh_tail_size: int = 64):
        self.fresh_tail_size = fresh_tail_size
        self.depth_0: list[LeafNode] = []  # Raw messages
        self.depth_1: list[SummaryNode] = []  # Conversation arcs
        self.depth_2: list[SummaryNode] = []  # Narrative
    
    def add_leaf(self, content: str, metadata: dict = None):
        """Add a raw message as depth-0 leaf."""
        # ... implementation
    
    def compress(self):
        """Compress: depth-0 → depth-1 → depth-2."""
        # ... implementation
    
    def expand(self, node_id: str) -> list[str]:
        """Expand a summary back to source messages."""
        # ... implementation
```

**Step 3: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_summary_dag.py::test_dag_compression -v
Expected: PASS
```

**Step 4: Commit**
```bash
git add src/nexusagent/memory/dag.py tests/test_summary_dag.py
git commit -t "feat(memory): hierarchical summary DAG for context compression"
```

### Task 3.2: Wire DAG into compaction pipeline

**Objective:** Replace flat compaction with DAG-based compression.

**Files:**
- Modify: `src/nexusagent/memory/compaction.py`

**Step 1: Write failing test**
```python
def test_dag_compaction_preserves_recent_messages():
    pipeline = CompactionPipeline(context_window_tokens=1000)
    # Add 50 messages (exceeds budget)
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"} for i in range(50)]
    compacted = pipeline.compact(messages)
    # Recent messages should be preserved
    assert len(compacted) < len(messages)  # Compressed
    assert "Message 49" in str(compacted[-1])  # Fresh tail preserved
```

**Step 2: Implement**
```python
# compaction.py
class CompactionPipeline:
    def compact(self, messages: list[dict]) -> list[dict]:
        # 1. Check if compaction needed
        if not self.should_compact(messages):
            return messages
        
        # 2. Build DAG
        dag = SummaryDAG(fresh_tail_size=self.fresh_tail_size)
        for msg in messages:
            dag.add_leaf(msg.get("content", ""), {"role": msg.get("role")})
        
        # 3. Compress
        dag.compress()
        
        # 4. Convert back to messages
        return self._dag_to_messages(dag)
```

**Step 3: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_compaction.py::test_dag_compaction_preserves_recent_messages -v
Expected: PASS
```

**Step 4: Commit**
```bash
git add src/nexusagent/memory/compaction.py tests/test_compaction.py
git commit -m "feat: wire DAG-based compression into compaction pipeline"
```

---

## Phase 4: Provenance & Observation Extraction (2 days)

### Task 4.1: Provenance tracking

**Objective:** Every memory entry stores `source_session_id` and `derived_from`.

**Files:**
- Modify: `src/nexusagent/memory/memory_files.py`
- Modify: `src/nexusagent/tools/register_all.py`

**Step 1: Write failing test**
```python
def test_provenance_tracking():
    fm = FileMemory(tmp_dir)
    fm.initialize()
    path = fm.write_entry(
        "Test fact", "world", "Test",
        source_session_id="session-abc",
        derived_from=["memory-xyz"]
    )
    content = fm.read_topic_file(path)
    assert "source_session_id: session-abc" in content
    assert "derived_from: memory-xyz" in content
```

**Step 2: Implement**
```python
# memory_files.py — add to write_entry():
def write_entry(self, ..., source_session_id: str | None = None, derived_from: list[str] | None = None) -> str:
    # Add to YAML frontmatter:
    if source_session_id:
        frontmatter["source_session_id"] = source_session_id
    if derived_from:
        frontmatter["derived_from"] = derived_from
```

**Step 3: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_provenance.py::test_provenance_tracking -v
Expected: PASS
```

**Step 4: Commit**
```bash
git add src/nexusagent/memory/memory_files.py tests/test_provenance.py
git commit -m "feat(memory): provenance tracking for memory entries"
```

### Task 4.2: Observation extraction

**Objective:** Background process extracts patterns across memories.

**Files:**
- Create: `src/nexusagent/memory/observations.py`

**Step 1: Write failing test**
```python
def test_observation_extraction():
    extractor = ObservationExtractor()
    memories = [
        {"content": "User prefers tabs over spaces", "type": "opinion"},
        {"content": "User uses tabs in all Python files", "type": "observation"},
        {"content": "User configures editor with tab_size=4", "type": "experience"},
    ]
    observations = extractor.extract(memories)
    assert any("tabs" in obs["content"] for obs in observations)
```

**Step 2: Implement**
```python
# src/nexusagent/memory/observations.py
class ObservationExtractor:
    """Extract observations from memory patterns."""
    
    def extract(self, memories: list[dict]) -> list[dict]:
        # Group by entity
        # Find recurring patterns
        # Generate observations
        # ... implementation
```

**Step 3: Run test to verify pass**
```bash
PYTHONPATH=src python3 -m pytest tests/test_observations.py::test_observation_extraction -v
Expected: PASS
```

**Step 4: Commit**
```bash
git add src/nexusagent/memory/observations.py tests/test_observations.py
git commit -m "feat(memory): observation extraction from memory patterns"
```

---

## Phase 5: Integration Testing & Polish (1-2 days)

### Task 5.1: End-to-end memory flow test

**Objective:** Verify the full flow: session start → recall → conversation → extract → flush → dream.

**Step 1: Write integration test**
```python
@pytest.mark.asyncio
async def test_full_memory_flow():
    """End-to-end: session recalls, extracts, flushes, and consolidates."""
    # 1. Create session with memory
    session = Session(session_id="e2e-test", working_dir=tmp_dir, ...)
    
    # 2. Pre-populate a memory
    session.hybrid_memory.remember(
        "The project uses FastAPI", type="world", description="Framework"
    )
    
    # 3. Send message — should recall memory
    await session.send("What framework does this project use?")
    
    # 4. Verify memory context was injected
    # 5. Verify auto-extraction created observations
    # 6. Flush — verify daily log
    # 7. Dream cycle — verify consolidation
```

**Step 2: Run integration test**
```bash
PYTHONPATH=src python3 -m pytest tests/test_memory_e2e.py -v
Expected: PASS
```

**Step 3: Run full test suite**
```bash
PYTHONPATH=src python3 -m pytest tests/ -q --tb=short
Expected: No regressions
```

**Step 4: Commit**
```bash
git add tests/test_memory_e2e.py
git commit -t "test: end-to-end memory flow integration test"
```

### Task 5.2: Update documentation

**Objective:** Update README, ARCHITECTURE, and AGENTS.md with new memory system.

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `AGENTS.md`

**Step 1: Document the memory system architecture**
**Step 2: Update refactoring history**
**Step 3: Commit**
```bash
git add README.md docs/ARCHITECTURE.md AGENTS.md
git commit -m "docs: update architecture docs with memory system integration"
```

---

## Task Summary

| Phase | Tasks | Estimated LOC | Duration |
|-------|-------|--------------|----------|
| 0: Config fix | 1 | 5 | 5 min |
| 1: Session integration | 6 | ~400 | 2-3 days |
| 2: Dream daemon | 2 | ~200 | 2-3 days |
| 3: DAG compression | 2 | ~300 | 3-5 days |
| 4: Provenance + observations | 2 | ~150 | 2 days |
| 5: Integration + docs | 2 | ~100 | 1-2 days |
| **Total** | **15** | **~1155** | **10-15 days** |

## Dependencies

```
Phase 0 (config fix)
  ↓
Phase 1 (session integration) ← blocks everything
  ↓
Phase 2 (dream daemon) ← can parallel with Phase 3
Phase 3 (DAG compression) ← can parallel with Phase 2
  ↓
Phase 4 (provenance + observations)
  ↓
Phase 5 (integration + docs)
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto-extraction LLM calls add latency | Medium | Fire-and-forget, use lightweight model |
| Federated search slow with many sessions | Low | Parallel search, cache results |
| DAG compression loses critical info | High | Fresh tail protection, expandable summaries |
| Memory tools not called by agent | Medium | Auto-extraction doesn't rely on agent calling tools |
| Breaking existing session tests | High | Run tests after every task, compat shims |
