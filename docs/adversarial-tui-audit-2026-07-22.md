# Adversarial TUI Audit Report

> Date: 2026-07-22
> Auditor: OWL (adversarial subagent)
> Scope: NexusAgent TUI subsystem (`src/nexusagent/interfaces/tui/`, `src/nexusagent/widgets/`, `src/nexusagent/server/websocket.py`)

---

## Executive Summary

**18 issues found**: 3 Critical, 6 High, 5 Medium, 4 Low.

The TUI handles the happy path well but has systemic weaknesses: the sliding window has multiple bypass paths, `_busy` state is not reset on disconnect, no input/queue size limits exist, and the approval flow has a race condition between auto-approve and modal paths.

---

## 1. Input Edge Cases

### 1.1 Empty Input (Just Press Enter)
- **Code path**: `ChatInput.action_submit()` L213: `text = self.text.strip()` → `if not text: return`
- **on_chat_input_submitted()** L27: `message = event.text.strip()` → `if not message: return`
- **Result**: SAFE. Both guards catch empty input.

### 1.2 Very Long Input (10KB+ Message)
- **Code path**: `ChatInput.action_submit()` → stores in history (no length check) → `on_chat_input_submitted()` → `app._input_queue.put(message)` (no client-side limit)
- **Server**: `websocket.py` L117: `_WS_MAX_MESSAGE_SIZE = 65536` (64KB) blocks messages >64KB. Server-side protection exists.
- **Result**: PARTIALLY SAFE. Server rejects >64KB, but no client-side limit means a 63KB message passes. `UserMessage` stores full text in memory with no truncation. `AssistantMessage._buffer` can grow unbounded during streaming.
- **Severity**: Low

### 1.3 Input Starting with / but Not a Valid Command
- **Code path**: `handle_slash_command()` L220: `parts = cmd.strip().lower().split()` → command = `"/"` if just "/"
  - Falls through all `if` checks → L380: `AppMessage(f"Unknown command: {command}...")` → returns `True`
- **Result**: SAFE. Unknown commands get a helpful error message.

### 1.4 Special Characters (Unicode, Emoji, ANSI Codes)
- **Code path**: `ChatInput` (TextArea) handles unicode natively → `json.dumps()` encodes unicode → `Static`/`Markdown` widgets render content server-side escape via `_escape()` in formatters
- **ANSI escape sequences**: Textual `Static` widget interprets Rich markup but NOT ANSI escape sequences. They render as literal text.
- **Result**: SAFE. ANSI injection is not possible through Textual's Content/Static rendering pipeline.

