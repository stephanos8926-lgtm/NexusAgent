# TUI Aesthetics Research — Visual/UX Perspective

> Generated: 2026-07-19
> Perspective: Beauty, rendering quality, visual polish, typography, color theory
> Scope: Ink, Textual, Bubble Tea, Ratatui frameworks. Exemplar apps analysis.

---

## 1. Ink (React for CLI) — Visual Patterns

**Component Model:** React components render to terminal via custom reconciler + Yoga Flexbox layout.

### Layout Primitives

Ink's `Box` is the fundamental layout component (like `<div>` with `display: flex`):
- `flexDirection`, `justifyContent`, `alignItems` — standard Flexbox props
- `padding`, `margin` — spacing (numbers = character cells)
- `borderStyle` — "single" | "double" | "round" | "bold" | "classic"
- `borderColor` — any color string
- `width`, `height` — fixed dimensions or "100%" strings

### Text Styling

```tsx
<Text color="green" bold italic underline dimColor>
  Styled text
</Text>
```

Colors: ANSI names ("red", "green", "blue"), 256-color codes ("rgb(255,0,0)", "#ff0000").
Styles: bold, italic, underline, strikethrough, dimColor.

### Static Component (Log Pattern)

Ink's `Static` component renders permanently above everything else — like a persistent log. Once rendered, it can't be updated. This is perfect for:
- Status bars (fixed at bottom)
- Command history (persistent output)
- Help screens (overlaid)

### Transform Component

Applies transformations (gradient text, links) to rendered output. Works on string output after React render.

### Visual Patterns for Chat UIs

**Message Bubbles:**
```tsx
<Box flexDirection="column" marginBottom={1}>
  <Box borderStyle="round" borderColor="blue" paddingX={1}>
    <Text color="blue" bold>User:</Text> <Text>{message}</Text>
  </Box>
</Box>
```

**Status Bar:**
```tsx
<Box height={1} backgroundColor="#1e293b" paddingX={1}>
  <Text color="#94a3b8">Ready</Text>
  <Text color="#94a3b8" marginLeft={3}>Model: claude-4</Text>
  <Text color="#94a3b8" marginLeft={3}>Session: abc123</Text>
</Box>
```

**Tool Call Display:**
```tsx
<Box borderStyle="single" borderColor="#f59e0b" paddingX={1}>
  <Text color="#f59e0b" bold>→ {toolName}</Text>
  <Text color="#94a3b8">{args}</Text>
</Box>
```

---

## 2. Textual (Python) — Our Framework

NexusAgent uses Textual. Understanding its visual capabilities is critical.

### CSS Variable System

Textual themes generate ~18 semantic variables from 11 base colors:

| Variable | Default | Purpose |
|----------|---------|---------|
| `$primary` | Accent color | Active elements, selected items |
| `$accent` | Secondary accent | Highlights, focus borders |
| `$secondary` | Muted accent | Less prominent accents |
| `$foreground` | Text color | Primary text |
| `$background` | BG color | Main background |
| `$surface` | Slightly elevated | Cards, panels, input areas |
| `$boost` | Light overlay | Hover effects, active states |
| `$border` | Divider color | Borders, separators |
| `$border-focus` | Accent | Focused input borders |
| `$text` | Adaptive | Text (auto-contrast) |
| `$text-muted` | Faded | Labels, hints |
| `$text-disabled` | Very faded | Disabled elements |
| `$error` | Red | Errors, destructive actions |
| `$warning` | Yellow/amber | Warnings |
| `$success` | Green | Success states |

### Layout Patterns for AI Agent UIs

**Chat Layout (stream):**
```css
#chat { height: 1fr; padding: 0 1; }
#messages { layout: stream; height: auto; }
#input-area { height: auto; min-height: 3; max-height: 15; }
#status-bar { height: 1; dock: bottom; }
```

**Message Styling:**
```css
.user-message { background: $surface; border-left: solid $primary; padding: 0 1; margin: 1 0; }
.assistant-message { padding: 0 1; margin: 1 0; }
.tool-call { border: solid $accent; padding: 0 1; margin: 1 0; }
.error-message { border: solid $error; background: $error 10%; }
```

### Performance Patterns

