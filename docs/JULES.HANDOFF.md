# Jules Handoff — TUI `/collapse` Command Implementation

**Branch:** `jules/tui-collapse-all`
**File:** `src/nexusagent/interfaces/tui/streaming.py`
**Line:** ~358

---

## The Issue

Current `/collapse` command at line 358 is a stub:

```python
if command in ("/collapse", "/a"):
    return True  # TODO: collapse all
```

It returns `True` but does nothing — no widget collapse happens.

---

## What Needs to Happen

1. **Find all expandable widgets** in the current view (messages, code blocks, etc.)
2. **Collapse each one** programmatically
3. **Show confirmation** to user (e.g., "Collapsed 3 items")

---

## Architecture Context

- **App class:** `NexusApp` in `src/nexusagent/interfaces/tui/app.py`
- **Messages:** `_mount_with_limit()` creates message widgets that can expand/collapse
- **Expand mechanism:** Messages likely have `.expanded` attribute or similar
- **Auto-expand:** See `/expand` handler at line 355-356 (`return True  # Widgets auto-expand`)

---

## Search for Existing Expand/Collapse Logic

```bash
# Search for expand/collapse in TUI
grep -rn "expand\|collapse\|expanded" src/nexusagent/interfaces/tui/ --include="*.py"
```

Key files to check:
- `src/nexusagent/interfaces/tui/app.py` — main app, widget management
- `src/nexusagent/interfaces/tui/streaming.py` — message rendering
- `src/nexusagent/interfaces/tui/widgets/` — if exists

---

## Implementation Notes

1. **Access the app:** The command handler receives `app` (NexusApp instance)
2. **Find collapsible widgets:** Likely need to walk `app.query("MessageWidget")` or similar
3. **Collapse method:** Check if widgets have `.collapse()`, `.set_expanded(False)`, or `.expanded = False`
4. **User feedback:** Use `_mount_with_limit(app, AppMessage("Collapsed N items"))`

---

## Testing

1. Run TUI: `python -m nexusagent.interfaces.tui.app`
2. Send some long messages that auto-expand
3. Run `/collapse` — all should collapse
4. Run `/expand` — all should expand back

---

## Acceptance Criteria

- [ ] `/collapse` (or `/a`) collapses all expanded message widgets
- [ ] `/expand` (or `/e`) expands all collapsed widgets
- [ ] User feedback shows count of items collapsed/expanded
- [ ] No regression in existing `/expand` behavior
- [ ] Works with mixed expanded/collapsed state