"""
Volcengine/Huoshan (火山引擎) LLM Shield content moderation provider implementation.
API Documentation: https://www.volcengine.com/docs/84990/1520618
"""

import time
import json
import logging
from typing import Dict, Any, List

from .base import (
    BaseProvider, 
    ModerationResult, 
    ContentType, 
    RiskLevel,
    ConfigurationError,
    APIError,
)
from ..config import Config

logger = logging.getLogger(__name__)

# Try to import volcengine SDK
try:
    from volcenginesdkllmshield import ClientV2, ModerateV2Request, MessageV2, ContentTypeV2
    HAS_VOLCENGINE_SDK = True
except ImportError:
    HAS_VOLCENGINE_SDK = False
    logger.warning("volcenginesdkllmshield not installed. Run: pip install volcengine-python-sdk")


class HuoshanProvider(BaseProvider):
    """
    Volcengine/Huoshan (火山引擎) LLM Shield content moderation provider.
    
    Uses the volcenginesdkllmshield SDK for API calls.
    
    Supports:
        - Text moderation (LLM Shield API)
        - Image moderation (not yet implemented)
    
    Configuration (via environment variables):
        - HUOSHAN_ACCESS_KEY: Volcengine Access Key (AK)
        - HUOSHAN_SECRET_KEY: Volcengine Secret Key (SK)
        - HUOSHAN_APP_ID: LLM Shield AppID
        - HUOSHAN_REGION: Region (cn-beijing or cn-shanghai)
    """
    
    name = "huoshan"
    display_name = "火山引擎"
    
    # Decision type mapping
    DECISION_MAPPING = {
        1: ("PASS", "通过"),
        2: ("REJECT", "拦截"),
        5: ("REVIEW", "安全代答"),
    }
    
    def _load_config(self) -> Dict[str, Any]:
        """Load Huoshan configuration from environment."""
        return Config.get_huoshan_config()
    
    def _validate_config(self) -> None:
        """Validate Huoshan configuration."""
        if not HAS_VOLCENGINE_SDK:
            raise ConfigurationError(
                "volcenginesdkllmshield SDK is not installed. "
                "Please run: pip install volcengine-python-sdk"
            )
        
        if not self.config.get("access_key") or not self.config.get("secret_key"):
            raise ConfigurationError(
                "HUOSHAN_ACCESS_KEY and HUOSHAN_SECRET_KEY are required. "
                "Please set them in your .env file."
            )
        
        if not self.config.get("app_id"):
            raise ConfigurationError(
                "HUOSHAN_APP_ID is required. "
                "Please set it in your .env file."
            )
    
    def _get_client(self):
        """Create and return LLM Shield client."""
        region = self.config.get("region", "cn-beijing")
        url = f"https://{region}.sdk.access.llm-shield.omini-shield.com"
        timeout = Config.REQUEST_TIMEOUT
        
        return ClientV2(
            url,
            self.config["access_key"],
            self.config["secret_key"],
            region,
            timeout
        )
    
    def moderate_text(self, text: str, **kwargs) -> ModerationResult:
        """
        Moderate text content using Huoshan LLM Shield API.
        
        Args:
            text: Text content to moderate
            role: Content role - 'user' (prompt), 'assistant' (response), 'system'
            
        Returns:
            ModerationResult with risk assessment
        """
        result = ModerationResult(
            provider=self.name,
            content_type=ContentType.TEXT,
        )
        
        role = kwargs.get("role", "user")
        retry_times = Config.RETRY_TIMES
        
        for attempt in range(retry_times):
            try:
                start_time = time.time()
                
                # Log request
                logger.debug(f"\n{'='*60}")
                logger.debug(f">>> API REQUEST")
                logger.debug(f"{'='*60}")
                logger.debug(f"AppID: {self.config['app_id']}")
                logger.debug(f"Role: {role}")
                logger.debug(f"Content: {text[:100]}...")
                
                # Create client and request
                client = self._get_client()
                request = ModerateV2Request(
                    scene=self.config["app_id"],
                    message=MessageV2(
                        role=role,
                        content=text,
                        contentType=ContentTypeV2.TEXT
                    )
                )
                
                # Make API call
                response = client.Moderate(request)
                
                result.response_time = time.time() - start_time
                result.success = True
                
                # Parse response
                raw_response = json.loads(response.model_dump_json(by_alias=True))
                result.raw_response = raw_response
                
                # Log response
                logger.debug(f"\n{'='*60}")
                logger.debug(f"<<< API RESPONSE")
                logger.debug(f"{'='*60}")
                logger.debug(f"Response Time: {result.response_time*1000:.0f}ms")
                logger.debug(f"Full Response:\n{json.dumps(raw_response, ensure_ascii=False, indent=2)}")
                
                # Extract decision
                decision_type = response.result.decision.decision_type
                decision_info = self.DECISION_MAPPING.get(decision_type, ("PASS", "未知"))
                
                if decision_type == 1:  # 通过
                    result.risk_level = RiskLevel.PASS
                    result.risk_label = "正常"
                    result.risk_labels = []
                elif decision_type == 2:  # 拦截
                    result.risk_level = RiskLevel.REJECT
                    # Extract risk labels
                    if response.result.risk_info and response.result.risk_info.risks:
                        labels = [risk.label for risk in response.result.risk_info.risks]
                        result.risk_labels = labels
                        result.risk_label = labels[0] if labels else "拦截"
                    else:
                        result.risk_label = "拦截"
                        result.risk_labels = ["拦截"]
                elif decision_type == 5:  # 安全代答
                    result.risk_level = RiskLevel.REVIEW
                    result.risk_label = "安全代答"
                    result.risk_labels = ["安全代答"]
                else:
                    result.risk_level = RiskLevel.PASS
                    result.risk_label = decision_info[1]
                
                result.confidence = 1.0 if decision_type != 1 else 0.0
                
                break
                
            except Exception as e:
                result.error = f"API error: {str(e)}"
                logger.error(f"Huoshan API error: {result.error}")
                
                if attempt < retry_times - 1:
                    time.sleep(1)
        
        return result
    
    def moderate_image(self, image_url: str, **kwargs) -> ModerationResult:
        """
        Moderate image content using Huoshan API.
        
        Note: Image moderation may not be supported by LLM Shield.
        
        Args:
            image_url: URL of the image to moderate
            
        Returns:
            ModerationResult with risk assessment
        """
        # LLM Shield is primarily for text (prompts/responses)
        # Image support may require different API
        return ModerationResult(
            provider=self.name,
            content_type=ContentType.IMAGE,
            success=False,
            error="Image moderation not supported by Huoshan LLM Shield. Use text moderation for prompts.",
        )
