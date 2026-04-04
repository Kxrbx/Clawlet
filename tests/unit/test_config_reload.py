from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from clawlet.config import Config
from clawlet.health import HealthChecker, HealthStatus


def test_config_reload_returns_new_instance(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
provider:
  primary: openrouter
  openrouter:
    api_key: before
""".strip(),
        encoding="utf-8",
    )

    config = Config.from_yaml(config_path)
    config.config_path = config_path

    config_path.write_text(
        """
provider:
  primary: openrouter
  openrouter:
    api_key: after
""".strip(),
        encoding="utf-8",
    )

    reloaded = config.reload()

    assert reloaded is not config
    assert reloaded.config_path == config_path
    assert config.provider.openrouter.api_key == "before"
    assert reloaded.provider.openrouter.api_key == "after"


@pytest.mark.asyncio
async def test_check_memory_mentions_monitoring_extra_when_psutil_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("psutil missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = await HealthChecker().check_memory()

    assert result.status == HealthStatus.HEALTHY
    assert "clawlet[monitoring]" in result.message
