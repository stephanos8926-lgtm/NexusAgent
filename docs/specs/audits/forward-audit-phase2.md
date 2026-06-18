# Forward Audit: Phase 2 — Workspace-Scoped Memory (SPEC-002)

> **Date:** 2026-07-21
> **Auditor:** OWL (Lucien) subagent
> **Scope:** Validate every claim in SPEC-002 and the Phase 2 section of MEMORY_IMPL_PLAN.md against the actual NexusAgent codebase
>
> **Files examined:**
> - `docs/specs/SPEC-002-workspace-scoped-memory.md` (the spec under audit)
> - `docs/MEMORY_IMPL_PLAN.md` (Phase 2 section, lines 49–83)
> - `src/nexusagent/infrastructure/config.py` (ConfigSchema)
> - `src/nexusagent/core/session/session.py` (Session.__init__)
> - `src/nexusagent/core/session/manager.py` (SessionManager.get_or_create)
> - `src/nexusagent/tools/register_all.py` (_get_memory_workspace + memory tools)
> - `src/nexusagent/memory/hybrid_memory.py` (HybridMemoryManager)
> - `src/nexusagent/memory/memory_files.py` (FileMemory)
> - `src/nexusagent/interfaces/cli.py` (CLI)
> - `src/nexusagent/server/websocket.py` (WebSocket handler)
> - `config/nexusagent.yaml` (current config)
> - `src/nexusagent/core/session/__init__.py` (session subpackage exports)
> - `src/nexusagent/core/__init__.py` (core exports)
> - `src/nexusagent/memory/memory.py` (compat shim)
> - `docs/MEMORY_SYSTEM_ANALYSIS.md` (reference)

---

## 1. Current State Verification

### 1.1 ConfigSchema — `memory_workspace` field

**SPEC claim:** Add `memory_workspace` to `infrastructure/config.py` ConfigSchema (line 62)

**Current code:** `ConfigSchema` (line 113 of `config.py`) has these top-level fields:
- `server`, `client`, `auth`, `agent`, `prompt`, `logging`, `hooks`
- `mcp_servers` (list of dicts)
- `log_level` (back-compat)

No `memory_workspace` field exists anywhere in ConfigSchema or any sub-model.

**Verdict:** ✅ VERIFIED — Spec correctly states this field needs to be added. No conflict with existing fields.

---

### 1.2 Session.__init__ — how `memory_dir` is set

**SPEC claim:** "Session-scoped path is underutilized — `~/.nexusagent/sessions/{session_id}/memory/` exists but tools don't use it" (line 15)

**Current code** (session.py lines 37–66):
```python
def __init__(self, session_id, working_dir, agent, db_repo, memory_dir=None):
    if memory_dir is None:
        memory_dir = os.path.expanduser(f"~/.nexusagent/sessions/{session_id}/memory")
    self.memory_dir = Path(memory_dir)
    self.memory_dir.mkdir(parents=True, exist_ok=True)
    self.hybrid_memory = HybridMemoryManager(str(self.memory_dir))
    self.hybrid_memory.initialize()
```

Session correctly defaults to `~/.nexusagent/sessions/{session_id}/memory/` and creates the directory. The `memory_dir` parameter allows external override. This is accurate.

**Verdict:** ✅ VERIFIED — Current state matches spec description exactly.

---

### 1.3 SessionManager.get_or_create — does it pass `memory_dir`?

**PLAN claim:** "Update session initialization (1 hour) — Point session hybrid_memory to workspace dir" (Task 2.5)

**Current code** (manager.py lines 32–62):
```python
async def get_or_create(self, session_id, working_dir=".", agent=None, db_repo=None):
    ...
    session = Session(
        session_id=session_id,
        working_dir=working_dir,
        agent=agent,
        db_repo=db_repo,
    )
```

`get_or_create` does NOT accept or forward a `memory_dir` parameter. It passes only `session_id`, `working_dir`, `agent`, `db_repo`. Session defaults to the global sessions path.

**Verdict:** ⚠️ CORRECTION — The spec's Task 2.5 must also add a `memory_dir` parameter to `SessionManager.get_or_create()` to allow callers to inject a workspace-scoped path. Without this change, there is no way for the WebSocket handler (or any caller) to pass a workspace-specific memory directory. The plan mentions "point session hybrid_memory to workspace dir" but doesn't explicitly state that `get_or_create` needs a new parameter.

---

### 1.4 `_get_memory_workspace()` — current implementation

