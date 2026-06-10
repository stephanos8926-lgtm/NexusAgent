# NexusAgent TUI & Frontend Layer — Semantic Codebase Map

> Generated: 2026-06-10
> Scope: `src/nexusagent/tui.py` (1168 lines), `src/nexusagent/cli.py` (198 lines), `src/nexusagent/web_ui.py` (90 lines)

---

## 1. File-Level Overview

| File | Lines | Purpose | Framework |
|------|-------|---------|-----------|
| `tui.py` | 1168 | Full terminal UI — real-time streaming chat with tool display, modals, slash commands, themes | Textual (TUI framework) |
| `cli.py` | 198 | Click-based CLI for task submission, worker spawning, session management | Click + asyncio |
| `web_ui.py` | 90 | Gradio-based web dashboard for task submission | Gradio |

---

## 2. tui.py — Complete Component Inventory

### 2.1 Imports & Dependencies

**Standard library:** `asyncio`, `contextlib`, `json`, `re`, `textwrap`, `uuid`, `datetime`, `typing.ClassVar`
**Third-party:** `websockets`, `textual` (App, Binding, containers, reactive, screen, timer, widgets)
**Internal:** `nexusagent.config.settings`

### 2.2 Color Themes (`NEXUS_THEMES`)

A list of 5 theme dicts, cycled via `/theme`:

| Index | Name | Header BG | Accent | Background |
|-------|------|-----------|--------|------------|
| 0 | `midnight` | `#1f2937` | `#10b981` (emerald) | `#111827` |
| 1 | `ocean` | `#0e4d6e` | `#38bdf8` (sky) | `#0c1929` |
| 2 | `forest` | `#14532d` | `#4ade80` (green) | `#052e16` |
| 3 | `sunset` | `#7c2d12` | `#fb923c` (orange) | `#1c1010` |
| 4 | `lavender` | `#3b3864` | `#a78bfa` (violet) | `#1a1830` |

Theme application is **partial** — only `background`, `header_bg`, and `header.color` are updated at runtime via `_apply_theme()`. The CSS string is static and does not change.

---

### 2.3 Widget Classes

#### `SpinnerLabel` (lines 60–108)
- **Inherits:** `Horizontal` (Textual container)
- **Purpose:** Animated spinner + text label for the status bar
- **Reactive property:** `tick` (int) — drives spinner animation
- **Spinner chars:** `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` (braille dots, 10 frames)
- **Timer interval:** 0.1s (10 FPS)
- **Composed children:**
  - `Static("", id="spinner-icon")` — spinner character
  - `Static("", id="spinner-text")` — status text
- **Key methods:**
  - `set_text(text, spinning)` — starts/stops timer, updates display
  - `_tick_spinner()` — increments `tick`
  - `watch_tick()` — reactive watcher, calls `update_display()`
  - `update_display()` — renders current spinner frame + text
  - `on_unmount()` — stops timer

#### `ApprovalModal` (lines 115–137)
- **Inherits:** `ModalScreen[bool]`
- **Purpose:** Tool call approval dialog
- **Constructor params:** `tool_name: str`, `tool_args: dict`, `call_id: str`
- **Composed children:**
  - `Vertical#approval-dialog`
    - `Static` — title: `"⚡ Approval Required: {tool_name}"`
    - `ScrollableContainer#approval-scroll` (max-height: 12)
      - `Static#approval-args` — key-value pairs of tool args
    - `Horizontal#approval-buttons`
      - `Button("✓ Approve", id="approve", variant="success")`
      - `Button("✗ Reject", id="reject", variant="error")`
      - `Button("Cancel", id="cancel")`
- **Event handler:**
  - `on_button_pressed` → `dismiss(True)` for approve, `dismiss(False)` for reject/cancel

#### `ErrorModal` (lines 144–159)
- **Inherits:** `ModalScreen[None]`
- **Purpose:** Error display dialog
- **Constructor params:** `error_message: str`
- **Composed children:**
  - `Vertical#approval-dialog` (reuses approval dialog CSS IDs)
    - `Static` — title: `"⚠ Error"`
    - `Static#approval-args` — error message
    - `Horizontal#approval-buttons`
      - `Button("OK", id="ok", variant="primary")`
