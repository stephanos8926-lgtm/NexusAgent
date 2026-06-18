# NexusAgent Memory System — Comprehensive Analysis & Recommendations

> **Date:** 2026-06-18
> **Author:** OWL (Lucien)
> **Scope:** Cross-session memory, context compression, consolidation, and competitive analysis

---

## 1. Executive Summary

NexusAgent's memory system has a solid foundation — file-based canonical storage, hybrid search (FTS5 + sqlite-vec), and a clean separation between session-scoped and global memories. However, compared to state-of-the-art systems like Letta, Mem0, Zep, and LangMem, there are significant gaps in **cross-session continuity**, **automatic consolidation**, **context compression**, and **agent self-management**.

This report identifies **18 specific gaps**, benchmarks against **6 competing systems**, and provides **12 actionable recommendations** organized by effort and impact.

---

## 2. Current Architecture Audit

### 2.1 Directory Structure

```
~/.nexusagent/
├── nexus.db              ← SQLite DB (config says data/nexus.db — MISMATCH)
├── NEXUS.md              ← Global base prompt
├── memory/               ← Global memory bank
│   ├── bank/             ← Typed memory pages (world/experience/opinion/observation)
│   ├── entities/         ← Entity pages
│   └── YYYY-MM-DD.md     ← Daily logs
├── sessions/             ← Per-session data
│   └── {session_id}/
│       └── memory/       ← Session-scoped memory (isolated per session)
│           ├── bank/
│           ├── entities/
│           ├── .memory/  ← HybridMemoryIndex (SQLite)
│           └── MEMORY.md  ← Session index
├── config/               ← Config directory
├── data/                 ← Data directory (empty — nexus.db is at root!)
├── auth/                 ← Auth keys
├── hooks/                ← Hook scripts
├── skills/               ← Skill definitions
└── worktrees/            ← Worktree state
```

### 2.2 Config Path Bug

**CRITICAL:** `ServerConfig.db_path` defaults to `"data/nexus.db"` and `load_config()` resolves relative paths against `nexus_home` (`~/.nexusagent/`). So the config system expects the DB at `~/.nexusagent/data/nexus.db`. But the actual `nexus.db` file is at `~/.nexusagent/nexus.db` (root level). This means either:
1. The config was never actually loaded from a file (using Pydantic defaults), OR
2. The DB was moved manually and the config wasn't updated

**Fix:** Either move `nexus.db` to `data/nexus.db` or update the config.

### 2.3 Session Memory Lifecycle

**Creation:**
1. `SessionManager.get_or_create(session_id, working_dir, memory_dir)` creates a new `Session`
2. `Session.__init__()` creates `HybridMemoryManager(memory_dir)` where `memory_dir` defaults to `~/.nexusagent/sessions/{session_id}/memory`
3. `HybridMemoryManager.initialize()` creates the directory structure and `HybridMemoryIndex` (SQLite at `.memory/index.sqlite`)
4. `FileMemory.initialize()` creates `bank/`, `entities/`, and `MEMORY.md`

**Indexing:**
- `memory_write()` → `FileMemory.write_entry()` writes to `bank/*.md` + updates `MEMORY.md` index
- `HybridMemoryManager.remember()` calls `write_entry()` then `async_index_file()` for vector embedding
- The index is lazy — files are indexed when written, not on session start

**Retrieval:**
- `memory_search()` → `HybridMemoryManager.search()` → `HybridMemoryIndex.search()` (async hybrid: vector + keyword)
- `memory_get()` → reads specific file from bank/
- Results are scoped to the session's `memory_dir` only

**Cross-session: DOES NOT EXIST**
- Each session has its own isolated `memory_dir`
- No mechanism to search across sessions
- No mechanism to inherit memories from previous sessions
- No mechanism to promote session memories to global memory

### 2.4 How Context is Injected

At the start of each session turn:
1. `Session.send()` calls `_load_system_prompt()` → loads NEXUS.md from CWD + home
2. `_build_context_injection()` → environment context (time, user, git, tools)
3. `hybrid_memory.get_memory_context()` → retrieves relevant memories from session's `HybridMemoryManager`
4. All three are combined as `SystemMessage`s prepended to the conversation

