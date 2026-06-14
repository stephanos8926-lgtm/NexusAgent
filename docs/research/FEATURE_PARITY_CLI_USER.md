# Feature Parity Research — CLI Agents (User/Workflow Perspective)

> Generated: 2026-07-19
> Perspective: Daily UX, commands, keybindings, session flow, tool interaction
> Scope: Claude Code CLI, Gemini CLI, Qwen Code CLI, OpenAI Codex CLI, Aider

---

## 1. Claude Code CLI (Anthropic)

**TUI Framework:** Ink (React-based) — React 19 support as of v7.0 (April 2026)
**Context Window:** Up to 1M tokens (Fable 5 model), 200K standard

### Keybindings (50+ customizable)

| Shortcut | Action | Context |
|----------|--------|---------|
| Ctrl+C | Interrupt / clear input | Global |
| Ctrl+D | Exit | Global |
| Ctrl+R | Reverse search history | Chat |
| Ctrl+L | Clear screen (redraw) | Chat |
| Ctrl+O | Toggle transcript viewer | Chat |
| Ctrl+B | Background tasks | Chat |
| Ctrl+G / Ctrl+X Ctrl+E | External editor | Chat |
| Ctrl+X Ctrl+K | Stop all subagents | Subagent tasks |
| Shift+Tab / Alt+M | Cycle permission modes | Chat |
| Meta+P | Model picker | Chat |
| Meta+O | Toggle fast mode | Chat |
| Meta+T | Toggle extended thinking | Chat |
| Ctrl+_ / Ctrl+Shift+- | Undo | Chat |
| Ctrl+S | Stash (summarize context) | Chat |
| Up/Down | History navigation | Chat |
| Cmd+K | Clear (fullscreen) | Chat |
| Escape | Interrupt Claude | Chat |

**Permission Modes** (cycle with Shift+Tab): default → acceptEdits → plan → auto → bypassPermissions

### Slash Commands (~100 total)

**Session & Context:** /clear, /compact, /context, /resume, /new, /rename
**Model & Output:** /model, /effort, /status, /config, /statusline, /theme, /color
**Planning & Review:** /plan, /diff, /code-review, /review, /security-review, /doctor
**Tools & Extensions:** /permissions, /mcp, /init, /memory, /hooks, /plugin, /agents
**Workflows & Sandbox:** /sandbox, /add-dir, /context, /effort, /btw, /workflows
**Account:** /login, /logout, /cost, /usage, /insights, /release-notes, /bug

### Security Model

- **Default**: Read-only with permission prompts for edits outside working directory
- **Sandbox modes**: Seatbelt (macOS), bubblewrap (Linux), custom profiles
- **Permission modes**: default, acceptEdits, plan, auto, bypassPermissions (5 levels)
- **CLAUDE.md hierarchy**: user/project/subdirectory — path-scoped rules load on file read
- **Auto-compaction**: At ~95% capacity, CLAUDE.md re-injected after compaction
- **Project-root CLAUDE.md**: Survives auto-compaction; path-scoped rules summarize away
- **Skills system**: Re-injected after compaction, large skills truncated to fit
- **24 hook events**: PreCompact, PostToolUse, PreToolUse, etc.
- **MCP servers**: Per-session, support stdio and HTTP transports

### Context Management

- Auto-compaction at ~95% capacity
- CLAUDE.md re-injected post-compaction
- Skills re-injected post-compaction
- Subagents keep large reads out of main context
- `/context` shows colored grid with optimization suggestions
- Memory system with 200-line/25KB limit (MEMORY.md)

### Unique Differentiators

1. **Agent Teams/workflows** — parallel subagent coordination
2. **CLAUDE.md hierarchical memory** — persistent project context
3. **24 hook events** — middleware hooks throughout agent lifecycle
4. **Fable 5** — 1M context window
5. **Desktop app** — parallel sessions + git worktrees, web version with cloud sandboxes
6. **Auto-mode** — 84% reduction in permission prompts with sandboxing
7. **Theme packs** — Catppuccin, Nord, Dracula, Tokyo Night, Gruvbox
8. **claude-skins** — 9 themes (Mythos, Netrunner, Mission Control, Retro86, Noir, Nebula, Sensei, Brutalist, Grimoire)

---

## 2. Gemini CLI (Google)

