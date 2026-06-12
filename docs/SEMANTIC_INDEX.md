# NexusAgent Semantic Architecture Index

> Generated: 2026-06-11
> Source files: 10 files, ~4,833 total lines

## Source Files

| # | File | Lines | Purpose |
|---|------|-------|---------|
| 1 | `src/nexusagent/interfaces/tui.py` | 1433 | Main TUI application (Textual) |
| 2 | `src/nexusagent/widgets/messages.py` | 473 | Message widget classes |
| 3 | `src/nexusagent/widgets/chat_input.py` | 216 | Chat input widget |
| 4 | `src/nexusagent/widgets/status.py` | 368 | Status bar + helpers |
| 5 | `src/nexusagent/widgets/theme/colors.py` | 274 | Color palette definitions |
| 6 | `src/nexusagent/widgets/theme/registry.py` | 69 | Theme CSS variable generation |
| 7 | `src/nexusagent/widgets/__init__.py` | 33 | Widget package exports |
| 8 | `src/nexusagent/interfaces/cli.py` | 249 | Click CLI commands |
| 9 | `src/nexusagent/server/server.py` | 355 | FastAPI server + WebSocket |
| 10 | `src/nexusagent/core/session.py` | 678 | Session + SessionManager |

---

## 1. TUI Application (`tui.py`)

### 1.1 Imports & Module-Level Constants (lines 1–60)

**Imports** (lines 18–51): `asyncio`, `contextlib`, `enum`, `json`, `logging`, `os`, `re`, `textwrap`, `time`, `uuid`, `datetime`, `typing`, `websockets`, Textual (`App`, `Binding`, `ModalScreen`, `Footer`, `Header`, etc.)

