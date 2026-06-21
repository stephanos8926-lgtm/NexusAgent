# NexusAgent Memory System Architecture

> **Version:** 2.0
> **Date:** 2026-06-21
> **Status:** Complete — 215 tests passing

---

## Overview

The NexusAgent memory system is a **hybrid file+vector architecture** with 4 layers. It provides persistent, searchable memory for AI agents across sessions, with automatic extraction, consolidation, and distributed sharing.

**Key design principles:**
1. **Files are canonical** — Markdown files in `bank/` are the source of truth
2. **Index is derived** — SQLite index is rebuilt from files on startup
3. **Git-backed** — Every change is committed for version history
4. **Lossless** — Compaction summarizes but never deletes originals

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT SESSION                             │
│                                                                  │
│  User Message → Memory Recall → Context Assembly → Agent Invoke  │
│       ↓              ↓                    ↓                      │
│  HybridMemoryManager         CompactionPipeline                  │
│       ↓              ↓                    ↓                      │
│  FileMemory (canonical)   DreamCycle (background)                │
│       ↓              ↓                    ↓                      │
│  HybridMemoryIndex (search)     NatsMemoryBus (distributed)      │
│       ↓                                                          │
│  bank/*.md + .memory/index.sqlite                                │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1: FileMemory (Canonical Storage)

**File:** `memory/memory_files.py`
**Class:** `FileMemory`

The canonical source of truth. All memories are stored as markdown files with YAML frontmatter in the `bank/` directory.

**File format:**
```markdown
---
name: "Brief description"
description: "Short title"
type: observation
confidence: 0.85
entities: ["entity1", "entity2"]
created: "2026-06-21T10:00:00+00:00"
valid_from: "2026-06-21T10:00:00+00:00"
valid_until: null
ttl_hours: null
source_session_id: "session-abc"
derived_from: []
related: ["bank/other-20260621.md"]
---

The full memory content goes here. This can be multiple paragraphs.
```

**Key methods:**
- `write_entry()` — Write a memory file with frontmatter
- `get_index_entries()` — Parse MEMORY.md index (with TTL filtering)
- `find_related()` — Find memories with shared entities or content overlap
- `sweep_expired()` — Remove expired memory files

**Features:**
- **Git-backed** — Auto-commits after every write via `MemoryGitOps`
- **TTL enforcement** — Expired entries excluded from search results
- **Bi-temporal** — `valid_from`/`valid_until` for time-based queries
- **Provenance** — `source_session_id` and `derived_from` for audit trail
- **Linking** — `related` field for bidirectional memory links

### Layer 2: HybridMemoryIndex (Search)

**File:** `memory/index/index.py`
**Class:** `HybridMemoryIndex`

SQLite-based hybrid search combining FTS5 (keyword) and sqlite-vec (vector similarity).

**Schema:**
```sql
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    content TEXT NOT NULL,
    embedding BLOB,
    indexed_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    content,
    id UNINDEXED,
    file_path UNINDEXED
);

CREATE VIRTUAL TABLE chunks_vec USING vec0(
    embedding float[384],
    id text,
    file_path text,
    content text
);
```

**Search flow:**
1. **Embed query** → vector (Gemini API → local model → SHA256 hash fallback)
2. **FTS5 search** → keyword matches with BM25 ranking
3. **Vector search** → cosine similarity with RRF fusion (k=60)
4. **Merge** → Combined results sorted by fused score
5. **Filter** → Apply bi-temporal and TTL filters

**Embedding provider chain:**
1. Gemini API (best quality)
2. Local sentence-transformers (fallback)
3. SHA256 hash (last resort — deterministic but low quality)

### Layer 3: HybridMemoryManager (Orchestration)

**File:** `memory/hybrid_memory.py`
**Class:** `HybridMemoryManager`

Top-level interface combining FileMemory + HybridMemoryIndex. Used by `Session` and memory tools.

**Key methods:**
- `remember()` — Write + index + auto-link + NATS publish
- `recall()` — Search both own + parent indices, merge results
- `get_memory_context()` — Search + format for prompt injection
- `flush()` — Pre-compaction save
- `close()` — Resource cleanup

**Parent memory inheritance:**
```python
mgr = HybridMemoryManager(
    workspace_dir="~/.nexusagent/sessions/child/memory",
    parent_memory_dir="~/.nexusagent/sessions/parent/memory",
)
# recall() searches both directories, marks parent results with [Parent]
```

**NATS integration:**
```python
mgr.set_nats_memory_bus(nats_bus)
# remember() publishes to NATS subjects after local write
```

### Layer 4: Background Processes

#### Auto-Extraction
**File:** `memory/extraction.py` (regex) + `memory/llm_extraction.py` (LLM)

Runs after every agent turn. Extracts facts from conversation text.

**Regex extractor** (always available):
- Decisions: "decided to", "chose to", "will use"
- Preferences: "I prefer", "I like", "always", "never"
- Errors: "error", "failed", "bug", "broken"
- Entities: file paths, proper nouns

**LLM extractor** (when `llm_call` provided):
- Structured JSON output with confidence scores
- Handles nuanced statements regex can't catch
- Falls back to regex on failure

#### Dream Cycle
**File:** `memory/dream.py`
**Class:** `DreamCycle`

Periodic 4-phase consolidation daemon:

1. **Scan** — Read all memory files, compute hashes, find duplicates/stale
2. **Patterns** — Extract recurring themes and insights (via LLM)
3. **Consolidate** — Merge duplicates, prune stale, resolve contradictions
4. **Trim** — Rebuild FTS5 index, trim MEMORY.md to ≤200 lines

**Trigger:** Every N turns (configurable, default 20)

#### Compaction Pipeline
**File:** `memory/compaction.py`
**Class:** `CompactionPipeline`

Graduated compaction strategies:
1. Clear old tool results
2. Microcompact (summarize short messages)
3. Summarize (LLM-based compression)
4. Truncate (emergency — hard limit)

**DAG-based compression** (`dag.py`):
- Depth-0: Specific decisions and technical details
- Depth-1: Conversation arc and outcomes
- Depth-2: Durable narrative and milestone timeline

#### NATS Memory Bus
**File:** `memory/nats_bus.py`
**Classes:** `NatsMemoryBus`, `NatsMemoryListener`

Distributed memory sharing across workers:

- **Publish** — Memory events published to `nexus.memory.remember/delete/promote`
- **Subscribe** — Workers receive memories from other workers
- **Dedup** — Event ID tracking prevents duplicate processing
- **Filter** — Own session events filtered out

#### Rate Limiter
**File:** `memory/rate_limiter.py`
**Class:** `MemoryRateLimiter`

Token-bucket rate limiting:
- 30 writes/minute
- 60 searches/minute
- Returns warning message when limit exceeded

---

## Session Integration

### Full Session (Session class)
**File:** `core/session/session.py`

```
Session.__init__()
  → HybridMemoryManager (memory_dir)
  → DreamCycle (dream_cycle_interval)
  → CompactionPipeline
  → MemoryExtractor (or LLMExtractor if llm_call)

Session.send(user_message)
  → hybrid_memory.get_memory_context() → SystemMessage
  → agent.invoke() with memory context
  → _schedule_extraction() (fire-and-forget)
  → _maybe_trigger_dream_cycle()
  → CompactionPipeline.check() → compact if needed
```

### Worker Session (SessionLite class)
**File:** `core/session/session_lite.py`

Lightweight session for worker agents — memory without event streaming.

```
SessionLite.__init__()
  → HybridMemoryManager (with optional parent_memory_dir)
  → MemoryExtractor (or LLMExtractor)

SessionLite.get_memory_context(query) → formatted context string
SessionLite.remember(content, type, ...) → filepath
SessionLite.extract_and_store(user_msg, response) → count
SessionLite.maybe_dream() → runs dream cycle at interval
```

### Worker Handler Integration
**File:** `core/worker/handler.py`

```python
# In _run_agent_task():
lite = SessionLite(working_dir, parent_memory_dir=parent_dir)
memory_ctx = await lite.get_memory_context(task.description)
state["task"] = f"{memory_ctx}\n\n---\n\nTask: {task.description}"
result = run_agent_task(state)
await lite.extract_and_store(task.description, result)
await lite.maybe_dream()
await lite.close()
```

---

## Configuration

```yaml
# config.yaml
agent:
  # Memory extraction
  memory_model: ""  # empty = use current model
  llm_extraction_enabled: false
  llm_extraction_min_confidence: 0.5

  # Dream cycle
  dream_cycle_interval: 20  # turns between consolidations

  # Compaction
  compaction_enabled: true
  compaction_tier2_threshold: 0.75
  compaction_tier2_fresh_tail: 32
  compaction_tier2_model: ""

  # NATS distributed memory
  nats_memory_enabled: false
  nats_memory_subject_prefix: "nexus.memory"
  nats_memory_filter_own_events: true

  # Git-backed memory
  memory_git_enabled: true
  memory_git_auto_commit: true

  # Rate limiting
  memory_rate_limit_writes_per_minute: 30
  memory_rate_limit_searches_per_minute: 60
```

---

## Data Flow

### At Session Start
```
1. Session created with session_id + working_dir
2. HybridMemoryManager initialized at ~/.nexusagent/sessions/{id}/memory/
3. FileMemory.initialize() creates bank/ + entities/ + git repo
4. HybridMemoryIndex loads or creates .memory/index.sqlite
5. If parent_memory_dir set → inherit parent memories
6. Cross-session memories discovered via working_dir matching
```

### During Conversation
```
1. User message received
2. hybrid_memory.get_memory_context() searches for relevant memories
3. Memories injected as SystemMessage
4. Agent processes with full context
5. Fire-and-forget: _run_extraction() extracts facts from turn
6. Extracted facts stored as observation memories
7. Every N turns: DreamCycle runs consolidation
```

### At Session End
```
1. hybrid_memory.flush() saves pre-compaction summary
2. hybrid_memory.close() releases SQLite connections
3. Git repo retains full history
```

### Worker Flow
```
1. Worker spawned with task + working_dir + parent_memory_dir
2. SessionLite created with parent inheritance
3. Memory context injected into task description
4. Agent processes task
5. Post-turn: auto-extraction stores observations
6. Dream cycle runs if interval reached
7. SessionLite.close() cleans up
```

---

## Competitive Comparison

| Feature | Letta | Mem0 | Zep | LangMem | NexusAgent |
|---------|-------|------|-----|---------|------------|
| Cross-session memory | ✅ | ✅ | ✅ | ✅ | ✅ |
| Auto-extraction | ✅ | ✅ | ✅ | ✅ | ✅ (regex + LLM) |
| Consolidation daemon | ✅ | ✅ | ✅ | ✅ | ✅ (dream cycle) |
| Bi-temporal facts | ✅ | ✅ | ✅ | ❌ | ✅ |
| Git-backed storage | ✅ | ❌ | ❌ | ❌ | ✅ |
| LLM refinement layer | ❌ | ❌ | ❌ | ❌ | ✅ |
| Contradiction detection | ❌ | ❌ | ✅ | ❌ | ✅ |
| Memory linking | ❌ | ❌ | ❌ | ❌ | ✅ |
| Rate limiting | ❌ | ❌ | ❌ | ❌ | ✅ |
| NATS distributed memory | ❌ | ❌ | ❌ | ❌ | ✅ |
| Worker memory inheritance | ❌ | ❌ | ❌ | ❌ | ✅ |
| Tests | — | — | — | — | 215 |

---

## Directory Structure

```
~/.nexusagent/
├── NEXUS.md                    # Global base prompt
├── memory/                     # Global memory bank
│   ├── bank/                   # Memory files (type-slug-timestamp.md)
│   │   ├── world-20260621.md
│   │   ├── observation-20260621.md
│   │   └── ...
│   ├── entities/               # Auto-generated entity pages
│   ├── memory/                 # HybridMemoryIndex
│   │   └── index.sqlite        # FTS5 + sqlite-vec
│   └── MEMORY.md               # Index (≤200 lines, ≤25KB)
│
└── sessions/
    └── {session_id}/
        └── memory/             # Session-scoped memory (same structure)
            ├── bank/
            ├── entities/
            ├── memory/
            │   └── index.sqlite
            └── MEMORY.md
```

---

## Key Lessons Learned

1. **Never trust session summaries over `git log`** — Compaction destroys history; git is the only source of truth
2. **Write SESSION_STATE.md within first 5 minutes** — Before compaction can hit
3. **Two compression systems = auto-reset** — Disable built-in when using LCM
4. **Subagents timeout at 600s** — Do complex work inline, delegate only S-sized tasks
5. **`patch` tool requires `path=` not `file=`** — Silent failure otherwise
6. **Workers bypass Session** — Need SessionLite or explicit memory wiring
