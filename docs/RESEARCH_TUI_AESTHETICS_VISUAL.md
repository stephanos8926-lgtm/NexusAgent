# TUI/TERMINAL AESTHETICS — VISUAL DESIGN REFERENCE

> Research compiled 2026-06-10. Covers 9 popular CLI/TUI tools and AI coding agents.
> Sources: official docs, source code, community themes, reverse-engineering analysis, user reviews.

---

## TABLE OF CONTENTS

1. [Color Palettes](#1-color-palettes)
2. [Layout Patterns](#2-layout-patterns)
3. [Typography & Visual Hierarchy](#3-typography--visual-hierarchy)
4. [Animations & Transitions](#4-animations--transitions)
5. [Information Density](#5-information-density)
6. [Tool-by-Tool Breakdown](#6-tool-by-tool-breakdown)
7. [Design Priority Tiers](#7-design-priority-tiers)
8. [Universal Principles (from TUI Design Skill)](#8-universal-principles)

---

## 1. COLOR PALETTES

### 1.1 Claude Code

**Framework:** Custom Ink fork (React for terminals + Yoga flexbox)
**Rendering:** ANSI relative cursor positioning, double-buffered, cell-level diffing

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| Background | terminal default (inherits) | terminal default | Respects terminal theme |
| Foreground | `#ffffff` (assistant), `#ffffff` (user) | — | Pure white text |
| Accent/Brand | `#b197f0` (purple) | — | Claude brand color |
| Success | `#4eba65` (rgb 78,186,101) | — | Tool OK, diff add |
| Error | `#ff6b80` (rgb 255,107,128) | — | Tool fail, errors |
| Warning | `#ffc107` (rgb 255,193,7) | — | Warnings, amber |
| Subtle/Dim | `#505050` | — | Secondary text, args |
| Inactive | `#999999` | — | Hints, metadata |
| Diff Add BG | `#225c2b` (rgb 34,92,43) | — | Dark green |
| Diff Del BG | `#7a2936` (rgb 122,41,54) | — | Dark red |
| Diff Word Add | `#38a660` | — | Medium green highlight |
| Diff Word Del | `#b3596b` | — | Soft red highlight |
| Plan Mode | `#48968c` (rgb 72,150,140) | — | Teal |
| Bash Mode | `#fd5db1` (rgb 253,93,177) | — | Hot pink |
| User Message BG | `#373737` | — | Lighter grey bubble |
| Selection BG | `#264f78` | — | VS Code-style blue |
| Rate Limit Fill | `#b197f0` | — | Light blue-purple |
| Rate Limit Empty | `#505370` | — | Medium blue-purple |
| User Msg Hover | `#464646` | — | Hover state |
| Message Actions | `#2c323e` | — | Cool gray with blue tint |

**Theme system:** 69 semantic color tokens in `~/.claude/themes/*.json`. Supports hex, rgb(), ansi256(), named ANSI. Hot-reload on edit. 6 built-in presets (dark, light, dark-daltonized, light-daltonized, dark-ansi, light-ansi). Plugin-distributable themes.

**Key design decision:** Claude Code uses terminal background by default (inherits), but layers its own UI colors on top. The ANSI-only modes respect the user's terminal theme exactly.

### 1.2 Gemini CLI

**Framework:** Ink (React for terminals), TypeScript
**Rendering:** Alternate buffer mode, virtualized list for history, static rendering for finalized content

**Default Dark Theme (v0.33 "Classic" — user-favorite):**

| Token | Hex | Usage |
|-------|-----|-------|
| Background | `#1E1E2E` | Catppuccin Mocha base |
| Foreground | `#CDD6F4` | Catppuccin Mocha text |
| Accent Blue | `#89B4FA` | Primary accent, focused borders |
| Accent Purple | `#CBA6F7` | Secondary accent, badges |
| Accent Cyan | `#89DCEB` | Info, symbols |
| Accent Green | `#A6E3A1` | Success |
| Accent Yellow | `#F9E2AF` | Warning |
| Accent Red | `#F38BA8` | Error |
| Comment | `#6C7086` | Muted text |
| Diff Added | `#28350B` | Dark green |
| Diff Removed | `#430000` | Dark red |
| Gradient | `#4796E4` → `#847ACE` → `#C3677F` | Decorative gradient |

**GitHub Dark Theme:**

| Token | Hex |
|-------|-----|
| Background | `#24292e` |
| Foreground | `#c0c4c8` |
| Accent Blue | `#79B8FF` |
| Accent Purple | `#B39F0` |
| Accent Green | `#85E89D` |
| Accent Yellow | `#FFAB70` |
| Accent Red | `#F97583` |

**Theme system:** JSON-based custom themes in `settings.json`. Supports hex, CSS named colors. Auto-theme switching via terminal background polling. 20+ built-in themes (dark + light). TerminalBuffer mode for flicker-free rendering.

### 1.3 OpenCode

**Framework:** Go + Bubble Tea (Charmbracelet ecosystem)
**Rendering:** Lipgloss for styling, glamour for markdown, chroma for syntax highlighting

**Default Dark Palette:**

| Token | Hex | Usage |
|-------|-----|-------|
| Background | `#212121` | Neutral dark |
| Current Line | `#252525` | Slightly elevated |
| Selection | `#303030` | Selection bg |
| Foreground | `#e0e0e0` | Primary text |
| Comment | `#6a6a6a` | Muted |
| Primary | `#fab283` | Orange/gold — brand |
| Secondary | `#5c9cf5` | Blue |
| Accent | `#9d7cd8` | Purple |
| Error | `#e06c75` | Red |
| Warning | `#f5a742` | Orange |
| Success | `#7fd88f` | Green |
| Info | `#56b6c2` | Cyan |
| Emphasized | `#e5c07b` | Yellow |
| Border | `#4b4c5c` | Subtle border |

**Theme system:** 15+ built-in themes (tokyonight, everforest, ayu, catppuccin, gruvbox, kanagawa, nord, matrix, one-dark, etc.). `system` theme auto-adapts to terminal colors. JSON/JSONC config. Custom themes in `~/.config/opencode/themes/`. Layout system with `default` and `dense` presets (18 spacing/visibility parameters).

### 1.4 Deep Agents CLI

**Framework:** Python + Textual
**Rendering:** Textual CSS variables, Rich markup for inline styling

**Dark Theme (LangChain brand, Tokyo Night–inspired):**

| Token | Hex | Usage |
|-------|-----|-------|
| Background | `#11121D` | Blue-tinted black |
| Surface/Card | `#1A1B2E` | Elevated surface |
| Border Dark | `#25283B` | Borders |
| Border Light | `#3A3E57` | Hovered borders |
| Body Text | `#C0CAF5` | High contrast |
| Primary | `#7AA2F7` | Blue accent |
| Secondary | `#BB9AF7` | Purple badges |
| Success | `#9ECE6A` | Green |
| Warning | `#EB8B46` | Amber |
| Error | `#F7768E` | Pink/red |
| Muted | `#545C7E` | Secondary text |
| Diff Add BG | `#1C2A38` | Subtle green |
| Diff Del BG | `#2A1F32` | Subtle pink |
| Panel | `#25283B` | Section bg |
| Skill | `#A78BFA` | Skill invocation |
| Tool | `#EB8B46` | Tool calls |

**Light Theme:**

| Token | Hex |
|-------|-----|
| Background | `#F5F5F7` |
| Surface | `#EAEAEE` |
| Body Text | `#24283B` |
| Primary | `#2E5EAA` |
| Muted | `#6B7280` |

**Theme system:** Semantic `ThemeColors` dataclass (16 fields). Custom themes in `~/.deepagents/config.toml`. CSS variable injection via `get_css_variable_defaults()`. App-specific vars: `$mode-bash`, `$mode-command`, `$skill`, `$tool`.

### 1.5 lazygit

**Framework:** Go + gocui (fork)
**Rendering:** Direct gocui rendering, TOML theme config

**Default (Catppuccin Mocha Blue):**

| Token | Hex | Usage |
|-------|-----|-------|
| Active Border | `#89b4fa` | Focused panel |
| Inactive Border | `#a6adc8` | Unfocused |
| Options Text | `#89b4fa` | Key hints |
| Selected Line | `#313244` | Current selection |
| Default FG | `#cdd6f4` | Text |
| Unstaged | `#f38ba8` | Red for unstaged |
| Cherry Pick FG | `#89b4fa` | Cherry-picked commit |
| Cherry Pick BG | `#45475a` | |
| Author | `#b4befe` | Commit author |

**Embark theme (community):**

| Token | Hex |
|-------|-----|
| Active Border | `#63F2F1` (cyan) |
| Inactive Border | `#585273` |
| Default FG | `#CBE3E7` |
| Unstaged | `#F48FB1` (pink) |

**Theme system:** TOML/YAML config. `activeBorderColor`, `inactiveBorderColor`, `searchingActiveBorderColor`, `optionsTextColor`, `selectedLineBgColor`, `selectedRangeBgColor`, `cherryPickedCommitBgColor`, `cherryPickedCommitFgColor`, `markedBaseCommitFgColor`, `markedBaseCommitBgColor`, `unstagedChangesColor`, `defaultFgColor`. Per-branch coloring. Author coloring.

### 1.6 k9s

**Framework:** Go + tview/tcell
**Rendering:** YAML skin config, per-context theming

**Semantic colors (YAML skin):**

| Token | Default | Usage |
|-------|---------|-------|
| Body FG | `dodgerblue` | Main text |
| Body BG | `#ffffff` | Background |
| Logo | `#0000ff` | Brand |
| Info FG | `lightskyblue` | Info text |
| Section | `steelblue` | Section headers |
| Border FG | `dodgerblue` | Borders |
| Border Focus | `aliceblue` | Focused border |
| Menu FG | `darkblue` | Menu text |
| Menu Key | `cornflowerblue` | Key hints |
| Crumbs FG | `white` | Breadcrumbs |
| Crumbs BG | `steelblue` | |
| Crumbs Active | `skyblue` | |
| New | `#00ff00` | New resource |
| Modify | `powderblue` | Modified |
| Add | `lightskyblue` | Added |
| Error | `indianred` | Error |
| Highlight | `royalblue` | Highlighted |
| Kill | `slategray` | Killed |
| Completed | `gray` | Completed |
| Cursor | `aqua` | Cursor |
| Header FG | `white` | Table header |
| Header BG | `darkblue` | |
| Sorter | `orange` | Sort indicator |
| YAML Key | `steelblue` | YAML keys |
| YAML Value | `royalblue` | YAML values |

**Theme system:** YAML skin files in `$XDG_CONFIG_HOME/k9s/skins/`. Per-cluster/context skinning (production vs staging visually distinct). Named colors or hex. Extensive customization (body, info, frame, menu, crumbs, status, views, table, yaml, logs).

### 1.7 btop

**Framework:** C++ custom renderer
**Rendering:** Truecolor with 256-color fallback, TOML theme files

**Default theme key colors:**

| Token | Hex | Usage |
|-------|-----|-------|
| Main BG | (terminal default) | Transparent |
| Main FG | `#F8F8F2` | Text |
| Title | `#F8F8F2` | Box titles |
| Highlight | `#2eb398` | Keyboard shortcuts |
| Selected BG | `#0d493d` | Selected item |
| Inactive | `#595647` | Disabled text |
| Graph Text | `#797667` | Overlay text |
| Proc Misc | `#33b165` | Process indicators |
| Box Border | `#75715E` | All box outlines |
| Div Line | `#595647` | Dividers |
| CPU Start | `#33b165` | Gradient start |
| CPU Mid | `#F8F8F2` | Gradient mid |
| CPU End | `#2eb398` | Gradient end |
| Temp Start | `#7976B7` | Purple |
| Temp Mid | `#D8B8B2` | Pink |
| Temp End | `#33b165` | Green |

**Theme system:** 50+ built-in themes (dracula, gruvbox, nord, tokyonight, solarized, ayu, monokai, everforest, kanagawa, etc.). TOML format. Gradient support (start/mid/end). TTY mode for 16-color terminals. Per-widget color config (cpu_box, mem_box, net_box, proc_box). Theme hot-reload via SIGUSR2.

### 1.8 yazi

**Framework:** Rust + Ratatui + Crossterm
**Rendering:** TOML theme config, async I/O

**Default Dark:**

| Token | Hex/Name | Usage |
|-------|----------|-------|
| CWD | `cyan` | Current directory |
| Find Keyword | `yellow` + bold + italic + underline | Search matches |
| Find Position | `magenta` + bold + italic | Match position |
| Symlink | italic | Symlink target |
| Marker Copied | `lightgreen` | Copy indicator |
| Marker Cut | `lightred` | Cut indicator |
| Marker Marked | `lightcyan` | Marked item |
| Marker Selected | `lightyellow` | Selected item |
| Count Copied | white on green | Count badge |
| Count Cut | white on red | Count badge |
| Count Selected | black on yellow | Count badge |
| Border | `gray` | Panel borders |
| Tab Active | `blue` + bold | Active tab |
| Tab Inactive | `blue` on gray | Inactive tab |
| Normal Mode | `blue` + bold | Mode indicator |
| Select Mode | `red` + bold | Mode indicator |
| File Type: Image | `yellow` | File coloring |
| File Type: Media | `magenta` | File coloring |
| File Type: Archive | `red` | File coloring |
| File Type: Document | `cyan` | File coloring |
| File Type: Exec | `green` | File coloring |
| File Type: Dir | `blue` | Directories |

**Claude-Inspired Community Flavor:**

| Token | Hex |
|-------|-----|
| Primary (orange) | `#C76A4F` |
| Secondary (amber) | `#C99A68` |
| Red | `#B44F5F` |
| Green | `#99B37E` |
| Cream (highlight) | `#FEF3C7` |
| Background | `#171412` |

**Theme system:** TOML with `[flavor]` dark/light. `[mgr]`, `[tabs]`, `[mode]`, `[status]`, `[which]`, `[confirm]`, `[spot]`, `[notify]`, `[pick]`, `[input]`, `[cmp]`, `[tasks]`, `[help]`, `[filetype]`, `[icon]` sections. File-type rules by MIME type and name. Nerd Font icons with per-directory colors. Lua plugins for extension.

### 1.9 atuin

**Framework:** Rust + Ratatui
**Rendering:** TOML theme config, semantic color meanings

**Semantic color system:**

| Meaning | Default | Usage |
|---------|---------|-------|
| Base | (terminal default) | Default foreground |
| Title | — | Section headers |
| Important | — | Highlighted info |
| Guidance | — | Help/context text |
| Annotation | — | Supporting text |
| Muted | grey | Subtle contrast |
| AlertInfo | — | Info level |
| AlertWarn | — | Warning level |
| AlertError | — | Error level |

**Community themes:** `default`, `autumn`, `marine`, `(none)`. Custom TOML in `~/.config/atuin/themes/`. Supports named colors, hex, ANSI codes (`@ansi_(n)`), RGB (`@rgb_(r,g,b)`). Neon cyberpunk, matrix, vaporwave community themes.

---

## 2. LAYOUT PATTERNS

### 2.1 Seven Canonical Layouts (from TUI Design Skill)

| Layout | Tools | Best For |
|--------|-------|----------|
| **Persistent Multi-Panel** | lazygit, btop, htop | At-a-glance observation, switching between views |
| **Miller Columns** | yazi, ranger, broot | Hierarchies (filesystems, JSON) |
| **Drill-Down Stack** | k9s, lazydocker | Many resource types, pivot navigation |
| **Widget Dashboard** | btop, bottom, glances | Monitoring/observability |
| **IDE Three-Panel** | Posting, Harlequin, helix | Editor-like workflows |
| **Overlay / Popup** | fzf, atuin, zoxide+fzf | Summon → choose → output |
| **Tabbed Within Panel** | lazygit, lazydocker | Multiple personalities per panel |

### 2.2 AI Coding Agent Layout (Chat Pattern)

All AI coding agents converge on the same layout:

```
┌─────────────────────────────────────────┐
│  [streaming response / history]         │  ← Scrollable, virtualized
│  [tool calls, diffs, code blocks]       │
├─────────────────────────────────────────┤  ← Separator (─ ━ ═)
│  ❯ [user input]                         │  ← Fixed at bottom
├─────────────────────────────────────────┤
│  [status: model, context, branch]       │  ← 2-space indent
│  [mode line: permissions, auto-approve] │  ← Last row
└─────────────────────────────────────────┘
```

**Key patterns across all AI agents:**
- Input anchored at bottom (never moves)
- Separator lines between zones (box-drawing characters)
- Status lines indented with 2 spaces (`\033[2C`)
- Spinner/timer above separator while working
- Mode line as last visible row
- Virtualized scrollable history above

### 2.3 Claude Code Specific Layout

**Bottom zone (fixed):**
- Spinner row: `✶ Undulating…`, `✻ Sautéed for 1m 19s`, `✳ Ideating…`
- Upper separator: `────` (may contain label like `──── extractor ──`)
- Prompt: `❯ [input]`
- Lower separator: `────`
- Status lines (0-N, indented 2 spaces)
- Mode line (last row, indented 2 spaces)

**Markers:** `✶` (U+2736), `✻` (U+273B), `✳` (U+2733), `✢` (U+2722), `·` (U+00B7), `⏵⏵` (U+23F5 x2), `⏸` (U+23F8)

**Fullscreen rendering:** Alternate screen buffer. Only visible messages in render tree (memory flat). Input fixed at bottom. Scroll-wheel support with bug detection.

### 2.4 Gemini CLI Layout

- Sticky headers for tool confirmations (persistent context)
- Input prompt anchored at bottom (stable, no bounce)
- Scrolling with virtualized list
- Mouse support for input prompt navigation
- Responsive: <80 columns switches to compact vertical layout
- Header logos: long/short/tiny ASCII art based on width

### 2.5 OpenCode Layout

- Page-based navigation (chat, logs, etc.)
- Multi-pane: messages left, editor bottom, diff overlay
- Dialog system with centered overlays
- Leader key sequences (`Ctrl+X` default)
- Command palette (`Ctrl+P`)
- Configurable layout system (default/dense, 18 spacing params)
- Home screen with ASCII logo and quick start

### 2.6 Deep Agents Layout

```
┌─────────────────────────────────────────┐
│  [WelcomeBanner]                        │
│  [VerticalScroll: messages]             │
│    [WelcomeBanner]                      │
│    [Container: messages]                │
├─────────────────────────────────────────┤
│  [bottom-app-container]                 │
│    [ChatInput]                          │
├─────────────────────────────────────────┤
│  [StatusBar]                            │  ← Bottom
└─────────────────────────────────────────┘
```

- Welcome banner with thread info, MCP tool count
- Vertical scroll with auto-anchor
- Chat input with image tracking
- Status bar (CWD, git branch, auto-approve state)
- Approval menu (y/n) for tool calls
- `gc.freeze()` after mount for GC optimization

---

## 3. TYPOGRAPHY & VISUAL HIERARCHY

### 3.1 Terminal Typography Constraints

- **Fixed cell width** — every character is the same width
- **No font size variation** — hierarchy must come from other signals
- **CJK/emoji width** — use wcwidth/unicode-segmentation, never `len()`
- **Nerd Font** — used by yazi, lazygit (icons), btop (braille sparklines)

### 3.2 Hierarchy Signals (ranked by effectiveness)

1. **Position** — top/left reads first; status bar at bottom; headers at top
2. **Color + weight** — bold + accent for titles/focused; dim for metadata
3. **Reverse video** — universally available since VT100; canonical selection marker
4. **Borders** — border color change = strongest focus indicator
5. **Indentation** — 2-cell indent standard; `├─ └─` for trees
6. **Bullets** — `▶` expandable, `▼` expanded, `●` active, `○` inactive
7. **Connectors** — Powerline separators (`` ``) in yazi tabs

### 3.3 Font Choices (from community/tooling)

| Font | Used By | Notes |
|------|---------|-------|
| JetBrains Mono | Recommended by atuin community | Ligatures, good readability |
| Fira Code | Recommended by atuin community | Ligatures |
| Nerd Font (any) | yazi, lazygit | Required for icons |
| Monospace (system) | All tools | Default terminal font |

### 3.4 Text Styling Conventions

| Style | Usage | Support |
|-------|-------|---------|
| **Bold** | Titles, focused items, primary content | Universal |
| **Dim** | Metadata, timestamps, disabled | Good |
| *Italic* | File paths, symlinks, emphasis | Poor — never sole signal |
| **Underline** | Hyperlinks (OSC 8), shortcut hints | Good |
| **Reverse** | Current selection, cursor row | Universal (VT100) |
| ~~Strikethrough~~ | Deprecated | Limited |
| Blink | **Never use** | Disabled in modern terminals |

---

## 4. ANIMATIONS & TRANSITIONS

### 4.1 Spinner Patterns

| Tool | Spinner Style | Unicode |
|------|--------------|---------|
| Claude Code | `✶ Undulating…` | U+2736 + text |
| Claude Code | `✻ Sautéed for 1m 19s` | U+273B + text |
| Claude Code | `✳ Ideating… (1m 32s · ↓ 2.2k tokens)` | U+2733 + text |
| Claude Code | `· Proofing…` | U+00B7 + text |
| Gemini CLI | Smooth flicker-free (TerminalBuffer) | No visible spinner |
| Deep Agents | Textual default | Configurable |
| OpenCode | Bubble Tea spinner | Charmbracelet style |

### 4.2 Progress Indicators

| Tool | Pattern |
|------|---------|
| btop | Truecolor gradient meters (CPU, mem, net) |
| btop | Braille sparkline graphs (high-res) |
| lazygit | Subtle pulse animation on background fetch |
| Claude Code | Context bar: `█░░░░░░░░░ 8%` |
| Gemini CLI | Gradient loading indicator |
| atuin | Minimal (instant search) |

### 4.3 Transition Patterns

| Pattern | Tools | Notes |
|---------|-------|-------|
| **Alternate screen** | Claude Code (fullscreen), Gemini CLI, k9s | No scrollback pollution |
| **Virtualized scrolling** | Claude Code, Gemini CLI, Deep Agents | Memory-flat for long sessions |
| **Static history + dynamic input** | Claude Code, Gemini CLI | `<Static>` / TerminalBuffer pattern |
| **Debounced redraw** | k9s, btop | Don't refresh on every event |
| **Event-driven redraw** | All modern tools | Never timer-based |
| **Resize handling** | All | SIGWINCH + debounce |
| **Suspend/Resume** | All | Ctrl+Z handling, state restore |

### 4.4 Animation Guidelines

- Cap at 30-60 fps
- Redraw on events, never on fixed timer
- Spinner updates should not cause full-screen flicker
- Use double-buffering for smooth transitions
- Respect `prefers-reduced-motion` where possible
- Lazygit's pulse animation: present but not commanding attention

---

## 5. INFORMATION DENSITY

### 5.1 Density Spectrum

| Tool | Density | Approach |
|------|---------|----------|
| htop | **Pack** | No internal borders, scan at a glance |
| btop | **Pack** | Bordered boxes, real-time updates |
| k9s | **Pack** | Dense tables, live updates |
| lazygit | **Moderate** | 5 panels + detail, borders for separation |
| yazi | **Moderate** | Miller columns, file-type coloring |
| atuin | **Minimal** | Overlay, single search + results |
| Claude Code | **Moderate** | Chat + status, separator zones |
| Gemini CLI | **Moderate** | Chat + sticky headers |
| OpenCode | **Configurable** | default/dense layout presets |
| Deep Agents | **Moderate** | Chat + status bar |

### 5.2 Footer Hint Bars (Discoverability)

| Tool | Pattern |
|------|---------|
| htop | F-key strip (F1-F10 always visible) |
| lazygit | Per-panel contextual hints (updates on focus change) |
| k9s | Bottom hints (context-sensitive) |
| btop | `h` for help modal (organized by widget) |
| Claude Code | Mode line (last row, permissions/agent status) |
| Gemini CLI | Sticky headers for context |
| OpenCode | Status bar (model, plan status) |
| Deep Agents | Status bar (CWD, git branch, auto-approve) |

### 5.3 Progressive Disclosure Layers

1. **Always-visible footer hints** (3-5 most useful keys)
2. **`?` opens full help screen** (all bindings)
3. **Leader-key which-key popup** (Space- menu in helix)
4. **Command palette** (Ctrl+P — every action searchable)
5. **Documentation** (last resort)

---

## 6. TOOL-BY-TOOL BREAKDOWN

### 6.1 lazygit

- **Layout:** 5 left panels + right detail + command log strip
- **Navigation:** `1-5` panel jumps, `Tab` cycles, `[`/`]` sub-tabs
- **Color:** Catppuccin Mocha default, 12 themeable YAML keys
- **Innovation:** Command transparency (shows actual git commands)
- **Animation:** Subtle pulse on background fetch
- **Borders:** Single-line, rounded in some themes
- **Undo:** `z`/`Ctrl+Z` for git operations including rebases

### 6.2 k9s

- **Layout:** Drill-down stack + command mode
- **Navigation:** Enter descends, Esc ascends, `:resource` jumps
- **Color:** YAML skin system, per-cluster theming (prod vs staging)
- **Innovation:** XRay mode (tree visualization), Pulse view (HUD)
- **Tables:** Sortable columns with `<`/`>`
- **Filter:** Fuzzy (`/`) for huge lists
- **Live updates:** Debounced redraw

### 6.3 btop

- **Layout:** Widget dashboard (T-shaped grid)
- **Navigation:** Mouse drag to resize, click to focus
- **Color:** Truecolor gradients, 50+ themes, TTY fallback
- **Innovation:** Braille sparklines, per-widget update cadence
- **Graphs:** CPU/memory/net/disk with gradient meters
- **Config:** TOML, rearrangeable widgets

### 6.4 yazi

- **Layout:** Miller columns (parent/current/preview, 1:4:3)
- **Navigation:** `hjkl` + arrows, `:` command mode
- **Color:** TOML theme, file-type rules (MIME + name), per-directory icon colors
- **Innovation:** Async-everything, 3 image protocols, Lua plugins
- **Preview:** Built-in image preview (Sixel/kitty/iTerm2)
- **Bookmarks:** `m{a-z}` mark, `'{a-z}` jump

### 6.5 atuin

- **Layout:** Overlay/popup (replaces Ctrl+R)
- **Navigation:** Fuzzy filter, arrow keys, Enter to execute
- **Color:** Semantic meaning → color mapping, TOML themes
- **Innovation:** Replaces a built-in seamlessly, encrypted sync
- **Metadata:** Exit code, CWD, hostname, duration on every result
- **Dual:** CLI (`atuin search`) + TUI from same core

### 6.6 Claude Code

- **Layout:** Chat (input bottom, output above, separators)
- **Rendering:** Custom Ink fork, 60fps, cell-level diffing
- **Color:** 69 semantic tokens, 6 presets, custom JSON themes
- **Innovation:** Fullscreen rendering (alt screen, virtualized, flat memory)
- **Streaming:** Token-by-token at 60fps without flicker
- **Vim mode:** Built-in vim keybindings for input
- **Status:** Context bar, model info, branch, permissions mode

### 6.7 Gemini CLI

- **Layout:** Chat + sticky headers + anchored input
- **Rendering:** Ink + TerminalBuffer (flicker-free), virtualized list
- **Color:** 20+ themes, auto-switching, Catppuccin Mocha default
- **Innovation:** Sticky headers, responsive <80col layout, PTY support
- **Scrolling:** Alternate buffer with virtualized history
- **Mouse:** Click-to-position in input, scroll wheel

### 6.8 OpenCode

- **Layout:** Page-based + multi-pane + overlay dialogs
- **Rendering:** Bubble Tea (Charmbracelet), Lipgloss, Glamour
- **Color:** 15+ themes, system auto-adapt, JSON/JSONC config
- **Innovation:** Layout system (18 spacing params), dense preset
- **Editor:** Integrated with vim keybindings
- **Diff:** Full-screen overlay with scroll + syntax

### 6.9 Deep Agents CLI

- **Layout:** Chat + welcome banner + status bar
- **Rendering:** Textual (Python), CSS variables, Rich markup
- **Color:** 16 semantic hex values, dark/light, custom TOML themes
- **Innovation:** Approval menu (y/n), auto-approve toggle
- **GC:** `gc.freeze()` after mount for render optimization
- **Scroll:** VerticalScroll with auto-anchor, reduced sensitivity

---

## 7. DESIGN PRIORITY TIERS

### 🔴 CRITICAL — Broken/Ugly Elements That Must Be Fixed

These are the issues that make a TUI feel unprofessional or unusable:

| Issue | Description | Tools Getting It Right |
|-------|-------------|----------------------|
| **No alternate screen** | Pollutes scrollback, leaves terminal dirty on exit | Claude Code (fullscreen), Gemini CLI, k9s |
| **Hardcoded colors clashing with user themes** | Overrides user's carefully chosen terminal palette | Claude Code (ANSI mode), Gemini CLI (auto-switch), atuin (semantic colors) |
| **Crash on resize** | No SIGWINCH handling, visual glitches | All modern tools handle this |
| **Blocking UI thread on I/O** | Freezes during git ops, network calls, file reads | lazygit (async fetch), yazi (async-everything), Deep Agents (workers) |
| **Color-only signaling** | Status shown only with color, invisible to CVD users | lazygit (M/A/D letters), k9s (symbols + color) |
| **No terminal state restoration on panic** | Leaves terminal in raw mode + alt screen | All tools with proper panic handlers |
| **No "terminal too small" message** | Crashes or renders garbage below minimum size | Gemini CLI (responsive <80col), OpenCode (dense layout) |
| **Flicker on every update** | Full-screen redraws cause visible flicker | Claude Code (cell-level diffing), Gemini CLI (TerminalBuffer) |
| **No footer hints** | Users must read docs to discover basic actions | htop (F-key strip), lazygit (contextual footer) |

### 🟡 MANDATORY — UX-Critical Aesthetic Fixes

These are the patterns that separate polished tools from rough ones:

| Issue | Description | Reference Implementation |
|-------|-------------|------------------------|
| **Semantic color tokens** | Define `status.error` not `#ff0000` | Claude Code (69 tokens), Deep Agents (16 fields), atuin (semantic meanings) |
| **Responsive layout** | Adapt to <80 columns, tmux splits | Gemini CLI (compact vertical), OpenCode (dense layout), Claude Code (stacked narrow) |
| **Virtualized lists** | Don't render 10k items | Claude Code (fullscreen), Gemini CLI (TerminalBuffer), Deep Agents (VerticalScroll) |
| **Progressive disclosure** | Footer → `?` → palette → docs | htop (F-keys), helix (which-key), lazygit (contextual footer) |
| **Consistent spatial layout** | Panels never move without user action | lazygit (fixed 5-panel), btop (fixed dashboard) |
| **Focus indication** | Border color change on focus | lazygit (active/inactive border), k9s (focusColor) |
| **Status bar** | Persistent context at bottom | Claude Code (model + context), Deep Agents (CWD + branch), Gemini CLI (sticky headers) |
| **Mode indication** | Clear modal state (vim modes, permissions) | Claude Code (mode line), k9s (command mode), OpenCode (page-based) |
| **Empty states** | "No X. Press `n` to create one." | Posting (explicit), Claude Code (spinner + separator) |
| **Table alignment** | Numeric right-align, text left, ISO-8601 dates | btop (process table), k9s (resource lists) |
| **Unicode fallback** | ASCII for legacy SSH/Windows | All modern tools provide ASCII fallback |
| **NO_COLOR support** | Respect no-color.org | Claude Code (fixed in settings), all tools should |
| **Theme system** | At least one community palette (Catppuccin/Gruvbox) | btop (50+ themes), OpenCode (15+), Claude Code (69-token custom) |

### 🟢 NICE TO HAVE — Cosmetic Improvements

These are the details that elevate from good to great:

| Issue | Description | Reference Implementation |
|-------|-------------|------------------------|
| **Truecolor gradients** | Beautiful color transitions in meters/graphs | btop (CPU/memory gradients), Gemini CLI (gradient loading) |
| **Braille sparklines** | High-resolution graphs in terminal | btop (per-core CPU graphs) |
| **Image preview** | Inline images in file manager | yazi (Sixel/kitty/iTerm2 auto-detect) |
| **Sticky headers** | Persistent context during scroll | Gemini CLI (tool confirmations) |
| **Which-key popups** | Leader key → available actions | helix (Space menu), OpenCode (leader key sequences) |
| **Command transparency** | Show underlying commands being run | lazygit (command log pane) |
| **Animation polish** | Smooth spinners, subtle pulses | Claude Code (undulating spinner), lazygit (subtle pulse) |
| **Mouse support** | Click to focus, drag to resize | btop (full mouse), Gemini CLI (input positioning) |
| **Multi-select** | Tab to mark multiple items | fzf (Tab multi-select), lazygit (Space toggle) |
| **Inline diff rendering** | Color-coded diffs in chat | Claude Code (word-level diff), OpenCode (diff overlay) |
| **Syntax highlighting** | Code blocks with proper coloring | All AI agents (markdown code blocks) |
| **Plugin system** | Extend without forking | yazi (Lua), k9s (TOML plugins), lazygit (custom commands) |
| **Bookmarks** | Quick-jump to marked locations | yazi (`m{a-z}`/`'{a-z}`), lazygit (bookmarks) |
| **Undo/redo** | Reversible operations | lazygit (`z`/`Ctrl+Z` for git ops) |
| **Per-cluster theming** | Visual distinction (prod vs staging) | k9s (context-aware skins) |

---

## 8. UNIVERSAL PRINCIPLES (from TUI Design Skill)

### 8.1 The Terminal Is a Constrained Design Medium

- Every cell is the same width. Type size doesn't change.
- ~80x24 at the small end, maybe 200x60.
- You compose grids of characters with foreground/background colors and attributes (bold, dim, italic, underline, reverse).
- **When something feels cramped, the answer is "remove something or use whitespace," never "add more."**

### 8.2 Three Observations That Drive Everything

1. **Spatial memory is the navigation.** Users learn where things live. Panels must never move without explicit user action.
2. **Color encodes meaning, not appearance.** Treat colors as semantic tokens. The app should be usable in monochrome. ~8% of males have red-green CVD.
3. **Keyboard is primary; mouse is augmentation.** Every action must be reachable from the keyboard. Vim motions are the lingua franca.

### 8.3 Color as a Semantic System (Three Tiers)

1. **Monochrome** — does the app work with `NO_COLOR=1`?
2. **16 ANSI** — does it look right with the user's theme?
3. **256 / truecolor** — fine-grained palette for designed themes

**Always respect `NO_COLOR`.** Conventional meanings: green=success, red=error, yellow=warning, cyan/blue=info, magenta=special, dim=secondary.

### 8.4 Borders, Density, Whitespace

- **Single-line borders** (`─ │ ┌ ┐ └ ┘`) by default. **Rounded** (`╭ ╮ ╰ ╯`) for modern Charm aesthetic.
- **Avoid double-line** (`═ ║ ╔`) — reads as "DOS."
- **ASCII fallback** (`+`, `-`, `|`) for legacy SSH and `TERM=dumb`.
- **Borders** when pane has dynamic content, needs focus state, or adjacent panels need separation.
- **Whitespace alone** when content is static or density matters more.

### 8.5 The Non-Negotiables (Terminal Hygiene)

1. **Use the alternate screen** for full-screen TUIs.
2. **Always restore terminal state on exit — even on panic.**
3. **Handle resize (SIGWINCH).** Re-layout on every resize. Define minimum size (80x24).
4. **Handle suspend (Ctrl+Z/SIGTSTP).** Disable raw mode, leave alt screen, restore cursor.

### 8.6 Performance

- **Truecolor is safe to assume in 2026.** Detect via `$COLORTERM=truecolor`.
- **Never block the UI thread on I/O.** All network/disk/subprocess work is async.
- **Don't redraw on a fixed timer.** Redraw on events. Cap animations at 30-60 fps.
- **Logging can't go to stdout.** Log to a file or in-app log pane.
- **Cell width ≠ string length.** Use wcwidth/unicode-segmentation.
- **Virtualize** any list that might exceed a few hundred items.

### 8.7 Cross-App Keybinding Conventions

| Key | Action |
|-----|--------|
| `q` | quit |
| `?` | help |
| `/` | search |
| `n`/`N` | next/prev match |
| `Esc` | cancel/back |
| `Enter` | confirm/drill in |
| `Space` | toggle/mark |
| `:` | command mode |
| `gg`/`G` | top/bottom |
| `Tab`/`Shift+Tab` | switch focus |
| `r` | refresh |
| `1`-`9` | jump to panel |
| `hjkl` + arrows | move (support both) |

**Never bind:** `Ctrl+C` (SIGINT), `Ctrl+Z` (SIGTSTP), `Ctrl+\` (SIGQUIT), `Ctrl+S`/`Ctrl+Q` (XON/XOFF).

### 8.8 The Clutter Audit

Count the offenders:
- **Border-nesting depth** — more than one border between terminal edge and content is too many
- **Duplicate signals** — `[PASS]` + green + `✅` + row marker = four signals for one state
- **Markers on every row** — a glyph on 100% of rows marks nothing
- **Chrome-vs-data ratio** — cells spent on borders/labels/boilerplate vs actual data

### 8.9 Pressure-Test the Floor

State what happens at **80x24 and a 60-column tmux split**:
- What collapses to a single pane?
- What hides?
- What truncates?
- What's the "terminal too small" message?

Multi-column layouts must have a single-pane fallback.

---

## APPENDIX A: COLOR PALETTE QUICK REFERENCE

### Dark Theme Backgrounds Compared

| Tool | Background | Undertone |
|------|-----------|-----------|
| Claude Code | terminal default | Inherits |
| Gemini CLI | `#1E1E2E` | Catppuccin Mocha (warm) |
| OpenCode | `#212121` | Neutral dark |
| Deep Agents | `#11121D` | Blue-tinted |
| lazygit | terminal default | Inherits |
| k9s | configurable | Varies by skin |
| btop | terminal default | Transparent |
| yazi | `#171412` (Claude flavor) | Warm dark |
| atuin | terminal default | Inherits |

### Accent Colors Compared

| Tool | Primary Accent | Secondary |
|------|---------------|-----------|
| Claude Code | `#b197f0` (purple) | — |
| Gemini CLI | `#89B4FA` (blue) | `#CBA6F7` (purple) |
| OpenCode | `#fab283` (orange) | `#5c9cf5` (blue) |
| Deep Agents | `#7AA2F7` (blue) | `#BB9AF7` (purple) |
| lazygit | `#89b4fa` (blue) | — |
| k9s | `dodgerblue` | `steelblue` |
| btop | `#2eb398` (teal) | `#33b165` (green) |
| yazi | `cyan` (CWD) | `blue` (dirs) |
| atuin | semantic | semantic |

---

## APPENDIX B: THEMATING MATURITY MODEL

| Level | Description | Example |
|-------|-------------|---------|
| 1. Hardcoded | Colors in source code | Legacy tools |
| 2. Config file | TOML/YAML theme files | lazygit, k9s, btop |
| 3. Semantic tokens | Meaning → color mapping | atuin, Claude Code |
| 4. Runtime switching | Change without restart | Claude Code (hot-reload), OpenCode |
| 5. Plugin themes | Community palette packages | btop (50+), OpenCode (15+), Claude Code (plugin-distributable) |
| 6. Auto-adapt | Detect terminal background | Gemini CLI (polling), OpenCode (system theme) |

---

## APPENDIX C: RENDERING ENGINE COMPARISON

| Tool | Language | Framework | Rendering Approach | Flicker-Free |
|------|----------|-----------|-------------------|-------------|
| Claude Code | TypeScript | Custom Ink fork | Cell-level diffing, double-buffered | Yes (fullscreen) |
| Gemini CLI | TypeScript | Ink + TerminalBuffer | Static history + dynamic input | Yes (TerminalBuffer) |
| OpenCode | Go | Bubble Tea + Lipgloss | MVU pattern, incremental | Yes |
| Deep Agents | Python | Textual | CSS variables, reactive | Yes (Textual default) |
| lazygit | Go | gocui fork | Direct gocui rendering | Partial |
| k9s | Go | tview/tcell | Tcell double-buffering | Yes |
| btop | C++ | Custom | Direct ANSI with gradient gen | Yes |
| yazi | Rust | Ratatui + Crossterm | Immediate mode + diffing | Yes |
| atuin | Rust | Ratatui | Immediate mode | Yes |

---

*Document created: 2026-06-10*
*Sources: Official docs, source code (GitHub), Claude Code from Source (claude-code-from-source.com), TUICommander, community themes, web research*
*Reference: TUI Design Skill at ~/.hermes/skills/creative/tui-design-skill/*
