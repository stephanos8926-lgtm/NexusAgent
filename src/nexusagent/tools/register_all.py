"""Tool registration — registers all tools in the global registry.

Registration has two paths:
1. Static tools: defined in tool_specs.py as TOOL_SPECS data, registered via register_all()
2. Dynamic tools: defined inline (spawn_subagent, ask_user, memory_*) with @register_tool decorator

Import this module once at startup to populate the registry:
    import nexusagent.tools.register_all  # noqa: F401
"""

from __future__ import annotations

import logging
import re

from nexusagent.memory.rate_limiter import MemoryRateLimiter
from nexusagent.tools.registry import register_tool

logger = logging.getLogger(__name__)

# ── Memory Rate Limiter (singleton) ──────────────────────────────────
# Prevents buggy loops from flooding the DB with low-value observations.
_memory_rate_limiter = MemoryRateLimiter(
    max_writes_per_minute=30,
    max_searches_per_minute=60,
)


def register_all() -> None:
    """Register all static tools from tool_specs into the global registry."""
    from nexusagent.tools.tool_specs import TOOL_SPECS

    count = 0
    for spec in TOOL_SPECS:
        name, description, parameters, example, category, returns, func = spec
        register_tool(
            name=name,
            description=description,
            parameters=parameters,
            example=example,
            category=category,
            returns=returns,
        )(func)
        count += 1
    logger.debug("Registered %d static tools from tool_specs", count)

    # Publish snapshot so agents see a consistent tool set
    from nexusagent.tools.registry import registry

    registry.freeze()


# ═══════════════════════════════════════════════════════════════════════
# MCP Plugin Loader (dynamic tools from configured MCP servers)
# ═══════════════════════════════════════════════════════════════════════

_MCP_REGISTRY: dict[str, list[dict]] = {}
_MCP_REGISTERED_NAMES: set[str] = set()


async def register_mcp_tools() -> list[str]:
    """Dynamically load MCP tools from configured servers.

    Reads MCP server configuration from settings.mcp_servers (list of
    dicts with 'name', 'url', 'transport' keys) and calls each
    server's tools/list endpoint to discover available tools.

    Returns:
        List of newly registered tool names.
    """
    from nexusagent.infrastructure.config import settings

    registered: list[str] = []
    servers = getattr(settings, "mcp_servers", None)
    if not servers:
        return registered

    try:
        import httpx  # noqa: F401 — used below for MCP tool loading
    except ImportError:
        logger.warning("httpx not installed — MCP tool loading skipped")
        return registered

    for server_cfg in servers:
        server_name = server_cfg.get("name", "unknown")
        server_url = server_cfg.get("url", "")
        transport = server_cfg.get("transport", "http")

        if not server_url:
            logger.warning("MCP server '%s' has no URL — skipping", server_name)
            continue

        try:
            tool_list = await _discover_mcp_tools(server_name, server_url, transport)
        except Exception as exc:
            logger.warning(
                "Failed to discover tools from MCP server '%s': %s",
                server_name,
                exc,
            )
            continue

        for tool_def in tool_list:
            tool_name = tool_def.get("name", "")
            if not tool_name or tool_name in _MCP_REGISTERED_NAMES:
                continue

            # SECURITY: Deny MCP tools that shadow built-in tool names
            from nexusagent.tools.tool_specs import BUILTIN_TOOL_NAMES

            if tool_name in BUILTIN_TOOL_NAMES:
                logger.warning(
                    "MCP server '%s' attempted to register tool '%s' "
                    "which shadows a built-in tool — BLOCKED",
                    server_name,
                    tool_name,
                )
                continue

            # SECURITY: Sanitize tool description (strip HTML/script tags)
            raw_description = tool_def.get("description", f"MCP tool from {server_name}")
            tool_description = _sanitize_description(raw_description)

            _MCP_REGISTERED_NAMES.add(tool_name)
            _MCP_REGISTRY.setdefault(server_name, []).append(tool_def)
            wrapped = _wrap_mcp_tool(server_name, server_url, transport, tool_def)
            tool_params = _extract_param_descriptions(tool_def.get("inputSchema", {}))

            register_tool(
                name=tool_name,
                description=f"[MCP:{server_name}] {tool_description}",
                parameters=tool_params,
                example=f"{tool_name}()",
                category="mcp",
                returns="Result from MCP server.",
            )(wrapped)

            registered.append(tool_name)
            logger.info("Registered MCP tool: %s (from %s)", tool_name, server_name)

    # Publish new snapshot for agents and prune old ones
    from nexusagent.tools.registry import registry

    registry.freeze()
    registry.prune(max(0, registry.version - 2))  # keep last 2 snapshots

    return registered


