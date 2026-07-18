# MistralAI Handoff — MCP Budget Alert Hook Implementation

**Branch:** `mistralai/mcp-budget-hook`
**File:** `src/nexusagent/infrastructure/utils/budget.py`
**Line:** ~419

---

## The Issue

Budget tracking has a TODO at line 419:

```python
# TODO: Hook integration for webhook/alerting
# Could call: run_hook("on_budget_alert", window_type, threshold, spent, budget)
```

When budget thresholds are crossed (50%, 80%, 95%), we should fire an alert via webhook/MCP.

---

## The Task

**Use the remote MCP endpoint `https://ast.rapidwebs.org/mcp` to analyze the codebase first**, then implement the hook integration.

### Step 1: Explore the Codebase via MCP

```bash
# Use the remote MCP endpoint to search
curl -X POST https://ast.rapidwebs.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_tools","arguments":{"query":"budget hook alert webhook"}}}'
```

Search for:
- Existing hook patterns in the codebase
- How `run_hook` is used elsewhere
- Budget threshold logic in `budget.py`
- Any webhook/alert patterns already in use

### Step 2: Understand the Budget Alert Logic

From `budget.py` around line 400-420:
- `_check_thresholds()` fires at 50%, 80%, 95% of budget
- `_alerted_thresholds` tracks which alerts have fired
- Need to add webhook/MCP call when threshold fires

### Step 3: Find Hook Pattern

Search for existing hooks:
- `src/nexusagent/hooks/` — if exists
- `run_hook` function pattern
- `settings.hooks` or similar config

---

## Expected Implementation

Add to `LLMBudgetGuard._check_thresholds()`:

```python
async def _check_thresholds(self, window_type: str, window: BudgetWindow) -> None:
    # ... existing threshold logic ...
    
    if not alerted and spent >= threshold * budget:
        self._alerted_thresholds.add(key)
        await self._fire_budget_alert(window_type, threshold, spent, budget)

async def _fire_budget_alert(self, window_type: str, threshold: float, spent: float, budget: float) -> None:
    """Fire budget alert via hook/MCP webhook."""
    from nexusagent.hooks import run_hook  # or similar
    try:
        await run_hook("on_budget_alert", {
            "window_type": window_type,
            "threshold": threshold,
            "spent": spent,
            "budget": budget,
            "percentage": (spent / budget) * 100,
        })
    except Exception as e:
        logger.warning(f"Budget alert hook failed: {e}")
```

---

## Test Plan

1. **Unit test:** Mock `run_hook`, trigger budget threshold, verify hook called with correct payload
2. **Integration test:** Run with real MCP endpoint, verify webhook fires
3. **Manual test:** Set low budget, make LLM calls, verify alert fires at 50%

---

## MCP Endpoint for Analysis

**URL:** `https://ast.rapidwebs.org/mcp`
**Auth:** None required (public endpoint)
**Transport:** HTTP JSON-RPC (MCP Streamable HTTP)

Example call:
```bash
curl -X POST https://ast.rapidwebs.org/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json,text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_tools","arguments":{"query":"hook webhook alert"}}}'
```

---

## Acceptance Criteria

- [ ] Budget alerts fire at 50%, 80%, 95% thresholds
- [ ] Hook payload includes: window_type, threshold, spent, budget, percentage
- [ ] Hook failures don't break budget tracking (graceful degradation)
- [ ] Hook uses existing hook infrastructure or defines new `on_budget_alert` hook
- [ ] Unit tests pass
- [ ] Manual verification: set $0.01 daily budget, make calls, verify alert