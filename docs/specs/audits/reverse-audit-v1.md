# Reverse Audit Report: Version Handshake + Dev Workflow v1

> **Date**: 2026-07-19
> **Auditor**: OWL (Lucien) — reverse audit pass
> **Spec**: `docs/specs/version-handshake-v1.md`
> **Plan**: `docs/plans/version-handshake-v1.md`
> **Forward audit**: `docs/specs/audits/forward-audit-v1.md` (read first, this complements it)
> **Test baseline**: 485 passed / 15 failed (pre-existing)

---

## Methodology

This is a **reverse audit** — instead of checking whether the plan implements the spec (that was the forward audit), this asks: *"What could go wrong? What did both documents entirely miss?"*

Every finding has been verified against the **live codebase** (actual server.py, sdk.py, cli.py, tui.py, config.py, web_ui.py, bus.py, api_auth.py, docker-compose.yml, Dockerfile, pyproject.toml).

---

## Summary

**Total gaps found: 27**
- 🔴 Critical: 5
- 🟠 High: 8
- 🟡 Medium: 9
- 🔵 Low: 5

The spec and plan address the *happy path* well. They systematically miss: (1) the Gradio web UI as a client that also submits tasks, (2) security surface of an unauthenticated `/version` endpoint, (3) semver edge cases with pre-release/build metadata strings, (4) rolling upgrade scenarios, (5) the fact that `health_check()` in the SDK talks to NATS (not HTTP) so the CLI's preflight strategy has a hidden dependency, (6) circular import chains from adding version imports, (7) the `nexus --version` command will break if it checks the server synchronously, and (8) the `VERSION` file being an unenforceable fourth copy of the version string.

---

## Critical Gaps (must fix before implementation)

### C1. `/version` endpoint is unauthenticated — exposes server version + NATS status to the network