**SPEC claim:** "Modify `_get_memory_workspace()` in `tools/register_all.py` to accept session context" (line 61)

**Current code** (register_all.py lines 322–331):
```python
_DEFAULT_MEMORY_WORKSPACE = "~/.nexusagent/memory/"

def _get_memory_workspace() -> str:
    import os
    path = os.path.expanduser(_DEFAULT_MEMORY_WORKSPACE)
    os.makedirs(path, exist_ok=True)
    return path
```

The function is a simple global default with no session context, no config awareness, and no fallback chain. It returns `~/.nexusagent/memory/` every time.

**Verdict:** ✅ VERIFIED — Spec accurately describes the current state and the needed change.

---

### 1.5 HybridMemoryManager — how does it use workspace path?

**SPEC claim:** "Works with existing `HybridMemoryIndex` (just different root path)" (line 45)

**Current code** (hybrid_memory.py lines 10–29):
```python
class HybridMemoryManager:
    def __init__(self, workspace_dir: str):
        from nexusagent.memory.memory_files import FileMemory
        from nexusagent.memory.memory_index import HybridMemoryIndex
        self.workspace_dir = workspace_dir
        self.file_memory = FileMemory(workspace_dir)
        self.index = HybridMemoryIndex(workspace_dir)
```

HybridMemoryManager takes a `workspace_dir` string and passes it to both `FileMemory` and `HybridMemoryIndex`. FileMemory creates `memory/`, `bank/`, `bank/entities/` subdirs and expects `MEMORY.md` at the root.

**Verdict:** ✅ VERIFIED — The claim is correct. HybridMemoryManager is already workspace-path-agnostic; it just needs a different root path passed in.

---

### 1.6 CLI — how is session created?

**SPEC check:** Does the CLI create interactive sessions?

**Current code** (cli.py): The CLI has these commands:
- `submit` — submits a task to NATS (no interactive session)
- `run` — spawns an isolated worker (no interactive session)
- `session` — CRUD operations on session DB records (no Session object creation)
- `hooks` — hook management only

**Verdict:** ✅ VERIFIED — The CLI does NOT create `Session` objects. It only manages DB session records. Session creation happens exclusively in the WebSocket handler.

---

### 1.7 WebSocket handler — how is session created?

**SPEC implication:** This is the primary session creation point that needs workspace awareness.

**Current code** (websocket.py lines 63–73):
```python
session_repo = get_session_repo()
agent = Agent(role="full", policy="permissive")
session = await session_manager.get_or_create(
    session_id,
    working_dir=".",
    agent=agent,
    db_repo=session_repo,
)
set_workspace_root(session.working_dir)
```

The WebSocket handler hardcodes `working_dir="."` and does not pass `memory_dir`.

**Verdict:** ⚠️ CORRECTION — Two issues:
1. `working_dir="."` is hardcoded. For workspace-scoped memory, this should derive the workspace from the request context (e.g., query param, header, or JWT claim).
2. No `memory_dir` is passed to `get_or_create`. The handler needs to compute the workspace path (e.g., `~/Workspaces/{project}/.nexusagent/`) and pass it as `memory_dir`.

---

### 1.8 Config file — any `memory_workspace` already set?

**Current code** (`config/nexusagent.yaml`): Contains `server`, `client`, `agent`, `prompt`, `logging` sections. No `memory_workspace` key at any level.

**Verdict:** ✅ VERIFIED — No `memory_workspace` exists in the current config.

---

## 2. Call Site Analysis

### 2.1 All `Session()` call sites

| File | Line | Calls Session()? | Notes |
|------|------|-----------------|-------|
| `core/session/manager.py` | 57 | ✅ Yes | Only production call site |
| `core/session/session.py` | 31 | No (definition) | Class definition |
| Tests | — | Likely | Not in scope for forward audit |

**Total production call sites for `Session()`: 1** (in `manager.py`)

### 2.2 All `get_or_create()` call sites

| File | Line | Passes `memory_dir`? | Notes |
|------|------|----------------------|-------|
| `server/websocket.py` | 68 | ❌ No | Primary interactive session |
| `core/session/manager.py` | 89 | ❌ No | Recursive retry |
| `interfaces/tui/` | — | N/A | TUI connects via WebSocket (indirect) |

**✅ VERIFIED** — Only ONE production call site (`websocket.py`) needs to change. The recursive self-call in `manager.py` will automatically propagate whatever the top-level caller passes.

### 2.3 TUI session creation path