**TUI Framework:** Custom TypeScript/React TUI
**Context Window:** 2M tokens (Gemini 2.5 Pro)

### Keybindings

| Shortcut | Action |
|----------|--------|
| Ctrl+C | Quit |
| Ctrl+L | Clear screen |
| Ctrl+V | Paste |
| Ctrl+Y | Toggle YOLO mode |
| Ctrl+X | External editor |
| Ctrl+T | Toggle tool descriptions |
| Ctrl+R | Reverse search |
| Ctrl+P/N | History up/down |
| F12 | Debug console |
| Shift+Enter | Newline |
| Esc | Cancel |

### Slash Commands

**Session:** /clear, /model, /theme, /settings, /memory, /chat (save/resume/list/delete)
**Tools:** /tools, /skills, /mcp, /extensions, /agents
**Info:** /help, /stats, /auth, /about, /privacy
**Advanced:** /vim, /plan, /policies, /permissions, /directory, /ide, /hooks, /compress, /restore
**Misc:** /bug, /upgrade, /docs, /editor, /terminal-setup, /shells, /corgi (toggle mascot), /teleport

### Security Model

- **Trusted Folders system**: trust folder / parent / don't trust — 3 tiers
- **YOLO/AUTO_EDIT modes**: Require trusted workspace
- **Sandbox**: Docker/Podman/macOS Seatbelt
- **6 Seatbelt profiles**: permissive-open (default) through restrictive-closed
- **Conseca**: Dynamic security layer (behind flag)
- **PolicyEngine**: Shell command security rules
- **Folder trust discovery**: Security warnings when encountering untrusted folders

### Context Management

- **GEMINI.md hierarchy**: user/project/subdirectory context files
- **Chat checkpointing**: /restore saves/resumes conversation state
- **/compress**: Conversation summarization
- **Tool Output Distillation**: Large outputs saved to disk, structurally truncated for LLM
- **Progressive Message Normalization**: Full fidelity in "grace zone", proportional compression for older messages
- **Episodic Context Graph**: Graph-based context with pipeline orchestration for GC
- **Multi-directory workspace** support

### Unique Differentiators

1. **Free tier** — Google account authentication
2. **Multi-directory workspaces** — work across multiple projects simultaneously
3. **Checkpoint/restore** — save and resume conversation state persistently
4. **Tool Output Distillation** — large outputs offloaded to disk with LLM summarization
5. **Loop Detection Service** — monitors for repetitive patterns auto-recovery
6. **17 themes** — 10 dark + 7 light, custom via settings.json, live preview
7. **corgi mascot** — toggle with /corgi
8. **Seamless scrolling** — mouse support for scrollable UI
9. **Release channels** — nightly/preview/stable

---

## 3. Qwen Code CLI (Alibaba/Qwen)

**TUI Framework:** Custom TypeScript TUI (forked from Gemini CLI)
**Context Window:** Varies by model (Qwen3-Coder)

### Keybindings

| Shortcut | Action |
|----------|--------|
| Ctrl+C / Ctrl+D | Cancel / Exit |
| Ctrl+L | Clear |
| Ctrl+T | Toggle tool descriptions |
| Ctrl+Z / Shift+Z | Undo / Redo |
| Ctrl+R | Reverse search |
| Ctrl+X | External editor |
| Ctrl+V | Paste |
| Shift+Enter | Newline |
| Up/Down | History navigation |

### Slash Commands

**Session:** /help, /clear, /compress, /stats, /auth, /resume, /reset
**Model:** /model, /theme, /settings, /config
**Tools:** /mcp (desc/nodesc/schema), /tools (desc/nodesc), /skills, /memory (show/add/refresh)
**Context:** /remember, /forget, /dream
**Advanced:** /directory, /editor, /permissions, /approval-mode, /plan
**Extensions:** /extensions, /agents, /ide, /hooks, /init, /terminal-setup
**Misc:** /bug, /docs, /about, /language, /export, /copy, /setup-github, /insight

### Security Model

- **Approval modes**: default, auto-edit, plan, yolo (4 modes)
- **Sandbox**: Docker/Podman/macOS Seatbelt
- **6 Seatbelt profiles**: Same as Gemini CLI
- **Trusted folders**: Per-folder trust settings
- **Per-MCP server trust**: Each MCP server can have its own trust settings
- **QWEN_SERVER_TOKEN**: Bearer auth for daemon mode

### Context Management

