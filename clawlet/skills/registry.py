"""
Skill registry for managing and discovering skills.

Skills are loaded from multiple directories in order of priority:
1. Bundled skills (clawlet/skills/bundled/)
2. User skills (~/.clawlet/skills/)
3. Workspace skills (./skills/)
"""

from pathlib import Path
from typing import Any, Optional

from loguru import logger

from clawlet.skills.base import BaseSkill, ToolDefinition
from clawlet.skills.loader import SkillLoader, discover_skills
from clawlet.tools.registry import ToolRegistry, ToolResult


class SkillRegistry:
    """
    Registry for managing skills.
    
    Features:
    - Load skills from multiple directories
    - Validate skill requirements against config
    - Generate tool definitions for LLM
    - Skill filtering based on environment/config
    - Integration with ToolRegistry
    """
    
    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        config: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize the skill registry.
        
        Args:
            tool_registry: Optional ToolRegistry to register skill tools with
            config: Optional configuration for skills
        """
        self._skills: dict[str, BaseSkill] = {}
        self._tool_registry = tool_registry
        self._config = config or {}
        self._disabled_skills: set[str] = set()
        self._skill_directories: list[Path] = []
        
        logger.info("SkillRegistry initialized")
    
    @property
    def skills(self) -> dict[str, BaseSkill]:
        """Get all registered skills."""
        return self._skills
    
    def add_skill_directory(self, directory: Path) -> int:
        """
        Add a directory to search for skills.
        
        Args:
            directory: Directory path to add
            
        Returns:
            Number of skills loaded from this directory
        """
        expanded = directory.expanduser()
        
        if not expanded.exists():
            logger.debug(f"Skill directory does not exist: {expanded}")
            return 0
        
        self._skill_directories.append(expanded)
        
        skills = discover_skills(expanded)
        loaded = 0
        
        for skill in skills:
            if skill.name in self._skills:
                # Don't override existing skills (priority order)
                logger.debug(f"Skill '{skill.name}' already loaded, skipping")
                continue
            
            self._skills[skill.name] = skill
            loaded += 1
            logger.info(f"Discovered skill '{skill.name}' from {expanded}")
        
        return loaded
    
    def load_from_directories(self, directories: list[Path]) -> int:
        """
        Load skills from multiple directories.
        
        Directories are processed in order, with earlier directories
        having higher priority (skills won't be overridden).
        
        Args:
            directories: List of directories to search
            
        Returns:
            Total number of skills loaded
        """
        total = 0
        for directory in directories:
            total += self.add_skill_directory(directory)
        return total
    
    def load_bundled_skills(self) -> int:
        """
        Load bundled skills shipped with Clawlet.
        
        Returns:
            Number of bundled skills loaded
        """
        bundled_path = Path(__file__).parent / "bundled"
        return self.add_skill_directory(bundled_path)
    
    def register(self, skill: BaseSkill) -> None:
        """
        Manually register a skill.
        
        Args:
            skill: Skill instance to register
        """
        if skill.name in self._skills:
            logger.warning(f"Overwriting existing skill: {skill.name}")
        
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")
    
    def unregister(self, name: str) -> None:
        """
        Unregister a skill.
        
        Args:
            name: Name of skill to unregister
        """
        if name in self._skills:
            del self._skills[name]
            logger.info(f"Unregistered skill: {name}")
    
    def get(self, name: str) -> Optional[BaseSkill]:
        """
        Get a skill by name.
        
        Args:
            name: Skill name
            
        Returns:
            Skill instance or None if not found
        """
        return self._skills.get(name)
    
    def all_skills(self) -> list[BaseSkill]:
        """Get all registered skills."""
        return list(self._skills.values())
    
    def enabled_skills(self) -> list[BaseSkill]:
        """Get all enabled skills."""
        return [
            skill for skill in self._skills.values()
            if skill.enabled and skill.name not in self._disabled_skills
        ]
    
    def disable_skill(self, name: str) -> None:
        """
        Disable a skill by name.
        
        Args:
            name: Skill name to disable
        """
        self._disabled_skills.add(name)
        logger.info(f"Disabled skill: {name}")
    
    def enable_skill(self, name: str) -> None:
        """
        Enable a previously disabled skill.
        
        Args:
            name: Skill name to enable
        """
        self._disabled_skills.discard(name)
        logger.info(f"Enabled skill: {name}")
    
    def configure_skill(self, name: str, config: dict[str, Any]) -> bool:
        """
        Configure a specific skill.
        
        Args:
            name: Skill name
            config: Configuration dictionary
            
        Returns:
            True if skill was configured, False if not found
        """
        skill = self.get(name)
        if not skill:
            return False
        
        skill.configure(config)
        
        # Validate requirements
        is_valid, missing = skill.validate_requirements()
        if not is_valid:
            logger.warning(
                f"Skill '{name}' has missing requirements: {missing}"
            )
        
        return True
    
    def configure_all(self, config: dict[str, Any]) -> None:
        """
        Configure all skills with the given config.
        
        Each skill will look for its configuration under config[skill_name].
        
        Args:
            config: Configuration dictionary with skill configs
        """
        for skill in self._skills.values():
            skill_config = config.get(skill.name, {})
            
            # Also check for global config values that match requirements
            for req in skill.requires:
                if req in config and req not in skill_config:
                    skill_config[req] = config[req]
            
            skill.configure(skill_config)
            
            # Validate requirements
            is_valid, missing = skill.validate_requirements()
            if not is_valid:
                logger.warning(
                    f"Skill '{skill.name}' has missing requirements: {missing}"
                )
    
    def get_all_tools(self) -> list[ToolDefinition]:
        """
        Get all tool definitions from enabled skills.
        
        Returns:
            List of ToolDefinition objects
        """
        tools = []
        for skill in self.enabled_skills():
            tools.extend(skill.tools)
        return tools
    
    def to_openai_tools(self) -> list[dict]:
        """
        Get all tools in OpenAI format with namespaced names.
        
        Returns:
            List of OpenAI function schemas
        """
        tools = []
        for skill in self.enabled_skills():
            tools.extend(skill.to_openai_tools())
        return tools
    
    def register_tools_with_registry(self) -> int:
        """
        Register all skill tools with the ToolRegistry.
        
        Creates wrapper tools that delegate to skill execution.
        
        Returns:
            Number of tools registered
        """
        if not self._tool_registry:
            logger.warning("No ToolRegistry set, cannot register tools")
            return 0
        
        registered = 0
        
        for skill in self.enabled_skills():
            for tool in skill.tools:
                # Create a wrapper tool
                namespaced_name = tool.get_namespaced_name(skill.name)
                
                # Create a closure to capture skill and tool_name
                async def execute_wrapper(
                    _skill: BaseSkill = skill,
                    _tool_name: str = tool.name,
                    **kwargs
                ) -> ToolResult:
                    return await _skill.execute_tool(_tool_name, **kwargs)
                
                # Create a dynamic tool class
                class SkillTool:
                    """Dynamic tool wrapper for skill tools."""
                    
                    def __init__(
                        self,
                        skill_inst: BaseSkill,
                        tool_def: ToolDefinition,
                        ns_name: str,
                    ):
                        self._skill = skill_inst
                        self._tool_def = tool_def
                        self._ns_name = ns_name
                    
                    @property
                    def name(self) -> str:
                        return self._ns_name
                    
                    @property
                    def description(self) -> str:
                        return self._tool_def.description
                    
                    @property
                    def parameters_schema(self) -> dict:
                        return self._tool_def.to_openai_schema()["function"]["parameters"]
                    
                    async def execute(self, **kwargs) -> ToolResult:
                        return await self._skill.execute_tool(
                            self._tool_def.name, **kwargs
                        )
                    
                    def to_openai_schema(self) -> dict:
                        schema = self._tool_def.to_openai_schema()
                        schema["function"]["name"] = self._ns_name
                        return schema
                
                tool_instance = SkillTool(skill, tool, namespaced_name)
                self._tool_registry.register(tool_instance)
                registered += 1
                logger.debug(f"Registered tool: {namespaced_name}")
        
        logger.info(f"Registered {registered} skill tools with ToolRegistry")
        return registered
    
    async def execute_tool(
        self,
        namespaced_name: str,
        **kwargs
    ) -> ToolResult:
        """
        Execute a skill tool by its namespaced name.
        
        Args:
            namespaced_name: Namespaced tool name (e.g., "email_send_email")
            **kwargs: Tool parameters
            
        Returns:
            ToolResult from execution
        """
        # Parse the namespaced name
        parts = namespaced_name.split("_", 1)
        if len(parts) != 2:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid tool name format: {namespaced_name}. "
                      f"Expected 'skillname_toolname'."
            )
        
        skill_name, tool_name = parts
        skill = self.get(skill_name)
        
        if not skill:
            return ToolResult(
                success=False,
                output="",
                error=f"Skill not found: {skill_name}"
            )
        
        if not skill.enabled or skill.name in self._disabled_skills:
            return ToolResult(
                success=False,
                output="",
                error=f"Skill '{skill_name}' is disabled"
            )
        
        return await skill.execute_tool(tool_name, **kwargs)
    
    def get_skill_instructions(self) -> dict[str, str]:
        """
        Get instructions for all enabled skills.
        
        Returns:
            Dictionary mapping skill names to their instructions
        """
        return {
            skill.name: skill.get_instructions()
            for skill in self.enabled_skills()
        }
    
    def validate_all_requirements(self) -> dict[str, list[str]]:
        """
        Validate requirements for all skills.
        
        Returns:
            Dictionary mapping skill names to lists of missing requirements
        """
        missing = {}
        for skill in self._skills.values():
            is_valid, missing_reqs = skill.validate_requirements()
            if not is_valid:
                missing[skill.name] = missing_reqs
        return missing
    
    def __repr__(self) -> str:
        return (
            f"SkillRegistry(skills={len(self._skills)}, "
            f"enabled={len(self.enabled_skills())}, "
            f"tools={len(self.get_all_tools())})"
        )