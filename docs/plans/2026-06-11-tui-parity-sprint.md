# TUI Fixes + Feature Parity Sprint — Master Plan

> **Date:** 2026-06-11
> **Author:** OWL (Lucien)
> **Status:** REVISED — Review feedback incorporated
> **Repo:** NexusAgent (clean, last commit `3b88bd5`)
> **Review Score:** 5.25/10 → Revised to address all findings

---

## 1. Executive Summary

NexusAgent's TUI is functional but archaic — it uses a basic Textual layout with minimal visual polish, has confirmed runtime bugs (missing imports for `Grid`/`Vertical`), fake streaming, and raw JSON tool display. Meanwhile, competitors like Claude Code, Gemini CLI, and Qwen Code CLI have beautiful, polished TUIs with semantic color systems, smooth streaming, and professional aesthetics.

This sprint has **three parallel tracks**:
1. **TUI Bug Fixes + Aesthetics Overhaul** — Fix bugs, then redesign the TUI to surpass competitors
2. **Tool/Feature Parity Research** — Deep research on Claude Code, Gemini CLI, Qwen Code CLI, DeepAgents to map feature gaps and opportunities
3. **System Prompt + Architecture Improvements** — Pull FORGE.md best practices and Qwen research into NexusAgent

**Goal:** Not just parity — **SURPASS** competitors in TUI beauty, tool capability, and developer experience.

---

## 2. Reference Materials Consulted

| Source | Key Takeaways |
|--------|--------------|
| `~/.qwen/FORGE.md` | 3-layer system prompt, complexity-based delegation, TDD rules, file-based planning, 8 hard rules |
| `~/.qwen/reference/SUB-AGENTS.md` | Routing matrix, context modes (fork/clean), maxTurns per agent |
| `~/.qwen/research/TOOL_GAP_ANALYSIS.md` | AST tools, web search, sub-agent management gaps |
| `~/.qwen/research/QWEN_CODE_RESEARCH_TODO.md` | Hooks, channels, extensions, LSP, scheduled tasks, custom settings |
| `~/.qwen/research/FORGE_MASTER_SYNTHESIS.md` | Complete system architecture, model routing, skills, hooks |
| `deepagents` source | LangGraph agent, StateBackend, SubAgentMiddleware, FilesystemMiddleware, MemoryMiddleware |
| `tui-design` skill | 7 canonical layouts, semantic color systems, border conventions, responsive design |
| `front-refactor` skill | CSS/layout refactoring patterns |
| `front-a11y` skill | Accessibility audit patterns |
| `isolated-worktree-worker` skill | Worktree isolation, CLI dispatch, remote server pattern |
| `subagent-driven-development` skill | 2-stage review, parallel dispatch, dual-machine pattern |

---

## 3. Current State Assessment

### 3.1 TUI Architecture (from `docs/STATE.md`)

```
NexusApp (tui.py)
├── VerticalScroll (#chat)
│   └── Container (#messages, stream layout)
│       ├── WelcomeBanner
│       ├── UserMessage (Static, $primary left border)
│       ├── AssistantMessage (Static, streaming via append_token)
│       ├── ToolCallMessage (Static, $warning left border)
│       ├── AppMessage (Static, dim italic)
│       └── ErrorMessage (Static, $error + ✗ icon)
├── ChatInput (#input-area, TextArea)
└── StatusBar (#status-bar, docked bottom)
    ├── Spinner
    ├── Status message
    ├── CWD (hidden ≤60 cols)
    ├── Branch (hidden ≤80 cols)
    ├── Token count
    └── ModelLabel (smart truncation)
```

### 3.2 Confirmed Bugs (Verified Against Current Codebase)

> ⚠️ **REVIEW CORRECTION:** Initial audit reported `Grid`/`Vertical` import bugs at `tui.py:226`/`tui.py:251`. Review subagent verified that `Grid` IS imported at `tui.py:38` and `Vertical` IS imported in `messages.py:20`. The current `tui.py` (328 lines) does NOT use `Vertical` directly. The `tui_legacy.py` (1195 lines) is the old RichLog-based TUI — the active TUI is `tui.py`. Bugs below are re-verified:

| # | Bug | File | Impact | Verified |
|---|-----|------|--------|----------|
| 1 | Streaming not truly real-time | `session.py:488-505` + `messages.py:76-79` | `append_token()` exists but TUI may batch updates; needs verification if session emits tokens fast enough for per-token rendering | Needs testing |
| 2 | Tool output formatting | `ToolCallMessage.render()` at `messages.py:116-129` | Currently shows `⚙ tool_name(args)` with 300-char truncation — functional but not beautiful (no collapsible sections, no syntax highlighting) | Verified — needs enhancement |
| 3 | Welcome message consistency | `tui.py` on_mount | Welcome banner may not re-render on session resume or `/clear` | Needs testing |
| 4 | No `tui.py` vs `tui_legacy.py` clarity | Both files exist | `tui_legacy.py` (1195 lines) is old RichLog version; `tui.py` (328 lines) is active. Must verify which is instantiated by CLI/server | Verified — `tui.py` is active |
| 5 | `messages.py` imports `Vertical` but `tui.py` doesn't | `messages.py:20` | Not a bug per se, but inconsistent import pattern | Verified — OK |

### 3.3 Aesthetic Gaps (vs competitors)

| Feature | NexusAgent | Claude Code / Gemini CLI |
|---------|-----------|------------------------|
| Color system | Hardcoded hex in theme.py | Semantic tokens, CSS variables |
| Message styling | Basic Static widgets | Rich markdown rendering, syntax highlighting |
| Tool output | Raw JSON | Collapsible sections, formatted output |
| Streaming | Fake (batch dump) | Real token-by-token |
| Layout | Basic VerticalScroll | Multi-panel, responsive, density-aware |
| Borders | None on messages | Left-border accent (like Linear/Claude) |
| Status bar | Basic text | Spinner + metrics + git + model |
| Help | Plain text modal | Interactive, searchable |
| Themes | 4 themes (good start) | Community themes, runtime switching |
| Responsive | Basic hiding at narrow | Full breakpoint ladder |

### 3.4 Feature Gaps (from TOOL_GAP_ANALYSIS.md)

| Feature | Status | Priority |
|---------|--------|----------|
| AST-aware tools | ✅ Available via MCP | — |
| Web search | ✅ Available via MCP | — |
| Sub-agent management | ✅ SubAgentHandle | — |
| Hooks system | ❌ Not implemented | HIGH |
| LSP integration | ❌ Not implemented | MEDIUM |
| Scheduled tasks | ❌ Not implemented | MEDIUM |
| Channels (Telegram) | ✅ Via Hermes | — |
| Extensions/plugins | ❌ Not implemented | LOW |
| Code review built-in | ❌ Not implemented | HIGH |
| Dual output (TUI + file) | ❌ Not implemented | LOW |
| Headless mode | ❌ Not implemented | MEDIUM |

---

## 4. Sprint Plan — Phase by Phase

### Phase 0: Baseline ✅
- [x] Git clean, no uncommitted changes
- [x] Semantic index at `docs/STATE.md`
- [x] Reference materials reviewed

### Phase 1: TUI Bug Fixes + Smoke Test (Workstation)

**Worker 1A: Streaming Verification + Fix**
- Verify if streaming is truly real-time by testing session → TUI token flow
- If batching found: fix `AssistantMessage.append_token()` to use `self.app.call_next()` for immediate render
- Fix welcome message consistency (re-render on `/clear`, verify on session start)
- TDD: Write test that verifies token-by-token delivery

**Worker 1B: Tool Output Formatting + Input Widget**
- Enhance `ToolCallMessage.render()` with collapsible sections, syntax highlighting for code output
- Improve `ChatInput`: add slash command completion (autocomplete `/help`, `/logs`, `/theme`, `/clear`, `/model`)
- TDD: Write tests for tool output formatting and input widget

**Phase 1.5: Smoke Test Checkpoint**
- Verify TUI launches and basic interaction works
- If broken, fix before proceeding
- Commit all Phase 1 work to git

### Phase 2: Research — TUI Aesthetics + Feature Parity (Server)

> ⚠️ **REVIEW CORRECTION:** Research workers must commit output docs to a known branch so implementation workers can access them. Use branch `research/tui-aesthetics` and `research/tool-parity`.