The TUI (`interfaces/tui/app.py`) creates a `session_id` but does NOT create a `Session` object directly. It opens a WebSocket connection to `/sessions/{session_id}/ws`, which triggers `session_websocket()` in the server, which calls `session_manager.get_or_create()`.

**Verdict:** ✅ VERIFIED — No changes needed in TUI code for Phase 2. The TUI doesn't create Session objects.

---

## 3. SPEC Claim-by-Claim Audit

### FR-1: Project-Scoped Memory Workspace

| Claim | Verdict | Notes |
|-------|---------|-------|
| Memory tools default to current session's workspace directory | ⚠️ NEEDS WORK | Tools use `_get_memory_workspace()` → global path, not session workspace |
| Workspace path: `~/Workspaces/{project}/.nexusagent/` (gitignored) | ✅ FEASIBLE | No such path exists yet; needs creation |
| Falls back to session directory if no project workspace | ✅ FEASIBLE | Can implement in `_get_memory_workspace()` or Session init |
| Falls back to global `~/.nexusagent/memory/` if neither exists | ✅ FEASIBLE | Already the current behavior |

### FR-2: Configurable Memory Workspace

| Claim | Verdict | Notes |
|-------|---------|-------|
| `memory_workspace` config option in `nexusagent.yaml` | ✅ FEASIBLE | Add to ConfigSchema; no naming conflicts |
| Per-session override via `memory_dir` parameter | ⚠️ PARTIAL | `Session.__init__` already accepts `memory_dir`, but `SessionManager.get_or_create` does NOT forward it |
| Tool parameter `workspace` overrides for explicit control | ✅ FEASIBLE | `memory_index_search`, `memory_index_rebuild`, `memory_delete`, `memory_update`, `memory_list`, `memory_prune` already accept `workspace` param. `memory_search`, `memory_write`, `memory_get` do NOT yet — but this is Phase 1 scope |

### FR-3: Memory Workspace Initialization

| Claim | Verdict | Notes |
|-------|---------|-------|
| Auto-create workspace directory structure on first use | ✅ FEASIBLE | `FileMemory.initialize()` already creates `memory/`, `bank/`, `bank/entities/`, and `MEMORY.md` |
| Create `.gitignore` in `.nexusagent/` to exclude from version control | 🔍 MISSING | Not mentioned anywhere in spec or plan. The `.gitignore` creation needs to be added to initialization logic. `FileMemory.initialize()` does NOT currently create a `.gitignore`. |
| Separate `MEMORY.md` index per workspace | ✅ FEASIBLE | `FileMemory.initialize()` already creates per-workspace `MEMORY.md` |

### FR-4: Cross-Workspace Memory Search

| Claim | Verdict | Notes |
|-------|---------|-------|
| `memory_search` accepts optional `workspace` parameter | ❌ NOT YET | `memory_search` (line 345) does NOT have a `workspace` param. Only `memory_index_search` does. |
| Default: search current workspace only | ⚠️ NEEDS WORK | Currently searches global workspace only |
| `workspace="all"` searches all configured workspaces | ❌ NOT IMPLEMENTED | Not in current code |
| Results tagged with workspace source | ❌ NOT IMPLEMENTED | Not in current code |

**🔍 MISSING — The SPEC implicitly requires `memory_search` and `memory_write` to accept a `workspace` parameter, but this is not explicitly stated in the requirements or plan tasks.**

---

## 4. Plan Task-by-Task Audit (Phase 2)

### Task 2.1: Update `_get_memory_workspace()` in tools (2 hours)

**Plan says:** Accept session context, default to session's workspace, fallback chain: workspace → session → global

**Verdict:** ⚠️ CORRECTION — `_get_memory_workspace()` is a synchronous function with no access to session context. The memory tools are stateless and have no reference to the current session. Two possible approaches:

**Option A (preferred):** Make `_get_memory_workspace()` check `settings.agent.memory_workspace` config first, then fall back to global. Session-level override would be handled by the session's own `hybrid_memory` (used for context injection), not by the tools.

**Option B (more complex):** Add a thread-local or contextvar that `_get_memory_workspace()` reads, set by the session when processing a message. This adds complexity but allows per-session tool workspace resolution.

**The plan's claimed 2 hours is likely optimistic for Option B.** Option A is cleaner and aligns with how the agent already works: the session uses its own `hybrid_memory` for context injection, and tools use the config-based default workspace for explicit memory operations.

