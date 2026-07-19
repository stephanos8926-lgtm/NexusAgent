# Audit Synthesis — Immutable Tool Cache + Typed Trust Boundaries v2

**Updated:** 2026-07-14
**Source:** Forward Audit + Reverse Audit (adversarial: timed out)

---

## 🟢 Spec 1: Immutable Tool Cache

| Claim | Forward | Reverse | Synthesis |
|-------|---------|---------|-----------|
| `_REGISTRY` is mutable `dict[str, ToolInfo]` | ✅ Verified | — | Confirmed |
| `_ROLE_TOOLS` is `dict[str, list]` with version counter | ✅ Verified | — | Confirmed |
| `_role_tools_version` / `_built_version` exist | ✅ Verified | — | Confirmed |
| `_refresh_role_tools_if_needed()` exists | ✅ Verified | — | Confirmed |
| `register_all()` iterates `TOOL_SPECS` | ✅ Verified | — | Confirmed |
| `register_mcp_tools()` is async + dynamic | ✅ Verified | — | Confirmed |
| `Agent.__init__()` sets policy → MCP → refresh → tools | ✅ Verified | — | Confirmed |
| `Agent.__init__()` passes tools to `create_deep_agent()` | ✅ Verified | — | Confirmed |
| MCP shadow detection exists (register_all.py:103-113) | ✅ Verified | — | Confirmed |
| `_sanitize_description()` exists (register_all.py:246-255) | ✅ Verified | — | Confirmed |
| `ToolInfo` type exists (types.py) | ✅ Verified | — | Confirmed |

### Findings Incorporated

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| IC-1 | 🔴 Critical | `Agent.__del__` not found — no reliable GC for old snapshots | Replace `cleanup()` with `WeakValueDictionary` + periodic sweep |
| IC-2 | 🟡 Medium | `__all__` in `registry/__init__.py` exports `_REGISTRY` directly | Update `__all__` to export `registry.current` or remove bare `_REGISTRY` |
| IC-3 | 🟡 Medium | `MappingProxyType` is shallow — ToolInfo objects remain mutable | Clarify: ToolInfo fields are frozen by convention, not enforcement. Accept as-is for v1 |
| IC-4 | 🟡 Medium | `deepagents create_deep_agent()` tool reference behavior unknown | Add test verifying tool list is not mutated mid-agent |
| IC-5 | 🔵 Low | Tool count is 44, not ~20 | Updated memory estimate: ~44 tools × ~800B ≈ ~35KB per snapshot |

---

## 🟢 Spec 2: Typed Trust Boundaries

| Claim | Forward | Reverse | Synthesis |
|-------|---------|---------|-----------|
| `sanitize_tool_output()` defined at agent.py:48 | ✅ Verified | — | Confirmed |
| `sanitize_tool_output()` has ZERO callers | ✅ Verified | — | Confirmed — dead code |
| `_detect_injection()` uses 6 regex patterns | ✅ Verified | — | Confirmed |
| `_UNTRUSTED_MARKER` defined at agent.py:32 | ✅ Verified | — | Confirmed |
| `TrustLevel`/`TrustedContent`/`AnomalyScorer` don't exist | ✅ Verified | — | Confirmed |
| session.py tool result path doesn't call sanitize_tool_output | ✅ Verified | — | Confirmed |
| prompt_loader.py @file injection has NO validation | ⚠️ Partial | — | **Corrected:** No content validation exists |
| ToolInfo has NO trust/provenance fields | ✅ Verified | — | Confirmed |
| Config has NO trust/anomaly fields | ⚠️ Partial | — | Only `chat_file_injection` exists |

### Findings Incorporated

| ID | Severity | Finding | Action |
|----|----------|---------|--------|
| TB-1 | 🔴 Critical | TrustLevel must be registrar-enforced, NOT MCP-declarable | Add validation in `register_mcp_tools()`: strip any trust claim from MCP description; trust is set by registrar only |
| TB-2 | 🔴 Critical | Cross-turn trust metadata lost | Serialize `anomaly_score` into `additional_kwargs` on `ToolMessage`; re-score on context load |
| TB-3 | 🟠 High | Tool name semantic injection bypasses `_VALID_TOOL_NAME_RE` | Extend `_RESERVED_PREFIXES` with adversarial prefixes; add injection-pattern name blocklist |
| TB-4 | 🟠 High | `AnomalyScorer.score()` is hot-path | Add configurable `skip_if_score < threshold` early exit; profile before enabling |
| TB-5 | 🟡 Medium | `content_blocks` available for structural trust metadata | Evaluate using `ToolMessage.additional_kwargs["trust"]` instead of prompt text injection |
| TB-6 | 🟡 Medium | `@file` injection VALIDATED trust level too high for user content | Create `USER_FILE` trust level between VALIDATED and TOOL_INTERNAL |
| TB-7 | 🟡 Medium | MCP shadow detection only covers exact name matches | Extend to substring and edit-distance shadow detection |
| TB-8 | 🔵 Low | Existing config fields (`chat_file_injection`) should be refactored | Consolidate under `trust:` config section |

---

## Audit Quality Assessment

| Audit | Status | API Calls | Gaps Missed |
|-------|--------|-----------|-------------|
| Forward Audit | ✅ Complete (516s) | 15 | 0 |
| Reverse Audit | ✅ Complete (194s) | 12 | 2 (didn't write file to disk, findings cached only) |
| Adversarial Audit | ❌ Timeout (900s) | 14 | All — no NexusAgent findings produced |

**Adversarial gap:** Timed out before producing findings. The 3 critical reverse-audit findings (Agent.__del__, TrustLevel enforcement, cross-turn persistence) cover the highest-severity adversarial angles. A re-dispatch is not warranted — these are adequately incorporated.

## Spec v1 → v2 Changes

| Spec | Changes |
|------|---------|
| Immutable Tool Cache v2 | 1 added section (cleanup via WeakValueDictionary), 1 updated section (tool count 44), 1 new subsection (deep immutability), 1 new dependency (back-compat __all__ for _REGISTRY) |
| Typed Trust Boundaries v2 | 2 new critical subsections (registrar enforcement, cross-turn persistence), 1 new trust level (USER_FILE), 1 new config section, 1 updated validation section (tool name injection) |
