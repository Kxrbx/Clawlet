"""Explicit runtime assembly helpers for workspace-bound services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clawlet.agent.memory import MemoryManager
from clawlet.skills.runtime import SkillRuntime, build_skill_runtime
from clawlet.tools import ToolRegistry, create_default_tool_registry


@dataclass(slots=True)
class RuntimeServices:
    memory_manager: MemoryManager
    skill_runtime: SkillRuntime
    tools: ToolRegistry


def build_runtime_services(
    workspace: Path,
    config: Any = None,
    *,
    memory_manager: MemoryManager | None = None,
) -> RuntimeServices:
    """Assemble workspace-scoped memory, skills, and tool registry explicitly."""
    resolved_workspace = workspace.expanduser().resolve()
    resolved_memory_manager = memory_manager or MemoryManager(workspace=resolved_workspace)
    skill_runtime = build_skill_runtime(resolved_workspace, config)
    tools = create_default_tool_registry(
        allowed_dir=str(resolved_workspace),
        config=config,
        memory_manager=resolved_memory_manager,
        skill_registry=skill_runtime.registry,
    )
    return RuntimeServices(
        memory_manager=resolved_memory_manager,
        skill_runtime=skill_runtime,
        tools=tools,
    )