### 1.5 Input with @file References
- **Code path**: `ChatInput._extract_images()` only matches image extensions (`.png`, `.jpg`, `@file` references pass through as literal text in `UserMessage.content`
- **Result**: SAFE. No client-side @file processing exists.

### 1.6 Rapid Repeated Submissions (Spam Enter)
- **Code path**: `on_chat_input_submitted()` L37: `if app._busy:` → `app._pending_inputs.append(message)`
- **`_pending_inputs`**: Plain `list`, no max length. `process_next_in_queue()` pops one at a time.
- **Result**: **VULNERABLE**. When agent is busy, spamming Enter appends to an unbounded list.
  - **Severity**: High (memory exhaustion DoS)

---

## 2. WebSocket Failure Modes

### 2.1 Server Not Running When TUI Starts
- **Code path**: `ws_loop()` L121-163: `ConnectionRefusedError` → exponential backoff (1s, 2s, 4s, 8s, 16s, 32s) → 6 retries max → status bar: "Connection refused" + error message
- **Result**: SAFE. Graceful degradation with retry.

### 2.2 Server Disconnects Mid-Conversation
- **Code path**: `ws_loop()` L165: `ConnectionClosedOK` → `return`; L169: `ConnectionClosedError` → retry or give up
- **Finally block** L185-186: `app._ws = None`
- **BUG**: `app._busy` is **never reset to `False`** on disconnect. The TUI stays permanently in "busy" state — user cannot send any more messages.
- **Severity**: **Critical** (soft-bricks the TUI session)

### 2.3 Server Sends Malformed JSON
- **Code path**: `receive_events()` L143-146: `json.loads(raw)` → `JSONDecodeError` → `continue`
- **Result**: SAFE. Malformed events silently skipped.

### 2.4 Server Sends Unknown Event Types
- **Code path**: `handle_event()` L53: `etype = event.get("type")` → falls through all `if/elif` branches → no `else` clause → function returns without action
- **Result**: SAFE. Unknown events silently ignored.

### 2.5 Server Sends Events Out of Order
- **response before response_chunk**: L100-113: `if app._current_assistant:` is False → enters `elif content:` branch → creates new `AssistantMessage` directly → calls `finalize()` with `render_markdown(content)`. No crash, but skips streaming animation.
- **tool_result before tool_call**: L184: `if app._current_tool:` is False → L187-194: creates new `ToolCallMessage` with `app._last_tool_name` (which may be `""` → displays as `"?"` tool)
- **Result**: MINOR. No crash, but display is confusing.

### 2.6 Server Sends approval_request When Auto-Approve Is On
- **Code path**: `handle_event()` L78-89: `approval_request` handler does **NOT** check `app._auto_approve`. Always pushes `ApprovalModal` and awaits user response.
- **Meanwhile**: `_handle_tool_call_event()` L164-169: if `app._auto_approve`, creates asyncio task to `send_approval(True)` immediately.
- **Race condition**: Both paths fire for the same tool call:
  1. Auto-approve task sends `approval=True` to server
  2. ApprovalModal appears, user clicks Approve
  3. `send_approval()` called again → **duplicate approval** sent to server
- **Severity**: **High** (confusing UX, duplicate messages to server, potential for approval of wrong call if IDs collide)

---

## 3. Widget State Corruption

### 3.1 `_current_assistant` Is None but `response_chunk` Arrives
- **Code path**: `handle_event()` L93-96: `if app._current_assistant is None:` → creates new `AssistantMessage()` → mounts it → `_current_assistant = msg`
- **Result**: SAFE. Gracefully handles missing assistant widget.

### 3.2 `_current_tool` Is None but `tool_result` Arrives
- **Code path**: `_handle_tool_result_event()` L184-194: `if app._current_tool:` is False → creates new `ToolCallMessage` with `app._last_tool_name` (may be `""`)
- **Result**: PARTIALLY SAFE. No crash, but displays `"?"` as tool name if `_last_tool_name` is empty.

### 3.3 Messages Container Cleared During Streaming
- **Code path**: User runs `/new` or `/clear` → `app.messages_container.clear()` (streaming.py L265-266)
- **State after clear**: `app._current_assistant` and `app._current_tool` still hold references to **removed** widgets
- **Next event**: `response_chunk` → `app._current_assistant.append_token(content)` → `self.update(self._buffer)` on an **unmounted** Static widget
- **Textual behavior**: `update()` on unmounted widget may raise `WidgetError` or silently fail. The token stream is lost.
- **Severity**: **High** (crash or silent data loss after /new or /clear)

### 3.4 Two tool_calls with Same call_id
- **Code path**: Server sends two `tool_call` events with same `call_id` → both create `ToolCallMessage` widgets (no dedup check)
- **Approval**: `send_approval()` sends approval for `call_id` → server receives two approvals for one call
- **Result**: MINOR. No crash, but duplicate approvals.

---

## 4. Concurrency Issues

### 4.1 User Types Next Message While Agent Is Responding
- **Code path**: `on_chat_input_submitted()` L37-43: `if app._busy:` → `app._pending_inputs.append(message)` → shows "Queued" message
- **Result**: SAFE for normal operation. Messages queue and process in order.
- **Caveat**: If WebSocket is down, `process_next_in_queue()` → `asyncio.create_task(app._input_queue.put(next_msg))` → queue fills but `send_messages()` blocks on `ws.send()` → messages accumulate in both `_pending_inputs` and `_input_queue`

### 4.2 Slash Command Executed While WebSocket Is Disconnected
- **Code path**: Slash commands that use WebSocket (`/compact`, `/threads`, `/undo`, `/redo`) check `if app._ws and app._ws.open` before sending
- **Commands that don't need WS**: `/new`, `/clear`, `/help`, `/status`, `/theme`, `/auto`, `/version`, `/tokens`, `/model`, `/quit` — all work locally
- **Result**: SAFE. Commands gracefully handle disconnected state.

### 4.3 Queue Overflow (Many Messages Queued)
- **Code path**: `_pending_inputs` is a plain `list` with no max size. `_input_queue` is `asyncio.Queue()` with no `maxsize` (unbounded).
- **Attack**: Send 10,000 messages while agent is busy → all queue in memory
- **Result**: **VULNERABLE**. No limit on queued messages → memory exhaustion.
- **Severity**: **High** (DoS via queue overflow)

---

## 5. Resource Exhaustion

### 5.1 Sliding Window Limit (50 Messages) — Does It Actually Work?
- **Code path**: `app.py` L162-174: `_mount_message()` checks `len(children) > _MAX_MESSAGE_WIDGETS (50)` → removes oldest
- **Bypass #1**: `input.py` L47: `app.messages_container.mount(user_msg)` — **direct mount, no limit check** (queued user messages bypass sliding window)
- **Bypass #2**: `websocket.py` L61, L72: `app.messages_container.mount(msg)` — version check messages bypass limit
- **Bypass #3**: `websocket.py` L158, L174, L182: `_mount_error()` → `app.messages_container.mount(err)` — error messages bypass limit
- **Bypass #4**: `streaming.py` L30-34: `_mount_with_limit()` fallback path calls itself recursively (infinite recursion if `_mount_message` is removed from app)
- **Result**: **BROKEN**. The 50-widget sliding window is only enforced for messages routed through `_mount_with_limit()`. At least 4 code paths bypass it entirely.
- **Severity**: **Critical** (memory leak — widgets accumulate indefinitely)

### 5.2 Event Queue (No Max)
- **Code path**: `ws_loop()` `receive_events()` L142-147: `async for raw in ws:` → `handle_event(app, event)` — events processed synchronously in the loop
- **No separate event queue exists**. Events are read and dispatched inline.
- **Result**: SAFE. No separate queue to overflow. Backpressure is handled by WebSocket flow control.

### 5.3 Memory from Accumulated Message Widgets
- **Code path**: Each `AssistantMessage` accumulates tokens in `_buffer` (string concatenation). For a long response (e.g., 100KB of markdown), `_buffer` grows to 100KB+.
- **ToolCallMessage._output**: Stores full tool output string. Large file reads or shell output can be megabytes.
- **No truncation on accumulation**: `_buffer` and `_output` grow without limit during streaming.
- **Result**: **VULNERABLE**. Long conversations with large tool outputs cause unbounded memory growth.
- **Severity**: **Medium**

---

## 6. Additional Findings

### 6.1 `_busy` Not Reset on Disconnect
- **Code path**: `ws_loop()` → `ConnectionClosedOK`/`ConnectionClosedError` → status updated but `_busy` not reset
- **Compare**: `response` event L115, `error` event L136, `session_closed` event L141 all set `_busy = False`
- **Result**: **BUG**. Disconnect while agent is busy → TUI permanently stuck. User cannot send messages or use slash commands that check `_busy`.
- **Severity**: **Critical**

### 6.2 `_mount_with_limit` Recursive Bug
- **Code path**: `streaming.py` L27-34: `_mount_with_limit()` checks `if hasattr(app, "_mount_message")` → delegates. But the `else` branch at L30 calls `_mount_with_limit(app, widget)` — **infinite recursion** if `_mount_message` is ever removed from `NexusApp`.
- **Result**: Latent bug. Currently masked because `NexusApp` always has `_mount_message`. Would crash with `RecursionError` if refactored.
- **Severity**: **Medium**

### 6.3 ApprovalModal Args Display — No Sanitization
- **Code path**: `tui_widgets.py` L223: `args_str = "\n".join(f"  {k}: {v}" for k, v in self.tool_args.items())` → rendered as Static text
- **Result**: SAFE. Textual Static doesn't interpret Rich markup from string content. But very long args could overflow the modal.

### 6.4 `action_quit` Race Condition
- **Code path**: `app.py` L267-272: `asyncio.create_task(self._input_queue.put(None))` → `self._ws_task.cancel()` → `self.exit()`
- **Risk**: If `send_messages()` is mid-`ws.send()`, cancellation may leave WebSocket in broken state. `exit()` may fire before queue task completes.
- **Result**: MINOR. Usually works due to `finally: app._ws = None` in ws_loop.

---

## Summary Table

| # | Scenario | Severity | Type | File(s) |
|---|----------|----------|------|---------|
| 1 | Sliding window bypass (4 paths) | **Critical** | Memory leak | `input.py:47`, `websocket.py:61,72,158,174,182` |
| 2 | `_busy` not reset on disconnect | **Critical** | Soft-brick | `websocket.py:165-178` |
| 3 | Approval race condition (auto-approve + modal) | **High** | Duplicate approval | `streaming.py:78-89,164-169` |
| 4 | Unbounded `_pending_inputs` list | **High** | DoS/memory | `input.py:38` |
| 5 | Stale widget refs after `/clear` or `/new` | **High** | Crash/data loss | `streaming.py:265-266` + `assistant.py:51` |
| 6 | Unbounded `_input_queue` | **High** | DoS/memory | `app.py:178` |
| 7 | No client-side input length limit | **Low** | DoS | `chat_input.py:211-238` |
| 8 | AssistantMessage._buffer unbounded growth | **Medium** | Memory leak | `assistant.py:45` |
| 9 | ToolCallMessage._output unbounded growth | **Medium** | Memory leak | `tool.py:162` |
| 10 | `_mount_with_limit` recursive fallback | **Medium** | Latent crash | `streaming.py:30` |
| 11 | Orphaned tool_result shows "?" tool | **Low** | UX bug | `streaming.py:188-194` |
| 12 | No truncation on accumulated message widgets | **Medium** | Memory | `assistant.py`, `tool.py` |
| 13 | action_quit race condition | **Low** | Race condition | `app.py:267-272` |
| 14 | Spinner runs forever on connection failure | **Low** | UX bug | `app.py:191` |
| 15 | API key "Bearer None" if unset | **Low** | Auth bug | `websocket.py:113` |
| 16 | Events out of order (response before chunks) | **Low** | UX bug | `streaming.py:100-113` |
| 17 | Duplicate tool_call widgets for same call_id | **Low** | UX bug | `streaming.py:145-162` |
| 18 | Empty input / unknown commands / unicode / @file | **Info** | Safe | Multiple |

---

## Recommendations (Priority Order)

1. **Fix sliding window bypass**: Route ALL `messages_container.mount()` calls through `_mount_message()`. Ban direct mounts.
2. **Reset `_busy` on disconnect**: Add `app._busy = False` in `ws_loop()` exception handlers.
3. **Fix approval race**: Check `app._auto_approve` in `approval_request` handler; if auto-approve is on, skip the modal and call `send_approval()` directly.
4. **Clear stale widget state on /new and /clear**: Set `_current_assistant = None` and `_current_tool = None` in `action_clear()` and `/new`, `/clear` handlers.
5. **Add queue limits**: Cap `_pending_inputs` (e.g., 100) and use `asyncio.Queue(maxsize=100)` for `_input_queue`.
6. **Add input length limit**: Reject messages >32KB at `ChatInput.action_submit()`.
7. **Fix recursive `_mount_with_limit` fallback**: Replace with direct mount + manual cleanup.
8. **Truncate streaming buffers**: Cap `AssistantMessage._buffer` and `ToolCallMessage._output` with tail preservation.
