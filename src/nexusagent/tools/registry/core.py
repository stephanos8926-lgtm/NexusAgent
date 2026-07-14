"""Core tool registry — registration, lookup, auto-correction.

Architecture:
    ToolRegistry encapsulates the mutable _REGISTRY dict with thread-safe
    versioned snapshots via MappingProxyType. Tools are registered into a
    pending buffer, then freeze() atomically publishes a read-only snapshot.

    Backward compatibility: ``_REGISTRY`` is still exported as a read-only
    proxy via ``registry.current``, so existing ``from .core import _REGISTRY``
    callers continue to work.
"""

from __future__ import annotations

import asyncio
import difflib
import functools
from collections.abc import Callable
from threading import RLock
from types import MappingProxyType
from typing import Any

from .types import ToolInfo


# ─── ToolRegistry ────────────────────────────────────────────────────────


class ToolRegistry:
    """Thread-safe registry with versioned immutable snapshots.

    Features:
        - Tools are buffered in a pending dict during registration.
        - ``freeze()`` atomically snapshots pending → a new ``MappingProxyType``.
        - ``current`` returns the latest snapshot (read-only mapping).
        - ``prune()`` drops snapshots older than *keep_version*.
        - All mutation is guarded by an ``RLock`` so concurrent calls are safe.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._pending: dict[str, ToolInfo] = {}
        self._snapshots: dict[int, MappingProxyType] = {}
        self._latest_version: int = 0

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def version(self) -> int:
        """Current snapshot version (0 before first freeze)."""
        return self._latest_version

    @property
    def current(self) -> MappingProxyType[str, ToolInfo]:
        """Return the latest read-only snapshot, or an empty proxy."""
        with self._lock:
            snap = self._snapshots.get(self._latest_version)
            if snap is not None:
                return snap
            # Before first freeze — wrap pending as a live read-only view.
            # Callers that need a frozen-in-time view must call freeze() first.
            return MappingProxyType(self._pending)

    # ── Registration ───────────────────────────────────────────────────

    def register(self, name: str, info: ToolInfo) -> None:
        """Register *info* under *name* in the pending buffer.

        The tool is not visible to consumers until ``freeze()`` is called.
        """
        with self._lock:
            self._pending[name] = info

    # ── Snapshots ──────────────────────────────────────────────────────

    def freeze(self) -> int:
        """Publish a new read-only snapshot from pending tools.

        Returns the new version number.
        """
        with self._lock:
            self._latest_version += 1
            # Copy the pending dict so subsequent registrations don't
            # leak into an already-published snapshot.
            snapshot = MappingProxyType(dict(self._pending))
            self._snapshots[self._latest_version] = snapshot
            return self._latest_version

    def get_snapshot(
        self, version: int | None = None
    ) -> MappingProxyType[str, ToolInfo] | None:
        """Return a specific version, or ``None`` if it was pruned."""
        with self._lock:
            return self._snapshots.get(version if version is not None else self._latest_version)

    def prune(self, keep_version: int) -> None:
        """Remove snapshots with version <= *keep_version*."""
        with self._lock:
            stale = [v for v in self._snapshots if v <= keep_version]
            for v in stale:
                del self._snapshots[v]

    # ── Lookup helpers (delegate to current snapshot) ──────────────────

    def get(self, name: str, default: Any = None) -> ToolInfo | None:
        return self.current.get(name, default)

    def __contains__(self, name: str) -> bool:
        return name in self.current

    def __len__(self) -> int:
        return len(self.current)

    def __iter__(self):
        return iter(self.current)


# Module-level singleton — replaces bare _REGISTRY dict.
registry = ToolRegistry()


# ── Backward-compatible proxy ────────────────────────────────────────────


def _registry_proxy() -> MappingProxyType[str, ToolInfo]:
    """Return a view over the latest snapshot (public API compat)."""
    return registry.current


# Legacy alias — consumers that ``from .core import _REGISTRY`` still work.
_REGISTRY: MappingProxyType[str, ToolInfo] = _registry_proxy()  # type: ignore[assignment]


# ── Registration Decorator ───────────────────────────────────────────────


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, str],
    example: str,
    category: str = "general",
    returns: str = "",
    requires: str = "",
) -> Callable:
    """Decorator to register a tool in the global registry.

    Async functions are wrapped to ensure results are awaited before returning
    to the agent framework (prevents coroutine object display in TUI).
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            # Wrap async functions to ensure the agent framework gets
            # the actual result, not the coroutine object. Also catch
            # exceptions and convert to an error string — LangGraph's
            # ToolNode default error handler only catches its own
            # ToolInvocationError; anything else (PermissionError from
            # our own safety checks, OSError, etc.) propagates raw,
            # breaks the astream() loop mid-turn, and silently drops the
            # entire turn (including the user's message) from session
            # history since the history-append only runs on success.
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    return f"Error: {exc}"

            registry.register(
                name,
                ToolInfo(
                    name=name,
                    func=async_wrapper,
                    description=description,
                    parameters=parameters,
                    example=example,
                    category=category,
                    returns=returns,
                    requires=requires,
                ),
            )
        else:
            # Same rationale as async_wrapper above — applies to sync tools.
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    return f"Error: {exc}"

            registry.register(
                name,
                ToolInfo(
                    name=name,
                    func=sync_wrapper,
                    description=description,
                    parameters=parameters,
                    example=example,
                    category=category,
                    returns=returns,
                    requires=requires,
                ),
            )
        return func

    return decorator


