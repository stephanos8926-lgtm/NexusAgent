# TUI Semantic Map — NexusAgent

> Generated: 2026-07-18
> Scope: Complete NexusAgent TUI subsystem
> Files mapped: 12 source files across 3 packages

---

## 1. Architecture Overview

The TUI subsystem is split across three packages:

```
interfaces/          ← Orchestration layer (app, widgets, formatters)
├── tui.py           ← NexusApp — main Textual application (953L)
├── tui_widgets.py   ← SpinnerLabel, Breakpoint, ApprovalModal, ErrorModal (231L)
└── tui_formatters.py← render_markdown, format_tool_result, truncate (296L)

widgets/             ← Reusable widget library (defined but UNUSED by TUI)
├── messages/        ← 6 message widget classes (extracted Phase 4)
│   ├── welcome.py   ← WelcomeBanner
│   ├── error.py     ← ErrorMessage
│   ├── app.py       ← AppMessage
│   ├── tool.py      ← ToolCallMessage
│   ├── assistant.py ← AssistantMessage
│   └── user.py      ← UserMessage
├── status.py        ← StatusBar, ModelLabel, GitStatus, ContextWindowBar, BrailleSpinner
├── chat_input.py    ← ChatInput (TextArea subclass)
└── theme/           ← 7-color theme system (extracted Phase 2)
    ├── colors.py    ← ThemeColors dataclass + 7 theme instances
    └── registry.py  ← CSS variable generation + theme registration
```

**Critical finding:** The `widgets/` package (messages, status, chat_input, theme) is **entirely disconnected** from the running TUI. NexusApp composes its own UI inline using basic Textual primitives (Header, RichLog, Static, Input, Footer, Collapsible). The widget classes exist as a designed-but-unintegrated layer.

---

## 2. File-by-File Analysis

### 2.1 `interfaces/tui.py` — NexusApp (953L)

**Purpose:** Main Textual application class. Composes the TUI layout, manages WebSocket connection, routes events to display helpers.

**Key classes:**
- `NexusApp(App)` — L89-953 — Main application

**Key methods:**
| Method | Line | Purpose |
|--------|------|---------|
| `compose()` | 243 | Builds layout: Header, ScrollableContainer(RichLog), Static(streaming), SpinnerLabel, 2x Static(badge/queue), Input, Footer |
| `__init__()` | 259 | Initializes state: yolo, breakpoint, resize, no_color |
| `on_mount()` | 266 | Sets up widget refs, state vars, greeting, WS task, SIGWINCH |
| `_install_sigwinch()` | 296 | Installs SIGWINCH handler for responsive layout |
| `_check_sigwinch()` | 312 | Polls pending flag, delegates to `_sigwinch_handler` |
| `_restore_sigwinch()` | 318 | Restores original signal handler |
| `_is_ascii_terminal()` | 327 | Detects ASCII-only terminal (NO_COLOR, TERM=dumb, no COLORTERM) |
| `_show_greeting()` | 339 | Writes ASCII art banner + command hints to RichLog |
| `_ws_loop()` | 371 | WebSocket connect loop: send_messages + receive_events gather |
| `_handle_event()` | 416 | Main event router (10 event types) |
| `_write_tool_result()` | 511 | Formats + displays tool output (inline or collapsible) |
| `_write_response()` | 538 | Writes final agent response with markdown |
| `_handle_slash_command()` | 551 | Routes 18 slash commands |
| `_apply_theme()` | 782 | Applies NEXUS_THEMES color set |
| `_show_help()` | 788 | Writes help text to log |
| `_write_response_chunk()` | 819 | Appends streaming token to in-progress response widget |
| `_finalize_response()` | 826 | Finalizes streaming: writes to log, clears streaming widget |
| `_process_next_in_queue()` | 848 | Dequeues next pending message |
| `_update_queue_status()` | 858 | Updates queue status display |
| `_send_approval()` | 865 | Sends approval/rejection over WebSocket |
| `on_input_submitted()` | 877 | Handles Input.Submitted: slash commands, queue, or send |
| `action_clear()` | 904 | Clears log + collapsibles + greeting |
| `action_quit()` | 909 | Puts None sentinel, cancels WS task, exits |
| `action_interrupt()` | 915 | Sends interrupt over WebSocket |
| `action_expand_all()` | 923 | Expands all Collapsible widgets |
| `action_collapse_all()` | 927 | Collapses all Collapsible widgets |
| `action_toggle_auto_approve()` | 931 | Toggles auto-approve mode + badge display |
| `main()` | 947 | Entry point: NexusApp(yolo=yolo).run() |

