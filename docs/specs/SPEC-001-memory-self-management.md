# SPEC-001: Memory System — Agent Self-Management Tools

> Status: DRAFT
> Priority: CRITICAL
> Author: OWL (Lucien)
> Date: 2026-07-21

## Problem

The NexusAgent memory system allows agents to write and search memories but provides no way to delete, update, or curate them. This creates several critical issues:

1. **Memory bloat** — Memories accumulate indefinitely with no pruning mechanism
2. **Stale data** — Outdated facts remain in the index, degrading retrieval quality
3. **Contradictions** — When facts change, old and new versions coexist without resolution
4. **No agent autonomy** — The agent cannot manage its own knowledge base

## Requirements

### FR-1: Memory Delete Tool
- Agent can delete a memory by its file path
- Deletion removes both the file and its index entries
- Confirmation message returned with details of what was deleted

### FR-2: Memory Update Tool
- Agent can update the content of an existing memory file
- Update re-indexes the modified file
- YAML frontmatter is preserved unless explicitly changed

### FR-3: Memory List Tool
- Agent can list all memories with optional filtering by type, date, or entity
- Returns file paths, descriptions, creation dates, and types

### FR-4: Memory Prune Tool
- Agent can prune memories matching criteria (age, type, low confidence)
- Dry-run mode shows what would be deleted without actually deleting
- Confirmation required for destructive operations

## Non-Functional Requirements

- All operations must maintain index consistency (file + SQLite index stay in sync)
- Operations must be atomic (no partial deletions)
- Path traversal protection on all file operations
- Tests for each new tool

## Acceptance Criteria

- [ ] `memory_delete(path)` tool registered and functional
- [ ] `memory_update(path, new_content)` tool registered and functional
- [ ] `memory_list(type?, date?, entity?)` tool registered and functional
- [ ] `memory_prune(older_than_days?, type?, dry_run=True)` tool registered and functional
- [ ] All tools have path traversal protection
- [ ] All tools maintain index consistency
- [ ] Tests pass for each tool (minimum 2 tests per tool)
- [ ] Zero regressions in existing tests

## Technical Notes

- File operations use `FileMemory` class methods
- Index operations use `HybridMemoryIndex` delete/rebuild methods
- Path validation uses `os.path.realpath()` + `startswith()` pattern (same as `memory_get`)
- Index cleanup: delete from `chunks`, `chunks_fts`, and `chunks_vec` tables where `file_path` matches
