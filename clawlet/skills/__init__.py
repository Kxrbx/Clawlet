"""
Skills system for Clawlet (OpenClaw-compatible).

Skills are modular capabilities that extend the agent's functionality
with structured instructions and tool definitions.

Example usage:

    from clawlet.skills import SkillRegistry, SkillLoader
    from clawlet.tools import ToolRegistry
    
    # Create registries
    tool_registry = ToolRegistry()
    skill_registry = SkillRegistry()
    
    # Load bundled skills
    skill_registry.load_bundled_skills()
    
    # Load installed validated skills from the active workspace
    skill_registry.add_skill_directory(Path(".skills") / "installed")
    
    # Configure skills
    skill_registry.configure_all({
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
    })
    
    # Register skill tools with the tool registry
    skill_registry.register_tools_with_registry(tool_registry)
    
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
from clawlet.skills.installer import SkillInstallerService
from clawlet.skills.registry import SkillRegistry
from clawlet.skills.runtime import SkillRuntime, build_skill_runtime

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
    "SkillInstallerService",
    # Registry
    "SkillRegistry",
    "SkillRuntime",
    "build_skill_runtime",
]
