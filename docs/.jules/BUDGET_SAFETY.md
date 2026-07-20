# Jules — Budget & Circuit Breaker Safety

**NexusAgent had a near-death budget incident (2026-06-30):** 30,000+ LLM API calls in 4 hours exhausted the monthly budget. This is a permanent scar — budget safety is non-negotiable.

## Hard Rules

**Rule 1 — Budget Guard is MANDATORY**
Every LLM call MUST pass through `LLMBudgetGuard`:
```python
from nexusagent.infrastructure.utils.budget import get_budget_guard
allowed, reason = await get_budget_guard().can_submit_task()
if not allowed:
    raise BudgetExceededError(f"Task rejected: {reason}")
```

**Rule 2 — Circuit Breaker on Quota Errors**
Trip immediately on `RESOURCE_EXHAUSTED`:
```python
from nexusagent.infrastructure.utils.circuit import CircuitBreaker

_breaker = CircuitBreaker(
    "agent",
    failure_threshold=5,
    quota_error_classes=(Exception,),
)
```

**Rule 3 — NEXUS_TEST_MODE for Tests**
Tests MUST run with `NEXUS_TEST_MODE=1` — blocks real API calls:
```
NEXUS_TEST_MODE=1 python3 -m pytest tests/core/ -q --tb=no --asyncio-mode=auto
```

**Rule 4 — NEVER hit production APIs in tests**
Mock external APIs. Real Gemini/OpenAI calls in test = budget overrun. The workstation has only OPENROUTER_API_KEY and GEMINI_API_KEY available. No Anthropic/OpenAI keys exist.

## Circuit Breaker Locations (read before modifying)

| File | Breaker | Threshold | Purpose |
|------|---------|-----------|---------|
| `src/nexusagent/infrastructure/utils/circuit.py` | Module | Configurable | Generic circuit breaker with quota detection |
| `src/nexusagent/core/worker/handler.py` | `_agent_breaker` | 5 failures, 30s recovery | Agent call protection |
| `src/nexusagent/core/worker/handler.py` | `_nats_breaker` | 3 failures, 15s recovery | NATS connection protection |
| `src/nexusagent/infrastructure/utils/budget.py` | `LLMBudgetGuard` | Per-config | Prevents budget overrun |

## Environment Variables Available

| Variable | Available? | Used For |
|----------|-----------|----------|
| `OPENROUTER_API_KEY` | ✅ Yes | LLM calls via OpenRouter |
| `GEMINI_API_KEY` | ✅ Yes | Google AI Studio models |
| `EXA_API_KEY` | ✅ Yes | Web search (research tasks) |
| `TAVILY_API_KEY` | ✅ Yes | Web search (validation tasks) |
| `ANTHROPIC_API_KEY` | ❌ No | Not available |
| `OPENAI_API_KEY` | ❌ No | Not available |

**LLM Models available on free tier:** deepseek-ai/deepseek-v4-flash (OpenRouter), gemma-4-31b-it (Gemini free, 15 RPM). Paid models available but budget-constrained after the incident.
