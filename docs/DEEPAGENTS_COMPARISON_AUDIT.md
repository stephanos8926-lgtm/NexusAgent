# DeepAgents vs NexusAgent — Detailed Comparison for Audit

**Date:** 2026-07-23  
**Purpose:** Reference comparison for external audit

---

## DeepAgents Architecture (v0.6.8)

### Core Graph Construction (`create_deep_agent`)

```python
# Key middleware stack (in order):
1. TodoListMiddleware           # Todo list tool
2. SkillsMiddleware             # If skills provided
3. FilesystemMiddleware         # File tools + permissions (REQUIRED)
4. SubAgentMiddleware           # Synchronous subagents via `task` tool (REQUIRED)
5. SummarizationMiddleware      # Context compression
6. PatchToolCallsMiddleware     # Tool call patching
7. AsyncSubAgentMiddleware      # Async subagents (if provided)
# User middleware inserted here
8. HarnessProfile.extra_middleware
9. _ToolExclusionMiddleware     # If profile has excluded_tools
10. AnthropicPromptCachingMiddleware  # Always (no-op for non-Anthropic)
11. MemoryMiddleware            # If memory paths provided
12. HumanInTheLoopMiddleware    # If interrupt_on provided
```

### State Schema
```python
class DeepAgentState(AgentState):
    messages: DeltaChannel(_messages_delta_reducer, snapshot_frequency=50)
    # DeltaChannel reduces checkpoint growth from O(N²) to O(N)
```

### Key Features
| Feature | Implementation |
|---------|---------------|
| **Subagents** | In-process via `SubAgentMiddleware` — `task` tool calls compiled subagent graph |
| **Async Subagents** | Background tasks via `AsyncSubAgentMiddleware` — `launch_task`, `check_task`, etc. |
| **Filesystem** | `FilesystemMiddleware` wraps all file tools, enforces `FilesystemPermission` rules |
| **Human-in-loop** | `HumanInTheLoopMiddleware` + `interrupt_on` config |
| **Memory** | `MemoryMiddleware` loads AGENTS.md files into system prompt |
| **Streaming** | `astream()` with `stream_mode="messages"` yields `(token, metadata)` tuples |
| **Checkpointing** | LangGraph `Checkpointer` (SQLite, Postgres, etc.) |
| **Backend** | Pluggable `BackendProtocol` — `StateBackend` (default), `FilesystemBackend`, `SandboxBackend` |

---

## NexusAgent Architecture

### Client-Server Split
| DeepAgents (Library) | NexusAgent (Platform) |
|---------------------|----------------------|
| In-process graph | Server (FastAPI) + Clients (TUI, CLI, Web, SDK) |
| `create_deep_agent()` per use | One `Agent` per WebSocket session |
| Single user | Multi-user, multi-session |
| No auth | API key + token exchange |
| No persistence | SQLite + NATS KV + JetStream |
| In-process subagents | NATS-based `WorkerPool` (distributed) |

### Agent Creation Paths

**Path 1: TUI WebSocket Session** (`websocket.py:88`)
```python
agent = Agent(role="full", policy="permissive")  # In-process, async
# Session.send() uses agent.astream() — fully async ✓
```

**Path 2: Worker Pool** (`handler.py:83`)
```python
result = await loop.run_in_executor(None, run_agent_task, state)  # Thread pool!
# run_agent_task creates Agent -> __call__ -> _inner.invoke() — BLOCKING ✗
```

**Path 3: Research Workflow** (`graph.py:242`)
```python
graph = await create_research_graph()  # LangGraph StateGraph
result = await graph.ainvoke(initial_state, config)  # Async ✓
```

---

## Critical Bug: Thread-Local Policy Context (CONFIRMED)

### The Chain
```
WorkerPool.handle_task()
  → handler._run_agent_task()
    → loop.run_in_executor(None, run_agent_task, state)  # Thread pool!
      → agent.py:run_agent_task()
        → Agent(role, policy)
          → set_policy_context(role, policy)  # contextvars.ContextVar.set()
        → agent(agent_state)
          → _inner.invoke()  # BLOCKING call
```

### The Problem
1. `contextvars.ContextVar` **does not propagate across threads**
2. `run_in_executor` runs on arbitrary thread from thread pool
3. `set_policy_context()` sets contextvar on **executor thread**
4. When `run_agent_task` returns, executor thread context is discarded
5. Any sub-agent spawned would run on **different thread** with wrong/no context

