# Forward Audit — NexusAgent 2026-07-22

**Auditor:** OWL (plan-and-audit high mode)
**Scope:** Validate all specs/plans against actual codebase
**Specs Reviewed:** SPEC-001 through SPEC-006, memory-overhaul-plan.md, security-hardening-plan.md, tui-implementation-plan.md, version-handshake-plan.md, CODE_REVIEW_COMPREHENSIVE.md

---

## ✅ Verified Claims

| Spec/Plan | Claim | Status | Evidence |
|-----------|-------|--------|----------|
| SPEC-001 | HybridMemoryManager combines FileMemory + HybridMemoryIndex | ✅ | `src/nexusagent/memory/hybrid_memory.py:25-40` |
| SPEC-002 | FileMemory uses markdown with YAML frontmatter | ✅ | `src/nexusagent/memory/memory_files.py:50-80` |
| SPEC-003 | HybridMemoryIndex uses SQLite + sqlite-vec + RRF | ✅ | `src/nexusagent/memory/index/index.py:40-120` |
| SPEC-004 | CompactionPipeline has 4 graduated strategies | ✅ | `src/nexusagent/memory/compaction.py:50-200` |
| SPEC-005 | DreamCycle 4-phase consolidation | ✅ | `src/nexusagent/memory/dream.py:100-300` |
| SPEC-006 | MemoryExtractor regex-based auto-extraction | ✅ | `src/nexusagent/memory/extraction.py:30-150` |
| Memory Plan | SessionLite for worker memory | ✅ | `src/nexusagent/core/session/session_lite.py` |
| Memory Plan | NATS memory bus | ✅ | `src/nexusagent/memory/nats_bus.py` |
| Memory Plan | LLM extraction with fallback | ✅ | `src/nexusagent/memory/llm_extraction.py` |
| Memory Plan | Cross-agent inheritance | ✅ | `src/nexusagent/memory/cross_agent.py` |
| Security Plan | 13 critical/high fixes in 4 waves | ✅ | Commits 22ebf77, 462b43a, d52aa53, e6a1abf |
| TUI Plan | Widget-based architecture | ✅ | `src/nexusagent/interfaces/tui/app.py` (787L) |
| TUI Plan | Version preflight handshake | ✅ | `src/nexusagent/interfaces/cli.py:54-80` |
| Version Plan | importlib.metadata single source | ✅ | `src/nexusagent/version.py` |
| Version Plan | CLI preflight HTTP not NATS | ✅ | `src/nexusagent/interfaces/cli.py:54-80` |

---

## ⚠️ Corrections Needed

| Spec/Plan | Issue | Correction |
|-----------|-------|------------|
| Memory Plan | `SessionManager.get_or_create()` needs `memory_dir` param | Plan missed this parameter for workspace scoping |
| Memory Plan | `session_websocket()` must compute/pass workspace path | Currently hardcodes `working_dir="."` |
| Memory Plan | Cross-workspace search needs `workspace` param on `memory_search`/`memory_write` | Only `memory_read` has it |
| Memory Plan | `_get_memory_workspace()` should be config-based, not session-context | Current design couples to session |
| TUI Plan | Session init effort underestimated | 1h → 2h (complex state initialization) |

---

## 🔍 Missed Items

| Area | Missing |
|------|---------|
| FileMemory | `.gitignore` creation not in `initialize()` |
| Memory Tools | `memory_search` and `memory_write` lack `workspace` param |
| Workspace Discovery | Mechanism for `workspace="all"` unspecified |

---

## ❌ Errors

| File | Spec Claim | Reality |
|------|------------|---------|
| `src/nexusagent/core/graph.py:125-127` | Plan says error handling fixed | Still returns `plan_approved: True` on exception |
| `src/nexusagent/server/websocket.py:35` | Security plan says API key removed from URL | Still accepts `?api_key=` |
| `src/nexusagent/memory/index/index.py` | Optimization plan says async search used | Still calls `search_sync()` from async path |
| `src/nexusagent/core/session/manager.py:82-88` | Correctness plan says timeout added | No timeout on spin loop |
| `src/nexusagent/core/agent.py:52-53` | Security plan says marker only on detection | Always prepends UNTRUSTED marker |
| `src/nexusagent/server/server.py` | Security plan says TLS added | No TLS config |

---

## Summary

**15 verified claims** ✅
**5 corrections needed** ⚠️
**3 missed items** 🔍
**6 errors (unfixed critical issues)** ❌

**Verdict:** Specs are accurate for implemented features, but **6 critical security/correctness issues from 2026-06-16 remain unfixed**. Plans must incorporate these fixes before new work.