**Dependencies:**
- `textual.app.App`, `ComposeResult`, `ModalScreen`, `Binding`
- `textual.containers.Horizontal`, `ScrollableContainer`, `Vertical`
- `textual.reactive.reactive`
- `textual.timer.Timer`
- `textual.widgets.Button`, `Collapsible`, `Footer`, `Header`, `Input`, `RichLog`, `Static`
- `websockets` (WebSocket client)
- `nexusagent.infrastructure.config.settings`
- `nexusagent.interfaces.tui_widgets` (SpinnerLabel, Breakpoint, ApprovalModal, ErrorModal, NO_COLOR, _get_terminal_size, _sigwinch_handler, classify_breakpoint, debounce_resize, is_no_color)
- `nexusagent.interfaces.tui_formatters` (format_arg_value, format_tool_output_generic, format_tool_result_for_display, render_markdown, truncate, truncate_output, _escape)
- `nexusagent.skills` (load_all_skills, get_skills_summary, get_skill_content) — only for `/skills` and `/skill` commands

**CSS classes used (defined in `CSS` string, L101-241):**
| CSS Selector | Line | Purpose |
|-------------|------|---------|
| `Screen` | 102 | Base layer, background |
| `#log-container` | 108 | ScrollableContainer wrapper |
| `#conversation-log` | 115 | RichLog widget |
| `#streaming-response` | 129 | Streaming response Static |
| `#input-area` | 145 | Input widget + focus |
| `#status-bar` | 157 | SpinnerLabel container |
| `#auto-approve-badge` | 166 | Auto-approve indicator |
| `#queue-status` | 175 | Queue status text |
| `Collapsible` | 183 | Tool result collapsibles |
| `#approval-dialog` | 203 | Approval modal container |
| `#approval-title` | 211 | Approval modal title |
| `#approval-args` | 216 | Approval modal args |
| `#approval-buttons` | 220 | Approval modal buttons |
| `#approval-scroll` | 227 | Approval modal scroll |
| `Header` | 232 | Header styling |
| `Footer` | 237 | Footer styling |

**Bindings (L90-99):**
| Key | Action | Display |
|-----|--------|---------|
| `q` | `action_quit` | Quit |
| `escape` | `action_quit` | Quit (hidden) |
| `c` | `action_clear` | Clear |
| `ctrl+c` | `action_interrupt` | Interrupt |
| `ctrl+u` | `action_interrupt` | Interrupt |
| `e` | `action_expand_all` | Expand |
| `a` | `action_collapse_all` | Collapse |
| `ctrl+underscore` | `action_toggle_auto_approve` | Auto-approve (hidden) |

---

### 2.2 `interfaces/tui_widgets.py` — Widgets & Modals (231L)

**Purpose:** Extracted from tui.py to reduce the monolith. Contains animated spinner, responsive breakpoints, approval modal, error modal, and SIGWINCH utilities.

**Key classes:**
| Class | Line | Purpose |
|-------|------|---------|
| `SpinnerLabel(Horizontal)` | 34 | Animated spinner + text label for status bar |
| `Breakpoint(enum.Enum)` | 90 | Terminal width breakpoints: WIDE, STANDARD, NARROW, TOO_SMALL |
| `ApprovalModal(ModalScreen[bool])` | 186 | Tool call approval dialog |
| `ErrorModal(ModalScreen[None])` | 216 | Error display dialog (⚠ imported but NEVER used in tui.py) |

**Key functions:**
| Function | Line | Purpose |
|----------|------|---------|
| `classify_breakpoint(width)` | 104 | Classifies terminal width into Breakpoint enum |
| `is_no_color()` | 121 | Checks NO_COLOR env var per no-color.org spec |
| `debounce_resize(state, time, debounce)` | 131 | Debounces resize events (0.2s default) |
| `_get_terminal_size()` | 147 | Returns (columns, rows), falls back to (80, 24) |
| `_sigwinch_handler(app)` | 156 | Handles SIGWINCH with debounce + breakpoint classification |