async def _discover_mcp_tools(
    server_name: str,
    server_url: str,
    transport: str,
) -> list[dict]:
    """Call an MCP server's tools/list endpoint and return tool definitions.

    Supports both Streamable HTTP and SSE transports.
    """
    base_url = server_url.rstrip("/")

    if transport in ("http", "streamable"):
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{base_url}/tools")
                response.raise_for_status()
                data = response.json()
                return data.get("tools", [])
        except Exception:
            # Fallback: try JSON-RPC tools/list
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                }
                response = await client.post(
                    f"{base_url}/mcp",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", {}).get("tools", [])
    else:
        raise ValueError(f"Unsupported MCP transport: {transport}")


def _wrap_mcp_tool(
    server_name: str,
    server_url: str,
    transport: str,
    tool_def: dict,
) -> callable:
    """Return an async callable that proxies calls to an MCP tool."""
    import httpx

    base_url = server_url.rstrip("/")
    tool_name = tool_def["name"]

    async def call_mcp_tool(**kwargs):
        """Dynamically generated MCP tool proxy."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": kwargs},
                }
                response = await client.post(
                    f"{base_url}/mcp",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("result", {}).get("content", [])
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                return "\n".join(texts) if texts else str(result)
        except Exception as exc:
            return f"[MCP:{server_name}] Error calling '{tool_name}': {exc}"

    call_mcp_tool.__name__ = tool_name
    call_mcp_tool.__doc__ = tool_def.get("description", f"MCP tool: {tool_name}")
    return call_mcp_tool


def _extract_param_descriptions(schema: dict) -> dict[str, str]:
    """Extract parameter descriptions from a JSON Schema."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    params: dict[str, str] = {}
    for pname, pdef in props.items():
        desc = pdef.get("description", pdef.get("type", "parameter"))
        if pname in required:
            desc = f"[required] {desc}"
        params[pname] = desc
    return params


# Regex to strip HTML/script tags from tool descriptions
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Maximum allowed length for MCP tool descriptions
_MAX_DESCRIPTION_LENGTH = 1000

# Valid tool name pattern: lowercase letters, digits, underscores; must start with letter or underscore
_VALID_TOOL_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

# Denylist of reserved/suspicious tool name prefixes (beyond BUILTIN_TOOL_NAMES)
_RESERVED_PREFIXES = ("system__", "internal__", "admin__", "root__")


def _sanitize_description(desc: str) -> str:
    """Strip HTML/script tags from tool descriptions and limit length.

    Prevents HTML/script injection attacks and overly long descriptions
    that could be used for prompt injection.
    """
    cleaned = _HTML_TAG_RE.sub("", desc).strip()
    if len(cleaned) > _MAX_DESCRIPTION_LENGTH:
        cleaned = cleaned[:_MAX_DESCRIPTION_LENGTH] + "…[truncated]"
    return cleaned


def _validate_tool_name(tool_name: str) -> tuple[bool, str]:
    """Validate an MCP tool name for safety.

    Returns:
        (is_valid, reason) — if is_valid is False, reason explains why.
    """
    if not tool_name:
        return False, "empty tool name"

    if not _VALID_TOOL_NAME_RE.match(tool_name):
        return False, (
            f"invalid tool name '{tool_name}': "
            "must match [a-z_][a-z0-9_]* (lowercase, digits, underscores only)"
        )

    for prefix in _RESERVED_PREFIXES:
        if tool_name.startswith(prefix):
            return False, f"tool name '{tool_name}' uses reserved prefix '{prefix}'"

    return True, ""


# ═══════════════════════════════════════════════════════════════════════
# Dynamic Tools (defined inline with @register_tool decorator)
# ═══════════════════════════════════════════════════════════════════════


@register_tool(
    name="spawn_subagent",
    description=(
        "Spawn an isolated worker to handle a task autonomously. "
        "The worker runs in its own space with bounded turns and reports back. "
        "Use for delegating PRs, isolated experiments, or parallel work."
    ),
    parameters={
        "task": "str — description of the work to do",
        "working_dir": "str — directory to work in (default: current)",
        "max_turns": "int — max agent iterations (default: 15)",
        "acceptance_criteria": "list[str] — how the agent knows it's done",
        "memory_mode": "str — 'isolated' or 'scoped' (default: 'isolated')",
    },
    example=(
        'spawn_subagent(task="Fix the auth bug in server.py", max_turns=20, '
        'acceptance_criteria=["All tests pass"])'
    ),
    category="orchestration",
    returns="str — worker ID and status",
)
async def spawn_subagent(
    task: str,
    working_dir: str = ".",
    max_turns: int = 15,
    acceptance_criteria: list[str] | None = None,
    memory_mode: str = "isolated",
    system_prompt: str | None = None,
) -> str:
    """Spawn a sub-agent worker to execute an isolated task and return its ID."""
    from nexusagent.core.worker import worker_pool
    from nexusagent.llm.models import MemoryScope, TaskContract

    contract = TaskContract(
        task_id=f"sub-{task[:20]}",
        title=task[:50],
        working_dir=working_dir,
        description=task,
        max_turns=max_turns,
        acceptance_criteria=acceptance_criteria or ["Task completed"],
        memory_scope=(
            MemoryScope(memory_mode)
            if memory_mode in ("isolated", "scoped")
            else MemoryScope.ISOLATED
        ),
        system_prompt=system_prompt,
    )

    handle = await worker_pool.spawn(contract)
    return f"Spawned worker {handle.worker_id} (status: {handle.status.value})"


@register_tool(
    name="ask_user",
    description=(
        "Ask the user a question and wait for their response. "
        "In TUI mode, shows the question in the chat. "
        "In headless mode, returns a default/fallback response. "
        "Use for confirmation, clarification, or interactive decisions."
    ),
    parameters={
        "question": "str — the question to ask the user",
        "options": "list[str] — optional list of choices (default: free-form)",
    },
    example='ask_user("Which file should we edit?", options=["main.py", "config.py", "other"])',
    category="interaction",
    returns="str — the user's response",
)
def ask_user(question: str, options: list[str] | None = None) -> str:
    """Ask the user a question. In TUI mode, pauses for user input.

    Returns the user's response, or a fallback if non-interactive.
    """
    # Check if we're running in TUI mode (event loop available)
    try:
        import asyncio

        asyncio.get_running_loop()
        # We're in an async context — this is the TUI
        # Return a signal that the TUI will handle via push_screen_wait
        return f"__ASK_USER__{question}__OPTIONS__{','.join(options or [])}__"
    except RuntimeError:
        pass

    # Non-interactive fallback
    if options:
        return (
            f"[ask_user] {question}\n"
            f"Options: {', '.join(options)}\n"
            f"[No interactive session — returning default: {options[0]}]"
        )
    return f"[ask_user] {question}\n[No interactive session — please respond in the TUI]"


# ═══════════════════════════════════════════════════════════════════════
# Memory Tools
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_MEMORY_WORKSPACE = "~/.nexusagent/memory/"


def _discover_workspaces() -> list[str]:
    """Discover all workspace memory directories.

    Scans ~/Workspaces/*/.nexusagent/ for directories that exist.
    Falls back to the default global workspace.

    Returns:
        List of absolute paths to workspace memory directories.
    """
    import os
    from pathlib import Path

    workspaces: list[str] = []
    workspaces_home = Path.home() / "Workspaces"
    if workspaces_home.is_dir():
        for project_dir in sorted(workspaces_home.iterdir()):
            nexus_dir = project_dir / ".nexusagent"
            if nexus_dir.is_dir():
                mem_dir = nexus_dir / "memory"
                if mem_dir.is_dir():
                    workspaces.append(str(mem_dir))

    # Always include the default global workspace as fallback
    default = os.path.expanduser(_DEFAULT_MEMORY_WORKSPACE)
    if default not in workspaces:
        workspaces.append(default)
    return workspaces


def _get_memory_workspace() -> str:
    """Get the memory workspace path.

    Resolution order:
    1. Thread-local worker override (set by _setup_workspace_context)
    2. Config setting ``agent.memory_workspace`` (if set)
    3. Default: ``~/.nexusagent/memory/``
    """
    import os

    # 1. Check thread-local worker override
    from nexusagent.core.agent import _ws_memory_dir
    from nexusagent.infrastructure.config import settings

    ws = _ws_memory_dir.get()
    if ws:
        os.makedirs(ws, exist_ok=True)
        return ws

    # 2. Check config
    ws = settings.agent.memory_workspace
    path = os.path.expanduser(ws) if ws else os.path.expanduser(_DEFAULT_MEMORY_WORKSPACE)
    os.makedirs(path, exist_ok=True)
    return path


@register_tool(
    name="memory_search",
    description="Search memory using hybrid keyword + vector search. Returns results with source citations.",
    parameters={
        "query": "Search query string",
        "max_results": "Maximum results to return (default: 6)",
        "workspace": "Override workspace path (optional, defaults to config or global)",
        "valid_from": "Optional ISO datetime — only return memories with valid_from >= this date",
        "valid_until": "Optional ISO datetime — only return memories with valid_until <= this date",
    },
    example='memory_search("authentication", max_results=5, valid_from="2026-01-01T00:00:00")',
    category="memory",
    returns="Formatted search results with citations.",
)
async def memory_search(
    query: str,
    max_results: int = 6,
    workspace: str | None = None,
    valid_from: str | None = None,
    valid_until: str | None = None,
) -> str:
    """Search memory using hybrid keyword + vector search.

    Args:
        query: Search query string.
        max_results: Maximum results to return per workspace (default: 6).
        workspace: Override workspace path, or "all" to search all workspaces.
        valid_from: Optional ISO datetime — filter memories with valid_from >= this date.
        valid_until: Optional ISO datetime — filter memories with valid_until <= this date.
    """
    rate_limit_msg = _memory_rate_limiter.check_search()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    from nexusagent.memory.memory import HybridMemoryManager

    if workspace == "all":
        workspaces = _discover_workspaces()
    else:
        ws = workspace or _get_memory_workspace()
        workspaces = [os.path.expanduser(ws)]

    all_results: list[dict] = []
    for ws in workspaces:
        try:
            mgr = HybridMemoryManager(ws)
            mgr.initialize()
            results = await mgr.recall(
                query, max_results=max_results, valid_from=valid_from, valid_until=valid_until
            )
            for r in results:
                r["_workspace"] = ws
            all_results.extend(results)
        except Exception:
            continue

    if not all_results:
        return f"No memories found for: {query}"

    # Deduplicate by content hash, keep highest score
    seen: dict[str, dict] = {}
    for r in all_results:
        key = r.get("content", "")[:100]
        if key not in seen or r.get("score", 0) > seen[key].get("score", 0):
            seen[key] = r

    # Sort by score, take top max_results
    merged = sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)[:max_results]

    lines = [f"Memory search results for: {query} ({len(merged)} results)\n"]
    for r in merged:
        source = r.get("file", "unknown")
        ws = r.get("_workspace", "")
        content = r.get("content", "").strip()
        score = r.get("score", 0)
        ws_label = f" [{ws}]" if workspace == "all" else ""
        lines.append(f"Source: {source}{ws_label} (score: {score:.2f})")
        lines.append(f"{content}\n")
    return "\n".join(lines)


