"""ToolInfo dataclass — metadata for a registered tool."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ToolInfo:
    """Metadata for a registered tool."""

    name: str
    func: Callable
    description: str
    parameters: dict[str, str]
    example: str
    category: str
    returns: str = ""
    requires: str = ""  # Optional: tools this tool depends on

    def to_prompt_format(self) -> str:
        """Format the tool metadata as a full prompt-ready string.

        Returns:
            Multi-line string with name, category, description,
            parameters, returns, and example.
        """
        params_str = "\n".join(f"    - {k}: {v}" for k, v in self.parameters.items())
        return (
            f"Tool: {self.name}\n"
            f"Category: {self.category}\n"
            f"Description: {self.description}\n"
            f"Parameters:\n{params_str}\n"
            f"Returns: {self.returns}\n"
            f"Example:\n{self.example}"
        )

    def to_compact(self) -> str:
        """Format the tool as a single-line compact summary.

        Returns:
            String like ``- name(param1, param2): description``.
        """
        params = ", ".join(self.parameters.keys())
        return f"- {self.name}({params}): {self.description}"
