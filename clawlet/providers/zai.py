"""Z.AI (GLM) provider implementation (OpenAI-compatible)."""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "glm-5",
    "glm-4-7b",
    "glm-4-32k",
    "glm-4v",
    "glm-3-turbo",
]


class ZAIProvider(OpenAICompatibleProvider):
    """Z.AI (GLM) API provider."""

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    PROVIDER_NAME = "zai"
    ENV_VAR_HINT = "ZAI_API_KEY"
    CONFIG_PATH_HINT = "provider.zai.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "glm-5"

    def __init__(
        self,
        api_key: str,
        default_model: str = "glm-5",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
