# LLM Provider SDK Audit — NexusAgent

**Date:** 2026-06-28  
**Audit Scope:** Provider SDK usage, native feature support (tool calling, structured output, etc.)

---

## Executive Summary

**FINDING: ❌ NEXUSAGENT DOES NOT USE NATIVE PROVIDER SDKs PROPERLY**

NexusAgent uses `langchain.chat_models.init_chat_model()` with string-based provider resolution instead of direct SDK instantiation. This means:

1. **❌ Google Gemini: NOT using native tool calling**
   - Uses generic OpenAI-compatible interface via `init_chat_model()`
   - Missing: Native `google-genai` SDK features (Google Search tool, Code Execution, URL Context, Think tool)
   - Missing: `ChatGoogleGenerativeAI.bind_tools()` for proper tool schema support
   - Missing: Native structured output, thought signatures, multi-modal features

2. **❌ All Providers: Generic abstraction layer**
   - Relies on deepagents' `apply_provider_profile()` for provider resolution
   - Loses provider-specific optimizations and features
   - No provider-native streaming, caching, or token counting

3. **✅ Correct SDK Dependencies Installed**
   - `google-genai>=2.0.0,<2.3.0` ✓
   - `google-generativeai` ✓
   - `openai` ✓
   - `langgraph` ✓

---

## Current Architecture

### Provider Initialization (src/nexusagent/core/agent.py:248-270)

```python
from deepagents.profiles.provider.provider_profiles import apply_provider_profile
from langchain.chat_models import init_chat_model

init_kwargs = apply_provider_profile(
    model_name,
    {
        "timeout": settings.agent.llm_request_timeout,
        "max_retries": settings.agent.llm_max_retries,
    },
)
model = init_chat_model(model_name, **init_kwargs)
```

**Problem:** `init_chat_model` returns a LangChain ChatModel **wrapper**, not the native SDK.

### Actual Provider Usage

**File:** `src/nexusagent/llm/llm.py`

```python
# Gemini - Uses legacy google.generativeai module (NOT native SDK features)
from google import genai  # Legacy module

model = genai.GenerativeModel(model_name=model_id, system_instruction=system_prompt)
response = await model.generate_content_async(prompt)
```

**Issue:** This uses the basic generation API, NOT the native tool calling API from `langchain-google-genai`.

---

## What's Missing: Native Google Gemini Features

### ✅ What Gemini SDK Supports (langchain-google-genai 4.0+)

| Feature | SDK Support | NexusAgent |
|---------|-------------|-----------|
| **Tool Calling** | ✅ `bind_tools([tools])` | ❌ NOT USED |
| **Google Search Tool** | ✅ `GenAITool(google_search={})` | ❌ NOT USED |
| **Code Execution Tool** | ✅ `GenAITool(code_execution={})` | ❌ NOT USED |
| **URL Context Tool** | ✅ `GenAITool(url_context={})` | ❌ NOT USED |
| **Structured Output** | ✅ `with_structured_output()` | ❌ NOT USED |
| **Multi-modal** | ✅ Image/Audio/Video input | ⚠️ Partial (images only) |
| **Token Streaming** | ✅ Native async streaming | ✅ Via LangChain |
| **Thought Signatures** | ✅ Encrypted reasoning | ❌ NOT USED |
| **Native Async** | ✅ `model.ainvoke()` | ⚠️ Via LangChain wrapper |
| **Logprobs** | ⚠️ Limited | ❌ NOT USED |

### ✅ What Native Implementation Looks Like

```python
# CORRECT: Native Google Gemini with tool calling
from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool

# Initialize with native SDK
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# Bind native Google tools
llm_with_search = llm.bind_tools([GenAITool(google_search={})])
llm_with_code = llm.bind_tools([GenAITool(code_execution={})])

# Use tools
response = llm_with_search.invoke("When is the next solar eclipse?")
print(response.tool_calls)  # Native tool call format

# Structured output
from pydantic import BaseModel

class Weather(BaseModel):
    location: str
    temperature: float

llm_structured = llm.with_structured_output(Weather)
result = llm_structured.invoke("What's the weather in Boston?")
# Returns: Weather(location="Boston", temperature=72.5)
```

---

## Recommendations

### Priority 1: Enable Native Google Gemini Tool Calling

