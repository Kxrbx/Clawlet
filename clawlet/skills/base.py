"""
Base classes for the Skills system.

Skills are modular capabilities that extend the agent's functionality
with structured instructions and tool definitions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

from loguru import logger

from clawlet.tools.registry import ToolResult


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array", "object"
    description: Optional[str] = None
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[list[str]] = None
    
    def to_json_schema(self) -> dict:
        """Convert to JSON Schema format."""
        schema: dict[str, Any] = {"type": self.type}
        if self.description:
            schema["description"] = self.description
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolDefinition:
    """Definition of a skill tool."""
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    
    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function schema format."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }
    
    def get_namespaced_name(self, skill_name: str) -> str:
        """Get the namespaced tool name (e.g., email_send_email)."""
        return f"{skill_name}_{self.name}"


@dataclass
class SkillMetadata:
    """Metadata parsed from SKILL.md frontmatter."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "unknown"
    requires: list[str] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)


class BaseSkill(ABC):
    """
    Base class for all skills.
    
    Skills are modular capabilities that extend the agent's functionality.
    Each skill can define tools that the agent can use.
    """
    
    def __init__(self, metadata: SkillMetadata, skill_path: Optional[Path] = None):
        self._metadata = metadata
        self._skill_path = skill_path
        self._config: dict[str, Any] = {}
        self._enabled = True
    
    @property
    def name(self) -> str:
        """Skill name."""
        return self._metadata.name
    
    @property
    def version(self) -> str:
        """Skill version."""
        return self._metadata.version
    
    @property
    def description(self) -> str:
        """Skill description."""
        return self._metadata.description
    
    @property
    def author(self) -> str:
        """Skill author."""
        return self._metadata.author
    
    @property
    def requires(self) -> list[str]:
        """Required configuration keys."""
        return self._metadata.requires
    
    @property
    def tools(self) -> list[ToolDefinition]:
        """Tool definitions provided by this skill."""
        return self._metadata.tools
    
    @property
    def skill_path(self) -> Optional[Path]:
        """Path to the skill directory."""
        return self._skill_path
    
    @property
    def enabled(self) -> bool:
        """Whether the skill is enabled."""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
    
    @property
    def config(self) -> dict[str, Any]:
        """Skill configuration."""
        return self._config
    
    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the skill with provided settings.
        
        Args:
            config: Configuration dictionary
        """
        self._config = config
        logger.debug(f"Configured skill {self.name} with {len(config)} settings")
    
    def validate_requirements(self) -> tuple[bool, list[str]]:
        """
        Validate that all required configuration is present.
        
        Returns:
            Tuple of (is_valid, missing_requirements)
        """
        missing = []
        for req in self.requires:
            if req not in self._config or not self._config[req]:
                missing.append(req)
        
        return len(missing) == 0, missing
    
    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute a skill tool.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution outcome
        """
        # Find the tool definition
        tool_def = None
        for tool in self.tools:
            if tool.name == tool_name:
                tool_def = tool
                break
        
        if not tool_def:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' not found in skill '{self.name}'"
            )
        
        # Validate required parameters
        for param in tool_def.parameters:
            if param.required and param.name not in kwargs:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Missing required parameter: {param.name}"
                )
        
        # Execute the tool (to be implemented by subclasses)
        try:
            result = await self._execute_tool_impl(tool_name, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} in skill {self.name}: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
    
    @abstractmethod
    async def _execute_tool_impl(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Implementation of tool execution.
        
        Override this method to implement actual tool functionality.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution outcome
        """
        pass
    
    def to_openai_tools(self) -> list[dict]:
        """
        Convert skill tools to OpenAI format with namespaced names.
        
        Returns:
            List of OpenAI function schemas
        """
        tools = []
        for tool in self.tools:
            schema = tool.to_openai_schema()
            # Namespace the tool name
            schema["function"]["name"] = tool.get_namespaced_name(self.name)
            tools.append(schema)
        return tools
    
    def get_instructions(self) -> str:
        """
        Get the skill instructions (markdown content from SKILL.md).
        
        Returns:
            Markdown instructions string
        """
        # To be overridden by subclasses that load from SKILL.md
        return ""
    
    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, version={self.version!r}, tools={len(self.tools)})"


class PlaceholderSkill(BaseSkill):
    """
    A placeholder skill that doesn't implement actual functionality.
    
    Used for skills that are defined in SKILL.md but don't have
    Python implementations. Returns helpful error messages when tools are called.
    """
    
    def __init__(
        self, 
        metadata: SkillMetadata, 
        skill_path: Optional[Path] = None,
        instructions: str = ""
    ):
        super().__init__(metadata, skill_path)
        self._instructions = instructions
    
    @property
    def instructions(self) -> str:
        """Get the skill instructions."""
        return self._instructions
    
    def get_instructions(self) -> str:
        """Get the skill instructions (markdown content from SKILL.md)."""
        return self._instructions
    
    async def _execute_tool_impl(self, tool_name: str, **kwargs) -> ToolResult:
        """Return a placeholder result indicating the skill is not implemented."""
        return ToolResult(
            success=False,
            output="",
            error=f"Skill '{self.name}' tool '{tool_name}' is defined but not implemented. "
                  f"This is a placeholder skill. To implement actual functionality, "
                  f"create a Python class extending BaseSkill."
        )
