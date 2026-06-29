# NexusAgent Memory Architecture v2

**Version:** 2.0 (2026-06-28)  
**Status:** ✅ Production-ready  
**Tests:** 208 passing (zero regressions)

---

## Overview

NexusAgent uses a **hybrid file+vector memory architecture** with 4 layers designed for persistence, search, and intelligent consolidation.

### Core Principles

1. **Files = Canonical** — Markdown files in `bank/` are the source of truth
2. **Index = Rebuildable** — Vector index can be regenerated from files
3. **Git-backed** — Every write auto-committed for audit trail
4. **Multi-timescale** — Short-term (session) + long-term (consolidated)
5. **TTL-aware** — Expired memories swept automatically
6. **Workspace-scoped** — Memories isolated per project/workspace

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Background Processes                          │
│  - MemoryExtractor (auto-extract from conversations)    │
│  - DreamCycle (4-phase consolidation daemon)           │
│  - CompactionPipeline (hierarchical compression)       │
│  - MemoryRateLimiter (token-bucket rate limiting)      │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│  Layer 3: HybridMemoryManager (Orchestration)           │
│  - remember() — Write + index                           │
│  - get_memory_context() — Search + format for prompts  │
│  - flush() — Pre-compaction save                        │
│  - close() — Resource cleanup                           │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│  Layer 2: HybridMemoryIndex (Search)                    │
│  - FTS5 (keyword search, BM25 scoring)                 │
│  - sqlite-vec (semantic search, cosine similarity)     │
│  - RRF fusion (k=60, combines both signals)            │
│  - Embedding providers (Gemini API → local fallback)   │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│  Layer 1: FileMemory (Canonical Storage)                │
│  - Markdown files with YAML frontmatter                │
│  - Git-backed auto-commits (MemoryGitOps)              │
│  - Bi-temporal fields (valid_from, valid_until)        │
│  - TTL enforcement (sweep_expired)                     │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 1: FileMemory (Canonical Storage)

**File:** `src/nexusagent/memory/memory_files.py`

### Structure

```
~/.nexusagent/bank/
├── 2026-06-28-decision-architecture-choice.md
├── 2026-06-28-preference-coding-style.md
├── 2026-06-28-error-toctou-race.md
└── daily/
    └── 2026-06-28.md  # Aggregated daily observations
```

### YAML Frontmatter Schema

```yaml
---
type: decision  # | preference | error | observation | entity
description: "Chose hybrid memory over pure vector DB"
confidence: 0.95
entities: ["NexusAgent", "memory system", "architecture"]
ttl_hours: 720  # 30 days
valid_from: "2026-06-28T00:00:00Z"
valid_until: "2026-07-28T00:00:00Z"
related: ["memory-system-v2", "file-backed-storage"]
---

Markdown content goes here...
```

### Key Features

- **Auto-commit:** Every write triggers `MemoryGitOps.commit()` with descriptive message
- **Bi-temporal:** `valid_from`/`valid_until` for time-based queries
- **TTL:** Expired memories excluded from recall, physically swept by `sweep_expired()`
- **Entity extraction:** Regex-based auto-tagging during write
- **Daily logs:** Observations aggregated into daily summaries

---

## Layer 2: HybridMemoryIndex (Search)

**Files:** 
- `src/nexusagent/memory/index/index.py` — Hybrid search engine
- `src/nexusagent/memory/index/embeddings.py` — Embedding provider

### Dual-Engine Search

| Engine | Purpose | Scoring | Speed |
|--------|---------|---------|-------|
| **FTS5** | Keyword matching | BM25 | <10ms |
| **sqlite-vec** | Semantic similarity | Cosine (384-dim) | <50ms |

### Fusion Strategy

**Reciprocal Rank Fusion (RRF, k=60):**
```python
score = 1 / (k + rank_fts5) + 1 / (k + rank_vec)
```

**Result:** Best of both worlds — exact matches + conceptual similarity

### Embedding Pipeline

```python
# 1. Generate embeddings (batch of texts)
embeddings = embedding_client.embed(texts)

# 2. Fallback chain (Gemini → local → hash)
if gemini_fails:
    if sentence_transformers_available:
        use_local_bge_small_en_v1_5()
    else:
        use_sha256_hash_fallback()

# 3. Store in sqlite-vec
conn.execute(
    "INSERT INTO symbol_embeddings VALUES (?, ?)",
    (symbol_id, embedding_vector)
)
```

