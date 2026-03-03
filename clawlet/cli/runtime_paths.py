"""Shared runtime path resolution helpers for CLI modules."""

from __future__ import annotations

from pathlib import Path


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
