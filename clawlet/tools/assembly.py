"""Explicit tool assembly helpers grouped by capability area."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from clawlet.tools.files import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from clawlet.tools.patch import ApplyPatchTool
from clawlet.tools.fetch_url import FetchUrlTool
from clawlet.tools.http_request import HttpRequestTool
from clawlet.tools.memory import MemoryTools
from clawlet.tools.registry import ToolRegistry
from clawlet.tools.shell import ShellTool
from clawlet.tools.skills import InstallSkillTool, ListSkillsTool
from clawlet.tools.web_search import WebSearchTool


FULL_EXEC_COMMANDS = [
    "mkdir", "cp", "mv", "rm", "touch", "chmod", "chown",
    "curl", "wget", "ssh", "scp", "rsync",
    "make", "docker", "kubectl", "terraform",
    "rg",
]


def register_file_and_shell_tools(
    registry: ToolRegistry,
    *,
    allowed_dir: str | None,
    config: Any = None,
) -> None:
    agent_mode = getattr(getattr(config, "agent", None), "mode", "safe") if config is not None else "safe"
    allow_dangerous = bool(getattr(getattr(config, "agent", None), "shell_allow_dangerous", False)) if config is not None else False
    use_rust_core = False
    effective_allowed_dir = None if agent_mode == "full_exec" else allowed_dir

    tools = [
        ReadFileTool(allowed_dir, use_rust_core=use_rust_core),
        WriteFileTool(allowed_dir, use_rust_core=use_rust_core),
        EditFileTool(allowed_dir, use_rust_core=use_rust_core),
        ApplyPatchTool(allowed_dir, use_rust_core=use_rust_core),
        ListDirTool(allowed_dir, use_rust_core=use_rust_core),
    ]
    for tool in tools:
        registry.register(tool)

    shell_tool = ShellTool(
        workspace=effective_allowed_dir,
        allow_dangerous=allow_dangerous,
        use_rust_core=use_rust_core,
    )
    if agent_mode == "full_exec":
        shell_tool.add_allowed(*FULL_EXEC_COMMANDS)
    registry.register(shell_tool)


def register_network_tools(
    registry: ToolRegistry,
    *,
    allowed_dir: str | None,
    config: Any = None,
) -> None:
    registry.register(FetchUrlTool())
    auth_profiles = {}
    if config is not None:
        raw_profiles = getattr(config, "http_auth_profiles", {}) or {}
        for name, profile in raw_profiles.items():
            if hasattr(profile, "model_dump"):
                auth_profiles[str(name)] = profile.model_dump(mode="python")
            else:
                auth_profiles[str(name)] = dict(profile or {})
    registry.register(HttpRequestTool(workspace=allowed_dir, auth_profiles=auth_profiles))

    api_key = None
    web_search_cfg = getattr(config, "web_search", None) if config is not None else None
    if web_search_cfg:
        api_key = web_search_cfg.api_key or os.environ.get("WEB_SEARCH_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")
    else:
        api_key = os.environ.get("WEB_SEARCH_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")
    registry.register(WebSearchTool(api_key=api_key))
    registry.register_alias("search_web", "web_search")
    registry.register_alias("websearch", "web_search")
    registry.register_alias("brave_search", "web_search")


def register_skill_tools(
    registry: ToolRegistry,
    *,
    skill_registry: Any = None,
) -> None:
    registry.register(InstallSkillTool(skill_registry=skill_registry))
    registry.register(ListSkillsTool(skill_registry=skill_registry))
    if skill_registry is not None:
        skill_registry.register_tools_with_registry(registry)


def register_memory_tools(
    registry: ToolRegistry,
    *,
    memory_manager: Any = None,
) -> None:
    if memory_manager is None:
        return
    memory_tools = MemoryTools(memory_manager)
    for tool in memory_tools.all_tools():
        registry.register(tool)
    registry.register_alias("recall_memory", "recall")
    registry.register_alias("search_memories", "search_memory")
    registry.register_alias("recent_memory", "recent_memories")
    registry.register_alias("daily_notes", "review_daily_notes")
    registry.register_alias("memory_maintenance", "curate_memory")
    registry.register_alias("memory_overview", "memory_status")


def register_plugin_tools(
    registry: ToolRegistry,
    *,
    allowed_dir: str | None,
    config: Any = None,
) -> None:
    plugin_cfg = getattr(config, "plugins", None) if config is not None else None
    if not plugin_cfg or not plugin_cfg.auto_load:
        return
    base_dir = Path(allowed_dir).expanduser() if allowed_dir else Path.cwd()
    plugin_dirs = []
    for raw_dir in plugin_cfg.directories:
        candidate = Path(raw_dir).expanduser()
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        plugin_dirs.append(candidate)
    from clawlet.plugins.loader import PluginLoader

    loader = PluginLoader(plugin_dirs)
    for tool in loader.load_tools():
        registry.register(tool)
