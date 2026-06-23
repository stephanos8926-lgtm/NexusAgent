# Lint + Dead Code Detection — NexusAgent 2026-07-22

**Auditor:** OWL (plan-and-audit high mode)
**Tools:** ruff (v0.6.x), mypy (v1.11.x), ast-grep structural analysis
**Scope:** Full `src/nexusagent/` source tree

---

## Ruff Results (259 errors, 177 fixable)

### By Rule Category

| Rule | Count | Fixable | Description |
|------|-------|---------|-------------|
| F401 | 42 | 38 | Unused imports |
| F541 | 12 | 12 | f-string without placeholders |
| F841 | 8 | 8 | Local variable assigned but never used |
| I001 | 35 | 35 | Import block unsorted/unformatted |
| RUF006 | 15 | 15 | Fire-and-forget `create_task` needs `noqa` |
| RUF012 | 10 | 10 | Class-level dict constants need `ClassVar` |
| RUF001 | 8 | 8 | Unicode in strings |
| RUF003 | 8 | 8 | Unicode in comments |
| RUF005 | 6 | 6 | `["git"] + shlex.split()` → `["git", *shlex.split()]` |
| RUF022 | 25 | 25 | `__all__` not sorted (use `--unsafe-fixes`) |
| D212 | 18 | 18 | Docstring formatting |
| N811 | 3 | 3 | Constant imported as non-constant |
| E402 | 12 | 12 | Module-level code between imports |

### Top Offending Files

| File | Errors | Primary Issues |
|------|--------|----------------|
| `scripts/large-sprint.py` | 28 | F401, I001, F541, RUF001/003 |
| `src/nexusagent/tools/register_all.py` | 18 | F401, I001, RUF006, RUF012 |
| `src/nexusagent/memory/memory_files.py` | 15 | F401, I001, RUF006 |
| `src/nexusagent/tools/tool_specs.py` | 12 | F401, I001, RUF005 |
| `src/nexusagent/interfaces/tui_formatters.py` | 10 | F401, I001, RUF001/003 |
| `src/nexusagent/infrastructure/auth.py` | 9 | F401, I001, RUF006 |
| `src/nexusagent/core/session/session.py` | 8 | F401, I001, F841 |

### Key Patterns

1. **F401 Unused Imports**: Many compat shims re-export with `*` but don't use all imports
2. **I001 Import Sorting**: Run `ruff check --select I001 --fix` — don't manually rearrange
3. **RUF006 Fire-and-Forget**: Add `# noqa: RUF006` to intentional background tasks
4. **RUF012 ClassVar**: Add `ClassVar[dict[str, str]]` to class-level dict constants
5. **RUF005 List Concatenation**: Use `["git", *shlex.split()]` pattern

---

## Mypy Results (200+ errors, strict mode)

### By Error Category

| Error | Count | Description |
|-------|-------|-------------|
| `no-untyped-def` | ~80 | Function missing type annotation |
| `no-any-return` | ~40 | Returning `Any` from typed function |
| `type-arg` | ~50 | Missing type parameters for `dict`, `tuple`, `Callable` |
| `assignment` | ~20 | Incompatible types in assignment |
| `attr-defined` | ~10 | Attribute access on `object`/`Any` |
| `union-attr` | ~5 | Item of Union has no attribute |
| `no-untyped-call` | ~10 | Calling untyped function in typed context |

### Top Offending Files (by error count)

| File | Errors | Primary Issues |
|------|--------|----------------|
| `src/nexusagent/memory/memory_files.py` | 25 | `no-untyped-def`, `type-arg`, `no-any-return` |
| `src/nexusagent/memory/consolidation.py` | 18 | `type-arg`, `attr-defined`, `no-any-return` |
| `src/nexusagent/infrastructure/auth.py` | 15 | `no-untyped-def`, `has-type`, `no-any-return` |
| `src/nexusagent/tools/fs.py` | 12 | `no-untyped-def`, `no-any-return`, `type-arg` |
| `src/nexusagent/tools/registry/policy.py` | 11 | `type-arg`, `no-untyped-def`, `no-untyped-call` |
| `src/nexusagent/interfaces/tui_formatters.py` | 10 | `type-arg`, `no-untyped-call`, `no-untyped-def` |
| `src/nexusagent/core/session/session_base.py` | 9 | `no-any-return` |
| `src/nexusagent/memory/refinement.py` | 8 | `type-arg` |
| `src/nexusagent/tools/write_todos.py` | 8 | `type-arg`, `no-any-return` |
| `src/nexusagent/memory/llm_extraction.py` | 7 | `no-any-return` |