- **QWEN.md / AGENTS.md / PROJECT.md**: Hierarchical context files
- **/compress**: Conversation summarization
- **--all-files**: Include all files in context
- **Session token limits**: Configurable per-session
- **Daemon mode** (`qwen serve`): HTTP+SSE exposing ACP protocol

### Unique Differentiators

1. **Daemon mode** — `qwen serve` exposes ACP over HTTP+SSE for multi-client sharing
2. **MCP server lifetime** — per-session with future cross-session sharing planned
3. **Event fan-out** — SSE with Last-Event-ID reconnect, 15s heartbeat
4. **Multi-protocol providers** — OpenAI/Anthropic/Gemini/Alibaba Cloud support
5. **SDKs** — TypeScript, Python, Java client SDKs
6. **Headless mode** — stream-json output for CI/CD
7. **ACP transport** — Streamable HTTP at /acp endpoint
8. **Stage 1.5 state CRUD** — daemon-side control plane (10+ routes)

---

## 4. OpenAI Codex CLI

**TUI Framework:** Rust-based (custom)
**Context Window:** Model-dependent (GPT-5.5 default)

### Keybindings

| Shortcut | Action |
|----------|--------|
| Ctrl+C | Cancel |
| Ctrl+D | Exit |
| Ctrl+L | Clear screen |
| Ctrl+R | Reverse history search (v0.121+) |
| Ctrl+G | External editor |
| Esc x2 | Edit previous message |
| Enter (while running) | Inject instructions |
| Tab (while running) | Queue follow-up |
| @ | Fuzzy file search |
| ! | Shell command |
| Alt+M | Cycle models |
| Alt+E | Cycle reasoning |
| Alt+,/. | Reasoning depth |
| Shift+Enter | Newline |
| Cmd+K / Cmd+Shift+P | Command menu |

### Slash Commands

**Session:** /help, /quit, /exit, /new, /resume, /fork, /title
**Model:** /model, /personality, /raw, /agent, /fast
**Review:** /diff, /review, /plan, /goal, /feedback
**Tools:** /permissions, /mcp, /apps, /skills, /plugins, /ps
**Memory:** /memories, /compact, /statusline
**Misc:** /config, /status, /vim, /hooks, /environment, /about, /logout, /keymap, /experimental

### Security Model (Most Sophisticated)

- **Triple-gated safety**: Network off by default + OS sandbox + approval policy
- **Sandbox modes** (3): workspace-write (default), read-only, danger-full-access
- **Approval policies**: untrusted, on-request, never, auto_review
- **Auto-review reviewer agent**: Automatically approves low-risk actions, escalates high-risk
- **Rule-based exec policy**: DSL-based rules in ~/.codex/rules/*.rules and workspace .codex/rules/*.rules
- **Bubblewrap sandbox**: Default on Linux since v0.115.0
- **Protected paths**: Specific paths remain protected even in writable roots
- **Profile system**: CI/CD profiles for automated environments
- **requirements.toml**: Enterprise-managed requirements users cannot override

### Context Management

- **AGENTS.md** (project) + **~/.codex/instructions.md** (global)
- **/compact** command + auto-compaction via summarization model
- **/status** shows context usage breakdown
- **goal mode**: Persistent objectives (v0.128+)
- **JSON-RPC app-server interface**
- **SQLite database** with job ownership leases (1-hour expiry)

### Unique Differentiators

1. **Rust implementation** — speed and safety
2. **Bubblewrap sandbox** — OS-level filesystem + network isolation
3. **Rule-based exec policy** — custom DSL for command matching
4. **Auto-review agent** — automatic approval review subagent
5. **Image inputs/generation** — multimodal support
6. **Codex Cloud** — remote TUI via WebSocket, app-server subcommand
7. **Local code review** — built-in review agent
8. **Desktop app** — full GUI wrapper
9. **Multi-runtime support** — consistent behavior across surfaces

---

## 5. Aider

**TUI Framework:** Python (prompt_toolkit + custom rendering)
**Context Window:** Varies by model (supports any LLM including local/Ollama)

### Keybindings