- **Severity**: 🔴 Critical
- **What**: The spec proposes `GET /version` (§4.1) with no `dependencies=[Depends(verify_api_key)]`. Every other endpoint on the server (`/tasks`, `/health` is the only other unauthenticated endpoint). The `/version` endpoint exposes `version`, `minClient`, `maxClient`, `server`, `uptime`, `nats`, and `workers` — a reconnaissance goldmine.
- **What could go wrong**: An attacker can fingerprint the exact server version, know NATS connection status, and plan targeted exploits. The CORS middleware already restricts localhost, but CORS is not a security boundary for non-browser clients (curl, scripts).
- **Suggested fix**: Either (a) add `dependencies=[Depends(verify_api_key)]` to `/version`, or (b) document explicitly that `/version` is intentionally public and contains no sensitive data. The `workers` field should be removed regardless (see forward audit #1 — it's misleading).

### C2. The CLI `preflight()` connects via NATS (not HTTP), so it won't work without NATS

- **Severity**: 🔴 Critical
- **What**: The spec §7 says `preflight()` calls `sdk.health_check()`. But `sdk.health_check()` does `{"nats": "connected" if self.bus.nc else "disconnected"}` — it checks the NATS bus object, it does NOT make an HTTP call to the server. If NATS is down but the HTTP server is up, `preflight()` will report the server as unreachable even though `GET /version` would succeed.
- **What could go wrong**: Developer's NATS instance crashes but HTTP server keeps running. `nexus run` fails with "server unreachable" but the server is fine for task submission via `POST /tasks`. The CLI cannot distinguish "completely down" from "NATS degraded".
- **Suggested fix**: The CLI preflight should make an **HTTP call to `GET /version`** (or `GET /health`), not use the SDK's NATS-based `health_check()`. These are separate concerns: HTTP reaches the SDK, NATS reaches the worker.

### C3. `VERSION` file creates an unenforceable fourth copy of the version string

- **Severity**: 🔴 Critical
- **What**: The spec introduces `VERSION` file as "single source of truth" (§5.2), the plan adds `VERSION = "0.1.0"` to `server.py` AND `SERVER_VERSION = "0.1.0"` to `sdk.py`. That's four locations: `pyproject.toml`, `VERSION` file, `server.py`, `sdk.py`. The plan's open question #1 says "add a test to verify" but no task creates this test.
- **What could go wrong**: On next version bump (0.2.0), someone updates `pyproject.toml` and `VERSION` but forgets `server.py` and `sdk.py`. Ships with wrong version. No CI check catches it.
- **Suggested fix**: Read version from `pyproject.toml` at runtime via `importlib.metadata.version("nexusagent")` (note: `importlib.metadata` is in stdlib for Python 3.8+). This is exactly what `cli.py:get_version()` already does as a fallback. Make this the *primary* mechanism everywhere. The `VERSION` file should be generated at build time, not hand-edited. If a `VERSION` file must exist, add a CI test: `assert open("VERSION").read().strip() == metadata.version("nexusagent")`.

### C4. Replacing `@click.version_option` with a synchronous server check will break `nexus --version`

- **Severity**: 🔴 Critical
- **What**: The plan §3.4 says "Replace with custom callback that also checks server version." But `cli.py` line 23 uses `@click.version_option(version=f"nexusagent {get_version()}")` on the root `@click.group()`. Click's `version_option` prints and exits before any command runs. There is no async event loop. Adding `asyncio.run(sdk.health_check())` inside a Click version callback is incompatible — Click calls it synchronously, and if an event loop already exists in the same thread (e.g., in tests), it will raise `RuntimeError`.
- **What could go wrong**: `nexus --version` raises an exception. Every tool that parses `nexus --version` output (CI scripts, shell prompts) breaks.
- **Suggested fix**: Keep `@click.version_option` as-is for the local version. Add a separate `--check-server` or `--server-version` flag to the root group that does the async check. OR create a `nexus version --check-server` subcommand.

### C5. Spec says TUI uses `urllib.request` — this blocks the async event loop

- **Severity**: 🔴 Critical (spec-level) / 🟠 High (plan-level, since plan may diverge)
- **What**: Spec §6.3 proposes `urllib.request.urlopen()` for the TUI's HTTP preflight. `urllib.request` is synchronous I/O. Running it inside `NexusApp._ws_loop()` (an async method in a Textual `App`) blocks the entire event loop for up to 5 seconds (timeout). The TUI freezes, SIGWINCH stops being processed, the status spinner stops.
- **What could go wrong**: During reconnection attempts, the TUI becomes completely unresponsive. Users see a frozen screen and think it crashed. This is a regression from the current experience (where at least the retry loop is async).
- **Suggested fix**: Use `httpx.AsyncClient` (already in `pyproject.toml` dependencies). The call becomes `async with httpx.AsyncClient() as client: resp = await client.get(url, timeout=5)`. Non-blocking.

---

## High Gaps (should fix before or immediately after implementation)

### H1. The Gradio web UI (`web_ui.py`) is not mentioned in the spec or plan

- **Severity**: 🟠 High
- **What**: `src/nexusagent/interfaces/web_ui.py` is a full client that submits tasks via `sdk.submit_task()`. It has no version check, no preflight, no error handling for "server unreachable" beyond a bare `except Exception`. It runs as `nexus-web` (entry point in `pyproject.toml` line 44). Neither the spec nor the plan mentions it at all.
- **What could go wrong**: A developer opens the web UI, types a task, clicks submit. Gets `Submission failed: NATSBus not connected` in a text box with no guidance. No "start the server with...", no version mismatch warning. The web UI is a first-class client; ignoring it leaves a silent-failure gap.
- **Suggested fix**: Add `web_ui.py` to the spec's File Manifest. Add a version check to `handle_submit()` or create a shared preflight utility. At minimum, show server status in the UI at load time.

### H2. The `nexus-client submit` command has no preflight or version check — plan only covers `run`

- **Severity**: 🟠 High
- **What**: Plan §3.2–3.3 says "Add preflight to `run` and `submit`" (the spec says this), but the plan's Phase 6 test plan only tests `nexus run` and `nexus --version`. There is no test for `nexus-client submit --dry-run`. The `submit` command at `cli.py:28-56` connects via `sdk.submit_task()` — if NATS is down, it raises an unhandled exception with no actionable message.
- **What could go wrong**: `nexus-client submit "fix bug"` prints a raw NATS exception traceback. The user doesn't know whether the server is down, NATS is down, or their API key is wrong.
- **Suggested fix**: Wrap `submit` error handling with the same preflight. Add to test plan: `test_submit_preflight_unreachable`, `test_submit_version_mismatch`.

### H3. No handling of semver pre-release or build metadata (e.g., `0.1.0-dev`, `1.0.0+build.123`)

- **Severity**: 🟠 High
- **What**: Plan §6.1 Test 1.2 says `test_parse_version_with_prerelease — handle "0.1.0-dev"` but the implementation in §3.1 is `parse_version(v) = tuple(int(x) for x in v.split("."))`. This will crash on `"0.1.0-dev"` because `int("0-dev")` raises `ValueError`. It will also crash on `"1.0.0+build.123"`. The spec §3 says "Semantic versioning" but doesn't define how pre-release strings interact with the compatibility rule.
- **What could go wrong**: A developer tags a pre-release build as `0.2.0-alpha.1`. The CLI or TUI tries to compare with the server's `0.1.0` and crashes with `ValueError: invalid literal for int()`. Entire command fails instead of warning.
- **Suggested fix**: Use `packaging.version.Version` (from `packaging` library, or the stdlib-compatible approach: strip pre-release with `v.split("-")[0]` and build metadata with `v.split("+")[0]` before parsing). Document the rule: pre-release versions are compatible if their base MAJOR.MINOR matches; build metadata is ignored.

### H4. Circular import risk: `server.py` imports from `sdk.py`, and now both import version constants

- **Severity**: 🟠 High
- **What**: Current code: `server.py` line 13 does `from nexusagent.server.sdk import sdk`. If `sdk.py` tries to import `VERSION` from `server.py` (to avoid duplication), that's a circular import. If `sdk.py` defines its own `SERVER_VERSION` and `server.py` imports it from `sdk.py`, the existing `from nexusagent.server.sdk import sdk` at module level means `sdk.py` is being imported, but `sdk.py` can't import back from `server.py`.
- **What could go wrong**: `ImportError: cannot import name 'VERSION' from partially initialized module 'nexusagent.server'`
- **Suggested fix**: Put version constants in a separate module: `src/nexusagent/version.py` with `VERSION`, `MIN_CLIENT_VERSION`, `MAX_CLIENT_VERSION`. Both `server.py` and `sdk.py` import from it. No circular dependency because `version.py` imports nothing from the package. This is also the right place for a `parse_version()` utility.

### H5. "nexus-server --reload" with NATS: server restarts break NATS connections

- **Severity**: 🟠 High
- **What**: The plan adds `uvicorn --reload` support. When uvicorn reloads, the entire Python process restarts. The `lifespan()` handler closes NATS on shutdown and reconnects on startup. But any in-flight task submissions during the restart window will fail. The SDK's global `sdk = NexusSDK()` singleton holds a stale NATS connection reference after reload.
- **What could go wrong**: Developer saves a file, uvicorn reloads, now the server's global `sdk` object has a closed NATS connection (`bus.nc` is None or stale). Task submissions fail silently or raise obscure errors until the server fully re-initializes.
- **Suggested fix**: Add NATS reconnection logic to the SDK's `connect()` method (it already checks `if not self.bus.nc` before connecting). After a reload, ensure `bus.connect()` is idempotent. Add a test: "after lifespan shutdown + restart, sdk.submit_task reconnects to NATS automatically."

### H6. Rolling upgrades: multiple server versions running simultaneously

- **Severity**: 🟠 High
- **What**: The spec says nothing about rolling upgrades. In a Docker Compose or k8s deployment with multiple replicas, during a rolling update, v0.1.0 and v0.2.0 servers run simultaneously. Clients with v0.1.0 may connect to a v0.2.0 server. Per the spec's compatibility rule §3, MAJOR.MINOR `0.1` vs `0.2` is compatible (client can degrade), but the spec doesn't define what "degrade" means in practice.
- **What could go wrong**: A v0.1.0 client sends a message type the v0.2.0 server doesn't recognize (or vice versa). The WebSocket protocol may have changed. There's no `maxClient` enforcement anywhere — the spec shows `maxClient` in the `/version` response but never says what clients should do with it.
- **Suggested fix**: Document that `maxClient` is informational only; clients should check `maxClient` and refuse to connect if their version exceeds it. Or remove `maxClient` from the spec entirely until the API is stable enough to enforce upper bounds.

### H7. The `workers` field in `/version` is misleading (forward audit #1 re-confirmed with severity upgrade)

- **Severity**: 🟠 High (upgraded from Low in forward audit)
- **What**: Server line 42 shows only ONE worker task: `asyncio.create_task(worker.start())`. The spec shows `"workers": 4` in the response. This is wrong — it's 1 worker with a semaphore of 4, but the semaphore is on `WorkerPool`, not the singleton `worker`. The `settings.server.worker_threads` field exists but is never used (it's in config but I couldn't find it referenced in worker.py or server.py).
- **What could go wrong**: Monitoring / ops tools read `"workers": 4` and expect 4 processes. Health dashboards report wrong data.
- **Suggested fix**: Either remove `workers` from `/version`, or add `settings.server.worker_threads` to the response. Don't hardcode `4`.

### H8. Docker Compose `develop.watch` won't work with the existing volume mounts

- **Severity**: 🟠 High
- **What**: The existing `docker-compose.yml` (line 12-13) mounts `nexus-data:/data` for the database. If the plan adds `develop.watch` with `path: ./src → /app/src`, this is a **bind mount** that replaces the container's `/app/src` at runtime. But the Dockerfile (line 13) already copies `src/` into the image at build time. The watch action `sync` copies host files to `/app/src`, which overwrites the built files. This works — but there's a conflict: if `nexus-data` volume and the `develop` action both try to modify container paths, and the user runs `docker compose up` (not `docker compose watch`), the watch section is silently ignored (only works with `docker compose watch` command, not `up`).
- **What could go wrong**: Developer reads the spec §8.2, runs `docker compose -f docker-compose.dev.yml up`, expects hot-reload. Nothing happens — watch requires `docker compose watch`. Confusion and wasted time.
- **Suggested fix**: Clarify in the spec that `develop.watch` only works with `docker compose watch`, not `docker compose up`. The `--reload` flag on the server is the proper in-container hot-reload mechanism. They are complementary, not alternatives.

---

## Medium Gaps (nice to have)

### M1. `health_check()` reports status based on NATS — but HTTP server is what clients connect to first

- **Severity**: 🟡 Medium
- **What**: The SDK's `health_check()` returns `"status": "ok"` if the bus object exists, regardless of whether NATS is actually reachable. It checks `self.bus.nc` (the NATS client object), not the actual connection state. `self.nc` is set to `None` on close (bus.py line 149) but between `connect()` failure and teardown, it could be a disconnected client object.
- **What could go wrong**: `health_check()` says "ok" but NATS is actually disconnected (e.g., after a network partition). The client proceeds to submit a task and it fails.
- **Suggested fix**: Add an actual NATS ping or check `self.bus.nc.is_connected` (NATS client has this property). Or separate `status` (HTTP server alive) from `nats` (NATS status).

### M2. `/health` endpoint currently has no version — adding it creates a response format mismatch

- **Severity**: 🟡 Medium
- **What**: The current `/health` returns `{"status": "ok", "nats": "connected"}`. The spec §4.2 adds `"version": "0.1.0"` but doesn't change the `status` field semantics. If any monitoring system parses `/health` strictly (expects exactly 2 keys), this breaks.
- **What could go wrong**: Monitoring alerts fire because the health response format changed unexpectedly.
- **Suggested fix**: Add a note in the spec: "Adding `version` to `/health` is a backward-compatible additive change." Document it clearly so monitoring consumers know.

### M3. `session` CLI commands also connect to the DB via SDK — no version check there either

- **Severity**: 🟡 Medium
- **What**: `cli.py` lines 111-194 implement `session list/resume/fork/rename/delete`. These call `session_repo.list_sessions()` etc. directly (not via NATS). If the server is a newer version with a different DB schema, these commands could fail with obscure SQL errors. There's no version check before DB access.
- **What could go wrong**: After a server upgrade, `nexus session list` fails with `sqlalchemy.exc.OperationalError: no such column` and the user has no idea why.
- **Suggested fix**: Add preflight to session commands too, or document that all CLI commands should run `preflight()` before executing. Add a test.

### M4. `/version` response includes `maxClient: "0.99.99"` — arbitrary upper bound that will be wrong

- **Severity**: 🟡 Medium
- **What**: The spec §4.1 shows `"maxClient": "0.99.99"` hardcoded. When the project reaches v1.0.0, this is wrong. When it reaches v1.0.0, no one will remember to update the `maxClient` string in server.py. And semantically, `maxClient` for a `0.1.0` server should probably be `0.99.99` to allow any 0.x client, but the spec doesn't explain the logic.
- **What could go wrong**: After v1.0.0 release, the server at v1.0.0 still reports `maxClient: "0.99.99"`, and v1.x clients think they're incompatible (they're below maxClient but above MAJOR version).
- **Suggested fix**: Derive `maxClient` from the current version: if server is `0.1.0`, `maxClient` = `0.99.99`. If server is `1.2.3`, `maxClient` = `1.99.99`. Formula: same MAJOR, `.99.99`. Generate it dynamically, don't hardcode.

