"""
Content moderation providers package.
Each provider implements the BaseProvider interface.
"""

from .base import BaseProvider, ModerationResult, ContentType
from .shumei import ShumeiProvider

# Registry of available providers
PROVIDERS = {
    "shumei": ShumeiProvider,
    # "bytedance": BytedanceProvider,  # TODO: Implement
    # "yidun": YidunProvider,          # TODO: Implement
    # "juntong": JuntongProvider,      # TODO: Implement
}


def get_provider(name: str) -> BaseProvider:
    """
    Get a provider instance by name.
    
    Args:
        name: Provider name (e.g., 'shumei', 'bytedance')
        
    Returns:
        Provider instance
        
    Raises:
        ValueError: If provider is not found
    """
    provider_class = PROVIDERS.get(name.lower())
    if not provider_class:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {name}. Available: {available}")
    
    return provider_class()


def list_providers() -> list:
    """List all available provider names."""
    return list(PROVIDERS.keys())


__all__ = [
    "BaseProvider",
    "ModerationResult", 
    "ContentType",
    "ShumeiProvider",
    "get_provider",
    "list_providers",
    "PROVIDERS",
]
