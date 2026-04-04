from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clawlet.bus.queue import MessageBus
from clawlet.agent.memory import MemoryManager
from clawlet.providers.base import LLMResponse


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ("SOUL.md", "USER.md", "MEMORY.md", "HEARTBEAT.md"):
        (workspace / name).write_text(f"# {name}\n", encoding="utf-8")
    return workspace


@pytest.fixture
def mock_provider():
    class _Provider:
        name = "mock"

        async def complete(self, *args, **kwargs):
            return LLMResponse(content="ok", model="mock", usage={})

        async def stream(self, *args, **kwargs):
            if False:
                yield ""

        def get_default_model(self) -> str:
            return "mock"

        async def close(self) -> None:
            return None

    return _Provider()


@pytest.fixture
def mock_bus() -> MessageBus:
    return MessageBus()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    path = tmp_path / "workspace"
    path.mkdir()
    return path


@pytest.fixture
def memory_manager(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> MemoryManager:
    manager = MemoryManager(workspace=workspace)

    async def noop_initialize() -> None:
        return None

    async def noop_upsert(entry) -> None:
        return None

    async def noop_delete(key) -> None:
        return None

    monkeypatch.setattr(manager, "initialize", noop_initialize)
    monkeypatch.setattr(manager, "_upsert_db_entry", noop_upsert)
    monkeypatch.setattr(manager, "_delete_db_entry", noop_delete)
    monkeypatch.setattr(manager, "_append_daily_note", lambda entry: None)
    return manager
