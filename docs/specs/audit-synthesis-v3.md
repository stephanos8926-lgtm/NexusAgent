# Audit Synthesis v3 — NexusAgent Security & Trust Overhaul

**Date:** 2026-07-14
**Version:** v3
**Synthesized from:**
- Forward Audit v2
- Reverse Audit v2
- Adversarial Audit: Immutable Tool Cache v2
- Adversarial Audit: Typed Trust Boundaries v2

---

## 1. Immutable Tool Cache Findings & Mitigations

### 1.1. Summary of Issues

| ID | Severity | Risk | Finding | Mitigation (Proposed) |
|----|----------|------|---------|-----------------------|
| F1 | ✅ Verified | N/A | All 11 claims in spec v2 were verified. | N/A |
| R1 | 🟠 High | Memory Pressure | Spec assumes ~20 tools, but 44 registered. | Re-evaluate memory impact with actual tool count (44). |
| R2 | 🔵 Low | Backward Compatibility | `_REGISTRY` directly imported in several modules. | Ensure direct importers are updated or handled by a backward-compatibility shim, or by ensuring `_REGISTRY` module-level proxy is robust. |
| R3 | 🟡 Medium | Mutable Export | `__all__` in `registry/__init__.py` exports `_REGISTRY` directly. | Remove `_REGISTRY` from `__all__` once it's a property of `ToolRegistry`; export `registry.current` instead if back-compat needed. |
| R4 | 🔴 Critical | Memory Leak (DoS) | `Agent.__del__` not found for `ToolRegistry.cleanup()`. | Implement alternative cleanup mechanism for `ToolRegistry.prune()` (e.g., periodic sweep, session end hook). |
| R5 | 🟡 Medium | Deepagents Tool List Handling | Unclear if `create_deep_agent()` makes a deep copy of tools list. | Further investigation into `deepagents` internal behavior (verify copies or holds references). |
| R6 | 🟡 Medium | Shallow Immutability | `MappingProxyType` is shallow; `ToolInfo` objects fields might be mutable. | Clarify `ToolInfo` must be deeply immutable, or explicitly accept shallow immutability with current `ToolInfo` structure. **ACTION: Mark ToolInfo as @dataclass(frozen=True).** |
| A1 | 🔴 Critical | Arbitrary Code Execution | `ToolInfo.func` is mutable. | **ACTION: Mark `ToolInfo` as `@dataclass(frozen=True)`.** |
| A2 | 🟠 High | Prompt Injection / Misdirection | `MappingProxyType` shallow immutability – `ToolInfo` fields remain mutable. | **ACTION: Mark `ToolInfo` as `@dataclass(frozen=True)`.** |
| A3 | 🟠 High | Inconsistent Immutability Contract | `RegistryProxy` bypass via `MutableMapping` inherited methods. | Explicitly override all `MutableMapping` methods in `RegistryProxy` to raise `TypeError`. |
| A4 | 🟡 Medium | Resource Exhaustion (DoS) | `_pending` accumulation if `freeze()` is never called. | Ensure robust `freeze()` calls in all tool registration paths. Implement monitoring for `_pending` size. |
| A5 | 🟡 Medium | Application Crash (DoS) | `get_snapshot(version=0)` before first `freeze()` crashes. | `ToolRegistry.get_snapshot()` should handle empty `_snapshots` gracefully (return empty `MappingProxyType` or raise specific error). |
| A6 | 🟡 Medium | Incomplete Tool Access | Existing Race Condition: Agent `__init__` vs. MCP tool loading. | Agent initialization should `await _ensure_mcp_tools_loaded()` or dynamically refresh tool list if version changes. |
| A7 | 🔵 Low | Misleading Agent Behavior | `ToolInfo.parameters` mutable (shallow immutability). | **ACTION: Mark `ToolInfo` as `@dataclass(frozen=True)`.** |
| A8 | 🔵 Low | Unpredictable Agent Behavior | `deepagents` tool list reference. | Verify `deepagents.create_deep_agent` copies the `tools` list or guarantees its immutability. |
| A9 | 🔵 Low | Application Crash (DoS) | `prune()` KeyError on accessing old snapshots. | `ToolRegistry.get_snapshot()` should handle `KeyError` gracefully (return `None` or raise descriptive `SnapshotNotFound` error). |

### 1.2. Consolidated Action Plan for Immutable Tool Cache