@register_tool(
    name="memory_get",
    description="Read a memory file by its relative path (e.g., 'bank/auth-20260712.md').",
    parameters={
        "path": "Relative path within the memory workspace",
        "offset": "Starting line number (1-indexed, default: 1)",
        "limit": "Maximum lines to read (default: 50)",
    },
    example='memory_get("bank/auth-20260712.md", offset=1, limit=50)',
    category="memory",
    returns="File content as string.",
)
def memory_get(path: str, offset: int = 1, limit: int = 50) -> str:
    """Read a memory file by its relative path."""
    rate_limit_msg = _memory_rate_limiter.check_search()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    workspace = _get_memory_workspace()
    full_path = os.path.realpath(os.path.join(workspace, path))
    if not full_path.startswith(os.path.realpath(workspace)):
        return "ACCESS DENIED: Path traversal detected"

    if not os.path.exists(full_path):
        return f"File not found: {path}"

    with open(full_path) as f:
        lines = f.readlines()

    start = max(0, offset - 1)
    end = min(len(lines), start + limit)
    selected = lines[start:end]

    numbered = [f"{start + i + 1}|{line}" for i, line in enumerate(selected)]
    return "".join(numbered)


@register_tool(
    name="memory_write",
    description="Write a memory entry. Stores in bank/ directory with YAML frontmatter and indexes it.",
    parameters={
        "content": "The memory content to store",
        "type": "Entry type: world, experience, opinion, observation (default: world)",
        "description": "Short description/title for the entry",
        "confidence": "Confidence score 0.0-1.0 (optional, for opinion entries)",
        "entities": "List of entity names this relates to (optional)",
        "workspace": "Override workspace path (optional, defaults to config or global)",
        "dedup_threshold": "Similarity threshold for deduplication (0.0-1.0, default: 0.95). Set to 0 to disable.",
    },
    example='memory_write("The auth module uses JWT tokens", type="world", description="Auth uses JWT", entities=["auth", "jwt"])',
    category="memory",
    returns="Confirmation message with file path of the written entry.",
)
async def memory_write(
    content: str,
    type: str = "world",
    description: str = "",
    confidence: float | None = None,
    entities: list[str] | None = None,
    workspace: str | None = None,
    dedup_threshold: float = 0.95,
) -> str:
    """Write a memory entry. Stores in bank/ directory with YAML frontmatter and indexes it.

    Before writing, checks for duplicate memories using hybrid search.
    If a similar memory already exists (score >= dedup_threshold), returns
    the existing file path instead of writing a duplicate.
    """
    rate_limit_msg = _memory_rate_limiter.check_write()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    from nexusagent.memory.memory import HybridMemoryManager

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    mgr = HybridMemoryManager(ws)
    mgr.initialize()

    # Write-time deduplication: check if similar memory already exists
    if dedup_threshold > 0:
        try:
            existing = await mgr.recall(content, max_results=3)
            if existing:
                top_score = existing[0].get("score", 0)
                if top_score >= dedup_threshold:
                    top_file = existing[0].get("file", "unknown")
                    return f"Duplicate memory (score: {top_score:.2f}). Existing entry: {top_file}"
        except Exception:
            pass  # If dedup check fails, proceed with write

    filepath = await mgr.remember(
        content=content,
        type=type,
        description=description or content[:50],
        confidence=confidence,
        entities=entities,
    )
    return f"Memory written to: {filepath}"


