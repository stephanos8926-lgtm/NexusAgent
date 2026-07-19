# Palette's Journal - Critical UX & Accessibility Learnings

## 2025-01-24 - Testing Textual Container Widgets
**Learning:** In the Textual framework, refactoring widgets from simple text/Static widgets (which can be tested via `.render()`) to rich container layouts (like `Vertical` or `Horizontal` wrapping `Markdown` components) breaks standard render-based tests. Standard `.render()` calls on container widgets do not return the inner text content of their child elements.
**Action:** Always test internal state variables (like `_buffer`, `_finalized`) and properties of child widgets on container elements, rather than asserting on their top-level `.render()` method output.