- **Event handler:**
  - `on_button_pressed` → `dismiss(None)`

#### `NexusApp` (lines 166–1159)
- **Inherits:** `App` (Textual base application)
- **Purpose:** Main TUI application — the entire chat interface

---

### 2.4 Keyboard Bindings (`NexusApp.BINDINGS`)

| Key | Action | Label | Shown in Footer | Priority |
|-----|--------|-------|-----------------|----------|
| `q` | `action_quit` | Quit | Yes | True |
| `escape` | `action_quit` | Quit | No | True |
| `c` | `action_clear` | Clear | Yes | — |
| `ctrl+c` | `action_interrupt` | Interrupt | Yes | — |
| `ctrl+u` | `action_interrupt` | Interrupt | Yes | — |
| `e` | `action_expand_all` | Expand | Yes | — |
| `a` | `action_collapse_all` | Collapse | Yes | — |
| `ctrl+underscore` | `action_toggle_auto_approve` | Auto-approve | No | — |

**Note:** `escape` and `q` share the same action. `escape` is hidden from footer. `ctrl+underscore` (Ctrl+Shift+-) is also hidden.

---

### 2.5 CSS Theme (lines 178–318)

Full CSS string with these selectors:

| Selector | Purpose | Key Styles |
|----------|---------|------------|
| `Screen` | Root layer | `layers: base overlay`, `background: #111827` |
| `#log-container` | Conversation scroll area | `width: 100%`, `height: 1fr`, `border: solid #1f2937`, `margin: 0 1` |
| `#conversation-log` | RichLog widget | `text-wrap: wrap`, `word-wrap: break-word`, `overflow-x: hidden`, `padding: 1 2` |
| `#streaming-response` | Live streaming text | `color: #93c5fd`, `border-left: wide #3b82f6`, `background: #1f2937` |
| `#input-area` | Input field | `height: 3`, `border: solid #374151`, focus: `border: solid #10b981` |
| `#status-bar` | Status bar | `height: 1`, `background: #1f2937`, `color: #9ca3af` |
| `#auto-approve-badge` | Auto-approve indicator | `color: #fbbf24`, `text-style: bold` |
| `#queue-status` | Queue indicator | `color: #6b7280`, `text-style: italic` |
| `Collapsible` | Tool result containers | `border-left: wide #fbbf24`, header: `#fbbf24` bold, collapsed: `#6b7280` |
| `#approval-dialog` | Modal dialog | `width: 80%`, `max-height: 20`, `border: solid #fbbf24` |
| `#approval-title` | Modal title | `text-style: bold`, `color: #fbbf24` |
| `#approval-args` | Modal body | `color: #d1d5db` |
| `#approval-buttons` | Modal buttons | `align: right middle` |
| `#approval-scroll` | Modal scroll area | `max-height: 12` |
| `Header` | App header | `background: #1f2937`, `color: #10b981`, `text-style: bold` |
| `Footer` | App footer | `background: #1f2937`, `color: #6b7280` |

---

### 2.6 `NexusApp.compose()` — Widget Tree

```
Header
ScrollableContainer#log-container
  RichLog#conversation-log (markup=True, auto_scroll=True, wrap=True)
Static#streaming-response
SpinnerLabel#status-bar
Static#auto-approve-badge
Static#queue-status
Input#input-area (placeholder="Type a message, @file to inject, or /help for commands...")
Footer
```

---

### 2.7 `NexusApp.on_mount()` — Initialization State