**Model:** `BAAI/bge-small-en-v1.5` (384-dim, ~130MB, CPU-only)

---

## Layer 3: HybridMemoryManager (Orchestration)

**File:** `src/nexusagent/memory/hybrid_memory.py`

### Public API

```python
class HybridMemoryManager:
    def __init__(self, memory_dir: str) -> None:
        self.memory_dir = Path(memory_dir)
        self.file_memory = FileMemory(memory_dir)
        self.index = HybridMemoryIndex(memory_dir)
    
    def remember(self, text: str, metadata: dict) -> str:
        """Write memory + index. Returns memory ID."""
        
    def get_memory_context(self, query: str, limit: int = 5) -> str:
        """Search + format for prompt injection."""
        
    def flush(self) -> None:
        """Pre-compaction save (persist pending writes)."""
        
    def close(self) -> None:
        """Resource cleanup (DB connections, locks)."""
```

### Session Integration

```python
# Session.__init__()
self.hybrid_memory = HybridMemoryManager(self.memory_dir)
self.hybrid_memory.initialize()

# Session.send() — before agent invocation
memory_context = self.hybrid_memory.get_memory_context(user_message)
messages.insert(0, SystemMessage(content=memory_context))

# Session.send() — after agent response
asyncio.create_task(self._run_extraction())  # Fire-and-forget
```

---

## Layer 4: Background Processes

### MemoryExtractor (`extraction.py`)

**Purpose:** Auto-extract memories from conversations using regex patterns.

**Patterns:**
- **Decisions:** "we decided", "chose X over Y", "going with"
- **Preferences:** "I prefer", "always do X", "never do Y"
- **Errors:** "bug fixed", "root cause was", "preventing Y"
- **Entities:** Project names, people, tools, files

**Execution:** Fire-and-forget asyncio task after each conversation turn.

---

### DreamCycle (`dream.py`)

**Purpose:** 4-phase consolidation daemon (runs every N turns, default 20).

**Phases:**
1. **Scan:** Identify patterns, contradictions, redundancies
2. **Patterns:** Cluster related memories, detect themes
3. **Consolidate:** Merge duplicates, resolve contradictions
4. **Trim:** Remove low-confidence or obsolete memories

**Execution:** Scheduled via `DreamCycle.schedule(every_n_turns=20)`

---

### CompactionPipeline (`compaction.py`)

**Purpose:** Hierarchical context compression for long conversations.

**Strategies (graduated by conversation length):**
- **Tier 1:** Remove redundant/low-value turns
- **Tier 2:** Summarize middle sections, keep recent turns
- **Tier 3:** Extract decisions/preferences, discard conversation
- **Tier 4:** Full summary + memory extraction

**Integration:** Called in `Session.send()` when context exceeds threshold.

---

### MemoryRateLimiter (`rate_limiter.py`)

**Purpose:** Token-bucket rate limiting to prevent API overload.

**Limits:**
- **Writes:** 30/minute (embedding API calls)
- **Searches:** 60/minute (SQLite queries)

**Implementation:**
```python
class MemoryRateLimiter:
    def __init__(self, writes_per_min=30, searches_per_min=60):
        self.write_tokens = writes_per_min
        self.search_tokens = searches_per_min
        # ... token bucket logic
```

---

## Data Flow

```
User Message
    ↓
[HybridMemoryManager.get_memory_context(query)]
    ↓
FTS5 scan → sqlite-vec search → RRF fusion → Top-5 memories
    ↓
Format as SystemMessage → Inject into agent prompt
    ↓
Agent generates response
    ↓
[HybridMemoryManager.remember(response_metadata)]
    ↓
Write to FileMemory (.md file) → Auto-commit to Git
    ↓
Index embeddings (async) → Update sqlite-vec
    ↓
[MemoryExtractor.extract() — fire-and-forget]
    ↓
Regex patterns → Create observation memories
    ↓
[DreamCycle — every 20 turns]
    ↓
4-phase consolidation → Update memories
```

---

## Workspace Isolation

### Memory Scopes