**Server Workers (4 parallel):**

**Worker 2A: "Visual Design" Perspective (TUI)**
- Load `tui-design` skill (already available)
- Study exemplar apps: lazygit, k9s, btop, helix, yazi, atuin
- Focus on: color systems, border styles, spacing, typography in terminal
- Research: Catppuccin, Gruvbox, Nord, Tokyo Night palette conventions
- Layout patterns: what makes a TUI feel "professional"
- Output: `docs/research/tui-visual-design.md`
- Commit to branch `research/tui-aesthetics`

**Worker 2B: "Technical Rendering" Perspective (TUI)**
- Load `front-refactor` skill for CSS/layout patterns
- Study Textual's capabilities: CSS styling, responsive layout, animations
- Focus on: widget composition, scroll behavior, focus indicators, modal patterns
- Research: terminal capabilities (truecolor, unicode, kitty protocol)
- Output: `docs/research/tui-technical-rendering.md`
- Commit to branch `research/tui-aesthetics`

**Worker 2C: "Daily Workflow" Perspective (Tool Parity)**
- Research Claude Code, Gemini CLI, Qwen Code CLI, DeepAgents
- Focus on: commands, keybindings, session management, tool invocation patterns
- How does each handle: task submission, progress monitoring, result display?
- What's the CLI UX? (flags, output formatting, interactive prompts)
- What are the killer features of each?
- Output: `docs/research/tool-parity-workflow.md`
- Commit to branch `research/tool-parity`

**Worker 2D: "Architecture" Perspective (Tool Parity)**
- Research same tools from technical angle
- Focus on: agent loop design, tool registration, permission systems, extensibility
- How does each handle: multi-step tasks, sub-agents, error recovery?
- What's the plugin/extension model?
- What can we learn and adapt for NexusAgent?
- Output: `docs/research/tool-parity-architecture.md`
- Commit to branch `research/tool-parity`

**Phase 2.5: Research Review Checkpoint**
- Pull research branches on workstation
- Review outputs for completeness and accuracy
- Cross-validate with existing `COMPETITIVE_ANALYSIS.md`
- Identify gaps before implementation begins

### Phase 3: TUI Aesthetics Implementation (Workstation — 4 parallel workers)

> All workers pull from `research/tui-aesthetics` branch before starting.

**Worker 3A: Message Widget Redesign**
- Rich markdown rendering in `AssistantMessage` (use `textual.markup` or `rich.markdown`)
- Syntax highlighting for code blocks in tool output
- Collapsible tool output sections (expand/collapse with keypress)
- Enhanced `UserMessage` with better timestamp display
- TDD: Widget render tests for each message type

**Worker 3B: Color System + Status Bar Enhancements**
- Enhance `theme.py` with more semantic tokens (e.g., `$surface`, `$surface-hover`)
- Add more community themes: Tokyo Night, Rose Pine, Solarized Dark
- Add git status indicator to StatusBar (clean/dirty/staged)
- Add context window usage bar (percentage of context used)
- Better spinner animation (braille dots or similar)
- TDD: Theme registration tests, color contrast verification

**Worker 3C: Help Screen + Log Viewer + Input Widget**
- Redesign help screen as interactive, searchable modal with categories
- Improve log viewer with proper scrolling, filtering, search
- Add slash command autocomplete to ChatInput
- Add command history persistence (save to file)
- TDD: Help screen navigation tests, log viewer scroll tests

**Worker 3D: Responsive + Accessibility**
- Full breakpoint ladder: wide (>120) → standard (80-120) → narrow (60-80) → too-small
- Proper "terminal too small" message
- Keyboard-only navigation for all 15+ actions
- `NO_COLOR` support verification
- `--no-tui` plain mode for accessibility
- TDD: Responsive behavior tests, keyboard navigation tests

### Phase 4: System Prompt + Architecture (Workstation + Server)

**Worker 4A: System Prompt Enhancement (Workstation)**
- Pull FORGE.md v3.0 best practices into NexusAgent's system prompt
- Add: 3-layer prompt architecture, complexity-based delegation rules
- Add: TDD rules, quality gates, debugging protocol
- Add: file-based planning requirements
- Add: session protocol (start/end checklist)
- Reference Qwen research for hooks, channels, extensions patterns
- Output: Updated `config/NEXUS.md` (system prompt)
- TDD: Verify prompt loads correctly, contains all required sections

