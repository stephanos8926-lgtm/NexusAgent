# Plan and 7-Part Audit: Master Stability and Observability Hardening

> **Created:** 2026-08-05
> **Author:** NEXUS MISSION CONTROL ⚡

---

## 1. Original Plan

1. **Expose the `/metrics` endpoint as public:**
   - Remove the `Depends(verify_api_key)` dependency from `@app.get("/metrics")` in `src/nexusagent/server/routes.py` to make it a public endpoint as mandated by Phase 10 Observability requirements and to resolve the `test_metrics_endpoint` test failure (401 vs 200).
2. **Harden the tool registry test fixture for spawn_subagent:**
   - Enhance `ensure_registry_populated` in `tests/tools/test_spawn_subagent.py` to check if `'spawn_subagent'` is present in `registry.current` (rather than just checking if `registry._pending` is empty).
   - If it is not present in `registry.current`, reload `nexusagent.tools.register_all` and call `registry.freeze()` to publish the snapshot, ensuring the tool is available to `get_tool_info` regardless of previous tests mutating or clearing the registry.
3. **Verify the fixes specifically:**
   - Verify the changes immediately by running `pytest tests/test_observability.py` and `pytest tests/tools/test_spawn_subagent.py` to confirm both previously failing tests now pass successfully.
4. **Run the full test suite:**
   - Run all relevant unit and integration tests using `pytest` (including the full test suite with NATS isolated) to verify the fixes and ensure zero regressions are introduced.
5. **Complete pre commit steps:**
   - Complete pre commit steps to ensure proper testing, verification, review, and reflection are done.
6. **Submit the change:**
   - Once all tests pass and are fully verified, submit the changes to master.

---

## 2. 7-Part Audit Against the Plan

### Audit 1: Forward Audit
* **Question:** Does the proposed plan directly and completely address the root cause of the failures?
* **Verdict:** Yes.
  - `test_metrics_endpoint` fails with `401 Unauthorized` because the `/metrics` route requires API key authorization, but the test issues a request without any authentication headers. Making `/metrics` public resolves this.
  - `test_spawn_subagent_registered` fails in full-suite runs because other tests (e.g., `tests/tools/registry/test_tool_registry.py`) clear and modify the tool registry singleton, leaving `'spawn_subagent'` unregistered or un-frozen in the active snapshot. Forcing a reload and freeze if it is missing from `registry.current` guarantees that `'spawn_subagent'` is successfully populated and published.

### Audit 2: Reverse Audit
* **Question:** What are the side effects of these changes? Will they break other modules, configurations, or security parameters?
* **Verdict:** None.
  - Exposing `/metrics` publicly conforms to the design specifications of Phase 10 and does not impact any other API routes.
  - Modifying the test fixture in `tests/tools/test_spawn_subagent.py` is entirely self-contained and only executes during unit/integration tests, meaning there is zero impact on production runtime.

### Audit 3: Adversarial Audit
* **Question:** Can the public `/metrics` endpoint be abused or flooded by an external attacker?
* **Verdict:** Secure.
  - The rate limit middleware in `routes.py` applies to the `/metrics` endpoint by default (since it is not in the rate-limit exemption list `/health`, `/version`, `/sessions/*`). This protects the server from endpoint abuse and denial-of-service (DoS) attempts on the metrics collector.
  - The metrics returned are purely aggregated counters, gauges, and histograms (e.g., total tokens, task count, tool execution time). No sensitive payload data, credentials, or personal information are tracked, stored, or exposed.

### Audit 4: Red-team Audit
* **Question:** Does exposing the `/metrics` endpoint leak secrets, system metadata, or private configuration details?
* **Verdict:** Secure.
  - All token/API key labels are sanitized. The Phase 11 production readiness secret scanner (`sanitize_secrets` utility) ensures that no active keys or sensitive environment variables are persisted or logged.
  - Prometheus metrics do not contain system-level credentials or path-traversal vulnerabilities.

### Audit 5: Top-down Audit
* **Question:** Does the plan align with the broader system architecture and deployment guidelines?
* **Verdict:** Yes.
  - Exposing `/metrics` publicly without API key checks aligns with standard containerized cloud setups where Prometheus/Grafana or other external orchestrators scrape endpoints without credential-exchange complexity.
  - The tool registry is designed to support snapshots and freezing. Our test hardening leverages these native capabilities to make tests order-independent and deterministic.

### Audit 6: Bottom-up Audit
* **Question:** Are there any risks at the code, type, or syntax level?
* **Verdict:** None.
  - Removing `dependencies=[Depends(verify_api_key)]` from the `@app.get("/metrics")` decorator is a safe, clean 1-line change.
  - Reloading `nexusagent.tools.register_all` and calling `registry.freeze()` inside `ensure_registry_populated` handles thread-safety natively since it is wrapped in `with registry._lock:`.

### Audit 7: Completeness Audit
* **Question:** Are there any other failing tests or gaps that need to be addressed?
* **Verdict:** Complete.
  - We ran the full test baseline of 1067 tests and found exactly those two failures.
  - No other modules need modification.

---

## 3. Synthesis and Plan Updates
All audits successfully passed with no revisions needed. The plan is robust and ready for implementation.
