# src/nexusagent/hooks/__init__.py
"""Hooks system for NexusAgent.

Provides event-driven hooks that fire at key points in the agent lifecycle:
- session_init: Fired when a new session starts
- post_tool_use: Fired after each tool execution
- subagent_start: Fired when a sub-agent is spawned
- subagent_stop: Fired when a sub-agent finishes
- error: Fired on errors
- user_prompt_submit: Fired when the user submits a prompt
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class HookEvent(StrEnum):
    """Hook event types fired at specific points in the agent lifecycle."""

    SESSION_INIT = "session_init"
    POST_TOOL_USE = "post_tool_use"
    SUBAGENT_START = "subagent_start"
    SUBAGENT_STOP = "subagent_stop"
    ERROR = "error"
    USER_PROMPT_SUBMIT = "user_prompt_submit"


class HookRegistration:
    """Represents a single registered hook."""

    def __init__(
        self,
        event: HookEvent,
        callback: Callable[..., Any],
        name: str | None = None,
    ) -> None:
        self.event = event
        self.name: str = name if name is not None else getattr(callback, "__name__", repr(callback))
        self.callback = callback
        self.enabled: bool = True

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False


class HookManager:
    """Manages hook registration and execution."""

    def __init__(self) -> None:
        self._hooks: dict[HookEvent, list[HookRegistration]] = {}
        self._registry: dict[str, HookRegistration] = {}

    def register_hook(
        self,
        event: HookEvent,
        callback: Callable[..., Any],
        name: str | None = None,
    ) -> HookRegistration:
        """Register a callback for a hook event.

        Args:
            event: The event type to listen for.
            callback: Async or sync callable that receives a context dict.
            name: Optional name for enable/disable. Derived from callback if omitted.

        Returns:
            The HookRegistration (can be used to disable/enable).
        """
        if name is None:
            name = getattr(callback, "__name__", repr(callback))

        reg = HookRegistration(event=event, name=name, callback=callback)

        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(reg)
        self._registry[name] = reg
        logger.debug("Registered hook '%s' for event '%s'", name, event.value)
        return reg

    def get_hooks(self, event: HookEvent) -> list[HookRegistration]:
        """Return all registrations for an event (including disabled)."""
        return self._hooks.get(event, [])

    def list_hooks(self) -> list[HookRegistration]:
        """Return all registered hooks."""
        return list(self._registry.values())

    def disable_hook(self, name: str) -> None:
        """Disable a hook by name."""
        if name not in self._registry:
            raise KeyError(f"No hook registered with name '{name}'")
        self._registry[name].disable()

    def enable_hook(self, name: str) -> None:
        """Enable a hook by name."""
        if name not in self._registry:
            raise KeyError(f"No hook registered with name '{name}'")
        self._registry[name].enable()

    def clear(self) -> None:
        """Remove all hooks."""
        self._hooks.clear()
        self._registry.clear()

    async def run_hooks(self, event: HookEvent, context: dict[str, Any]) -> None:
        """Run all enabled hooks for an event, sequentially.

        Errors in individual hooks are logged but do not prevent
        subsequent hooks from running.

        Args:
            event: The event type to fire.
            context: Arbitrary data passed to each hook callback.
        """
        hooks = self._hooks.get(event, [])
        for reg in hooks:
            if not reg.enabled:
                continue
            logger.debug("Running hook '%s' for event '%s'", reg.name, event.value)
            try:
                result = reg.callback(context)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.warning(
                    "Hook '%s' for event '%s' raised an exception",
                    reg.name, event.value,
                    exc_info=True,
                )


# ── Module-level singleton ──────────────────────────────────────────────────

_manager: HookManager | None = None


def get_hook_manager() -> HookManager:
    """Return the global HookManager singleton."""
    global _manager
    if _manager is None:
        _manager = HookManager()
    return _manager


def reset_hook_manager() -> None:
    """Reset the global HookManager (for testing)."""
    global _manager
    _manager = HookManager()


# ── Convenience functions ────────────────────────────────────────────────────


def register_hook(
    event: HookEvent,
    callback: Callable[..., Any],
    name: str | None = None,
) -> HookRegistration:
    """Register a hook on the global manager."""
    return get_hook_manager().register_hook(event, callback, name=name)


async def run_hooks(event: HookEvent, context: dict[str, Any]) -> None:
    """Run hooks on the global manager."""
    await get_hook_manager().run_hooks(event, context)
