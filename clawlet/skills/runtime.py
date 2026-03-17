"""Assembly helpers for workspace-bound skill runtime components."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clawlet.skills.installer import SkillInstallerService
from clawlet.skills.registry import SkillRegistry
from clawlet.workspace_layout import get_workspace_layout


@dataclass(slots=True)
class SkillRuntime:
    registry: SkillRegistry
    installer: SkillInstallerService


def build_skill_runtime(workspace: Path, config: Any = None) -> SkillRuntime:
    layout = get_workspace_layout(workspace)
    registry = SkillRegistry(workspace=layout.root)
    installer = SkillInstallerService(layout)
    registry.load_bundled_skills()

    skill_dirs = list(getattr(getattr(config, "skills", None), "directories", []) or [])
    for skill_dir in skill_dirs:
        registry.add_skill_directory(layout.resolve(skill_dir))

    return SkillRuntime(registry=registry, installer=installer)
