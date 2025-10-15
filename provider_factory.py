import os
from logger import get_logger
from providers.google import GoogleProvider
from providers.openai import OpenAIProvider
from providers.anthropic import AnthropicProvider

logger = get_logger(__name__)

# Registry of available providers
PROVIDER_REGISTRY = {
    "google": {
        "class": GoogleProvider,
        "api_key_env": "GOOGLE_API_KEY"
    },
    "openai": {
        "class": OpenAIProvider,
        "api_key_env": "OPENAI_API_KEY"
    },
    "anthropic": {
        "class": AnthropicProvider,
        "api_key_env": "ANTHROPIC_API_KEY"
    }
}


def get_provider(provider_name):
    """
    Factory function to get a provider instance from the registry.
    """
    provider_name = provider_name.lower()
    provider_config = PROVIDER_REGISTRY.get(provider_name)

    if not provider_config:
        raise ValueError(
            f"Unsupported provider. Choose from: {list(PROVIDER_REGISTRY.keys())}"
        )

    api_key_env = provider_config["api_key_env"]
    api_key = os.getenv(api_key_env)

    if not api_key:
        raise ValueError(
            f"API key environment variable '{api_key_env}' not set.")

    provider_class = provider_config["class"]
    return provider_class(api_key)
