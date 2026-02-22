"""
Memory tools for the agent.
"""

from typing import Optional

from loguru import logger

from clawlet.tools.registry import BaseTool, ToolResult


class RememberTool(BaseTool):
    """Tool to store information in memory."""
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
    
    @property
    def name(self) -> str:
        return "remember"
    
    @property
    def description(self) -> str:
        return "Store important information in memory for later recall. Use this to remember user preferences, important facts, or anything the user wants to be reminded of."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "A short, descriptive key to identify this memory"
                },
                "value": {
                    "type": "string",
                    "description": "The information to remember"
                },
                "category": {
                    "type": "string",
                    "description": "Category for organization (e.g., 'preferences', 'facts', 'user_info')",
                    "default": "general"
                },
                "importance": {
                    "type": "integer",
                    "description": "Importance level 1-10, higher values are remembered longer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5
                }
            },
            "required": ["key", "value"]
        }
    
    async def execute(self, key: str, value: str, category: str = "general", importance: int = 5) -> ToolResult:
        """Store information in memory."""
        try:
            self.memory.remember(key, value, category, importance)
            logger.debug(f"Remembered: {key} in category {category}")
            return ToolResult(
                success=True,
                output=f"Successfully remembered: {key}"
            )
        except Exception as e:
            logger.error(f"Failed to remember {key}: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class RecallTool(BaseTool):
    """Tool to retrieve information from memory."""
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
    
    @property
    def name(self) -> str:
        return "recall"
    
    @property
    def description(self) -> str:
        return "Recall previously stored information from memory using its key."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key of the memory to recall"
                }
            },
            "required": ["key"]
        }
    
    async def execute(self, key: str) -> ToolResult:
        """Retrieve information from memory."""
        try:
            value = self.memory.recall(key)
            if value is not None:
                logger.debug(f"Recalled: {key}")
                return ToolResult(
                    success=True,
                    output=f"Found: {value}"
                )
            else:
                return ToolResult(
                    success=True,
                    output=f"No memory found for key: {key}"
                )
        except Exception as e:
            logger.error(f"Failed to recall {key}: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class ForgetTool(BaseTool):
    """Tool to remove information from memory."""
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
    
    @property
    def name(self) -> str:
        return "forget"
    
    @property
    def description(self) -> str:
        return "Remove a specific memory from storage."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key of the memory to remove"
                }
            },
            "required": ["key"]
        }
    
    async def execute(self, key: str) -> ToolResult:
        """Remove information from memory."""
        try:
            removed = self.memory.forget(key)
            if removed:
                logger.debug(f"Forgot: {key}")
                return ToolResult(
                    success=True,
                    output=f"Successfully removed memory: {key}"
                )
            else:
                return ToolResult(
                    success=True,
                    output=f"No memory found to remove for key: {key}"
                )
        except Exception as e:
            logger.error(f"Failed to forget {key}: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class GetContextTool(BaseTool):
    """Tool to get relevant memories as context."""
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
    
    @property
    def name(self) -> str:
        return "get_context"
    
    @property
    def description(self) -> str:
        return "Get relevant memories as context for the current conversation. Returns important stored information."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "max_entries": {
                    "type": "integer",
                    "description": "Maximum number of memories to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50
                }
            }
        }
    
    async def execute(self, max_entries: int = 10) -> ToolResult:
        """Get memories as context."""
        try:
            context = self.memory.get_context(max_entries)
            logger.debug(f"Retrieved context with max_entries={max_entries}")
            return ToolResult(
                success=True,
                output=context if context else "No memories found."
            )
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class MemoryTools:
    """
    Container class for memory-related tools.
    
    Provides tools that allow the LLM to interact with the agent's memory.
    """
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.remember = RememberTool(memory_manager)
        self.recall = RecallTool(memory_manager)
        self.forget = ForgetTool(memory_manager)
        self.get_context = GetContextTool(memory_manager)
    
    def all_tools(self) -> list[BaseTool]:
        """Return all memory tools."""
        return [
            self.remember,
            self.recall,
            self.forget,
            self.get_context,
        ]
