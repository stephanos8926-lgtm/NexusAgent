# Multi-Agent System

## Overview

NexusAgent supports dynamic multi-agent parallelism. Parent agents can spawn specialized sub-agents that run concurrently.

## Agent Spawning

```python
from nexusagent.agent import Agent

# Spawn a coder sub-agent
coder = Agent(role="coder", policy="restricted")

# Spawn a tester sub-agent
tester = Agent(role="tester", policy="restricted")

# Spawn a reviewer sub-agent
reviewer = Agent(role="reviewer", policy="strict")
```

## Memory Slicing

When spawning a child agent, only relevant context is transferred:

1. **Keyword matching**: Score memory items by relevance to subtask
2. **Dependency scoring**: Include items that reference the same symbols
3. **Temporal recency**: Prefer recent context
4. **Semantic similarity**: Use embedding similarity (future)

This reduces memory overhead by ~42% compared to full context transfer.

## Conflict Resolution

When multiple agents edit the same files:

1. **Automatic merge**: Non-overlapping changes
2. **Semantic merge**: LLM reconciles intent-compatible overlaps
3. **Parent escalation**: Contradictory edits go to parent for judgment

## Thread Safety

Each agent's policy context is stored in thread-local storage, so parent and sub-agents can run concurrently without interfering with each other.
