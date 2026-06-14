# Spec: NexusAgent Home Directory (`~/.nexusagent/`)

> Status: DRAFT
> Author: OWL (Lucien)
> Date: 2026-07-18
> Scope: Move all runtime data from project root to `~/.nexusagent/`

---

## Problem

NexusAgent's runtime configuration, data, and state files are scattered across the project root:
- `config/nexusagent.yaml` — runtime config
- `config/NEXUS.md` — system prompt
- `nexus.db` / `data/nexus.db` — SQLite database
- `.master.secret`, `keystore.json`, `.master.salt` — auth secrets
- Skills loaded from `~/.hermes/skills/` (wrong product)
- Hooks referenced as `.nexusagent/hooks` (relative, unresolved)

This creates portability problems:
- Can't deploy as a pip package without dragging config into the repo
- `get_project_root()` uses `Path(__file__).parent.parent.parent.parent` — only works from source layout
- No clean separation between installed code and user data
- Auth secrets live in the project tree (security concern)

## Goal

Establish `~/.nexusagent/` as NexusAgent's single config/data home, following XDG conventions. All runtime data lives here. The project repo contains only code.

## Target Structure

```
~/.nexusagent/
├── config/
│   └── nexusagent.yaml         # Runtime configuration
├── data/
│   └── nexus.db                # SQLite database (server)
├── auth/
│   ├── .master.secret          # Fernet master secret
│   ├── keystore.json           # Encrypted key store
│   └── .master.salt            # KDF salt
├── skills/                     # NexusAgent skills (SKILL.md dirs)
├── hooks/                      # NexusAgent hooks (HOOK.yaml + handler.py)
├── sessions/                   # Session data (already exists)
│   └── {session_id}/memory/    # Hybrid memory files
├── logs/
│   └── tui.log                 # TUI telemetry (already exists)
├── errors/                     # Error collection (already exists)
├── memory/                     # Memory workspace (already exists)
├── history.json                # TUI command history (already exists)
└── NEXUS.md                    # Base system prompt (copy or symlink)
```

## Migration Plan

### Phase 1: Config defaults (config.py)

**File:** `src/nexusagent/infrastructure/config.py`

| Config Key | Old Default | New Default |
|------------|-------------|-------------|
| `server.db_path` | `"nexus.db"` | `"~/.nexusagent/data/nexus.db"` |
| `auth.master_secret_path` | `".master.secret"` | `"~/.nexusagent/auth/.master.secret"` |
| `auth.keystore_path` | `"keystore.json"` | `"~/.nexusagent/auth/keystore.json"` |
| `auth.salt_path` | `".master.salt"` | `"~/.nexusagent/auth/.master.salt"` |
| `prompt.base_prompt_file` | `"config/NEXUS.md"` | `"~/.nexusagent/NEXUS.md"` |
| `hooks.hooks_dir` | `".nexusagent/hooks"` | `"~/.nexusagent/hooks"` |

**Resolution logic change (lines 160-179):**
- Old: resolves relative paths against `get_project_root()` (repo root)
- New: resolves relative paths against `Path.home() / ".nexusagent"` for `server.*` and `auth.*`
- `hooks.hooks_dir`: resolve against `Path.home() / ".nexusagent"` (currently unresolved)
- `prompt.base_prompt_file`: resolve against `Path.home() / ".nexusagent"` for default; allow CWD-relative overrides

**`load_config()` change:**
- Old default: `config_file="config/nexusagent.yaml"` (relative to repo root)
- New default: `config_file="~/.nexusagent/config/nexusagent.yaml"`

### Phase 2: Skills directory (skills.py)

**File:** `src/nexusagent/skills.py`

| Old | New |
|-----|-----|
| `Path.home() / ".hermes" / "skills"` | `Path.home() / ".nexusagent" / "skills"` |

### Phase 3: Prompt loader (prompt_loader.py)

**File:** `src/nexusagent/infrastructure/prompt_loader.py`