**Key constants:**
| Constant | Line | Value |
|----------|------|-------|
| `SPINNER_CHARS` | 31 | `"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"` |
| `NO_COLOR` | 118 | `"NO_COLOR" in os.environ` |
| `_WIDE_THRESHOLD` | 99 | 120 |
| `_STANDARD_THRESHOLD` | 100 | 80 |
| `_NARROW_THRESHOLD` | 101 | 60 |
| `_DEFAULT_DEBOUNCE_SECONDS` | 128 | 0.2 |

**SpinnerLabel details (L34-83):**
- `spinner_chars = SPINNER_CHARS` — class-level
- `tick = reactive(0)` — reactive property
- `compose()` → yields `Static(id="spinner-icon")`, `Static(id="spinner-text")`
- `set_text(text, spinning)` — starts/stops 0.1s interval timer
- `watch_tick()` — called on tick change, updates display
- `update_display()` — queries spinner-icon and spinner-text, updates both

**ApprovalModal details (L186-208):**
- `compose()` → Vertical(#approval-dialog) > Static(#approval-title), ScrollableContainer(#approval-scroll) > Static(#approval-args), Horizontal(#approval-buttons) > 3 Buttons
- `on_button_pressed()` → approve dismiss(True), reject/cancel dismiss(False)
- Buttons: "✓ Approve" (id="approve", variant="success"), "✗ Reject" (id="reject", variant="error"), "Cancel" (id="cancel")

**ErrorModal details (L216-231):**
- Uses same CSS IDs as ApprovalModal (#approval-dialog, #approval-title, #approval-args, #approval-buttons)
- Single "OK" button (id="ok", variant="primary")
- **⚠ DEAD CODE:** Imported in tui.py (line 54) but never instantiated or pushed as a screen

---

### 2.3 `interfaces/tui_formatters.py` — Formatters (296L)

**Purpose:** All output formatting, markdown rendering, truncation, and escaping for the TUI.

**Key functions:**
| Function | Line | Purpose |
|----------|------|---------|
| `render_markdown(text, code_blocks=True)` | 22 | Unified markdown→RichLog markup renderer |
| `format_tool_result_for_display(tool_name, success, output, max_chars=400)` | 71 | Per-tool dispatch formatter |
| `format_shell_output(output)` | 111 | Shell: exit code + truncated stdout (15 lines) |
| `format_read_file_output(output)` | 136 | Read: line count + preview (12 lines) |
| `format_write_file_output(output, tool_name)` | 151 | Write/edit: success indicator + path |
| `format_git_output(output, tool_name)` | 162 | Git: command + result (10 lines) |
| `format_search_output(output)` | 173 | Search: result count + top URLs (3 max) |
| `format_subagent_output(output)` | 184 | Subagent: worker ID + status |
| `format_tool_output_generic(output, max_chars=400)` | 194 | Default: JSON parsing → human-readable |
| `truncate_output(output, max_chars=400)` | 251 | Head/tail truncation with char count |
| `truncate(text, max_len)` | 260 | Simple truncation with ellipsis |
| `format_arg_value(value)` | 267 | Format tool argument for display |
| `_escape(text)` | 278 | Escape RichLog markup (`[` → `\[`, `]` → `\]`) |
| `contextlib_suppress` | 285 | Minimal context manager (avoids import) |

**`render_markdown` details (L22-63):**
- Extracts fenced code blocks (```lang\n...```) with placeholders
- Inline code → `[reverse]...[/reverse]`
- Bold (`**...**`) → `[b]...[/b]`
- Italic (`*...*`) → `[i]...[/i]`
- Restores code blocks with dim styling, truncates to 20 lines

**`format_tool_result_for_display` dispatch (L71-108):**
- Exact match: `run_shell`, `run_shell_streaming`, `shell`, `read_file`, `read_multiple_files`, `write_file`, `write_multiple_files`, `edit_file`, `apply_patch`
- Prefix match: `tool_name.startswith("git_")`
- Exact match: `search_web`, `search_local_docs`
- Exact match: `spawn_subagent`
- Fallback: `format_tool_output_generic`

---

### 2.4 `widgets/status.py` — Status Bar (367L)

**Purpose:** Status bar widget with responsive layout, git status detection, context window bar, and braille spinner. **⚠ NOT USED by NexusApp** (which uses SpinnerLabel from tui_widgets.py instead).

**Key classes:**
| Class | Line | Purpose |
|-------|------|---------|
| `ModelLabel(Static)` | 36 | Model name with smart truncation |
| `StatusBar(Horizontal)` | 80 | Full status bar: spinner + message + CWD + branch + tokens + model |
| `GitStatus` | 249 | Git working tree status detection (static methods) |
| `ContextWindowBar` | 302 | Context window usage bar with color thresholds |
| `BrailleSpinner` | 349 | Braille dot spinner animation frames |

**StatusBar CSS classes (L86-122):**
| Selector | Line | Purpose |
|----------|------|---------|
| `StatusBar` | 87 | Container: height 1, dock bottom, $surface bg |
| `StatusBar .status-message` | 93 | 1fr width, $text-secondary |
| `StatusBar .status-cwd` | 99 | auto width, $text-muted |
| `StatusBar .status-branch` | 105 | auto width, $text-muted |
| `StatusBar .status-tokens` | 111 | auto width, $text-muted |
| `StatusBar .status-spinner` | 117 | width 2, $warning |

**StatusBar responsive behavior (L166-180):**
- Width > 120: show everything
- Width 80-120: hide branch
- Width 60-80: hide branch + CWD
- Width < 60: show only status + spinner

**StatusBar methods:**
| Method | Line | Purpose |
|--------|------|---------|
| `set_status(msg)` | 186 | Update status message |
| `set_cwd(cwd)` | 190 | Update CWD display |
| `set_branch(branch)` | 194 | Update git branch |
| `set_tokens(count)` | 198 | Update token count |
| `set_model(provider, model)` | 202 | Update model label |
| `set_spinner(spinning)` | 207 | Start/stop spinner |
| `tick_spinner()` | 213 | Advance spinner frame |

**GitStatus states (L249-296):** `clean`, `dirty`, `staged`, `None` (not a git repo)

**ContextWindowBar thresholds (L302-343):**
- < 70%: `#10B981` (green/safe)
- 70–90%: `#EB8B46` (amber/warn)
- > 90%: `#F7768E` (red/danger)

**⚠ Duplicate NO_COLOR (L226):** `bool(os.environ.get("NO_COLOR"))` — non-standard per no-color.org. The canonical version is in `tui_widgets.py` (line 118): `"NO_COLOR" in os.environ`.

---

### 2.5 `widgets/chat_input.py` — Chat Input (215L)

**Purpose:** Multiline chat input with history, autocomplete, image paste. **⚠ NOT USED by NexusApp** (which uses `Input` widget directly).

**Key class:** `ChatInput(TextArea)` — L65

**Key features:**
- Enter to submit, Shift+Enter for newline
- Up/Down for command history (persisted to `~/.nexusagent/history.json`)
- Tab for slash command autocomplete
- Image path/URL extraction from text
- `Submitted(text, images)` message posted on submit

**CSS (L81-97):**
| Selector | Line | Purpose |
|----------|------|---------|
| `ChatInput` | 82 | auto height, min 3, max 15, $surface bg, $border |
| `ChatInput:focus` | 91 | $border-focus |
| `ChatInput .hint` | 94 | $text-muted |

**Bindings (L75-79):**
| Key | Action |
|-----|--------|
| `enter` | `action_submit` |
| `escape` | `action_cancel` |
| `tab` | `action_autocomplete` |

**⚠ SLASH_COMMANDS mismatch (L28-34):** Only lists 5 commands: `/help`, `/logs`, `/theme`, `/clear`, `/model`. But tui.py handles 18+ commands including `/new`, `/sessions`, `/expand`, `/collapse`, `/quit`, `/compact`, `/copy`, `/version`, `/tokens`, `/threads`, `/auto`, `/undo`, `/redo`, `/skills`, `/skill`, `/interrupt`, `/status`. The autocomplete will not suggest most valid commands.

---

### 2.6 `widgets/messages/` — Message Widgets (6 files)

**Purpose:** Typed message widgets for structured conversation display. **⚠ ALL DEAD CODE** — defined but never imported or used anywhere in the codebase.

#### `messages/user.py` (41L)
- `UserMessage(Static)` — L12 — Left border accent ($primary), timestamp prefix
- CSS: `border-left: wide $primary`, transparent bg, auto height

#### `messages/assistant.py` (130L)
- `AssistantMessage(Static)` — L11 — Streaming support via `append_token()` + `finalize()`
- Custom markdown parser (`_parse_markdown`) for **bold**, *italic*, `code`
- Uses `Content.assemble()` for styled rendering
- `append_token()` uses `self.app.call_next(self._render_buffer)` for per-token repaint

#### `messages/tool.py` (192L)
- `ToolCallMessage(Static)` — L23 — Tool call with collapsible output
- Status icons: ⚙ running, ✔ success, ✘ failed
- Auto-collapse threshold: 4+ lines or 300+ chars
- Syntax detection from fenced code blocks
- Methods: `update_status()`, `update_output()`, `toggle_collapse()`

#### `messages/app.py` (34L)
- `AppMessage(Static)` — L11 — System/app messages, dim italic styling

#### `messages/error.py` (34L)
- `ErrorMessage(Static)` — L11 — Error display with $error color + left border

#### `messages/welcome.py` (47L)
- `WelcomeBanner(Static)` — L12 — Compact welcome banner with session info

---

### 2.7 `widgets/theme/` — Theme System (3 files)

**Purpose:** 7-color theme system with semantic CSS variables. **⚠ NOT USED by NexusApp** (which uses hardcoded `NEXUS_THEMES` dict in tui.py).

#### `theme/colors.py` (273L)
- `ThemeColors(frozen dataclass)` — L171 — 18 semantic color fields
- 7 theme instances: `DARK_COLORS`, `TOKYO_NIGHT_COLORS`, `ROSE_PINE_COLORS`, `SOLARIZED_DARK_COLORS`, `CATPPUCCIN_MOCHA_COLORS`, `GRUVBOX_DARK_COLORS`, `NORD_COLORS`
- `THEME_REGISTRY` — L263 — dict mapping theme name → ThemeColors
- `ALL_THEMES` — L273 — list of all 7 theme names

#### `theme/registry.py` (68L)
- `get_theme_colors(name)` — L14 — Returns ThemeColors for name
- `get_theme_css(name)` — L19 — Returns CSS variable dict (28 variables)
- `get_css_variable_defaults()` — L49 — Returns nexus-dark CSS
- `register_themes(app)` — L54 — Registers all 7 themes with Textual app

**CSS variables generated (L22-46):**
Standard: `background`, `surface`, `primary`, `secondary`, `success`, `warning`, `error`, `text`, `text-muted`, `text-secondary`
App-specific: `border`, `border-subtle`, `border-focus`, `bg-surface`, `bg-hover`, `error-muted`, `accent-light`
Extended: `text-dim`, `accent-hover`, `panel`

---

## 3. Event Flow — Full Trace

### 3.1 WebSocket Message → Display

```
WebSocket raw text
  → json.loads(raw)                    [tui.py:L392]
  → self._handle_event(event)          [tui.py:L395]
```

### 3.2 Event Type Routing (`_handle_event`, L416-507)

| Event Type | Handler | Display Helper | Widget Updated |
|------------|---------|----------------|----------------|
| `session_status` | L419-420 | — | *(no-op: `pass`)* |
| `thinking` | L422-428 | `_escape(content)` | `log_widget.write()` |
| `tool_call` | L430-449 | `format_arg_value()` + `truncate()` | `log_widget.write()` + `status_widget.set_text(spinning=True)` |
| `tool_result` | L451-456 | `_write_tool_result()` → `format_tool_result_for_display()` | `log_widget.write()` or `log_widget.mount(Collapsible)` |
| `tool_error` | L458-466 | `_escape(error)` | `log_widget.write()` + `status_widget.set_text()` |
| `approval_request` | L468-475 | `ApprovalModal` screen | `push_screen_wait()` → `_send_approval()` |
| `response_chunk` | L477-480 | `_write_response_chunk()` | `_streaming_widget.update()` |
| `response` | L482-494 | `_finalize_response()` → `render_markdown()` | `log_widget.write()` + `_streaming_widget.update("")` |
| `error` | L496-501 | `_escape(message)` | `log_widget.write()` + `status_widget.set_text()` |
| `session_closed` | L503-507 | — | `log_widget.write()` + `status_widget.set_text()` |

### 3.3 Detailed Flow: `tool_call` Event

```
event = {"type": "tool_call", "tool": "run_shell", "args": {"cmd": "ls"}, "call_id": "abc"}
  → tool = "run_shell"
  → args = {"cmd": "ls"}
  → self._last_tool_name = "run_shell"                    [L433]
  → args_str = "cmd=[white]ls[/white]"                    [L434-440]
  → log_widget.write("[dim]⚙[/dim] [b orange]run_shell[/b orange](cmd=ls)")  [L441-444]
  → if self._auto_approve and tool != "tool_search":      [L446]
      → _send_approval(call_id, True)                     [L448]
  → status_widget.set_text("Running: run_shell", spinning=True)  [L449]
```

### 3.4 Detailed Flow: `tool_result` Event

```
event = {"type": "tool_result", "output": "file1\nfile2", "success": True, "call_id": "abc"}
  → tool_name = self._last_tool_name                     [L513]
  → max_chars = settings.agent.max_tool_output_chars      [L514]
  → display = format_tool_result_for_display(tool_name, True, output, max_chars)  [L516]
  → if len(display) <= max_chars:                         [L518]
      → log_widget.write("   [green]✓[/green] {display}") [L521-524]
  → else:                                                 [L525]
      → truncated = truncate_output(display, max_chars)   [L526]
      → collapsible = Collapsible(Static(truncated), ...) [L529-533]
      → self._collapsibles.append(collapsible)            [L534]
      → log_widget.mount(collapsible)                     [L535]
      → log_widget.scroll_end(animate=False)              [L536]
```

### 3.5 Detailed Flow: `response` Event (Final)

```
event = {"type": "response", "content": "Hello!", "tokens_used": 150}
  → content = "Hello!"                                    [L485]
  → self._finalize_response(content)                      [L486]
      → if self._streaming_response:                      [L828]
          → final = content                               [L829]
          → formatted = render_markdown(final, code_blocks=True)  [L831]
          → log_widget.write(formatted)                   [L837]
      → _streaming_widget.update("")                      [L843]
      → _streaming_response = ""                          [L844]
  → self._busy = False                                    [L487]
  → self._request_count += 1                              [L488]
  → self._total_tokens_used += 150                        [L492]
  → self._process_next_in_queue()                         [L493]
  → status_widget.set_text("Ready")                       [L494]
```

### 3.6 Input Flow

```
User types message + Enter
  → Input.Submitted event                                 [L877]
  → message = event.value.strip()                         [L879]
  → if message.startswith("/"):                           [L884]
      → _handle_slash_command(message)                    [L886]
  → elif self._busy:                                      [L889]
      → _pending_inputs.append(message)                   [L890]
      → log_widget.write("[dim]⏳ Queued: ...")           [L891]
  → else:                                                 [L896]
      → self._busy = True                                 [L896]
      → log_widget.write("[b cyan]You:[/b cyan] ...")    [L897]
      → status_widget.set_text("Thinking...", spinning=True)  [L899]
      → await self._input_queue.put(message)              [L900]
  → WS send_messages loop picks up from queue             [L382-387]
```

---

## 4. Slash Command Routing (`_handle_slash_command`, L551-780)

| Command | Line | Action |
|---------|------|--------|
| `/help`, `/h` | 557 | `_show_help()` |
| `/new`, `/n` | 561 | Clear + greeting |
| `/clear` | 572 | Clear + greeting |
| `/expand`, `/e` | 580 | Expand all collapsibles |
| `/collapse`, `/a` | 585 | Collapse all collapsibles |
| `/quit`, `/q` | 590 | `action_quit()` |
| `/sessions` | 594 | Show current session ID |
| `/status` | 602 | Show status: busy/ready, session, queue, auto-approve, tokens, requests |
| `/interrupt` | 615 | `action_interrupt()` |
| `/compact` | 619 | Send `{"type": "compact"}` over WS |
| `/copy` | 634 | Show "not available" message |
| `/version` | 642 | Show version, model, session, theme |
| `/auto` | 652 | `action_toggle_auto_approve()` |
| `/tokens` | 656 | Show token usage stats |
| `/model` | 683 | Show model + provider |
| `/threads` | 696 | Send `{"type": "list_sessions"}` over WS |
| `/theme` | 710 | Cycle NEXUS_THEMES + `_apply_theme()` |
| `/undo` | 720 | Send `{"type": "undo"}` over WS |
| `/redo` | 731 | Send `{"type": "redo"}` over WS |
| `/skills` | 742 | Load + list all skills |
| `/skill <name>` | 756 | Show skill content (20 lines) |
| *(unknown)* | 775 | Error message |

---

## 5. Theme System — Two Parallel Systems

### 5.1 Active: `NEXUS_THEMES` dict (tui.py, L76-82)

Hardcoded 5 themes used by `/theme` cycling:

```python
NEXUS_THEMES = [
    {"name": "midnight", "header_bg": "#1f2937", "accent": "#10b981", "bg": "#111827"},
    {"name": "ocean", "header_bg": "#0e4d6e", "accent": "#38bdf8", "bg": "#0c1929"},
    {"name": "forest", "header_bg": "#14532d", "accent": "#4ade80", "bg": "#052e16"},
    {"name": "sunset", "header_bg": "#7c2d12", "accent": "#fb923c", "bg": "#1c1010"},
    {"name": "lavender", "header_bg": "#3b3864", "accent": "#a78bfa", "bg": "#1a1830"},
]
```

Applied via `_apply_theme()` (L782-786): sets `self.styles.background`, Header background + color.

### 5.2 Inactive: `widgets/theme/` package

7 full themes with 18 semantic color tokens each, CSS variable generation, and Textual `Theme` registration. **Never called by NexusApp.**

---

## 6. Issues Found

### 6.1 Dead Code / Unused Functions

| Item | Location | Notes |
|------|----------|-------|
| `ErrorModal` class | tui_widgets.py:L216 | Imported in tui.py:L54 but never instantiated |
| `session_status` handler | tui.py:L419-420 | `pass` — no-op, does nothing |
| All message widgets | `widgets/messages/*.py` | 6 classes, never imported anywhere |
| `StatusBar` class | `widgets/status.py:L80` | Never used; NexusApp uses SpinnerLabel from tui_widgets |
| `ChatInput` class | `widgets/chat_input.py:L65` | Never used; NexusApp uses `Input` widget directly |
| `ContextWindowBar` class | `widgets/status.py:L302` | Never instantiated anywhere |
| `BrailleSpinner` class | `widgets/status.py:L349` | Never instantiated anywhere |
| `register_themes()` | `widgets/theme/registry.py:L54` | Never called; NexusApp uses hardcoded NEXUS_THEMES |
| `get_theme_css()`, `get_theme_colors()` | `widgets/theme/registry.py` | Never called |
| `GitStatus` class | `widgets/status.py:L249` | Never called (StatusBar doesn't use it) |
| `ModelLabel` class | `widgets/status.py:L36` | Composed inside StatusBar but StatusBar is unused |

### 6.2 Orphaned CSS Rules

| CSS Selector | Defined In | Used By |
|-------------|-----------|---------|
| `StatusBar` + sub-selectors | `widgets/status.py:L86-122` | **Orphaned** — StatusBar not used |
| `ChatInput` + sub-selectors | `widgets/chat_input.py:L81-97` | **Orphaned** — ChatInput not used |
| `UserMessage` | `widgets/messages/user.py:L20-30` | **Orphaned** |
| `AssistantMessage` | `widgets/messages/assistant.py:L19-28` | **Orphaned** |
| `ToolCallMessage` | `widgets/messages/tool.py:L42-53` | **Orphaned** |
| `AppMessage` | `widgets/messages/app.py:L17-26` | **Orphaned** |
| `ErrorMessage` | `widgets/messages/error.py:L17-26` | **Orphaned** |
| `WelcomeBanner` | `widgets/messages/welcome.py:L20-30` | **Orphaned** |
| `ModelLabel` | `widgets/status.py:L44-50` | **Orphaned** (inside unused StatusBar) |

### 6.3 Broken Connections

| Issue | Details |
|-------|---------|
| `ErrorModal` imported but unused | tui.py:L54 imports it, but all error display goes through `log_widget.write()` directly |
| `SLASH_COMMANDS` mismatch | `chat_input.py` lists 5 commands; `tui.py` handles 18+. Autocomplete won't suggest `/new`, `/quit`, `/expand`, `/collapse`, `/sessions`, `/status`, `/compact`, `/copy`, `/version`, `/tokens`, `/model`, `/threads`, `/auto`, `/undo`, `/redo`, `/skills`, `/skill`, `/interrupt` |
| Duplicate `NO_COLOR` | `tui_widgets.py:L118` (correct: `"NO_COLOR" in os.environ`) vs `status.py:L226` (incorrect: `bool(os.environ.get("NO_COLOR"))`) |
| Duplicate `SPINNER_CHARS` | `tui_widgets.py:L31` (canonical) vs `status.py:L125` (copy inside StatusBar) |
| `widgets/` package entirely disconnected | No module outside `widgets/` imports from it. The package exists as a designed-but-unintegrated layer |

### 6.4 Potential Bugs

| Issue | Location | Severity |
|-------|----------|----------|
| `_handle_slash_command` unused variable | tui.py:L555 — `parts[1:] if len(parts) > 1 else []` — result is discarded (should be `args = ...`) | Low |
| `tool_search` auto-approve skip | tui.py:L446 — `tool != "tool_search"` — no such tool exists in formatters; likely meant `search_web` or similar | Low |
| `_write_response` never called directly | tui.py:L538 — defined but only called from `_finalize_response` when `content` is set and `_streaming_response` is empty (L840). The method exists for potential direct use but is never invoked by the event handler | Info |
| `contextlib_suppress` non-standard | tui_formatters.py:L285 — reinvents `contextlib.suppress`; functional but unusual | Info |

### 6.5 Performance Notes

| Issue | Location | Impact |
|-------|----------|--------|
| `_write_response_chunk` string concatenation | tui.py:L821 — `self._streaming_response += content` — O(n²) for n tokens. Each token creates a new string. For long responses this is measurable. | Low-Medium |
| `_collapsibles` list growth | tui.py:L276 — `self._collapsibles` grows unboundedly within a session. Only cleared on `/clear` or `/new`. | Low |
| `_pending_inputs` queue | tui.py:L277 — `pop(0)` on list is O(n). For typical use (1-2 queued msgs) negligible. | Negligible |
| `render_markdown` regex | tui_formatters.py:L22 — Multiple regex passes over same text. For typical agent responses (<10K chars) fine. | Negligible |
| `format_tool_output_generic` JSON parse | tui_formatters.py:L199 — Attempts `json.loads` on every non-matched tool output. Usually fails fast. | Negligible |

---

## 7. Dependency Graph

```
NexusApp (tui.py)
├── tui_widgets.py
│   ├── SpinnerLabel ← used by compose() as #status-bar
│   ├── Breakpoint ← used by _sigwinch_handler
│   ├── ApprovalModal ← used by approval_request handler
│   ├── ErrorModal ← imported but NEVER used ⚠
│   ├── NO_COLOR ← used by __init__
│   ├── _sigwinch_handler ← used by _check_sigwinch
│   ├── classify_breakpoint ← used by _sigwinch_handler
│   ├── debounce_resize ← used by _sigwinch_handler
│   └── is_no_color ← used by _is_ascii_terminal
├── tui_formatters.py
│   ├── format_arg_value ← used by tool_call handler
│   ├── format_tool_result_for_display ← used by _write_tool_result
│   ├── format_tool_output_generic ← fallback in dispatch
│   ├── render_markdown ← used by _write_response, _finalize_response
│   ├── truncate ← used by tool_call handler
│   ├── truncate_output ← used by _write_tool_result
│   └── _escape ← used by thinking, tool_error, error handlers
├── nexusagent.infrastructure.config.settings
│   ├── settings.client.api_key
│   ├── settings.server.api_port
│   ├── settings.agent.yolo
│   ├── settings.agent.max_tool_output_chars
│   └── settings.agent.default_model / primary_provider
├── nexusagent.skills (conditional)
│   ├── load_all_skills ← /skills command
│   ├── get_skills_summary ← /skills command
│   └── get_skill_content ← /skill command
└── textual framework
    ├── App, ComposeResult, ModalScreen, Binding
    ├── Horizontal, ScrollableContainer, Vertical
    ├── reactive, Timer
    ├── Button, Collapsible, Footer, Header, Input, RichLog, Static
    └── websockets (external)

widgets/ package (DISCONNECTED)
├── messages/ ← no external consumers
├── status.py ← no external consumers
├── chat_input.py ← no external consumers
└── theme/ ← no external consumers
```

---

## 8. Summary Statistics

| Metric | Value |
|--------|-------|
| Total TUI source files | 12 |
| Total lines of code | ~2,800 |
| Active files (used by NexusApp) | 3 (tui.py, tui_widgets.py, tui_formatters.py) |
| Inactive files (dead code) | 9 (all of widgets/) |
| Event types handled | 10 |
| Slash commands supported | 18+ |
| Theme systems | 2 (1 active, 1 inactive) |
| CSS selectors defined | ~30 (18 active, ~12 orphaned) |
| Modal screens | 2 (1 active, 1 dead) |
| Duplicate constants | 2 (NO_COLOR, SPINNER_CHARS) |