### M5. No definition of what "compatible" means for client newer than server

- **Severity**: 🟡 Medium
- **What**: Spec §3 says "Server `0.1.0` + Client `0.2.0` → compatible (client newer, can degrade)" but doesn't specify *how* the client degrades. Does the TUI disable features? Does the CLI skip optional flags? There's no feature negotiation, just a version number.
- **What could go wrong**: A v0.2.0 TUI connects to a v0.1.0 server and sends a `"type": "compact"` WebSocket message that the server doesn't understand. The server ignores it (best case) or throws an error (worst case).
- **Suggested fix**: Define a **minimum feature set** for each MAJOR.MINOR. Or document that "client newer, can degrade" means the client should check the server version and disable features not supported by that version. Add server capabilities list to `/version`.

### M6. `--reload` flag and Docker Compose are alternative dev workflows — but the spec presents them as complementary without explaining when to use which

- **Severity**: 🟡 Medium
- **What**: The spec §4.4 and §8 offer `--reload` flag vs Docker Compose watch as if they're the same thing. They're not. `--reload` is for running `nexus-server` natively on the host (requires Python, NATS, etc.). Docker Compose watch is for running in a container. They target different developers and different environments.
- **What could go wrong**: A developer tries to use `--reload` inside a Docker container. It doesn't work well because uvicorn's file watching needs inotify, which may not propagate through Docker volumes correctly.
- **Suggested fix**: Add a note: "Use `--reload` for native host development. Use `docker compose watch` for container-based development. Don't combine them."