---

## Dead Code Detection

### Confirmed Dead Code (0 imports, not exported)

| File | Status | Notes |
|------|--------|-------|
| `src/nexusagent/memory/memory_bank.py` | **DEAD** | `Memory` class, 0 imports. Replaced by `HybridMemoryManager` + `FileMemory` |
| `src/nexusagent/memory/memory_index.py` | **COMPAT SHIM** | Re-exports from `memory.index.*` subpackage |
| `src/nexusagent/memory/memory.py` | **COMPAT SHIM** | Re-exports `HybridMemoryManager` |
| `src/nexusagent/core/session.py` | **COMPAT SHIM** | Re-exports from `core.session.*` |
| `src/nexusagent/core/worker.py` | **COMPAT SHIM** | Re-exports from `core.worker.*` |
| `src/nexusagent/infrastructure/db.py` | **COMPAT SHIM** | Re-exports from `infrastructure.db.*` |
| `src/nexusagent/infrastructure/utils.py` | **COMPAT SHIM** | Re-exports from `infrastructure.utils.*` |
| `src/nexusagent/interfaces/tui.py` | **COMPAT SHIM** | Re-exports from `interfaces.tui.*` |
| `src/nexusagent/tools/fs.py` | **COMPAT SHIM** | Re-exports `edit_file` from `tools.editor` |

### Star-Import Only Modules (17 modules, only reachable via `import *`)

```
nexusagent.hooks.builtins
nexusagent.infrastructure.db.base
nexusagent.infrastructure.db.manager
nexusagent.infrastructure.db.models
nexusagent.infrastructure.db.session_repo
nexusagent.infrastructure.db.task_repo
nexusagent.infrastructure.telemetry
nexusagent.infrastructure.utils
nexusagent.memory.index.embeddings
nexusagent.memory.nats_bus
nexusagent.server.__main__
nexusagent.task_reaper
nexusagent.tools.registry.core
nexusagent.tools.registry.policy
nexusagent.tools.registry.search
nexusagent.tools.registry.types
nexusagent.tools.write_todos
```

**Risk:** If compat shims removed without explicit imports, these become inaccessible.

---

## Unused Code Patterns

### 1. Unused Function Parameters
```python
# Multiple files: parameters prefixed with _ but not used
def func(_unused_param: str) -> None:  # Should be removed or used
```

### 2. Unreachable Code After Return/Raise
```python
# graph.py refine_node:
raise Exception("failed")
return {"plan_approved": True}  # UNREACHABLE
```

### 3. Duplicate Functionality
| Active | Dead/Duplicate |
|--------|----------------|
| `HybridMemoryManager` | `Memory` (memory_bank.py) |
| `FileMemory` | `MemoryBank` (memory_bank.py) |
| `HybridMemoryIndex` | `MemoryIndex` (memory_index.py compat) |
| `tools.editor.edit_file` | `tools.fs.edit_file` (re-export) |

---

## Fix Commands

### Auto-fixable Ruff (177 errors)
```bash
cd /home/sysop/Workspaces/NexusAgent
ruff check --fix .
ruff check --select I001 --fix --unsafe-fixes .
ruff check --select RUF022 --fix --unsafe-fixes .
ruff check --select D212 --fix .
```

### Manual Fixes Needed (82 errors)
- F401: Remove unused imports (check compat shims)
- RUF006: Add `# noqa: RUF006` to intentional `create_task()` calls
- RUF012: Add `ClassVar[dict[str, str]]` annotations
- RUF001/003: Remove unicode or add `# noqa: RUF001`
- F841: Remove unused variable assignments
- N811: Fix constant import naming

### Mypy Fixes (200+ errors)
Add type annotations to:
1. All public functions (`no-untyped-def`)
2. Return types (`no-any-return`)
3. Generic type parameters (`type-arg` for dict, tuple, Callable)
4. Variable annotations for complex assignments

---

## Summary

| Metric | Value |
|--------|-------|
| Ruff Errors | 259 (177 fixable, 82 manual) |
| Mypy Errors | 200+ |
| Dead Modules | 1 confirmed (`memory_bank.py`), 9 compat shims |
| Star-Import Only | 17 modules |
| Duplicate Systems | 2 memory systems coexisting |

**Recommendation:** Run auto-fixes first, then address mypy errors module-by-module starting with highest-error files. Remove `memory_bank.py` dead code after verifying no tests depend on it.