Set up on mount:
- `self.session_id` — 8-char UUID prefix
- Widget references: `log_widget`, `status_widget`, `queue_status`, `_streaming_widget`
- `_streaming_response: str = ""` — accumulated streaming text
- `_input_queue: asyncio.Queue[str | None]` — message queue for WS send
- `_busy: bool = False` — agent busy flag
- `_ws: WebSocketClientProtocol | None` — WebSocket connection
- `_collapsibles: list[Collapsible]` — tracked for expand/collapse
- `_pending_inputs: list[str]` — queued user messages
- `_current_task: asyncio.Task | None` — for interrupt
- `_auto_approve: bool = False`
- `_theme_index: int = 0`
- `_total_tokens_used: int = 0`
- `_request_count: int = 0`

Then calls `_show_greeting()` and starts `_ws_loop()` as asyncio task.

---

### 2.8 Greeting/Welcome Flow (`_show_greeting`)

Writes to `log_widget` (RichLog):
1. Empty line
2. Box top: `╔══════════════════════════════════════════╗`
3. Title: `║  NexusAgent — Interactive AI Agent    ║`
4. Session info: `║  Session: {id}  {HH:MM}              ║`
5. Box bottom: `╚══════════════════════════════════════════╝`
6. Empty line
7. Commands hint: `Commands: /help  /new  /clear  /expand  /collapse  /quit`
8. Keys hint: `Keys: Ctrl+C=interrupt  Q=quit  C=clear  E=expand  A=collapse`
9. Empty line

Uses RichLog markup: `[b cyan]`, `[b white]`, `[yellow]`, `[dim]`.

---

### 2.9 WebSocket Communication (`_ws_loop`)

**Connection URL:** `ws://127.0.0.1:{port}/sessions/{session_id}/ws` (with optional `?api_key=`)

**Two concurrent tasks via `asyncio.gather`:**
1. `send_messages()` — dequeues from `_input_queue`, sends as `{"type": "user_input", "content": msg}`. `None` sentinel = stop.
2. `receive_events()` — iterates `async for raw in ws`, JSON-parses each message, dispatches to `_handle_event()`.

**Error handling:**
- `ConnectionRefusedError` — red error message + "Disconnected" status
- `ConnectionClosedOK` — dim "Session closed" message
- `ConnectionClosedError` — red error with reason
- Generic `Exception` — red error message
- `finally` — sets `_ws = None`

---

### 2.10 Event Handling (`_handle_event`) — Complete Dispatch Table

| Event Type | Handler Behavior |
|------------|-----------------|
| `session_status` | No-op (pass) |
| `thinking` | Writes italic dim `⟶ {content}` to log (skips "Processing...") |
| `tool_call` | Writes `⚙ tool_name(arg1=val1, ...)` in orange. Stores `_last_tool_name`. Auto-approves if enabled (except `tool_search`). Sets status to "Running: {tool}" with spinner. |
| `tool_result` | Calls `_write_tool_result()`. Sets status to "Processing response..." with spinner. |
| `tool_error` | Writes `✗ {tool} failed: {error}` in red. Sets status to "Error in {tool}". |
| `approval_request` | Pushes `ApprovalModal` screen, awaits result, sends approval WS message. |
| `response_chunk` | Calls `_write_response_chunk()` — appends token to streaming widget |
| `response` | Calls `_finalize_response()`, increments request count, tracks tokens, processes queue, sets "Ready" |
| `error` | Writes red error message, processes queue, sets "Error" |
| `session_closed` | Writes dim message, clears WS, sets "Disconnected" |

---

### 2.11 Streaming Response Mechanism

**Token flow:**
1. Server sends `{"type": "response_chunk", "content": "token text"}` events
2. `_write_response_chunk()` appends to `self._streaming_response` string
3. Updates `#streaming-response` Static widget in-place: `[b green]Agent:[/b green] {accumulated text}`
4. User sees text appearing token-by-token in the dedicated streaming area

**Finalization:**
1. Server sends `{"type": "response", "content": "full text", "tokens_used": N}`
2. `_finalize_response()`:
   - If streaming was active: formats with `_enhanced_markdown()`, writes to log, clears streaming widget
   - If no streaming: falls back to `_write_response()` with `_simple_markdown()`
3. Clears `_streaming_response` and streaming widget