@register_tool(
    name="memory_index_search",
    description=(
        "Search the hybrid memory index (FTS5 + vector similarity) directly. "
        "More powerful than memory_search — uses sqlite-vec for high-quality "
        "vector search."
    ),
    parameters={
        "query": "Search query string",
        "max_results": "Maximum results to return (default: 6)",
        "workspace": "Override workspace path (optional)",
    },
    example='memory_index_search("authentication flow", max_results=5)',
    category="memory",
    returns="Formatted search results with file citations and scores.",
)
async def memory_index_search(
    query: str,
    max_results: int = 6,
    workspace: str | None = None,
) -> str:
    """Search the hybrid memory index directly using HybridMemoryIndex.search()."""
    rate_limit_msg = _memory_rate_limiter.check_search()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    os.makedirs(ws, exist_ok=True)

    try:
        from nexusagent.memory.index.index import HybridMemoryIndex

        idx = HybridMemoryIndex(ws)
        results = await idx.search(query, max_results=max_results)
    except Exception as exc:
        return f"Index search failed: {exc}"

    if not results:
        return f"No index results for: {query}"

    lines = [f"Index search results for: {query}\n"]
    for r in results:
        source = r.get("file", "unknown")
        content = r.get("content", "").strip()
        score = r.get("score", 0)
        lines.append(f"Source: {source} (score: {score:.4f})")
        lines.append(f"{content}\n")
    return "\n".join(lines)


