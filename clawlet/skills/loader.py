"""
SKILL.md parser and loader.

Parses OpenClaw-compatible SKILL.md files with YAML frontmatter.
"""

import re
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from clawlet.skills.base import (
    BaseSkill,
    SkillMetadata,
    ToolDefinition,
    ToolParameter,
    PlaceholderSkill,
)


class SkillLoadError(Exception):
    """Error loading a skill."""
    pass


class SkillLoader:
    """
    Parser and loader for SKILL.md files.
    
    SKILL.md files use YAML frontmatter followed by markdown content:
    
    ```markdown
    ---
    name: email
    version: 1.0.0
    description: Send and manage emails
    author: clawlet
    requires:
      - smtp_server
      - smtp_port
    tools:
      - name: send_email
        description: Send an email
        parameters:
          - name: to
            type: string
            description: Recipient email address
            required: true
          - name: subject
            type: string
            required: true
    ---
    
    # Email Skill
    
    Instructions for using this skill...
    ```
    """
    
    # Pattern to match YAML frontmatter
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n(.*)$',
        re.DOTALL
    )
    
    @classmethod
    def parse_skill_md(cls, content: str) -> tuple[dict, str]:
        """
        Parse a SKILL.md file content.
        
        Args:
            content: Raw SKILL.md content
            
        Returns:
            Tuple of (frontmatter_dict, markdown_content)
            
        Raises:
            SkillLoadError: If parsing fails
        """
        match = cls.FRONTMATTER_PATTERN.match(content)
        
        if not match:
            raise SkillLoadError(
                "Invalid SKILL.md format: missing YAML frontmatter. "
                "File must start with '---' followed by YAML metadata."
            )
        
        frontmatter_yaml = match.group(1)
        markdown_content = match.group(2).strip()
        
        try:
            frontmatter = yaml.safe_load(frontmatter_yaml)
        except yaml.YAMLError as e:
            raise SkillLoadError(f"Invalid YAML in frontmatter: {e}")
        
        if not isinstance(frontmatter, dict):
            raise SkillLoadError("Frontmatter must be a YAML dictionary")
        
        return frontmatter, markdown_content
    
    @classmethod
    def parse_tool_parameter(cls, param_data: dict) -> ToolParameter:
        """
        Parse a tool parameter definition.
        
        Args:
            param_data: Parameter data from frontmatter
            
        Returns:
            ToolParameter object
        """
        return ToolParameter(
            name=param_data.get("name", ""),
            type=param_data.get("type", "string"),
            description=param_data.get("description"),
            required=param_data.get("required", True),
            default=param_data.get("default"),
            enum=param_data.get("enum"),
        )
    
    @classmethod
    def parse_tool_definition(cls, tool_data: dict) -> ToolDefinition:
        """
        Parse a tool definition from frontmatter.
        
        Args:
            tool_data: Tool data from frontmatter
            
        Returns:
            ToolDefinition object
        """
        parameters = []
        for param in tool_data.get("parameters", []):
            parameters.append(cls.parse_tool_parameter(param))
        
        return ToolDefinition(
            name=tool_data.get("name", ""),
            description=tool_data.get("description", ""),
            parameters=parameters,
        )
    
    @classmethod
    def parse_metadata(cls, frontmatter: dict) -> SkillMetadata:
        """
        Parse skill metadata from frontmatter.
        
        Args:
            frontmatter: Parsed YAML frontmatter
            
        Returns:
            SkillMetadata object
        """
        # Parse tools
        tools = []
        for tool_data in frontmatter.get("tools", []):
            tools.append(cls.parse_tool_definition(tool_data))
        
        return SkillMetadata(
            name=frontmatter.get("name", "unknown"),
            version=frontmatter.get("version", "1.0.0"),
            description=frontmatter.get("description", ""),
            author=frontmatter.get("author", "unknown"),
            requires=frontmatter.get("requires", []),
            tools=tools,
        )
    
    @classmethod
    def load_from_file(cls, skill_md_path: Path) -> BaseSkill:
        """
        Load a skill from a SKILL.md file.
        
        Args:
            skill_md_path: Path to the SKILL.md file
            
        Returns:
            BaseSkill (PlaceholderSkill) instance
            
        Raises:
            SkillLoadError: If loading fails
        """
        if not skill_md_path.exists():
            raise SkillLoadError(f"SKILL.md not found: {skill_md_path}")
        
        try:
            content = skill_md_path.read_text(encoding="utf-8")
        except Exception as e:
            raise SkillLoadError(f"Error reading {skill_md_path}: {e}")
        
        frontmatter, markdown_content = cls.parse_skill_md(content)
        metadata = cls.parse_metadata(frontmatter)
        
        skill_path = skill_md_path.parent
        
        logger.info(f"Loaded skill '{metadata.name}' v{metadata.version} from {skill_path}")
        
        return PlaceholderSkill(
            metadata=metadata,
            skill_path=skill_path,
            instructions=markdown_content,
        )
    
    @classmethod
    def load_from_directory(cls, skill_dir: Path) -> Optional[BaseSkill]:
        """
        Load a skill from a directory containing SKILL.md.
        
        Args:
            skill_dir: Path to skill directory
            
        Returns:
            BaseSkill instance, or None if no SKILL.md found
        """
        skill_md_path = skill_dir / "SKILL.md"
        
        if not skill_md_path.exists():
            logger.debug(f"No SKILL.md in {skill_dir}")
            return None
        
        try:
            return cls.load_from_file(skill_md_path)
        except SkillLoadError as e:
            logger.error(f"Error loading skill from {skill_dir}: {e}")
            return None


def discover_skills(directory: Path) -> list[BaseSkill]:
    """
    Discover and load all skills in a directory.
    
    Each skill should be in its own subdirectory with a SKILL.md file.
    
    Args:
        directory: Directory to search for skills
        
    Returns:
        List of loaded skills
    """
    skills = []
    
    if not directory.exists():
        logger.debug(f"Skills directory does not exist: {directory}")
        return skills
    
    for item in directory.iterdir():
        if item.is_dir():
            skill = SkillLoader.load_from_directory(item)
            if skill:
                skills.append(skill)
    
    return skills
