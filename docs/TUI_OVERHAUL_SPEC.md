# NexusAgent TUI Overhaul — Research Synthesis & Implementation Spec

> **Date**: 2026-06-11
> **Sources**: DeepAgents CLI source (installed locally), tui-design skill, existing NexusAgent codebase maps, RESEARCH_TUI_AESTHETICS_VISUAL.md
> **Goal**: SURPASS deepagents — not match it

---

## 1. Executive Summary

The current NexusAgent TUI is architecturally broken. It uses `RichLog` (a monolithic text buffer) for all messages, wastes ~40% of terminal real estate on chrome, has broken word wrapping, no semantic color system, and no structured logging.

The fix is a **ground-up rewrite** modeled after DeepAgents CLI (which is installed locally and fully readable), but **surpassing it** with:
- Better real estate usage (no Header widget at all)
- Richer message types (tool calls with inline output, collapsible sections)
- Better streaming (true token-by-token with proper Textual widgets)
- Structured logging + in-app log viewer
- Community theme support (Catppuccin, Gruvbox, Nord) from day one
- Image input support (already built in our session layer)

---

## 2. DeepAgents Architecture Analysis

### 2.1 Layout (from `app.py` compose())

```
Screen (layout: vertical)
├── [Header] (optional, controlled by env var)
├── VerticalScroll (id="chat", height: 1fr)     ← chat area fills ALL space
│   ├── WelcomeBanner (height: auto)            ← single compact widget
│   └── Container (id="messages", layout: "stream")  ← O(1) append
│       ├── UserMessage (Static, border-left: $primary)
│       ├── AssistantMessage (Static, markdown)
│       ├── ToolCallMessage (Static, border-left: $tool)
│       ├── AppMessage (Static, dim italic)
│       └── ErrorMessage (Static, $error)
├── Container (id="bottom-app-container")
│   └── ChatInput (TextArea, min: 3, max: 25)
└── StatusBar (id="status-bar", height: 1, dock: bottom)
```

**Key insight**: The chat area uses `height: 1fr` — it fills ALL remaining space. The status bar is `dock: bottom` with `height: 1`. The input is `height: auto` with `min-height: 3`. Everything else is messages.

### 2.2 CSS (from `app.tcss`)

```css
Screen {
    layout: vertical;
    layers: base autocomplete;
}
* {
    scrollbar-size-vertical: 1;    /* thin scrollbars */
}
#chat {
    height: 1fr;                   /* fills remaining space */
    padding: 1 2;
    background: $background;
}
#messages {
    layout: stream;                /* O(1) append — Textual ≥5.2.0 */
    height: auto;
}
#input-area {
    height: auto;
    min-height: 3;
    max-height: 25;
}
#status-bar {
    height: 1;
    dock: bottom;
}
```

**Key insight**: `layout: stream` on `#messages` is critical — it enables O(1) append performance via incremental placement caching. Without it, appending messages gets slower as the chat grows.

### 2.3 Message Widgets (from `widgets/messages.py`)

Each message is a separate `Static` widget:

```python
class UserMessage(Static):
    DEFAULT_CSS = """
    UserMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0 0 0;
        background: transparent;
        border-left: wide $primary;
    }
    """
    def render(self) -> Content:
        # Returns styled Content with mode prefix, @mentions highlighted
```

**Key patterns:**
- `height: auto` — widget expands to fit content
- `padding: 0 1` — horizontal breathing room
- `margin: 1 0 0 0` — vertical spacing between messages
- `border-left: wide $primary` — visual indicator (semantic color)
- `render()` returns `Content` object with inline styling
- Mode-specific CSS classes: `-mode-shell`, `-mode-command`, `-ascii`

### 2.4 Theme System (from `theme.py`)

Semantic color tokens:
```
LC_DARK = "#11121D"      # Background — blue-tinted, not pure black
LC_CARD = "#1A1B2E"      # Surface / card
LC_BODY = "#C0CAF5"      # Body text
LC_BLUE = "#7AA2F7"      # Primary accent
LC_PURPLE = "#BB9AF7"    # Secondary accent
LC_GREEN = "#9ECE6A"     # Success
LC_AMBER = "#EB8B46"     # Warning
LC_PINK = "#F7768E"      # Error
LC_MUTED = "#545C7E"     # Muted text
LC_PANEL = "#25283B"     # Panel background
```

CSS variable mapping:
```python
def get_css_variable_defaults(*, dark=True, colors=None):
    return {
        "mode-bash": c.mode_bash,
        "mode-command": c.mode_command,
        "mode-incognito": c.mode_incognito,
        "skill": c.skill,
        "skill-hover": c.skill_hover,
        "tool": c.tool,
        "tool-hover": c.tool_hover,
    }
```

