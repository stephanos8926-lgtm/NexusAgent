# Memory System Overhaul — Research-Backed Implementation Plan

> **Version:** 2.0 (Research-Enhanced)
> **Date:** 2026-07-22
> **Author:** OWL (Lucien)
> **Research Sources:** Letta (MemGPT) codebase analysis, Mem0/Zep/LangMem comparison, hybrid RAG best practices, context compression research (CMV, ContextWeaver, PicoClaw, parallel compaction)
> **Reference Implementation:** `/tmp/letta-reference` (Letta AI, Apache 2.0)

---

## Table of Contents

1. [Research Synthesis](#1-research-synthesis)
2. [Reference Implementation Analysis](#2-reference-implementation-analysis)
3. [Architecture Decision Records](#3-architecture-decision-records)
4. [Specifications](#4-specifications)
5. [Implementation Plan](#5-implementation-plan)
6. [Audit Reports](#6-audit-reports)

---

## 1. Research Synthesis

### 1.1 Memory Architecture Landscape (2026)

| System | Architecture | Strengths | Weaknesses | Best For |
|--------|-------------|-----------|------------|----------|
| **Mem0** | Vector + graph + KV, auto-extraction | Fastest integration, 26% over OpenAI | Graph behind paywall, no temporal | Managed memory layer |
| **Letta** | 3-tier (core/recall/archival), agent-managed | Most flexible, self-editing, git-backed | Full agent runtime, not drop-in | Long-running stateful agents |
| **Zep** | Temporal knowledge graph (Graphiti) | Bi-temporal facts, 63.8% LongMemEval | Cloud-focused, deprecated CE | Temporal reasoning at scale |
| **LangMem** | LangGraph-native, 3-type taxonomy | Deep LangGraph integration | 59.8s p95 latency, LangChain-only | LangGraph batch processing |

**Key Insight:** The emerging pattern is a **consolidation layer** that routes different memory types to appropriate stores: working memory in context, semantic preferences in vector store, entity relationships in graph, procedural knowledge in git-backed blocks.

### 1.2 RAG & Hybrid Search Best Practices

| Practice | Evidence | Recommendation |
|----------|----------|----------------|
| Hybrid search (BM25 + vector) | 7-31% NDCG lift over dense-only | **Required** — NexusAgent already has FTS5 + sqlite-vec |
| Reciprocal Rank Fusion (k=60) | Zero tuning, production default | **Use RRF** for fusion, not weighted average |
| Cross-encoder reranking | 100-400ms, highest precision gain | **Phase 2** — add after basic hybrid works |
| Chunk size: 256-512 tokens | Optimal for both sparse and dense | **Use 256 tokens** with 15% overlap |
| Hierarchical chunking | Parent/child for context preservation | **Consider** for large memory files |

### 1.3 Context Compression Techniques

| Technique | Source | Key Innovation |
|-----------|--------|----------------|
| **DAG-based state management** | CMV paper (arXiv 2602.22402) | Preserves full fidelity, removes structural bloat |
| **Parallel compaction** | arXiv 2605.23296 | Block-based, async background, predictable summary volume |
| **ContextWeaver** | arXiv 2604.23069 | Dependency-structured memory, preserves reasoning chains |
| **Two-tier compaction** | PicoClaw | Leaf compaction (every turn, sync) + condensed (background, async) |
| **AdmTree** | arXiv 2512.04550 | Adaptive semantic tree, dynamic segmentation |

**Key Insight:** Two-tier compaction is the production pattern. Tier 1: lightweight observation masking every turn. Tier 2: heavy LLM-based summarization in background when context exceeds 75% capacity.

### 1.4 Letta Reference Implementation — Key Patterns

Analyzed at `/tmp/letta-reference`:

**Pattern 1: Memory as First-Class Object**
```python
# Letta passes Memory through agent state, not as a global
class AgentState:
    memory: Memory  # Core memory blocks (human, persona)
    recall_memory: ArchivalMemory  # Searchable history
    archival_memory: ArchivalMemory  # Vector store
```

**Pattern 2: Agent-Managed Memory**
```python
# Agent decides what to store/retrieve via tools
core_memory_append(label="human", content="User prefers...")
core_memory_replace(label="persona", old="...", new="...")
archival_memory_search(query="previous decisions")
```

**Pattern 3: Git-Backed Memory (MemFS)**
```python
# Memory is a git repo — every change is committed
# Enables full version history, diff, rollback
# ~/.letta/memfs/{org_id}/{agent_id}/repo.git/
```

**Pattern 4: Compile Pattern**
```python
# Clean separation between storage and prompt injection
memory.compile(tool_usage_rules, sources, max_files_open, llm_config)
# Returns a prompt string with memory blocks rendered
```

**Pattern 5: Block-Based Memory**
```python
# Memory is organized into labeled blocks
# human block: user preferences, persona block: agent personality
# Each block has a char limit to prevent context bloat
CORE_MEMORY_BLOCK_CHAR_LIMIT = 2000  # per block
```

---

## 2. Architecture Decision Records

### ADR-006: Memory System Architecture (Revised)

> **Status:** Revised v2
> **See:** `docs/adrs/0006-memory-session-integration.md`

**Key Decisions (updated with research):**

1. **Three-Tier Memory Model** (inspired by Letta)
   - **Core Memory** (always in context): NEXUS.md + workspace context + top-3 cross-session memories
   - **Recall Memory** (searchable): HybridMemoryIndex (FTS5 + sqlite-vec) with RRF fusion
   - **Archival Memory** (on-demand): Full conversation history in SQLite, retrievable via session_search

2. **Agent-Managed Memory** (inspired by Letta)
   - Agent auto-extracts observations after each turn (regex-first, LLM-optional)
   - Agent can consciously write memories via memory_write tool
   - Agent can search memories via memory_search tool

3. **Two-Tier Compaction** (inspired by PicoClaw + parallel compaction research)
   - **Tier 1 (every turn):** Observation masking — replace old tool outputs with stubs
   - **Tier 2 (background):** LLM-based summarization when context > 75% capacity

4. **Hybrid Search with RRF** (industry standard)
   - BM25 (FTS5) + dense vector (sqlite-vec) with RRF k=60 fusion
   - 70% vector / 30% keyword weight (existing in NexusAgent)

5. **Provenance Tracking** (essential for trust)
   - Every memory entry stores `source_session_id` and `derived_from`
   - Enables "show me where this was learned" audit trail

6. **Git-Backed Memory** (inspired by Letta MemFS)
   - Initialize git repo in each memory directory
   - Commit after every memory write
   - Enables full version history, diff, rollback

### ADR-007: Context Compression Strategy

> **Status:** New
> **Date:** 2026-07-22

**Decision:** Adopt two-tier compaction with observation masking (Tier 1) and background LLM summarization (Tier 2).

**Rationale:**
- Research shows parallel compaction reduces wall time by 40-60% vs sequential
- Observation masking is fast (no LLM call) and handles 80% of bloat
- Background summarization only triggers when needed (context > 75%)
- Fresh tail protection: last 32 messages never compacted

**Consequences:**
- Session history bounded by context window
- Agent can always recover original messages via session_search
- Predictable summary volume (configurable block size)

### ADR-008: Cross-Session Memory Strategy

> **Status:** New
> **Date:** 2026-07-22

**Decision:** Federated search with lazy discovery and caching.

**Rationale:**
- Cross-session memory is the #1 gap in competitive analysis
- Federated search (parallel across session dirs) is fast enough for session start
- Lazy discovery avoids blocking session creation
- Caching prevents re-discovery on every session for the same workspace

**Consequences:**
- Session startup adds ~200ms for memory recall (acceptable)
- Previous session memories injected as SystemMessage
- Workspace-scoped memories shared across all sessions for that project

---

## 3. Specifications

### SPEC-003: Session-Memory Integration (Revised)

> **Status:** Revised v2
> **See:** `docs/specs/SPEC-003-session-memory-integration.md`

**Key Changes from v1:**
- Task 1.1, 1.2, 1.4 removed (already implemented)
- Task 1.5 split into 1.5a (DB migration), 1.5b (query method), 1.5c (discovery)
- Added Task 1.7: Git-backed memory initialization
- Added Task 1.8: Two-tier compaction wiring

### SPEC-004: Consolidation Daemon (Revised)

> **Status:** Revised v2
> **See:** `docs/specs/SPEC-004-consolidation-daemon.md`

**Key Changes from v1:**
- Added file locking to prevent race conditions
- Added git commit after consolidation
- Added dry-run mode for safety
- Added health report with before/after metrics

### SPEC-005: Two-Tier Context Compaction

> **Status:** New
> **Date:** 2026-07-22

**Goal:** Implement two-tier compaction: observation masking (Tier 1) + background summarization (Tier 2).

**Tier 1 — Observation Masking (every turn, synchronous):**
- Replace tool outputs older than 5 turns with stubs: `[Tool output: {tool_name} — {summary}]`
- Keep all user/assistant messages verbatim
- No LLM call required (fast, <10ms)
- Handles 80% of context bloat

**Tier 2 — Background Summarization (async, when context > 75%):**
- Triggered when estimated tokens > 75% of context window
- Runs in background (doesn't block agent)
- Summarizes blocks of 16k tokens into ~2k token summaries
- Fresh tail protection: last 32 messages never summarized
- Source messages preserved in SQLite (recoverable via session_search)

**Files to modify:**
- `src/nexusagent/core/session/session.py` — Tier 1 in send(), Tier 2 trigger
- `src/nexusagent/memory/compaction.py` — Add two-tier logic
- `src/nexusagent/infrastructure/config.py` — Add compaction config

### SPEC-006: Git-Backed Memory

> **Status:** New
> **Date:** 2026-07-22

**Goal:** Initialize git repo in each memory directory for version history.

**Implementation:**
- `FileMemory.initialize()` creates `.git` repo if not exists
- After every `write_entry()`, commit with auto-generated message
- After every `delete_by_file()`, commit with deletion message
- Enables: `git log`, `git diff`, `git rollback`

**Config:**
- `memory_git_enabled: bool = True` (can be disabled for performance)
- `memory_git_auto_commit: bool = True`

---

## 4. Implementation Plan

### Phase 0: Foundation Fixes (Day 1)

| Task | Description | Est. LOC | Status |
|------|-------------|----------|--------|
| 0.1 | Fix config path bug (db_path) | 5 | TODO |
| 0.2 | Add `memory_dir` column to `SessionModel` + migration | 30 | TODO |
| 0.3 | Add `find_sessions_by_working_dir()` to `SessionRepository` | 20 | TODO |
| 0.4 | Add index on `working_dir` in sessions table | 5 | TODO |
| 0.5 | Add `memory_model`, `memory_git_enabled`, `compaction_tier2_threshold` config fields | 15 | TODO |
| 0.6 | Add `close()` to `HybridMemoryManager` | 10 | TODO |

### Phase 1: Session-Memory Wiring (Days 2-4)

| Task | Description | Est. LOC | Depends |
|------|-------------|----------|---------|
| 1.1 | Wire `HybridMemoryManager` into `Session.__init__()` (verify existing) | 0 | Phase 0 |
| 1.2 | Auto-recall memory context in `send()` (verify existing) | 0 | Phase 0 |
| 1.3 | Pre-compaction flush (verify existing) | 0 | Phase 0 |
| 1.4 | Wire `memory_dir` through server → agent → session (verify existing) | 0 | Phase 0 |
| 1.5 | Cross-session memory discovery (async, cached) | 80 | 0.2, 0.3 |
| 1.6 | Auto memory extraction (regex-based) | 60 | Phase 0 |
| 1.7 | Git-backed memory initialization | 30 | Phase 0 |
| 1.8 | Session.close() cleanup for hybrid_memory | 10 | Phase 0 |

### Phase 2: Two-Tier Compaction (Days 5-7)

| Task | Description | Est. LOC | Depends |
|------|-------------|----------|---------|
| 2.1 | Tier 1: Observation masking in send() | 40 | Phase 1 |
| 2.2 | Tier 2: Background summarization trigger | 60 | Phase 1 |
| 2.3 | Summary DAG for hierarchical compression | 100 | 2.2 |
| 2.4 | Fresh tail protection (last 32 messages) | 15 | 2.1 |
| 2.5 | Compaction config fields + CLI flags | 20 | Phase 0 |

### Phase 3: Consolidation Daemon (Days 8-10)

| Task | Description | Est. LOC | Depends |
|------|-------------|----------|---------|
| 3.1 | Dream cycle engine (4-phase) | 120 | Phase 1 |
| 3.2 | File locking for dream cycle | 20 | 3.1 |
| 3.3 | Git commit after consolidation | 10 | 3.1, 1.7 |
| 3.4 | `memory_dream` tool + CLI command | 40 | 3.1 |
| 3.5 | Cron integration | 20 | 3.4 |

### Phase 4: Provenance & Polish (Days 11-13)

| Task | Description | Est. LOC | Depends |
|------|-------------|----------|---------|
| 4.1 | Provenance tracking (source_session_id, derived_from) | 30 | Phase 1 |
| 4.2 | Memory health dashboard (CLI) | 40 | Phase 3 |
| 4.3 | End-to-end integration tests | 80 | All phases |
| 4.4 | Update docs (CODEBASE_MAP, SEMANTIC_INDEX, README) | 50 | All phases |

### Deferred (Not in v1)

| Feature | Reason | Target |
|---------|--------|--------|
| DAG-based context compression (LCM-style) | Current graduated compaction is good enough | v2 |
| LLM-based auto-extraction | Regex-based is sufficient for v1 | v2 |
| Cross-encoder reranking | Hybrid search with RRF is sufficient for v1 | v2 |
| Observation extraction (pattern detection) | No clear user value yet | v2 |
| Namespace scoping (user/agent/app) | Single-user deployment for now | v2 |

---

## 5. Audit Reports

### 5.1 Forward Audit (Partial — timed out at 600s)

**Status:** Incomplete due to timeout. Partial findings:
- All file paths in the plan exist and are writable
- All import references resolve correctly
- Test directories exist
- Code examples are syntactically valid Python

### 5.2 Reverse Audit (38 gaps found)

**Critical (7):**
1. `find_sessions_by_working_dir` does not exist in `SessionRepository`
2. `memory_dir` not stored in DB — cross-session discovery broken
3. `HybridMemoryManager.remember()` type mismatch (string vs enum)
4. `flush()` is async but plan's test doesn't await it
5. `SessionModel.memory_id` vs `memory_dir` confusion
6. No `ConsolidationEngine` class — Task 2.1 builds on nothing
7. `SummaryDAG` has no LLM integration — compression unimplementable as specified

**High (8):**
8. Missing `memory_dir` flow through `run_agent_task`
9. Singleton pattern inconsistency
10. No error handling for `initialize()` failure
11. Fire-and-forget extraction has no error reporting
12. `memory_dream` tool not specified in detail
13. `Session.close()` doesn't clean up `hybrid_memory`
14. No test for `memory_dir` default path construction
15. Import from compat shim, not direct module

**Medium (10):**
16-25. Various missing tests, performance concerns, doc gaps

**Low (13):**
26-38. Minor issues, typos, style

### 5.3 Adversarial Audit (6 show-stoppers)

**Show-Stoppers:**
1. **Plan claims work that's already done** (~40% vaporware)
2. **Missing DB method + column** for cross-session discovery
3. **`aiohttp` listed but not a dependency**
4. **Auto-extraction latency underestimated** by 10x
5. **Dream cycle race condition** with active sessions
6. **NATS bus integration completely unaddressed**

**Major Concerns:**
- N+1 SQLite queries in cross-session discovery
- Memory dir resolution inconsistency (WebSocket vs Session)
- No `memory_model` config field
- DAG has no eviction strategy (grows forever)
- `_build_session_summary()` accesses nonexistent `self._messages`

**Minimum Viable Scope (from adversarial audit):**
- Sprint 1: Fix foundation + cross-session (3 days)
- Sprint 2: Background maintenance (3 days)
- Sprint 3: Refine and test (4 days)
- **Total: 10 days** (down from 10-15)

---

## 6. Revised Estimate

| Phase | Days | Confidence | Key Risk |
|-------|------|-----------|----------|
| 0: Foundation | 1 | High | DB migration |
| 1: Session wiring | 3 | High | Cross-session discovery |
| 2: Two-tier compaction | 3 | Medium | Background summarization |
| 3: Dream daemon | 3 | Medium | File locking |
| 4: Polish | 3 | High | Integration testing |
| **Total** | **13** | **Medium** | |

---

## Appendix A: Research Sources

1. **Memory Architecture Comparison:** https://maidul-haque.vercel.app/blog/agent-memory-architectures-2026/
2. **Agent Long-Term Memory:** https://agentmarketcap.ai/blog/2026/04/08/agent-long-term-memory-architecture-letta-memgpt-langmem-zep

3. **Best AI Agent Memory Frameworks:** https://atlan.com/know/best-ai-agent-memory-frameworks-2026/

4. **Mem0 Paper:** https://arxiv.org/html/2504.19413v1

5. **Hybrid RAG:** https://atlan.com/know/hybrid-rag/

6. **Context Compression (CMV):** https://arxiv.org/html/2602.22402

7. **Parallel Compaction:** https://arxiv.org/html/2605.23296

8. **ContextWeaver:** https://arxiv.org/html/2604.23069

9. **AdmTree:** https://arxiv.org/html/2512.04550

10. **Letta Reference:** `/tmp/letta-reference` (cloned 2026-07-22)

## Appendix B: Reference Implementation Analysis

### Letta Memory Architecture (from `/tmp/letta-reference`)

**Core Classes:**
- `Memory` (schemas/memory.py) — Base memory class with blocks
- `BasicBlockMemory` — Editable memory with `core_memory_append`/`core_memory_replace`
- `ChatMemory` — Two default blocks: `human` and `persona`
- `LocalStorageBackend` — Git-backed filesystem storage

**Key Patterns:**
1. Memory is a **first-class object** in agent state (not global)
2. Agent **manages its own memory** via tools
3. **Git-backed** storage for version history
4. **Compile pattern** — clean separation between storage and prompt injection
5. **Block-based** memory with labeled sections and char limits

**Applicable to NexusAgent:**
- ✅ Three-tier model (core/recall/archival)
- ✅ Git-backed memory for version history
- ✅ Block-based memory for organized storage
- ✅ Compile pattern for prompt injection
- ❌ Agent-managed memory (NexusAgent uses auto-extraction)
- ❌ Full agent runtime (NexusAgent has its own agent loop)