### Task 2.2: Add `memory_workspace` config option (1 hour)

**Plan says:** Add to ConfigSchema, tests

**Verdict:** ✅ FEASIBLE — Simple addition to `AgentConfig` or top-level `ConfigSchema`. Estimated 1 hour is reasonable. Should add:
- `memory_workspace: str | None = None` to `AgentConfig` (or top-level `ConfigSchema`)
- Env var support via `NEXUS_AGENT__MEMORY_WORKSPACE=...`
- Test that config loads correctly from YAML and env var

### Task 2.3: Add workspace initialization (2 hours)

**Plan says:** Auto-create directory structure, create `.gitignore`, separate MEMORY.md per workspace

**Verdict:** ⚠️ CORRECTION — Directory structure and MEMORY.md are already handled by `FileMemory.initialize()`. The missing piece is `.gitignore` creation. Two sub-items:

1. **`.gitignore` creation:** NOT currently implemented. Must be added to `FileMemory.initialize()` or to the workspace initialization logic. Content should be:
   ```
   *
   !.gitignore
   ```
   (ignore everything in `.nexusagent/` by default)

2. **Index file location:** SPEC says `.memory/index.sqlite` (hidden directory, line 64). Current implementation uses `HybridMemoryIndex` which stores index at `{workspace}/.memory/index.sqlite` — needs verification but likely already correct.

**Estimated effort: ~1 hour** (only `.gitignore` is new; directory structure exists).

### Task 2.4: Add cross-workspace search (2 hours)

**Plan says:** `workspace="all"` parameter, results tagged with workspace source

**Verdict:** ⚠️ CORRECTION — This is more complex than 2 hours because:
1. `memory_search` doesn't currently accept `workspace` param (needs adding)
2. `memory_write` doesn't currently accept `workspace` param (needs adding)
3. `workspace="all"` requires enumerating all known workspaces (from config, session registry, filesystem?)
4. Result tagging requires modifying `HybridMemoryManager.recall()` or post-processing results
5. Need at least 2 new tests for cross-workspace behavior

**Revised estimate: 3–4 hours**

### Task 2.5: Update session initialization (1 hour)

**Plan says:** Point session hybrid_memory to workspace dir, tests

**Verdict:** ⚠️ INCOMPLETE — The plan doesn't specify all the changes needed:

1. **`SessionManager.get_or_create`** needs a new `memory_dir: str | None = None` parameter
2. **`session_websocket`** needs to compute workspace path and pass it as `memory_dir`
3. The fallback chain logic needs to be decided:
   - If `config.agent.memory_workspace` is set, use that
   - Else if session has a workspace (from request), use `~/Workspaces/{project}/.nexusagent/`
   - Else fall back to `~/.nexusagent/sessions/{session_id}/memory/` (current default)

**Estimated effort: 2 hours** (parameter addition + websocket update + tests)

---

## 5. File Path Verification

| File in SPEC/Plan | Actual Path | Match? |
|-------------------|-------------|--------|
| `infrastructure/config.py` | `src/nexusagent/infrastructure/config.py` | ✅ |
| `tools/register_all.py` | `src/nexusagent/tools/register_all.py` | ✅ |
| `core/session` | `src/nexusagent/core/session/` (subpackage) | ✅ |

---

## 6. Import/Breaking Change Analysis

### Changes that WILL break things:

1. **Adding `memory_dir` param to `SessionManager.get_or_create()`** — Safe. New param with default `None` is a backward-compatible addition. Existing callers (websocket.py, recursive self-call) don't pass it.

2. **Adding `memory_workspace` to ConfigSchema** — Safe. New field with default `None` is backward-compatible. Env var `NEXUS_AGENT__MEMORY_WORKSPACE` will be ignored if not set.

3. **Modifying `_get_memory_workspace()` to check config** — Safe. Currently returns global path; checking config first is additive.

4. **Adding `workspace` param to `memory_search`, `memory_write`** — Safe. New optional param with default `None` is backward-compatible. These tools already create a new `HybridMemoryManager` each call.

### Changes that will NOT break things:

- `FileMemory.initialize()` adding `.gitignore` creation — Safe, purely additive
- `Session.__init__` — No changes needed; already accepts `memory_dir`

---

## 7. Findings Summary

### ✅ Verified (8 items)

