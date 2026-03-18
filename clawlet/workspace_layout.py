"""Workspace domain boundaries for runtime state, user work, and installed assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WorkspaceLayout:
    root: Path

    @property
    def runtime_dir(self) -> Path:
        return self.root / ".runtime"

    @property
    def memory_dir(self) -> Path:
        return self.root / "memory"

    @property
    def notes_dir(self) -> Path:
        return self.root / "notes"

    @property
    def project_dir(self) -> Path:
        return self.root / "workspace"

    @property
    def notes_db_path(self) -> Path:
        return self.root / "notes.db"

    @property
    def config_path(self) -> Path:
        return self.root / "config.yaml"

    @property
    def database_path(self) -> Path:
        return self.root / "clawlet.db"

    @property
    def soul_path(self) -> Path:
        return self.root / "SOUL.md"

    @property
    def user_path(self) -> Path:
        return self.root / "USER.md"

    @property
    def memory_markdown_path(self) -> Path:
        return self.root / "MEMORY.md"

    @property
    def heartbeat_path(self) -> Path:
        return self.root / "HEARTBEAT.md"

    @property
    def health_history_path(self) -> Path:
        return self.runtime_dir / "health_history.jsonl"

    @property
    def installed_skills_dir(self) -> Path:
        return self.root / ".skills" / "installed"

    @property
    def skill_sources_dir(self) -> Path:
        return self.runtime_dir / "skill-sources"

    @property
    def legacy_skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def heartbeat_state_path(self) -> Path:
        return self.memory_dir / "heartbeat-state.json"

    @property
    def agent_pid_path(self) -> Path:
        return self.runtime_dir / "agent.pid"

    def ensure_directories(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.installed_skills_dir.mkdir(parents=True, exist_ok=True)
        self.skill_sources_dir.mkdir(parents=True, exist_ok=True)

    def context_roots(self) -> list[Path]:
        """Return the workspace roots that should participate in prompt context indexing."""
        return [self.root]

    def resolve(self, path: Path | str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        return candidate.resolve()

    def resolve_many(self, paths: Iterable[Path | str]) -> list[Path]:
        return [self.resolve(path) for path in paths]


def get_workspace_layout(workspace: Path | str) -> WorkspaceLayout:
    root = Path(workspace).expanduser().resolve()
    return WorkspaceLayout(root=root)