def get_tool_info(name: str) -> ToolInfo | None:
    """Look up a tool by name in the global registry.

    Args:
        name: The registered tool name.

    Returns:
        The ToolInfo if found, or None.
    """
    return registry.get(name)


def list_all_tools() -> list[ToolInfo]:
    """Return all registered tools.

    Returns:
        List of all ToolInfo entries in the current snapshot.
    """
    return list(registry.current.values())


# ── Auto-Correction ────────────────────────────────────────────────────


def auto_correct(tool_name: str, kwargs: dict[str, Any] | None = None) -> str:
    """Validate a tool call and return corrections if needed.

    Checks:
    1. Tool exists in registry
    2. Tool is available under current policy
    3. Parameters are correct

    Returns:
        Correction message or validation confirmation.
    """
    # Delayed import to avoid circular dependency with policy module
    from .policy import _get_ctx, _is_tool_allowed, get_manifest

    # Check policy first
    allowed, reason = _is_tool_allowed(tool_name)
    if not allowed:
        return f"ACCESS DENIED: {reason}"

    if tool_name not in registry:
        # Fuzzy match within available tools
        ctx = _get_ctx()
        manifest = get_manifest(ctx["role"])
        if ctx["policy"] == "strict":
            available = {n: registry.current[n] for n in manifest if n in registry}
        else:
            unlocked = ctx.get("unlocked", set())
            available = {n: registry.current[n] for n in (manifest | unlocked) if n in registry}

        for cutoff in [0.5, 0.4, 0.3]:
            close = difflib.get_close_matches(tool_name, available.keys(), n=3, cutoff=cutoff)
            if close:
                suggestions = [f"  - {n}: {available[n].description}" for n in close]
                return f"Tool '{tool_name}' not found. Did you mean:\n" + "\n".join(suggestions)
        return f"Tool '{tool_name}' not found. Use tool_search() to list available tools."

    info = registry.get(tool_name)
    if info is None:
        return f"Internal error: Tool '{tool_name}' found in registry but info is None."

    # Validate parameters
    if kwargs:
        valid_params = set(info.parameters.keys())
        provided_params = set(kwargs.keys())
        unknown = provided_params - valid_params

        if unknown:
            corrections = []
            for bad in unknown:
                close = difflib.get_close_matches(bad, valid_params, n=1, cutoff=0.5)
                if close:
                    corrections.append(f"  - '{bad}' → did you mean '{close[0]}'?")
                else:
                    corrections.append(f"  - '{bad}' is not a valid parameter")
            params_list = ", ".join(sorted(valid_params))
            return (
                f"Invalid parameter(s) for '{tool_name}':\n"
                + "\n".join(corrections)
                + f"\n\nValid parameters: {params_list}\n"
                f"Example: {info.example}"
            )

    return f"Tool '{tool_name}' is valid. {info.description}\nExample: {info.example}"