1. **`gc.freeze()`** before first paint — prevents GC during rendering
2. **`layout: stream`** — O(1) append vs O(n) for vertical layout
3. **`dirty`** tracking — only re-renders changed widgets
4. **`update(layout=False)`** — skip layout recalc when dimensions unchanged
5. **`FIFOCache`** — widget rendering cache with configurable size
6. **`StylesCache`** — CSS style rendering cache with dirty tracking

### Animation System

```python
# Spinner animation
from textual.widgets import LoadingIndicator
# Built-in spinner with configurable style

# Custom animation via CSS
#my-widget { transition: background 200ms in-out; }
```

---

## 3. Bubble Tea (Go) — Visual Patterns

**Architecture:** Elm Architecture (Model-View-Update)

### Lip Gloss Styling System

Bubble Tea's companion library for visual styling:

```go
import "github.com/charmbracelet/lipgloss"

style := lipgloss.NewStyle().
    Bold(true).
    Foreground(lipgloss.Color("#7D56F4")).
    Background(lipgloss.Color("#1e1e2e")).
    Padding(1, 2).
    Border(lipgloss.RoundedBorder()).
    BorderForeground(lipgloss.Color("#89b4fa"))

// Horizontal join for side-by-side panels
lipgloss.JoinHorizontal(lipgloss.Top, leftPanel, rightPanel)
```

### Color System

Lip Gloss supports:
- ANSI colors (16)
- 256-color palette
- True color (24-bit hex)
- Adaptive colors (auto dark/light)
- Color blending and gradients

### Bubbles Component Library

Pre-built UI components:
- `textinput` — text input with cursor
- `viewport` — scrollable content area
- `spinner` — animated spinner
- `progress` — progress bar
- `table` — data table
- `list` — selectable list
- `textarea` — multi-line input

### Harmonica Animation

Spring-based animation for smooth transitions:
```go
import "github.com/charmbracelet/harmonica"

anim := harmonica.NewSpring(60, 20, 15) // FPS, stiffness, damping
```

### Visual Patterns for Chat UIs

**Message List (Viewport):**
```go
func (m model) View() string {
    var messages []string
    for _, msg := range m.messages {
        style := lipgloss.NewStyle().Padding(0, 1)
        if msg.role == "user" {
            style = style.Foreground(lipgloss.Color("#89b4fa"))
        }
        messages = append(messages, style.Render(msg.content))
    }
    return m.viewport.View()
}
```

**Status Bar:**
```go
statusStyle := lipgloss.NewStyle().
    Background(lipgloss.Color("#313244")).
    Foreground(lipgloss.Color("#a6e3a1")).
    Padding(0, 1).
    Width(m.width)
```

---

## 4. Ratatui (Rust) — Visual Patterns

**Architecture:** Immediate-mode rendering with constraint-based layout.

### Layout System

```rust
use ratatui::layout::{Constraint, Direction, Layout};

let chunks = Layout::default()
    .direction(Direction::Vertical)
    .constraints([
        Constraint::Min(3),      // Chat area
        Constraint::Length(3),    // Input area
        Constraint::Length(1),    // Status bar
    ])
    .split(frame.size());
```

### Styling

```rust
use ratatui::style::{Color, Modifier, Style};

let user_style = Style::default()
    .fg(Color::Blue)
    .add_modifier(Modifier::BOLD);

let assistant_style = Style::default()
    .fg(Color::Green);

let border_style = Style::default()
    .fg(Color::DarkGray);
```

### Widgets

- `Paragraph` — wrapped text display
- `List` — selectable list
- `Table` — data table
- `Gauge` — progress bar
- `Tabs` — tab bar
- `Block` — bordered container
- `Sparkline` — inline chart
- `Chart` — full chart widget
- `Scrollbar` — scroll indicator

### Color Themes

