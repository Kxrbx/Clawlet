"""Venice AI provider implementation (OpenAI-compatible).
Uncensored models.
"""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "venice-llama-4",
    "venice-llama-3-70b",
    "venice-llama-3-8b",
    "venice-mistral",
    "venice-uncensored",
]


class VeniceProvider(OpenAICompatibleProvider):
    """Venice AI API provider."""

    BASE_URL = "https://api.venice.ai/api/v1"
    PROVIDER_NAME = "venice"
    ENV_VAR_HINT = "VENICE_API_KEY"
    CONFIG_PATH_HINT = "provider.venice.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "venice-llama-4"

    def __init__(
        self,
        api_key: str,
        default_model: str = "venice-llama-4",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
