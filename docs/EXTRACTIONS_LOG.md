# Configuration Extractions Log

> Generated: 2026-06-30
> Purpose: Track all magic numbers, hardcoded values, and settings extracted into the configuration system
> Format: [Date] | Component | Setting | Previous Location | Config Path | Reason

---

## Budget Guard System (2026-06-30)

| Date | Component | Setting | Previous Location | Config Path | Reason |
|------|-----------|---------|-------------------|-------------|--------|
| 2026-06-30 | Budget Guard | daily_budget_usd | `LLMBudgetGuard.__init__` default=10.0 | `budget.daily_budget_usd` | Hardcoded default; user must be able to set daily spend limit |
| 2026-06-30 | Budget Guard | monthly_budget_usd | `LLMBudgetGuard.__init__` default=100.0 | `budget.monthly_budget_usd` | Hardcoded default; user must be able to set monthly spend limit |
| 2026-06-30 | Budget Guard | alert_thresholds | `LLMBudgetGuard.__init__` default=[0.5,0.8,0.95] | `budget.alert_thresholds` | Magic numbers for warning levels; user should configure alert sensitivity |
| 2026-06-30 | Budget Guard | quota_cooldown_seconds | `LLMBudgetGuard.__init__` default=3600 | `budget.quota_cooldown_seconds` | Hardcoded cooldown after quota exhaustion; environment-specific |
| 2026-06-30 | Budget Guard | enabled | N/A (implicitly always on) | `budget.enabled` | Feature flag to disable budget guard entirely if needed |

---

## Test Mode System (2026-06-30)

| Date | Component | Setting | Previous Location | Config Path | Reason |
|------|-----------|---------|-------------------|-------------|--------|
| 2026-06-30 | Test Mode | block_real_api | `NEXUS_TEST_MODE` env var only | `test_mode.block_real_api` | Env var only was error-prone; config provides persistent setting |

---

## Existing Configurations (Pre-2026-06-30, now formally documented)

### Agent Configuration

| Date | Component | Setting | Previous Location | Config Path | Reason |
|------|-----------|---------|-------------------|-------------|--------|
| Pre-2026 | Agent | default_model | `AgentConfig` default | `agent.default_model` | User must choose model |
| Pre-2026 | Agent | primary_provider | `AgentConfig` default | `agent.primary_provider` | User must choose provider |
| Pre-2026 | Agent | gemini_model | `AgentConfig` default | `agent.gemini_model` | Provider-specific model |
| Pre-2026 | Agent | llm_request_timeout | `AgentConfig` default=90.0 | `agent.llm_request_timeout` | **Magic number** — timeout varies by provider/model |
| Pre-2026 | Agent | llm_max_retries | `AgentConfig` default=2 | `agent.llm_max_retries` | **Magic number** — retry behavior should be tunable |
| Pre-2026 | Agent | enabled_tools | `AgentConfig` default list | `agent.enabled_tools` | Security: which tools are available by default |
| Pre-2026 | Agent | max_tool_output_chars | `AgentConfig` default=400 | `agent.max_tool_output_chars` | Token budget management |
| Pre-2026 | Agent | max_conversation_history | `AgentConfig` default=40 | `agent.max_conversation_history` | Context window management |
| Pre-2026 | Agent | compaction_enabled | `AgentConfig` default=True | `agent.compaction_enabled` | Feature flag |
| Pre-2026 | Agent | memory_model | `AgentConfig` default="" | `agent.memory_model` | Extraction model selection |
| Pre-2026 | Agent | compaction_tier2_threshold | `AgentConfig` default=0.75 | `agent.compaction_tier2_threshold` | **Magic number** — when to trigger summarization |
| Pre-2026 | Agent | compaction_tier2_fresh_tail | `AgentConfig` default=32 | `agent.compaction_tier2_fresh_tail` | **Magic number** — messages to preserve |
| Pre-2026 | Agent | dream_cycle_interval | `AgentConfig` default=20 | `agent.dream_cycle_interval` | **Magic number** — how often to consolidate |

### Server Configuration

| Date | Component | Setting | Previous Location | Config Path | Reason |
|------|-----------|---------|-------------------|-------------|--------|
| Pre-2026 | Server | nats_url | `ServerConfig` default | `server.nats_url` | Deployment-specific |
| Pre-2026 | Server | db_path | `ServerConfig` default | `server.db_path` | Path varies by environment |
| Pre-2026 | Server | api_port | `ServerConfig` default=8000 | `server.api_port` | Port conflicts in multi-tenant |
| Pre-2026 | Server | worker_threads | `ServerConfig` default=4 | `server.worker_threads` | CPU-dependent tuning |
| Pre-2026 | Server | nats_reconnect_wait | `ServerConfig` default=2 | `server.nats_reconnect_wait` | **Magic number** — network-dependent |
| Pre-2026 | Server | nats_max_reconnects | `ServerConfig` default=60 | `server.nats_max_reconnects` | **Magic number** — reliability tuning |
| Pre-2026 | Server | tls_enabled | `ServerConfig` default=True | `server.tls_enabled` | Security requirement varies |

