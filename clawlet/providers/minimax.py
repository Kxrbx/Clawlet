"""MiniMax provider implementation (OpenAI-compatible)."""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "abab7-preview",
    "abab6.5s-chat",
    "abab6.5-chat",
    "abab6-chat",
    "abab5.5s-chat",
    "abab5.5-chat",
    "abab5-chat",
]


class MiniMaxProvider(OpenAICompatibleProvider):
    """MiniMax API provider."""

    BASE_URL = "https://api.minimax.chat/v1"
    PROVIDER_NAME = "minimax"
    ENV_VAR_HINT = "MINIMAX_API_KEY"
    CONFIG_PATH_HINT = "provider.minimax.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "abab7-preview"

    def __init__(
        self,
        api_key: str,
        default_model: str = "abab7-preview",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
