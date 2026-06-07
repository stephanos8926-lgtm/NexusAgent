# 🚀 NexusAgent Production & Feature Backlog

## 🌐 Phase 1: Web Intelligence (The Search Core)
- [ ] **Multi-Provider Search**: Implement `SearchOrchestrator` (Exa $\rightarrow$ Tavily $\rightarrow$ Brave).
- [ ] **Web Fetch**: Implement robust `web_fetch` tool.
- [ ] **AI Summarization**: Provider check $\rightarrow$ Local Nexus-Summarizer fallback.
- [ ] **Intelligent Failover**: Automatic recovery on 429/500 errors.
- [ ] **LLM Provider Bridge**: Unified client for Gemini and OpenRouter (supporting model-specific routing).

## 🧬 Phase 2: Dynamic Capability Layer (The Tooling)
- [ ] **MCP Integration**: Local (stdio) and Remote (SSE/WS) MCP server support.
- [ ] **Tool Registry**: Metadata-based manifest for all available tools.
- [ ] **JIT Tool Loading**: `search_tool_registry` $\rightarrow$ `unlock_tool` flow to prevent context bloat.
- [ ] **Intelligent Recovery**: "Did you mean...?" loop for missing tools.

## 🔬 Phase 3: Deep Research Engine (The Reasoning)
- [ ] **Agentic Workflow**: Intent $\rightarrow$ Plan $\rightarrow$ Refine $\rightarrow$ User Approval $\rightarrow$ Execute.
- [ ] **Research Orchestrator**: Recursive search/fetch loop and local knowledge graph update.
- [ ] **Template Engine**: 
    - Professional (Exec Summary $\rightarrow$ Analysis $\rightarrow$ Recommendations).
    - Academic (IMRaD: Abstract $\rightarrow$ Methods $\rightarrow$ Results $\rightarrow$ Discussion).
    - Basic (BLUF $\rightarrow$ Top Takeaways).

## 📦 Phase 4: Productionization (The Deployment)
- [ ] **Database Migration**: Move `nexus.db` to `/var/lib/nexusagent/` with configurable path in Pydantic settings.
- [ ] **Deployment Infrastructure**: Create `/deployments` folder with `install.sh`, `uninstall.sh`, and `systemd` units for server and client.
- [ ] **Packaging**: Build script to create `nexusagent-server.tar.gz` and `nexusagent-client.tar.gz`.
- [ ] **Documentation**: Update `RUNBOOK.md` and create `DEPLOYMENT.md`.
