# Spec: TUI Real Streaming Architecture Fix

> Version: 1.0
> Date: 2026-07-19
> Status: Draft — pending audit

## Problem Statement

The TUI's streaming is **fake**. Tokens are not streamed in real-time:

1. **`core/session.py:408`** — `session.send()` calls `self.agent({"messages": messages})` using **sync `invoke()`**, which blocks until the full response is complete
2. **`_handle_message_token()` and `_handle_update()`** exist but are **dead code** — never called
3. The TUI only receives a single `response` event containing the complete output — no `response_chunk` events
4. **Word wrapping**: `text-wrap: wrap` CSS is set on widgets but `Content` (plain Textual content) does not wrap — Rich renderable wrapping only works with Rich's own rendering, not CSS
5. **Tool calls**: `ToolCallMessage` renders formatted (this works in `tool.py` Raw), but `_format_args()` re-serializes pretty-printed JSON back to string, losing structure

## Goals

| ID | Goal | Priority |
|----|------|----------|
| G1 | Replace `invoke()` with `astream()` for real token-by-token streaming | CRITICAL |
| G2 | Wire `_handle_message_token()` into `astream_events()` callback | CRITICAL |
| G3 | Fix word wrapping in AssistantMessage/ToolCallMessage | HIGH |
| G4 | Split `interfaces/tui.py` into focused subpackage (screens/output/commands) | MEDIUM |
| G5 | `tools/register_all.py` → self-describing tools pattern | LOW |

## Compatibility Rules

- All existing imports from `interfaces/tui.py` must still work (compat shim)
- All existing imports from `core/session.py` must still work
- Test baseline: 595 pass / 3 fail — zero regressions
- WebSocket protocol: add `response_chunk` events, keep `response` events (backward compat)

## File Manifest

| File | Change |
|------|--------|
| `core/session.py` | Replace `invoke()` with `astream()` + wire `_handle_message_token()` to callback |
| `interfaces/tui.py` | Split to `interfaces/tui/` subpackage (app/formatter/screens/commands) |
| `interfaces/tui.py` (compat shim) | Re-export from subpackage |
| `widgets/messages/assistant.py` | Verify `append_token()` works with real streaming |
| `widgets/messages/tool.py` | Keep current formatting, verify JSON args display |
| `server/server.py` | Verify WebSocket handler still works with new event types |
| `tests/test_tui_streaming.py` | New — streaming behavior tests |
| `tests/test_session_streaming.py` | New — astream + event emission tests |

## Acceptance Criteria

- [ ] Agent uses `astream()` instead of `invoke()`
- [ ] `_handle_message_token()` is called per token chunk
- [ ] TUI receives `response_chunk` events (not just `response`)
- [ ] `AssistantMessage.append_token()` is called per chunk in TUI
- [ ] Tokens appear one-by-one in TUI (not batch dump)
- [ ] `response` event still sent at end (backward compat)
- [ ] Word wrapping works for lines > terminal width
- [ ] `test_tui_streaming.py` passes (mock stream → verify per-token callbacks)
- [ ] `test_session_streaming.py` passes (mock agent → verify event emission)
- [ ] Full test suite: 595+ pass / ≤3 fail (pre-existing e2e only)

## Out of Scope

- MCP tool loading changes
- Memory index refactoring
- Worker pool refactoring
- Theme system changes