| Scope | Location | Use Case |
|-------|----------|----------|
| **SHARED** | `~/.nexusagent/memory/` | Cross-project knowledge |
| **ISOLATED** | `~/.nexusagent/sessions/{id}/memory/` | Session-specific |
| **SCOPED** | `~/Workspaces/{project}/.nexusagent/memory/` | Project-specific |

### Configuration

```yaml
# ~/.nexusagent/config/nexusagent.yaml
agent:
  memory_scope: "scoped"  # | "isolated" | "shared"
  memory_workspace: "~/Workspaces/NexusAgent"  # For SCOPED scope
```

---

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| **Write + Index** | <100ms | Embedding generation dominates |
| **Keyword Search** | <10ms | FTS5 BM25 |
| **Semantic Search** | <50ms | sqlite-vec cosine |
| **Hybrid Search** | <100ms | RRF fusion overhead |
| **Dream Cycle** | 2-5s | LLM-based pattern detection |
| **Compaction** | 1-10s | Depends on conversation length |

---

## Failure Modes & Recovery

### Embedding API Unavailable

**Fallback Chain:**
1. Gemini API (primary)
2. Local `sentence-transformers` (BAAI/bge-small-en-v1.5)
3. SHA256 hash (degenerate, but preserves dedup)

**Recovery:** When API restores, background re-embedding job runs.

### Git Auto-Commit Fails

**Behavior:** Warning logged, memory still written to file.

**Recovery:** Manual `git add && git commit` or next successful write.

### sqlite-vec Extension Missing

**Fallback:** Degrade to FTS5-only search (keyword matching).

**Recovery:** Install `sqlite-vec` package, rebuild index.

---

## Testing Strategy

### Unit Tests (150 tests)

- `test_memory_files.py` — Frontmatter parsing, git ops
- `test_memory_index.py` — FTS5, sqlite-vec, RRF fusion
- `test_hybrid_memory.py` — Orchestrator integration
- `test_extraction.py` — Regex pattern matching
- `test_compaction.py` — Graduated strategies
- `test_dream.py` — 4-phase consolidation

### Integration Tests (58 tests)

- `test_session_memory.py` — Session owns HybridMemoryManager
- `test_memory_cross_agent.py` — Workspace isolation
- `test_memory_contradiction.py` — Conflict detection
- `test_e2e_production.py` — Full recall + extraction loop

### Performance Tests

- `test_index_performance.py` — FTS5 <10ms, vec <50ms
- `test_rate_limiter.py` — Token bucket enforcement

---

## Future Enhancements

### Short-term (Next Sprint)

1. **Memory Linking** — Auto-detect `related` field connections
2. **Contradiction Detection** — Flag conflicting memories for review
3. **Provenance Tracking** — Track memory lifecycle (created→modified→consolidated)

### Medium-term (Next Month)

4. **Cross-Agent Memory Bus** — NATS-based distributed memory sharing
5. **SessionLite for Workers** — Lightweight memory for subagents
6. **Dashboard UI** — Visualize memory graph, search, edit

### Long-term (Next Quarter)

7. **Product Extraction** — `nexus-memory` as standalone PyPI package
8. **Pluggable Embeddings** — Support Ollama, Cohere, custom models
9. **Temporal Queries** — "What did we decide last week about X?"

---

## References

- **SPEC-001:** Memory Self-Management (`docs/specs/SPEC-001-memory-self-management.md`)
- **SPEC-002:** Workspace-Scoped Memory (`docs/specs/SPEC-002-workspace-scoped-memory.md`)
- **SPEC-003:** Session Memory Integration (`docs/specs/SPEC-003-session-memory-integration.md`)
- **SPEC-004:** Consolidation Daemon (`docs/specs/SPEC-004-consolidation-daemon.md`)
- **SPEC-005:** Two-Tier Compaction (`docs/specs/SPEC-005-two-tier-compaction.md`)
- **SPEC-006:** Git-Backed Memory (`docs/specs/SPEC-006-git-backed-memory.md`)
- **Plan:** Memory System Overhaul (`docs/plans/2026-07-22-memory-system-overhaul.md`)
- **Audit Synthesis:** Memory System Audit (`docs/plans/2026-07-22-memory-system-audit-synthesis.md`)

---

**Last Updated:** 2026-06-28  
**Maintained By:** OWL (Lucien)  
**Test Coverage:** 208 tests passing