**Impact:** High — unlocks Google Search, Code Execution, URL Context tools  
**Effort:** Medium — requires agent.py + tools/ integration

**Steps:**
1. **Replace generic init with native:**
   ```python
   # agent.py (CURRENT - WRONG)
   model = init_chat_model("google_genai:gemini-2.5-flash")
   
   # (RECOMMENDED - CORRECT)
   from langchain_google_genai import ChatGoogleGenerativeAI
   model = ChatGoogleGenerativeAI(
       model="gemini-2.5-flash",
       api_key=settings.agent.gemini_api_key,
   )
   ```

2. **Bind native Google tools:**
   ```python
   # In tools/__init__.py or agent.py
   from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
   
   native_tools = []
   if settings.agent.enable_google_search:
       native_tools.append(GenAITool(google_search={}))
   if settings.agent.enable_code_execution:
       native_tools.append(GenAITool(code_execution={}))
   
   model = model.bind_tools(native_tools)
   ```

3. **Update tool handling in session.py:**
   - Detect native `GenAITool` responses vs. custom tools
   - Execute Google native tools differently (no custom code needed)

### Priority 2: Add Structured Output Support

**Impact:** Medium — better reliability for JSON extraction, data tasks  
**Effort:** Low-Medium

```python
# Add to agent.py
model_with_structure = model.with_structured_output(ResponseSchema)
```

### Priority 3: Use Provider-Specific Streaming

**Impact:** Low — current LangChain streaming works fine  
**Effort:** Medium

```python
# Currently uses LangChain's astream()
# Could use native Google streaming for better token-level control
```

---

## Provider Comparison

### OpenRouter (OpenAI-compatible)

**Current Status:** ✅ Acceptable

- Uses `AsyncOpenAI` client with OpenRouter base URL
- OpenAI-compatible tool calling works correctly
- No major missing features

**Recommendation:** Keep current implementation.

---

## Files to Modify

| File | Current | Change Required |
|------|---------|----------------|
| `src/nexusagent/core/agent.py:248-270` | `init_chat_model()` | Direct SDK instantiation |
| `src/nexusagent/llm/llm.py` | Legacy `google.generativeai` | Native `ChatGoogleGenerativeAI` |
| `src/nexusagent/tools/__init__.py` | Custom tools only | Add native Google tool binding |
| `src/nexusagent/core/session/session.py` | Generic tool handling | Detect native vs. custom tools |
| `config/nexusagent.yaml` | No Google tool config | Add `enable_google_search`, `enable_code_execution` |

---

## Testing Strategy

1. **Unit Tests:**
   - Verify `ChatGoogleGenerativeAI` instantiation
   - Test native tool binding
   - Verify tool call parsing

2. **Integration Tests:**
   - End-to-end Google Search tool execution
   - Code execution tool (sandboxed)
   - Structured output with Pydantic models

3. **Regression Tests:**
   - Ensure existing non-Google providers still work
   - Verify tool calling doesn't break for custom tools

---

## Implementation Timeline

| Phase | Tasks | Estimated Effort |
|-------|-------|-----------------|
| **Phase 1** | Replace `init_chat_model` with native SDK | 2-3 hours |
| **Phase 2** | Bind native Google tools (Search, Code) | 2-3 hours |
| **Phase 3** | Update tool execution logic | 1-2 hours |
| **Phase 4** | Add structured output support | 1-2 hours |
| **Phase 5** | Testing + docs | 2-3 hours |
| **TOTAL** | | **8-13 hours** |

---

## Risks

- **Breaking Changes:** Existing tool schemas may need migration
- **Provider Lock-in:** Native features tied to Google SDK
- **Testing Complexity:** Need real API keys for E2E testing
- **Prompt Caching:** Changing model init may invalidate caches

---

## Conclusion

**NexusAgent is missing critical native features** by using generic LangChain abstraction instead of provider-native SDKs. The biggest gap is **Google Gemini native tool calling** (Search, Code Execution, URL Context), which would provide powerful zero-shot capabilities without custom Python tool implementations.

**Recommendation:** Implement Priority 1 (native Gemini tool calling) in the next sprint. Estimated 8-13 hours for full rollout.

---

**Audit Status:** ✅ COMPLETE  
**Next Action:** Decision required — proceed with native SDK migration?