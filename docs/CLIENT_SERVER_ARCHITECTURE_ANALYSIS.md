# NexusAgent Client/Server Architecture Analysis

**Date:** 2026-07-23  
**Status:** Analysis only — no changes made  
**Purpose:** Document findings for external audit

---

## Architecture Overview

NexusAgent uses a **client-server architecture** with three distinct layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENTS (Consumers)                       │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│    TUI      │   CLI       │  Web UI     │  External SDK     │
│ (Textual)   │  (Click)    │  (Gradio)   │  (Python)         │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │             │
       ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    NEXUS SERVER (FastAPI)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ REST API │  │ WebSocket│  │  Auth    │  │ Rate Limit │  │
│  │ /tasks   │  │ /sessions│  │ /auth/   │  │ Middleware │  │
│  │ /health  │  │   /ws    │  │  token   │  │            │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────┘
       │             │
       ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │   NATS     │  │  SQLite    │  │  Worker Pool         │  │
│  │ JetStream  │  │  (Async)   │  │  (Background Tasks)  │  │
│  └────────────┘  └────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Server Components (src/nexusagent/server/)

| File | Responsibility | Key Details |
|------|---------------|-------------|
| `server.py` | FastAPI app factory, lifespan, uvicorn entry | Creates app, registers routes + WS endpoint, starts worker |
| `routes.py` | REST endpoints + rate limiting middleware | `/tasks`, `/health`, `/version`, `/workers`, `/tools`, `/auth/token` |
| `websocket.py` | Interactive session WebSocket handler | Auth, session creation, event streaming, message dispatch |
| `sdk.py` | High-level NATS client for task submission | `submit_task`, `get_result`, `wait_for_result`, `health_check` |
| `version.py` | Version constants via importlib.metadata | `VERSION`, `MIN_CLIENT_VERSION`, `SERVER_VERSION` |

---

## Client Components

| Client | Entry Point | Key Files |
|--------|------------|-----------|
| **TUI** | `nexusagent.tui:main` | `interfaces/tui/app.py`, `websocket.py`, `streaming.py`, `input.py` |
| **CLI** | `nexusagent.cli:main` | `interfaces/cli.py` |
| **Web UI** | `nexusagent.web_ui:run_ui` | `interfaces/web_ui.py` (Gradio) |
| **SDK** | `nexusagent.server.sdk` | `server/sdk.py` |

---

## Communication Protocols

### WebSocket Protocol (TUI ↔ Server)

**Connection:** `ws://127.0.0.1:8000/sessions/{session_id}/ws?working_dir=...`

**Auth:** `Authorization: Bearer <api_key>` header or `?token=<token>` query param

**Event Types (Server → Client):**
| Event | Purpose | Handled By |
|-------|---------|------------|
| `session_status` | Session state (active/idle/closed) | - |
| `thinking` | "Still thinking..." heartbeat | TUI shows 💭 message |
| `tool_call` | Agent invoked a tool | TUI shows running ToolCallMessage |
| `tool_result` | Tool completed | TUI updates ToolCallMessage output |
| `tool_error` | Tool failed | TUI shows ErrorMessage |
| `approval_request` | Needs user approval | TUI shows ApprovalModal |
| `response_chunk` | Streaming token | TUI appends to AssistantMessage |
| `response` | Final response | TUI finalizes AssistantMessage |
| `error` | Agent error | TUI shows ErrorMessage |
| `session_closed` | Session ended | TUI updates status |
| `session_list` | List sessions response | TUI shows session list |
| `compact_result` | Compaction result | TUI shows status |

**Event Types (Client → Server):**
| Event | Purpose |
|-------|---------|
| `user_input` | User message (content + optional images) |
| `approval` | Approval decision (call_id + approved) |
| `interrupt` | Cancel current agent run |
| `list_sessions` | Request session list |
| `compact` | Trigger context compaction |
| `close` | Close session |

---

## Session Flow (WebSocket)

```
TUI                          SERVER (websocket.py)
  │                              │
  ├── ws://.../ws (connect) ───► │
  │         [Auth check]         │
  │         [Origin check]       │
  │         [Accept]             │
  │ ◄─── session_status ─────────│
  │                              │
  ├── user_input ───────────────► │ session.send(content)
  │                              │   │
  │                              │   ▼ (Agent.astream)
  │ ◄─── thinking (heartbeat) ────│
  │ ◄─── tool_call ──────────────│
  │ ◄─── tool_result ────────────│
  │ ◄─── response_chunk (stream) │
  │ ◄─── response (final) ───────│
  │                              │
  ├── approval (if needed) ─────► │ session.approve()
  │                              │
  ├── interrupt (if needed) ────► │ session.interrupt()
```

---

## Key Differences from DeepAgents Reference

| Aspect | DeepAgents (Library) | NexusAgent (Platform) |
|--------|---------------------|----------------------|
| **Execution** | In-process `create_deep_agent().astream()` | Separate server process, WebSocket |
| **State** | LangGraph `StateGraph` checkpointer | NATS + SQLite persistence |
| **Auth** | None (library) | API key + token exchange |
| **Session** | In-memory | Persistent (DB + memory) |
| **Tools** | Built-in + custom middleware | 25+ registered tools via registry |
| **Subagents** | `task` tool via SubAgentMiddleware | NATS-based `WorkerPool` (distributed) |
| **Memory** | Optional `MemoryMiddleware` | 4-layer hybrid (file+vector+compaction+dream) |
| **Multi-client** | Single process | Multiple clients (TUI, CLI, Web, SDK) |

---

## Critical Architecture Decisions

1. **Server runs WorkerPool** — `NexusWorker` starts in FastAPI lifespan (line 43-46 of server.py)
2. **SessionManager is global singleton** — manages all interactive sessions
3. **WebSocket creates real Agent per connection** — `Agent(role="full", policy="permissive")` (websocket.py:88)
4. **Workspace-scoped memory** — via `working_dir` query param → `.nexusagent/memory` directory
5. **Version preflight** — TUI checks `/version` before WS connect (warn-only on mismatch)
6. **Token exchange for browsers** — `/auth/token` returns API key as short-lived token