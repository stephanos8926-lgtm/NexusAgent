# Gemini Native Tool Calling with Interactions API

**Last updated:** 2026-06-28  
**SDK:** `google-genai>=2.3.0`  
**API:** Interactions API (Generally Available as of June 2026)

---

## Overview

As of **June 2026**, NexusAgent uses Google's **Interactions API** for native Gemini tool calling. This provides zero-shot access to powerful server-side tools without manual integration.

## Enabled Native Tools

NexusAgent automatically enables these built-in Gemini tools:

| Tool | Type | Purpose | Example |
|------|------|---------|---------|
| **google_search** | Server-side | Ground responses in real-time web data | "What's the current price of Bitcoin?" |
| **code_execution** | Server-side | Execute Python code in sandbox | "Calculate the sum of first 50 primes" |
| **url_context** | Server-side | Fetch and summarize URLs | "Summarize this article: https://..." |

### How It Works

```python
from nexusagent.llm.llm import llm

# Single call - tools run automatically on Google's servers
response = await llm.generate(
    prompt="What's the weather in Boston? Calculate the average of 5, 10, 15.",
    system_prompt="Use available tools for real-time data and calculations."
)

print(response.content)  # → Answer with weather + calculation
print(response.interaction_id)  # → For multi-turn context
```

**Behind the scenes:**
1. Gemini decides which tools to use
2. Google executes tools server-side (google_search, code_execution)
3. Results are automatically incorporated into the final answer
4. No manual tool execution required!

---

## Multi-Turn Conversations

Preserve tool context across turns using `previous_interaction_id`:

```python
# Turn 1
response1 = await llm.generate(
    prompt="Find the top 3 cryptocurrencies by market cap"
)
print(response1.content)

# Turn 2 - continues from previous context
response2 = await llm.generate(
    prompt="Now calculate the total market cap of those three",
    previous_interaction_id=response1.interaction_id
)
print(response2.content)
```

The Interactions API maintains conversation state and tool context automatically.

---

## Tool Execution Flow

### Server-Side Tools (Automatic)

Tools like `google_search` and `code_execution` run entirely on Google's servers:

```
User Prompt → Gemini → [Tool Decision] → Google Executes → Response
                     ↓
              google_search (HTTP request)
              code_execution (Python sandbox)
              url_context (Webpage fetch)
                     ↓
              Results baked into final answer
```

**No application code needed** - Google handles everything.

### Client-Side Tools (Function Calling)

