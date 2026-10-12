"""Shared workspace path resolution (CLI-independent, no heavy imports)."""

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