### M7. The spec doesn't define what happens if `minClient > server version` (bug/misconfiguration)

- **Severity**: 🟡 Medium
- **What**: If someone accidentally sets `minClient: "0.2.0"` while the server is `0.1.0`, then ALL clients are rejected as too old, including identical-version clients. This is a simple typo that bricks the entire API surface from the client's perspective.
- **What could go wrong**: After a botched upgrade, `minClient` is higher than the running server version. `nexus run` fails with "server version too old" even though it's the same version.
- **Suggested fix**: Add a server-side assertion: `assert parse_version(MIN_CLIENT_VERSION) <= parse_version(VERSION)` at startup. Crash early with a clear error message rather than silently rejecting all clients.

### M8. No semver comparison library: hand-rolled `parse_version` is fragile

- **Severity**: 🟡 Medium
- **What**: Plan §3.1 proposes `parse_version(v) = tuple(int(x) for x in v.split("."))`. This doesn't handle: pre-release (`0.1.0-dev`), build metadata (`0.1.0+build.1`), leading zeros (`0.01.0`), or non-numeric components. The `packaging` library (which provides `packaging.version.Version`) is the standard Python semver parser — but it's not in dependencies.
- **What could go wrong**: Any non-standard semver string shipped from CI (common with tools like `semantic-release`) crashes the version comparison.
- **Suggested fix**: Either add `packaging` to dependencies and use `packaging.version.Version`, or at minimum, strip pre-release and build metadata: `v.split("-")[0].split("+")[0]` before parsing. Document that only `MAJOR.MINOR.PATCH` numeric components are supported.

