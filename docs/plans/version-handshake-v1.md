# Implementation Plan: Version Handshake + Dev Workflow

> **Spec**: `docs/specs/version-handshake-v1.md`
> **Date**: 2026-07-19
> **Status**: READY FOR AUDIT

---

## FILE MANIFEST

| # | File | Action | Lines | Description |
|---|------|--------|-------|-------------|
| 1 | `VERSION` | CREATE | 3 | Single source of truth version string |
| 2 | `src/nexusagent/server/server.py` | MODIFY | +30 | Add `/version` endpoint, startup log, `--reload` |
| 3 | `src/nexusagent/server/sdk.py` | MODIFY | +15 | Add version constants, enhance `health_check()` |
| 4 | `src/nexusagent/interfaces/cli.py` | MODIFY | +40 | Add `preflight()`, enhance `--version`, connection validation |
| 5 | `src/nexusagent/interfaces/tui.py` | MODIFY | +35 | Add pre-connect version check, `/version` command |
| 6 | `src/nexusagent/infrastructure/config.py` | MODIFY | +2 | Add `reload: bool` to `ServerConfig` |
| 7 | `config/nexusagent.yaml` | MODIFY | +1 | Add `reload: false` |
| 8 | `docker-compose.yml` | MODIFY | +30 | Add `develop.watch` section |
| 9 | `Dockerfile.dev` | CREATE | 15 | Dev-optimized Dockerfile |
| 10 | `tests/test_server_version.py` | CREATE | ~40 | `/version` endpoint tests |
| 11 | `tests/test_version_compat.py` | CREATE | ~30 | Version comparison logic tests |
| 12 | `tests/test_tui_version.py` | CREATE | ~35 | TUI preflight version check tests |
| 13 | `tests/test_cli_preflight.py` | CREATE | ~50 | CLI preflight + version check tests |

**Total estimated**: ~290 lines of production code, ~155 lines of tests

---

## PHASE 1: SERVER VERSION ENDPOINT

**Files**: `VERSION`, `server.py`, `config.py`, `config/nexusagent.yaml`

### Task 1.1: Create `VERSION` file
```
0.1.0
```

### Task 1.2: Add version constant to `server.py`
```python
# At top of file
VERSION = "0.1.0"
```

### Task 1.3: Add `/version` endpoint
```python
@app.get("/version")
async def version():
    import time
    return {
        "version": VERSION,
        "minClient": "0.1.0",
        "server": "nexus-server",
        "uptime": time.monotonic(),
        "nats": "connected" if get_bus().nc else "disconnected",
    }
```

### Task 1.4: Enhance startup logging
In `lifespan()`, add:
```python
logger.info(f"NexusAgent Server v{VERSION} starting...")
```

### Task 1.5: Enhance `/health` endpoint
Add version to existing health response.

### Task 1.6: Add `--reload` flag
Add `reload: bool = Field(default=False)` to `ServerConfig`. Pass to `uvicorn.run(reload=...)`.

---

## PHASE 2: SDK VERSION HANDSHAKE

**Files**: `sdk.py`

### Task 2.1: Add version constants
```python
SERVER_VERSION = "0.1.0"  # Must match VERSION file
MIN_CLIENT_VERSION = "0.1.0"
```

### Task 2.2: Enhance `health_check()`
Include version in response dict.

---

## PHASE 3: CLI PREFLIGHT + VERSION CHECK

**Files**: `cli.py`

### Task 3.1: Add version comparison utility
```python
def parse_version(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))

def is_compatible(server_ver: str, client_ver: str) -> bool:
    s = parse_version(server_ver)
    c = parse_version(client_ver)
    return s[0] == c[0] and s[1] == c[1]
```

### Task 3.2: Add `preflight()` function
Connect to server, fetch health, compare versions, warn on mismatch.

### Task 3.3: Integrate into CLI commands
Add `@click.option("--skip-version-check", is_flag=True)` to `run` and `submit`.
Run `preflight()` before main logic unless skipped.

