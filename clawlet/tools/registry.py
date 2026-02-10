"""
Tool registry and base tool interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
import json

from loguru import logger


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: str
    error: Optional[str] = None
    data: Any = None


class BaseTool(ABC):
    """
    Base class for all tools.
    
    Tools are capabilities the agent can use to interact with the world.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (used by LLM to call it)."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description (shown to LLM)."""
        pass
    
    @property
    def parameters_schema(self) -> dict:
        """JSON schema for tool parameters."""
        return {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
    
    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            }
        }


class ToolRegistry:
    """Registry for all available tools."""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        logger.info("ToolRegistry initialized")
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def all_tools(self) -> list[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def to_openai_tools(self) -> list[dict]:
        """Get all tools in OpenAI format."""
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool not found: {name}"
            )
        
        try:
            result = await tool.execute(**kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
