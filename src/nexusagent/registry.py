from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

@dataclass
class ToolDefinition:
    tool_id: str
    name: str
    description: str
    parameters: Dict[str, Any]
    category: str
    unlock_condition: Optional[str] = None
    is_active: bool = False

class ToolRegistry:
    \"\"\"
    ToolRegistry manages a manifest of available tools and their accessibility.
    \"\"\"
    def __init__(self):
        self._registry: Dict[str, ToolDefinition] = {}

    def register_tool(self, tool_def: ToolDefinition):
        \"\"\"Adds a tool to the registry.\"\"\"
        self._registry[tool_def.tool_id] = tool_def

    def unlock_tool(self, tool_id: str):
        \"\"\"Marks a tool as active for the current session.\"\"\"
        if tool_id in self._registry:
            self._registry[tool_id].is_active = True
            print(f"Tool {tool_id} has been unlocked.")
        else:
            print(f"Tool {tool_id} not found in registry.")

    def search_tool_registry(self, query: str) -> List[ToolDefinition]:
        \"\"\"Finds tools by name or use-case keywords in the description.\"\"\"
        query = query.lower()
        results = []
        for tool in self._registry.values():
            if query in tool.name.lower() or query in tool.description.lower():
                results.append(tool)
        return results

    def get_active_tools(self) -> List[ToolDefinition]:
        \"\"\"Returns all tools currently unlocked/active.\"\"\"
        return [tool for tool in self._registry.values() if tool.is_active]

    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        \"\"\"Returns a specific tool definition by ID.\"\"\"
        return self._registry.get(tool_id)

def find_suggested_tool(registry: ToolRegistry, failed_tool_name: str) -> Optional[ToolDefinition]:
    \"\"\"
    Error Recovery Logic: Searches the registry for the most likely candidate 
    when a tool call fails.
    \"\"\"
    # Try exact name match first
    for tool in registry._registry.values():
        if tool.name.lower() == failed_tool_name.lower():
            return tool

    # Try keyword matching
    keywords = failed_tool_name.lower().split('_')
    best_match = None
    max_score = 0

    for tool in registry._registry.values():
        score = 0
        # Name score
        for kw in keywords:
            if kw in tool.name.lower():
                score += 2
        # Description score
        for kw in keywords:
            if kw in tool.description.lower():
                score += 1
        
        if score > max_score:
            max_score = score
            best_match = tool

    return best_match if max_score > 0 else None
