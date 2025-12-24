"""
JunTong (君同未来) content moderation provider implementation.
API Documentation: 内部文档
"""

import time
import json
import logging
import requests
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


class JunTongProvider(BaseProvider):
    """
    JunTong (君同未来) content moderation provider.
    
    Supports:
        - Text moderation (conversation/detect API)
        - Image moderation (image API)
    
    Configuration (via environment variables):
        - JUNTONG_API_KEY: API key for authentication
        - JUNTONG_BASE_URL: Base URL for API (default: http://121.40.172.175:8269)
    """
    
    name = "juntong"
    display_name = "君同未来"
    
    # API endpoints
    TEXT_ENDPOINT = "/api/v1/shield/conversation/detect"
    IMAGE_ENDPOINT = "/api/v1/shield/image"
    
    def _load_config(self) -> Dict[str, Any]:
        """Load JunTong configuration from environment."""
        return Config.get_juntong_config()
    
    def _validate_config(self) -> None:
        """Validate JunTong configuration."""
        if not self.config.get("text_api_key") and not self.config.get("image_api_key"):
            raise ConfigurationError(
                "JUNTONG_TEXT_API_KEY or JUNTONG_IMAGE_API_KEY is required. "
                "Please set them in your .env file."
            )
    
    def moderate_text(self, text: str, **kwargs) -> ModerationResult:
        """
        Moderate text content using JunTong API.
        
        Args:
            text: Text content to moderate
            
        Returns:
            ModerationResult with risk assessment
        """
        url = f"{self.config['base_url']}{self.TEXT_ENDPOINT}"
        
        payload = {
            "input": text,
            "format": "simple",
            "stream": False,
            "reasoning": False,
        }
        
        return self._call_api(
            url=url,
            payload=payload,
            content_type=ContentType.TEXT,
        )
    
    def moderate_image(self, image_url: str, **kwargs) -> ModerationResult:
        """
        Moderate image content using JunTong API.
        
        Supports both URL and local file paths:
        - If image_url starts with 'http', uses URL upload
        - Otherwise, reads local file and uses Base64 upload
        
        Args:
            image_url: URL or local path of the image to moderate
            
        Returns:
            ModerationResult with risk assessment
        """
        url = f"{self.config['base_url']}{self.IMAGE_ENDPOINT}"
        
        # Check if it's a URL or local file path
        if image_url.startswith('http://') or image_url.startswith('https://'):
            # URL-based upload
            payload = {
                "image": image_url,
                "upload_type": "URL",
                "role": "user",
            }
        else:
            # Local file - convert to Base64
            import base64
            from pathlib import Path
            
            img_path = Path(image_url)
            if not img_path.exists():
                result = ModerationResult(
                    provider=self.name,
                    content_type=ContentType.IMAGE,
                )
                result.error = f"Image file not found: {image_url}"
                result.success = False
                return result
            
            try:
                with open(img_path, 'rb') as img_file:
                    img_data = img_file.read()
                    img_base64 = base64.b64encode(img_data).decode('utf-8')
            except Exception as e:
                result = ModerationResult(
                    provider=self.name,
                    content_type=ContentType.IMAGE,
                )
                result.error = f"Failed to read image: {e}"
                result.success = False
                return result
            
            payload = {
                "image": img_base64,
                "upload_type": "BASE64",
                "role": "user",
            }
        
        return self._call_api(
            url=url,
            payload=payload,
            content_type=ContentType.IMAGE,
        )
    
    def _call_api(
        self, 
        url: str, 
        payload: Dict[str, Any],
        content_type: ContentType,
    ) -> ModerationResult:
        """
        Make API call to JunTong with retry logic.
        
        Args:
            url: API endpoint URL
            payload: Request payload
            content_type: Type of content being moderated
            
        Returns:
            ModerationResult
        """
        result = ModerationResult(
            provider=self.name,
            content_type=content_type,
        )
        
        retry_times = Config.RETRY_TIMES
        timeout = Config.REQUEST_TIMEOUT
        
        # Use different API keys for text and image
        if content_type == ContentType.TEXT:
            api_key = self.config["text_api_key"]
        else:
            api_key = self.config["image_api_key"]
        
        headers = {
            "Content-Type": "application/json",
            "Shield-Api-Key": api_key,
        }
        
        for attempt in range(retry_times):
            try:
                start_time = time.time()
                
                # Log request details at DEBUG level
                logger.debug(f"\n{'='*60}")
                logger.debug(f">>> API REQUEST")
                logger.debug(f"{'='*60}")
                logger.debug(f"URL: {url}")
                logger.debug(f"Content Type: {content_type.value}")
                logger.debug(f"Payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
                
                result.response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    result.raw_response = data
                    result.success = True
                    
                    # Log response details at DEBUG level
                    logger.debug(f"\n{'='*60}")
                    logger.debug(f"<<< API RESPONSE")
                    logger.debug(f"{'='*60}")
                    logger.debug(f"Response Time: {result.response_time*1000:.0f}ms")
                    logger.debug(f"Full Response:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    # Parse response based on content type
                    if data.get("code") == 0:  # Success
                        if content_type == ContentType.TEXT:
                            self._parse_text_response(data, result)
                        else:
                            self._parse_image_response(data, result)
                    else:
                        result.error = f"API error: {data.get('code')} - {data.get('message')}"
                        result.success = False
                    
                    break
                else:
                    result.error = f"HTTP {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                result.error = f"Request timeout (attempt {attempt + 1}/{retry_times})"
                logger.warning(f"JunTong API timeout: {result.error}")
                
            except requests.exceptions.RequestException as e:
                result.error = f"Network error: {str(e)}"
                logger.error(f"JunTong API network error: {result.error}")
                
            except Exception as e:
                result.error = f"Unexpected error: {str(e)}"
                logger.error(f"JunTong API error: {result.error}")
            
            # Wait before retry
            if attempt < retry_times - 1:
                time.sleep(1)
        
        return result
    
    def _parse_text_response(self, data: Dict[str, Any], result: ModerationResult) -> None:
        """
        Parse JunTong text API response and populate result.
        
        Response format:
        {"code":0,"message":"成功","data":{"level":"high/medium/none","pass":true/false,"score":0-1}}
        
        Args:
            data: Raw API response
            result: ModerationResult to populate
        """
        response_data = data.get("data", {})
        
        # Parse risk level based on 'level' and 'pass' fields
        level = response_data.get("level", "none")
        passed = response_data.get("pass", True)
        score = response_data.get("score", 0.0)
        
        if passed:
            result.risk_level = RiskLevel.PASS
            result.risk_label = "正常"
            result.risk_labels = []
        elif level == "high":
            result.risk_level = RiskLevel.REJECT
            result.risk_label = "高风险"
            result.risk_labels = ["高风险内容"]
        elif level == "medium":
            result.risk_level = RiskLevel.REVIEW
            result.risk_label = "中风险"
            result.risk_labels = ["中风险内容"]
        else:
            result.risk_level = RiskLevel.REJECT
            result.risk_label = "风险内容"
            result.risk_labels = ["风险内容"]
        
        # Set confidence score
        result.confidence = score
    
    def _parse_image_response(self, data: Dict[str, Any], result: ModerationResult) -> None:
        """
        Parse JunTong image API response and populate result.
        
        Response format:
        {"code":0,"message":"成功","data":{"risk_event":[{"risk_level":"NO_RISK/RISK","risk_name":"合规检测"}]}}
        
        Args:
            data: Raw API response
            result: ModerationResult to populate
        """
        response_data = data.get("data", {})
        risk_events = response_data.get("risk_event", [])
        
        # Check risk level from risk_event array
        is_risk = False
        risk_labels = []
        
        for event in risk_events:
            risk_level = event.get("risk_level", "NO_RISK")
            risk_name = event.get("risk_name", "")
            
            if risk_level == "RISK":
                is_risk = True
                if risk_name:
                    risk_labels.append(risk_name)
        
        if is_risk:
            result.risk_level = RiskLevel.REJECT
            result.risk_label = risk_labels[0] if risk_labels else "风险图片"
            result.risk_labels = risk_labels if risk_labels else ["风险图片"]
            result.confidence = 1.0
        else:
            result.risk_level = RiskLevel.PASS
            result.risk_label = "正常"
            result.risk_labels = []
            result.confidence = 0.0
