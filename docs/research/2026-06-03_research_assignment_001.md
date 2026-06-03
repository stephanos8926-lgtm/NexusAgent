# AI Software Engineering Agent Research - Assignment 001
Date: 2026-06-03

## Overview
Investigation into the current landscape of AI software engineering agents (2025-2026), analyzing the most prominent autonomous and semi-autonomous tools.

## Comparative Analysis

| Agent | Archetype | Open Source | Autonomy | Primary Interface | Best For... |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Devin** | Autonomous | No | Very High | Web Dashboard | Fully offloading well-defined tasks. |
| **OpenHands** | Autonomous | **Yes** | High | Web UI / CLI | Enterprise-grade open-source autonomy. |
| **SWE-agent** | Autonomous | **Yes** | High | CLI / API | Research-grade precision & ACI efficiency. |
| **Aider** | CLI-Native | **Yes** | Medium | Terminal | Git-centric, rapid pair programming. |
| **Plandex** | CLI-Native | **Yes** | Medium | Terminal | Complex, multi-step planning & execution. |
| **Claude Code**| CLI-Native | No | High | Terminal | Deep reasoning & multi-file refactors. |
| **Cursor** | IDE-Native | No | Medium/High | VS Code Fork | Daily feature work & visual editing. |

## Key Technical Insights

### 1. The ACI (Agent-Computer Interface)
A critical finding from SWE-agent is that the **interface is more important than the model**. Specialized ACIs reduce cognitive load on the LLM, consolidating complex operations and filtering noisy terminal output.

### 2. Context Window Management
- **Repo Mapping:** Aider and Plandex use Tree-sitter to index codebases, creating a "bird's-eye view" (symbol maps) that allows the AI to understand project structure without reading every file.
- **Staging/Sandboxing:** Plandex uses a diff-based sandbox to stage changes before applying them to the filesystem.

### 3. Autonomy Loops
- **CodeAct Loop:** OpenHands employs a "Reasoning $\rightarrow$ Execution $\rightarrow$ Observation" cycle, allowing the agent to self-correct based on real-time execution errors.

## NexusAgent Strategic Fit
NexusAgent's unique edge is its **distributed NATS-based worker architecture**. While other tools are mostly synchronous loops, NexusAgent is a distributed system.

**Recommended Evolutions:**
- Implement an ACI-inspired SDK.
- Integrate Tree-sitter for project mapping.
- Move worker execution into Docker sandboxes for security.
