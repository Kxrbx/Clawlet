"""
Skill management tools.
"""

import subprocess
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from clawlet.tools.registry import BaseTool, ToolResult


class InstallSkillTool(BaseTool):
    """Tool to install a skill from a GitHub URL."""
    
    def __init__(self, skill_registry=None):
        self._skill_registry = skill_registry
    
    @property
    def name(self) -> str:
        return "install_skill"
    
    @property
    def description(self) -> str:
        return "Install a skill from a GitHub URL. Downloads and registers the skill for use."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "github_url": {
                    "type": "string",
                    "description": "GitHub repository URL (e.g., https://github.com/owner/repo)"
                }
            },
            "required": ["github_url"]
        }
    
    async def execute(self, github_url: str, **kwargs) -> ToolResult:
        """Install a skill from GitHub URL."""
        try:
            # Validate URL format
            if not re.match(r'https://github\.com/[^/]+/[^/]+', github_url):
                if not re.match(r'git@github\.com:[^/]+/[^/]+', github_url):
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Invalid GitHub URL format: {github_url}"
                    )
            
            # Parse owner/repo from URL
            match = re.match(r'https://github\.com/([^/]+)/([^/]+)', github_url)
            if not match:
                match = re.match(r'git@github\.com:([^/]+)/([^/]+)', github_url)
            
            if not match:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Could not parse owner/repo from URL: {github_url}"
                )
            
            owner, repo = match.groups()
            repo = repo.replace('.git', '')
            
            # Determine target directory
            user_skills_dir = Path.home() / ".clawlet" / "skills"
            target_dir = user_skills_dir / repo
            
            if target_dir.exists():
                return ToolResult(
                    success=True,
                    output=f"Skill '{repo}' already installed at {target_dir}",
                    data={"path": str(target_dir), "skill_name": repo}
                )
            
            # Create skills directory if needed
            user_skills_dir.mkdir(parents=True, exist_ok=True)
            
            # Clone the repository
            logger.info(f"Cloning {github_url} to {target_dir}")
            
            result = subprocess.run(
                ["git", "clone", "--depth", "1", github_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to clone repository: {result.stderr}"
                )
            
            # Check if SKILL.md exists
            skill_md = target_dir / "SKILL.md"
            if not skill_md.exists():
                return ToolResult(
                    success=True,
                    output=f"Cloned {repo} to {target_dir}, but no SKILL.md found. Please ensure the repository contains a valid SKILL.md file.",
                    data={"path": str(target_dir), "skill_name": repo}
                )
            
            # Read skill metadata
            skill_content = skill_md.read_text(encoding="utf-8")
            
            # Try to parse skill name from frontmatter
            skill_name = repo
            import yaml
            try:
                if skill_content.startswith('---'):
                    frontmatter_end = skill_content.find('---', 3)
                    if frontmatter_end > 0:
                        frontmatter = skill_content[3:frontmatter_end]
                        metadata = yaml.safe_load(frontmatter)
                        if metadata and 'name' in metadata:
                            skill_name = metadata['name']
            except Exception:
                pass
            
            return ToolResult(
                success=True,
                output=f"Successfully installed skill '{skill_name}' from {github_url}",
                data={
                    "path": str(target_dir),
                    "skill_name": skill_name,
                    "github_url": github_url
                }
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Git clone timed out (120s limit)"
            )
        except Exception as e:
            logger.error(f"Failed to install skill: {e}")
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class ListSkillsTool(BaseTool):
    """Tool to list installed skills."""
    
    def __init__(self, skill_registry=None):
        self._skill_registry = skill_registry
    
    @property
    def name(self) -> str:
        return "list_skills"
    
    @property
    def description(self) -> str:
        return "List all installed skills."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """List all installed skills."""
        try:
            # Check user skills directory
            user_skills_dir = Path.home() / ".clawlet" / "skills"
            
            if not user_skills_dir.exists():
                return ToolResult(
                    success=True,
                    output="No user skills installed",
                    data={"skills": []}
                )
            
            skills = []
            for item in user_skills_dir.iterdir():
                if item.is_dir():
                    skill_md = item / "SKILL.md"
                    if skill_md.exists():
                        skills.append({
                            "name": item.name,
                            "path": str(item),
                            "has_skill_md": True
                        })
                    else:
                        skills.append({
                            "name": item.name,
                            "path": str(item),
                            "has_skill_md": False
                        })
            
            if not skills:
                return ToolResult(
                    success=True,
                    output="No skills found in ~/.clawlet/skills/",
                    data={"skills": []}
                )
            
            output_lines = [f"Installed skills ({len(skills)}):"]
            for skill in skills:
                status = "✓" if skill["has_skill_md"] else "?"
                output_lines.append(f"  {status} {skill['name']}")
            
            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                data={"skills": skills}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
