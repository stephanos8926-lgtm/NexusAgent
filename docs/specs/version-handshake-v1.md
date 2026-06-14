# Spec: Version Handshake + Dev Workflow

> **Version**: 1.0
> **Date**: 2026-07-19
> **Author**: OWL (Lucien)
> **Status**: DRAFT — awaiting audit + sign-off

---

## 1. Problem Statement

NexusAgent currently has **no version coordination** between server and clients:

- `nexus-server` emits no version information on startup or via API
- `nexus` (TUI) connects via WebSocket with no version check — just retry/backoff on raw connection failure
- `nexus-client` submits tasks via NATS with no pre-flight server check
- No Docker Compose hot-reload for development — every code change requires `docker compose down && docker compose up --build`
- `nexus-server` has no `--reload` flag for local dev

**User impact**: Version mismatches cause silent failures (wrong API contract, missing features). Dev loop is slow (manual rebuilds). Connection failures give cryptic WebSocket errors instead of actionable diagnostics.

## 2. Goals

| ID | Goal | Priority |
|----|------|----------|
| G1 | Server exposes structured version via `/version` endpoint | P0 |
| G2 | SDK `health_check()` returns version + compatibility metadata | P0 |
| G3 | CLI warns if server version is incompatible before executing commands | P0 |
| G4 | TUI warns (non-blocking) if client/server versions mismatch on connect | P0 |
| G5 | `nexus-server --reload` for local development (uvicorn `--reload`) | P1 |
| G6 | Docker Compose watch for hot-reload dev workflow | P1 |
| G7 | Connection validation with actionable error messages | P0 |

## 3. Version Scheme

**Semantic versioning** (`MAJOR.MINOR.PATCH`):
- `MAJOR`: Breaking API contract changes
- `MINOR`: New features, backward-compatible
- `PATCH`: Bug fixes, no API change

**Compatibility rule**: Clients and servers with matching `MAJOR.MINOR` are compatible. `PATCH` differences are always allowed.

**Examples**:
- Server `0.1.0` + Client `0.1.0` → compatible
- Server `0.1.0` + Client `0.2.0` → compatible (client newer, can degrade)
- Server `0.2.0` + Client `0.1.0` → warning (client older, may miss features)
- Server `1.0.0` + Client `0.1.0` → incompatible (major version mismatch)

## 4. Server Changes

### 4.1 `/version` Endpoint

```
GET /version
→ {
    "version": "0.1.0",
    "minClient": "0.1.0",
    "maxClient": "0.99.99",
    "server": "nexus-server",
    "uptime": 1234.5,
    "nats": "connected",
    "workers": 4
  }
```

**Implementation**: Add version constant in `server.py`, import `time` for uptime. Add `/version` route returning structured JSON.

### 4.2 `/health` Endpoint Enhancement

```
GET /health
→ {
    "status": "ok",
    "version": "0.1.0",
    "nats": "connected"
  }
```

### 4.3 Startup Log

Server startup log should include version:
```
INFO: NexusAgent Server v0.1.0 starting...
INFO: API listening on 0.0.0.0:8000
INFO: NATS connected to nats://localhost:4222
INFO: Workers started (4 threads)
```

### 4.4 `--reload` Flag

```bash
nexus-server --reload    # Enable uvicorn --reload for auto-restart on code change
nexus-server --reload --reload-dir src  # Watch specific directory
```

**Implementation**: Add `reload: bool = False` to `ServerConfig`. Pass `reload=settings.server.reload` to `uvicorn.run()`.

## 5. SDK Changes

### 5.1 Enhanced `health_check()`

```python
async def health_check(self) -> dict:
    return {
        "status": "ok",
        "version": SERVER_VERSION,
        "minClient": MIN_CLIENT_VERSION,
        "nats": "connected" if self.bus.nc else "disconnected",
    }
```

### 5.2 Constants

Add to `sdk.py`:
```python
SERVER_VERSION = "0.1.0"  # Single source of truth
MIN_CLIENT_VERSION = "0.1.0"
```

## 6. TUI Changes

### 6.1 Pre-Connect Version Check

Before establishing WebSocket:
1. Fetch `GET /version` via HTTP
2. Compare versions using `MAJOR.MINOR` matching
3. If client newer than server: log warning, continue
4. If server major > client major: show prominent warning, continue with `--force` equivalent
5. If server unreachable: show "Server unreachable at {url}" (existing behavior)

### 6.2 Version Display

- Status bar shows server version when connected (optional, compact)
- `/version` command shows full client + server version info
- Connection status distinguishes "unreachable" from "version mismatch" from "connected"

### 6.3 Implementation Approach

