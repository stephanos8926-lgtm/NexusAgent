# NexusAgent Memory System — Comprehensive Analysis

> Date: 2026-07-21
> Author: OWL (Lucien)
> Status: Draft for review

---

## Table of Contents

1. [How the New Memory System Works (Detailed)](#1-how-the-new-memory-system-works)
2. [Agent Memory Management Capabilities](#2-agent-memory-management-capabilities)
3. [Where Memories Are Stored](#3-where-memories-are-stored)
4. [Comparison with Other Memory Systems](#4-comparison-with-other-memory-systems)
5. [Forward Audit — What's Missing](#5-forward-audit--whats-missing)
6. [Reverse Audit — What Could Go Wrong](#6-reverse-audit--what-could-go-wrong)
7. [Innovation Brainstorm](#7-innovation-brainstorm)
8. [Recommendations](#8-recommendations)

---

## 1. How the New Memory System Works

### Architecture Overview

The system follows a **"files are canonical, index is derived"** philosophy. There are 4 layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                    HybridMemoryManager                          │
│                    (Top-level API)                               │
│                                                                 │
│  remember() → write file + index it                            │
│  recall()   → hybrid search (keyword + vector)                 │
│  get_memory_context() → format results for prompt injection    │
│  flush()    → write daily log + re-index                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐    ┌──────────────────────────────┐   │
│  │    FileMemory        │    │   HybridMemoryIndex           │   │
│  │  (Canonical Store)   │    │   (Search Engine)             │   │
│  │                      │    │                                │   │
│  │  MEMORY.md (index)   │    │  SQLite FTS5 (keyword/BM25)   │   │
│  │  memory/YYYY-MM-DD   │    │  sqlite-vec (vector KNN)      │   │
│  │  bank/*.md (topics)  │    │  Union merge: 70% vec + 30% kw│   │
│  │  bank/entities/*.md  │    │                                │   │
│  └─────────────────────┘    └──────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              EmbeddingProvider                             │  │
│  │  Tier 1: Gemini API (3072-dim, best quality)              │  │
│  │  Tier 2: sentence-transformers local (384-dim, padded)    │  │
│  │  Tier 3: SHA256 hash fallback (3072-dim, deterministic)   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1: FileMemory — Canonical Storage

**Location:** `src/nexusagent/memory/memory_files.py`

All memories are stored as markdown files on disk. This is the **source of truth** — the index is always rebuildable from these files.

**Directory structure:**
```
workspace/
├── MEMORY.md              ← Index (pointers only, ≤200 lines / 25KB)
├── memory/
│   └── 2026-07-21.md      ← Daily log (narrative + ## Retain sections)
└── bank/
    ├── auth-jwt-20260721.md    ← Topic file (typed memory entry)
    ├── deploy-20260721.md      ← Topic file
    └── entities/
        └── steven.md           ← Entity page (aggregated mentions)
```

**Topic file format (YAML frontmatter + markdown):**
```yaml
---
name: "Auth uses JWT"
description: "The authentication module uses JWT tokens"
type: world
created: 2026-07-21T12:00:00
---
The auth module in NexusAgent uses JWT tokens for API key verification.
Tokens are stored in Fernet-encrypted keystore at ~/.nexusagent/.keys.
```

**Memory types (StrEnum):**
- `world` — Objective facts about the environment
- `experience` — Actions the agent has taken
- `opinion` — Preferences with confidence scores (0.0-1.0)
- `observation` — Summaries or generated insights

**Key functions:**

| Function | Purpose |
|----------|---------|
| `initialize()` | Creates directory structure and empty MEMORY.md |
| `write_entry(content, type, description, confidence, entities)` | Writes topic file + updates index + creates entity pages |
| `append_daily_log(content)` | Appends to today's daily log |
| `get_index_entries()` | Parses MEMORY.md, returns list of index pointers |
| `read_topic_file(filename)` | Reads a specific topic file |
| `get_daily_logs(days=2)` | Returns recent daily logs with `## Retain` sections |
| `list_all_files()` | Lists all .md files in bank/ and memory/ |

**Index management:**
- MEMORY.md is kept under 200 lines / 25KB
- Each entry is a one-line pointer: `- [W] Auth uses JWT → bank/auth-jwt-20260721.md`
- Truncation happens automatically when limits are exceeded

### Layer 2: HybridMemoryIndex — Search Engine

**Location:** `src/nexusagent/memory/index/index.py`

Makes files searchable via **two complementary methods**:

**SQLite FTS5 (keyword search):**
- Breaks documents into tokens
- Uses BM25 ranking
- Good for exact matches, code references, proper nouns

**sqlite-vec (vector similarity search):**
- Each document chunk → 3072-dim float vector
- KNN (K-Nearest Neighbors) search
- Good for semantic similarity, paraphrased queries

**Search flow:**
```
Query: "how does authentication work?"
  ↓
1. Embed query → 3072-dim vector (via EmbeddingProvider)
2. FTS5 search: MATCH '"authentication" AND "work"' → top 24 results
3. sqlite-vec KNN: embedding MATCH ? → top 24 results
4. Union merge: 0.7 × vector_score + 0.3 × keyword_score
5. Return top 6 with citations (file path + line numbers)
```

**Chunking strategy:**
- Chunk size: ~400 characters (~4 chars per token heuristic)
- Overlap: 80 characters between chunks
- YAML frontmatter is stripped before indexing

**Database schema:**
```sql
chunks (id, file_path, line_start, line_end, content, embedding, indexed_at)
chunks_fts (content, id UNINDEXED, file_path UNINDEXED)  -- FTS5 virtual table
chunks_vec (id, embedding float[3072])                     -- sqlite-vec virtual table
file_meta (file_path, mtime, hash, last_indexed)
```

**Key functions:**

| Function | Purpose |
|----------|---------|
| `index_file(path)` | Sync indexing (uses hash embedding fallback) |
| `async_index_file(path)` | Async indexing (uses full Gemini→local→hash chain) |
| `search(query, max_results=6)` | Hybrid async search |
| `search_sync(query, max_results=6)` | Synchronous search (hash fallback only) |
| `_chunk_text(text)` | Splits text into overlapping chunks |
| `rebuild()` | Drops and re-indexes all files |

### Layer 3: EmbeddingProvider — Vectorization

**Location:** `src/nexusagent/memory/index/embeddings.py`

Three-tier fallback chain:

```
Tier 1: Gemini API (gemini-embedding-001)
  → 3072-dim vectors, best quality
  → Requires GEMINI_API_KEY
  → ~20 requests/day free tier shared across all Gemini models
  ↓ fails
Tier 2: Local sentence-transformers (all-MiniLM-L6-v2)
  → 384-dim vectors, padded to 3072
  → Requires sentence-transformers package + model download (~90MB)
  ↓ fails
Tier 3: SHA256 hash fallback
  → 3072-dim deterministic pseudo-vectors
  → Always works, no dependencies
  → Low quality: only exact/near-exact matches work
```

**Vector serialization:**
- `_vec_to_blob(vec)` → pack float32 list into bytes for sqlite-vec storage
- `_blob_to_vec(blob)` → unpack bytes back to float32 list

**Thread pool:**
- Per-tenant ThreadPoolExecutor (keyed by workspace path)
- 4 workers per pool
- Used to run blocking SQLite operations in async context

### Layer 4: HybridMemoryManager — Top-Level API

**Location:** `src/nexusagent/memory/hybrid_memory.py`

The unified interface that combines all layers:

| Function | What it does |
|----------|-------------|
| `remember(content, type, description, confidence, entities)` | Writes entry to file + async index. Returns file path. |
| `recall(query, max_results=6)` | Hybrid search. Returns `[{file, content, score}, ...]` |
| `get_memory_context(query, max_results=5)` | Formats recall results as `"## Relevant Memories\nSource: bank/foo.md (score: 0.95)\n..."` for prompt injection |
| `flush(session_summary)` | Writes summary to daily log + re-indexes. Called before compaction. |

### CompactionPipeline — Context Window Management

**Location:** `src/nexusagent/memory/compaction.py`

Four graduated levels (cheapest → most expensive):

1. **Clear tool results** — Replace old tool result content with placeholder (keeps last 5 turns)
2. **Microcompact** — Same but more aggressive (keeps last 3 turns)
3. **Summarize** — Replace old messages with heuristic summary SystemMessage
4. **Emergency truncate** — Keep only last 5 messages + warning

Triggered when token count exceeds 75% of context window (default 200K tokens).

**Pre-compaction flush:** Before compaction, the session summary is written to the daily log via `hybrid_memory.flush()` so nothing is lost.

---

## 2. Agent Memory Management Capabilities

### What the Agent CAN Do

The agent has 5 memory-related tools registered:

| Tool | Description |
|------|-------------|
| `memory_search(query, max_results=6)` | Search memory using hybrid keyword + vector search |
| `memory_get(path, offset, limit)` | Read a specific memory file by relative path |
| `memory_write(content, type, description, confidence, entities)` | Write a new memory entry |
| `memory_index_search(query, max_results, workspace)` | Direct index search (more powerful) |
| `memory_index_rebuild(workspace)` | Rebuild the entire index from files |

**The agent can:**
- ✅ Write new memories (typed: world/experience/opinion/observation)
- ✅ Search existing memories (hybrid keyword + vector)
- ✅ Read specific memory files
- ✅ Rebuild the index
- ✅ Have memories automatically injected into its system prompt via `get_memory_context()`

### What the Agent CANNOT Do

- ❌ **Delete memories** — No `memory_delete()` tool exists
- ❌ **Edit memories** — No `memory_update()` tool exists
- ❌ **Curate/prune memories** — No deduplication, staleness detection, or consolidation
- ❌ **Resolve contradictions** — No conflict detection between memories
- ❌ **Set memory importance/priority** — No importance scoring or TTL
- ❌ **Organize memories** — No tagging, categorization, or linking beyond entity pages
- ❌ **Forget** — No decay, no staleness detection, no automatic pruning

### What Happens Automatically

1. **Memory context injection** — Every user message triggers `get_memory_context()` which searches and injects relevant memories as a SystemMessage
2. **Daily log flushing** — Before context compaction, session summaries are written to daily logs
3. **Index rebuilding** — Available as a tool but not automatic
4. **Entity page creation** — When `entities` parameter is provided to `memory_write()`

---

## 3. Where Memories Are Stored

### Current Storage Locations

There are **two separate memory workspaces**:

**1. Session-scoped (in `Session.__init__`):**
```python
memory_dir = ~/.nexusagent/sessions/{session_id}/memory/
```
Used by `session.hybrid_memory` for automatic memory context injection during conversations.

**2. Global default (in `_get_memory_workspace`):**
```python
_DEFAULT_MEMORY_WORKSPACE = "~/.nexusagent/memory/"
```
Used by the agent's memory tools (`memory_search`, `memory_write`, etc.).

### The Problem

**Memories are NOT stored in the user's workspace.** They're stored in `~/.nexusagent/` which is a global, hidden directory. This means:

1. **Project-specific memories are lost** — If you work on project A, then switch to project B, memories from project A are still in the global workspace but not relevant
2. **No workspace isolation** — All projects share the same memory pool
3. **No `.gitignore` integration** — Memories in `~/.nexusagent/` can't be version-controlled per-project
4. **The session-scoped path is created but underutilized** — Each session gets its own directory, but the memory tools don't use it

### Where They SHOULD Be Stored

The ideal setup:
```
~/.nexusagent/
├── memory/                    ← Global/cross-project memories
│   ├── MEMORY.md
│   ├── memory/
│   └── bank/
└── sessions/
    └── {session_id}/
        └── memory/            ← Session-scoped memories
            ├── MEMORY.md
            ├── memory/
            └── bank/

~/Workspaces/{project}/        ← User's workspace
├── .nexusagent/               ← Project-specific memories (gitignored)
│   ├── MEMORY.md
│   ├── memory/
│   └── bank/
└── ...
```

---

## 4. Comparison with Other Memory Systems

### A) NexusAgent vs Hermes Memory System

| Dimension | NexusAgent | Hermes Agent |
|-----------|-----------|--------------|
| **Storage** | Files (markdown) + SQLite index | Honcho (external service) + local memory files |
| **Search** | Hybrid FTS5 + sqlite-vec | Honcho semantic search + file-based |
| **Scope** | Session + global | Cross-session via Honcho |
| **Consolidation** | None (manual only) | Honcho dialectic deriver (automatic) |
| **Forgetting** | None | Honcho manages decay |
| **Privacy** | Local-only | Cloud (Honcho service) |
| **Offline** | Fully offline | Requires Honcho connection for full features |
| **Memory types** | world/experience/opinion/observation | User profile, conversation history, conclusions |
| **Agent self-management** | Write/search only | Limited (via Honcho API) |

**Key difference:** Hermes relies on an external managed service (Honcho) for cross-session memory, while NexusAgent is entirely local. NexusAgent has better file-based organization but lacks Honcho's automatic consolidation and dialectic reasoning.

### B) NexusAgent vs Honcho

| Dimension | NexusAgent | Honcho |
|-----------|-----------|--------|
| **Architecture** | File + SQLite vector index | Cloud-hosted dialectic memory service |
| **Reasoning** | None (static storage) | Dialectic reasoning layer (LLM-powered) |
| **Memory model** | Typed entries (world/experience/opinion) | Peer cards, conclusions, conversation excerpts |
| **Consolidation** | None | Automatic (deriver runs on schedule) |
| **Cross-session** | Via file persistence | Native (cloud-backed) |
| **Privacy** | Fully local | Data sent to Honcho servers |
| **Cost** | Free (local compute) | Free tier + paid for dialectic features |
| **Failure mode** | Index corruption (rebuildable) | Service outage = no memory |

**Key difference:** Honcho is a managed intelligence layer that reasons about memories. NexusAgent is a storage layer that the agent must manually manage. Honcho's dialectic reasoning can synthesize new insights from accumulated memories; NexusAgent has no equivalent.

### C) NexusAgent vs Leading Memory Systems (2026)

| System | Architecture | Key Innovation | NexusAgent Gap |
|--------|-------------|----------------|----------------|
| **Mem0** | Vector store + LLM extraction | 4-scope model (user/session/agent/task), 26% improvement on LoCoMo | No scope separation, no LLM extraction |
| **Letta (MemGPT)** | Virtual context + blocks | Agent self-manages memory like OS pages | No self-management, no block swapping |
| **Graphiti/Zep** | Temporal knowledge graph | Bi-temporal edges, entity-event synthesis, 94.8% DMR | No graph, no temporal versioning |
| **A-MEM** | Zettelkasten-style links | Dynamic inter-memory linking, NeurIPS 2025 | No linking between memories |
| **MemForest** | Hierarchical temporal index | MemTree: time-ordered tree structure, write-efficient | Flat file structure, no temporal hierarchy |
| **Engram** | Bi-temporal graph + hybrid read | Dual-process (fast write + slow consolidation), provenance-tagged | No consolidation process, no provenance |
| **Minta** | Quality-focused | Conflict detection, staleness monitoring, redundancy checks | No quality checks at all |
| **Dream Memory** | Sleep-cycle consolidation | Orient→Gather→Consolidate→Prune pipeline | No background consolidation |
| **xMemory** | Decouple→Aggregate | Hierarchical grouping, adaptive retrieval | Flat chunks, no grouping |
| **PRISM** | Intent-aware graph retrieval | Typed-edge routing, LLM-side compression | No graph edges, no intent routing |
| **Amory** | Narrative-driven | Episodic narratives, momentum-aware consolidation | No narrative structure |
| **DeltaCore** | Causal delta + belief state | Causal deltas, POMDP belief update, SO-Spindle-Ripple | No causal modeling, no belief state |

### Summary of Gaps

| Capability | NexusAgent | Best-in-class |
|-----------|-----------|---------------|
| **Storage** | Files + SQLite | ✅ Competitive |
| **Search** | FTS5 + vector | ✅ Competitive |
| **Embedding** | 3-tier fallback | ✅ Competitive |
| **Consolidation** | ❌ None | Dream Memory, Letta |
| **Forgetting/Decay** | ❌ None | Minta, DeltaCore |
| **Conflict resolution** | ❌ None | Minta, Engram |
| **Temporal reasoning** | ❌ None | Graphiti, Engram |
| **Knowledge graph** | ❌ None | Graphiti, PRISM |
| **Self-management** | ❌ None | Letta, MemGPT |
| **Quality monitoring** | ❌ None | Minta |
| **Narrative structure** | ❌ None | Amory |
| **Causal modeling** | ❌ None | DeltaCore |
| **Scope separation** | Partial (session/global) | Mem0 (4-scope) |
| **Write-time dedup** | ❌ None | AgentOS, Distill |
| **Hierarchical indexing** | ❌ None | MemForest, xMemory |

---

## 5. Forward Audit — What's Missing

### Critical Gaps (Deployment Blocking)

1. **No memory deletion** — Agent can write but never delete. Accumulated stale memories will bloat context and degrade retrieval quality.

2. **No memory editing** — Agent can't update existing memories. If a fact changes, the agent must write a new memory and the old one stays, creating contradictions.

3. **No staleness detection** — Memories never expire or decay. A preference from 6 months ago is treated with equal weight to one from today.

4. **No conflict resolution** — When two memories contradict each other, the system has no way to detect or resolve it.

5. **No consolidation** — No background process to merge duplicates, prune stale entries, or synthesize higher-level insights.

6. **No workspace isolation** — All projects share the same memory pool. Project A's memories pollute Project B's context.

### High-Priority Gaps (Quality of Life)

7. **No write-time deduplication** — Agent can write the same fact 10 times. No cosine similarity check at write time.

8. **No importance scoring** — All memories are equal. No way to mark some as "core" vs "ephemeral".

9. **No memory linking** — Memories are isolated files. No "see also" or "related" connections.

10. **No temporal metadata** — No "valid from" / "valid until" timestamps. No way to represent "this was true then but not now".

11. **No entity resolution** — "Steven", "Steven Page", "sysop" are treated as separate entities.

12. **No background consolidation daemon** — No periodic "sleep cycle" to organize memories.

### Medium-Priority Gaps (Competitive Parity)

13. **No hierarchical memory** — Flat file structure. No topic/subtopic hierarchy.

14. **No knowledge graph** — No entity-relationship modeling. Can't answer "what does X depend on?"

15. **No narrative structure** — No episodic narratives. Just isolated facts.

16. **No provenance tracking** — Can't trace which conversation a memory came from.

17. **No memory health metrics** — No way to measure memory quality, coverage, or staleness.

18. **No TTL support** — Can't set "forget this in 7 days".

### Low-Priority Gaps (Nice to Have)

19. **No multi-modal memories** — Text only. No image/audio memory support.

20. **No collaborative memory** — No way to share memories across agents or users.

21. **No memory encryption** — Memories stored in plaintext on disk.

22. **No memory versioning** — Can't see history of changes to a memory.

---

## 6. Reverse Audit — What Could Go Wrong

### Stability Risks

1. **Index corruption** — If `index.sqlite` gets corrupted, all vector search breaks. The `rebuild()` function exists but is manual. No automatic integrity checking.

2. **Embedding dimension mismatch** — If the embedding model changes (e.g., switching from Gemini to a different provider), existing vectors become incompatible. The code handles this for `chunks_vec` but not for the old `Memory` system's `vec_memories`.

3. **SQLite in async context** — The `HybridMemoryIndex` uses `run_in_executor` for SQLite operations, but the connection is opened/closed per operation. Under high load, this could cause connection storms.

4. **No file locking** — If two sessions write to the same memory file simultaneously, data loss could occur.

5. **MEMORY.md truncation** — The 200-line/25KB limit could silently drop index entries if not monitored.

6. **Thread pool exhaustion** — Per-tenant thread pools (4 workers each) could exhaust system resources with many concurrent workspaces.

### Security Risks

7. **Path traversal in memory_get** — The `memory_get` tool has path traversal protection, but `memory_write` does not validate the description parameter which is used to generate filenames.

8. **No memory access control** — Any tool caller can read/write any memory. No per-user or per-session isolation.

9. **Sensitive data in memories** — No scanning for secrets/credentials in memory content.

### Data Integrity Risks

10. **Silent embedding failures** — If Gemini and local embeddings both fail, the hash fallback produces low-quality vectors silently. Search quality degrades without warning.

11. **Chunk boundary issues** — Fixed-size chunking (400 chars) can split sentences mid-word, reducing retrieval quality.

12. **No transaction safety** — If the process crashes during `async_index_file()`, the database could be in an inconsistent state (some chunks written, others not).

### Scalability Risks

13. **Brute-force vector fallback** — If sqlite-vec KNN fails, the brute-force cosine similarity loads ALL embeddings into memory. With 10K+ chunks, this causes OOM.

14. **No pagination for large result sets** — `list_all_files()` returns all files at once.

15. **File system limits** — With thousands of small .md files in `bank/`, filesystem performance degrades.

---

## 7. Innovation Brainstorm

### Near-Term (1-2 weeks)

**1. Write-time deduplication**
```python
async def remember(content, ...):
    # Before writing, check if similar memory exists
    existing = await self.recall(content, max_results=3)
    if existing and existing[0]["score"] > 0.95:
        return existing[0]["file"]  # Skip duplicate
    # ... proceed with write
```

**2. Memory edit/delete tools**
```python
@register_tool(name="memory_update", ...)
async def memory_update(path, new_content): ...

@register_tool(name="memory_delete", ...)
async def memory_delete(path): ...
```

**3. TTL support**
```yaml
---
name: "Temporary fact"
type: world
ttl_hours: 24
---
```
Auto-prune expired entries during consolidation.

**4. Workspace-scoped memory tools**
```python
# In memory tools, use session's workspace instead of global default
def _get_memory_workspace():
    session = get_current_session()
    if session:
        return session.memory_dir  # Project/session specific
    return _DEFAULT_MEMORY_WORKSPACE
```

### Medium-Term (1-2 months)

**5. Background consolidation daemon** (à la Dream Memory)
```
Every N minutes or M new memories:
  1. Orient: Scan all memories, identify stale/contradictory/redundant
  2. Gather: Collect related memories into groups
  3. Consolidate: Merge duplicates, resolve contradictions (prefer newer)
  4. Prune: Remove stale, low-value entries
  5. Re-index: Rebuild FTS5 index
```

**6. Bi-temporal memory** (à la Graphiti/Engram)
```yaml
---
name: "API uses JWT"
type: world
valid_from: 2026-01-01
valid_until: 2026-06-15
superseded_by: bank/api-oauth-20260615.md
---
```
Enables "what did we believe at time T?" queries.

**7. Entity resolution**
```python
# During write_entry, normalize entity names
"Steven" → "Steven Page" (via entity resolution)
"sysop" → "Steven Page" (via alias mapping)
```

**8. Memory linking** (à la A-MEM/Zettelkasten)
```yaml
---
name: "Auth uses JWT"
related: [bank/deploy-pipeline-20260720.md, bank/api-design-20260718.md]
derived_from: memory/2026-07-21.md#12:30
---
```

### Long-Term (3-6 months)

**9. Hierarchical temporal index** (à la MemForest)
```
bank/
├── 2026/
│   ├── 07/
│   │   ├── 21/
│   │   │   ├── auth-jwt.md
│   │   │   └── deploy-pipeline.md
│   │   └── 20/
│   │       └── api-design.md
```
Enables time-range queries: "what did I learn about auth in July?"

**10. Knowledge graph layer** (à la Graphiti/PRISM)
```python
# Extract entities and relationships from memories
graph.add_entity("JWT", type="technology")
graph.add_entity("AuthModule", type="component")
graph.add_edge("AuthModule", "uses", "JWT", confidence=0.95)
```

**11. Dual-process architecture** (à la Engram)
```
System-1 (fast): Write raw chunk to daily log immediately
System-2 (slow): Background LLM extracts facts, builds knowledge graph
```

**12. Memory quality scoring** (à la Minta)
```python
class MemoryQuality:
    freshness: float      # Decay based on age
    retrieval_count: int  # How often accessed
    conflict_score: float # Contradicts other memories
    confidence: float     # From source (opinion type)
    utility: float        # Composite score
```

**13. Associative retrieval** (à la MRAgent)
```python
# Instead of flat vector search, use tag-based associative indexing
tags = {"auth", "jwt", "security", "api"}
# Query: "security" → finds all security-tagged memories
# Then: traverse links to related tags
```

**14. Causal delta tracking** (à la DeltaCore)
```python
class CausalDelta:
    cause: str      # "User changed auth from JWT to OAuth"
    effect: str     # "API tokens now use OAuth flow"
    outcome: str    # "Auth tests pass"
    confidence: float
```

### Truly Innovative Ideas

**15. Memory "dream state"** — During idle time, the agent runs a background process that:
- Re-reads all memories
- Identifies patterns and connections the agent missed while busy
- Synthesizes new "insight" memories
- Prunes memories that haven't been accessed in N days
- Resolves contradictions by preferring more recent or more confident sources

**16. Memory "immune system"** — Detect and flag:
- Memories that contradict each other (conflict detection)
- Memories that are too similar (redundancy detection)
- Memories that contain sensitive data (PII scanning)
- Memories that are stale based on external signals (e.g., file changed)

**17. Memory "genome"** — Each memory gets a structured "genome":
```yaml
---
genome:
  type: world
  domain: authentication
  confidence: 0.95
  sources: [conversation, code-analysis]
  related_entities: [jwt, api, security]
  valid: forever
  access_pattern: [2026-07-21, 2026-07-22]  # Track when retrieved
  mutation_history: []  # Track edits
---
```

**18. Cross-agent memory sharing** — Multiple agents working on the same project can share a memory pool with conflict resolution:
```
Agent A writes: "The API uses JWT"
Agent B writes: "The API uses OAuth"  
System detects conflict → flags for resolution
```

---

## 8. Recommendations

### Immediate (This Week)

1. **Add `memory_delete` and `memory_update` tools** — 2 hours of work, critical for agent autonomy
2. **Add write-time deduplication** — Check cosine similarity before writing, skip if >0.95
3. **Fix workspace isolation** — Memory tools should use session's `memory_dir`, not global default
4. **Add TTL support** — Simple `ttl_hours` field in YAML frontmatter, prune during flush

### Short-Term (Next 2 Weeks)

5. **Add background consolidation daemon** — Orient→Gather→Consolidate→Prune cycle
6. **Add memory health metrics** — Count, size, staleness, contradiction rate
7. **Add entity resolution** — Normalize entity names during write
8. **Add automatic index integrity check** — On startup, verify index matches files

### Medium-Term (Next Month)

9. **Add bi-temporal support** — `valid_from`/`valid_until` fields
10. **Add memory linking** — `related` field in YAML frontmatter
11. **Add knowledge graph layer** — Extract entities and relationships
12. **Add memory quality scoring** — Freshness, retrieval count, conflict score

### Long-Term (Next Quarter)

13. **Implement dual-process architecture** — Fast write + slow consolidation
14. **Add hierarchical temporal indexing** — Date-based directory structure
15. **Add associative retrieval** — Tag-based navigation
16. **Add memory "dream state"** — Background synthesis and pruning

---

## Appendix: Database Schema Comparison

### NexusAgent (New System)
```
Files on disk:
  MEMORY.md                    ← Index (pointers)
  memory/YYYY-MM-DD.md         ← Daily logs
  bank/*.md                    ← Topic files (typed memories)
  bank/entities/*.md           ← Entity pages

SQLite (index.sqlite):
  chunks (id, file_path, line_start, line_end, content, embedding, indexed_at)
  chunks_fts (content, id, file_path)     -- FTS5
  chunks_vec (id, embedding float[3072])  -- sqlite-vec
  file_meta (file_path, mtime, hash, last_indexed)
```

### NexusAgent (Old System — Dead Code)
```
SQLite (per-session):
  memories (id, memory_id, content, metadata, created_at, embedding)
  vec_memories (id, memory_id, embedding float[3072])  -- sqlite-vec
```

### Mem0 (Reference)
```
Vector store:
  memories (id, text, embedding, metadata, created_at, updated_at)
  entities (id, name, type, metadata)
  
Scopes: user, session, agent, task
```

### Graphiti/Zep (Reference)
```
Graph database (Neo4j):
  nodes: Entity, Episode, Community
  edges: RELATES_TO, MENTIONS, SUPERSEDES
  temporal: valid_from, valid_until on all edges
```

### Engram (Reference)
```
Dual store:
  Hot: Raw chunks (immediate write)
  Warm: Bi-temporal knowledge graph (async consolidation)
  
Retrieval: dense + lexical + graph + recency → RRF fusion
```