**Markdown processing (`_enhanced_markdown`):**
- Extracts fenced code blocks (` ```lang\n...\n``` `) → placeholders
- Inline code → `[reverse]...[/reverse]`
- Bold → `[b]...[/b]`
- Italic → `[i]...[/i]`
- Restores code blocks with dim styling, truncates at 20 lines

**Simple markdown (`_simple_markdown`):**
- Bold, italic, inline code (same as enhanced)
- Strips code block fences entirely (no code block rendering)

---

### 2.12 Tool Call Display Formatting

**Tool call line** (in `_handle_event` for `tool_call`):
```
⚙ tool_name(arg1=val1, arg2=val2)
```
- Tool name in bold orange
- Args truncated to 60 chars each
- Values in white, keys in yellow

**Tool result dispatch** (`_format_tool_result_for_display`):

| Tool Category | Tools | Formatter | Output Format |
|---------------|-------|-----------|---------------|
| Shell | `run_shell`, `run_shell_streaming`, `shell` | `_format_shell_output` | `exit {N}` + first 15 lines |
| File read | `read_file`, `read_multiple_files` | `_format_read_file_output` | `(N lines)` + 12-line preview |
| File write | `write_file`, `write_multiple_files`, `edit_file`, `apply_patch` | `_format_write_file_output` | `✓ tool_name → path` |
| Git | `git_*` (prefix match) | `_format_git_output` | `git {subcmd}` + 10 lines |
| Search | `search_web`, `search_local_docs` | `_format_search_output` | `(N results)` + top 3 URLs |
| Subagent | `spawn_subagent` | `_format_subagent_output` | `subagent {id} status: {status}` |
| Default | anything else | `_format_tool_output` | JSON parsing → key-value summary or list |

**Inline vs Collapsible:**
- Short results (≤ `settings.agent.max_tool_output_chars`): written inline with ✓/✗ icon
- Long results: truncated via `_truncate_output()` (head+tail with char count), mounted as `Collapsible` widget (collapsed by default)

---

### 2.13 Word Wrapping Implementation

Word wrapping is achieved through **two mechanisms**:

1. **Textual CSS:** `#conversation-log` and `#streaming-response` both have:
   - `text-wrap: wrap`
   - `word-wrap: break-word`
   - `overflow-x: hidden`
   - `max-width: 100%`

2. **RichLog widget:** Created with `wrap=True` parameter

3. **No horizontal scroll:** `overflow-x: hidden` on conversation log

---

### 2.14 Slash Command Handling (`_handle_slash_command`)

All commands return `True` (handled). Unknown commands show error + help prompt.

| Command | Aliases | Behavior |
|---------|---------|----------|
| `/help` | `/h` | Shows full help text (commands + keyboard shortcuts) |
| `/new` | `/n` | Clears log, clears collapsibles, shows greeting |
| `/clear` | — | Clears log, clears collapsibles, clears streaming, shows greeting |
| `/expand` | `/e` | Expands all Collapsible widgets |
| `/collapse` | `/a` | Collapses all Collapsible widgets |
| `/quit` | `/q` | Calls `action_quit()` |
| `/sessions` | — | Shows "coming soon" + current session ID |
| `/status` | — | Shows: status, session, queue count, auto-approve, tokens, requests |
| `/interrupt` | — | Calls `action_interrupt()` |
| `/compact` | — | Sends `{"type": "compact"}` to server via WS |
| `/copy` | — | Shows "not available in TUI" message |
| `/version` | — | Shows: v0.1.0, model, session, theme |
| `/tokens` | — | Shows: total tokens, requests, model, session, avg tokens/request |
| `/model` | — | Shows: model, provider, session |
| `/threads` | — | Sends `{"type": "list_sessions"}` to server, or shows current session |
| `/theme` | — | Cycles to next theme in `NEXUS_THEMES`, applies via `_apply_theme()` |

---

### 2.15 Modal Screens

