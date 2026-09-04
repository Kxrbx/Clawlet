"""Provider factory — build a provider instance from a task profile.

Centralizes the provider-construction ladder (previously duplicated in
``cli/models_ui.py``) so the orchestrator and CLI share one
code path: ``(provider_name, model_override, ProviderConfig) -> provider``.
"""

from __future__ import annotations

from typing import Any


def _credentials_for(provider_config: Any, provider_name: str) -> dict[str, str]:
    """Resolve API credentials: environment variable first, config second."""
    env_by_provider = {
        "openrouter": ("OPENROUTER_API_KEY", "api_key"),
        "openai": ("OPENAI_API_KEY", "api_key"),
        "anthropic": ("ANTHROPIC_API_KEY", "api_key"),
        "minimax": ("MINIMAX_API_KEY", "api_key"),
        "moonshot": ("MOONSHOT_API_KEY", "api_key"),
        "google": ("GOOGLE_API_KEY", "api_key"),
        "qwen": ("QWEN_API_KEY", "api_key"),
        "zai": ("ZAI_API_KEY", "api_key"),
        "copilot": ("GITHUB_TOKEN", "access_token"),
        "vercel": ("VERCEL_API_KEY", "api_key"),
        "opencode_zen": ("OPENCODE_ZEN_API_KEY", "api_key"),
        "xiaomi": ("XIAOMI_API_KEY", "api_key"),
        "synthetic": ("SYNTHETIC_API_KEY", "api_key"),
        "venice": ("VENICE_API_KEY", "api_key"),
    }
    import os

    section = getattr(provider_config, provider_name, None)
    if provider_name in ("ollama", "lmstudio"):
        return {}
    env_var, field_name = env_by_provider.get(provider_name, ("", "api_key"))
    env_value = os.environ.get(env_var, "") if env_var else ""
    config_value = getattr(section, field_name, "") if section is not None else ""
    return {field_name: env_value or config_value or ""}


def build_provider(
    provider_name: str,
    provider_config: Any,
    *,
    model: str = "",
) -> Any:
    """Build a provider instance for ``provider_name``.

    ``model`` overrides the configured default model when non-empty.
    Raises :class:`ValueError` for unknown provider names.
    """
    name = (provider_name or "").strip().lower() or "openrouter"
    section = getattr(provider_config, name, None)
    default_model = model.strip() or getattr(section, "model", "") or ""
    credentials = _credentials_for(provider_config, name)

    if name == "openrouter":
        from clawlet.providers.openrouter import OpenRouterProvider

        return OpenRouterProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "openai":
        from clawlet.providers.openai import OpenAIProvider

        organization = getattr(section, "organization", None)
        return OpenAIProvider(
            api_key=credentials.get("api_key", ""),
            default_model=default_model,
            organization=organization,
        )
    if name == "anthropic":
        from clawlet.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "minimax":
        from clawlet.providers.minimax import MiniMaxProvider

        return MiniMaxProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "moonshot":
        from clawlet.providers.moonshot import MoonshotProvider

        return MoonshotProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "google":
        from clawlet.providers.google import GoogleProvider

        return GoogleProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "qwen":
        from clawlet.providers.qwen import QwenProvider

        return QwenProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "zai":
        from clawlet.providers.zai import ZAIProvider

        return ZAIProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "copilot":
        from clawlet.providers.copilot import CopilotProvider

        return CopilotProvider(
            access_token=credentials.get("access_token", ""),
            default_model=default_model,
        )
    if name == "vercel":
        from clawlet.providers.vercel import VercelProvider

        return VercelProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "opencode_zen":
        from clawlet.providers.opencode_zen import OpenCodeZenProvider

        return OpenCodeZenProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "xiaomi":
        from clawlet.providers.xiaomi import XiaomiProvider

        return XiaomiProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "synthetic":
        from clawlet.providers.synthetic import SyntheticProvider

        return SyntheticProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "venice":
        from clawlet.providers.venice import VeniceProvider

        return VeniceProvider(
            api_key=credentials.get("api_key", ""), default_model=default_model
        )
    if name == "ollama":
        from clawlet.providers.ollama import OllamaProvider

        base_url = (
            getattr(section, "base_url", "http://localhost:11434")
            or "http://localhost:11434"
        )
        return OllamaProvider(
            base_url=base_url, default_model=default_model or "llama3.2"
        )
    if name == "lmstudio":
        from clawlet.providers.lmstudio import LMStudioProvider

        base_url = (
            getattr(section, "base_url", "http://localhost:1234")
            or "http://localhost:1234"
        )
        return LMStudioProvider(
            base_url=base_url, default_model=default_model or "local-model"
        )
    raise ValueError(f"Unknown provider: {provider_name!r}")
