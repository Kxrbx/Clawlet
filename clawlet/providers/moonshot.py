"""Moonshot AI (Kimi) provider implementation (OpenAI-compatible)."""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "kimi-k2.5",
    "kimi-k1.5",
    "moonshot-v1-8k",
    "moonshot-v1-32k",
    "moonshot-v1-128k",
]


class MoonshotProvider(OpenAICompatibleProvider):
    """Moonshot AI (Kimi) API provider."""

    BASE_URL = "https://api.moonshot.ai/v1"
    PROVIDER_NAME = "moonshot"
    ENV_VAR_HINT = "MOONSHOT_API_KEY"
    CONFIG_PATH_HINT = "provider.moonshot.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "kimi-k2.5"

    def __init__(
        self,
        api_key: str,
        default_model: str = "kimi-k2.5",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