| Old | New |
|-----|-----|
| `package_root = Path(__file__).parent.parent.parent` → `package_root / "config" / "NEXUS.md"` | Load base prompt from `Path.home() / ".nexusagent" / "NEXUS.md"` |

Keep CWD-relative NEXUS.md override (project-specific prompts).

### Phase 4: Auth file creation (auth.py)

**File:** `src/nexusagent/infrastructure/auth.py`

Ensure `auth/` subdirectory is created automatically when writing secrets. Currently reads from config paths — will work once config defaults are updated.

### Phase 5: Embeddings .env loading (embeddings.py)

**File:** `src/nexusagent/memory/index/embeddings.py`

| Old | New |
|-----|-----|
| `env_path = get_project_root() / ".env"` | `env_path = Path.home() / ".nexusagent" / ".env"` with fallback to `get_project_root() / ".env"` |

### Phase 6: YAML config defaults

**File:** `config/nexusagent.yaml`

Update all path defaults to `~/.nexusagent/` paths.

### Phase 7: Scripts (Tier 2)

**Files:** `scripts/worktree-worker.py`, `scripts/large-sprint.py`

| Old | New |
|-----|-----|
| `Path.cwd() / ".hermes" / "worktrees"` | `Path.home() / ".nexusagent" / "worktrees"` |
| `Path.cwd() / ".hermes" / "worktree-state.json"` | `Path.home() / ".nexusagent" / "worktree-state.json"` |
| Same pattern for `large-sprint.py` | `~/.nexusagent/sprints/` |

### Phase 8: Tests

**File:** `tests/conftest.py`

| Old | New |
|-----|-----|
| `_DBM("data/nexus.db")` (CWD-relative) | Use `tempfile.mkdtemp()` for test DB |

## Files That Need NO Changes

These already use `~/.nexusagent/` correctly:
- `infrastructure/telemetry.py` → `~/.nexusagent/logs/`
- `core/session.py` → `~/.nexusagent/sessions/`
- `hooks/builtins.py` → `~/.nexusagent/errors/`
- `widgets/chat_input.py` → `~/.nexusagent/history.json`
- `tools/register_all.py` → `~/.nexusagent/memory/`
- `memory/index/index.py` → `{workspace}/.memory/index.sqlite` (derived from workspace)
- `memory/memory_files.py` → `{workspace}/memory/` (derived from workspace)
- `server/server.py` → uses `settings.*` (correct once config is fixed)
- `server/sdk.py` → no hardcoded paths
- `interfaces/cli.py` → uses `settings.*` (correct once config is fixed)
- `interfaces/tui.py` → uses `settings.*` (correct once config is fixed)
- `core/orchestration.py` → `Path(__file__).parent / "templates/"` (package data, correct)

## Docker / Deployment

Docker deployments use explicit env var overrides (`NEXUS_SERVER__DB_PATH=/data/nexus.db`) — no change needed. The new defaults only affect non-containerized deployments.

## Backward Compatibility

Since the product hasn't launched:
- No migration from old paths needed
- Old `config/nexusagent.yaml` in the repo root is a development convenience — can be removed or kept as a dev-only file
- Docker compose files already override paths via env vars — unaffected

## File Manifest

| File | Change | Tier |
|------|--------|------|
| `src/nexusagent/infrastructure/config.py` | Update defaults + resolution logic | 1 |
| `src/nexusagent/skills.py` | Update skills dir path | 1 |
| `src/nexusagent/infrastructure/prompt_loader.py` | Update base prompt path | 1 |
| `src/nexusagent/infrastructure/auth.py` | Ensure auth/ subdir creation | 1 |
| `src/nexusagent/memory/index/embeddings.py` | Update .env path | 1 |
| `config/nexusagent.yaml` | Update default paths | 1 |
| `scripts/worktree-worker.py` | Update worktree paths | 2 |
| `scripts/large-sprint.py` | Update sprint paths | 2 |
| `tests/conftest.py` | Use temp dir for test DB | 1 |