**Key insight**: They define colors as Python constants, then map them to CSS variables. This enables both Python-side styling (Rich markup) and CSS-side styling (TCSS) from the same source of truth.

### 2.5 Status Bar (from `widgets/status.py`)

```python
class StatusBar(Horizontal):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        background: $surface;
    }
    """
```

Layout (left to right):
```
[MODE] [AUTO-APPROVE] StatusMessage.......... CWD  branch  tokens  provider:model
```

- Mode indicator: colored pill (blue=shell, purple=command, teal=incognito)
- Auto-approve: colored pill (green=on, yellow=off)
- Status message: transient text
- CWD: truncated, hidden below width threshold
- Branch: hidden below width threshold
- Tokens: session token count
- Model: smart truncation (drop provider first, then left-truncate model)

### 2.6 What Makes DeepAgents Feel Polished

1. **O(1) message append** via `layout: stream`
2. **Semantic color system** — no hardcoded hex in widget CSS
3. **Thin scrollbars** (`scrollbar-size-vertical: 1`)
4. **Smart truncation** in status bar (model name, CWD)
5. **ASCII fallback** mode for legacy terminals
6. **iTerm2 cursor guide workaround** (disables visual glitch)
7. **gc.freeze()** before first paint (prevents GC pauses)
8. **Panic handler** that restores terminal state
9. **Welcome banner** as a single widget (not multiple write() calls)
10. **Click-to-timestamp** on messages (shows creation time)

---

## 3. How to SURPASS DeepAgents

### 3.1 Layout Improvements

| Aspect | DeepAgents | NexusAgent (Target) |
|--------|-----------|---------------------|
| Header | Optional (8-cell icon gutter) | **None** — saves 1 line |
| Welcome | WelcomeBanner widget | **Inline first message** — auto-removed |
| Chat area | `1fr` with padding `1 2` | `1fr` with padding `0 1` — more space |
| Input | `min: 3, max: 25` | `min: 3, max: 15` — more conservative |
| Status bar | `height: 1, dock: bottom` | Same, but **richer content** |
| Footer | Textual Footer widget | **None** — key hints in status bar |

### 3.2 Message Widget Improvements

| Aspect | DeepAgents | NexusAgent (Target) |
|--------|-----------|---------------------|
| UserMessage | Static text | **Rich Content** with @mentions, /commands |
| AssistantMessage | Static text | **Markdown rendering** with code blocks |
| ToolCallMessage | Static text | **Collapsible output** with syntax highlighting |
| AppMessage | Dim italic | **Spinner + dim italic** for thinking state |
| ErrorMessage | Red text | **Red + icon + collapsible details** |
| ImageMessage | N/A | **Image attachment display** (we already have the session layer) |

### 3.3 Streaming Improvements

DeepAgents uses a `TextualUIAdapter` that buffers tokens and calls `AssistantMessage.update()`. We should do the same but with:
- **Debounced updates** (max 30fps) to avoid overwhelming the TUI
- **Smooth scrolling** — auto-scroll only if user is at bottom
- **Cancel support** — Ctrl+C stops the stream mid-flight

### 3.4 Logging & Telemetry

DeepAgents has `configure_debug_logging()` but no in-app log viewer. We should:
- Log to `~/.nexusagent/logs/tui.log` (rotating, 5MB × 3)
- Add `/logs` command that shows recent log entries in a modal
- Track session metrics (tokens, tool calls, errors)
- Export metrics as JSON for analysis

### 3.5 Theme System

DeepAgents has 2 built-in themes (dark/light) + user-defined. We should:
- Ship with **Catppuccin Mocha**, **Gruvbox Dark**, **Nord**, **Tokyo Night**
- Support `NO_COLOR` env var
- Support light/dark auto-detection via OSC `]11;?`
- Allow runtime theme switching via `/theme`

---

## 4. Implementation Plan

### Phase 1: Widget System (New Files)

**`src/nexusagent/widgets/__init__.py`** — Package init
**`src/nexusagent/widgets/theme.py`** — Semantic color definitions
```python
# Dark palette (Tokyonight-inspired, like deepagents)
BG = "#11181C"           # Background — NOT pure black
SURFACE = "#1A1D23"      # Elevated surface
PRIMARY = "#7AA2F7"      # Blue accent
SECONDARY = "#BB9AF7"    # Purple accent
SUCCESS = "#9ECE6A"      # Green
WARNING = "#EB8B46"      # Amber
ERROR = "#F7768E"        # Pink
TEXT = "#C0C4C8"         # Primary text
TEXT_MUTED = "#545C7E"   # Secondary text
BORDER = "#25283B"       # Default border
```