**Inline module constant:**
- `NEXUS_THEMES` (lines 53–59): List of 5 inline theme dicts with keys `name`, `header_bg`, `accent`, `bg`:
  - `midnight` (#1f2937 / #10b981 / #111827)
  - `ocean` (#0e4d6e / #38bdf8 / #0c1929)
  - `forest` (#14532d / #4ade80 / #052e16)
  - `sunset` (#7c2d12 / #fb923c / #1c1010)
  - `lavender` (#3b3864 / #a78bfa / #1a1830)

### 1.2 `SpinnerLabel` (lines 66–115)

> `class SpinnerLabel(Horizontal)` — Animated spinner + text widget

| Member | Lines | Type | Description |
|--------|-------|------|-------------|
| `spinner_chars` | 68 | ClassVar `str` | `"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"` |
| `tick` | 69 | `reactive(int)` | Animation frame counter |
| `__init__` | 71–76 | method | `text`, `_timer`, `_spinning` |
| `compose` | 77–79 | method | `Static("#spinner-icon")` + `Static("#spinner-text")` |
| `on_mount` | 81–82 | event handler | Calls `update_display()` |
| `set_text` | 84–94 | method | Update text, start/stop spinner timer |
| `_tick_spinner` | 96–97 | method | `self.tick += 1` on timer |
| `watch_tick` | 99–100 | reactive watcher | Calls `update_display()` on tick change |
| `update_display` | 102–110 | method | Updates spinner-icon and spinner-text Static widgets |
| `on_unmount` | 112–114 | event handler | Stops timer on unmount |

### 1.3 `Breakpoint` enum (lines 122–133)

| Member | Line | Value |
|--------|------|-------|
| `WIDE` | 124 | `"wide"` — > 120 cols |
| `STANDARD` | 125 | `"standard"` — 80–120 cols |
| `NARROW` | 126 | `"narrow"` — 60–79 cols |
| `TOO_SMALL` | 127 | `"too_small"` — < 60 cols |

**Module-level constants** (lines 131–133):
- `_WIDE_THRESHOLD = 120`
- `_STANDARD_THRESHOLD = 80`
- `_NARROW_THRESHOLD = 60`

**Standalone function:**
- `classify_breakpoint(width: int) -> Breakpoint` (lines 136–151)

### 1.4 Accessibility & Helpers (lines 154–241)

| Function / Variable | Lines | Description |
|---------------------|-------|-------------|
| `NO_COLOR` | 157 | `bool` — module-level, checks `"NO_COLOR" in os.environ` |
| `is_no_color()` | 160–166 | Returns `True` if `NO_COLOR` env var present |
| `debounce_resize(state, current_time, debounce_seconds=0.2)` | 174–197 | Returns `True` if resize should be handled |
| `_DEFAULT_DEBOUNCE_SECONDS` | 171 | `0.2` |
| `_sigwinch_handler(app)` | 200–226 | Debounce + breakpoint reclassify + warning notify |
| `_get_terminal_size()` | 229–240 | Returns `(columns, rows)`, fallback `(80, 24)` |

### 1.5 Modal Screens

#### `ApprovalModal` (lines 247–269)

> `class ApprovalModal(ModalScreen[bool])` — Tool call approval dialog

| Member | Lines | Description |
|--------|-------|-------------|
| `__init__` | 248–252 | `tool_name`, `tool_args`, `call_id` |
| `compose` | 254–263 | Vertical `#approval-dialog` → `Static(#approval-title)`, `ScrollableContainer(#approval-scroll)` → `Static(#approval-args)`, `Horizontal(#approval-buttons)` → `Button#approve(variant="success")`, `Button#reject(variant="error")`, `Button#cancel` |
| `on_button_pressed` | 265–269 | If approve → `dismiss(True)`, else `dismiss(False)` |

#### `ErrorModal` (lines 276–291)

> `class ErrorModal(ModalScreen[None])` — Error display dialog

| Member | Lines | Description |
|--------|-------|-------------|
| `__init__` | 279–281 | `error_message` |
| `compose` | 283–288 | Vertical `#approval-dialog` → `Static("⚠ Error")`, `Static(error_message)`, `Button#ok(variant="primary")` |
| `on_button_pressed` | 290–291 | `dismiss(None)` |

### 1.6 `NexusApp` — Main Application (lines 298–1425)

> `class NexusApp(App)` — Textual TUI application

#### BINDINGS (lines 299–308)

| Keys | Action | Label | Show |
|------|--------|-------|------|
| `q` | `action_quit` | "Quit" | Yes |
| `escape` | `action_quit` | "Quit" | No (hidden) |
| `c` | `action_clear` | "Clear" | Yes |
| `ctrl+c` | `action_interrupt` | "Interrupt" | Yes |
| `ctrl+u` | `action_interrupt` | "Interrupt" | Yes |
| `e` | `action_expand_all` | "Expand" | Yes |
| `a` | `action_collapse_all` | "Collapse" | Yes |
| `ctrl+underscore` | `action_toggle_auto_approve` | "Auto-approve" | No (hidden) |

#### CSS (lines 310–450)

All selectors and style properties:

| Selector | Lines | Key Properties |
|----------|-------|----------------|
| `Screen` | 311–314 | `layers: base overlay`, `background: #111827` |
| `#log-container` | 317–322 | `width: 100%`, `height: 1fr`, `border: solid #1f2937`, `margin: 0 1` |
| `#conversation-log` | 324–335 | `width: 100%`, `max-width: 100%`, `background: #111827`, `padding: 1 2`, `overflow-y: auto`, `overflow-x: hidden`, `text-wrap: wrap`, `word-wrap: break-word` |
| `#streaming-response` | 338–351 | `height: auto`, `color: #93c5fd`, `background: #1f2937`, `border-left: wide #3b82f6` |
| `#input-area` | 354–363 | `border: solid #374151`, `height: 3`, `background: #1f2937`; focus: `border: solid #10b981` |
| `#status-bar` | 366–372 | `height: 1`, `background: #1f2937`, `color: #9ca3af` |
| `#auto-approve-badge` | 375–381 | `height: 1`, `color: #fbbf24`, `text-style: bold` |
| `#queue-status` | 384–389 | `color: #6b7280`, `text-style: italic`, `height: 1` |
| `Collapsible` | 392–409 | `border-left: wide #fbbf24`, `margin: 1 2`, `background: #1f2937`; header color `#fbbf24`; collapsed header `#6b7280`; content `color: #d1d5db` |
| `#approval-dialog` | 412–438 | `width: 80%`, `max-height: 20`, `border: solid #fbbf24`, `background: #1f2937`; title bold `#fbbf24`; args `color: #d1d5db`; buttons align right |
| `Header` | 441–445 | `background: #1f2937`, `color: #10b981`, `text-style: bold` |
| `Footer` | 446–449 | `background: #1f2937`, `color: #6b7280` |

**Inline hex colors used in TUI CSS:**
- Backgrounds: `#111827`, `#1f2937`, `#374151`
- Text: `#93c5fd`, `#9ca3af`, `#d1d5db`, `#6b7280`, `#fbbf24`
- Borders: `#1f2937`, `#374151`, `#10b981`, `#fbbf24`, `#3b82f6`

#### Layout Structure — `compose()` output tree (lines 452–466)

```
Screen
├── Header                          (line 453)
├── ScrollableContainer#log-container   (lines 454–457)
│   └── RichLog#conversation-log       (line 455, markup=True, auto_scroll=True, wrap=True)
├── Static#streaming-response          (line 458) — inline streaming widget
├── SpinnerLabel#status-bar            (line 459, text="Ready")
├── Static#auto-approve-badge          (line 460)
├── Static#queue-status               (line 461)
├── Input#input-area                   (line 462–465, placeholder="Type a message...")
└── Footer                           (line 466)
```

#### `__init__` (lines 468–473)

| Param/Attr | Line | Default |
|------------|------|---------|
| `session_id` | 468 (param) | `None` |
| `yolo` | 468, 470 | `False` |
| `_breakpoint` | 471 | `Breakpoint.STANDARD` |
| `_resize_state` | 472 | `{}` |
| `_no_color` | 473 | module-level `NO_COLOR` |

#### Lifecycle & Mount

- `on_mount` (lines 475–501): Initializes `session_id` (UUID[:8]), widget refs, state vars, greeting, starts `_ws_task`, installs SIGWINCH.

#### Lifecycle — `__init__` state vars (lines 476–495)

| Attribute | Line | Type | Initial |
|-----------|------|------|---------|
| `session_id` | 476 | `str` | `str(uuid.uuid4())[:8]` |
| `log_widget` | 477 | `RichLog` | query |
| `status_widget` | 478 | `SpinnerLabel` | query |
| `queue_status` | 479 | `Static` | query |
| `_streaming_widget` | 480 | `Static` | query |
| `_streaming_response` | 481 | `str` | `""` |
| `_input_queue` | 482 | `asyncio.Queue[str \| None]` | new |
| `_busy` | 483 | `bool` | `False` |
| `_ws` | 484 | `websockets.WebSocketClientProtocol \| None` | `None` |
| `_collapsibles` | 485 | `list[Collapsible]` | `[]` |
| `_pending_inputs` | 486 | `list[str]` | `[]` |
| `_current_task` | 487 | `asyncio.Task \| None` | `None` |
| `_auto_approve` | 488 | `bool` | `self._yolo_default or settings.agent.yolo` |
| `_auto_approve_task` | 489 | `asyncio.Task \| None` | `None` |
| `_interrupt_task` | 490 | `asyncio.Task \| None` | `None` |
| `_theme_index` | 491 | `int` | `0` |
| `_total_tokens_used` | 492 | `int` | `0` |
| `_request_count` | 493 | `int` | `0` |
| `_auto_approve_badge` | 494 | `Static` | query |

#### Event Handlers (`on_*`)

| Method | Lines | Trigger |
|--------|-------|---------|
| `on_mount` | 475–501 | Widget mount |
| `on_input_submitted` | 1321–1344 | `Input.Submitted` event from `#input-area` |

#### WebSocket Event Handlers / Message Types (`_handle_event`, lines 646–738)

| WS `type` | Lines | Handler Behavior |
|-----------|-------|------------------|
| `session_status` | 649–650 | No-op (`pass`) |
| `thinking` | 652–659 | Writes italic dim message to log |
| `tool_call` | 660–679 | Displays tool call, auto-approve check, starts spinner |
| `tool_result` | 681–686 | Calls `_write_tool_result()`, stops spinner |
| `tool_error` | 688–696 | Writes red error message to log |
| `approval_request` | 698–705 | Pushes `ApprovalModal` screen, sends approval |
| `response_chunk` | 707–710 | Appends streaming token via `_write_response_chunk()` |
| `response` | 712–723 | Finalizes response, updates tokens, processes queue |
| `error` | 726–732 | Writes error, clears busy, processes queue |
| `session_closed` | 733–737 | Writes disconnect, nulls ws |

#### WebSocket Outbound Messages (sent by TUI)

| Type | Lines | Direction |
|------|-------|-----------|
| `user_input` | 617 | TUI → Server (via `_input_queue`) |
| `approval` | 1311–1315 | TUI → Server (via `approve()`) |
| `interrupt` | 1362 | TUI → Server (via `action_interrupt()`) |
| `compact` | 1025 | TUI → Server (via `/compact`) |
| `list_sessions` | 1102 | TUI → Server (via `/threads`) |
| `undo` | 1122 | TUI → Server (via `/undo`) |
| `redo` | 1133 | TUI → Server (via `/redo`) |

#### Action Methods (`action_*`)

| Method | Lines | Binding | Description |
|--------|-------|---------|-------------|
| `action_clear` | 1348–1351 | `c` | Clears log, collapsibles, shows greeting |
| `action_quit` | 1353–1357 | `q`, `escape` | Puts `None` in queue, cancels ws task, exits |
| `action_interrupt` | 1359–1365 | `ctrl+c`, `ctrl+u` | Sends `{"type": "interrupt"}` to server |
| `action_expand_all` | 1367–1369 | `e` | Sets all collapsibles to `collapsed=False` |
| `action_collapse_all` | 1371–1373 | `a` | Sets all collapsibles to `collapsed=True` |
| `action_toggle_auto_approve` | 1375–1388 | `ctrl+underscore` | Toggles `_auto_approve`, updates badge |

#### Slash Commands (`_handle_slash_command`, lines 951–1180)

| Command | Aliases | Lines | Behavior |
|---------|---------|-------|----------|
| `/help` | `/h` | 957–959 | Shows `_show_help()` |
| `/new` | `/n` | 961–969 | Clears, shows greeting |
| `/clear` | — | 972–978 | Clears log + streaming area, shows greeting |
| `/expand` | `/e` | 980–983 | Expands all collapsibles |
| `/collapse` | `/a` | 985–988 | Collapses all collapsibles |
| `/quit` | `/q` | 990–992 | Calls `action_quit()` |
| `/sessions` | — | 994–1000 | Stub: shows session management coming soon |
| `/status` | — | 1002–1013 | Shows status, session, queue, auto-approve, tokens, requests |
| `/interrupt` | — | 1015–1017 | Calls `action_interrupt()` |
| `/compact` | — | 1019–1032 | Sends `{"type": "compact"}` to server |
| `/copy` | — | 1034–1040 | Shows "not available" message |
| `/version` | — | 1042–1050 | Shows v0.1.0, model, session, theme |
| `/auto` | — | 1052–1054 | Toggles auto-approve |
| `/tokens` | — | 1056–1081 | Shows total tokens, requests, avg/request |
| `/model` | — | 1083–1094 | Shows model + provider |
| `/threads` | — | 1096–1108 | Sends `{"type": "list_sessions"}` to server |
| `/theme` | — | 1110–1118 | Cycles `NEXUS_THEMES`, applies via `_apply_theme()` |
| `/undo` | — | 1120–1129 | Sends `{"type": "undo"}` |
| `/redo` | — | 1131–1140 | Sends `{"type": "redo"}` |
| `/skills` | — | 1142–1154 | Loads and displays all skills |
| `/skill <name>` | — | 1156–1173 | Shows skill content (first 20 lines) |
| *(unknown)* | — | 1175–1180 | Shows "Unknown command" |

#### Tool Result Formatters (lines 773–798, 800–878)

| Method | Lines | Tool Match |
|--------|-------|------------|
| `_format_tool_result_for_display` | 773–798 | Dispatch table by tool name |
| `_format_shell_output` | 800–823 | `run_shell`, `run_shell_streaming`, `shell` |
| `_format_read_file_output` | 825–838 | `read_file`, `read_multiple_files` |
| `_format_write_file_output` | 840–846 | `write_file`, `write_multiple_files`, `edit_file`, `apply_patch` |
| `_format_git_output` | 848–857 | `git_*` (startswith) |
| `_format_search_output` | 859–868 | `search_web`, `search_local_docs` |
| `_format_subagent_output` | 870–878 | `spawn_subagent` |
| `_format_tool_output` | 880–936 | Default: JSON parse + human-readable |

#### Streaming & Display Helpers

| Method | Lines | Description |
|--------|-------|-------------|
| `_write_tool_result` | 741–771 | Short results inline, long results collapsible |
| `_write_response` | 938–947 | Final response with timestamp + markdown |
| `_write_response_chunk` | 1220–1229 | Appends token to streaming-response widget |
| `_finalize_response` | 1231–1255 | Moves streaming to log, clears streaming widget |
| `_enhanced_markdown` | 1257–1288 | Code block extraction, bold/inline code styling |
| `_simple_markdown` | 1418–1424 | Bold/italic/code regex replacement |
| `_show_help` | 1189–1216 | Displays all commands and key shortcuts |

#### Misc Internal Methods

| Method | Lines | Description |
|--------|-------|-------------|
| `_ws_loop` | 601–642 | WebSocket connection loop (connect, send/receive) |
| `_show_greeting` | 569–597 | ASCII art banner + command/key hints |
| `_apply_theme` | 1182–1187 | Updates background + header colors |
| `_process_next_in_queue` | 1292–1300 | Processes message queue |
| `_update_queue_status` | 1302–1307 | Updates queue status display |
| `_send_approval` | 1309–1317 | Sends approval JSON over WS |
| `_truncate_output` | 1392–1398 | Head+tail truncation |
| `_truncate` | 1400–1403 | Simple string truncation |
| `_format_arg_value` | 1405–1413 | Format tool args (JSON or escaped) |
| `_escape` | 1415–1416 | Escape Rich markup brackets |

#### SIGWINCH / Responsive

| Method | Lines | Description |
|--------|-------|-------------|
| `_install_sigwinch` | 505–527 | Installs SIGWINCH signal handler |
| `_check_sigwinch` | 529–537 | Polls pending flag, calls `_sigwinch_handler` |
| `_restore_sigwinch` | 539–548 | Restores original signal handler |

#### Accessibility

| Method | Lines | Description |
|--------|-------|-------------|
| `_is_ascii_terminal` | 550–565 | Checks NO_COLOR, TERM=dumb, COLORTERM |

### 1.7 Standalone Functions (lines 1427–1433)

| Function | Lines | Description |
|----------|-------|-------------|
| `main(yolo=False)` | 1427–1429 | Entry point: creates `NexusApp` and runs it |
| `if __name__ == "__main__"` | 1432–1433 | Calls `main()` |

---

## 2. Widgets

### 2.1 `messages.py` — Message Widget Classes (lines 1–472)

**Module-level patterns** (lines 38–53):

| Variable | Line | Value |
|----------|------|-------|
| `_CODE_BLOCK_RE` | 38 | `re.compile(r"```[\s\S]*?```")` |
| `_INLINE_CODE_RE` | 39 | `re.compile(r"`[^`]+`")` |
| `_CODE_BLOCK_LANG_RE` | 41 | `re.compile(r"```(\w*)\n[\s\S]*?```")` |
| `_NEWLINE_RE` | 43 | `re.compile(r"\n")` |
| `_COLLAPSE_LINE_THRESHOLD` | 46 | `4` |
| `_COLLAPSE_CHAR_THRESHOLD` | 47 | `300` |
| `_BOLD_RE` | 50 | `re.compile(r"\*\*(.+?)\*\*")` |
| `_ITALIC_RE` | 51 | `re.compile(r"\*(.+?)\*")` |
| `_INLINE_CODE_RENDER_RE` | 52 | `re.compile(r"`([^`]+)`")` |

#### `UserMessage(Static)` (lines 55–84)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 63–73 | `border-left: wide $primary`, `text-wrap: wrap`, `height: auto` |
| `__init__` | 75–77 | Stores `content` |
| `render` | 79–84 | Returns `Content.assemble` with dim timestamp + content |

#### `AssistantMessage(Static)` (lines 87–208)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 95–104 | `text-wrap: wrap`, `height: auto`, transparent bg |
| `__init__` | 106–108 | `_buffer = ""` |
| `append_token` | 110–120 | Async: append token, schedule `_render_buffer` via `call_next` |
| `_render_buffer` | 122–124 | Updates widget with `Content(_buffer)` |
| `finalize` | 126–129 | Sets final content |
| `render` | 131–132 | Returns `_render_markdown(_buffer)` |
| `_render_markdown` | 134–151 | Fast path if no MD chars; delegates to `_parse_markdown` |
| `_parse_markdown` | 153–208 | Parses `**bold**`, `*italic*`, `` `code` `` → `Content.assemble(*parts)` |

#### `ToolCallMessage(Static)` (lines 211–380)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 229–242 | `border-left: wide $warning`, hover → `$accent-light` |
| `STATUS_RUNNING` | 245 | `"running"` |
| `STATUS_SUCCESS` | 246 | `"success"` |
| `STATUS_FAILED` | 247 | `"failed"` |
| `_STATUS_ICONS` | 249–253 | `⚙`, `✔`, `✘` |
| `_STATUS_STYLES` | 255–259 | `"bold warning"`, `"bold success"`, `"bold error"` |
| `__init__` | 261–275 | `tool`, `args`, `output=""`, `status="running"`, `_collapsed` |
| `_should_collapse` | 277–282 | Threshold: ≥4 lines or ≥300 chars |
| `_format_args` | 284–296 | JSON pretty-print or raw |
| `_detect_code` | 298–300 | Checks for code blocks |
| `_detect_syntax_hint` | 302–312 | Language hint from first fenced block |
| `_truncate_output` | 314–320 | Truncates with remaining chars indicator |
| `_count_lines` | 322–326 | Counts `\n` + 1 |
| `update_status` | 328–331 | Updates status + refresh |
| `update_output` | 333–337 | Updates output + recalc collapse + refresh |
| `toggle_collapse` | 339–342 | Toggles `_collapsed` + refresh |
| `render` | 344–380 | Returns `Content.assemble` with icon, header, args, output |

#### `AppMessage(Static)` (lines 383–406)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 389–399 | `$text-muted`, italic, `text-wrap: wrap` |
| `render` | 405–406 | `"○ "` + message in muted |

#### `ErrorMessage(Static)` (lines 409–432)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 415–425 | `color: $error`, `border-left: wide $error` |
| `render` | 431–432 | `"✗ Error: "` bold red + message red |

#### `WelcomeBanner(Static)` (lines 435–472)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 443–453 | `$surface` bg, `border: solid $border` |
| `__init__` | 455–461 | `session_id`, timestamp |
| `render` | 463–472 | "NexusAgent — AI Coding Agent" with session info |

---

### 2.2 `chat_input.py` — Chat Input Widget (lines 1–215)

**Module-level constants:**

| Variable | Line | Value |
|----------|------|-------|
| `SLASH_COMMANDS` | 28–34 | `["/clear", "/help", "/logs", "/model", "/theme"]` (sorted) |
| `_HISTORY_DIR` | 37 | `Path.home() / ".nexusagent"` |
| `_HISTORY_FILE` | 38 | `_HISTORY_DIR / "history.json"` |
| `_MAX_HISTORY` | 39 | `200` |

**Standalone functions:**

| Function | Lines | Description |
|----------|-------|-------------|
| `_load_history()` | 42–52 | Loads history from `~/.nexusagent/history.json` |
| `_save_history(history)` | 55–62 | Persists history to disk |

#### `ChatInput(TextArea)` (lines 65–215)

| Member | Line | Description |
|--------|------|-------------|
| `BINDINGS` | 75–78 | `enter→action_submit`, `escape→action_cancel`, `tab→action_autocomplete` |
| `DEFAULT_CSS` | 81–97 | `$surface` bg, `$border` border → `$border-focus` on focus |
| `__init__` | 99–105 | `_history`, `_history_idx`, `_slash_matches`, `_slash_match_idx`, `_hint` |
| `on_mount` | 107–109 | Sets `border_title = "Message"`, updates hint |
| `_update_hint` | 111–117 | Updates `border_subtitle` with slash hints |
| `action_submit` | 119–146 | Validates, adds to history, persists, extracts images, clears, posts `Submitted` |
| `action_cancel` | 148–153 | Clears text + slash state |
| `on_input_changed` | 155–157 | Updates slash command hint |
| `action_autocomplete` | 159–178 | Tab: cycle slash commands or insert spaces |
| `_extract_images` | 180–196 | Regex: URLs + local paths for images (png/jpg/jpeg/webp/gif/bmp) |
| `_get_slash_hint` | 198–207 | Returns space-joined matching commands |
| `inner class Submitted(TextArea.Changed)` | 209–215 | Event with `.text` and `.images` |

---

### 2.3 `status.py` — Status Bar Widget (lines 1–367)

#### `ModelLabel(Static)` (lines 36–77)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 44–50 | `$text-muted`, auto width |
| `__init__` | 52–55 | `_provider`, `_model` |
| `set_model` | 57–60 | Updates provider+model, refreshes |
| `render` | 62–77 | Smart truncation: full → model-only → left-ellipsis |

#### `StatusBar(Horizontal)` (lines 80–221)

| Member | Line | Description |
|--------|------|-------------|
| `DEFAULT_CSS` | 86–122 | `dock: bottom`, `$surface` bg; CSS classes: `.status-message` (1fr), `.status-cwd`, `.status-branch`, `.status-tokens`, `.status-spinner` (width:2, $warning) |
| `SPINNER_CHARS` | 125 | `"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"` |
| `__init__` | 127–136 | `_status_message`, `_cwd`, `_branch`, `_tokens`, `_model_*`, `_spinning`, `_spinner_idx` |
| `compose` | 138–144 | `Static#status-spinner`, `Static#status-message`, `Static#status-cwd`, `Static#status-branch`, `Static#status-tokens`, `ModelLabel#status-model` |
| `on_mount` | 146–147 | Calls `_update_widgets()` |
| `_update_widgets` | 149–184 | Responsive: hides CWD ≤60 cols, hides branch ≤80 cols |
| `set_status` | 186–188 | Updates message |
| `set_cwd` | 190–192 | Updates CWD |
| `set_branch` | 194–196 | Updates branch |
| `set_tokens` | 198–200 | Updates token count |
| `set_model` | 202–205 | Updates model |
| `set_spinner` | 207–211 | Start/stop spinner |
| `tick_spinner` | 213–221 | Advance spinner frame |

#### `GitStatus` (lines 249–296)

| Member | Line | Description |
|--------|------|-------------|
| `detect()` (static) | 260–284 | Returns `"clean"`, `"dirty"`, `"staged"`, or `None` |
| `label(status)` (static) | 287–296 | Returns display label string |

#### `ContextWindowBar` (lines 302–343)

| Member | Line | Description |
|--------|------|-------------|
| `SAFE_COLOR` | 312 | `"#10B981"` |
| `WARN_COLOR` | 313 | `"#EB8B46"` |
| `DANGER_COLOR` | 314 | `"#F7768E"` |
| `__init__` | 316–318 | `used`, `total` |
| `percentage` (property) | 320–325 | Integer 0–100 |
| `color` (property) | 327–335 | Based on thresholds |
| `bar(width=10)` | 337–343 | Returns `"████░░░░░░ 40%"` |

#### `BrailleSpinner` (lines 349–367)

| Member | Line | Description |
|--------|------|-------------|
| `CHARS` | 352 | `"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"` |
| `tick()` | 357–359 | Advance frame |
| `current()` | 361–363 | Current char |
| `reset()` | 365–367 | Reset to frame 0 |

**Module-level:**
- `NO_COLOR` (line 226): `bool(os.environ.get("NO_COLOR"))`
- `_run_git(*args)` (lines 232–246): Runs git command, returns stdout or None

---

### 2.4 `theme/colors.py` — Color Palette Definitions (lines 1–273)

**Module-level color constants** (hex values):

| Variable | Line | Value | Theme |
|----------|------|-------|-------|
| `BG` | 9 | `#11181C` | Nexus Dark |
| `BG_PANEL` | 10 | `#1A1D23` | |
| `BG_SURFACE` | 11 | `#23252A` | |
| `BG_HOVER` | 12 | `#28282C` | |
| `TEXT` | 15 | `#F7F8F8` | |
| `TEXT_SECONDARY` | 16 | `#D0D6E0` | |
| `TEXT_MUTED` | 17 | `#8A8F98` | |
| `TEXT_DIM` | 18 | `#62666D` | |
| `ACCENT` | 21 | `#5E6AD2` | |
| `ACCENT_HOVER` | 22 | `#7170FF` | |
| `ACCENT_LIGHT` | 23 | `#828FFF` | |
| `SUCCESS` | 26 | `#10B981` | |
| `WARNING` | 27 | `#EB8B46` | |
| `ERROR` | 28 | `#F7768E` | |
| `ERROR_BG` | 29 | `#2A1F32` | |
| `BORDER` | 32 | `rgba(255,255,255,0.08)` | |
| `BORDER_SUBTLE` | 33 | `rgba(255,255,255,0.05)` | |
| `BORDER_FOCUS` | 34 | `#5E6AD2` | |

Same pattern for: `TN_*` (Tokyo Night, lines 39–56), `RP_*` (Rosé Pine, lines 61–78), `SD_*` (Solarized Dark, lines 83–100), `CP_*` (Catppuccin Mocha, lines 105–122), `GB_*` (Gruvbox Dark, lines 127–144), `ND_*` (Nord, lines 149–166).

#### `ThemeColors` dataclass (lines 171–200)

> `@dataclass(frozen=True)` — 17 fields: `bg`, `bg_panel`, `bg_surface`, `bg_hover`, `text`, `text_secondary`, `text_muted`, `text_dim`, `accent`, `accent_hover`, `accent_light`, `success`, `warning`, `error`, `error_bg`, `border`, `border_subtle`, `border_focus`

#### Theme Instances (lines 205–271)

| Variable | Line | Name |
|----------|------|------|
| `DARK_COLORS` | 205–211 | nexus-dark |
| `TOKYO_NIGHT_COLORS` | 213–219 | tokyo-night |
| `ROSE_PINE_COLORS` | 221–227 | rose-pine |
| `SOLARIZED_DARK_COLORS` | 229–235 | solarized-dark |
| `CATPPUCCIN_MOCHA_COLORS` | 237–243 | catppuccin-mocha |
| `GRUVBOX_DARK_COLORS` | 245–251 | gruvbox-dark |
| `NORD_COLORS` | 253–259 | nord |

| Variable | Line | Description |
|----------|------|-------------|
| `THEME_REGISTRY` | 263–271 | `dict[str, ThemeColors]` — 7 themes |
| `ALL_THEMES` | 273 | `list[str]` — all theme names |

---

### 2.5 `theme/registry.py` — Theme CSS Variable Generation (lines 1–68)

| Function | Lines | Description |
|----------|-------|-------------|
| `get_theme_colors(theme_name="nexus-dark")` | 14–16 | Returns `ThemeColors` for name |
| `get_theme_css(theme_name="nexus-dark")` | 19–46 | Returns `dict[str, str]` with 20+ CSS variables |
| `get_css_variable_defaults()` | 49–51 | Returns defaults for "nexus-dark" |
| `register_themes(app)` | 54–68 | Registers all 7 themes with Textual app via `Theme(name, variables=...)` |

**CSS variables generated by `get_theme_css()`** (lines 22–46):

| Variable | Maps to |
|----------|---------|
| `background` | `c.bg` |
| `surface` | `c.bg_panel` |
| `primary` | `c.accent` |
| `secondary` | `c.accent_hover` |
| `success` | `c.success` |
| `warning` | `c.warning` |
| `error` | `c.error` |
| `text` | `c.text` |
| `text-muted` | `c.text_muted` |
| `text-secondary` | `c.text_secondary` |
| `border` | `c.border` |
| `border-subtle` | `c.border_subtle` |
| `border-focus` | `c.border_focus` |
| `bg-surface` | `c.bg_surface` |
| `bg-hover` | `c.bg_hover` |
| `error-muted` | `c.error_bg` |
| `accent-light` | `c.accent_light` |
| `text-dim` | `c.text_dim` |
| `accent-hover` | `c.accent_hover` |
| `panel` | `c.bg_panel` |

---

## 3. Server & WebSocket (`server.py`)

### 3.1 HTTP Endpoints

| Method | Path | Lines | Auth | Description |
|--------|------|-------|------|-------------|
| `POST` | `/tasks` | 78–114 | API key | Submit a new task |
| `GET` | `/tasks/{task_id}/status` | 117–123 | API key | Get task status |
| `GET` | `/tasks/{task_id}/result` | 126–135 | API key | Get task result (404 if not ready) |
| `GET` | `/health` | 138–141 | None | Health check (NATS status) |
| `GET` | `/tasks` | 147–153 | API key | List tasks (filter + pagination) |
| `POST` | `/tasks/{task_id}/cancel` | 159–167 | API key | Cancel a task |
| `POST` | `/tasks/{task_id}/retry` | 173–186 | API key | Retry a failed task |
| `GET` | `/workers` | 192–214 | API key | List workers + circuit breaker state |
| `GET` | `/tools` | 217–233 | API key | List all tools grouped by category |

### 3.2 WebSocket Endpoint

| Path | Lines | Description |
|------|-------|-------------|
| `/sessions/{session_id}/ws` | 239–343 | Real-time interactive session |

**WebSocket auth:** API key via query param `?api_key=xxx` (line 243). Closes with code `4001` on invalid key (line 254).

### 3.3 WebSocket Message Types (Server → Client)

| Type | Lines | Description |
|------|-------|-------------|
| `session_status` | 279 | Initial status after connect |
| `thinking` | 333 (session.py) | Agent is processing |
| `tool_call` | 461 (session.py) | Tool invocation started |
| `tool_result` | 474, 529 (session.py) | Tool execution result |
| `tool_error` | — | Server-emitted tool failure |
| `approval_request` | — | Request tool call approval |
| `response_chunk` | 507 (session.py) | Streaming token chunk |
| `response` | 405 (session.py) | Final response |
| `error` | 315, 443 (session.py) | Error event |
| `session_closed` | 581 (session.py) | Session closed |
| `session_list` | 305 (server.py) | List of sessions |
| `compact_result` | 320 (server.py) | Compaction result |

### 3.4 WebSocket Message Types (Client → Server)

| Type | Lines | Description |
|------|-------|-------------|
| `user_input` | 290–296 | User message (text + optional images) |
| `approval` | 297–298 | Approve/reject tool call |
| `interrupt` | 299–300 | Cancel current turn |
| `list_sessions` | 301–315 | Request session list |
| `compact` | 316–331 | Trigger context compaction |
| `close` | 332–334 | Close session |

### 3.5 Server Lifespan (`lifespan`, lines 23–54)

1. Initialize DB (`db_manager.init_db()`)
2. Connect to NATS (`get_bus().connect()`)
3. Start worker background task (`worker.start()`)
4. On shutdown: cancel worker, close NATS

### 3.6 Pydantic Models

| Model | Line | Fields |
|-------|------|--------|
| `SubmitTaskRequest` | 72–75 | `description: str`, `priority: int = 1`, `metadata: dict = {}` |

### 3.7 Entry Point

- `run()` (lines 346–350): Runs `uvicorn` on `0.0.0.0:settings.server.api_port`

---

## 4. Session Management (`session.py`)

### 4.1 Standalone Helper Functions

| Function | Lines | Description |
|----------|-------|-------------|
| `_extract_agent_response(result)` | 30–71 | Extracts text from str/list/dict/agent result |
| `_get_git_info(working_dir)` | 74–97 | Returns branch + changed files count |
| `_build_environment_context(working_dir)` | 100–143 | Builds environment block (dir, user, OS, time, git, tools) |
| `_build_session_history_context(working_dir)` | 146–159 | Stub: returns empty string |

### 4.2 `Session` Class (lines 162–597)

| Member | Line | Description |
|--------|------|-------------|
| `__init__` | 168–202 | `session_id`, `working_dir`, `agent`, `memory`, `db_repo`, `memory_dir`, `hybrid_memory`, `status="active"`, `_cancel_flag`, `_event_queue`, `_pending_approvals`, `_approval_results`, `_seen_tool_results`, `_seen_tool_calls`, `_conversation_history` |
| `_load_system_prompt()` | 206–224 | Loads NEXUS.md + project NEXUS.md, caches |
| `_build_context_injection()` | 226–235 | Environment + session history context |
| `_process_chat_input(user_message)` | 239–265 | @file injection in chat |
| `_build_user_message(user_message, images)` | 267–301 | Builds HumanMessage (text or multimodal) |
| `send(user_message, images)` | 303–443 | Main: hooks, DB store, build messages, compaction, invoke agent, emit events |
| `_handle_message_token(token, metadata, accumulated)` | 445–510 | Process streaming token (tool_call, tool_result, text chunk) |
| `_handle_update(data)` | 512–534 | Process update chunk from stream |
| `pre_compaction_flush()` | 538–548 | Flush to daily log before compaction |
| `approve(call_id, approved)` | 552–557 | Record approval decision |
| `_wait_for_approval(call_id)` | 559–563 | Create/get approval gate |
| `interrupt()` | 567–569 | Set cancel flag |
| `close()` | 573–581 | Close session, update DB, enqueue `session_closed` |
| `event_stream()` | 585–591 | Async generator yielding events from queue |
| `_enqueue(event)` | 595–597 | Put event on queue (non-blocking) |

### 4.3 `SessionManager` Class (lines 600–674)

| Member | Line | Description |
|--------|------|-------------|
| `__init__` | 606–608 | `_sessions: dict[str, Session]`, `_lock: asyncio.Lock` |
| `get(session_id)` | 610–615 | Return cached session or None |
| `get_or_create(session_id, ...)` | 617–651 | Thread-safe get or create (double-checked locking) |
| `mark_idle(session_id)` | 653–662 | Transition to idle, update DB |
| `close(session_id)` | 664–668 | Close and remove from cache |
| `active_count` (property) | 670–673 | Number of cached sessions |

**Module-level singleton:** `session_manager = SessionManager()` (line 677)

---

## 5. CLI (`cli.py`)

### 5.1 Commands

| Command | Lines | Description |
|---------|-------|-------------|
| `main` (group) | 22–26 | Root CLI group with version option |
| `submit <task>` | 28–56 | Submit a task to the agent service |
| `run <task>` | 59–108 | Spawn isolated worker (options: `--working-dir`, `--max-turns`, `--wall-time`, `--memory-mode`, `--acceptance`, `--model`, `--max-depth`, `--summary-only`) |
| `session <action> [session_id]` | 111–194 | Session management (actions: `list`, `resume`, `fork`, `rename`, `delete`) |
| `hooks` (group) | 197–199 | Hook management |
| `hooks list` | 202–216 | List all hooks |
| `hooks enable <name>` | 219–230 | Enable a hook |
| `hooks disable <name>` | 233–244 | Disable a hook |

### 5.2 Entry Points

| Function | Line | Description |
|----------|------|-------------|
| `get_version()` | 11–19 | Gets version from package or pyproject.toml |
| `if __name__ == "__main__"` | 247–248 | Calls `main()` |

### 5.3 CLI Options for `run` command

| Option | Short | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--working-dir` | `-d` | `"."` | str | Working directory |
| `--max-turns` | `-t` | `20` | int | Max agent turns |
| `--wall-time` | `-w` | `1800.0` | float | Wall time limit (seconds) |
| `--memory-mode` | `-m` | `"isolated"` | Choice: isolated/scoped/shared | Memory scope |
| `--acceptance` | `-a` | () | multiple str | Acceptance criteria |
| `--model` | `-M` | `None` | str | Model override |
| `--max-depth` | — | `3` | int | Max sub-agent nesting |
| `--summary-only` | — | `False` | flag | Return only summary |

### 5.4 CLI Options for `session` command

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--new-id` | `-n` | `None` | New session ID (rename/fork) |
| `--working-dir` | `-d` | `None` | Working dir (fork) |
| `--status` | `-s` | `None` | Filter by status (active/idle/closed) |
| `--limit` | `-l` | `20` | Max results |

---

## 6. Slash Commands Registry (Complete)

| Command | Aliases | Lines (tui.py) | Category |
|---------|---------|----------------|----------|
| `/help` | `/h` | 957 | Meta |
| `/new` | `/n` | 961 | Session |
| `/clear` | — | 972 | Display |
| `/expand` | `/e` | 980 | Display |
| `/collapse` | `/a` | 985 | Display |
| `/quit` | `/q` | 990 | Meta |
| `/sessions` | — | 994 | Session |
| `/status` | — | 1002 | Meta |
| `/interrupt` | — | 1015 | Agent |
| `/compact` | — | 1019 | Agent |
| `/copy` | — | 1034 | Display |
| `/version` | — | 1042 | Meta |
| `/auto` | — | 1052 | Agent |
| `/tokens` | — | 1056 | Meta |
| `/model` | — | 1083 | Meta |
| `/threads` | — | 1096 | Session |
| `/theme` | — | 1110 | Display |
| `/undo` | — | 1120 | Agent |
| `/redo` | — | 1131 | Agent |
| `/skills` | — | 1142 | Meta |
| `/skill <name>` | — | 1156 | Meta |

---

## 7. Key Bindings Registry (Complete)

### NexusApp BINDINGS (tui.py, lines 299–308)

| Keys | Action Method | Label | Shown |
|------|---------------|-------|-------|
| `q` | `action_quit` | "Quit" | Yes |
| `escape` | `action_quit` | "Quit" | No |
| `c` | `action_clear` | "Clear" | Yes |
| `ctrl+c` | `action_interrupt` | "Interrupt" | Yes |
| `ctrl+u` | `action_interrupt` | "Interrupt" | Yes |
| `e` | `action_expand_all` | "Expand" | Yes |
| `a` | `action_collapse_all` | "Collapse" | Yes |
| `ctrl+underscore` | `action_toggle_auto_approve` | "Auto-approve" | No |

### ChatInput BINDINGS (chat_input.py, lines 75–78)

| Keys | Action Method | Label | Shown |
|------|---------------|-------|-------|
| `enter` | `action_submit` | "Submit" | No |
| `escape` | `action_cancel` | "Cancel" | No |
| `tab` | `action_autocomplete` | "Autocomplete" | No |

---

## 8. Theme/Color System

### 8.1 Inline Themes (tui.py `NEXUS_THEMES`, lines 53–59)

| Name | header_bg | accent | bg |
|------|-----------|--------|-----|
| midnight | `#1f2937` | `#10b981` | `#111827` |
| ocean | `#0e4d6e` | `#38bdf8` | `#0c1929` |
| forest | `#14532d` | `#4ade80` | `#052e16` |
| sunset | `#7c2d12` | `#fb923c` | `#1c1010` |
| lavender | `#3b3864` | `#a78bfa` | `#1a1830` |

### 8.2 Registered Themes (colors.py + registry.py)

| Theme Name | Instance Variable | Line (colors.py) |
|------------|-------------------|------------------|
| `nexus-dark` | `DARK_COLORS` | 205 |
| `tokyo-night` | `TOKYO_NIGHT_COLORS` | 213 |
| `rose-pine` | `ROSE_PINE_COLORS` | 221 |
| `solarized-dark` | `SOLARIZED_DARK_COLORS` | 229 |
| `catppuccin-mocha` | `CATPPUCCIN_MOCHA_COLORS` | 237 |
| `gruvbox-dark` | `GRUVBOX_DARK_COLORS` | 245 |
| `nord` | `NORD_COLORS` | 253 |

### 8.3 Semantic Color Tokens (`ThemeColors` dataclass, lines 171–200)

**Backgrounds (4):** `bg`, `bg_panel`, `bg_surface`, `bg_hover`
**Text (4):** `text`, `text_secondary`, `text_muted`, `text_dim`
**Accent (3):** `accent`, `accent_hover`, `accent_light`
**Status (4):** `success`, `warning`, `error`, `error_bg`
**Borders (3):** `border`, `border_subtle`, `border_focus`

### 8.4 CSS Variables (registry.py `get_theme_css()`, lines 22–46)

20 variables mapped from `ThemeColors` → CSS custom properties for Textual.

### 8.5 Widget CSS Class Reference

| Widget | CSS Selector | Key Variables/Colors |
|--------|-------------|---------------------|
| `UserMessage` | `UserMessage` | `$primary` (border-left) |
| `AssistantMessage` | `AssistantMessage` | transparent bg |
| `ToolCallMessage` | `ToolCallMessage` | `$warning` (border-left), `$accent-light` (hover) |
| `AppMessage` | `AppMessage` | `$text-muted` |
| `ErrorMessage` | `ErrorMessage` | `$error` (color + border) |
| `WelcomeBanner` | `WelcomeBanner` | `$surface` bg, `$border` border |
| `ChatInput` | `ChatInput` | `$surface` bg, `$border` → `$border-focus` |
| `StatusBar` | `StatusBar` | `$surface` bg, `$text-secondary`, `$text-muted`, `$warning` |
| `ModelLabel` | `ModelLabel` | `$text-muted` |
| `SpinnerLabel` | `#status-bar SpinnerLabel` | (inherits from #status-bar) |

---

## 9. Widget Package Exports (`__init__.py`)

**`__all__`** (lines 16–32):

- Messages: `UserMessage`, `AssistantMessage`, `ToolCallMessage`, `AppMessage`, `ErrorMessage`, `WelcomeBanner`
- Status: `StatusBar`, `ModelLabel`
- Input: `ChatInput`
- Theme: `ThemeColors`, `get_css_variable_defaults`

---

## 10. WebSocket Event Flow Diagram

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   TUI        │  WS     │   Server     │  Agent  │   Session   │
│  (tui.py)    │◄───────►│ (server.py)  │◄───────►│(session.py) │
└─────────────┘         └──────────────┘         └─────────────┘

Client → Server:
  user_input ──────────────────► Session.send()
  approval  ──────────────────► Session.approve()
  interrupt ──────────────────► Session.interrupt()
  compact   ──────────────────► Session.pre_compaction_flush()
  list_sessions ──────────────► session_repo.list_sessions()
  close     ──────────────────► Session.close()

Server → Client:
  session_status ◄──────────── session.status
  thinking      ◄──────────── ThinkingEvent
  tool_call     ◄──────────── _handle_message_token (AIMessageChunk)
  tool_result   ◄──────────── _handle_message_token (ToolMessage)
  tool_error    ◄──────────── (server-emitted)
  approval_request ◄───────── (server-emitted)
  response_chunk ◄─────────── _handle_message_token (text chunks)
  response      ◄──────────── ResponseEvent (final)
  error         ◄──────────── ErrorEvent
  session_closed ◄─────────── Session.close() enqueue
  session_list  ◄──────────── session_repo.list_sessions()
  compact_result ◄─────────── Session.pre_compaction_flush()
```

---

*End of Semantic Architecture Index — 10 files, ~4,833 lines indexed.*