For custom tools (e.g., NexusAgent's own tools), use the standard function calling pattern:

```python
# Define custom tool
def get_weather(city: str) -> str:
    """Get weather for a city"""
    # ... your implementation

# Pass to Gemini (future enhancement)
interaction = client.interactions.create(
    model="gemini-2.5-flash",
    input="What's the weather in Boston?",
    tools=[
        {"type": "google_search"},  # Built-in
        {"type": "function", "function": get_weather}  # Custom
    ]
)
```

**Current status:** NexusAgent uses built-in tools only. Custom function calling can be added later.

---

## Configuration

### Enable Native Tools

Tools are enabled by default in `src/nexusagent/llm/llm.py`:

```python
def _get_gemini_tools(self) -> list[dict[str, Any]]:
    tools = [
        {"type": "google_search"},
        {"type": "code_execution"},
        {"type": "url_context"},
    ]
    return tools
```

### Disable Specific Tools

To disable a tool (e.g., for cost control):

```python
def _get_gemini_tools(self) -> list[dict[str, Any]]:
    tools = [
        {"type": "google_search"},
        # {"type": "code_execution"},  # Disabled
        # {"type": "url_context"},     # Disabled
    ]
    return tools
```

---

## Billing

### Google Search (Grounding)

- **Gemini 3 models**: Billed per search query executed
- Multiple queries per prompt = multiple billable events
- Example: "Compare Bitcoin and Ethereum prices" may trigger 2 queries

### Code Execution

- Included in Gemini API pricing
- No additional charges
- Python only (limited standard library + common packages)

### URL Context

- Included in Gemini API pricing
- No additional charges
- Fetches + summarizes webpages automatically

---

## Testing

### Test Google Search

```python
from nexusagent.llm.llm import llm
import asyncio

async def test():
    response = await llm.generate(
        prompt="What is the current price of Bitcoin?"
    )
    print(f"Answer: {response.content}")
    print(f"Used Google Search: {response.tool_calls is not None}")

asyncio.run(test())
```

**Expected output:**
```
Answer: The current price of Bitcoin is $59,447 USD (as of June 29, 2026)...
Used Google Search: True
```

### Test Code Execution

```python
response = await llm.generate(
    prompt="What is the sum of the first 50 prime numbers? Generate and run Python code."
)
print(response.content)
```

**Expected output:**
```
The sum of the first 50 prime numbers is 5117.
First 50 primes: 2, 3, 5, 7, 11, ...
```

---

## Troubleshooting

### "tool not supported" Error

**Cause:** Using old `google-generativeai` SDK instead of `google-genai`

**Fix:** 
```bash
pip install -U "google-genai>=2.3.0"
```

Check `pyproject.toml`:
```toml
dependencies = [
    "google-genai>=2.3.0",  # ✅ Correct
    "google-generativeai",  # ❌ Old SDK - can remove
]
```

### No Real-Time Data in Responses

**Cause:** Google Search tool not enabled

**Fix:** Verify `_get_gemini_tools()` includes `{"type": "google_search"}`

### Code Execution Fails

**Cause:** Model doesn't support code execution or code times out

**Fix:**
- Use `gemini-2.5-flash` or newer
- Avoid infinite loops in generated code
- Keep computations under 10 seconds

### Interaction ID Expired

**Cause:** `previous_interaction_id` references old/expired interaction

**Fix:**
- Interactions expire after 24 hours
- Store fresh interaction IDs per session
- Refresh with new `llm.generate()` call

---

## Migration from Old API

### Before (Old SDK)

```python
import google.generativeai as genai

model = genai.GenerativeModel("gemini-2.5-flash")
response = await model.generate_content_async("Hello")
print(response.text)
```

❌ No native tool support  
❌ No multi-turn state management  
❌ No tool context circulation

### After (Interactions API)

```python
from google import genai

client = genai.Client(api_key=API_KEY)
interaction = client.interactions.create(
    model="gemini-2.5-flash",
    input="Hello",
    tools=[{"type": "google_search"}]
)
print(interaction.output_text)
```

✅ Native tools work automatically  
✅ Multi-turn with `previous_interaction_id`  
✅ Tool context circulation

---

## API Reference

### `LLMProvider.generate()`

```python
async def generate(
    prompt: str,
    system_prompt: str | None = None,
    timeout: float = 120.0,
    previous_interaction_id: str | None = None,  # Multi-turn
    **kwargs
) -> LLMResponse:
    """Generate response with native tool support."""
```

### `LLMResponse` Fields

```python
class LLMResponse(BaseModel):
    content: str              # Final answer
    model_used: str           # e.g., "gemini-2.5-flash"
    provider: str             # "gemini" or "openrouter"
    tool_calls: list | None   # Custom tool calls (if any)
    interaction_id: str       # For multi-turn conversations
```

---

## Future Enhancements

1. **Custom Function Calling**: Add NexusAgent tools to Gemini's tool registry
2. **Parallel Tool Execution**: Run multiple tools simultaneously
3. **Tool Choice Control**: Force or prevent specific tool usage
4. **Streaming Tool Calls**: Real-time tool execution updates

---

## References

- [Gemini Interactions API Docs](https://ai.google.dev/gemini-api/docs/interactions)
- [Tool Combinations Guide](https://ai.google.dev/gemini-api/docs/interactions/tool-combination)
- [Google Search Tool](https://ai.google.dev/gemini-api/docs/interactions/google-search)
- [Code Execution Tool](https://ai.google.dev/gemini-api/docs/interactions/code-execution)
- [python-genai SDK](https://github.com/googleapis/python-genai)