Ratatui doesn't include a theme system — apps build their own. Common patterns:
- Catppuccin: 27 colors (rosewater #f5e0dc, flamingo #f2cdcd, pink #f5c2e7, mauve #cba6f7, red #f38ba8, peach #fab387, yellow #f9e2af, green #a6e3a1, teal #94e2d5, sky #89dceb, sapphire #74c7ec, blue #89b4fa, lavender #b4befe, text #cdd6f4, surface0 #313244, surface1 #45475a, base #1e1e2e, mantle #181825, crust #11111b)
- Gruvbox: warm browns and oranges
- Nord: arctic blues and grays
- Tokyo Night: deep blues with purple accents

---

## 5. Exemplar App Analysis

### lazygit — The Gold Standard

**Layout:** 5 left panels (status, files, branches, commits, stash) + right detail panel
**Framework:** Go (gocui fork)

**Key Visual Patterns:**
- **Contextual keybinding footer** — available actions update as focus changes (zero memorization)
- **Popup layering** — confirmation dialogs as overlays without losing spatial context
- **Command transparency** — shows actual git commands being executed
- **Guided workflows** — interactive rebase, conflict resolution via progressive disclosure
- **Color-coded file status** — green (staged), red (deleted), yellow (modified), blue (renamed)
- **Branch visualization** — commit graph with branch colors
- **Theme system** — centralized theme with regex-based dynamic matching

**Color Palette (default):**
- Background: transparent (terminal default)
- Active tab: #1e1e2e (dark blue-gray)
- Inactive tab: #313244 (lighter gray)
- Selected line: #45475a (highlight)
- Confirmation: #f38ba8 (red accent)

### k9s — Command-Mode Navigation

**Layout:** Top menu bar + main content area + status bar
**Framework:** Go (tcell/tview)

**Key Visual Patterns:**
- **`:resource` command mode** — type `:pods`, `:deployments` to jump (URL bar equivalent)
- **XRay mode** — tree visualization of related resources
- **Pulse view** — heads-up display of cluster health
- **Context-aware skins** — different color schemes per cluster (production vs staging)
- **Log streaming** — real-time log tailing with search
- **Resource table** — sortable columns with color-coded status

### btop — Polished System Monitor

**Layout:** T-shaped grid of bordered widget boxes
**Framework:** C++ (custom)

**Key Visual Patterns:**
- **Bordered box zones** — each widget is a self-contained panel with title
- **Braille sparklines** — high-resolution graphs using Unicode braille (U+2800-U+28FF)
- **Theme ecosystem** — 24-bit truecolor with 256-color fallback
- **CPU meter colors** — green (user), red (kernel), blue (low-priority), cyan (virtualization)
- **Process table** — sortable with tree view option
- **Memory breakdown** — bar chart visualization

### helix — Modal Editor

**Layout:** Editor area + gutter + status line
**Framework:** Rust (custom)

**Key Visual Patterns:**
- **Modal editing** — normal/insert/select modes with visual indicators
- **Gutter** — line numbers, git blame, diagnostics
- **Status line** — mode, file info, cursor position, encoding
- **Selection highlighting** — visual selection with line numbers
- **Completion menu** — floating menu with documentation preview
- **Color themes** — extensive theme support (100+ community themes)

### yazi — File Browser

**Layout:** Three-panel (parent + current + preview)
**Framework:** Rust (custom)

**Key Visual Patterns:**
- **Three-panel layout** — parent directory, current directory, file preview
- **Icon support** — nerd font icons for file types
- **Preview pane** — file content preview (text, images, code)
- **Color-coded file types** — by extension
- **Status bar** — file info, permissions, size
- **Search/filter** — fuzzy find with live preview

### atuin — Shell History Search

**Layout:** Full-screen search + results list
**Framework:** Rust (custom)

**Key Visual Patterns:**
- **Fuzzy search** — real-time filtering as you type
- **Statistics** — command frequency, time of day patterns
- **Preview pane** — full command preview on selection
- **Keyboard-driven** — vim-style navigation
- **Theme support** — multiple color schemes

---

## 6. Color Palette Recommendations for NexusAgent

### Primary Palette (Based on Catppuccin Mocha)

| Token | Hex | Usage |
|-------|-----|-------|
| `$background` | #1e1e2e | Main background |
| `$surface` | #313244 | Cards, panels, input areas |
| `$surface-light` | #45475a | Hover states, selected items |
| `$primary` | #cba6f7 | Active elements, user messages |
| `$accent` | #89b4fa | Focus borders, tool calls |
| `$text` | #cdd6f4 | Primary text |
| `$text-muted` | #a6adc8 | Labels, hints |
| `$text-disabled` | #6c7086 | Disabled elements |
| `$success` | #a6e3a1 | Success states, completed tools |
| `$warning` | #f9e2af | Warnings, running tools |
| `$error` | #f38ba8 | Errors, failed tools |
| `$border` | #45475a | Default borders |
| `$border-focus` | #cba6f7 | Focused input borders |

### Semantic Color Mapping

```python
SEMANTIC_COLORS = {
    "user": "#89b4fa",        # Blue
    "assistant": "#cdd6f4",   # Text (white)
    "tool-call": "#f9e2af",   # Yellow
    "tool-success": "#a6e3a1", # Green
    "tool-error": "#f38ba8",  # Red
    "thinking": "#cba6f7",    # Purple
    "system": "#a6adc8",      # Muted
    "error": "#f38ba8",       # Red
    "border": "#45475a",      # Gray
    "surface": "#313244",     # Dark gray
}
```

### NO_COLOR Support

Per https://no-color.org:
```python
import os
NO_COLOR = "NO_COLOR" in os.environ
if NO_COLOR:
    # All colors → empty string, no ANSI codes
    # Use ASCII fallback: [ ] for checkboxes, * for bullets, - for borders
```

---

## 7. Typography in Terminals

### Box-Drawing Characters

```
┌─┐  ╭─╮  ┏━┓  ╔═╗
│ │  │ │  ┃ ┃  ║ ║
└─┘  ╰─╯  ┗━┛  ╚═╝
Single  Rounded  Double  Heavy

─ │  ┄ ┆  ╌ ╎     Horizontal/Vertical
┼  ┿  ╋  ╂     Crosses
► ◄  ●  ○     Indicators
```

### ASCII Fallback

```
+--+  +-+  (rounded corners)
|  |  | |
+--+  +-+

- | +  (crosses)
> * o  (indicators)
```

### Nerd Font Icons (Optional)

```
   Terminal  
   Folder   
   File     
   Git branch  
   Check mark  
   X mark   
   Warning  
   Info     
   Spinner  
```

### Spinner Animations

```
ASCII:   | / - \ | / - Unicode:  ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏
Braille:  ⠋ ⠙ ⠚ ⠞ ⠖ ⠦ ⠴ ⠲ ⠳ ⠓
Blocks:  ▁ ▂ ▃ ▄ ▅ ▆ ▇ █
```

---

## 8. Layout Recommendations for NexusAgent

### Recommended Layout (ASCII Mockup)

```
┌──────────────────────────────────────────────────────┐
│ [Model: claude-4] [CWD: ~/project] [Branch: main] [●]│  StatusBar (1 line)
├──────────────────────────────────────────────────────┤
│                                                      │
│  ╭─ User ────────────────────────────────────────╮   │
│  │ Fix the authentication bug in auth.py        │   │
│  ╰───────────────────────────────────────────────╯   │
│                                                      │
│  ╭─ Assistant ────────────────────────────────────╮  │
│  │ I'll start by examining the auth module...     │  │
│  │                                               │  │
│  │ ```python                                     │  │
│  │ def authenticate(user, password):             │  │
│  │     ...                                       │  │
│  │ ```                                           │  │
│  ╰───────────────────────────────────────────────╯  │
│                                                      │
│  ┌─ tool_search ──────────────────────────────────┐  │
│  │ ● Running: search for "auth.py"               │  │
│  │ ○ Result: Found 3 matches                      │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ file_read ────────────────────────────────────┐  │
│  │ ● Reading: src/auth.py (120 lines)            │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
├──────────────────────────────────────────────────────┤
│ > Type your message...                         [Send]│  InputArea (3-15 lines)
└──────────────────────────────────────────────────────┘
```

### Key Layout Principles

1. **Maximize chat area** — ≥70% of terminal real estate
2. **Single status bar** — 1 line at bottom with model/CWD/branch/spinner
3. **No header** — save the chrome, use status bar for info
4. **Message differentiation** — user messages have colored borders, assistant messages are plain
5. **Tool calls as cards** — bordered boxes with status indicators
6. **Input area** — auto-expanding, 3-15 lines, with border
7. **Responsive** — collapse panels at narrow widths

### Responsive Breakpoints

| Width | Layout |
|-------|--------|
| ≥120 | Full layout with all info |
| 80-119 | Compact status bar, narrower messages |
| 60-79 | Minimal status bar, single-column |
| <60 | Ultra-minimal, hide status bar extras |
