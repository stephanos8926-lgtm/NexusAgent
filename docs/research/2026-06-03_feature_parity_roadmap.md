# NexusAgent Feature Parity Roadmap
Date: 2026-06-03

## Goal
Transition NexusAgent from a functional prototype to a professional-grade AI software engineering agent capable of handling complex, multi-file projects with high autonomy and reliability.

## Implementation Phases

### Phase A: The "Awareness" Layer (Immediate)
*   **Project Constitution:** Implement a `NEXUS.md` standard. The agent must read this at the start of every session to ground its situational awareness.
*   **JIT Retrieval:** Transition from whole-file reading to "Just-In-Time" retrieval using `grep`, `glob`, and symbol mapping (Tree-sitter) to reduce context bloat.
*   **Context Compaction:** Implement a `/compact` mechanism to summarize session history and reclaim token space.

### Phase B: The "Execution" Layer (Short-Term)
*   **Plan-Driven Workflow:** Implement a mandatory `Plan -> Review -> Execute` loop for complex tasks.
*   **Sandbox Isolation:** Move NATS workers into Docker containers to ensure system security.
*   **Automated Verification:** Integrate a "Test-Check-Fix" loop where the agent must verify its changes against the project's test suite before completion.

### Phase C: The "Advanced" Layer (Long-Term)
*   **Subagent Orchestration:** Implement a system of specialized sub-workers (e.g., Research, Testing, Documentation) coordinated via the NATS bus.
*   **MCP Integration:** Adopt the Model Context Protocol (MCP) to connect to external data sources (GitHub, Jira, Slack).
*   **High-Fidelity Memory:** Integrate a semantic memory graph to maintain long-term project knowledge across sessions.