#### ApprovalModal
- **Triggered by:** `approval_request` WS event
- **Displayed via:** `push_screen_wait()` — blocks until dismissed
- **Returns:** `bool` (True=approved, False=rejected/cancelled)
- **CSS IDs:** `#approval-dialog`, `#approval-title`, `#approval-args`, `#approval-buttons`, `#approval-scroll`
- **Buttons:** Approve (success), Reject (error), Cancel (default)
- **After dismiss:** sends `{"type": "approval", "call_id": ..., "approved": ...}` via WS

#### ErrorModal
- **Not auto-triggered** — no code currently pushes ErrorModal (potential issue)
- **CSS IDs:** Reuses `#approval-dialog` IDs (shares styling)
- **Buttons:** OK (primary)
- **Returns:** `None`

---

### 2.16 Queue Management

When the agent is busy (`_busy == True`):
- New messages are appended to `_pending_inputs`
- User sees `⏳ Queued: {message}` in dim
- Queue status widget shows `⏳ N message(s) queued`
- When current response completes (`response` or `error` event), `_process_next_in_queue()` dequeues and sends the next message

---

### 2.17 Actions

| Action | Method | Behavior |
|--------|--------|----------|
| `action_clear` | `action_clear()` | Clears log, clears collapsibles, shows greeting |
| `action_quit` | `action_quit()` | Puts `None` sentinel in input queue, cancels WS task, calls `exit()` |
| `action_interrupt` | `action_interrupt()` | Sends `{"type": "interrupt"}` via WS if connected |
| `action_expand_all` | `action_expand_all()` | Sets all `Collapsible.collapsed = False` |
| `action_collapse_all` | `action_collapse_all()` | Sets all `Collapsible.collapsed = True` |
| `action_toggle_auto_approve` | `action_toggle_auto_approve()` | Toggles `_auto_approve`, updates badge widget |

---

### 2.18 Input Handling (`on_input_submitted`)

Flow:
1. Strip whitespace — ignore empty
2. If starts with `/` → clear input, call `_handle_slash_command()`, return
3. If busy → queue message, show "Queued", clear input, return
4. Set `_busy = True`, write `You: {message}` to log, clear input
5. Set status to "Thinking..." with spinner
6. Put message in `_input_queue` (sent by `send_messages()` coroutine)

---

### 2.19 Helper Methods

| Method | Lines | Purpose |
|--------|-------|---------|
| `_truncate_output(output)` | 1127–1133 | Head+tail truncation with char count |
| `_truncate(text, max_len)` | 1135–1138 | Simple string truncation with "..." |
| `_format_arg_value(value)` | 1140–1148 | Format tool arg: JSON for dict/list, escape for str |
| `_escape(text)` | 1150–1151 | Escape `[` → `\[`, `]` → `\]` (RichLog markup safety) |
| `_simple_markdown(text)` | 1153–1159 | Basic markdown → RichLog markup |

---

