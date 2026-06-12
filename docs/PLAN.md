# Master Sprint Plan — NexusAgent TUI Overhaul + Feature Parity Research

> **Date**: 2026-07-19
> **Author**: OWL (Lucien)
> **Status**: PLAN — awaiting approval before execution
> **Test Baseline**: 475 pass / 20 fail (all pre-existing)

---

## CONTEXT

The NexusAgent TUI has significant runtime bugs and design gaps identified through prior audit sessions:

**Confirmed TUI Bugs (from user reports + code audit):**
1. **Fake streaming** — tokens accumulate in `_streaming_response` string, then dumped as single event via `_finalize_response()`. No token-by-token rendering.
2. **No search providers wired** — code references `search_web` tool but no actual provider registered.
3. **Word wrapping broken** — `wrap=True` on `RichLog` doesn't work reliably with long URLs, paths, or code blocks.
4. **Tool calls show raw JSON** — `format_arg_value()` output not properly escaped/formatted for RichLog markup.
5. **Greeting may not render** — clears log immediately after writing greeting, causing race condition.
6. **Status bar is minimal** — single spinner widget, no model/CWD/branch/token info.
7. **No semantic color system** — hardcoded hex codes throughout CSS.
8. **Header + Footer waste 40% chrome** — Header widget, Footer widget, auto-approve badge, queue status all consume screen real estate.

**Goal**: Fix all TUI bugs + achieve feature parity with Claude Code / Gemini CLI / Qwen Code CLI TUI agents, focusing on aesthetics, rendering quality, and developer experience.

---

## PHASE 0: FOUNDATION (Pre-Sprint)

**Machine**: Workstation (orchestrator)
**Duration**: ~15 min
**Workers**: 0

| Task | Description | Verification |
|------|-------------|-------------|
| 0.1 | Commit all current changes to git, push to GitHub | `git push origin main` |
| 0.2 | Clean up test project.json/references/ left by testing | `rm -rf project.json references/` in test dirs |
| 0.3 | Verify test baseline: 475 pass / 20 fail | `pytest tests/ -q --tb=no` |

---

## PHASE 1: DEEP AUDIT + SEMANTIC INDEX

**Machine**: Workstation (main agent) + Server (parallel indexer)
**Duration**: ~30 min
**Workers**: 3 parallel (1 self-audit, 2 indexers)

### 1A: TUI Deep Audit (Main Agent)

Comprehensive audit of the entire TUI subsystem with focus on:
- **Message rendering pipeline**: event → widget → display. Trace every event type.
- **Streaming architecture**: How `_write_response_chunk` and `_finalize_response` interact. Token flow.
- **Widget composition**: `compose()` tree, CSS inheritance, layout performance.
- **Slash command completeness**: Every `/command` tested against actual behavior.
- **Theme system**: Current 5-theme cycling vs. semantic token approach.
- **Responsive behavior**: SIGWINCH handling, breakpoint system, minimum sizes.
- **Error handling**: Connection loss, server errors, malformed events.
- **Keyboard handling**: All bindings, conflicts, missing bindings.

**Output**: `docs/TUI_AUDIT.md` — structured bug list with severity + fix approach

### 1B: Semantic Codebase Index (Parallel Indexer — Server)

Dispatch to `rapidwebs-01`:
- Map all TUI-related files with their responsibilities
- Cross-reference: which events trigger which display updates
- Dependency graph: tui.py → tui_widgets.py → tui_formatters.py → config.py
- Identify dead code, unused functions, orphaned CSS rules

**Output**: `docs/TUI_SEMANTIC_MAP.md`

### 1C: Codebase State Verification (Parallel Indexer — Server)

Dispatch to `rapidwebs-01`:
- Verify all files in `docs/CODEBASE_MAP.md` match actual codebase
- Check for files mentioned in map but missing from disk
- Check for files on disk but missing from map
- Update `docs/STATE.md` if stale

**Output**: Updated `docs/STATE.md`

---

## PHASE 2: FEATURE PARITY RESEARCH — CLI AGENTS

**Machine**: Workstation + Server (dual-perspective research)
**Duration**: ~45 min
**Workers**: 4 parallel (2 per machine, different perspectives)

### Research Targets

| Tool | Developer | TUI Framework | Key Differentiator |
|------|-----------|---------------|-------------------|
| **Claude Code CLI** | Anthropic | Ink (React) | Plan mode, tool visualization, inline diffs |
| **Gemini CLI** | Google | Custom (TS) | Multi-agent, context compaction UI, inline citations |
| **Qwen Code CLI** | Alibaba/Qwen | Custom (TS) | Bilingual, session management, tool streaming |
| **OpenAI Codex** | OpenAI | Custom | Sandbox mode, approval flow |
| **Aider** | Aider | Custom (Python) | Git-native, diff-first UI |
| **Continue** | Continue.dev | VS Code ext | IDE-native, tab-completion |

