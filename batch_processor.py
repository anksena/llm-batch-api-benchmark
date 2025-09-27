import os
from providers.google import GoogleProvider
from providers.openai import OpenAIProvider

def get_provider(provider_name):
    if provider_name.lower() == "google":
        api_key = os.getenv("GEMINI_API_KEY")
        return GoogleProvider(api_key)
    elif provider_name.lower() == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        return OpenAIProvider(api_key)
    else:
        raise ValueError("Unsupported provider. Choose 'google' or 'openai'.")