The TUI already connects via WebSocket (`_ws_loop`). Add an HTTP preflight step:
```python
async def _check_server_version(self) -> dict | None:
    """Fetch server version before WebSocket connect."""
    import urllib.request
    try:
        url = f"http://127.0.0.1:{settings.server.api_port}/version"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None
```

## 7. CLI Changes

### 7.1 Pre-Flight Check

Before `nexus run` or `nexus-client submit`:
1. Call `sdk.health_check()` (already connects to NATS)
2. If unreachable: print error with guidance ("Start the server with: nexus-server")
3. If version mismatch: print warning, continue

### 7.2 `--version` Enhancement

```bash
nexus --version
# NexusAgent v0.1.0 (client)
# Server: v0.1.0 (compatible) — or "unreachable"

nexus --version --server
# Same but always checks server, errors if unreachable
```

### 7.3 Connection Validation

Add a `preflight()` function to validate server is reachable:
```python
async def preflight() -> dict:
    """Check server connectivity and version. Returns server info or raises."""
    result = await sdk.health_check()
    server_version = result.get("version", "unknown")
    # Compare versions
    if not is_compatible(CLIENT_VERSION, server_version):
        logger.warning(f"Server v{server_version} may not be compatible with client v{CLIENT_VERSION}")
    return result
```

## 8. Docker Compose Dev Workflow

### 8.1 Development Compose Override

Create `docker-compose.dev.yml`:
```yaml
services:
  nexus:
    build:
      context: .
      dockerfile: Dockerfile.dev
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: pyproject.toml
        - action: sync+restart
          path: config
          target: /app/config
    environment:
      - NEXUS_LOG_LEVEL=DEBUG
```

### 8.2 Dev Workflow Commands

```bash
# Development (hot-reload)
docker compose -f docker-compose.dev.yml up

# Or with watch (Docker Compose 2.22+)
docker compose -f docker-compose.yml -f docker-compose.dev.yml watch

# Production build test
docker compose build && docker compose up -d

# Full rebuild
docker compose down && docker compose up -d --build
```

## 9. File Manifest

| File | Action | Description |
|------|--------|-------------|
| `src/nexusagent/server/server.py` | MODIFY | Add `/version` endpoint, version constant, startup log, `--reload` flag |
| `src/nexusagent/server/sdk.py` | MODIFY | Add `SERVER_VERSION`, `MIN_CLIENT_VERSION`, enhance `health_check()` |
| `src/nexusagent/interfaces/cli.py` | MODIFY | Add `preflight()`, enhance `--version`, add connection validation |
| `src/nexusagent/interfaces/tui.py` | MODIFY | Add pre-connect version check, `/version` command, version display |
| `src/nexusagent/infrastructure/config.py` | MODIFY | Add `reload: bool` to `ServerConfig` |
| `src/nexusagent/core/worker.py` | NO CHANGE | Version already tracked via import |
| `config/nexusagent.yaml` | MODIFY | Add `reload: false` under `server` |
| `docker-compose.yml` | MODIFY | Add `develop.watch` section |
| `pyproject.toml` | NO CHANGE | Version already in `[project]` |
| `VERSION` | CREATE | Single source of truth version file |

## 10. Test Plan

### 10.1 Unit Tests

| Test | File | What |
|------|------|------|
| `test_server_version_endpoint` | `tests/test_server_version.py` | `GET /version` returns correct structure |
| `test_sdk_health_includes_version` | `tests/test_sdk_health.py` | `health_check()` returns version |
| `test_version_comparison` | `test_version_compat.py` | semver comparison logic |

### 10.2 Integration Tests

| Test | File | What |
|------|------|------|
| `test_tui_preflight_version_check` | `tests/test_tui_version.py` | TUI fetches `/version` before WS connect |
| `test_cli_preflight_connection` | `tests/test_cli_preflight.py` | CLI validates server before running |
| `test_mismatch_warning` | `tests/test_version_mismatch.py` | Warning emitted when versions mismatch |

### 10.3 E2E Tests

| Test | File | What |
|------|------|------|
| `test_server_client_compatibility` | `tests/test_e2e_compatibility.py` | Full server start → client connect → version check |

## 11. Acceptance Criteria

- [ ] `nexus-server` startup logs version
- [ ] `GET /version` returns structured JSON with version, minClient
- [ ] `GET /health` includes version field
- [ ] `nexus --version` shows client + server version
- [ ] `nexus run` warns if server unreachable with actionable message
- [ ] `nexus` TUI warns (non-blocking) on version mismatch
- [ ] `nexus-server --reload` enables uvicorn hot-reload
- [ ] `docker compose -f docker-compose.dev.yml up` provides hot-reload dev
- [ ] All existing tests pass (485+)
- [ ] New tests cover version endpoints, compatibility, mismatch warnings