### 2A: Feature Parity Matrix — Workstation (User/Workflow Perspective)

**Lens**: Daily UX, commands, keybindings, session flow, tool interaction patterns

Research and document for each tool:
- **Nice-to-have features**: Quality-of-life improvements (themes, animations, ASCII art)
- **Mandatory for our use case**: Session management, tool approval, streaming, interrupt
- **CRITICAL**: Security model, sandboxing, error recovery, context management

**Output**: `docs/research/FEATURE_PARITY_CLI_USER.md`

### 2B: Feature Parity Matrix — Server (Architecture/Technical Perspective)

**Lens**: Internal design, agent loops, tool execution, memory systems, performance

Research and document for each tool:
- Agent loop architecture (LangGraph vs custom vs ReAct)
- Tool execution model (async, sandboxed, approval-gated)
- Memory/context management (compaction, summarization, token budgeting)
- Streaming implementation (WebSocket, SSE, IPC)
- Extension/plugin system

**Output**: `docs/research/FEATURE_PARITY_CLI_ARCH.md`

### 2C: Synthesis

Merge both perspectives into a single prioritized feature matrix:
- **P0 (Critical)**: Must-have for production use
- **P1 (Mandatory)**: Required for competitive parity
- **P2 (Nice-to-have)**: Differentiators

**Output**: `docs/research/FEATURE_PARITY_SYNTHESIS.md`

---

## PHASE 3: FEATURE PARITY RESEARCH — TUI/AESTHETICS

**Machine**: Workstation + Server (dual-perspective research)
**Duration**: ~45 min
**Workers**: 4 parallel (2 per machine)

### Research Focus

**TUI Terminal React Development Tools** — specifically:
- Ink (React for CLI) — component model, layout, styling
- Textual (Python) — our current framework, advanced patterns
- Bubble Tea (Go) — MVU architecture, rendering model
- Ratatui (Rust) — immediate-mode, performance

### 3A: TUI Aesthetics Research — Workstation (Visual/UX Perspective)

**Lens**: Beauty, rendering quality, visual polish, typography, color theory

Research and document:
- **Color systems**: Semantic tokens, theme engines, dark/light/auto, community palettes (Catppuccin, Gruvbox, Nord, Tokyo Night)
- **Layout patterns**: 7 canonical layouts, responsive design, density choices
- **Animation**: Spinner design, progress indicators, transition effects
- **Typography in terminals**: Unicode box-drawing, Nerd Font icons, ASCII fallback
- **Message rendering**: Markdown rendering quality, code highlighting, collapsible sections
- **Status bar design**: Information density, smart truncation, context-aware content
- **Exemplar apps**: Deep dive into lazygit, k9s, btop, helix, yazi, atuin, fzf visual design

**Output**: `docs/research/TUI_AESTHETICS_VISUAL.md`

### 3B: TUI Technical Patterns — Server (Implementation Perspective)

**Lens**: Performance, architecture, framework capabilities, rendering pipeline

Research and document:
- **Textual advanced patterns**: Custom widgets, CSS variables, layout: stream, gc.freeze()
- **Streaming rendering**: Token-by-token update strategies, debouncing, smooth scrolling
- **Performance optimization**: Virtual scrolling, lazy rendering, incremental placement
- **Input handling**: History, autocomplete, file path completion, image paste
- **Signal handling**: SIGWINCH, SIGTSTP, terminal restoration, panic handlers
- **Testing TUIs**: Textual's test framework, snapshot testing, headless rendering

**Output**: `docs/research/TUI_AESTHETICS_TECHNICAL.md`

### 3C: Synthesis

Merge into actionable TUI design spec:
- Color palette recommendations (with specific hex codes)
- Layout specification (pixel-perfect ASCII mockups)
- Widget hierarchy and CSS architecture
- Streaming implementation approach
- Theme system design
- Animation and interaction patterns

**Output**: `docs/research/TUI_AESTHETICS_SYNTHESIS.md`

---

## PHASE 4: TUI IMPLEMENTATION — BUG FIXES + AESTHETICS

**Machine**: Workstation (orchestrator) + Server (parallel workers)
**Duration**: ~90 min
**Workers**: Up to 6 parallel (3 per machine)

### Sprint Structure

**Phase 4A: Bug Fixes (Critical Path)**

| Task | Description | Files | Machine |
|------|-------------|-------|---------|
| 4A.1 | Fix streaming: token-by-token rendering | tui.py | Workstation |
| 4A.2 | Fix word wrapping: proper RichLog configuration | tui.py CSS | Workstation |
| 4A.3 | Fix tool call display: proper markup escaping | tui_formatters.py | Workstation |
| 4A.4 | Fix greeting race condition | tui.py | Workstation |
| 4A.5 | Fix search provider wiring | tools/ + config | Server |

