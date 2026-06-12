# TUI Feature Parity Sprint — Master Plan

> Created: 2026-07-18
> Status: PLAN — pending execution approval
> Scope: TUI bug fixes, monolith refactor, competitive feature parity audit, TUI aesthetics research

---

## Context

NexusAgent's TUI (`tui.py`, 1433 lines) is the last monolithic file. It has known runtime bugs (fake streaming, broken word wrap, raw JSON tool output, greeting may not render). The codebase has been substantially refactored (utils/theme extracted), but the TUI remains untouched. We need:

1. **Fix what's broken** — make the TUI actually work as documented
2. **Refactor the monolith** — extract widgets, formatters, commands into focused modules
3. **Research the competition** — Claude Code, Gemini CLI, Qwen Code feature parity
4. **Research TUI aesthetics** — beautiful terminal rendering patterns from exemplar apps

---

## Sprint Architecture

```
WORKSTATION (i3, 3.7GB RAM)                    SERVER (rapidwebs-01, 5.7GB+ free)
├── Main agent (orchestrator)                   ├── Research Worker A: Feature parity
├── TUI Audit Worker (deep dive)                │   (Claude Code, Gemini CLI, Qwen)
├── TUI Refactor Workers (parallel)             ├── Research Worker B: TUI aesthetics
│   ├── Worker: Streaming fix                   │   (lazygit, helix, k9s, yazi, etc.)
│   ├── Worker: Word-wrap fix                   └── Research Worker C: Exemplar deep-dive
│   ├── Worker: Tool output formatting              (specific tool source code analysis)
│   └── Worker: Slash command extraction
├── Codebase Semantic Indexer (done ✅)
└── Plan Audit Workers (forward + reverse)
```

---

## Phase 0: Pre-Sprint (DONE ✅)

| Task | Status |
|------|--------|
| Commit & push all changes | ✅ Clean, pushed |
| Sequential thinking MCP | ✅ Configured |
| Load all relevant skills | ✅ subagent-driven-development, isolated-worktree-worker, tui-design |
| Semantic codebase index | ✅ `docs/SEMANTIC_INDEX.md` (917 lines) |

---

## Phase 1: TUI Deep-Dive Audit (Main Agent)

**Goal:** Identify every bug, code smell, and structural issue in the TUI codebase.

**Method:** Read the semantic index + key source files. Cross-reference against:
- User-reported bugs (fake streaming, word wrap, raw JSON, greeting)
- tui-design skill checklist (alt screen, terminal restore, resize, suspend, NO_COLOR, semantic colors)
- Code-level issues (dead code, duplication, tight coupling)

**Output:** `docs/TUI_AUDIT.md` — structured bug list with severity + file:line

**Key files to audit:**
- `src/nexusagent/interfaces/tui.py` (primary target)
- `src/nexusagent/widgets/messages.py`
- `src/nexusagent/widgets/chat_input.py`
- `src/nexusagent/widgets/status.py`
- `src/nexusagent/server/server.py` (WebSocket handler)

---

## Phase 2: Plan Audit (Parallel Subagents)

### Forward Audit Worker
**Goal:** Verify every claim in the TUI audit against actual code.
- Read each file mentioned in the audit
- Confirm each bug exists at the stated location
- Check for false positives

### Reverse Audit Worker
**Goal:** Find everything the audit MISSED.
- Read files the audit didn't cover
- Check for: dead code, unused imports, broken references, missing error handling
- Cross-reference imports → actual usage

**Output:** Both workers return findings → synthesize into refined `docs/TUI_AUDIT.md`

---

## Phase 3: TUI Monolith Refactor (Parallel Workers)

**Goal:** Break `tui.py` (1433L) into focused modules. NO behavior changes.

**Pre-condition:** Phase 2 audit complete and approved.

### Worker A: Extract Streaming & Event Handling
**Target:** `src/nexusagent/tui/streaming.py`
- Extract `_ws_loop()`, `_handle_event()`, `_write_response()`, `_write_response_chunk()`, `_finalize_response()`
- Extract WebSocket message type constants
- Extract queue management (`_process_next_in_queue`, `_update_queue_status`)
- **Fix:** Real token-by-token streaming (not fake accumulation + dump)
- **Fix:** Greeting rendering on startup

### Worker B: Extract Tool Output Formatters
**Target:** `src/nexusagent/tui/formatters.py`
- Extract `_format_tool_output()`, `_format_shell_output()`, `_format_read_file_output()`, `_format_write_file_output()`, `_format_git_output()`, `_format_search_output()`, `_format_subagent_output()`
- Extract `_write_tool_result()`, `_format_tool_result_for_display()`
- Extract `_truncate_output()`, `_truncate()`, `_format_arg_value()`, `_escape()`
- **Fix:** Tool output should be beautifully formatted, not raw JSON

### Worker C: Extract Slash Commands
**Target:** `src/nexusagent/tui/commands.py`
- Extract `_handle_slash_command()` and all command handlers
- Extract `_show_help()`, `_apply_theme()`
- Extract `_enhanced_markdown()`, `_simple_markdown()`
- Build a clean command registry (command name → handler function)

### Worker D: Extract Modal Screens & Utilities
**Target:** `src/nexusagent/tui/modals.py`
- Extract `ApprovalModal`, `ErrorModal`
- Extract `SpinnerLabel`, `Breakpoint`, `classify_breakpoint()`
- Extract `is_no_color()`, `debounce_resize()`, `_sigwinch_handler()`, `_get_terminal_size()`
- Extract `_is_ascii_terminal()`

