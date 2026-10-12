"""Qwen (Alibaba) provider implementation (OpenAI-compatible)."""

from typing import Optional

from clawlet.providers.openai_compat import OpenAICompatibleProvider


# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "qwen4",
    "qwen3",
    "qwen2.5-72b-instruct",
    "qwen2.5-32b-instruct",
    "qwen2.5-14b-instruct",
    "qwen2.5-7b-instruct",
    "qwen2-72b-instruct",
    "qwen2-7b-instruct",
]


class QwenProvider(OpenAICompatibleProvider):
    """Qwen (Alibaba) API provider."""

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    PROVIDER_NAME = "qwen"
    ENV_VAR_HINT = "QWEN_API_KEY"
    CONFIG_PATH_HINT = "provider.qwen.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "qwen4"

    def __init__(
        self,
        api_key: str,
        default_model: str = "qwen4",
        base_url: Optional[str] = None,
    ):
        super().__init__(api_key=api_key, default_model=default_model, base_url=base_url)
