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


class SearchMemoryTool(BaseTool):
    """Tool to search stored memories by text query."""

    def __init__(self, memory_manager):
        self.memory = memory_manager

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "Search stored memories by query text, with optional category filtering."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for in stored memories"},
                "category": {"type": "string", "description": "Optional category filter"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, category: Optional[str] = None, limit: int = 5) -> ToolResult:
        try:
            matches = self.memory.search(query=query, category=category, limit=limit)
            if not matches:
                return ToolResult(success=True, output="No matching memories found.")
            lines = ["## Memory Search Results"]
            for entry in matches:
                lines.append(f"- [{entry.category}] {entry.key}: {entry.value}")
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return ToolResult(success=False, output="", error=str(e))


class RecentMemoriesTool(BaseTool):
    """Tool to retrieve recently updated memories."""

    def __init__(self, memory_manager):
        self.memory = memory_manager

    @property
    def name(self) -> str:
        return "recent_memories"

    @property
    def description(self) -> str:
        return "Get the most recently updated memories, optionally filtered by category."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "category": {"type": "string", "description": "Optional category filter"},
            },
        }

    async def execute(self, limit: int = 5, category: Optional[str] = None) -> ToolResult:
        try:
            matches = self.memory.recent(limit=limit, category=category)
            if not matches:
                return ToolResult(success=True, output="No recent memories found.")
            lines = ["## Recent Memories"]
            for entry in matches:
                lines.append(f"- [{entry.category}] {entry.key}: {entry.value}")
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to load recent memories: {e}")
            return ToolResult(success=False, output="", error=str(e))


class ReviewDailyNotesTool(BaseTool):
    """Tool to inspect recent episodic daily notes."""

    def __init__(self, memory_manager):
        self.memory = memory_manager

    @property
    def name(self) -> str:
        return "review_daily_notes"

    @property
    def description(self) -> str:
        return "Review recent daily memory notes to curate or summarize longer-term memory."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many recent days of notes to include",
                    "default": 7,
                    "minimum": 1,
                    "maximum": 30,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to return",
                    "default": 200,
                    "minimum": 20,
                    "maximum": 500,
                },
            },
        }

    async def execute(self, days: int = 7, limit: int = 200) -> ToolResult:
        try:
            content = self.memory.get_recent_daily_notes(days=days, limit=limit)
            return ToolResult(success=True, output=content or "No recent daily notes found.")
        except Exception as e:
            logger.error(f"Failed to review daily notes: {e}")
            return ToolResult(success=False, output="", error=str(e))


class CurateMemoryTool(BaseTool):
    """Tool to promote durable daily notes into curated long-term memory."""

    def __init__(self, memory_manager):
        self.memory = memory_manager

    @property
    def name(self) -> str:
        return "curate_memory"

    @property
    def description(self) -> str:
        return "Review recent daily notes and promote durable items into curated long-term memory."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many recent days of notes to inspect",
                    "default": 7,
                    "minimum": 1,
                    "maximum": 30,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of curated items to promote",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
        }

    async def execute(self, days: int = 7, limit: int = 10) -> ToolResult:
        try:
            promoted = self.memory.curate_from_recent_daily_notes(days=days, limit=limit)
            if not promoted:
                return ToolResult(success=True, output="No durable items needed promotion from recent daily notes.")
            lines = ["## Curated Memory Updates"]
            lines.extend(f"- {item}" for item in promoted)
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to curate memory: {e}")
            return ToolResult(success=False, output="", error=str(e))


class MemoryStatusTool(BaseTool):
    """Tool to explain how memory is stored and projected."""

    def __init__(self, memory_manager):
        self.memory = memory_manager

    @property
    def name(self) -> str:
        return "memory_status"

    @property
    def description(self) -> str:
        return "Explain the current memory tiers, counts, and why some memories exist in SQLite or daily notes but not in MEMORY.md."

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        try:
            stats = self.memory.get_stats()
            lines = [
                "## Memory Status",
                f"- SQLite entries: {stats.get('sqlite_entry_count', 0)}",
                f"- Curated MEMORY.md entries: {stats.get('curated_projection_count', 0)}",
                f"- Daily-note entries: {stats.get('daily_note_count', 0)}",
                f"- Short-term entries: {stats.get('short_term_count', 0)}",
                f"- MEMORY.md path: {stats.get('memory_md_path', '')}",
                f"- Daily notes dir: {stats.get('daily_notes_dir', '')}",
                "- Projection rule: SQLite is the durable source of truth. MEMORY.md only includes curated memories and high-importance entries.",
                "- Daily notes are stored in both SQLite and memory/YYYY-MM-DD.md for review and later curation.",
            ]
            categories = stats.get("categories") or []
            if categories:
                lines.append(f"- Categories: {', '.join(categories)}")
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            logger.error(f"Failed to get memory status: {e}")
            return ToolResult(success=False, output="", error=str(e))


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
        self.search_memory = SearchMemoryTool(memory_manager)
        self.recent_memories = RecentMemoriesTool(memory_manager)
        self.review_daily_notes = ReviewDailyNotesTool(memory_manager)
        self.curate_memory = CurateMemoryTool(memory_manager)
        self.memory_status = MemoryStatusTool(memory_manager)
    
    def all_tools(self) -> list[BaseTool]:
        """Return all memory tools."""
        return [
            self.remember,
            self.recall,
            self.forget,
            self.get_context,
            self.search_memory,
            self.recent_memories,
            self.review_daily_notes,
            self.curate_memory,
            self.memory_status,
        ]