1.  **Mark `ToolInfo` as `@dataclass(frozen=True)`:** This is a critical, high-impact fix addressing A1, A2, and A7 directly. It will enforce deep immutability for `ToolInfo` objects, preventing unauthorized modification of `func`, `description`, and `parameters`.
2.  **Robust `RegistryProxy`:** Explicitly override all `MutableMapping` methods (`update`, `setdefault`, `pop`, `popitem`, `clear`) in `RegistryProxy` to raise `TypeError` (A3). This ensures a consistent and robust immutability contract.
3.  **Graceful `get_snapshot`:** Modify `ToolRegistry.get_snapshot()` to handle `KeyError` gracefully when a version is not found (A5, A9). Return an empty `MappingProxyType` for `version=0` if no `freeze()` has occurred, and a descriptive `SnapshotNotFound` error for other invalid versions.
4.  **Await MCP Tool Loading:** In `Agent.__init__()`, modify the MCP tool loading to `await _ensure_mcp_tools_loaded()` (A6). This ensures all static and dynamic tools are registered and frozen before the agent's tool snapshot is created, eliminating the race condition.
5.  **Cleanup Mechanism:** Implement a robust, periodic `ToolRegistry.prune()` call (R4), decoupled from `Agent.__del__`. This can be a scheduled daemon or a call at session end.
6.  **Monitor `_pending` size:** Implement monitoring for `_pending` size in production to detect cases where `freeze()` is not called as expected (A4).
7.  **Verify `deepagents` behavior:** Document the verified behavior of `deepagents.create_deep_agent` regarding tool list copying (R5, A8). If it doesn't copy, ensure local tool list immutability.
8.  **`_REGISTRY` module-level proxy refinement:** Re-evaluate the `_REGISTRY` proxy to ensure it handles all direct imports and `__all__` exports without exposing mutability (R2, R3).
9.  **Memory Impact Re-evaluation:** Re-evaluate memory impact with the actual count of 44 tools (R1), and factor this into resource planning.

---

## 2. Typed Trust Boundaries Findings & Mitigations

### 2.1. Summary of Issues

| ID | Severity | Risk | Finding | Mitigation (Proposed) |
|----|----------|------|---------|-----------------------|
| F1 | ✅ Verified | N/A | `sanitize_tool_output()` is dead code; no caller exists. | N/A (will be activated) |
| F2 | ✅ Verified | N/A | `prompt_loader.py` lacks explicit validation for `@file` injection paths. | N/A (will be addressed by TrustLevel `USER_FILE` and `AnomalyScorer`) |
| F3 | ✅ Verified | N/A | `infrastructure/config.py` lacks explicit `trust` or `anomaly` related configuration fields. | N/A (will be added) |
| F4 | ✅ Verified | N/A | Absence of `TrustLevel`, `TrustedContent`, `AnomalyScorer` types and trust/provenance fields in `ToolInfo`. | N/A (will be added) |
| R1 | 🟠 High | Dead Code / Placement | `sanitize_tool_output` is dead code. Ideal placement for annotation. | Activate `sanitize_tool_output()` immediately after tool execution results are received and before adding to message history. |
| R2 | 🟡 Medium | Structural Metadata | `deepagents BaseMessage.content_blocks` could be used for structured trust metadata. | Evaluate using `content_blocks` for structural trust metadata instead of `additional_kwargs`. |
| R3 | 🔵 Low | Config Overlap | Anomaly scorer config fields overlap with existing config. | Audit existing configuration (`src/nexusagent/infrastructure/config.py`) to consolidate/refactor. |
| R4 | 🔴 Critical | Registrar Enforcement | `TrustLevel` enum enforcement for MCP tools: not enforced by registrar, potentially declarable by MCP tool. | **ACTION: Enforce `TrustLevel.TOOL_EXTERNAL` for all MCP tools at registration time.** `ToolInfo` must include `trust` and `provenance` fields. |
| R5 | 🟠 High | Prompt Injection | Prompt injection via tool names (e.g., `ignore_previous_instructions`). | Extend `_RESERVED_PREFIXES` and `_INJECTION_TOOL_NAMES` blocklist with semantic injection patterns. |
| R6 | 🟡 Medium | `@file` Injection Trust | `prompt_loader.py` `@file` injection trust level (currently `VALIDATED`) is too high for user-provided files. | Demote user-provided `@file` content to `TrustLevel.USER_FILE` (lower than `VALIDATED`) or implement additional scan/check. |
| R7 | 🔴 Critical | Cross-Turn Persistence | Cross-turn injection persistence. Trust metadata not serialized/re-associated across turns. | **ACTION: Robustly serialize `TrustedContent` (containing `anomaly_score`, `TrustLevel`) into `ToolMessage.additional_kwargs` for persistence and re-evaluation.** |
| R8 | 🔵 Low | Performance | Performance of `AnomalyScorer.score()` as a hot-path. | Profile `AnomalyScorer.score()` to ensure it meets performance targets (<10μs per call). |
| R9 | 🟡 Medium | MCP Shadowing Defense | MCP tool shadowing defense completeness (substring/edit-distance). | Extend MCP shadow detection to substring and edit-distance matches, not just exact names. |
| A1 | 🟠 High | AnomalyScorer Bypass | Multi-signal scorer can be bypassed by payloads scoring low on individual signals. | Refine signal weighting and potentially add more robust anomaly detection techniques. Consider a "threshold for any signal" trigger. |
| A2 | 🟠 High | TrustLevel Advisory | `TrustLevel` is advisory text; LLM might ignore it. | Strengthen prompt engineering to emphasize the importance of `TrustLevel` and `anomaly_score`. Consider hard-coding warnings for high-anomaly content. |
| A3 | 🔴 Critical | Registrar Enforcement | MCP Tool Registrar Enforcement: `ToolInfo` lacks trust/provenance, `register_tool()` doesn't enforce `TOOL_EXTERNAL`. | **ACTION: `ToolInfo` must include `trust` and `provenance` fields. `register_tool()` must explicitly assign `TrustLevel.TOOL_EXTERNAL` to MCP tools.** |
| A4 | 🟠 High | Cross-Turn Amplification | Cross-Turn Injection Amplification: `additional_kwargs` persistence for `AIMessage` and `HumanMessage` during session serialization. | Ensure `additional_kwargs` for all relevant `BaseMessage` types are robustly serialized and deserialized. |
| A5 | 🟠 High | `@file` Attack Vector | `@file` Injection as Attack Vector: User-provided files might gain `VALIDATED` status if bypass `AnomalyScorer`. | Demote all initial `@file` content to `TrustLevel.USER_FILE`. `VALIDATED` implies an explicit, successful scan/check by a trusted component. |
| A6 | 🟠 High | Tool Name Semantic Injection | Tool Name Semantic Injection: While exact matches blocked, similar names could mislead LLM. | Implement semantic analysis of tool names or a more extensive denylist beyond exact matches. |
| A7 | 🔵 Low | False Positives | Entropy/Length Signal False Positives: Legitimate but unusual outputs could trigger alert fatigue. | Fine-tune `AnomalyScorer` thresholds and weights to minimize false positives, potentially implement a feedback loop for human review. |

