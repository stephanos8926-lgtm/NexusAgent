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

## 2026-07-26 | Interactive Keyboard Accessibility in TUI Messages
- **Issue:** The `ToolCallMessage` widget displayed collapsible tool results but was not focusable by keyboard-only or screen-reader users, preventing them from expanding/collapse outputs.
- **Fix:** Configured `can_focus = True` on `ToolCallMessage`, added visual `:focus` styles using `$primary` border and `$boost` background, assigned a user-friendly tooltip, and handled Enter/Space keys to toggle collapse.
- **Learning:** Accessibility must be baked into custom container elements from the start. Making interactive elements focusable with visual feedback and intuitive keystroke handlers ensures that all developers and users can navigate logs easily.

## 2026-07-26 | [UX Improvement]
- **Issue:** The TUI's git branch and working tree status was retrieved only once at startup, leading to outdated status bar information if the branch or repository files were modified while the TUI remained open.
- **Fix:** Implemented a robust, cancellable async background task loop that uses `asyncio.to_thread` to check and refresh Git status and branch name asynchronously every 15 seconds without blocking the main UI main loop. Added lifecycle hooks in `action_quit` and `on_unmount` to safely cancel the task and clean up signal handlers.
- **Learning:** Periodically and asynchronously polling environment status (such as Git branch and workspace dirty states) directly in the background keeps terminal UI status bars accurate and responsive while maintaining standard non-blocking UX principles.

## 2026-07-30 | [UX Improvement]
- **Issue:** The TUI's expand-all (`/expand`, `/e`) and collapse-all (`/collapse`, `/a`) slash commands were stubbed out as no-op placeholders returning `True` without performing any actual actions on the mounted tool call widgets.
- **Fix:** Wired the `/expand`, `/e`, `/collapse`, and `/a` slash commands directly to the core TUI `NexusApp` actions `action_expand_all()` and `action_collapse_all()`, completely resolving the legacy TODO. Added a comprehensive suite of unit tests verifying correct integration and toggle-state propagation.
- **Learning:** Slash commands and global keyboard hotkeys representing the same intent should always delegate to the exact same core action handler. Centralizing this invocation path prevents divergence in UX behavior and simplifies automated unit testing of visual interface state transitions.

## 2026-08-02 | [UX Improvement]
- **Issue:** TUI themes could only be cycled sequentially via keyboard and lacks a direct selection command or a visual grid preview, and the context window usage bar used static color constants instead of active theme design tokens.
- **Fix:** Implemented direct theme selection in the `/theme` command with automatic string normalization, and a new `/theme-preview` slash command that displays a visual grid of registered themes with active indicators. Updated `ContextWindowBar` and `StatusBar` to dynamically map context bar colors using active theme design tokens (`success`, `warning`, `error` from `ThemeColors`).
- **Learning:** Supporting direct, normalized selection parameters and visual theme preview grids adds massive user delight and clarity, while mapping colors to design tokens guarantees visual coherence across themes.

## 2026-08-04 | [UX Improvement]
- **Issue:** The `/copy` slash command was previously a stub ("Copy not available"), requiring users to manually highlight and select terminal text, and standard TUI message widgets (`AssistantMessage`, `UserMessage`, `ErrorMessage`, `AppMessage`) lacked keyboard focusability and screen-reader tooltips, reducing accessibility compliance.
- **Fix:** Implemented the full `/copy` and `/c` slash commands in the TUI to retrieve the last assistant response and copy it to the system clipboard using Textual's `copy_to_clipboard()`. Set `can_focus = True` on all message widgets, defined clear focus visual styles via `:focus` rules with background `$boost` or corresponding borders, and configured accessible screen-reader tooltips.
- **Learning:** Providing quick keyboard shortcuts for clipboard copy operations enormously boosts developer productivity, and baking focus states and tooltips directly into custom TUI container elements ensures high-standard WCAG/a11y compliance.
