# SPEC-002: Memory System — Workspace-Scoped Storage

> Status: DRAFT
> Priority: HIGH
> Author: OWL (Lucien)
> Date: 2026-07-21

## Problem

Memories are currently stored in `~/.nexusagent/memory/` (global) regardless of which project the agent is working on. This means:

1. **Project A's memories pollute Project B's context** — Retrieval returns irrelevant memories from other projects
2. **No workspace isolation** — All projects share the same memory pool
3. **No version control** — Memories can't be committed alongside project code
4. **Session-scoped path is underutilized** — `~/.nexusagent/sessions/{session_id}/memory/` exists but tools don't use it

## Requirements

### FR-1: Project-Scoped Memory Workspace
- Memory tools default to the current session's workspace directory
- Workspace path: `~/Workspaces/{project}/.nexusagent/` (gitignored)
- Falls back to session directory if no project workspace
- Falls back to global `~/.nexusagent/memory/` if neither exists

### FR-2: Configurable Memory Workspace
- `memory_workspace` config option in `nexusagent.yaml`
- Per-session override via `memory_dir` parameter
- Tool parameter `workspace` overrides for explicit control

### FR-3: Memory Workspace Initialization
- Auto-create workspace directory structure on first use
- Create `.gitignore` in `.nexusagent/` to exclude from version control
- Separate `MEMORY.md` index per workspace

### FR-4: Cross-Workspace Memory Search
- `memory_search` accepts optional `workspace` parameter
- Default: search current workspace only
- `workspace="all"` searches all configured workspaces
- Results tagged with workspace source

## Non-Functional Requirements

- Backward compatible: existing global memories still accessible
- No data migration required (old global memories remain valid)
- Works with existing `HybridMemoryIndex` (just different root path)
- Tests for workspace isolation

## Acceptance Criteria

- [ ] Memory tools use session's workspace by default
- [ ] `memory_workspace` config option works
- [ ] Workspace directory auto-created with proper structure
- [ ] `.gitignore` created in workspace `.nexusagent/`
- [ ] Cross-workspace search works
- [ ] Existing global memories still accessible
- [ ] Tests pass (minimum 3 new tests)
- [ ] Zero regressions

## Technical Notes

- Modify `_get_memory_workspace()` in `tools/register_all.py` to accept session context
- Add `memory_workspace` to `infrastructure/config.py` ConfigSchema
- Workspace structure mirrors global: `MEMORY.md`, `memory/`, `bank/`, `bank/entities/`
- Index file: `.memory/index.sqlite` (hidden directory)