### M9. `nexus-server` startup log specifies port `0.0.0.0:8000` but spec says `0.0.0.0:8000` as hardcoded text

- **Severity**: 🟡 Medium
- **What**: Spec §4.3 shows `INFO: API listening on 0.0.0.0:8000`. If `settings.server.api_port` is changed to 8080, the log still says 8000. Same issue for NATS URL in the startup log.
- **What could go wrong**: Log says port 8000, but the server is actually on 8080. Confusing during debugging.
- **Suggested fix**: Use `settings.server.api_port` and `settings.server.nats_url` in the startup log format strings.

---

## Low Gaps (optional improvements)

### L1. The `nexus --version` output format doesn't match the spec

- **Severity**: 🔵 Low
- **What**: Spec §7.2 says:
  ```
  nexus --version
  # NexusAgent v0.1.0 (client)
  # Server: v0.1.0 (compatible) — or "unreachable"
  ```
  But `cli.py` line 23 uses `@click.version_option(version=f"nexusagent {get_version()}")` which outputs `nexusagent 0.1.0`. The format is different, and the server check is a separate concern.
- **Fix**: Standardize the output format. Consider a custom callback that matches the spec.

### L2. The spec's TUI code example appends `"api_port"` to `127.0.0.1` as a string

- **Severity**: 🔵 Low
- **What**: Spec §6.3: `f"http://127.0.0.1:{settings.server.api_port}/version"` — this is correct. But if `api_port` is set via env var to a string (env vars are always strings in config.py), this would still work because f-strings handle it. It's fine.
- **Just a note**: The TUI might want to read the port from `settings.client` if it's a client-side config, not `settings.server`.

