# Category 1: Security & Input Safety — Implementation Plan (rev 1)

## Goal
Harden NexusAgent’s authentication, authorization, logging hygiene, and prompt-injection boundaries so the runtime can operate without credential leakage, unauthorized destructive actions, or prompt manipulation.

## Current Context
- `websocket.py:77` logs the raw API key on auth failure — **credential leak**
- `pool.py` logs POL escalation error messages and worker descriptions that may contain task/user data
- `routes.py:130` logs raw NATS exception objects
- `task_store.py:80` `delete_task` has no authz check
- `memory_files.py:575` `delete_by_file` has no authz check
- `refinement.py:386-390` builds LLM prompts by concatenating untrusted memory content without sanitization or system boundary framing
- `worker.py` accepts NATS tasks without owner/authz validation; `_handle_cancel` logs untrusted input verbatim

## Proposed Approach
Fix security issues in 4 waves:
1. **Wave 1 — Credential/secret logging hygiene**: redact sensitive data from logs
2. **Wave 2 — Authz on destructive ops**: guard delete endpoints
3. **Wave 3 — Prompt injection defense**: sanitize and boundary-frame LLM prompt assembly
4. **Wave 4 — Worker trust boundary**: add task ownership/cancel authz and sanitize worker logs

## Step-by-Step Plan

### Wave 1: Credential/Secret Logging Hygiene
- [ ] **W1.1** `src/nexusagent/server/websocket.py`
  - Replace `logger.warning(f"WS auth failed for key={header_key}: {e}")` with redacted key logging
  - Ensure no other paths log raw API keys, tokens, or bearer credentials
- [ ] **W1.2** `src/nexusagent/core/worker/pool.py`
  - Redact task descriptions/user data from POL escalation logs
  - Redact worker execution context logs if they contain sensitive metadata
- [ ] **W1.3** `src/nexusagent/server/routes.py`
  - Replace raw NATS exception logging with sanitized message/log-level check
  - Ensure no request/response payloads are logged verbatim

### Wave 2: Authz on Destructive Ops
- [ ] **W2.1** `src/nexusagent/core/task/task_store.py`
  - Add authz hook to `delete_task`
  - Define capability contract: who can delete tasks (admin vs operator vs owner)
- [ ] **W2.2** `src/nexusagent/memory/memory_files.py`
  - Add authz hook to `delete_by_file`
  - Ensure memory deletion respects same role/capability model
- [ ] **W2.3** Authz helper/integration
  - If a shared authz helper exists, use it; if not, add minimal capability check without circular imports
  - Ensure route-level `require_admin`/`verify_api_key` patterns are consistent with store-level checks

### Wave 3: Prompt Injection Defense
- [ ] **W3.1** `src/nexusagent/memory/refinement.py`
  - Add `_sanitize_memory_content()` helper: strip control characters, normalize whitespace, escape framing that could manipulate LLM instructions
  - Parameterize `_check_contradiction_llm()` prompt assembly: pass sanitized entity + sanitized memory snippets
  - Add system-level boundary instruction: treat memory content as data, not instructions
- [ ] **W3.2** Add prompt-injection regression tests
  - Malicious memory content with instruction-like text must not alter LLM system behavior
  - Verify sanitized prompts retain semantic meaning for legitimate content

### Wave 4: Worker Trust Boundary
- [ ] **W4.1** `src/nexusagent/core/worker/worker.py`
  - Add task ownership validation in `handle_task` before execution
  - Ensure `_handle_cancel` only cancels tasks owned by the requesting principal
  - Sanitize cancel handler logs: log task_id only, not raw message payload
- [ ] **W4.2** `src/nexusagent/core/worker/pool.py`
  - Ensure emitted events do not include sensitive task metadata unless explicitly required

## Files Likely to Change
- `src/nexusagent/server/websocket.py`
- `src/nexusagent/core/worker/pool.py`
- `src/nexusagent/server/routes.py`
- `src/nexusagent/core/task/task_store.py`
- `src/nexusagent/memory/memory_files.py`
- `src/nexusagent/memory/refinement.py`
- `src/nexusagent/core/worker/worker.py`
- `tests/` — targeted regression tests for authz, logging hygiene, prompt injection

## Tests / Validation
- Run targeted pytest: `PYTHONPATH=src pytest tests/test_session.py tests/test_orchestration.py tests/test_new_tools.py -q --tb=short`
- Run `ruff check src/ tests/`
- Run `rw_codegate` on changed files
- Verify no raw API keys/tokens appear in captured log output
- Verify authz-denied delete operations return 403/appropriate error

## Risks, Tradeoffs, and Open Questions
- **Risk**: Adding authz to task_store/memory_files may break existing internal callers.
  - *Mitigation*: Add capability checks with backward-compatible defaults; tighten after verifying callers.
- **Risk**: Prompt sanitization may alter legitimate memory content.
  - *Mitigation*: Use reversible normalization; add tests for multilingual/edge-case content.
- **Risk**: Logging changes may remove useful debug context.
  - *Mitigation*: Replace with structured debug fields that are redacted in production but available in debug mode.
- **Open Question**: Is there an existing capability/role model we should align with, or do we need a minimal local check?
