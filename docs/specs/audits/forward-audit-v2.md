## FORWARD AUDIT: Immutable Tool Cache + Typed Trust Boundaries

**Date:** 2026-07-14
**Auditor:** Lucien
**Project Root:** `/home/sysop/Workspaces/NexusAgent/src/nexusagent`
**Output File:** `docs/specs/audits/forward-audit-v2.md`

---
## SPEC 1: Immutable Tool Cache

**CLAIMS TO VERIFY:**

1.  `_REGISTRY` at `tools/registry/core.py:15` is a mutable `dict[str, ToolInfo]`
    *   **Verification:** `core.py:15` shows `_REGISTRY: dict[str, ToolInfo] = {}`.
    *   **Result:** ✅ Verified.

2.  `_ROLE_TOOLS` at `core/agent.py:146` is a `dict[str, list]` with version counter pattern
    *   **Verification:** `agent.py:146` shows `_ROLE_TOOLS: dict[str, list] = {}`. `_role_tools_version` at `agent.py:117` and `_built_version` at `agent.py:118` implement the version counter pattern.
    *   **Result:** ✅ Verified.

3.  `_role_tools_version` / `_built_version` exist and work as described
    *   **Verification:** `agent.py:117` and `agent.py:118` define these variables. `_refresh_role_tools_if_needed()` at `agent.py:121` uses them to check if `_ROLE_TOOLS` needs to be rebuilt.
    *   **Result:** ✅ Verified.

4.  `_refresh_role_tools_if_needed()` exists and works as described
    *   **Verification:** `agent.py:121` defines `_refresh_role_tools_if_needed()`. It checks `_built_version != _role_tools_version` and rebuilds `_ROLE_TOOLS` if needed.
    *   **Result:** ✅ Verified.

5.  `register_all()` in `tools/register_all.py` iterates `TOOL_SPECS` and calls `register_tool()` decorator
    *   **Verification:** `register_all.py:29` defines `register_all()`. It imports `TOOL_SPECS` and iterates through it, calling `register_tool()` with `(func)` to apply the decorator.
    *   **Result:** ✅ Verified.

6.  `register_mcp_tools()` is async and dynamically registers tools mid-session
    *   **Verification:** `register_all.py:56` defines `async def register_mcp_tools()`. `agent.py:104` calls `await register_mcp_tools()`, confirming it's async and dynamically loaded.
    *   **Result:** ✅ Verified.

7.  `Agent.__init__()` at `core/agent.py:215` sets policy context, fires MCP loading, calls `_refresh_role_tools_if_needed()`, gets tools from `_ROLE_TOOLS`
    *   **Verification:**
        *   `agent.py:238`: `set_policy_context(role, policy)` - sets policy context.
        *   `agent.py:245`: `_ = loop.create_task(_ensure_mcp_tools_loaded())` - fires MCP loading.
        *   `agent.py:251`: `_refresh_role_tools_if_needed()` - calls refresh.
        *   `agent.py:254`: `tools = _ROLE_TOOLS.get(role, _ROLE_TOOLS["full"])` - gets tools.
    *   **Result:** ✅ Verified.

8.  `Agent.__init__()` passes tools list to `create_deep_agent()`
    *   **Verification:** `agent.py:295`: `self._inner = create_deep_agent(model=model, tools=tools,)` passes the `tools` list.
    *   **Result:** ✅ Verified.

9.  MCP tool shadow detection exists in `register_all.py` (lines ~103-113)
    *   **Verification:** `register_all.py:104-113` contains the code block that checks `if tool_name in BUILTIN_TOOL_NAMES:` and blocks registration if a shadow is detected.
    *   **Result:** ✅ Verified.

10. `_sanitize_description()` exists in `register_all.py` (lines ~246-255)
    *   **Verification:** `register_all.py:246-255` defines `_sanitize_description()`, which strips HTML/script tags and limits length.
    *   **Result:** ✅ Verified.

11. `ToolInfo` type exists in `tools/registry/types.py`
    *   **Verification:** `types.py:10` defines `@dataclass class ToolInfo:`.
    *   **Result:** ✅ Verified.

---
## SPEC 2: Typed Trust Boundaries

**CLAIMS TO VERIFY:**

