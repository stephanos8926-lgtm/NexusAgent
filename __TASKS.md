# __TASKS.md — DevBoard Multi-Agent Coordination

> **Shared task board for all agents.** Check this file before starting any work.
> Status: `[ ]` backlog | `[~]` in progress | `[r]` review | `[x]` done | `[!]` blocked

---

## 🔴 ACTIVE — Do Not Touch (Other Agent Working)
_If a task is marked `[~]`, another agent is working on it. Do NOT start it._

| Status | Task ID | Description | Agent | Project |
|--------|---------|-------------|-------|---------|

---

## 🟡 IN PROGRESS
_Tasks currently being worked on. Only one agent per task._

| Status | Task ID | Description | Agent | Project |
|--------|---------|-------------|-------|---------|

---

## 🟢 COMPLETED
_Finished tasks._

| Status | Task ID | Description | Agent | Project |
|--------|---------|-------------|-------|---------|

---

## 🤖 AGENT PROTOCOL

### Before Starting Any Task
1. **Check this file** — is the task already `[~]`? If yes, pick a different task.
2. **Check dependencies** — are all deps `[x]`? If no, pick a different task.
3. **Claim the task** — use `devboard claim <id> --agent <name>` or `devboard pick --agent <name>`.
4. **One task at a time** — respect WIP limits.

### While Working
- Update the task body with progress notes
- If blocked, use `devboard edit <id> --block "reason"`

### After Completion
1. `devboard complete <id>`
2. Commit with message: `devboard: [TASK_ID] [x] — [brief description]`

### Coordination Rules
- **Never modify a task file that belongs to another agent**
- **Never start a task marked `[~]`** — find something else
- **Always update this file first** before doing any work
- **Claims expire after 1 hour** — refresh with `devboard edit <id> --claim <name>`
