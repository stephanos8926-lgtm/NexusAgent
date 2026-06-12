# TUI Deep Audit — NexusAgent

> Generated: 2026-07-19
> Scope: Complete TUI subsystem runtime behavior analysis
> Source: tui.py (953L), tui_widgets.py (231L), tui_formatters.py (296L), widgets/ (dead code)

---

## 1. Confirmed Bugs (Runtime)

### BUG-1: Fake Streaming (CRITICAL)
**File**: tui.py L819-824, L826-844
**Symptom**: Tokens accumulate in `_streaming_response` string via `_write_response_chunk()`, then the entire accumulated text is written to the log as a single event in `_finalize_response()`. The `_streaming_widget` (a Static widget) shows partial text, but it's updated via `self._streaming_widget.update()` which replaces the whole content each time — this is O(n²) string concatenation + full widget repaint per token.

**Root cause**: `_write_response_chunk()` does `self._streaming_response += content` then calls `update()` on the Static widget with the full accumulated string. Each token triggers a full repaint of all previous tokens.

**Fix approach**: 
1. Use a `Static` widget per streaming response (not shared with log)
2. Use `widget.update()` with only the NEW token appended via RichLog markup
3. Or better: mount a new AssistantMessage widget that uses `append_token()` pattern (already exists in widgets/messages/assistant.py — dead code)

**Severity**: CRITICAL — this is the #1 user complaint

### BUG-2: Word Wrapping (HIGH)
**File**: tui.py L115-126 (CSS)
**Symptom**: `text-wrap: wrap` and `word-wrap: break-word` are set on `#conversation-log` RichLog, but long URLs, file paths, and code blocks still overflow horizontally.

**Root cause**: RichLog's `wrap=True` parameter should handle this, but the CSS `overflow-x: hidden` clips content instead of wrapping. The `max-width: 100%` constraint may not be respected by RichLog's internal rendering.

**Fix approach**: 
1. Verify RichLog `wrap=True` is working (test with `textual` version)
2. Add `overflow-x: auto` as fallback for horizontal scroll
3. Consider replacing RichLog with individual Static widgets that naturally wrap

**Severity**: HIGH — affects readability

### BUG-3: Tool Call Display (MEDIUM)
**File**: tui.py L430-444
**Symptom**: Tool call arguments show raw JSON-like output instead of formatted values.

**Root cause**: `format_arg_value()` (L267-276 of tui_formatters.py) does basic truncation but doesn't handle nested dicts, lists, or special types well. The RichLog markup `[yellow]{k}[/yellow]=[white]{v}[/white]` can break if `v` contains RichLog markup characters (`[`, `]`).

**Fix approach**:
1. Apply `_escape()` to all argument values before writing to RichLog
2. Handle nested structures with indentation
3. Truncate individual values more aggressively

**Severity**: MEDIUM — cosmetic but affects usability

### BUG-4: Greeting Race Condition (MEDIUM)
**File**: tui.py L266-289 (on_mount), L339-367 (_show_greeting)
**Symptom**: Greeting may not render because `_show_greeting()` writes to `log_widget` (RichLog) before the WebSocket connection is established, and `/clear` command clears the log immediately after writing the greeting.

**Root cause**: `on_mount()` calls `_show_greeting()` at L288, then starts `_ws_loop()` at L289. If the WS connection fails, the error message overwrites the greeting. Also, `_show_greeting()` writes 7 separate lines to RichLog which can be slow.

**Fix approach**:
1. Make greeting a single Static widget (not RichLog writes)
2. Auto-remove greeting when first real event arrives
3. Or buffer greeting until WS connection confirmed

**Severity**: MEDIUM — affects first impression

### BUG-5: Status Bar Minimal (LOW)
**File**: tui.py L243-257 (compose)
**Symptom**: Status bar is a single SpinnerLabel showing "Ready" or "Thinking...". No model name, CWD, branch, or token count visible.

**Fix approach**: Integrate the existing `StatusBar` widget from `widgets/status.py` (currently dead code) or build a new one inline.

**Severity**: LOW — feature gap, not a bug

### BUG-6: Header + Footer Waste Screen Space (MEDIUM)
**File**: tui.py L243-257 (compose)
**Symptom**: Header widget (1 line) + Footer widget (1 line) + auto-approve badge (1 line) + queue status (1 line) = 4 lines of chrome. On a 24-line terminal, that's 17% of screen real estate.

**Fix approach**: Remove Header and Footer entirely. Move key hints to status bar or a `?` help screen.

**Severity**: MEDIUM — affects chat real estate

### BUG-7: No Semantic Color System (LOW)
**File**: tui.py L101-241 (CSS)
**Symptom**: All colors are hardcoded hex codes (`#111827`, `#1f2937`, `#10b981`, etc.). No CSS variables, no semantic tokens. The `widgets/theme/` package has a full semantic system but it's dead code.

**Fix approach**: Use the existing `widgets/theme/` system (7 themes, 18 semantic tokens each) and register_themes().

**Severity**: LOW — architectural debt

### BUG-8: ErrorModal Imported But Never Used (LOW)
**File**: tui.py L54 (import), tui_widgets.py L216-231 (class)
**Symptom**: `ErrorModal` is imported in tui.py but never instantiated or pushed as a screen.

