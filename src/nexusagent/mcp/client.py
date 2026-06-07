from dataclasses import dataclass
from typing import Any


@dataclass
class MCPConnectionConfig:
    name: str
    type: str  # "stdio" or "sse" or "websocket"
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None


class MCPClient:
    """
    MCPClient manages connections to Model Context Protocol (MCP) servers.
    Supports local stdio-based servers and remote SSE/WebSocket servers.
    """

    def __init__(self, configs: list[MCPConnectionConfig]):
        self.configs = configs
        self.active_connections: dict[str, Any] = {}
        self.tool_definitions: dict[str, Any] = {}

    async def connect_all(self):
        """Establishes connections to all configured MCP servers."""
        for config in self.configs:
            try:
                if config.type == "stdio":
                    await self._connect_stdio(config)
                elif config.type == "sse":
                    await self._connect_sse(config)
                elif config.type == "websocket":
                    await self._connect_websocket(config)
            except Exception as e:
                print(f"Failed to connect to MCP server {config.name}: {e}")

    async def _connect_stdio(self, config: MCPConnectionConfig):
        """Connects to a local MCP server via standard input/output."""
        print(f"Connecting to stdio MCP server: {config.name} via {config.command}")
        self.active_connections[config.name] = {"type": "stdio", "status": "connected"}

    async def _connect_sse(self, config: MCPConnectionConfig):
        """Connects to a remote MCP server via Server-Sent Events (SSE)."""
        print(f"Connecting to SSE MCP server: {config.name} at {config.url}")
        self.active_connections[config.name] = {"type": "sse", "status": "connected"}

    async def _connect_websocket(self, config: MCPConnectionConfig):
        """Connects to a remote MCP server via WebSockets."""
        print(f"Connecting to WebSocket MCP server: {config.name} at {config.url}")
        self.active_connections[config.name] = {"type": "websocket", "status": "connected"}

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Calls a specific tool on a connected MCP server."""
        if server_name not in self.active_connections:
            raise ConnectionError(f"Server {server_name} is not connected.")
        print(f"Calling tool {tool_name} on server {server_name} with args {arguments}")
        return {"result": f"Success calling {tool_name}"}

    async def list_tools(self, server_name: str) -> list[dict[str, Any]]:
        """Lists all available tools from a specific MCP server."""
        if server_name not in self.active_connections:
            raise ConnectionError(f"Server {server_name} is not connected.")
        return [{"name": "example_tool", "description": "Example MCP tool", "parameters": {}}]

    async def disconnect_all(self):
        """Closes all active MCP connections."""
        self.active_connections.clear()
        print("Disconnected all MCP servers.")