## 3. Event Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INPUT FLOW                               │
│                                                                      │
│  User types → Enter → on_input_submitted()                           │
│    ├─ "/" prefix → _handle_slash_command() → various actions         │
│    ├─ busy=True → queue in _pending_inputs → show "Queued"           │
│    └─ busy=False → write "You:" to log → put in _input_queue         │
│                                                                      │
│  _input_queue → send_messages() coroutine → WebSocket.send(JSON)     │
│    {"type": "user_input", "content": message}                        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     SERVER EVENT FLOW                                │
│                                                                      │
│  WebSocket.receive() → JSON.parse → _handle_event()                  │
│    ├─ "session_status" → (no-op)                                     │
│    ├─ "thinking" → log italic dim "⟶ {content}"                      │
│    ├─ "tool_call" → log "⚙ tool(args)" + auto-approve check          │
│    ├─ "tool_result" → _write_tool_result()                           │
│    │    ├─ short → inline ✓/✗ + formatted output                     │
│    │    └─ long → Collapsible (collapsed) + truncated output         │
│    ├─ "tool_error" → log red "✗ tool failed: error"                  │
│    ├─ "approval_request" → push ApprovalModal → _send_approval()     │
│    ├─ "response_chunk" → _write_response_chunk()                     │
│    │    └─ append to _streaming_response → update #streaming widget  │
│    ├─ "response" → _finalize_response()                              │
│    │    ├─ format with _enhanced_markdown() → write to log           │
│    │    ├─ clear streaming widget                                    │
│    │    ├─ track tokens + request count                              │
│    │    └─ _process_next_in_queue()                                  │
│    ├─ "error" → log red error → _process_next_in_queue()             │
│    └─ "session_closed" → log dim message → set disconnected          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    STREAMING TOKEN FLOW                               │
│                                                                      │
│  Server ──WS──→ "response_chunk" {content: "The"}                    │
│              ──WS──→ "response_chunk" {content: " answer"}           │
│              ──WS──→ "response_chunk" {content: " is"}               │
│              ──WS──→ "response" {content: "The answer is..."}        │
│                                                                      │
│  TUI: streaming_response += chunk                                    │
│       #streaming-response Static updated in-place                    │
│       User sees: "Agent: The" → "Agent: The answer" → ...           │
│                                                                      │
│  On "response": _enhanced_markdown() → log (final)                   │
│                 streaming widget cleared                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   APPROVAL FLOW                                      │
│                                                                      │
│  Server ──WS──→ "approval_request" {tool, args, call_id}             │
│  TUI: push_screen_wait(ApprovalModal)                                │
│       ├─ Approve → dismiss(True)  → WS: {"type":"approval", true}    │
│       ├─ Reject  → dismiss(False) → WS: {"type":"approval", false}   │
│       └─ Cancel  → dismiss(False) → WS: {"type":"approval", false}   │
│                                                                      │
│  Auto-approve (if ON, except tool_search):                           │
│  "tool_call" → immediately _send_approval(call_id, True)             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   QUEUE FLOW                                         │
│                                                                      │
│  Agent busy → User sends msg2 → queued in _pending_inputs            │
│  Agent busy → User sends msg3 → queued in _pending_inputs            │
│  Status: "⏳ 2 messages queued"                                      │
│                                                                      │
│  "response" event → _process_next_in_queue()                         │
│    → dequeue msg2 → write "You: msg2" → send via WS                 │
│    → Status: "⏳ 1 message queued"                                   │
│                                                                      │
│  "response" event → _process_next_in_queue()                         │
│    → dequeue msg3 → write "You: msg3" → send via WS                 │
│    → Queue empty → clear queue status                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. cli.py — Command Reference

### Entry Point: `main()` — Click group

| Command | Args | Options | Purpose |
|---------|------|---------|---------|
| `submit` | `task` (required) | — | Submit a task via SDK |
| `run` | `task` (required) | `--working-dir`, `--max-turns`, `--wall-time`, `--memory-mode`, `--acceptance`, `--model`, `--max-depth`, `--summary-only` | Spawn isolated worker |
| `session` | `action` (list/resume/fork/rename/delete), `session_id` (optional) | `--new-id`, `--working-dir`, `--status`, `--limit` | Manage sessions |

**Session actions:**
- `list` — Tabular output of sessions
- `resume` — Print session details
- `fork` — Copy session to new ID
- `rename` — Rename session
- `delete` — Delete session

---

## 5. web_ui.py — Gradio Dashboard

### Aesthetic Constants
- `THEME_COLOR`: `#FF4B2B` (Industrial Orange-Red)
- `BG_COLOR`: `#1A1A1A` (Deep Charcoal)
- `TEXT_COLOR`: `#E0E0E0` (Soft White)

### Components
- **Title:** "⚡ NEXUSAGENT CONTROL CENTER"
- **Status line:** `System Status: ONLINE | Protocol: CONTRACT-FIRST`
- **Left column (scale=2):**
  - `gr.Textbox` — "TASK DEFINITION" input (3 lines)
  - `gr.Button` — "TRANSMIT TASK" (uppercase, bold)
- **Right column (scale=1):**
  - `gr.Textbox` — "SDK STATUS" (read-only, default "IDLE")
