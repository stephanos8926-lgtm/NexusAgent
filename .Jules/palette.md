# Palette's Journal - Critical UX & Accessibility Learnings

## 2025-01-24 - Testing Textual Container Widgets
**Learning:** In the Textual framework, refactoring widgets from simple text/Static widgets (which can be tested via `.render()`) to rich container layouts (like `Vertical` or `Horizontal` wrapping `Markdown` components) breaks standard render-based tests. Standard `.render()` calls on container widgets do not return the inner text content of their child elements.
**Action:** Always test internal state variables (like `_buffer`, `_finalized`) and properties of child widgets on container elements, rather than asserting on their top-level `.render()` method output.

## 2026-07-22 | [TUI Robustness, Safety, and User-Feedback Polish]
- **Issue:** Several critical edge cases in the Textual-based TUI client could cause soft-bricks (stuck `_busy` state on disconnected WebSockets), duplicate approvals/renderings for same-ID tool calls, uninformative connection failure reporting, and client-side memory exhaustion via unbounded message inputs or spamming.
- **Fix:** Wrapped `ws_loop` in an outer `try-finally` block to reset busy/spinner state reliably. Added persistent connection and mismatch messages in the chat. Implemented `_seen_tool_calls`, `_seen_tool_results`, and `_approved_call_ids` to deduplicate events and approvals. Added call-ID to tool mapping to prevent unknown/placeholder (`"?"`) tool names when the current tool reference is missing. Added client-side message size limit of 32KB.
- **Learning:** Textual apps running async websocket event loops can easily end up with desynchronized client-server state when connections are dropped or task cancellation is triggered. Guaranteeing cleanup of state-machine trackers (busy states, loading animations, active assistant/tool refs) in the topmost `try-finally` block of the WebSocket connection task is essential to prevent permanent UI locks.
