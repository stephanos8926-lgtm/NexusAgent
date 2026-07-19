# v3 Security & Trust Overhaul — Phased Implementation Plan

**Date:** 2026-07-14
**Mode:** HIGH (12-phase plan-and-audit)
**Spec Sources:**
- `docs/specs/immutable-tool-cache-v3.md`
- `docs/specs/typed-trust-boundaries-v3.md`
- `docs/specs/audit-synthesis-v3.md`
**Audit Sources:**
- `docs/specs/audits/forward-audit-v2.md` — All claims verified ✅
- `docs/specs/audits/reverse-audit-v2.md` — 3 🔴, 3 🟠, 5 🟡, 3 🔵 gaps
- `docs/specs/audits/adversarial-registry-v2.md` — 1 🔴, 2 🟠, 3 🟡, 3 🔵 vulns

---

## Executive Summary

6-phase implementation overhauling tool registry immutability and prompt injection defense. Total estimated effort: **~6.5 days**.

| Phase | Title | Files | Est. | Dependencies |
|-------|-------|-------|------|--------------|
| 1 | ToolInfo Immutability + ToolRegistry | 3 | 1.25d | None |
| 2 | Agent Integration — Lazy Loading + MCP Await | 1 | 0.5d | Phase 1 |
| 3 | Registration Wiring — freeze() + prune() | 1 | 0.25d | Phase 2 |
| 4 | Trust Foundations — TrustLevel, TrustedContent, AnomalyScorer | 2 | 1.5d | None |
| 5 | Trust Integration — Wiring into Session, MCP, PromptLoader | 5 | 2.0d | Phases 1, 4 |
| 6 | Tests + Documentation | 6-8 | 1.0d | All above |

**Rollback:** Each phase committed independently. Full rollback via `git revert <phase-commit>`.

---

## Phase 1: ToolInfo Immutability + ToolRegistry

**Spec:** `immutable-tool-cache-v3.md`
**Effort:** ~1.25 day
**Risk:** Low (mechanical refactor, no behavioral change)

### File Manifest

| File | Change | ± Lines |
|------|--------|---------|
| `tools/registry/types.py` | Mark `ToolInfo` as `@dataclass(frozen=True)`. Keep existing fields; add no new fields yet (trust/provenance come in Phase 5). | +1 |
| `tools/registry/core.py` | Extract mutable `_REGISTRY` into `ToolRegistry` class. Add `_registry_proxy()`. Keep `register_tool()` as facade over `registry.register()`. Add `get_snapshot()` with graceful `KeyError` handling. Add `prune()` with `keep_version` support. Add `WeakValueDictionary` for agent refs. | -30 +150 |
| `tools/registry/__init__.py` | Export `registry` singleton, `ToolRegistry` class. Add `registry.current` to `__all__`. Remove `_REGISTRY` from direct export (keep via proxy only). | +5 |

### Task List

1. **`tools/registry/types.py`**: Add `frozen=True` to `@dataclass` decorator on `ToolInfo`.
2. **`tools/registry/core.py`**: Implement `ToolRegistry` class with:
   - `_lock: RLock`, `_snapshots: dict[int, MappingProxyType]`, `_latest_version: int`, `_pending: dict[str, ToolInfo]`, `_refs: WeakValueDictionary`
   - `version` property
   - `current` property → returns latest snapshot
   - `register(name, info)` → adds to pending
   - `freeze()` → atomically creates snapshot, returns version
   - `get_snapshot(version=None)` → returns snapshot or None (graceful KeyError)
   - `prune(keep_version)` → removes old snapshots
3. **`tools/registry/core.py`**: Implement `_registry_proxy()` with full `MutableMapping` override (update, setdefault, pop, popitem, clear all raise TypeError).
4. **`tools/registry/__init__.py`**: Update exports for `registry` singleton, `ToolRegistry`, `registry.current`.

### Test Plan

