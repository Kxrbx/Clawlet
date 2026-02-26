"""Plugin discovery and loading helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Iterable

from loguru import logger

from clawlet.plugins.sdk import PluginTool


class PluginLoader:
    """Loads plugin tools from local plugin directories."""

    def __init__(self, directories: Iterable[Path]):
        self.directories = [Path(d) for d in directories]

    def load_tools(self) -> list[PluginTool]:
        tools: list[PluginTool] = []
        for directory in self.directories:
            if not directory.exists() or not directory.is_dir():
                continue
            plugin_file = directory / "plugin.py"
            if not plugin_file.exists():
                continue

            loaded = self._load_from_file(plugin_file)
            tools.extend(loaded)
        return tools

    def _load_from_file(self, plugin_file: Path) -> list[PluginTool]:
        tools: list[PluginTool] = []
        module_name = f"clawlet_plugin_{plugin_file.parent.name}"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if not spec or not spec.loader:
            return tools

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Failed to load plugin module {plugin_file}: {e}")
            return tools

        candidates = getattr(module, "TOOLS", [])
        for candidate in candidates:
            if isinstance(candidate, PluginTool):
                tools.append(candidate)
            else:
                logger.warning(f"Skipping non-plugin tool candidate in {plugin_file}: {candidate}")

        return tools