**The gap:** Step 3 only searches the **current session's** memory. Previous sessions are invisible.

---

## 3. Competitive Analysis

### 3.1 Letta (formerly MemGPT)

**Architecture:** Memory-first agent harness with two-tier memory:
- **Core memory** (always in context): persona + human blocks, like RAM
- **Archival memory** (searchable): file-based MemFS, git-backed, like disk

**Key innovations:**
- **MemFS**: All memory is a git-backed filesystem. Every change is committed. Full version history.
- **Self-editing**: Agent can rewrite its own memory blocks using `rethink_memory()` tool
- **Sleep-time compute**: Background "dream" subagents that consolidate memory during idle periods
- **Cross-session by design**: All conversations with the same agent share the same MemFS. No session isolation.

**Benchmark:** 94.8% on DMR (Deep Memory Retrieval), outperforming MemGPT's 93.4%

**What we should adopt:**
- Git-backed memory for version history and auditability
- Sleep-time consolidation daemon (periodic background reflection)
- Always-loaded core memory blocks (persona, user info, project context)
- Agent self-editing capability

### 3.2 Mem0

**Architecture:** Managed memory layer with automatic extraction and consolidation.

**Key innovations:**
- **4-scope model**: user_id, agent_id, app_id, run_id — prevents cross-scope leakage
- **Write-time deduplication**: LLM-powered conflict resolution before storing
- **Multi-signal retrieval**: semantic + BM25 + entity matching in parallel
- **Temporal reasoning**: Time-aware retrieval for queries about current/past/future state
- **Memory compression engine**: Automatically condenses chat history into compact memories
- **Graph variant (Mem0^g)**: Knowledge graph for relational memory, 2% higher accuracy

**Benchmarks:** 26% improvement over OpenAI on LLM-as-a-Judge, 91% lower p95 latency vs full-context

**What we should adopt:**
- 4-scope model (we only have session-scoped vs global — missing user/agent/app scoping)
- Write-time LLM-powered deduplication (we only have hash-based exact dedup)
- Multi-signal retrieval (we have vector + keyword, but no entity matching)
- Temporal reasoning in search

### 3.3 Zep (Graphiti)

**Architecture:** Temporal knowledge graph for agent memory.

**Key innovations:**
- **Bi-temporal facts**: Every fact has `valid_from` and `valid_until` — can query "what was true on date X"
- **Provenance**: Every fact traces back to its source episode
- **Observations**: Pattern extraction across sessions (not just facts, but derived insights)
- **Context Block assembly**: Automatically assembles prompt-ready context from graph traversal
- **Sub-200ms retrieval**: Optimized for production latency

**Benchmarks:** 18.5% accuracy improvement on LongMemEval, 48.2% improvement on temporal reasoning