**`src/nexusagent/widgets/messages.py`** — Message widget classes
- `UserMessage(Static)` — border-left: $primary, Content rendering
- `AssistantMessage(Static)` — markdown, streaming support
- `ToolCallMessage(Static)` — border-left: $warning, collapsible output
- `AppMessage(Static)` — dim italic, spinner
- `ErrorMessage(Static)` — $error, icon, collapsible
- `WelcomeBanner(Static)` — compact welcome
- `ImageMessage(Static)` — image attachment display

**`src/nexusagent/widgets/status.py`** — Status bar
- `StatusBar(Horizontal)` — mode, status, spinner, CWD, branch, tokens, model
- `ModelLabel(Widget)` — smart truncation
- Responsive behavior (hide CWD/branch on narrow terminals)

**`src/nexusagent/widgets/chat_input.py`** — Input widget
- `ChatInput(Vertical)` — TextArea + autocomplete popup
- History navigation (Up/Down)
- Slash command completion
- File path completion (@ trigger)
- Image paste support

### Phase 2: TUI Rewrite (Modify `tui.py`)

**New compose():**
```python
def compose(self) -> ComposeResult:
    # NO Header widget — saves 1 line
    with VerticalScroll(id="chat"):
        yield Container(id="messages")
    yield ChatInput(id="input-area")
    yield StatusBar(id="status-bar")
```

**New CSS:**
```css
Screen {
    layout: vertical;
    layers: base autocomplete;
}
* {
    scrollbar-size-vertical: 1;
}
#chat {
    height: 1fr;
    padding: 0 1;
    background: $background;
}
#messages {
    layout: stream;
    height: auto;
}
#input-area {
    height: auto;
    min-height: 3;
    max-height: 15;
}
#status-bar {
    height: 1;
    dock: bottom;
    background: $surface;
}
```

**Event handling changes:**
- `response_chunk` → append to current `AssistantMessage`
- `response` → finalize `AssistantMessage`
- `tool_call` → mount new `ToolCallMessage`
- `tool_result` → update `ToolCallMessage` with output
- `thinking` → mount `AppMessage` with spinner
- `error` → mount `ErrorMessage`

### Phase 3: Logging & Telemetry (New Files)

**`src/nexusagent/telemetry.py`** — Structured logging
```python
def setup_logging():
    handler = RotatingFileHandler(
        "~/.nexusagent/logs/tui.log",
        maxBytes=5_000_000,
        backupCount=3,
    )
    handler.setFormatter(Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logging.getLogger("nexusagent").addHandler(handler)
```

**Log viewer modal** — `/logs` command shows recent entries

### Phase 4: Polish

- Theme files for Catppuccin, Gruvbox, Nord
- ASCII fallback mode
- iTerm2 cursor guide workaround
- gc.freeze() before first paint
- Panic handler for terminal state restoration
- Responsive breakpoints

---

## 5. File Manifest

### New Files
- `src/nexusagent/widgets/__init__.py`
- `src/nexusagent/widgets/theme.py`
- `src/nexusagent/widgets/messages.py`
- `src/nexusagent/widgets/status.py`
- `src/nexusagent/widgets/chat_input.py`
- `src/nexusagent/telemetry.py`
- `themes/catppuccin-mocha.tcss`
- `themes/gruvbox-dark.tcss`
- `themes/nord.tcss`

### Modified Files
- `src/nexusagent/tui.py` — Complete rewrite
- `src/nexusagent/cli.py` — Add `--theme` option

### Preserved Files (for rollback)
- `src/nexusagent/tui_legacy.py` — Old TUI (renamed)

---

## 6. Success Criteria

- [ ] Chat area uses ≥70% of terminal height (currently ~40%)
- [ ] Word wrapping works for all text types (URLs, paths, code)
- [ ] Messages are individually styled widgets (not RichLog)
- [ ] Status bar shows model, tokens, CWD, branch in 1 line
- [ ] Streaming shows token-by-token in AssistantMessage
- [ ] No hardcoded hex codes — all colors via CSS variables
- [ ] Structured logging to file + in-app log viewer
- [ ] Works at 80×24 minimum
- [ ] No CSS parse errors
- [ ] All existing slash commands work
- [ ] No breaking changes to server or session layers
- [ ] 3 community themes ship out of the box
- [ ] Image input works end-to-end