1.  `sanitize_tool_output()` is defined at `agent.py:48`
    *   **Verification:** `agent.py:48` defines `def sanitize_tool_output(text: str) -> str:`.
    *   **Result:** ✅ Verified.

2.  `sanitize_tool_output()` is NEVER called from ANYWHERE (zero callers — confirm with grep)
    *   **Command:** `cd /home/sysop/Workspaces/NexusAgent/src/nexusagent && grep -rn "sanitize_tool_output" . --include="*.py"`
    *   **Output:** `./core/agent.py:48:def sanitize_tool_output(text: str) -> str:`
    *   **Finding:** The grep command only returned the definition of the function, meaning it's not called anywhere else in the Python files.
    *   **Result:** ✅ Verified.

3.  `_detect_injection()` at `agent.py:43` uses the 6 regex patterns listed
    *   **Verification:** `agent.py:43` defines `_detect_injection()`. `_INSTRUCTION_PATTERNS` at `agent.py:33` lists 6 regex patterns.
    *   **Result:** ✅ Verified.

4.  `_UNTRUSTED_MARKER` is defined at `agent.py:32`
    *   **Verification:** `agent.py:32` defines `_UNTRUSTED_MARKER = "[TOOL OUTPUT - UNTRUSTED CONTENT BELOW]"`.
    *   **Result:** ✅ Verified.

5.  `TrustLevel`, `TrustedContent`, `AnomalyScorer` do NOT exist anywhere in the codebase
    *   **Command:** `cd /home/sysop/Workspaces/NexusAgent/src/nexusagent && grep -rn "TrustLevel\|TrustedContent\|AnomalyScorer" . --include="*.py"`
    *   **Output:** (empty)
    *   **Finding:** The grep command returned no output, confirming these terms do not exist in the Python files.
    *   **Result:** ✅ Verified.

6.  `session.py` tool result handling path — does it call sanitize_tool_output? Trace the path from tool execution → result → prompt assembly
    *   **Command:** `cd /home/sysop/Workspaces/NexusAgent/src/nexusagent && grep -n "tool_output\\|sanitize\\|_detect_injection" core/session/session.py`
    *   **Output:** (empty)
    *   **Finding:** The grep command returned no output, indicating that `sanitize_tool_output` or `_detect_injection` are not directly called within `session.py`'s tool result handling.
    *   **Result:** ✅ Verified.

7.  `prompt_loader.py` @file injection path — what validation exists now?
    *   **Command:** `cd /home/sysop/Workspaces/NexusAgent/src/nexusagent && grep -n "sanitize\\|injection\\|validate\\|trust" infrastructure/prompt_loader.py`
    *   **Output:**
        ```
        9:For chat-time injection:
        136:        logger.warning("File injection error: %s", e)
        ```
    *   **Finding:** The `prompt_loader.py` file has comments and logging related to "chat-time injection" and "File injection error", but no explicit calls to `sanitize`, `validate`, or `trust` functions or mechanisms for actual validation or sanitization.
    *   **Result:** ⚠️ Partial. Mentions injection, but no clear validation or sanitization.

8.  `ToolInfo` type in `types.py` — does it have trust/provenance fields?
    *   **Command:** `python3 -c "from nexusagent.tools.registry.types import ToolInfo; print(ToolInfo.__annotations__)"`
    *   **Output:** `{'name': 'str', 'func': 'Callable', 'description': 'str', 'parameters': 'dict[str, str]', 'example': 'str', 'category': 'str', 'returns': 'str', 'requires': 'str'}`
    *   **Finding:** The output shows no `trust` or `provenance` fields.
    *   **Result:** ✅ Verified.

9.  Config in `infrastructure/config.py` — are there existing injection/trust config fields?
    *   **Command:** `cd /home/sysop/Workspaces/NexusAgent/src/nexusagent && grep -n "injection\\|trust\\|anomaly" infrastructure/config.py`
    *   **Output:**
        ```
        220:    # Maximum file size for @file injection (bytes)
        222:    # Whether to enable @file injection in chat input
        223:    chat_file_injection: bool = Field(default=True)
        224:    # Number of recent sessions to summarize for context injection
        ```
    *   **Finding:** The config file contains `chat_file_injection` related fields, which are "injection config fields". However, there are no explicit `trust` or `anomaly` fields.
    *   **Result:** ⚠️ Partial. `chat_file_injection` exists, but no `trust` or `anomaly` fields.