@register_tool(
    name="memory_index_rebuild",
    description=(
        "Rebuild the hybrid memory index from workspace files. "
        "Drops all indexed chunks and re-scans bank/ and memory/ directories. "
        "Use after bulk file changes."
    ),
    parameters={
        "workspace": "Override workspace path (optional)",
    },
    example="memory_index_rebuild()",
    category="memory",
    returns="Confirmation message with file count.",
)
def memory_index_rebuild(workspace: str | None = None) -> str:
    """Rebuild the hybrid memory index using HybridMemoryIndex.rebuild()."""
    rate_limit_msg = _memory_rate_limiter.check_write()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    os.makedirs(ws, exist_ok=True)

    try:
        from nexusagent.memory.index.index import HybridMemoryIndex

        idx = HybridMemoryIndex(ws)
        idx.rebuild()
    except Exception as exc:
        return f"Index rebuild failed: {exc}"

    return f"Memory index rebuilt for workspace: {ws}"


# ═══════════════════════════════════════════════════════════════════════
# Memory Self-Management Tools (Phase 1)
# ═══════════════════════════════════════════════════════════════════════


@register_tool(
    name="memory_delete",
    description=(
        "Delete a memory entry by its relative path. "
        "Removes the file and all its index entries. "
        "Use for removing stale, incorrect, or duplicate memories."
    ),
    parameters={
        "path": "Relative path within the memory workspace (e.g., 'bank/auth-20260712.md')",
        "workspace": "Override workspace path (optional, defaults to configured memory workspace)",
    },
    example='memory_delete("bank/auth-20260712.md")',
    category="memory",
    returns="Confirmation message with deletion details.",
)
def memory_delete(path: str, workspace: str | None = None) -> str:
    """Delete a memory entry and its index entries."""
    rate_limit_msg = _memory_rate_limiter.check_write()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    full_path = os.path.realpath(os.path.join(ws, path))
    real_workspace = os.path.realpath(ws)

    if not full_path.startswith(real_workspace):
        return "ACCESS DENIED: Path traversal detected"

    if not os.path.exists(full_path):
        return f"File not found: {path}"

    # Delete from index first
    try:
        from nexusagent.memory.index.index import HybridMemoryIndex

        idx = HybridMemoryIndex(ws)
        deleted_count = idx.delete_by_file(path)
    except Exception as exc:
        return f"Index cleanup failed: {exc}"

    # Delete the file
    try:
        os.remove(full_path)
    except OSError as exc:
        return f"File deletion failed: {exc}"

    return f"Deleted memory: {path} ({deleted_count} index entries removed)"


