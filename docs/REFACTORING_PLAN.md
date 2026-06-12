# NexusAgent Refactoring Plan

**Date:** 2026-07-18
**Baseline:** 453 passing, 20 failed (all pre-existing), 0 errors

---

## Research Summary

### How similar projects organize code

**Textualize/textual (the framework we use):**
- `src/textual/` → framework internals
- `app.py` (single file, ~2000 lines for the entire App class)
- `screen.py`, `widget.py` → each major concept = one file
- `widgets/` → one file per widget type
- `css/`, `drivers/`, `renderables/` → technical infrastructure as subpackages
- Pattern: **flat within categories, deep within domains**

**LangGraph/LangChain (our agent framework):**
- `agents/<name>/graph.py` — one graph per agent
- `utils/` — shared utilities (models.py, helpers.py)
- Pattern: **one directory per agent, shared utils at top level**

**Python best practices (Real Python, EngineersOfAI):**
- Group by domain, not by file type
- One-way dependencies (outer → inner, never reverse)
- `__init__.py` curates public API — no logic, no expensive imports
- Split triggers: >500 lines, >3 responsibilities, section-separator comments
- Tests mirror source structure

**Refactoring methodology (ClaudeGuide, Martin Fowler):**
- Extract methods first, then extract classes
- One concern per slice, <400 lines per operation
- Test gate after each slice
- Strangler fig pattern for large extractions

---

## Refactoring Candidates (Prioritized)

### Tier 1 — CRITICAL (structural problems causing bugs)

#### 1. TUI Monolith: `interfaces/tui.py` (1,433 lines, 5 classes, 58 functions)
**Problem:** NexusApp has 41 methods, `_handle_slash_command` is 229 lines, output formatting is interleaved with event handling. This is the source of: fake streaming, broken word wrapping, raw JSON tool calls.

**Textual best practice:** App class should be thin — screens handle navigation, widgets handle display, services handle business logic. "Attributes down, messages up."

**Proposed split:**
```
interfaces/tui/
├── __init__.py
├── app.py              (NexusApp — ~300 lines: lifecycle, routing, signals)
├── screens/
│   ├── __init__.py
│   ├── main_screen.py  (chat view + input — the primary UI)
│   └── settings_screen.py (theme, approval mode, config)
├── output/
│   ├── __init__.py
│   ├── formatter.py    (tool output formatting, markdown rendering)
│   ├── streaming.py    (streaming response handler — fixes fake streaming)
│   └── welcome.py      (greeting, help, theme display)
└── commands/
    ├── __init__.py
    └── slash_commands.py (_handle_slash_command split into handlers)
```

**Impact:** Directly fixes all reported TUI bugs
**Risk:** High (TUI is the most complex file) — use strangler fig, one screen at a time
**Estimated:** 3-4 phases

---

#### 2. Session God Object: `core/session.py` (677 lines, 2 classes, 15 functions)
**Problem:** `send()` is 140 lines, `_handle_message_token` is 65 lines. Session handles: message building, system prompt loading, memory context injection, approval flow, event streaming, compaction callbacks — too many concerns.

**Proposed split:**
```
core/
├── session/
│   ├── __init__.py
│   ├── manager.py      (SessionManager — unchanged, ~40 lines)
│   ├── session.py      (Session class — ~200 lines: lifecycle, send)
│   ├── prompt.py       (system prompt loading, context injection)
│   ├── memory_ctx.py   (memory recall → system prompt integration)
│   ├── approval.py     (approval flow, HITL)
│   └── compaction.py   (pre-compaction flush, callbacks)
```

**Impact:** Fixes streaming bugs (event handling isolated), enables proper prompt management
**Risk:** Medium — session is well-tested, changes are internal
**Estimated:** 2 phases

---

#### 3. Memory Index Monolith: `memory/memory_index.py` (717 lines, 2 classes, 14 functions)
**Problem:** Embedding providers, vector search, keyword search, result merging, chunking — all in one file. `_init_db`, `index_file`, `async_index_file` are each 73-93 lines.

**Proposed split:**
```
memory/
├── memory_index/
│   ├── __init__.py
│   ├── index.py        (HybridMemoryIndex class — public API, search entry)
│   ├── embedding.py    (EmbeddingProvider — Gemini, local, hash strategies)
│   ├── chunking.py     (_chunk_text, file splitting)
│   ├── vector_search.py (_search_vector, _search_vector_brute, _vec_to_blob)
│   ├── keyword_search.py (_search_keyword, FTS5 queries)
│   └── merge.py        (_merge_results, scored union merge)
```

**Impact:** Untangles the most technically complex file, enables testing search strategies independently
**Risk:** Medium — internal restructuring, same public interface
**Estimated:** 2 phases

---

### Tier 2 — HIGH (significant complexity, improvement opportunities)

