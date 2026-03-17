"""Skill management tools."""

from __future__ import annotations

from pathlib import Path

from clawlet.cli.runtime_paths import get_default_workspace_path
from clawlet.skills.installer import SkillInstallerService
from clawlet.tools.registry import BaseTool, ToolResult
from clawlet.workspace_layout import WorkspaceLayout, get_workspace_layout


def _workspace_layout_from_kwargs(kwargs: dict) -> WorkspaceLayout:
    workspace_path = kwargs.get("_workspace_path") or get_default_workspace_path()
    layout = get_workspace_layout(workspace_path)
    layout.ensure_directories()
    return layout


class InstallSkillTool(BaseTool):
    """Tool to install a skill from a GitHub repository root URL."""

    def __init__(self, skill_registry=None):
        self._skill_registry = skill_registry

    @property
    def name(self) -> str:
        return "install_skill"

    @property
    def description(self) -> str:
        return (
            "Install a skill from a GitHub repository root URL. "
            "Rejects repository subpaths and only installs validated skill directories."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "github_url": {
                    "type": "string",
                    "description": "GitHub repository root URL (e.g., https://github.com/owner/repo)",
                }
            },
            "required": ["github_url"],
        }

    async def execute(self, github_url: str, **kwargs) -> ToolResult:
        layout = _workspace_layout_from_kwargs(kwargs)
        installer = SkillInstallerService(layout)
        result = await installer.install_from_github(github_url)
        if not result.success:
            return ToolResult(success=False, output="", error=result.message)
        return ToolResult(
            success=True,
            output=result.message,
            data={"path": result.path, "skill_name": result.skill_name, "github_url": result.github_url},
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
        return "List all validated installed skills."

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            layout = _workspace_layout_from_kwargs(kwargs)
            installed_dir = layout.installed_skills_dir
            if not installed_dir.exists():
                return ToolResult(success=True, output="No installed skills", data={"skills": []})

            skills = []
            for item in sorted(installed_dir.iterdir()):
                if not item.is_dir():
                    continue
                skill_md = item / "SKILL.md"
                if not skill_md.exists():
                    continue
                metadata_path = item / SKILL_METADATA_FILENAME
                source = {}
                if metadata_path.exists():
                    try:
                        source = json.loads(metadata_path.read_text(encoding="utf-8"))
                    except Exception:
                        source = {}
                skills.append(
                    {
                        "name": _skill_name_from_dir(item),
                        "slug": item.name,
                        "path": str(item),
                        "github_url": str(source.get("github_url", "") or ""),
                    }
                )

            if not skills:
                return ToolResult(
                    success=True,
                    output=f"No skills found in {installed_dir}",
                    data={"skills": []},
                )

            output_lines = [f"Installed skills ({len(skills)}):"]
            for skill in skills:
                suffix = f" - {skill['github_url']}" if skill["github_url"] else ""
                output_lines.append(f"  ✓ {skill['slug']}{suffix}")
            return ToolResult(success=True, output="\n".join(output_lines), data={"skills": skills})
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
