"""OpenCode Zen provider implementation (OpenAI-compatible)."""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "zen-3.0",
    "zen-2.5",
    "zen-code-3.0",
    "zen-reasoning",
]


class OpenCodeZenProvider(OpenAICompatibleProvider):
    """OpenCode Zen API provider."""

    BASE_URL = "https://api.opencode.ai/v1"
    PROVIDER_NAME = "opencode_zen"
    ENV_VAR_HINT = "OPENCODE_ZEN_API_KEY"
    CONFIG_PATH_HINT = "provider.opencode_zen.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "zen-3.0"

    def __init__(
        self,
        api_key: str,
        default_model: str = "zen-3.0",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
