# TUI Partial Extraction Reference

> Saved from earlier subagent attempt (2026-07-18).
> These files are reference only — do NOT import from them.
> The tui.py extraction will start fresh from the original 1433-line monolith.

## What was extracted

### breakpoints.py (119 lines)
- `Breakpoint` enum: WIDE (>120), STANDARD (80-120), NARROW (60-79), TOO_SMALL (<60)
- `classify_breakpoint(width)` — maps column count to breakpoint
- `debounce_resize(state, current_time, debounce_seconds=0.2)` — SIGWINCH debounce
- `_sigwinch_handler(app)` — updates breakpoint, notifies on too-small
- `_get_terminal_size()` — shutil.get_terminal_size() with fallback (80, 24)
- Threshold constants: `_WIDE_THRESHOLD=120`, `_STANDARD_THRESHOLD=80`, `_NARROW_THRESHOLD=60`

### modals.py (107 lines)
- `SpinnerLabel(Horizontal)` — animated braille spinner + text
  - `set_text(text, spinning)` — updates text and spinner state
  - `_tick_spinner()` — increments tick counter
  - `update_display()` — refreshes Static widgets
- `ApprovalModal(ModalScreen[bool])` — tool call approval dialog
  - Shows tool name, args, approve/reject/cancel buttons
- `ErrorModal(ModalScreen[None])` — error display dialog
  - Shows error message, OK button

### helpers.py (18 lines)
- `NO_COLOR: bool` — module-level, checks `"NO_COLOR" in os.environ`
- `is_no_color()` — returns True if NO_COLOR is set

## Key patterns to preserve in fresh extraction
- Module-level `NO_COLOR` constant (not just function)
- `debounce_resize()` takes a mutable state dict
- `_sigwinch_handler(app)` accesses `app._resize_state`, `app._breakpoint`, `app.notify()`
- ApprovalModal and ErrorModal share `id="approval-dialog"` CSS ID (same styling)
- SpinnerLabel uses `query_one("#spinner-icon", Static)` to update child widgets
