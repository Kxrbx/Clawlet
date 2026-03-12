from __future__ import annotations

import asyncio
import os
import shutil
import stat
import tempfile
from pathlib import Path

from clawlet.cli.onboard import _merge_channel_tokens_into_config
from clawlet.config import Config, ProviderConfig, OllamaConfig
from clawlet.tools.http_request import HttpRequestTool


def main() -> int:
    workspace_dir = Path(tempfile.mkdtemp(prefix="clawlet-release-regression-"))
    try:
        config = Config(provider=ProviderConfig(primary="ollama", ollama=OllamaConfig()))
        _merge_channel_tokens_into_config(
            config,
            telegram_token="test-telegram-token",
            discord_token="test-discord-token",
        )
        config_path = workspace_dir / "config.yaml"
        config.save(config_path)

        loaded = Config.from_yaml(config_path)
        telegram = loaded.channels.get("telegram", {})
        discord = loaded.channels.get("discord", {})
        if not bool(getattr(telegram, "enabled", telegram.get("enabled", False))):
            raise SystemExit("Onboarding channel merge did not enable telegram in canonical channels config")
        if not bool(getattr(discord, "enabled", discord.get("enabled", False))):
            raise SystemExit("Onboarding channel merge did not enable discord in canonical channels config")

        mode = stat.S_IMODE(config_path.stat().st_mode)
        if mode != 0o600:
            raise SystemExit(f"Config permissions are not 0600: {oct(mode)}")

        creds_dir = workspace_dir / ".config" / "example_service"
        creds_dir.mkdir(parents=True, exist_ok=True)
        (creds_dir / "credentials.json").write_text('{"api_key":"example-token"}', encoding="utf-8")
        tool = HttpRequestTool(
            workspace=workspace_dir,
            auth_profiles={
                "example_service": {
                    "bearer_token_path": ".config/example_service/credentials.json",
                    "header_name": "Authorization",
                    "header_prefix": "Bearer ",
                }
            },
        )
        explicit_headers = tool._apply_local_auth(
            "https://api.example.com/v1/status",
            {},
            auth_profile="example_service",
        )
        if explicit_headers.get("Authorization") != "Bearer example-token":
            raise SystemExit("Explicit auth_profile did not inject the configured bearer token")

        implicit_headers = tool._apply_local_auth("https://api.example.com/v1/status", {}, auth_profile=None)
        if "Authorization" in implicit_headers:
            raise SystemExit("http_request injected credentials without an explicit auth_profile")

    finally:
        shutil.rmtree(workspace_dir, ignore_errors=True)

    print("release regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