| Shortcut | Action |
|----------|--------|
| Ctrl+C (x2) | Force exit |
| Ctrl+A/E | Line start/end |
| Ctrl+K/U | Kill/yank |
| Ctrl+Y/W | Yank/pop |
| Ctrl+P/N | History up/down |
| Ctrl+R | Reverse search |
| Ctrl+L | Clear |
| Ctrl+X Ctrl+E | External editor |
| Ctrl+Up/Down | Per-message history |
| Meta-Enter | Multiline |
| Tab (Vi mode) | Mode switch |

### Slash Commands (43 total)

**Modes:** /code, /ask, /architect, /help, /chat-mode
**Files:** /add, /drop, /read-only, /edit, /save
**Git:** /commit, /diff, /undo, /lint, /context
**Model:** /model, /models, /editor-model, /weak-model
**Session:** /clear, /reset, /load, /map, /map-refresh
**Actions:** /run, /test, /voice, /web, /ok
**Info:** /reasoning-effort, /think-tokens, /tokens, /report, /settings
**Advanced:** /shell-completions, /notifications, /browser, /gui

### Security Model

- No built-in sandbox — relies on user's environment
- Git-based undo (every change is a commit)
- /read-only mode for files
- Manual file management (/add, /drop — explicit control)
- Dry-run mode for commands
- Commit --dry-run option

### Context Management

- **Repo-map**: tree-sitter + PageRank algorithm (default 1K tokens, configurable)
- **Binary search fitting**: Optimizes repo map to fit token budget
- **Caching**: mtime-based invalidation
- **Expansion**: 8x expansion when no files in chat
- **Architect mode**: Two-model approach (architect + editor)
- **MMAP.md**: Auto memory
- **Streamlit GUI mode**: Optional web UI

### Unique Differentiators

1. **Voice-to-code** — Whisper API integration, /voice command
2. **Architect/editor two-model mode** — planner + executor pattern
3. **Automatic git commits** — LLM-generated commit messages per turn
4. **Repo-map with PageRank** — smart context selection without full scan
5. **Most model-flexible** — supports Ollama, any LLM provider
6. **43 slash commands + 175+ CLI flags**
7. **Streamlit GUI mode** — web-based interface option
8. **Polyglot coding leaderboard** — benchmarked across languages
9. **Self-improving** — ~80% of codebase written by itself
10. **Image + web page input** — multimodal context ingestion

---

## Feature Parity Matrix (Our Use Case)

| Feature | Claude Code | Gemini CLI | Qwen Code | OpenAI Codex | Aider | NexusAgent |
|---------|-------------|------------|-----------|--------------|-------|------------|
| Token-by-token streaming | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Multi-model support | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sandbox/seatbelt | ✅ | ✅ | ✅ | ✅ (bwrap) | ❌ | ❌ |
| Auto-approval modes | 5 modes | YOLO/AUTO_EDIT | 4 modes | 3+reviewer | ❌ | yolo flag |
| Session persistence | ✅ | ✅ (checkpoint) | ✅ (daemon) | ✅ (resume) | ✅ (git) | ✅ |
| Context compaction | auto + /compact | auto + /compress | /compress | auto + /compact | repo-map | /compact |
| Slash commands | ~100 | ~50 | ~40 | ~40 | 43 | ~25 |
| Theming | 8+ themes | 17 themes | inherited | tmTheme | ✅ (flags) | 7 themes |
| Status bar info | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Subagent delegation | ✅ | ✅ (agents) | ✅ | ✅ | ❌ | ✅ |
| Skill/plugin system | skills + MCP | skills + MCP | skills + MCP | skills + plugins | ❌ | ✅ |
| Inline diffs | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Git integration | hooks | basic | basic | basic | deep | basic |
| Voice input | ❌ | ❌ | ❌ | ❌ | ✅ (Whisper) | ❌ |
| Web UI | ✅ (cloud) | ❌ | ✅ (daemon) | ✅ (Codex Cloud) | ✅ (GUI) | ✅ (Gradio) |

### Priority Classification for NexusAgent

**CRITICAL (Must-have for production):**
- Inline diff display (all competitors have this)
- Git integration / status indicator
- Compact command with visual feedback
- Repo-map equivalent for context efficiency

**Mandatory (Competitive parity):**
- Improved /help with categorized commands
- Session save/restore (persistent)
- Auto-approval mode cycling (multiple levels)
- Theming with live preview

**Nice-to-have (Differentiators):**
- Voice input (Aider unique)
- Web daemon mode (Qwen unique)
- Architect mode (Aider unique)
- Multi-directory workspace (Gemini unique)