**Fix approach**: Either use it for error display or remove the import.

**Severity**: LOW — dead code

---

## 2. Architecture Issues

### ARCH-1: widgets/ Package Is Dead Code
**Scope**: All 12 files in `widgets/` package
**Finding**: The entire `widgets/` package (messages/, status.py, chat_input.py, theme/) is defined but never imported or used by NexusApp. NexusApp composes its own UI inline using basic Textual primitives.

**Impact**: ~1,200 lines of designed-but-unintegrated code. The widgets include:
- Better message rendering (UserMessage, AssistantMessage, ToolCallMessage)
- Rich status bar (StatusBar with CWD, branch, tokens, model)
- Theme system (7 themes, 18 semantic tokens)
- Better chat input (history, autocomplete)

**Fix approach**: Integrate the widgets/ package into NexusApp. This is the single highest-impact architectural improvement.

### ARCH-2: RichLog Monolith
**File**: tui.py L245-247
**Finding**: All messages (user, agent, tool calls, errors) are written to a single RichLog widget. This means:
- No individual message styling (all same format)
- No per-message interactivity (can't click to expand/collapse individual messages)
- No per-message timestamps
- Scrolling performance degrades as messages accumulate

**Fix approach**: Replace RichLog with a Container(layout="stream") of individual Static widgets. The `widgets/messages/` package already has these classes.

### ARCH-3: No Message Types
**File**: tui.py L416-507 (_handle_event)
**Finding**: All events are rendered as plain text in RichLog. There's no distinction between message types at the widget level — user messages, agent responses, tool calls, and errors all look similar.

**Fix approach**: Use different widget classes for each message type (already defined in widgets/messages/).

---

## 3. Performance Issues

### PERF-1: O(n²) Streaming (CRITICAL)
**File**: tui.py L820-824
**Issue**: `self._streaming_response += content` creates a new string on every token. For a 1000-token response, this is ~500K string copies.

### PERF-2: RichLog Growth (MEDIUM)
**File**: tui.py L245-247
**Issue**: RichLog accumulates all messages. After 100+ messages, scrolling and rendering slow down.

### PERF-3: No Virtual Scrolling (LOW)
**File**: tui.py L245-247
**Issue**: All messages are rendered in the DOM. No virtualization means memory grows with conversation length.

---

## 4. Missing Features (vs. DeepAgents CLI)

| Feature | DeepAgents | NexusAgent | Gap |
|---------|-----------|------------|-----|
| Token-by-token streaming | ✅ | ❌ (fake) | CRITICAL |
| Per-message styling | ✅ | ❌ | HIGH |
| Collapsible tool output | ✅ | ✅ (Collapsible) | NONE |
| Status bar with model/CWD | ✅ | ❌ | HIGH |
| Theme system (7+ themes) | ✅ (2) | ✅ (5, hardcoded) | MEDIUM |
| Semantic color tokens | ✅ | ❌ | MEDIUM |
| Message timestamps | ✅ | ✅ (partial) | LOW |
| Markdown rendering | ✅ | ✅ (basic) | LOW |
| Image display | ✅ | ❌ | MEDIUM |
| Log viewer | ✅ | ❌ | LOW |
| Command palette | ✅ | ❌ | LOW |
| Multi-panel layout | ❌ | ❌ | N/A |

---

## 5. Recommended Fix Priority

| Priority | Bug/Arch | Effort | Impact |
|----------|----------|--------|--------|
| P0 | BUG-1: Fake streaming | Medium | CRITICAL |
| P0 | BUG-6: Header/Footer removal | Low | HIGH |
| P1 | BUG-2: Word wrapping | Low | HIGH |
| P1 | BUG-3: Tool call display | Low | MEDIUM |
| P1 | BUG-4: Greeting race condition | Low | MEDIUM |
| P1 | ARCH-1: Integrate widgets/ | High | CRITICAL |
| P2 | BUG-5: Status bar | Medium | MEDIUM |
| P2 | BUG-7: Semantic colors | Medium | LOW |
| P2 | ARCH-2: Replace RichLog | High | HIGH |
| P3 | PERF-1: O(n²) streaming | Low | CRITICAL (same as BUG-1) |
| P3 | BUG-8: ErrorModal cleanup | Low | LOW |
| P3 | ARCH-3: Message types | High | MEDIUM |

---

## 6. Test Impact Assessment

| Change | Existing Tests Affected | New Tests Needed |
|--------|----------------------|------------------|
| Streaming fix | test_tui_streaming.py, test_tui_bug_fixes.py | Test token-by-token rendering |
| Header/Footer removal | test_tui_streaming.py (compose test) | Test new compose() structure |
| Word wrapping | test_tui_bug_fixes.py (word wrapping test) | Test with various text lengths |
| widgets/ integration | None (widgets are new) | Test all widget classes |
| Status bar | None | Test StatusBar rendering |
| Theme system | test_tui_theme.py | Test new theme integration |
| RichLog replacement | test_tui_streaming.py, many others | Test individual message widgets |

**Baseline**: 475 pass / 20 fail (pre-existing). Must maintain 475+ pass after all changes.
