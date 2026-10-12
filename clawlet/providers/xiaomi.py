"""Xiaomi provider implementation (OpenAI-compatible)."""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "mi-agent-2",
    "mi-agent-2-pro",
    "mi-reasoning",
    "mi-code",
]


class XiaomiProvider(OpenAICompatibleProvider):
    """Xiaomi API provider."""

    BASE_URL = "https://api.xiaomi.com/v1"
    PROVIDER_NAME = "xiaomi"
    ENV_VAR_HINT = "XIAOMI_API_KEY"
    CONFIG_PATH_HINT = "provider.xiaomi.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "mi-agent-2"

    def __init__(
        self,
        api_key: str,
        default_model: str = "mi-agent-2",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