#### 4. Tool Registration: `tools/register_all.py` (728 lines, 4 functions)
**Problem:** Every tool's registration, description, category mapping, and example is in one massive function. Adding a new tool means editing this monolith.

**Proposed approach:** Keep as a registry file but extract tool metadata into each tool's module (self-describing tools). `register_all.py` becomes a scanner, not a catalog.

**Risk:** Low — additive pattern, no existing behavior changes
**Estimated:** 1 phase

---

#### 5. Tool Registry + Policy: `tools/registry.py` (623 lines, 1 class, 21 functions)
**Problem:** Tool registration, policy enforcement, search (exact, fuzzy, use-case), auto-correction, manifest generation — all interleaved.

**Proposed split:**
```
tools/
├── registry/
│   ├── __init__.py
│   ├── registry.py     (ToolRegistry — register, get, list)
│   ├── policy.py       (policy enforcement, _is_tool_allowed, require_policy)
│   ├── search.py       (tool_search, _exact_search, _use_case_search, auto_correct)
│   └── manifest.py     (get_manifest, to_prompt_format, to_compact)
```

**Risk:** Medium — policy logic is security-critical, needs careful migration
**Estimated:** 2 phases

---

#### 6. Utils Grab Bag: `infrastructure/utils.py` (354 lines, 3 classes, 13 functions)
**Problem:** `CircuitBreaker`, `retry_with_backoff`, `retry_on_false`, decorators — unrelated utilities crammed together.

**Proposed split:**
```
infrastructure/
├── utils/
│   ├── __init__.py
│   ├── retry.py        (retry_with_backoff, retry_on_false)
│   ├── circuit.py      (CircuitBreaker, CircuitState, CircuitBreakerError)
│   └── decorators.py   (decorator utilities)
```

**Risk:** Low — straightforward extraction, re-export from old path temporarily
**Estimated:** 1 phase (quick)

---

### Tier 3 — MEDIUM (cleanliness improvements)

#### 7. Database Layer: `infrastructure/db.py` (416 lines, 8 classes)
**Problem:** Models + repositories + manager in one file. `SessionRepository` alone is ~150 lines.

**Proposed split:**
```
infrastructure/db/
├── __init__.py
├── manager.py          (DatabaseManager, engine setup)
├── models.py           (TaskModel, SessionModel, MessageModel, ResultModel, Base)
├── repositories.py     (TaskRepository, SessionRepository)
└── types.py            (TaskStatus enum)
```

**Risk:** Low — clean separation, each repository tested independently
**Estimated:** 1 phase

---

#### 8. Filesystem Tool: `tools/fs.py` (343 lines, 14 functions)
**Problem:** `edit_file` is 104 lines, `list_directory` is 56 lines — these are large functions with complex logic.

**Proposed approach:** Extract `edit_file` helper into a dedicated `editor.py` module, keep `fs.py` as the tool interface. Also extract path validation into `path_utils.py`.

**Risk:** Low — single-file extraction
**Estimated:** 1 phase

---

#### 9. Code Review Tool: `tools/code_review.py` (367 lines, 10 functions)
**Problem:** 5 independent check functions (`_check_security`, `_check_bugs`, `_check_style`, `_check_performance`, `_check_python_ast`) each 30-60 lines, with a `review_code` orchestrator.

**Proposed split:**
```
tools/code_review/
├── __init__.py
├── review_code.py      (CodeReviewTool — tool interface + review_code orchestrator)
├── checks/
│   ├── __init__.py
│   ├── security.py     (_check_security)
│   ├── bugs.py         (_check_bugs)
│   ├── style.py        (_check_style)
│   ├── performance.py  (_check_performance)
│   └── ast_check.py    (_check_python_ast)
└── models.py           (Issue, IssueSeverity, IssueCategory)
```

**Risk:** Low — each check is already self-contained
**Estimated:** 1 phase

---

#### 10. Worker Pool: `core/worker.py` (303 lines, 2 classes, 3 functions)
**Problem:** `handle_task()` is 80 lines with deeply nested try/except/finally. Worker and WorkerPool classes interleaved.

**Proposed split:**
```
core/worker/
├── __init__.py
├── worker.py           (NexusWorker — task execution lifecycle)
├── pool.py             (WorkerPool — pool management, spawn, cancel)
└── handler.py          (handle_task — extracted with proper error handling)
```

**Risk:** Medium — worker is runtime-critical, errors affect task execution
**Estimated:** 1 phase

---

#### 11. HTTP Server: `server/server.py` (354 lines, 1 class, 11 functions)
**Problem:** `session_websocket` is 103 lines — the entire WebSocket lifecycle in one function. Routes, middleware, and WebSocket handlers mixed.

**Proposed split:**
```
server/
├── server.py           (app factory, middleware, route registration — ~100 lines)
├── websocket.py        (session_websocket — extracted with state machine)
└── routes.py           (HTTP REST endpoints)
```

