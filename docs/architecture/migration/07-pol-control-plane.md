# Phase 6 — Platform Orchestration Layer

## Objective

Create a persistent AI governance layer that oversees all agent activity.

## POL Responsibilities

- **Policy decisions** — evaluate and enforce operational boundaries
- **Worker monitoring** — track health, progress, and failure rates
- **Intervention** — inject system-level guidance when anomalies are detected
- **Remediation** — coordinate recovery from failures and escalations
- **Approval handling** — approve or deny high-risk operations

## POL Architecture

```
POL
 |
 Event Stream
 |
 Workers
```

POL is not another worker. It is a persistent background control-plane agent that subscribes to the event stream and reacts to system events.

## POL Messages

POL communicates through **structured system messages**, never through normal chat.

```json
{
    "type": "system_intervention",
    "source": "POL",
    "priority": "high",
    "reason": "repeated_tool_failure",
    "guidance": "Review dependency conflict before retrying"
}
```

## Implementation Steps

### Step 1 — Create POL service

A persistent daemon that subscribes to the event backbone (NATS) and runs alongside the gateway. It has no user-facing interface — it operates entirely through events and system messages.

### Step 2 — Create policy engine

A rules-based evaluator that determines whether actions are permitted. Rules are organized by:

| Domain | Example |
|--------|---------|
| Execution | "No shell commands outside workspace" |
| Network | "Only allowlisted endpoints" |
| Memory | "No deletion of semantic memories" |
| Tools | "MCP tools require TOOL_EXTERNAL trust level" |

### Step 3 — Create intervention protocol

When POL detects an anomaly (repeated failures, policy violations, resource exhaustion), it injects a `system_intervention` event into the session or worker's event stream. The recipient must acknowledge and adjust behavior.

### Step 4 — Create escalation system

If a worker fails and cannot recover, POL escalates:

1. Notify the orchestrator to re-dispatch
2. If the orchestrator also fails, notify the user
3. If the task is critical, invoke a human-in-the-loop approval

## Completion Criteria

- [ ] Workers can operate safely without constant human supervision
- [ ] Policy violations are detected and blocked in real-time
- [ ] POL interventions are observable in the event log
- [ ] Escalation paths are well-defined and tested