@register_tool(
    name="memory_update",
    description=(
        "Update an existing memory entry. Replaces the content and re-indexes it. "
        "Preserves YAML frontmatter unless new frontmatter is provided. "
        "Use for correcting or refreshing existing memories."
    ),
    parameters={
        "path": "Relative path within the memory workspace (e.g., 'bank/auth-20260712.md')",
        "content": "New content for the memory entry",
        "type": "Entry type: world, experience, opinion, observation (optional, preserved from frontmatter if not set)",
        "description": "Short description/title (optional, preserved from frontmatter if not set)",
    },
    example='memory_update("bank/auth-20260712.md", content="Updated: the auth module now uses JWT + refresh tokens", type="world")',
    category="memory",
    returns="Confirmation message with update details.",
)
def memory_update(
    path: str,
    content: str,
    type: str = "",
    description: str = "",
    workspace: str | None = None,
) -> str:
    """Update an existing memory entry and re-index it."""
    rate_limit_msg = _memory_rate_limiter.check_write()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    full_path = os.path.realpath(os.path.join(ws, path))
    real_workspace = os.path.realpath(ws)

    if not full_path.startswith(real_workspace):
        return "ACCESS DENIED: Path traversal detected"

    if not os.path.exists(full_path):
        return f"File not found: {path}"

    # Read existing file to preserve frontmatter if needed
    with open(full_path) as _f:
        existing_content = _f.read()
    existing_fm = {}

    # Parse existing frontmatter
    if existing_content.startswith("---"):
        parts = existing_content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            # Simple YAML key: value parsing
            for line in fm_text.split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    existing_fm[key.strip()] = val.strip().strip("\"'")

    # Determine frontmatter values
    final_type = type or existing_fm.get("type", "world")
    final_desc = description or existing_fm.get("description", "")
    existing_entities = existing_fm.get("entities", "")
    existing_created = existing_fm.get("created", "")
    existing_confidence = existing_fm.get("confidence", "")

    # Build new content with preserved frontmatter
    fm_lines = ["---"]
    fm_lines.append(f'name: "{final_desc or path}"')
    fm_lines.append(f"description: {final_desc}")
    fm_lines.append(f"type: {final_type}")
    if existing_created:
        fm_lines.append(f"created: {existing_created}")
    else:
        from datetime import UTC, datetime

        fm_lines.append(f"created: {datetime.now(UTC).isoformat()}")
    if existing_confidence:
        fm_lines.append(f"confidence: {existing_confidence}")
    if existing_entities:
        fm_lines.append(f"entities: {existing_entities}")
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append(content)

    new_content = "\n".join(fm_lines)

    # Write updated file
    try:
        with open(full_path, "w") as f:
            f.write(new_content + "\n")
    except OSError as exc:
        return f"File write failed: {exc}"

    # Re-index the file
    try:
        from nexusagent.memory.index.index import HybridMemoryIndex

        idx = HybridMemoryIndex(ws)
        idx.reindex_file(path)
    except Exception as exc:
        return f"File updated but re-index failed: {exc}"

    return f"Updated memory: {path}"


@register_tool(
    name="memory_list",
    description=(
        "List memory entries with optional filtering. "
        "Shows file paths, types, descriptions, and creation dates. "
        "Use for discovering what memories exist before updating or pruning."
    ),
    parameters={
        "type": "Filter by entry type: world, experience, opinion, observation (optional)",
        "limit": "Maximum number of entries to return (default: 50)",
        "workspace": "Override workspace path (optional)",
    },
    example='memory_list(type="world", limit=20)',
    category="memory",
    returns="Formatted list of memory entries.",
)
def memory_list(
    type: str = "",
    limit: int = 50,
    workspace: str | None = None,
) -> str:
    """List memory entries with optional filtering."""
    rate_limit_msg = _memory_rate_limiter.check_search()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    os.makedirs(ws, exist_ok=True)

    bank_dir = os.path.join(ws, "bank")
    if not os.path.exists(bank_dir):
        return "No memories found (bank directory does not exist)"

    entries = []
    for md_file in sorted(os.listdir(bank_dir)):
        if not md_file.endswith(".md"):
            continue
        filepath = os.path.join(bank_dir, md_file)
        try:
            with open(filepath) as _f:
                content = _f.read()
        except OSError:
            continue

        # Parse frontmatter
        entry_type = "unknown"
        desc = ""
        created = ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if line.startswith("type:"):
                        entry_type = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
                    elif line.startswith("created:"):
                        created = line.split(":", 1)[1].strip()
                    elif line.startswith("name:"):
                        name = line.split(":", 1)[1].strip().strip("\"'")
                        if not desc:
                            desc = name

        # Apply type filter
        if type and entry_type != type:
            continue

        entries.append(
            {
                "file": f"bank/{md_file}",
                "type": entry_type,
                "description": desc,
                "created": created,
            }
        )

    if not entries:
        return "No memories found matching the criteria"

    # Apply limit
    entries = entries[:limit]

    lines = [f"Memory entries ({len(entries)} shown):\n"]
    for e in entries:
        lines.append(f"  {e['file']}  [{e['type']}]")
        if e["description"]:
            lines.append(f"    {e['description']}")
        if e["created"]:
            lines.append(f"    Created: {e['created']}")
        lines.append("")

    return "\n".join(lines)