### Client Configuration

| Date | Component | Setting | Previous Location | Config Path | Reason |
|------|-----------|---------|-------------------|-------------|--------|
| Pre-2026 | Client | tui_theme | `ClientConfig` default | `client.tui_theme` | User preference |
| Pre-2026 | Client | timeout | `ClientConfig` default=30 | `client.timeout` | **Magic number** — network-dependent |
| Pre-2026 | Client | retry_limit | `ClientConfig` default=3 | `client.retry_limit` | **Magic number** — reliability tuning |
| Pre-2026 | Client | tui_responsive_enabled | `ClientConfig` default=True | `client.tui_responsive_enabled` | Feature flag for small screens |

### Prompt Configuration

| Date | Component | Setting | Previous Location | Config Path | Reason |
|------|-----------|---------|-------------------|-------------|--------|
| Pre-2026 | Prompt | max_chain_depth | `PromptConfig` default=8 | `prompt.max_chain_depth` | **Magic number** — prevents infinite recursion |
| Pre-2026 | Prompt | max_inject_file_size | `PromptConfig` default=262144 | `prompt.max_inject_file_size` | **Magic number** — memory/token budget |
| Pre-2026 | Prompt | session_history_count | `PromptConfig` default=5 | `prompt.session_history_count` | **Magic number** — context window management |

---

## Future Extractions Needed (Identified but not yet done)

| Priority | Component | Setting | Current Location | Target Config Path | Reason |
|----------|-----------|---------|-------------------|-------------------|--------|
| HIGH | Memory | memory_rate_limit_writes | `MemoryRateLimiter` default=30/min | `memory.rate_limit_writes` | Rate limiting varies by workload |
| HIGH | Memory | memory_rate_limit_searches | `MemoryRateLimiter` default=60/min | `memory.rate_limit_searches` | Rate limiting varies by workload |
| HIGH | Memory | extraction_min_confidence | `LLMExtractor` default=0.5 | `memory.extraction_min_confidence` | Quality threshold should be tunable |
| HIGH | Circuit Breaker | nats_failure_threshold | `_nats_breaker` default=3 | `circuit_breaker.nats_failure_threshold` | Network reliability varies |
| HIGH | Circuit Breaker | agent_failure_threshold | `_agent_breaker` default=5 | `circuit_breaker.agent_failure_threshold` | Provider reliability varies |
| MEDIUM | TUI | streaming_chunk_delay | `_write_response_chunk` hardcoded | `tui.streaming_chunk_delay` | UX preference |
| MEDIUM | TUI | max_message_history | `_streaming_response` buffer | `tui.max_message_history` | Memory management |
| MEDIUM | Worker | health_check_interval | `HEALTH_CHECK_INTERVAL` = 10.0 | `worker.health_check_interval` | **Magic number** — monitoring sensitivity |
| MEDIUM | Worker | degraded_timeout | `DEGRADED_TIMEOUT` = 30.0 | `worker.degraded_timeout` | **Magic number** — failure detection |
| LOW | Auth | kdf_iterations | `AuthConfig` default=100000 | `auth.kdf_iterations` | Security tuning (already configurable) |

---

## Extraction Rules Applied

For each extraction, the following MUST be done:
1. ✅ Add field to appropriate Pydantic config class with `Field(description="...")` explaining WHY
2. ✅ Add entry in `config/nexusagent.yaml` (project defaults)
3. ✅ Add section to `override_from_env` section list in `load_config()`
4. ✅ Document in AGENTS.md "Configuration System Philosophy" section
4. ✅ Reference in code via `settings.<section>.<field>` — NEVER hardcode
5. ✅ If env var needed for secrets/CI → add to `_env_mapping` or section override list

---

## Anti-Patterns Avoided

| Anti-Pattern | Example | Fix |
|--------------|---------|-----|
| Magic number in code | `timeout = 30` | `settings.client.timeout` |
| Hardcoded default in class | `__init__(self, budget=10.0)` | `settings.budget.daily_budget_usd` |
| Env var only (no config) | `os.getenv("TEST_MODE")` | `settings.test_mode.block_real_api` |
| Scattered config files | `~/.nexusagent/budget.yaml` | Single unified config with sections |
| User prefs in project config | `timeout: 30` in repo | Project config = deployment defaults ONLY |