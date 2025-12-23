"""
Content moderation providers package.
Each provider implements the BaseProvider interface.
"""

from .base import BaseProvider, ModerationResult, ContentType
from .shumei import ShumeiProvider
from .juntong import JunTongProvider
from .yidun import YidunProvider
from .huoshan import HuoshanProvider

# Registry of available providers
PROVIDERS = {
    "shumei": ShumeiProvider,
    "juntong": JunTongProvider,
    "yidun": YidunProvider,
    "huoshan": HuoshanProvider,
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
    "JunTongProvider",
    "YidunProvider",
    "HuoshanProvider",
    "get_provider",
    "list_providers",
    "PROVIDERS",
]