| File | Tests |
|------|-------|
| `tests/tools/registry/test_tool_registry.py` | (NEW 15) register+freeze, snapshot immutability, concurrent RLock safety, version monotonic, prune keeps last N, empty freeze no-op, MCP batch atomicity, graceful get_snapshot (empty before first freeze, KeyError for pruned versions), RegistryProxy TypeError on mutation |

### Rollback
```bash
git revert HEAD  # Single commit safe
```

---

## Phase 2: Agent Integration — Lazy Loading + MCP Await

**Spec:** `immutable-tool-cache-v3.md`
**Effort:** ~0.5 day
**Risk:** Medium (changes agent init flow; test after commit)

### File Manifest

| File | Change | ± Lines |
|------|--------|---------|
| `core/agent.py` | Remove `_ROLE_TOOLS` dict, version counter, `_refresh_role_tools_if_needed()`. Add per-agent snapshot in `__init__`. `await _ensure_mcp_tools_loaded()` (blocking). Implement `_ensure_tools_registered()` with `threading.RLock()` double-checked locking. Implement `_init_role_tools()`. Restore `_ws_memory_dir`. | -40 +30 |

### Task List

1. **`core/agent.py`**: Near top — ensure `_ensure_tools_registered()` uses `RLock` (already done by merged PR #1; verify thread-safety).
2. **`core/agent.py`**: In `Agent.__init__()` — change fire-and-forget MCP loading to `await _ensure_mcp_tools_loaded()`:
   ```python
   # BEFORE:
   _ = loop.create_task(_ensure_mcp_tools_loaded())
   
   # AFTER:
   await _ensure_mcp_tools_loaded()
   ```
   **Note:** This requires `Agent.__init__()` to be `async def`. Verify all callers.
3. **`core/agent.py`**: In `Agent.__init__()` — add per-agent snapshot logic:
   ```python
   self._snapshot = registry.current
   self._version = registry.version
   self._tools = [
       self._snapshot[name].func
       for name in manifest if name in self._snapshot
   ]
   ```
4. **`core/agent.py`**: Verify `_ws_memory_dir` still correctly defined at module bottom.

### Test Plan

| File | Tests |
|------|-------|
| `tests/core/test_agent_tools.py` | (NEW 10) agent captures correct snapshot, version tracking across MCP loads, role filtering from frozen snapshot, MCP tools loaded before agent uses them, concurrent agent creation thread-safe |

### ⚠️ Breaking Change: Agent.__init__ becomes async

This requires updating ALL callers of `Agent(...)` to `await Agent(...)`. Impact analysis needed.

**Callers to update:**
- `core/session.py` — Session creation path
- `core/worker.py` — Worker pool agent creation
- `interfaces/cli.py` — CLI agent
- Tests

### Rollback
```bash
git revert HEAD  # But verify all callers revert cleanly
```

---

## Phase 3: Registration Wiring — freeze() + prune()

**Spec:** `immutable-tool-cache-v3.md`
**Effort:** ~0.25 day
**Risk:** Low

### File Manifest

| File | Change | ± Lines |
|------|--------|---------|
| `tools/register_all.py` | Call `registry.freeze()` after static registration batch. Call `registry.freeze()` + `registry.prune()` after MCP discovery. | +5 |

### Task List

1. **`tools/register_all.py`**: After the main `TOOL_SPECS` registration loop:
   ```python
   registry.freeze()  # version 1
   ```
2. **`tools/register_all.py`**: In `register_mcp_tools()`, after MCP discovery loop:
   ```python
   registry.freeze()  # version N+1
   registry.prune(max(0, registry.version - 2))  # keep last 2 snapshots
   ```

### Rollback
```bash
git revert HEAD  # Safe
```

---

## Phase 4: Trust Foundations — TrustLevel, TrustedContent, AnomalyScorer

**Spec:** `typed-trust-boundaries-v3.md`
**Effort:** ~1.5 day
**Risk:** Low-Medium (additive, new file + config)

### File Manifest

| File | Change | ± Lines |
|------|--------|---------|
| `core/trust.py` | **(NEW)** `TrustLevel` enum, `TrustedContent` frozen dataclass, `AnomalyScorer` class with multi-signal scoring, bypass mitigation, `TrustConfig` dataclass. | ~180 |
| `infrastructure/config.py` | Add `trust:` config section with `enabled`, `anomaly_threshold`, `min_score`, signal weights, `single_signal_boost_threshold`, `single_signal_boost_multiplier`. Consolidate existing anomaly/injection fields. | +30 |

### Task List

1. **`core/trust.py`**: Implement `TrustLevel(IntEnum)`.
2. **`core/trust.py`**: Implement `TrustedContent` frozen dataclass with `to_dict()` / `from_dict()`.
3. **`core/trust.py`**: Implement `AnomalyScorer`:
   - `_pattern_score()` — weighted regex match
   - `_entropy_score()` — Shannon entropy computation
   - `_length_score()` — 3σ from historical mean per tool
   - `_instruction_density()` — imperative verb ratio
   - `score()` — fusion with early exit + single-signal boost trigger
   - Thread-safe `_length_history` via `Lock`
4. **`core/trust.py`**: Implement `TrustConfig` dataclass.
5. **`infrastructure/config.py`**: Add `trust:` section to `ConfigSchema`. Consolidate any existing anomaly/injection fields.

### Test Plan

| File | Tests |
|------|-------|
| `tests/core/test_trust.py` | (NEW 30) AnomalyScorer: each signal in isolation, known injection patterns, entropy/length/density outliers, combined score, early exit, empty text, non-ASCII, single-signal boost trigger, fine-tuned thresholds. TrustedContent: serialization, deserialization, immutability. TrustConfig: defaults. |

### Rollback
```bash
git revert HEAD  # Pure additive, safe
```

---

## Phase 5: Trust Integration — Wiring into Session, MCP, PromptLoader, ToolInfo

**Spec:** `typed-trust-boundaries-v3.md`
**Effort:** ~2.0 day
**Risk:** Medium (cross-cutting changes, test thoroughly)

### File Manifest

| File | Change | ± Lines |
|------|--------|---------|
| `tools/registry/types.py` | Add `trust: TrustLevel` and `provenance: str` fields to `ToolInfo`. Already frozen from Phase 1. | +2 |
| `tools/register_all.py` | Tag MCP tools with `trust=TOOL_EXTERNAL`, strip trust claims from descriptions. Extend `_RESERVED_PREFIXES`. Add `_INJECTION_TOOL_NAMES` blocklist with substring/edit-distance matching. | +20 |
| `core/agent.py` | Replace `_detect_injection()`/`sanitize_tool_output()` with `annotate_tool_output()`. Keep old names as deprecated wrappers. Add `get_trust_level()` mapping from tool name → ToolInfo.trust. | -25 +35 |
| `core/session/session.py` | Wire `annotate_tool_output()` into tool result handler. Add trust schema to system prompt. Add cross-turn `additional_kwargs` serialization/deserialization for all relevant BaseMessage types. | +40 |
| `infrastructure/prompt_loader.py` | Add `_load_file_with_trust()` with AnomalyScorer. All initial @file content is `USER_FILE`. | +25 |

### Task List

1. **`tools/registry/types.py`**: Add `trust: TrustLevel = TrustLevel.TOOL_INTERNAL` and `provenance: str = ""` fields to `ToolInfo`. Already frozen — new fields must have defaults.
2. **`tools/register_all.py`**: 
   - In `register_mcp_tools()`: hardcode `trust=TOOL_EXTERNAL`, strip trust claims from descriptions
   - Extend `_RESERVED_PREFIXES` with semantic injection patterns
   - Add `_INJECTION_TOOL_NAMES` blocklist
3. **`core/agent.py`**: 
   - Implement `annotate_tool_output(text, tool_name, trust_level) → TrustedContent`
   - Wrap old `sanitize_tool_output()` / `_detect_injection()` as deprecated callers
   - Add `get_trust_level(tool_name) → TrustLevel`
4. **`core/session/session.py`**: 
   - In tool result handler: call `annotate_tool_output()` before creating `ToolMessage`
   - Serialize `TrustedContent` to `additional_kwargs["trust"]`
   - On context load: deserialize `TrustedContent`, prepend warning if `anomaly_score > threshold`
   - Add trust schema to system prompt
5. **`infrastructure/prompt_loader.py`**: 
   - Implement `_load_file_with_trust(path) → TrustedContent`
   - Default all @file content to `USER_FILE`

### Test Plan

| File | Tests |
|------|-------|
| `tests/core/test_trust_integration.py` | (NEW 15) annotate_tool_output, additional_kwargs round-trips, trust survives context reload, MCP trust enforcement |
| `tests/tools/test_mcp_security.py` | (NEW 10) MCP shadow detection (exact, substring, edit-distance), description sanitization, INJECTION_TOOL_NAMES, registrar trust override |
| `tests/core/test_session_trust.py` | (NEW 8) Tool result handler calls annotate_tool_output, TrustedContent serialized/deserialized, system prompt trust schema |
| `tests/infrastructure/test_prompt_loader_trust.py` | (NEW 5) _load_file_with_trust returns USER_FILE, AnomalyScorer applied, path validation |

### Rollback
```bash
git revert HEAD  # But verify all integration points reverted
```

---

## Phase 6: Tests + Documentation

**Spec:** All v3 specs
**Effort:** ~1.0 day
**Risk:** Low

### File Manifest

| File | Change |
|------|--------|
| `tests/tools/registry/test_tool_registry.py` | (NEW) Phase 1 + Phase 3 tests |
| `tests/core/test_agent_tools.py` | (NEW) Phase 2 tests |
| `tests/core/test_trust.py` | (NEW) Phase 4 tests |
| `tests/core/test_trust_integration.py` | (NEW) Phase 5 tests |
| `tests/tools/test_mcp_security.py` | (NEW) Phase 5 tests |
| `tests/core/test_session_trust.py` | (NEW) Phase 5 tests |
| `tests/infrastructure/test_prompt_loader_trust.py` | (NEW) Phase 5 tests |
| `docs/plans/v3-security-trust-overhaul-v1.md` | This document (master plan) |

### Task List

1. Write all test files listed above
2. Run full test suite: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=short`
3. Run lint: `ruff check src/ tests/`
4. Update CHANGELOG with v3 changes
5. Update AGENTS.md with architecture changes

### Test Baseline
```bash
# Record baseline BEFORE Phase 1
PYTHONPATH=src python3 -m pytest tests/ -q --tb=line --no-header | tail -3
# Expected: 680 pass, 11 pre-existing fail
```

### Rollback
```bash
git revert HEAD  # Safe — tests don't affect runtime
```

---

## Dependency Graph

```
Phase 1 (ToolInfo/Registry) ──→ Phase 2 (Agent Integration) ──→ Phase 3 (Registration Wiring)
                                                                       │
Phase 4 (Trust Foundations) ──→ Phase 5 (Trust Integration) ←──────────┘
                                       │
                                       ↓
                                 Phase 6 (Tests + Docs)
```

Phases 1 and 4 are independent and could run in parallel.

---

## Sign-off Checklist (HIGH Mode)

Before implementation begins:

- [x] Spec written (v3 specs — DONE)
- [x] Forward audit (v2 — DONE)
- [x] Reverse audit (v2 — DONE)
- [x] Adversarial audits (registry v2 — DONE; trust v2 — DONE via subagent)
- [x] Audit synthesis (v3 — DONE)
- [ ] **User sign-off** ← YOU ARE HERE
- [ ] TDD: Tests written FIRST per phase
- [ ] Lint + dead code check per phase
- [ ] Documentation updated (Phase 6)
- [ ] Manual validation on workstation
- [ ] Rollback plan documented (included per phase above)
- [ ] Push to GitHub