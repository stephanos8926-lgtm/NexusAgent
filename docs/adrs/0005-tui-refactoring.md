# ADR 0005: TUI Module Split — interfaces/tui.py Refactoring

> Status: Accepted
> Date: 2026-07-18
> Deciders: OWL (Lucien) + Steven Page
> References: CODEBASE_MAP.md, SEMANTIC_INDEX.md, REFACTORING_PLAN.md

## Context

`interfaces/tui.py` grew to 1,433 lines containing 5 classes and 58 functions. It mixed:
- The main `NexusApp` application class (lifecycle, event handling, slash commands)
- Widget definitions (SpinnerLabel, ApprovalModal, ErrorModal)
- Responsive layout utilities (Breakpoint, SIGWINCH handling, terminal size)
- All output formatters (12 `_format_*` methods)
- Two redundant markdown renderers (`_simple_markdown` + `_enhanced_markdown`)

This violated single-responsibility, made testing difficult, and was the source of multiple reported bugs (fake streaming, broken word wrapping, raw JSON display).

## Decision

Split `tui.py` into three focused modules:

```
interfaces/
├── tui.py              (953L) — NexusApp, lifecycle, events, slash commands, actions
├── tui_widgets.py      (231L) — SpinnerLabel, Breakpoint, modals, SIGWINCH, terminal
└── tui_formatters.py   (296L) — render_markdown(), all formatters, truncation, escaping
```

### Key design choices:

1. **Merged markdown renderers**: `_simple_markdown` + `_enhanced_markdown` → single `render_markdown(text, *, code_blocks=True)` with a mode flag. Eliminates redundancy and inconsistency.

2. **Single source of truth for SPINNER_CHARS**: Defined in `tui_widgets.py`, exported as `SPINNER_CHARS`. Both `SpinnerLabel` and `StatusBar` (in `widgets/status.py`) use the same constant.

3. **Zero interface changes**: `from nexusagent.interfaces.tui import NexusApp, main` continues to work. The `interfaces/__init__.py` re-exports these symbols.

4. **Formatter extraction**: All `_format_*` methods moved to `tui_formatters.py` as standalone functions. `NexusApp` calls them via imports rather than method calls. This makes formatters independently testable.

5. **Widget extraction**: `SpinnerLabel`, `ApprovalModal`, `ErrorModal`, `Breakpoint`, and all SIGWINCH/terminal utilities moved to `tui_widgets.py`. These are pure UI concerns with no business logic.

## Consequences

### Positive
- `tui.py` reduced from 1,433L to 953L (33% reduction)
- Each extracted module is independently testable
- Formatters can be unit-tested without instantiating NexusApp
- Widget styling changes don't require touching event handling code
- New formatters can be added to `tui_formatters.py` without modifying `tui.py`

### Negative
- Cross-module imports add slight complexity (formatters imported into tui.py)
- Debugging requires jumping between 3 files instead of 1
- `tui.py` still at 953L — could benefit from further extraction of slash commands

### Risks
- **Mitigated**: All existing import paths preserved via `__init__.py` re-exports
- **Mitigated**: Full test suite passes (475/475 relevant tests)
- **Mitigated**: No behavior changes — pure structural refactoring

## Alternatives Considered

1. **Full subpackage** (`interfaces/tui/` with `app.py`, `widgets.py`, `formatters.py`, `commands.py`): More granular but over-engineered for current needs. Can be done incrementally.

2. **Keep as-is with section markers**: Would not solve the testing and complexity problems.

3. **Extract only formatters**: Would leave widgets and modals in the monolith. Partial improvement.

## Related
- CODEBASE_MAP.md — Full module dependency graph
- SEMANTIC_INDEX.md — Semantic architecture index
- REFACTORING_PLAN.md — 14-item prioritized refactoring plan
- ADR 0002: Project Structure and Build Modes
- ADR 0004: Documentation Standards
