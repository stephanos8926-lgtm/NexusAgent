# Phase 7 — Capability Security Model

## Objective

Prevent uncontrolled agent authority by replacing direct tool access with capability-based execution.

## Replace

```
Agent → Tool
```

## With

```
Agent → Capability Request → Policy → Tool
```

## Capabilities

Every privileged operation is modeled as a capability:

| Capability | Scope | Risk Level |
|------------|-------|------------|
| `filesystem.read` | Workspace directory | Low |
| `filesystem.write` | Workspace directory | Medium |
| `execute.tests` | Project workspace | Low |
| `git.commit` | Current repository | High |
| `network.access` | Allowlisted endpoints | High |
| `shell.execute` | Workspace directory | Critical |

## Capability Requirements

Every capability must define:

- **Scope** — what resources it can access
- **Permissions** — read, write, execute, admin
- **Risk level** — low, medium, high, critical
- **Audit logging** — every capability request is logged

## Implementation Steps

### Step 1 — Define capability registry

A catalog of all capabilities, their scopes, and risk levels. This replaces the current `_RESERVED_PREFIXES` / `_INJECTION_TOOL_NAMES` approach with a structured model.

### Step 2 — Implement capability router

All tool calls go through the router. The router checks:
1. Does the agent have the required capability?
2. Is the capability within scope?
3. Does the policy allow this risk level?

### Step 3 — Wire policy engine

The policy engine evaluates capability requests against the current policy context. Policies can be role-based (worker vs. interactive session) or task-specific.

### Step 4 — Add audit trail

Every capability grant and denial is logged to the event store with:
- Agent identity
- Requested capability
- Scope
- Decision (granted / denied)
- Policy rule that triggered the decision

## Completion Criteria

- [ ] No agent directly executes privileged operations
- [ ] All tool access is mediated through capability requests
- [ ] Policy violations are logged and observable
- [ ] Capability grants are scoped to the minimum required