### L3. No test for Docker Compose dev workflow

- **Severity**: 🔵 Low
- **What**: The spec §8 defines a Docker Compose dev workflow, but the test plan §10 only covers unit/integration/E2E for the Python code. There's no smoke test for `docker-compose.dev.yml` validation.
- **Fix**: Add a `docker compose -f docker-compose.dev.yml config` CI step to validate the YAML syntax.

### L4. No rollback procedure for the `VERSION` file

- **Severity**: 🔵 Low
- **What**: The plan §Rollback Plan says `git revert HEAD` per phase. But if the `VERSION` file is added in Phase 1 and modified in a later phase, reverting a later phase leaves the `VERSION` file in an inconsistent state.
- **Fix**: Note in the rollback plan that the `VERSION` file is additive (created once, never modified) so rollback is safe.

### L5. Spec doesn't mention the `nexus-client` entry point name in any example

- **Severity**: 🔵 Low
- **What**: Spec §7 uses `nexus-client submit` (pyproject.toml line 42: `nexus-client = "nexusagent.cli:main"`), but §7 also references `nexus run` (which is actually the `run` command within the same CLI). The TUI is `nexus` (line 43). There's no entry-point glossary.
- **Fix**: Add a small table: `nexus-server` → `nexusagent.server:run`, `nexus-client` / `nexus` (CLI) → `nexusagent.cli:main`, `nexus` (TUI) → `nexusagent.tui:main`, `nexus-web` → `nexusagent.web_ui:run_ui`. (Note: `nexus` CLI and TUI share the name `nexus` — this is itself a potential confusion point.)

---

## Architectural Concerns

### AC1. The spec introduces three separate "single sources of truth" that contradict each other

- `VERSION` file (spec §5.2: "Single source of truth")
- `sdk.py` `SERVER_VERSION` (spec §5.2: `# Single source of truth`)
- `pyproject.toml` `[project].version` (already exists, `0.1.0`)

The forward audit identified this too, but it's worth restating with emphasis: **until resolved, this will be a persistent source of bugs**. Every version bump is a multi-file manual operation. The recommended resolution:

```
src/nexusagent/version.py          # Only place VERSION is defined
    ↓ imported by
server/server.py: VERSION → version.VERSION
server/sdk.py: SERVER_VERSION → version.VERSION  
cli.py: get_version() → version.VERSION (drop pyproject.toml fallback)
tests/test_version_sync.py: assert all sources match
```

### AC2. `health_check()` conflates "is SDK connected to NATS" with "is server healthy"

The current `sdk.health_check()` doesn't check the server at all — it checks the SDK's own NATS bus. The server's `/health` endpoint checks server-side NATS. These are two different things. The CLI spec §7 says "Call `sdk.health_check()` to check if server is reachable" — but it doesn't. It checks if the *client's NATS bus* is connected, which is almost certainly false for the CLI unless NATS is pre-connected.

**Resolution**: The CLI should make an HTTP call (`GET /version` or `GET /health`) to check server reachability. The SDK's `health_check()` should be renamed to `nats_status()` or supplemented with a separate `server_health()` that makes an HTTP call.

### AC3. No version check exists for the WebSocket handshake itself

The TUI connects via WebSocket at `ws://127.0.0.1:8000/sessions/{id}/ws`. The spec proposes a pre-flight HTTP check before the WS connect, but if the HTTP check passes and then the server restarts between the check and the WS connect (race condition), the WS connection could fail to a different server version. This is unlikely but possible in containerized environments.

**Resolution**: Accept as a known edge case. The retry loop in `_ws_loop()` handles this by reconnecting.

---