### Post-Worker: Reassemble NexusApp
**Target:** `src/nexusagent/interfaces/tui.py` (reduced to ~300-400 lines)
- NexusApp becomes a thin orchestrator: compose layout, delegate to modules
- All imports from extracted modules
- CSS moves to a separate `.py` file or TCSS

**Test gate:** 453+ tests pass, zero regressions

---

## Phase 4: TUI Bug Fixes (Parallel with Phase 3 where possible)

**Goal:** Fix the user-reported runtime bugs.

| Bug | Root Cause (Hypothesis) | Fix Approach |
|-----|----------------------|--------------|
| Fake streaming | Tokens accumulated in `_write_response_chunk`, dumped as single event | Wire `_write_response_chunk` to emit per-token via `self.app.call_after_refresh` |
| No word wrapping | RichLog `wrap=True` doesn't work with Container layout | Use Static widgets with `text-wrap: wrap` CSS (per tui-design skill) |
| Raw JSON tool output | `_format_tool_output` falls through to `str(output)` | Implement per-tool formatters with syntax highlighting |
| Greeting not rendering | `_show_greeting` may race with WebSocket connect | Add `on_mount` delay or use `call_after_refresh` |
| Tool args show raw JSON | `_format_arg_value` returns `str(value)` | Pretty-print with `json.dumps(indent=2)` for dicts |

---

## Phase 5: Competitive Feature Parity Research (Server Workers)

**Goal:** Map Claude Code / Gemini CLI / Qwen Code features → NexusAgent gaps.

### Worker A: Feature Parity Audit
**Target:** `docs/research/FEATURE_PARITY_AUDIT.md`
- Research each tool's: tool system, permissions, hooks, MCP, memory, sessions, TUI
- Categorize: 🟢 Nice to have, 🟡 Mandatory, 🔴 CRITICAL
- Focus on: tool registry, policy enforcement, session management, memory/context

### Worker B: TUI Aesthetics Research
**Target:** `docs/research/TUI_AESTHETICS_RESEARCH.md`
- Research: lazygit, helix, k9s, yazi, btop, delta, atuin, gum, presenterm
- Extract: rendering approach, color systems, layout patterns, animation techniques
- Focus on: concrete implementable patterns for Textual (Python)

### Worker C: Exemplar Deep-Dive
**Target:** `docs/research/EXEMPLAR_DEEP_DIVE.md`
- Deep-source analysis of 2-3 exemplar tools' actual TUI code
- Extract specific design patterns: border styles, color palettes, responsive behavior
- Map patterns → Textual implementation recipes

**Research method:** web_search for overview → web_extract for docs → GitHub source for code patterns

---

## Phase 6: Synthesis & Report

**Goal:** Combine all research into actionable recommendations.

**Output:** `docs/TUI_PARITY_REPORT.md`
- Section 1: Current State Assessment (from semantic index + audit)
- Section 2: Bug Fix Summary (from Phase 4)
- Section 3: Refactor Summary (from Phase 3)
- Section 4: Feature Parity Gap Analysis (from Phase 5 Worker A)
- Section 5: TUI Aesthetics Recommendations (from Phase 5 Workers B+C)
- Section 6: Prioritized Implementation Roadmap
  - P0: Critical bugs + must-have features
  - P1: Important fixes + competitive parity
  - P2: Nice-to-have + aesthetic polish

---

## Phase 7: Isolated Worktree Worker Script

**Goal:** Create/update `scripts/worktree-worker.py` as a companion CLI tool.

**Features:**
- `create --name NAME --task TASK` — Create worktree + dispatch task
- `list` — Show active worktrees with status
- `collect --name NAME` — Pull results from worktree
- `destroy --name NAME` — Remove worktree + branch
- `remote --name NAME --server SERVER --task TASK` — Dispatch to remote

**Also:** Create a skill entry in `docs/WORKTREE_WORKER.md` documenting the workflow.

---

## Execution Order

```
Phase 0: Pre-sprint ✅ DONE
    │
    ▼
Phase 1: TUI Audit (main agent) ──────────────────┐
    │                                                │
    ▼                                                │
Phase 2: Forward + Reverse Audit (parallel)          │
    │                                                │
    ▼                                                │
Phase 3: TUI Refactor (4 parallel workers)           ├── Phase 5: Research (3 server workers)
    │                                                │   (runs in PARALLEL with Phases 3-4)
    ▼                                                │
Phase 4: Bug Fixes (parallel with Phase 3)           │
    │                                                │
    ▼                                                │
Phase 6: Synthesis ◄─────────────────────────────────┘
    │
    ▼
Phase 7: Worktree worker script
```

**Key:** Phases 3-4 (workstation) and Phase 5 (server) run CONCURRENTLY.

---

## Success Criteria

- [ ] `tui.py` reduced from 1433 lines to <400 lines
- [ ] All known bugs fixed (streaming, word wrap, JSON output, greeting)
- [ ] 453+ tests pass, zero regressions
- [ ] `docs/TUI_PARITY_REPORT.md` with complete competitive analysis
- [ ] `docs/research/FEATURE_PARITY_AUDIT.md` — feature comparison
- [ ] `docs/research/TUI_AESTHETICS_RESEARCH.md` — design patterns
- [ ] `scripts/worktree-worker.py` — working CLI tool
- [ ] All changes committed and pushed to GitHub
- [ ] NO breaking changes — all additive, surgical, methodical

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Refactor breaks TUI at runtime | Commit-per-phase, test after each worker |
| Research workers timeout | Tight scope, "write early" instructions |
| Too many concurrent workers | Max 3 per machine, queue if needed |
| OpenRouter truncation | Keep contexts small, use file paths not code blocks |
| Breaking changes slip through | Forward + reverse audit, test gate after each phase |
