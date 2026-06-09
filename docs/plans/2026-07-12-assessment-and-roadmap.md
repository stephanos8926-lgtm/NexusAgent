# NexusAgent — Honest Assessment & Roadmap

## What's Built (1,780 lines, 148 tests passing)

### Fully Working
| Component | Lines | Status |
|-----------|-------|--------|
| File-based memory (MEMORY.md index, bank/, daily logs) | 264 | ✅ Tested |
| Hybrid search index (FTS5 + sqlite-vec) | 586 | ✅ Tested |
| Embedding provider (Gemini → local → hash fallback) | — | ✅ Working (Gemini key active) |
| Memory tools (memory_search, memory_get, memory_write) | — | ✅ Registered |
| Compaction pipeline (4-layer graduated) | 233 | ✅ Tested |
| Isolated workers (WorkerPool, TaskContract, SubAgentHandle) | — | ✅ Tested |
| Session persistence (DB, messages) | — | ✅ Tested |
| Streaming events, approval modal, CLI commands | — | ✅ Tested |

### Exists But Not Connected
| Component | What's Missing |
|-----------|---------------|
| **Memory → Agent injection** | `session.send()` builds context correctly, but `NexusAgent.__call__()` passes it as `state["context"]` which `deepagents.invoke()` doesn't understand. Need to inject into system prompt or message history. |
| **Compaction in agent loop** | `CompactionPipeline` exists but is never called before model invocation. Need to hook into the agent's message processing loop. |
| **Async embedding for indexing** | `index_file()` uses hash embeddings (sync). Stored vectors are low-quality. Need async re-indexing or make `index_file` async. |
| **WebSocket TUI connection** | TUI submits via SDK (poll), not WebSocket. WebSocket endpoint exists but TUI doesn't use it. |

## What Needs to Be Done — In Priority Order

### P0: Wire Memory Into the Agent (2-3 hours)
The agent can't use memories because they're passed in a format it doesn't understand.

**The problem:**
```python
# session.py:92 — context is built correctly
state = {"message": user_message, "context": context}

# session.py:97 — but agent.invoke() gets this as-is
result = self.agent(state)

# agent.py:108 — deepagents.invoke() expects messages=[...], not context=
return self._inner.invoke(*args, **kwargs)
```

**The fix:** Inject memory context into the system prompt or as a synthetic user message before calling the agent:
```python
# In session.send(), build the full prompt:
memory_context = self.hybrid_memory.get_memory_context(user_message)
if memory_context:
    # Prepend to system prompt or inject as first message
    system_prompt = f"{base_system_prompt}\n\n{memory_context}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
else:
    messages = [{"role": "user", "content": user_message}]

result = self.agent.invoke({"messages": messages, ...})
```

### P1: Async Embedding for Indexing (1-2 hours)
Stored vectors use hash embeddings; query vectors use Gemini. This means semantic search is asymmetric.

**The fix:** Make `index_file()` async and use the full embedding chain:
```python
async def index_file(self, relative_path: str):
    ...
    for chunk in chunks:
        vec = await self.embedder.embed(chunk["content"])  # Gemini/local
        vec_blob = _vec_to_blob(vec)
        ...

# Call from remember() with await
async def remember(self, ...):
    ...
    await self.index.index_file(rel_path)
```

### P2: Compaction in Agent Loop (2-3 hours)
Without compaction, sessions die at ~200K tokens.

**The fix:** Hook `CompactionPipeline` into the agent's message processing:
```python
# Before each model call:
if self.compaction.should_compact(messages):
    # 1. Pre-compaction flush to memory files
    await self.pre_compaction_flush(session_summary)
    # 2. Compact messages
    messages = self.compaction.compact(messages)
```

### P3: WebSocket TUI (3-4 hours)
Current TUI polls the SDK. Should use WebSocket for real-time streaming.

### P4: Session Management CLI (1-2 hours)
`nexus session list/resume/fork/rename/delete` commands.

### P5: Sub-Agent Improvements (2-3 hours)
Summary-only returns, per-agent model selection, max depth control, worktree isolation.

## Recommended Order

1. **P0: Wire memory into agent** — without this, memories are written but never used
2. **P1: Async embedding for indexing** — without this, semantic search quality is poor
3. **P2: Compaction in agent loop** — without this, long sessions are impossible
4. **P3-P5: Polish** — TUI, CLI, sub-agents

Total: ~12-17 hours of focused work to reach Claude Code feature parity on the core loop.