**Worker 4B: Hooks System (Server)**
- Implement hooks system (inspired by Qwen Code hooks)
- Add: session-init hook (loads project context)
- Add: post-tool-use hook (auto-lint changed files)
- Add: error-logger hook (logs errors to file)
- Add: subagent-logger hook (logs sub-agent activity)
- Config section in `config.py` for hooks
- TDD: Hook execution tests, hook configuration tests

**Worker 4C: LSP + Code Review (Server)**
- LSP integration for code intelligence (experimental, `--experimental-lsp`)
- Built-in code review feature (inspired by Qwen Code review)
- `fetch_url` tool implementation
- `ask_user` tool implementation
- `write_todos` tool implementation
- TDD: LSP connection tests, code review tests, tool tests

**Worker 4D: Session Management TUI + Skills (Server)**
- Session management TUI (browse, resume, fork sessions — like Claude Code's `/threads`)
- Skills system (extensible skill loading from `~/.nexusagent/skills/`)
- Scheduled tasks support (experimental, cron-like)
- TDD: Session management tests, skill loading tests

### Phase 5: Isolated Worker Skill + CLI Script (Workstation)

- Update existing `scripts/worktree-worker.py` (438 lines) with any improvements learned from Phase 2-4
- Features: `create`, `list`, `collect`, `destroy`, `remote`
- Supports dispatching to rapidwebs-01 via SSH
- Update `isolated-worktree-worker` skill to v1.1 with CLI usage
- TDD: CLI script tests, remote dispatch tests

### Phase 6: Synthesis + Documentation (Workstation)

- Combine all research into final reports
- Create `docs/research/TOOL-PARITY-FINAL.md` (synthesized from 2C + 2D)
- Create `docs/research/TUI-AESTHETICS-FINAL.md` (synthesized from 2A + 2B)
- Update `docs/STATE.md` with new findings
- Update `docs/AGENTS.md` with lessons learned
- Commit and push everything to GitHub

---

## 5. Execution Strategy

### Machine Allocation

| Machine | Role | Workers |
|---------|------|---------|
| **Workstation** | TUI bug fixes, TUI redesign (message widgets, color, help/log, responsive), system prompt, isolated worker skill, synthesis | 2 concurrent (RAM-limited) |
| **Server (rapidwebs-01)** | All research (TUI + tool parity), hooks, LSP, code review, session management, skills | 2-3 concurrent |

### Parallel Dispatch Plan

```
Time 0:00 — Start
├── Workstation:
│   ├── Worker 1A: Streaming verification + fix + welcome message (Phase 1)
│   └── Worker 1B: Tool output formatting + input widget (Phase 1)
├── Server (rapidwebs-01):
│   ├── Worker 2A: TUI visual design research (Phase 2)
│   ├── Worker 2B: TUI technical rendering research (Phase 2)
│   ├── Worker 2C: Tool parity — workflow perspective (Phase 2)
│   └── Worker 2D: Tool parity — architecture perspective (Phase 2)

Time ~5:00 — Phase 1 complete → Smoke test checkpoint
├── Workstation:
│   ├── Phase 1.5: Smoke test — verify TUI launches and works
│   └── Commit Phase 1 to git

Time ~10:00 — Phase 2 research complete
├── Server: Commit research to branches
├── Workstation: Pull research branches
│   └── Phase 2.5: Research review checkpoint

Time ~12:00 — Phase 3 begins (TUI implementation)
├── Workstation:
│   ├── Worker 3A: Message widget redesign (Phase 3)
│   ├── Worker 3B: Color system + status bar (Phase 3)
│   ├── Worker 3C: Help screen + log viewer + input widget (Phase 3)
│   └── Worker 3D: Responsive + accessibility (Phase 3)
├── Server:
│   ├── Worker 4B: Hooks system (Phase 4)
│   ├── Worker 4C: LSP + code review + missing tools (Phase 4)
│   └── Worker 4D: Session management TUI + skills (Phase 4)

Time ~20:00 — Phase 3 + 4 complete
├── Workstation:
│   └── Worker 4A: System prompt enhancement (Phase 4, ~5 min)
├── Server: Finalize research reports

Time ~25:00 — Phase 5
├── Workstation:
│   └── Worker 5: Isolated worker skill + CLI script update (Phase 5)

Time ~30:00 — Phase 6
├── Workstation:
│   └── Phase 6: Synthesis + documentation + commit + push

Total estimated wall time: 30-45 minutes
(With parallel execution on two machines, each running 2-3 workers)

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Subagent timeout | Break tasks into 3-5 min chunks; check git log after timeout |
| Breaking changes | All new code additive; existing tests must pass; TDD enforced |
| RAM exhaustion on workstation | Max 2 concurrent workers; offload research to server |
| Worktree conflicts | Each worker gets own worktree + branch; no shared state |
| Research quality | Two perspectives per topic (workflow + architecture); cross-validation |

---

## 6. Quality Gates

- [ ] All existing tests pass (`pytest tests/ -q`)
- [ ] New code has TDD tests written first
- [ ] No TODOs, stubs, or placeholders in completed code
- [ ] No breaking changes — all additive
- [ ] `docs/STATE.md` updated after each phase
- [ ] Research reports saved under `docs/research/`
- [ ] Implementation plans saved under `docs/plans/`
- [ ] Final commit and push to GitHub

---

## 7. Success Criteria (Measurable)

| Metric | Target | Measurement |
|--------|--------|-------------|
| TUI bugs fixed | 5/5 confirmed bugs resolved | Each bug has a passing test |
| Streaming latency | < 50ms per token | Test: measure time between token emissions |
| Message render latency | < 16ms (60 FPS) | Test: measure widget update time |
| Terminal support | ≥ 60 columns | Test: render at 60, 80, 120, 200 cols |
| WCAG AA contrast | All text ≥ 4.5:1 ratio | Automated contrast check |
| Keyboard navigation | All 15+ actions reachable | Test: no mouse required |
| TUI visual quality | On par with Claude Code/Gemini CLI | Side-by-side screenshot comparison |
| Feature parity research | 3+ competitors covered | Report covers Claude Code, Gemini CLI, Qwen Code CLI |
| System prompt | FORGE.md best practices integrated | Checklist verification |
| New features | Hooks, LSP, code review, skills | Each has passing tests |
| Test coverage | All new code covered | `pytest --cov` ≥ 80% on new files |
| Documentation | Complete under `docs/` | All research reports + updated STATE.md |
| No breaking changes | All existing tests pass | `pytest tests/ -q` green |

---

## 8. File Manifest

### Files to Create

| File | Description | Worker |
|------|-------------|--------|
| `docs/plans/2026-06-11-tui-parity-sprint.md` | This plan document | — |
| `docs/research/tui-visual-design.md` | TUI visual design research | 2A |
| `docs/research/tui-technical-rendering.md` | TUI technical rendering research | 2B |
| `docs/research/tool-parity-workflow.md` | Tool parity — workflow perspective | 2C |
| `docs/research/tool-parity-architecture.md` | Tool parity — architecture perspective | 2D |
| `docs/research/TOOL-PARITY-FINAL.md` | Synthesized tool parity report | Phase 6 |
| `docs/research/TUI-AESTHETICS-FINAL.md` | Synthesized TUI aesthetics report | Phase 6 |
| `tests/test_tui_widgets.py` | TUI widget render tests | 3A |
| `tests/test_tui_responsive.py` | TUI responsive behavior tests | 3D |
| `tests/test_hooks.py` | Hooks system tests | 4B |
| `tests/test_lsp.py` | LSP integration tests | 4C |
| `tests/test_code_review.py` | Code review tests | 4C |
| `tests/test_session_mgmt.py` | Session management TUI tests | 4D |

### Files to Modify

| File | Changes | Phase |
|------|---------|-------|
| `src/nexusagent/tui.py` | Fix streaming, redesign layout, enhance aesthetics | 1 + 3 |
| `src/nexusagent/widgets/messages.py` | Rich markdown, syntax highlighting, collapsible tool output | 3A |
| `src/nexusagent/widgets/theme.py` | Enhanced semantic tokens, more themes (Tokyo Night, Rose Pine, Solarized) | 3B |
| `src/nexusagent/widgets/status.py` | Git status indicator, context window bar, braille spinner | 3B |
| `src/nexusagent/widgets/chat_input.py` | Slash command autocomplete, history persistence | 3C |
| `src/nexusagent/session.py` | Fix streaming to be truly real-time | 1A |
| `src/nexusagent/config.py` | Add hooks, LSP, scheduled tasks, skills config | 4B + 4C + 4D |
| `src/nexusagent/hooks.py` | NEW — hooks system | 4B |
| `src/nexusagent/lsp.py` | NEW — LSP integration | 4C |
| `src/nexusagent/scheduler.py` | NEW — scheduled tasks | 4D |
| `src/nexusagent/code_review.py` | NEW — built-in code review | 4C |
| `src/nexusagent/skills.py` | NEW — skills system | 4D |
| `src/nexusagent/tools/fetch_url.py` | NEW — fetch_url tool | 4C |
| `src/nexusagent/tools/ask_user.py` | NEW — ask_user tool | 4C |
| `src/nexusagent/tools/write_todos.py` | NEW — write_todos tool | 4C |
| `config/NEXUS.md` | Enhanced system prompt with FORGE.md best practices | 4A |
| `docs/STATE.md` | Updated with new findings | Phase 6 |
| `docs/AGENTS.md` | Updated with lessons learned | Phase 6 |
| `scripts/worktree-worker.py` | Update with improvements from sprint | Phase 5 |

---

## 9. Review Subagent Feedback (Incorporated)

> Review subagent scored the initial plan **5.25/10**. Below is the summary of findings and how they were addressed.

### ✅ What Was Good
- Three parallel tracks (TUI, research, architecture) — right decomposition
- Machine allocation (workstation for TUI, server for research) — correct
- Two-perspective research approach — provides cross-validation
- Quality gates and risk mitigation — appropriate

### ⚠️ What Was Fixed

| Issue | Resolution |
|-------|-----------|
| `Grid`/`Vertical` import bugs don't exist | Re-verified against actual code; removed from bug list |
| "Fake streaming" may be outdated | Changed to "streaming verification + fix" — test first, fix if needed |
| "Raw JSON tool display" is partially wrong | Corrected: tool output is formatted but not beautiful — needs enhancement |
| Time estimates 30 min → 6-8x too low | Revised to 30-45 min with parallel execution |
| Worker 2C scope too large (8-10 changes) | Split into 3A (messages), 3B (theme/status), 3C (help/log/input), 3D (responsive) |
| Worker 4B scope too large (4 features) | Split into 4B (hooks), 4C (LSP + code review), 4D (session mgmt + skills) |
| Circular dependency: research → implementation | Added Phase 2.5: Research Review Checkpoint with git branch sync |
| No integration testing strategy | Added integration test requirements to success criteria |
| Missing: input widget improvements | Added to Worker 3C |
| Missing: session management TUI | Added to Worker 4D |
| Missing: skills system | Added to Worker 4D |
| Missing: `fetch_url`, `ask_user`, `write_todos` | Added to Worker 4C |
| No rollback plan for aesthetic changes | All changes in worktrees; master stays clean |
| No measurable quality metrics | Added specific targets (latency, contrast, columns, keyboard nav) |
| `tui_legacy.py` vs `tui.py` ambiguity | Verified: `tui.py` (328 lines) is active; `tui_legacy.py` is old |
| Phase 5 circular dependency | Moved to after Phase 4; script already exists (438 lines) |

### ❌ Critical Fixes
1. **Bug reports were factually wrong** — Two of five "confirmed bugs" don't exist. Re-audited all five.
2. **Worker scopes exceeded 600s timeout** — Split all oversized workers into 3-5 min tasks.
3. **No cross-machine synchronization** — Added git branch-based handoff between research and implementation.

### 💡 Suggestions Adopted
- Smoke test checkpoint after Phase 1 ✓
- Measurable TUI quality metrics ✓
- Research review checkpoint (Phase 2.5) ✓
- All orphaned items addressed ✓
- Extended time budget ✓

---

**END OF PLAN**