### Task 3.4: Enhance `--version` flag
Existing `--version` already prints client version via `@click.version_option`.
Replace with custom callback that also checks server version.

---

## PHASE 4: TUI VERSION CHECK

**Files**: `tui.py`

### Task 4.1: Add HTTP preflight before WebSocket
In `_ws_loop()`, before `websockets.connect()`, fetch `/version`.

### Task 4.2: Version warning on mismatch
Show AppMessage in chat if versions don't match. Non-blocking.

### Task 4.3: Enhance `/version` command
Show client + server version info.

### Task 4.4: Update connection status messages
Distinguish "unreachable" from "version mismatch" from "compatible".

---

## PHASE 5: DOCKER COMPOSE DEV WORKFLOW

**Files**: `docker-compose.yml`, `Dockerfile.dev`

### Task 5.1: Add `develop.watch` section
Sync `./src` → `/app/src`, rebuild on `pyproject.toml` change, sync+restart on `config/` change.

### Task 5.2: Create `Dockerfile.dev`
Based on existing `Dockerfile` but with `ENV NEXUS_LOG_LEVEL=DEBUG`.

---

## PHASE 6: TESTS

### Task 6.1: Unit tests (`tests/test_version_compat.py`)
- `test_parse_version_valid` — parse "0.1.0" → (0, 1, 0)
- `test_parse_version_with_prerelease` — handle "0.1.0-dev"
- `test_compatible_same_version` — "0.1.0" vs "0.1.0" → True
- `test_compatible_patch_diff` — "0.1.0" vs "0.1.5" → True
- `test_compatible_minor_diff` — "0.1.0" vs "0.2.0" → True (client newer OK)
- `test_incompatible_major_diff` — "0.1.0" vs "1.0.0" → False
- `test_incompatible_client_older` — "0.2.0" vs "0.1.0" → False

### Task 6.2: Integration tests (`tests/test_server_version.py`)
- `test_version_endpoint_returns_200` — HTTP GET returns JSON
- `test_version_has_required_fields` — version, minClient, server present
- `test_health_includes_version` — /health response has version
- `test_startup_log_includes_version` — capture log output

### Task 6.3: Integration tests (`tests/test_cli_preflight.py`)
- `test_preflight_server_reachable` — mock health_check, verifies pass
- `test_preflight_server_unreachable` — mock connection failure, verifies error message
- `test_preflight_version_mismatch_warning` — mock old server, verify warning
- `test_preflight_skip_flag` — `--skip-version-check` bypasses

### Task 6.4: TUI tests (`tests/test_tui_version.py`)
- test_tui_shows_version_warning_on_mismatch
- test_tui_shows_unreachable_message
- test_tui_version_command_shows_both_versions

### Task 6.5: E2E tests (`tests/test_e2e_compatibility.py`)
- test_server_starts_then_client_connects_with_version_match
- test_server_older_than_client_warns

---

## PHASE 7: REVIEW + FINALIZE

### Task 7.1: Self-review all code
- [ ] Version string consistency across VERSION, server.py, sdk.py
- [ ] semver comparison edge cases handled
- [ ] Error messages are actionable
- [ ] No breaking changes (485+ tests pass)

### Task 7.2: Run full test suite
```bash
PYTHONPATH=src python3 -m pytest tests/ -q --tb=short
```

### Task 7.3: Integration test
```bash
nexus-server &
sleep 2
nexus --version --server
nexus-client submit --dry-run "test"
kill %1
```

### Task 7.4: Commit + push
Per-phase commits for review safety.

---

## ROLLBACK PLAN

Each phase = one commit. If any phase breaks:
```bash
git revert HEAD  # Undo last phase
```

## OPEN QUESTIONS

1. Should `VERSION` file use the same value as `pyproject.toml` `[project].version`? **Yes — add a test to verify.**
2. Should we auto-bump patch on build? **No — manual SemVer for now; consider bump-my-version later.**
3. NATS is required for `health_check()` — what if NATS is down but HTTP works? **Health endpoint should report "degraded" with NATS status separately.**
