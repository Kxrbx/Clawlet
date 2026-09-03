"""GitHub Copilot provider implementation (OpenAI-compatible)."""


from clawlet.providers.openai_compat import OpenAICompatibleProvider

# Default models list (fallback when API is unavailable)
DEFAULT_MODELS = [
    "gpt-4.2",
    "gpt-4o",
    "claude-3.5-sonnet",
    "claude-3-opus",
]


class CopilotProvider(OpenAICompatibleProvider):
    """GitHub Copilot API provider."""

    BASE_URL = "https://api.github.com/copilot"
    PROVIDER_NAME = "copilot"
    ENV_VAR_HINT = "GITHUB_TOKEN"
    CONFIG_PATH_HINT = "provider.copilot.api_key"
    DEFAULT_MODELS = DEFAULT_MODELS
    FALLBACK_MODEL = "gpt-4.2"

    def __init__(
        self,
        access_token: str = "",
        default_model: str = "gpt-4.2",
        base_url: str | None = None,
        **kwargs,
    ):
        # Note: Use a GitHub Personal Access Token with 'copilot' scope.
        super().__init__(
            api_key=access_token or kwargs.get("api_key", ""),
            default_model=default_model,
            base_url=base_url,
        )