1. `memory_workspace` field does not exist in ConfigSchema — needs adding
2. `Session.__init__` correctly defaults to `~/.nexusagent/sessions/{session_id}/memory/`
3. `Session.__init__` already accepts `memory_dir` override parameter
4. `_get_memory_workspace()` is a simple global default with no session awareness
5. HybridMemoryManager is workspace-path-agnostic (takes any root path)
6. CLI does NOT create Session objects — only WebSocket handler does
7. Config file has no `memory_workspace` key
8. File paths in spec match actual project structure

### ⚠️ Corrections needed (5 items)

1. **`SessionManager.get_or_create()` needs `memory_dir` param** — Plan Task 2.5 is incomplete without this. The plan says "point session hybrid_memory to workspace dir" but doesn't mention adding the parameter to the manager.

2. **`websocket.py` needs to pass workspace path** — Currently hardcodes `working_dir="."` and passes no `memory_dir`. This is the primary integration point.

3. **Cross-workspace search under-scoped** — Task 2.4 estimates 2 hours but requires changes to `memory_search`, `memory_write`, result formatting, and workspace enumeration. Realistic estimate: 3–4 hours.

4. **`_get_memory_workspace()` redesign approach unclear** — Plan says "accept session context" but tools are stateless. Recommended approach: check `config.agent.memory_workspace` first, fall back to global. Session-level override is already handled by `session.hybrid_memory`.

5. **Session initialization effort underestimated** — Task 2.5 estimates 1 hour but requires changes to two files (`manager.py`, `websocket.py`) plus fallback logic.

### ❌ Errors (0 items)

No claims are outright wrong. The spec correctly describes current state and desired state.

### 🔍 Missing items (3 items)

1. **`.gitignore` creation** — SPEC mentions it (FR-3, line 33) but `FileMemory.initialize()` does NOT currently create a `.gitignore`. This must be added to the initialization logic.

2. **Tool parameter consistency for `memory_search` and `memory_write`** — Phase 1 already added `workspace` param to `memory_delete`, `memory_update`, `memory_list`, `memory_prune`, `memory_index_search`, `memory_index_rebuild`. But `memory_search` and `memory_write` still lack it. The spec's FR-4 implies these should have it for cross-workspace support.

3. **Workspace discovery mechanism** — The spec mentions `workspace="all"` but doesn't specify how workspaces are enumerated. Need a registry of known workspaces (from config, filesystem scan of `~/Workspaces/*/.nexusagent/`, or a dedicated registry file). This is a design gap that needs resolution before implementation.

---

## 8. Recommended Revised Plan

| Task | Revised Scope | Revised Estimate |
|------|--------------|-----------------|
| 2.1 Update `_get_memory_workspace()` | Add config check + fallback chain (config → global). Drop "session context" approach in favor of config-based default. | 2 hours |
| 2.2 Add `memory_workspace` config | Add `memory_workspace: str | None = None` to `AgentConfig`; test env var loading | 1 hour |
| 2.3 Workspace initialization | Add `.gitignore` creation to `FileMemory.initialize()` | 1 hour |
| 2.4 Cross-workspace search | Add `workspace` param to `memory_search` + `memory_write`; implement `workspace="all"` with workspace registry; tag results | 3–4 hours |
| 2.5 Session initialization | Add `memory_dir` param to `SessionManager.get_or_create()`; compute workspace path in `session_websocket`; wire fallback chain | 2 hours |
| **2.6 NEW: Workspace discovery** | Implement workspace enumeration (scan `~/Workspaces/*/.nexusagent/` or config-based list) for `workspace="all"` | 1 hour |
| **Total Phase 2** | | **10–11 hours** (vs plan's 8 hours) |

---

## 9. Risk Assessment Updates

| Risk | From Plan | Additional Notes |
|------|-----------|-----------------|
| Workspace config breaking existing sessions | Low/Medium | ✅ Valid concern. Mitigated by: `memory_workspace=None` default preserves global behavior; session-scoped fallback unchanged |
| Session ID collisions across workspaces | Not mentioned | 🔍 NEW: If two projects reuse the same session_id, they'd share memory. Consider workspace-scoped session IDs or namespacing |
| `.gitignore` in non-git directories | Not mentioned | 🔍 NEW: `~/Workspaces/{project}/` may not be a git repo. `.gitignore` creation should be silent/no-op if no `.git/` exists |
| `_get_memory_workspace()` called from non-session context | Not mentioned | 🔍 NEW: Tools can be called outside a session (e.g., CLI, manual invocation). Must still return a valid path |

---

*Audit complete. Spec is structurally sound with minor corrections needed. No blocking issues found.*
