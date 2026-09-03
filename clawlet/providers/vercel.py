"""Vercel AI Gateway provider implementation (OpenAI-compatible)."""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "openai/gpt-5",
    "openai/gpt-4o",
    "openai/gpt-4-turbo",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "google/gemini-1.5-pro",
    "google/gemini-1.5-flash",
]


class VercelProvider(OpenAICompatibleProvider):
    """Vercel AI Gateway provider."""

    BASE_URL = "https://gateway.ai.cloudflare.com/v1"
    PROVIDER_NAME = "vercel"
    ENV_VAR_HINT = "VERCEL_API_KEY"
    CONFIG_PATH_HINT = "provider.vercel.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "openai/gpt-5"

    def __init__(
        self,
        api_key: str,
        default_model: str = "openai/gpt-5",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