## Everything the Plan Misses (Quick Reference)

| # | Gap | Severity | Forward Audit Found It? |
|---|-----|----------|------------------------|
| C1 | `/version` unauthenticated — reconnaissance risk | 🔴 Critical | No |
| C2 | CLI preflight uses NATS `health_check()` not HTTP | 🔴 Critical | No |
| C3 | `VERSION` file = unenforceable 4th copy | 🔴 Critical | Partial (landed in Q1) |
| C4 | Replacing `@click.version_option` breaks sync/async | 🔴 Critical | Yes (#3) |
| C5 | `urllib.request` blocks async event loop | 🔴 Critical | Yes (#5) |
| H1 | Gradio web UI completely omitted | 🟠 High | No |
| H2 | `submit` command has no preflight/test | 🟠 High | No |
| H3 | Pre-release semver crashes `parse_version()` | 🟠 High | No |
| H4 | Circular import risk server.py ↔ sdk.py | 🟠 High | No |
| H5 | `--reload` breaks NATS singleton | 🟠 High | No |
| H6 | Rolling upgrades not addressed | 🟠 High | No |
| H7 | `workers: 4` is misleading | 🟠 High | Yes (#1) |
| H8 | Docker `develop.watch` requires `watch` not `up` | 🟠 High | No |
| M1 | `health_check()` doesn't verify NATS is actually connected | 🟡 Medium | No |
| M2 | `/health` format change may break monitoring | 🟡 Medium | No |
| M3 | `session` commands also need preflight | 🟡 Medium | No |
| M4 | `maxClient: "0.99.99"` hardcoded, will be wrong | 🟡 Medium | No |
| M5 | "client degrades" not defined | 🟡 Medium | No |
| M6 | `--reload` vs Docker watch — when to use which | 🟡 Medium | No |
| M7 | `minClient > VERSION` misconfiguration not caught | 🟡 Medium | No |
| M8 | Hand-rolled `parse_version` is fragile | 🟡 Medium | No |
| M9 | Startup log hardcodes port instead of using settings | 🟡 Medium | No |
| L1 | `--version` output format doesn't match spec | 🔵 Low | No |
| L2 | TUI reads port from server config, not client | 🔵 Low | No |
| L3 | No Docker Compose validation test | 🔵 Low | No |
| L4 | Rollback plan doesn't address VERSION file | 🔵 Low | No |
| L5 | No entry-point glossary for command names | 🔵 Low | No |

---

## Recommendations (Priority Order)

1. **Resolve version constants architecture now**: Create `src/nexusagent/version.py`, read everything from `importlib.metadata`, eliminate hardcoded strings. This is a 10-minute fix that prevents an entire class of bugs.

2. **Switch CLI preflight from SDK to HTTP**: `preflight()` should call `GET /version` via `httpx`, not `sdk.health_check()`. Different concern, different transport.

3. **Fix the TUI preflight now**: Replace `urllib.request` with `httpx.AsyncClient` in the spec. A sync call in an async Textual app is a hard bug, not a nice-to-have.

4. **Add `web_ui.py` to the scope**: The Gradio UI is a client. It needs at minimum a server-status check on load. At minimum, add it to the File Manifest.

5. **Clarify `--version` behavior**: Don't break `@click.version_option`. Add a separate mechanism for `--check-server`. Keep it clean.

6. **Add version-sync test**: One test file that asserts `pyproject.toml` version == `version.VERSION` == server constant == sdk constant. Add it to CI.

7. **Document `develop.watch` limitations**: It requires `docker compose watch`, not `up`. The `--reload` flag is the right mechanism inside a container.

---

## Conclusion

The spec and plan are **well-structured for the happy path** but miss enough edge cases, security considerations, and client coverage to warrant a revision pass before implementation. The most critical issues are: (1) the CLI preflight strategy checks NATS instead of HTTP, (2) the TUI spec proposes blocking I/O in an async loop, (3) the version constant architecture guarantees drift, and (4) the entire Gradio web UI was omitted from scope.

With the fixes in this report integrated, the spec will be robust against real-world usage patterns including NATS outages, rolling upgrades, semver edge cases, and the synchronous/asynchronous boundary problems inherent in the Click + Textual + asyncio architecture.

---

*This reverse audit complements the forward audit (`forward-audit-v1.md`). The forward audit verified accuracy; this audit stress-tests resilience.*
