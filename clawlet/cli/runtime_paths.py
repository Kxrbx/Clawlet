"""Shared runtime path resolution helpers."""

from __future__ import annotations

import os
from pathlib import Path

from clawlet.workspace_layout import WorkspaceLayout, get_workspace_layout


def get_default_workspace_path() -> Path:
    """Resolve the default workspace path, honoring explicit environment overrides."""
    configured = os.environ.get("CLAWLET_WORKSPACE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".clawlet").expanduser().resolve()


def get_workspace_layout_for(workspace: Path | None = None) -> WorkspaceLayout:
    return get_workspace_layout(workspace or get_default_workspace_path())


def resolve_replay_dir(workspace_path: Path) -> Path:
    """Resolve replay directory from runtime config with workspace-relative support."""
    from clawlet.config import RuntimeSettings

    runtime_cfg = RuntimeSettings()
    config_path = workspace_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            runtime_cfg = RuntimeSettings(**(raw.get("runtime") or {}))
        except Exception:
            pass

    replay_dir = Path(runtime_cfg.replay.directory).expanduser()
    if not replay_dir.is_absolute():
        replay_dir = workspace_path / replay_dir
    return replay_dir
