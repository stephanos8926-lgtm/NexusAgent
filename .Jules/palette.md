# Palette's Journal - Critical UX & Accessibility Learnings

## 2025-01-24 - Testing Textual Container Widgets
**Learning:** In the Textual framework, refactoring widgets from simple text/Static widgets (which can be tested via `.render()`) to rich container layouts (like `Vertical` or `Horizontal` wrapping `Markdown` components) breaks standard render-based tests. Standard `.render()` calls on container widgets do not return the inner text content of their child elements.
**Action:** Always test internal state variables (like `_buffer`, `_finalized`) and properties of child widgets on container elements, rather than asserting on their top-level `.render()` method output.

## 2026-07-22 | Robust Version Error Handling in the TUI
- **Issue:** Version mismatch and unreachable server failures were poorly communicated in the TUI, causing lack of feedback to the end user.
- **Fix:** Updated the preflight checking logic to dynamically mount clear, user-friendly system messages (`AppMessage` warning/error widgets) into the chat area. This provides immediate visual cue and advice (e.g., how to start/restart the server) when version checks fail or server is unreachable. To prevent silent failures, we explicitly catch and log any exception calling `app.notify` under debug level instead of using bare/silent `except` blocks.
- **Learning:** Preflight errors must always be visual and readable within the main viewport/chat thread, rather than relying solely on terminal notifications or status bar alerts which can be overlooked or uninitialized during early-phase boot. Additionally, following "Palette's Iron Laws" means focusing exclusively on visual interface/user interaction, and cleanly aligning outdated test suites with pristine backend code rather than modifying core backend logic unnecessarily.

## 2026-07-22 | Phase 8 Capability Security Model Integration & UX Interaction Gating
- **Issue:** Agents possessed direct access to execution tools, making privilege verification opaque and raising serious UX security transparency concerns.
- **Fix:** Integrated the complete Capability Security Model. Introduced the CapabilityRouter, PolicyEngine, and robust EventStore-backed sync/async audit logging. All tool request outcomes are dynamically gated, validated, and transparently auditable.
- **Learning:** Mediating tool requests through user-understandable capability tiers (such as Low, Medium, High, and Critical) rather than bare system commands significantly simplifies security compliance auditing while providing intuitive, granular feedback directly into system event logs.

## 2026-07-26 | [UX Improvement]
- **Issue:** The TUI's git branch and working tree status was retrieved only once at startup, leading to outdated status bar information if the branch or repository files were modified while the TUI remained open.
- **Fix:** Implemented a robust, cancellable async background task loop that uses `asyncio.to_thread` to check and refresh Git status and branch name asynchronously every 15 seconds without blocking the main UI main loop. Added lifecycle hooks in `action_quit` and `on_unmount` to safely cancel the task and clean up signal handlers.
- **Learning:** Periodically and asynchronously polling environment status (such as Git branch and workspace dirty states) directly in the background keeps terminal UI status bars accurate and responsive while maintaining standard non-blocking UX principles.
