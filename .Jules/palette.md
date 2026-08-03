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
- **Issue:** The `ToolCallMessage` widget displayed collapsible tool results but was not focusable by keyboard-only or screen-reader users, preventing them from expanding/collapsing outputs.
- **Fix:** Configured `can_focus = True` on `ToolCallMessage`, added visual `:focus` styles using `$primary` border and `$boost` background, assigned a user-friendly tooltip, and handled Enter/Space keys to toggle collapse.
- **Learning:** Accessibility must be baked into custom container elements from the start. Making interactive elements focusable with visual feedback and intuitive keystroke handlers ensures that all developers and users can navigate logs easily.

## 2026-07-26 | [UX Improvement]
- **Issue:** The TUI's git branch and working tree status was retrieved only once at startup, leading to outdated status bar information if the branch or repository files were modified while the TUI remained open.
- **Fix:** Implemented a robust, cancellable async background task loop that uses `asyncio.to_thread` to check and refresh Git status and branch name asynchronously every 15 seconds without blocking the main UI main loop. Added lifecycle hooks in `action_quit` and `on_unmount` to safely cancel the task and clean up signal handlers.
- **Learning:** Periodically and asynchronously polling environment status (such as Git branch and workspace dirty states) directly in the background keeps terminal UI status bars accurate and responsive while maintaining standard non-blocking UX principles.

## 2026-07-26 | [UX Improvement]
- **Issue:** Selecting specific themes or discovering available themes in the TUI required repetitive cycling (using Ctrl+T or parameter-less `/theme` command), which is slow and inaccessible for users with specific contrast requirements.
- **Fix:** Updated `/theme` slash command to support direct theme switching (e.g. `/theme tokyo night` or `/theme catppuccin_mocha` handles spaces and underscores using hyphen normalization), falling back to listing available options on mismatch. Implemented the unhandled `/theme-preview` slash command to display a beautiful visual swatch grid showing Accent, Background, and Text color block previews for all 7 themes using dynamic hex values from `THEME_REGISTRY`, complete with an active theme indicator.
- **Learning:** Giving users direct command access and visual color swatch previews significantly enhances usability, accessibility, and visual discoverability of user themes in terminal applications.