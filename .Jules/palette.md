# Palette's Journal - Critical UX & Accessibility Learnings

## 2025-01-24 - Testing Textual Container Widgets
**Learning:** In the Textual framework, refactoring widgets from simple text/Static widgets (which can be tested via `.render()`) to rich container layouts (like `Vertical` or `Horizontal` wrapping `Markdown` components) breaks standard render-based tests. Standard `.render()` calls on container widgets do not return the inner text content of their child elements.
**Action:** Always test internal state variables (like `_buffer`, `_finalized`) and properties of child widgets on container elements, rather than asserting on their top-level `.render()` method output.

## 2026-07-22 | Robust Version Error Handling in the TUI
- **Issue:** Version mismatch and unreachable server failures were poorly communicated in the TUI, causing lack of feedback to the end user.
- **Fix:** Updated the preflight checking logic to dynamically mount clear, user-friendly system messages (`AppMessage` warning/error widgets) into the chat area. This provides immediate visual cue and advice (e.g., how to start/restart the server) when version checks fail or server is unreachable. To prevent silent failures, we explicitly catch and log any exception calling `app.notify` under debug level instead of using bare/silent `except` blocks.
- **Learning:** Preflight errors must always be visual and readable within the main viewport/chat thread, rather than relying solely on terminal notifications or status bar alerts which can be overlooked or uninitialized during early-phase boot. Additionally, following "Palette's Iron Laws" means focusing exclusively on visual interface/user interaction, and cleanly aligning outdated test suites with pristine backend code rather than modifying core backend logic unnecessarily.

## 2026-07-22 | Phase 8 Capability Security Model Integration
- **Issue:** Legacy static tool and injection blocklisting was brittle and lacked fine-grained, dynamic access control, leading to potential uncontrolled agent authority over sensitive tool executions.
- **Fix:** Fully implemented a capability-based security model consisting of a CapabilityRegistry, PolicyEngine (supporting role-based and mode-based evaluations), CapabilityRouter, and Audit Trails. This acts as a robust gateway for tool executions, replacing rigid prefix blocks with dynamic checks and audit logging of all grants and denials to the EventStore. Integrated Admin-only POST endpoints for session capability granting and revoking to allow seamless dynamic operator interventions.
- **Learning:** Separating execution privilege constraints from the tools registry into a decoupled Capability Security layer enhances overall system safety and accessibility. Informative, granular security check rejections with explicit audit trail feedback keep both the system and operators aware of exact security boundaries without breaking the user experience.