- **Bottom row:**
  - `gr.TextArea` — "SYSTEM OUTPUT" (10 lines, read-only, bordered)

### Functions
- `handle_submit(text, sdk)` — Submits task via `NexusSDK.submit_task()`, returns log message + status
- `create_ui()` — Builds the Gradio Blocks layout
- `run_ui()` — Launches on `0.0.0.0:7860`

### Limitations
- No streaming — single submit/response cycle
- No conversation history
- No tool display
- No session management
- SDK status is static (not reactive)

---

## 6. Issues & Observations

### tui.py
1. **ErrorModal is never used** — defined but never pushed by any code path. The `error` event type writes directly to the log instead.
2. **Theme cycling is incomplete** — `_apply_theme()` only updates `background`, `header_bg`, and `header.color`. The CSS string remains static; accent colors for Collapsibles, streaming response border, etc. don't change.
3. **`_current_task` is set but never used** — assigned `None` in `on_mount()` but never assigned an actual task, so interrupt doesn't cancel a local task.
4. **No `@file` injection** — The input placeholder mentions `@file to inject` but no code handles `@` prefix in `on_input_submitted()`.
5. **`/sessions` is a stub** — Shows "coming soon" message.
6. **`/copy` is a stub** — Shows "not available" message.
7. **No reconnection logic** — If WS disconnects, the app shows "Disconnected" but doesn't attempt to reconnect.
8. **No message persistence** — Conversation log is in-memory only; closing the app loses all history.
9. **RichLog markup escaping** — `_escape()` only escapes `[` and `]`. If agent output contains RichLog markup-like strings (e.g., `[bold]`), they could be interpreted as markup.
10. **No input history** — No up/down arrow key binding for command history.
11. **Queue uses `asyncio.Queue` for send but `list` for pending** — The `_input_queue` (asyncio.Queue) is for WS send; `_pending_inputs` (list) is for user-level queuing. These are separate mechanisms.
12. **`# noqa: RUF006`** — Two fire-and-forget `asyncio.create_task()` calls suppress the RUF006 lint warning (asyncio task not awaited).

### cli.py
1. **No TUI integration** — CLI is completely separate from TUI; no way to launch TUI from CLI.
2. **Session resume is read-only** — `session resume` only prints info; doesn't reconnect to a session.

### web_ui.py
1. **No streaming** — Web UI has no real-time output; it's a simple submit-and-wait form.
2. **SDK instantiated per call** — `handle_submit()` creates a new `NexusSDK()` if none provided, but the Gradio `click()` handler passes only `inputs=[task_input]`, so a new SDK is created every time.
3. **No error handling for SDK init** — If `NexusSDK()` constructor fails, the error is caught by the generic `except` but the error message may be confusing.
4. **Port 7860 hardcoded** — No configuration option for the web UI port.

---

## 7. Architecture Summary

```
┌──────────────────────────────────────────────────────────┐
│                    NexusAgent Frontend                     │
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐ │
│  │   tui.py    │  │   cli.py    │  │    web_ui.py     │ │
│  │  (Textual)  │  │   (Click)   │  │    (Gradio)      │ │
│  │  Port: TTY  │  │  Port: CLI  │  │   Port: 7860     │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘ │
│         │                │                   │           │
│         └────────┬───────┴───────────┬───────┘           │
│                  │                   │                    │
│           ┌──────▼──────┐    ┌───────▼──────┐            │
│           │  WebSocket  │    │   SDK/HTTP   │            │
│           │  (ws://)    │    │   (internal) │            │
│           └──────┬──────┘    └───────┬──────┘            │
│                  │                   │                    │
│           ┌──────▼───────────────────▼──────┐            │
│           │        NexusAgent Server         │            │
│           │   (agent service + session mgmt) │            │
│           └─────────────────────────────────┘            │
└──────────────────────────────────────────────────────────┘
```

The TUI is the primary interactive interface, using WebSocket for real-time bidirectional communication. The CLI is a separate tool for task submission and session management. The web UI is a minimal dashboard for task submission only.
