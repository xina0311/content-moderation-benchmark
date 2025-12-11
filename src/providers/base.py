"""
Base provider interface for content moderation services.
All providers must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time


class ContentType(Enum):
    """Types of content that can be moderated."""
    TEXT = "text"
    IMAGE = "image"
    # Future support
    # AUDIO = "audio"
    # VIDEO = "video"


class RiskLevel(Enum):
    """Standard risk levels."""
    PASS = "PASS"       # Safe content
    REVIEW = "REVIEW"   # Needs manual review
    REJECT = "REJECT"   # Should be blocked


@dataclass
class ModerationResult:
    """
    Standardized result from content moderation API.
    All providers should return results in this format.
    """
    # Request status
    success: bool = False
    error: Optional[str] = None
    
    # Risk assessment
    risk_level: RiskLevel = RiskLevel.PASS
    risk_label: str = "正常"           # Primary risk label (Chinese)
    risk_labels: List[str] = field(default_factory=list)  # All detected risk labels
    confidence: float = 0.0            # Confidence score (0-1)
    
    # Performance metrics
    response_time: float = 0.0         # Response time in seconds
    
    # Raw data for debugging
    raw_response: Optional[Dict[str, Any]] = None
    
    # Provider info
    provider: str = ""
    content_type: ContentType = ContentType.TEXT
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "error": self.error,
            "risk_level": self.risk_level.value,
            "risk_label": self.risk_label,
            "risk_labels": self.risk_labels,
            "confidence": self.confidence,
            "response_time": self.response_time,
            "provider": self.provider,
            "content_type": self.content_type.value,
        }


class BaseProvider(ABC):
    """
    Abstract base class for content moderation providers.
    
    All provider implementations must inherit from this class
    and implement the required methods.
    
    Example:
        class MyProvider(BaseProvider):
            name = "myprovider"
            
            def moderate_text(self, text, **kwargs):
                # Implementation
                pass
    """
    
    # Provider identification
    name: str = "base"
    display_name: str = "Base Provider"
    
    # Supported content types
    supported_types: List[ContentType] = [ContentType.TEXT, ContentType.IMAGE]
    
    def __init__(self):
        """Initialize provider with configuration."""
        self.config = self._load_config()
        self._validate_config()
    
    @abstractmethod
    def _load_config(self) -> Dict[str, Any]:
        """
        Load provider-specific configuration.
        
        Returns:
            Dictionary containing provider configuration
        """
        pass
    
    def _validate_config(self) -> None:
        """
        Validate that required configuration is present.
        Raises ConfigurationError if validation fails.
        """
        pass
    
    @abstractmethod
    def moderate_text(self, text: str, **kwargs) -> ModerationResult:
        """
        Moderate text content.
        
        Args:
            text: Text content to moderate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            ModerationResult with risk assessment
        """
        pass
    
    @abstractmethod
    def moderate_image(self, image_url: str, **kwargs) -> ModerationResult:
        """
        Moderate image content.
        
        Args:
            image_url: URL of the image to moderate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            ModerationResult with risk assessment
        """
        pass
    
    def moderate(self, content: str, content_type: ContentType, **kwargs) -> ModerationResult:
        """
        General moderation method that routes to specific type handler.
        
        Args:
            content: Content to moderate (text or image URL)
            content_type: Type of content
            **kwargs: Additional parameters
            
        Returns:
            ModerationResult
        """
        if content_type == ContentType.TEXT:
            return self.moderate_text(content, **kwargs)
        elif content_type == ContentType.IMAGE:
            return self.moderate_image(content, **kwargs)
        else:
            return ModerationResult(
                success=False,
                error=f"Unsupported content type: {content_type}",
                provider=self.name,
                content_type=content_type,
            )
    
    def health_check(self) -> bool:
        """
        Check if the provider is configured and accessible.
        
        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            # Try a simple text moderation
            result = self.moderate_text("test")
            return result.success
        except Exception:
            return False
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class ConfigurationError(ProviderError):
    """Raised when provider configuration is invalid."""
    pass


class APIError(ProviderError):
    """Raised when API call fails."""
    pass