**What we should adopt:**
- Bi-temporal facts (we added the fields but don't use them in search/query)
- Provenance tracking (which session/memory derived each fact)
- Observation extraction (pattern detection across sessions)
- Context Block assembly (smart context budgeting)

### 3.4 LangMem

**Architecture:** Memory management SDK for LangGraph agents.

**Key innovations:**
- **Dual-path memory**: "Hot path" (agent consciously saves) + "Background" (automatic extraction)
- **Namespace scoping**: Hierarchical namespaces (user, team, app, session)
- **Memory managers**: Background process that extracts, consolidates, and updates memories
- **Prompt optimization**: Memories can update the agent's own system prompt (procedural memory)
- **Conflict resolution**: LLM-powered reconciliation when new info contradicts old

**What we should adopt:**
- Dual-path memory (conscious + automatic extraction)
- Background memory manager (runs between sessions)
- Procedural memory (agent can update its own prompt based on learnings)
- Namespace scoping beyond just session/global

### 3.5 Auto-Dreamer

**Architecture:** Learned offline memory consolidator.

**Key innovations:**
- **Region rewriting**: Treats a selected memory region as read-only evidence, synthesizes fresh compact replacement
- **Trained with downstream task reward**: Consolidation is optimized for actual task performance
- **Two-timescale**: Fast per-session writing + slow cross-session consolidation

**Key insight:** Learned consolidation outperforms fixed prompted pipelines on ALFWorld, ScienceWorld, WebArena

### 3.6 Hermes LCM (Lossless Context Management)

**Architecture:** DAG-based context compression that never loses a message.

**Key innovations:**
- **Hierarchical summary DAG**: Depth-0 (specifics) → Depth-1 (arc) → Depth-2 (narrative)
- **Fresh tail protection**: Recent N messages never compacted
- **Lossless pointers**: Every summary links to source messages, recoverable via `lcm_expand`
- **Three-level escalation**: If summarization doesn't reduce enough, escalate to more aggressive strategy
- **Cache-aware compaction**: Backs off when prompt cache hit rate is high
- **Agent tools**: `lcm_grep`, `lcm_expand`, `lcm_describe`, `lcm_expand_query` for navigating compacted history

**What we should adopt:**
- Hierarchical summary DAG for session history
- Lossless compaction (summaries + pointers, not replacement)
- Agent tools for navigating compacted history
- Fresh tail protection

---

## 4. Gap Analysis

### Critical Gaps (must fix)

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| 1 | **No cross-session memory** — Each session is isolated. Agent forgets everything between sessions. | 🔴 Critical | 2-3 days |
| 2 | **No automatic memory extraction** — Agent must consciously call `memory_write()`. No background extraction from conversations. | 🔴 Critical | 2-3 days |
| 3 | **No consolidation daemon** — No dream/sleep-time process. Memories accumulate without pruning or merging. | 🔴 Critical | 2-3 days |
| 4 | **Config path bug** — `nexus.db` at root but config expects `data/nexus.db` | 🔴 Critical | 5 min |
| 5 | **No context compression** — Session history grows unbounded. No hierarchical summarization. | 🔴 High | 3-5 days |
| 6 | **No bi-temporal search** — Fields exist but search doesn't filter by valid_from/until | 🔴 High | 1-2 days |

### Important Gaps (should fix)

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| 7 | **No provenance tracking** — Can't trace which session/memory derived each fact | 🟠 High | 1 day |
| 8 | **No observation extraction** — No pattern detection across sessions | 🟠 High | 2-3 days |
| 9 | **No namespace scoping** — Only session/global. No user/agent/app scoping. | 🟠 Medium | 1-2 days |
| 10 | **No procedural memory** — Agent can't update its own prompt based on learnings | 🟠 Medium | 1-2 days |
| 11 | **No git-backed memory** — No version history of memory changes | 🟠 Medium | 1 day |
| 12 | **No entity resolution** — "Steven" ≠ "Steven Page" ≠ "sysop" | 🟠 Medium | 2 days |

### Nice-to-Have Gaps

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| 13 | **No context block assembly** — No smart token-budgeted context construction | 🟡 Low | 1-2 days |
| 14 | **No memory quality scoring in search** — Quality field exists but doesn't affect ranking | 🟡 Low | 0.5 days |
| 15 | **No multi-signal retrieval** — Missing entity matching in search fusion | 🟡 Low | 1 day |
| 16 | **No memory linking** — No `related` field between memories | 🟡 Low | 0.5 days |
| 17 | **No table of contents for session history** — No hierarchical markers or bookmarks | 🟡 Low | 1-2 days |
| 18 | **No human-readable session archive** — No compiled conversation summaries for human review | 🟡 Low | 1-2 days |

---

## 5. Recommendations

### 5.1 Immediate (this week)

**R1: Fix config path bug**
- Move `~/.nexusagent/nexusagent.yaml` to reference correct DB path, OR
- Move `nexus.db` to `data/nexus.db`

**R2: Implement cross-session memory search**
- Add `memory_search(cross_session=True)` parameter
- When enabled, search across ALL session memory dirs + global memory
- Use the existing `HybridMemoryIndex.search()` but with a merged index or federated search

**R3: Add session memory inheritance**
- At session start, inject top-N relevant memories from previous sessions
- Use `PromptConfig.session_history_count` (already exists, default 5) to control how many
- Build a session summary from previous session memories and inject as context

### 5.2 Short-term (next 2 weeks)

**R4: Implement automatic memory extraction**
- Hook into `on_message` and `on_tool_call` events
- After each agent turn, extract salient facts using LLM
- Store extracted facts as `observation` type memories
- This is the "background" path from LangMem

**R5: Implement consolidation daemon (dream service)**
- Periodic background process (every 24h or after N new sessions)
- 4-phase cycle (from Claude Code's auto-dream):
  1. Scan memory directory, read MEMORY.md, skim topic files
  2. Search recent session transcripts for high-value patterns
  3. Merge new facts into durable memory files, delete contradicted notes
  4. Trim index back under length budget
- Sandboxed: can only write to memory files, never source code

**R6: Implement hierarchical context compression**
- Adopt LCM's DAG-based approach for session history
- Depth-0: specific decisions and technical details
- Depth-1: conversation arc and outcomes
- Depth-2: durable narrative and milestone timeline
- Fresh tail protection: last N messages never compacted
- Agent tools: `session_search`, `session_expand`, `session_describe`

**R7: Add bi-temporal search**
- Filter memories by `valid_from`/`valid_until` in `HybridMemoryIndex.search()`
- Support queries like "what was true about X on date Y"
- Invalidate old facts when new contradictory facts are added

### 5.3 Medium-term (next month)

**R8: Add provenance tracking**
- Every memory entry stores `source_session_id` and `derived_from` fields
- Enables "show me the full conversation where this was learned"
- Required for auditability and trust

**R9: Add observation extraction**
- Background process that analyzes memory patterns
- Extracts insights like "User prefers X in 80% of cases" or "Project Y uses pattern Z"
- Stores as `observation` type with `derived_from` links to source memories

**R10: Add namespace scoping**
- Extend beyond session/global to: user_id, agent_id, app_id, session_id
- Prevents cross-user/cross-agent memory leakage
- Required for multi-user deployments

**R11: Add procedural memory**
- Agent can update its own system prompt based on learnings
- Stored as special `procedure` type memories
- Injected into system prompt at session start

**R12: Add git-backed memory**
- Initialize git repo in each memory directory
- Commit after every memory write
- Enables full version history, diff, and rollback

---

## 6. Architecture Vision

### Target Architecture (6 months)

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT SESSION                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Core Memory  │  │  Session DAG │  │  Context Block   │  │
│  │  (always in   │  │  (hierarchical│  │  (assembled for  │  │
│  │   context)    │  │   summaries)  │  │   this turn)     │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                  │                    │             │
│  ┌──────▼──────────────────▼────────────────────▼─────────┐  │
│  │              MEMORY ORCHESTRATOR                       │  │
│  │  • Cross-session search (federated)                    │  │
│  │  • Bi-temporal filtering                               │  │
│  │  • Multi-signal fusion (vector + keyword + entity)     │  │
│  │  • Quality-weighted ranking                            │  │
│  │  • Token-budgeted context assembly                     │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │              STORAGE LAYER                             │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  │  │
│  │  │ Session Mem  │  │  Global Mem  │  │  User Mem   │  │  │
│  │  │ (ephemeral)  │  │  (persistent)│  │ (persistent)│  │  │
│  │  │ git-backed   │  │  git-backed  │  │ git-backed  │  │  │
│  │  └─────────────┘  └──────────────┘  └─────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  Hybrid Index (FTS5 + sqlite-vec + entity graph) │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              BACKGROUND DAEMON                         │  │
│  │  • Auto-extraction (after each turn)                   │  │
│  │  • Consolidation (dream cycle, every 24h)              │  │
│  │  • Entity resolution (continuous)                      │  │
│  │  • Observation extraction (weekly)                     │  │
│  │  • Health monitoring (continuous)                      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow at Session Start

```
1. User connects → Session created with working_dir
2. Load NEXUS.md from working_dir + global
3. Build environment context (time, user, git, tools)
4. Search CROSS-SESSION memories for relevant context
   - Query: recent conversation summary + working_dir context
   - Search: global bank + previous session banks + user bank
   - Filter: bi-temporal (valid now), quality score > threshold
   - Rank: multi-signal fusion, quality-weighted
   - Assemble: token-budgeted context block
5. Inject: core memory + cross-session context + environment
6. Begin conversation with full context
```

### Data Flow During Session

```
1. User message received
2. Agent processes with full context
3. Agent calls tools (memory_write, memory_search, etc.)
4. AFTER each turn (hook):
   a. Extract salient facts → auto-memories
   b. Update session DAG (compact if needed)
   c. Update entity graph
5. Response returned to user
```

### Data Flow Between Sessions (Dream Cycle)

```
1. Trigger: 24h elapsed OR 5 new sessions
2. Scan all memory directories
3. Read recent session transcripts
4. Extract patterns and insights
5. Merge duplicates, resolve conflicts
6. Prune stale entries (TTL expired, low quality)
7. Update entity pages
8. Rebuild search indices
9. Generate health report
10. Commit all changes (git-backed)
```

---

## 7. Implementation Roadmap

| Phase | What | Duration | Priority |
|-------|------|----------|----------|
| 0 | Fix config path bug | 5 min | P0 |
| 1 | Cross-session search + inheritance | 2-3 days | P0 |
| 2 | Auto memory extraction (hooks) | 2-3 days | P0 |
| 3 | Consolidation daemon (dream) | 2-3 days | P0 |
| 4 | Hierarchical context compression (LCM-style) | 3-5 days | P1 |
| 5 | Bi-temporal search | 1-2 days | P1 |
| 6 | Provenance tracking | 1 day | P1 |
| 7 | Observation extraction | 2-3 days | P1 |
| 8 | Namespace scoping | 1-2 days | P2 |
| 9 | Procedural memory | 1-2 days | P2 |
| 10 | Git-backed memory | 1 day | P2 |
| 11 | Entity resolution | 2 days | P2 |
| 12 | Context block assembly | 1-2 days | P3 |

**Total estimated effort:** 20-30 days

---

## 8. Key Design Decisions

### 8.1 Session Isolation vs. Cross-Session Sharing

**Decision:** Keep session-isolated memory as the default, but enable cross-session search when explicitly requested or at session start for context inheritance.

**Rationale:** Session isolation prevents context pollution. But the agent needs to "remember" across sessions to be useful. The solution is a federated search that queries across all sessions but ranks by relevance and recency.

### 8.2 File-Based vs. Database Storage

**Decision:** Keep files as the canonical source (current design), but add a unified search index that spans all memory directories.

**Rationale:** Files are human-readable, git-backed, and debuggable. The SQLite index is derived and rebuildable. This is the right approach. We just need to extend it to span multiple directories.

### 8.3 Automatic vs. Manual Memory

**Decision:** Dual-path. Agent can consciously write memories (manual), AND the system automatically extracts memories from conversations (automatic).

**Rationale:** LangMem's research shows both paths are needed. Manual for important facts the agent consciously decides to remember. Automatic for capturing details the agent might not think to save.

### 8.4 Consolidation Strategy

**Decision:** Periodic background daemon (dream cycle) + write-time deduplication.

**Rationale:** Write-time dedup prevents bloat at the source. Periodic consolidation handles the long-term health (merging, pruning, extracting patterns). Both are needed.

---

## 9. Conclusion

NexusAgent's memory system has the right foundation but lacks the cross-session continuity, automatic extraction, and intelligent consolidation that modern agent memory systems provide. The good news: the architecture is clean enough that these can be added incrementally without breaking changes.

The highest-impact changes are:
1. **Cross-session search** — agent remembers across sessions
2. **Auto-extraction** — memories created without conscious effort
3. **Consolidation daemon** — automatic memory health maintenance
4. **Hierarchical context compression** — LCM-style DAG for session history

These four changes would put NexusAgent on par with Letta, Mem0, and Zep in terms of memory capabilities.