@register_tool(
    name="memory_prune",
    description=(
        "Prune memory entries matching criteria. "
        "Supports dry-run mode to preview what would be deleted. "
        "Use for removing old, low-confidence, or specific-type memories."
    ),
    parameters={
        "older_than_days": "Delete entries older than N days (optional)",
        "type": "Only delete entries of this type (optional)",
        "dry_run": "If True, preview what would be deleted without actually deleting (default: True)",
        "workspace": "Override workspace path (optional)",
    },
    example='memory_prune(older_than_days=30, type="observation", dry_run=True)',
    category="memory",
    returns="Report of deleted (or would-be-deleted) entries.",
)
def memory_prune(
    older_than_days: int = 0,
    type: str = "",
    dry_run: bool = True,
    workspace: str | None = None,
) -> str:
    """Prune memory entries matching criteria."""
    rate_limit_msg = _memory_rate_limiter.check_write()
    if rate_limit_msg:
        return rate_limit_msg

    import os
    from datetime import UTC, datetime, timedelta

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)

    # First, list matching entries
    bank_dir = os.path.join(ws, "bank")
    if not os.path.exists(bank_dir):
        return "No memories found (bank directory does not exist)"

    to_delete = []
    cutoff = None
    if older_than_days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

    for md_file in sorted(os.listdir(bank_dir)):
        if not md_file.endswith(".md"):
            continue
        filepath = os.path.join(bank_dir, md_file)
        rel_path = f"bank/{md_file}"

        try:
            with open(filepath) as _f:
                content = _f.read()
        except OSError:
            continue

        # Parse frontmatter
        entry_type = "world"
        created_str = ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if line.startswith("type:"):
                        entry_type = line.split(":", 1)[1].strip()
                    elif line.startswith("created:"):
                        created_str = line.split(":", 1)[1].strip()

        # Apply type filter
        if type and entry_type != type:
            continue

        # Apply age filter
        if cutoff and created_str:
            try:
                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if created_dt > cutoff:
                    continue
            except ValueError:
                pass  # If date parsing fails, include it

        # If no age filter, only delete if explicitly matches type
        if not cutoff and not type:
            continue

        to_delete.append(
            {
                "file": rel_path,
                "type": entry_type,
                "created": created_str,
                "full_path": filepath,
            }
        )

    if not to_delete:
        return "No memories match the prune criteria"

    # Dry run or actual deletion
    action = "Would delete" if dry_run else "Deleted"
    lines = [f"Memory prune ({action} {len(to_delete)} entries):\n"]
    for entry in to_delete:
        lines.append(f"  {entry['file']}  [{entry['type']}]  {entry['created']}")

    if not dry_run:
        # Actually delete
        from nexusagent.memory.index.index import HybridMemoryIndex

        idx = HybridMemoryIndex(ws)
        for entry in to_delete:
            try:
                idx.delete_by_file(entry["file"])
                os.remove(entry["full_path"])
            except Exception as exc:
                lines.append(f"\n  ERROR deleting {entry['file']}: {exc}")
        lines.append(f"\nPruned {len(to_delete)} memories")
    else:
        lines.append("\nDry run — no memories deleted. Set dry_run=False to execute.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Memory Consolidation Tools (Phase 4)
# ═══════════════════════════════════════════════════════════════════════


@register_tool(
    name="memory_consolidate",
    description=(
        "Consolidate memory entries by removing duplicates and stale entries. "
        "Scans all memories, identifies duplicates by content hash, "
        "and prunes entries older than 30 days. "
        "Supports dry-run mode to preview changes."
    ),
    parameters={
        "workspace": "Override workspace path (optional)",
        "dry_run": "If True, preview what would be deleted (default: True)",
    },
    example="memory_consolidate(dry_run=True)",
    category="memory",
    returns="Consolidation report with actions taken.",
)
def memory_consolidate(workspace: str | None = None, dry_run: bool = True) -> str:
    """Consolidate memory entries by removing duplicates and stale entries."""
    rate_limit_msg = _memory_rate_limiter.check_write()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)

    try:
        from nexusagent.memory.consolidation import ConsolidationEngine

        engine = ConsolidationEngine(ws, dry_run=dry_run)
        report = engine.scan()
        actions = engine.consolidate(report)
    except Exception as exc:
        return f"Consolidation failed: {exc}"

    lines = ["Memory Consolidation Report\n"]
    lines.append(f"Total memories: {report['total_files']}")
    lines.append(f"Total entities: {report['total_entities']}")
    lines.append(f"Duplicates found: {len(report['duplicates'])}")
    lines.append(f"Stale entries: {len(report['stale'])}")

    if actions.get("dry_run"):
        lines.append("\nDry run — no changes made. Set dry_run=False to execute.")
    else:
        lines.append(f"\nDuplicates removed: {actions['duplicates_removed']}")
        lines.append(f"Stale pruned: {actions['stale_pruned']}")
        lines.append(f"Index rebuilt: {actions['index_rebuilt']}")

    return "\n".join(lines)


