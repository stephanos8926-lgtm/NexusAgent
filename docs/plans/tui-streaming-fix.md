# Implementation Plan: TUI Real Streaming Architecture Fix

> Spec: `docs/specs/tui-streaming-fix.md`
> Date: 2026-07-19

## Phase 1: Session Streaming (core/session.py) — CRITICAL

**Scope**: Replace `invoke()` with `astream()`, wire `_handle_message_token()`

### 1.1 — Add `astream()` method to Session

Add new method that wraps the agent's `astream()`:

```python
async def astream(self, user_message: str, images: list[str] | None = None) -> None:
    """Stream a user message through the agent, emitting events per token."""
    # ... same setup as send() (prompt building, compaction, etc.)
    # Replace: result = self.agent({"messages": messages})
    # With:    async for chunk in self.agent.astream({"messages"}, ...):
    #              await self._handle_message_token(chunk, {}, accumulated)
```

Key change: `session.py:408` — the single `invoke()` call becomes an `async for` loop.

### 1.2 — Wire `_handle_message_token` to `astream_events`

The existing `_handle_message_token()` (line 456) processes `AIMessageChunk` and `ToolMessage` — this is already correct. But it needs to be called from the `astream` loop.

Also wire `_handle_update()` (line 523) for node-level progress.

### 1.3 — Keep `send()` as sync wrapper, add `astream()` as new primary

For backward compatibility, `send()` stays but delegates to `astream()` internally. The WebSocket handler calls `session.send()` — no change needed on the server side.

Files changed:
- `core/session.py` — add `astream()` method, modify `send()` to use it
- Tests: `tests/test_session_streaming.py` — new test file

### 1.4 — Test plan

```python
# tests/test_session_streaming.py
# - Mock agent.astream() to yield fake AIMessageChunks
# - Verify _handle_message_token emits response_chunk events
# - Verify tool_call events emitted for tool_call_chunks
# - Verify final response event still emitted
```

## Phase 2: TUI Split (interfaces/tui.py) — MEDIUM

**Scope**: Split 810-line `tui.py` into `interfaces/tui/` subpackage

### 2.1 — New structure

```
interfaces/tui/
├── __init__.py          # Re-exports NexusApp + all widgets (compat)
├── app.py               # NexusApp class (~300 lines: lifecycle, routing)
├── screens/
│   ├── __init__.py
│   └── main_screen.py   # Chat view + input composition
├── output/
│   ├── __init__.py
│   ├── streaming.py     # Token handler, event→widget routing
│   └── formatter.py     # Tool output formatting (from tui_formatters.py)
└── commands/
    ├── __init__.py
    └── slash_commands.py # _handle_slash_command split into handlers
```

### 2.2 — Old file becomes compat shim

`interfaces/tui.py` → `from nexusagent.interfaces.tui import *`

All existing tests import from `tui.py` — must keep working.

### 2.3 — Files changed

- `interfaces/tui/__init__.py` — new
- `interfaces/tui/app.py` — extracted from tui.py
- `interfaces/tui/screens/main_screen.py` — extracted compose() + chat logic
- `interfaces/tui/output/streaming.py` — extracted _handle_event() + token routing
- `interfaces/tui/output/formatter.py` — from tui_formatters.py
- `interfaces/tui/commands/slash_commands.py` — extracted slash handlers
- `interfaces/tui.py` — compat shim (re-exports)

## Phase 3: Tool Registration Refactor — LOW

**Scope**: `tools/register_all.py` (728 lines) → self-describing tools

### 3.1 — Pattern

Each tool module exports:
```python
TOOL_INFO = ToolInfo(name="read_file", category="fs", description="...", func=read_file)
```

`register_all.py` becomes a scanner that discovers `TOOL_INFO` from each module.

### 3.2 — Files changed

- Each `tools/*.py` — add `TOOL_INFO` export
- `tools/register_all.py` → scanner pattern
- Tests: verify all tools still registered

## Execution Order

| Phase | Files | Risk | Est. Time |
|-------|-------|------|-----------|
| 1 | session.py + tests | MEDIUM | 2-3 hours |
| 2 | tui.py split + tests | HIGH | 3-4 hours |
| 3 | register_all.py | LOW | 1-2 hours |

**Total: ~6-9 hours across 2-3 sessions**

## Rollback Plan

Each phase = one commit:
- `feat(session): add astream() for real token streaming`
- `refactor(tui): split tui.py into focused subpackage`
- `refactor(tools): self-describing tool registration`

If any phase breaks: `git revert HEAD` → back to clean state.