**Risk:** Medium — WebSocket is the primary interface, bugs = connection drops
**Estimated:** 1 phase

---

#### 12. Theme System: `widgets/theme.py` (445 lines, 1 class, 4 functions)
**Problem:** `register_themes` is 84 lines. Theme definition and registration logic mixed with color conversion utilities.

**Proposed split:**
```
widgets/theme/
├── __init__.py
├── theme.py            (Theme class — definition + get/set)
├── registry.py         (register_themes, theme switching)
└── colors.py           (color conversion utilities)
```

**Risk:** Low — isolated subsystem
**Estimated:** 1 phase (quick)

---

#### 13. Message Rendering: `widgets/messages.py` (472 lines, 6 classes, 25 functions)
**Problem:** `_parse_markdown` is 55 lines. Message display classes mixed with markdown rendering logic.

**Proposed approach:** Extract markdown rendering into `widgets/rendering.py` or `widgets/markdown.py`. Keep message widgets focused on display.

**Risk:** Low — display logic only
**Estimated:** 1 phase

---

#### 14. Prompt Loader: `infrastructure/prompt_loader.py` (240 lines, 2 classes, 5 functions)
**Problem:** `load_prompt_content` (88 lines) and `load_nexus_prompt` (67 lines) have complex path resolution and error handling.

**Proposed approach:** Extract `@` chaining logic into a dedicated `infrastructure/template_includes.py`. Keep `prompt_loader.py` as the main entry point.

**Risk:** Low — isolated subsystem
**Estimated:** 1 phase

---

## Priority Order (completion time, shortest first)

| # | Module | Lines | Risk | Est. Phase | Rationale |
|---|--------|-------|------|------------|-----------|
| 6  | utils.py | 354 | Low | 1 | Quick win, validates approach |
| 12 | theme.py | 445 | Low | 1 | Quick win, isolated |
| 7  | db.py | 416 | Low | 1 | Clean separation, high testability |
| 4  | register_all.py | 728 | Low | 1 | Self-describing tools pattern |
| 14 | prompt_loader.py | 240 | Low | 1 | Isolated, simple extraction |
| 13 | messages.py | 472 | Low | 1 | Display-only refactor |
| 9  | code_review.py | 367 | Low | 1 | Each check self-contained |
| 8  | fs.py | 343 | Low | 1 | Single-function extraction |
| 10 | worker.py | 303 | Med | 1 | Runtime-critical but small scope |
| 11 | server.py | 354 | Med | 1 | WebSocket needs careful handling |
| 5  | registry.py | 623 | Med | 2 | Security-critical policy logic |
| 3  | memory_index.py | 717 | Med | 2 | Complex but well-tested |
| 2  | session.py | 677 | Med | 2 | Core logic, needs test coverage |
| 1  | tui.py | 1,433 | High | 3-4 | Largest impact, highest risk |

**Total: ~22 phases across ~6 weeks of focused work**

---

## Execution Methodology (per phase)

For each refactoring phase:

### A. Implementation Plan (written before touching code)
1. Identify the exact code blocks to extract
2. Define the new module/file structure
3. Map all import paths that need updating
4. Identify tests that need updates

### B. Skills & Tools
- `ast-tools`: Read structure before modifying
- `ast-edit`: Surgical edits where possible
- `patch`: Targeted find-and-replace for import updates
- `git mv`: File renames that preserve history

### C. Forward Audit (main agent)
1. Read the target file completely
2. Map all internal dependencies (imports, function calls)
3. Identify the extraction boundaries
4. Verify test coverage for the target

### D. Reverse Audit (subagent, parallel)
1. Dispatch subagent to independently analyze the same file
2. Compare findings with forward audit
3. Identify blind spots (dead code, hidden coupling, missing tests)

### E. Plan Reconciliation
1. Merge forward + reverse audit findings
2. Update the implementation plan
3. Present changes for sign-off

### F. Execution
1. Create new module directory + `__init__.py`
2. `git mv` or copy extracted code to new file
3. Update all import paths (internal + tests)
4. Run full test suite after EACH file move

### G. Regression Testing
1. `PYTHONPATH=src python3 -m pytest tests/ -q`
2. Compare pass/fail counts with baseline
3. Any regression → fix immediately, do not proceed

### H. Documentation Update
1. Update `CODEBASE_MAP.md` with new structure
2. Update any module docstrings
3. Update `mkdocs.yml` if needed

### I. Commit & Proceed
1. Commit with descriptive message: `refactor: extract X from Y into Z`
2. Push to GitHub
3. Move to next phase

---

## Constraints

- **Zero breaking changes** — all public APIs must remain accessible from their original import paths (re-export from old location if needed)
- **No behavior changes** — refactoring only, no feature changes
- **Test gate mandatory** — every extraction must pass the full test suite
- **One phase at a time** — complete and verify before starting next
- **Git history preserved** — use `git mv` for renames