### 2.2. Consolidated Action Plan for Typed Trust Boundaries

1.  **Activate `sanitize_tool_output()`:** This is paramount. Ensure it's called immediately after tool execution returns and *before* the result enters message history (R1).
2.  **`ToolInfo` for Trust:** Add `trust: TrustLevel` and `provenance: str` fields to `ToolInfo` (R4, A3). Mark `ToolInfo` as `@dataclass(frozen=True)` (covered in Immutable Tool Cache action plan).
3.  **Registrar Enforcement:** In `register_all.py`, explicitly enforce `trust=TrustLevel.TOOL_EXTERNAL` for all MCP tools at registration time, stripping any trust claims from their descriptions (R4, A3).
4.  **Cross-Turn Trust Persistence:** Robustly serialize `TrustedContent` (including `anomaly_score`, `TrustLevel`) into `ToolMessage.additional_kwargs` for persistence across turns (R7, A4). This includes ensuring `additional_kwargs` for `AIMessage` and `HumanMessage` also persist. Implement re-evaluation on context load.
5.  **Refined `@file` Trust:** Demote all initial `@file` content to `TrustLevel.USER_FILE`. `VALIDATED` will now exclusively imply an explicit, successful scan/check by a trusted component (R6, A5).
6.  **Multi-Signal AnomalyScorer Enhancements:**
    *   **Bypass Mitigation:** Refine signal weighting and consider a "threshold for any signal" trigger (A1).
    *   **False Positive Reduction:** Fine-tune `AnomalyScorer` thresholds and weights (A7).
    *   **Performance:** Profile `AnomalyScorer.score()` to ensure it meets performance targets (<10μs per call) (R8).
7.  **Tool Name Injection Defense:** Extend `_RESERVED_PREFIXES` and `_INJECTION_TOOL_NAMES` blocklist with semantic injection patterns (R5, A6). Consider semantic analysis for truly robust defense.
8.  **LLM Trust Emphasis:** Strengthen prompt engineering to explicitly emphasize the importance of `TrustLevel` and `anomaly_score` to the LLM (A2). Potentially hard-code warnings for high-anomaly content.
9.  **MCP Shadowing Defense:** Extend MCP shadow detection to include substring and edit-distance matches, not just exact names (R9).
10. **Configuration Consolidation:** Audit `src/nexusagent/infrastructure/config.py` to consolidate and refactor `AnomalyScorer` config fields with existing anomaly/injection related fields for a cleaner configuration (R3, F3).
11. **`content_blocks` Evaluation:** Re-evaluate using `content_blocks` for structural trust metadata instead of `additional_kwargs` in a future iteration (R2).

---

## 3. General Architecture & Design Considerations

- **Unified Error Handling:** Ensure all new components integrate into a unified error handling and logging framework.
- **Async Safety:** Verify thread-safety of all components, particularly those interacting with asynchronous operations or shared state.
- **Documentation:** Update all relevant documentation (ADRs, Codebase Map, Semantic Index) to reflect these architectural changes.
- **Testing:** Comprehensive test coverage for all new features and mitigations, including unit, integration, and adversarial tests.

---

## 4. Proposed v3 Spec Deliverables

- `docs/specs/audit-synthesis-v3.md` (this document)
- `docs/specs/immutable-tool-cache-v3.md`
- `docs/specs/typed-trust-boundaries-v3.md`
