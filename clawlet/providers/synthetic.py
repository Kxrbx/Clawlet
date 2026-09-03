"""Synthetic AI provider implementation (OpenAI-compatible).
Privacy-focused AI platform.
"""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "synthetic-llm-2",
    "synthetic-llm-2-reasoning",
    "synthetic-code-2",
    "synthetic-llm-1",
]


class SyntheticProvider(OpenAICompatibleProvider):
    """Synthetic AI API provider."""

    BASE_URL = "https://api.synthetic.ai/v1"
    PROVIDER_NAME = "synthetic"
    ENV_VAR_HINT = "SYNTHETIC_API_KEY"
    CONFIG_PATH_HINT = "provider.synthetic.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "synthetic-llm-2"

    def __init__(
        self,
        api_key: str,
        default_model: str = "synthetic-llm-2",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
