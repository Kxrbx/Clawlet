"""
Skills system for Clawlet (OpenClaw-compatible).

Skills are modular capabilities that extend the agent's functionality
with structured instructions and tool definitions.

Example usage:

    from clawlet.skills import SkillRegistry, SkillLoader
    from clawlet.tools import ToolRegistry
    
    # Create registries
    tool_registry = ToolRegistry()
    skill_registry = SkillRegistry(tool_registry=tool_registry)
    
    # Load bundled skills
    skill_registry.load_bundled_skills()
    
    # Load user skills
    skill_registry.add_skill_directory(Path.home() / ".clawlet" / "skills")
    
    # Configure skills
    skill_registry.configure_all({
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
    })
    
    # Register skill tools with the tool registry
    skill_registry.register_tools_with_registry()
    
    # Get OpenAI-format tool definitions
    tools = skill_registry.to_openai_tools()
"""

from clawlet.skills.base import (
    BaseSkill,
    PlaceholderSkill,
    SkillMetadata,
    ToolDefinition,
    ToolParameter,
)
from clawlet.skills.loader import (
    SkillLoader,
    SkillLoadError,
    discover_skills,
)
from clawlet.skills.registry import SkillRegistry

__all__ = [
    # Base classes
    "BaseSkill",
    "PlaceholderSkill",
    "SkillMetadata",
    "ToolDefinition",
    "ToolParameter",
    # Loader
    "SkillLoader",
    "SkillLoadError",
    "discover_skills",
    # Registry
    "SkillRegistry",
]