### Evidence: `policy.py` Uses `contextvars` (Correct for Async, Not Threads)
```python
# policy.py:16-18 — Uses contextvars (async-safe)
_policy_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "policy_context", default=None
)
```

But `contextvars` **does not work across threads** — each thread has its own context.

### Impact
- **Security boundary violation**: Sub-agents inherit random policy from thread pool
- **Data leakage**: `strict` policy sub-agent could get `permissive` tools
- **Non-deterministic**: Behavior depends on which thread pool thread executes

---

## Other Confirmed Bugs

### 1. SQLite Connection Leak (`graph.py:242-248`)
```python
def create_research_graph():
    conn = sqlite3.connect(":memory:")  # or file
    checkpointer = SqliteSaver(conn)
    # conn never closed!
    return graph
```
Every research task leaks a DB connection.

### 2. Blocking `invoke()` in Async Session (`session.py:397`)
```python
# session.py line ~262 — uses astream() ✓
async for chunk in self.agent.astream({"messages": messages}, stream_mode="messages"):
    ...

# BUT agent.py line 285-287 — __call__ uses blocking invoke()
def __call__(self, *args, **kwargs):
    return self._inner.invoke(*args, **kwargs)

# handler.py line 83 uses run_in_executor + __call__ = blocking in thread
result = await loop.run_in_executor(None, run_agent_task, state)
```

### 3. Unbounded Event Queue (`session.py:197`)
```python
self._event_queue = asyncio.Queue()  # No maxsize
```

### 4. Heartbeat Task Leak (`session.py:249-259`)
```python
asyncio.create_task(_heartbeat())  # Never cancelled on error
```

---

## What NexusAgent Does Better Than DeepAgents

| Feature | NexusAgent | DeepAgents |
|---------|-----------|------------|
| **Multi-client** | TUI, CLI, Web, SDK, Gateway | Single process |
| **Persistent sessions** | DB + memory + NATS | Checkpointer only |
| **Distributed workers** | NATS JetStream + WorkerPool | In-process only |
| **Memory system** | 4-layer hybrid (file+vec+compaction+dream) | Optional MemoryMiddleware |
| **Version negotiation** | `/version` preflight + minClient | None |
| **Workspace isolation** | Path jail + scoped memory | FilesystemPermission only |
| **Dream cycle** | 4-phase consolidation + contradiction detection | None |
| **Provenance tracking** | Git-backed memory with full history | None |

---

## What DeepAgents Does Better

| Feature | DeepAgents | NexusAgent |
|---------|-----------|------------|
| **DeltaChannel state** | Reduces checkpoint O(N²)→O(N) | Custom session state |
| **Middleware architecture** | Composable, typed, extensible | Custom policy enforcement |
| **Human-in-loop** | Built-in middleware + `interrupt_on` | Custom approval events |
| **Subagent isolation** | Compiled subgraphs, explicit state | NATS messages (looser) |
| **Streaming** | Native `astream()` with metadata | Wrapped in WebSocket |
| **Checkpointing** | Pluggable, battle-tested | Manual SQLite + NATS |
| **Permissions model** | Declarative `FilesystemPermission` | Path jail + policy context |

---

## Migration Path Considerations

If NexusAgent wanted to align more with DeepAgents:

1. **Replace `run_in_executor` + `invoke`** → Use `astream`/`ainvoke` directly in worker path
2. **Adopt `DeltaChannel`** for session message state
3. **Use `HumanInTheLoopMiddleware`** for approvals instead of custom WebSocket events
4. **Use LangGraph checkpointer** instead of manual SQLite + NATS KV
5. **Adopt `FilesystemMiddleware` + `FilesystemPermission`** for path jail
6. **Consider `AsyncSubAgentMiddleware`** for distributed workers (but NATS is more robust)

---

## Summary for Audit

**NexusAgent is a platform built on top of DeepAgents**, not a fork. It adds:
- Client-server architecture (WebSocket + REST)
- Multi-session persistence
- Distributed task orchestration (NATS)
- Advanced memory system (4-layer with dream cycle)
- Multi-client support (TUI, CLI, Web, SDK, Telegram/Discord gateway)

**Critical bugs exist** in the worker execution path (thread-local context, blocking calls, connection leaks) but **the TUI/WebSocket path is clean** (uses `astream` directly).

**DeepAgents provides solid primitives** — NexusAgent's bugs are in how it integrates/wraps them, not in DeepAgents itself.