**Phase 4B: Layout Overhaul (Parallel)**

| Task | Description | Files | Machine |
|------|-------------|-------|---------|
| 4B.1 | Remove Header + Footer, save 2 lines | tui.py compose() | Workstation |
| 4B.2 | Implement semantic color system | tui.py CSS + new theme.py | Workstation |
| 4B.3 | Build rich status bar (model, CWD, branch, tokens) | tui_widgets.py | Server |
| 4B.4 | Implement responsive breakpoints | tui_widgets.py | Server |

**Phase 4C: Visual Polish (Parallel)**

| Task | Description | Files | Machine |
|------|-------------|-------|---------|
| 4C.1 | Catppuccin Mocha + Gruvbox Dark + Nord themes | themes/*.tcss | Workstation |
| 4C.2 | Improved message widgets (User, Assistant, Tool, Error) | new messages.py | Server |
| 4C.3 | Markdown rendering improvements (code blocks, tables) | tui_formatters.py | Server |
| 4C.4 | Spinner + animation improvements | tui_widgets.py | Workstation |

**Phase 4D: Feature Parity Additions (Parallel)**

| Task | Description | Files | Machine |
|------|-------------|-------|---------|
| 4D.1 | Session state indicator in status bar | tui.py + session.py | Server |
| 4D.2 | Token usage display (real-time) | tui.py + server.py | Server |
| 4D.3 | Improved /help with full command reference | tui.py | Workstation |
| 4D.4 | /theme command with theme preview | tui.py | Workstation |

### Implementation Rules

1. **No breaking changes** — all additive, existing tests must pass
2. **Commit-per-phase** — each sub-phase gets its own commit for rollback
3. **TDD for new logic** — write failing test first
4. **Test after every merge** — 475 pass baseline must hold
5. **Semantic colors only** — no hardcoded hex in new code
6. **ASCII fallback** — all Unicode must have ASCII equivalent
7. **NO_COLOR support** — respect https://no-color.org

---

## PHASE 5: ISOLATED WORKTREE WORKER SKILL + SCRIPT

**Machine**: Workstation
**Duration**: ~30 min
**Workers**: 1

### 5A: Skill Enhancement

Update `isolated-worktree-worker` skill with:
- Companion script CLI entry point documentation
- Server-side dispatch patterns
- Result collection via SSH
- State synchronization

### 5B: Companion Script

Enhance `scripts/worktree-worker.py` with:
- `init` command: set up isolated Hermes config in worktree
- `doctor` command: diagnose common issues (already exists, enhance)
- `sync` command: bidirectional state sync (already exists, enhance)
- Better error handling and user feedback
- JSON output mode for all commands

---

## PHASE 6: FINAL VERIFICATION + DOCUMENTATION

**Machine**: Workstation
**Duration**: ~15 min
**Workers**: 0

| Task | Description | Verification |
|------|-------------|-------------|
| 6.1 | Full test suite: 475+ pass, 0 new failures | `pytest tests/ -q` |
| 6.2 | TUI visual inspection (if possible) | Manual |
| 6.3 | Update CODEBASE_MAP.md | Verify all new files mapped |
| 6.4 | Update SEMANTIC_INDEX.md | Verify all new connections documented |
| 6.5 | Commit + push all changes | `git push origin main` |
| 6.6 | Clean up worktrees | `worktree-worker.py list` → destroy all |

---

## RISK MITIGATION

| Risk | Mitigation |
|------|-----------|
| Test regression after TUI changes | Run `pytest` after every commit, not just at end |
| Subagent timeout on large tasks | Break into 3-4 file scopes, check git log after timeout |
| CSS parse errors in new themes | Test each theme file individually before deploying |
| Breaking existing slash commands | Test every `/command` after changes |
| OpenRouter truncation | Keep subagent contexts small, use file paths not inline code |
| RAM exhaustion on workstation | Offload heavy work to server, max 2 local subagents |

---

## SUCCESS CRITERIA

- [ ] All 5 confirmed TUI bugs fixed (streaming, wrapping, tool display, greeting, status bar)
- [ ] Chat area uses ≥70% of terminal real estate (no Header/Footer)
- [ ] Word wrapping works for all text types
- [ ] Streaming shows token-by-token (not accumulated dump)
- [ ] Status bar shows model, CWD, branch, tokens in 1 line
- [ ] 3 community themes ship (Catppuccin Mocha, Gruvbox Dark, Nord)
- [ ] All existing slash commands work unchanged
- [ ] NO_COLOR support
- [ ] Test suite: 475+ pass, 0 new failures
- [ ] Feature parity research reports saved to `docs/research/`
- [ ] Semantic codebase index updated
- [ ] All changes committed and pushed to GitHub
- [ ] No breaking changes to server or session layers