@register_tool(
    name="memory_health",
    description=(
        "Report memory health metrics including total entries, "
        "duplicates, stale entries, and overall health score."
    ),
    parameters={
        "workspace": "Override workspace path (optional)",
    },
    example="memory_health()",
    category="memory",
    returns="Health report with metrics and score.",
)
def memory_health(workspace: str | None = None) -> str:
    """Report memory health metrics."""
    rate_limit_msg = _memory_rate_limiter.check_search()
    if rate_limit_msg:
        return rate_limit_msg

    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)

    try:
        from nexusagent.memory.consolidation import ConsolidationEngine

        engine = ConsolidationEngine(ws, dry_run=True)
        health = engine.health_report()
    except Exception as exc:
        return f"Health check failed: {exc}"

    lines = ["Memory Health Report\n"]
    lines.append(f"Total memories: {health['total_memories']}")
    lines.append(f"Total entities: {health['total_entities']}")
    lines.append(f"Duplicates: {health['duplicate_count']}")
    lines.append(f"Stale entries: {health['stale_count']}")
    lines.append(f"Health score: {health['health_score']:.2f}")

    if health["health_score"] >= 0.9:
        lines.append("\nStatus: HEALTHY")
    elif health["health_score"] >= 0.7:
        lines.append("\nStatus: NEEDS_ATTENTION")
    else:
        lines.append("\nStatus: DEGRADED — consolidation recommended")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# Dream Cycle Tool (manual trigger)
# ═══════════════════════════════════════════════════════════════════════


@register_tool(
    name="memory_dream",
    description=(
        "Manually trigger a dream cycle to consolidate memories. "
        "Runs the 4-phase cycle: scan, patterns, consolidate, trim. "
        "Removes duplicates, prunes stale entries, extracts patterns, "
        "and rebuilds the memory index. "
        "Supports dry-run mode to preview changes."
    ),
    parameters={
        "workspace": "Override workspace path (optional, defaults to configured memory workspace)",
        "dry_run": "If True, preview changes without modifying files (default: True)",
    },
    example="memory_dream(dry_run=True)",
    category="memory",
    returns="Dream cycle report with actions taken.",
)
async def memory_dream(workspace: str | None = None, dry_run: bool = True) -> str:
    """Manually trigger a dream cycle consolidation."""
    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)

    try:
        from nexusagent.memory.dream import DreamCycle

        cycle = DreamCycle(ws)
        report = await cycle.run(dry_run=dry_run)
    except Exception as exc:
        return f"Dream cycle failed: {exc}"

    lines = ["Dream Cycle Report\n"]
    lines.append(f"Dry run: {report['dry_run']}")
    lines.append(f"Patterns extracted: {report['patterns_extracted']}")
    lines.append(f"Duplicates removed: {report['duplicates_removed']}")
    lines.append(f"Stale pruned: {report['stale_pruned']}")
    lines.append(f"Health: {report['health_before']:.2f} -> {report['health_after']:.2f}")

    if report["dry_run"]:
        consolidate = report.get("phase3_consolidate", {})
        lines.append(f"\nWould remove {consolidate.get('would_remove_duplicates', 0)} duplicates")
        lines.append(f"Would prune {consolidate.get('would_prune_stale', 0)} stale entries")
        lines.append("Dry run — no changes made. Set dry_run=False to execute.")

    return "\n".join(lines)
