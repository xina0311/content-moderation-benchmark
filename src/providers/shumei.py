"""
Shumei (数美科技) content moderation provider implementation.
API Documentation: https://www.ishumei.com/help/documents.html
"""

import time
import json
import base64
import logging
import requests
from pathlib import Path
from typing import Dict, Any, List

from .base import (
    BaseProvider, 
    ModerationResult, 
    ContentType, 
    RiskLevel,
    ConfigurationError,
    APIError,
)
from ..config import Config, RISK_LABEL_MAPPING

logger = logging.getLogger(__name__)


class ShumeiProvider(BaseProvider):
    """
    Shumei (数美科技) content moderation provider.
    
    Supports:
        - Text moderation (v4 API)
        - Image moderation (v4 API)
    
    Configuration (via environment variables):
        - SHUMEI_ACCESS_KEY: API access key
        - SHUMEI_APP_ID: Application ID (default: 'default')
        - SHUMEI_TEXT_URL: Text API endpoint
        - SHUMEI_IMAGE_URL: Image API endpoint
    """
    
    name = "shumei"
    display_name = "数美科技"
    
    # Default event IDs
    TEXT_EVENT_ID = "input"   # User input content
    IMAGE_EVENT_ID = "input"
    
    # Detection types
    TEXT_TYPE = "TEXTRISK"
    IMAGE_TYPE = "POLITY_EROTIC_VIOLENT_ADVERT_QRCODE_IMGTEXTRISK"
    
    def _load_config(self) -> Dict[str, Any]:
        """Load Shumei configuration from environment."""
        return Config.get_shumei_config()
    
    def _validate_config(self) -> None:
        """Validate Shumei configuration."""
        if not self.config.get("access_key"):
            raise ConfigurationError(
                "SHUMEI_ACCESS_KEY is required. "
                "Please set it in your .env file."
            )
    
    def moderate_text(self, text: str, **kwargs) -> ModerationResult:
        """
        Moderate text content using Shumei API.
        
        Args:
            text: Text content to moderate
            token_id: User identifier (optional)
            event_id: Event type (optional, default: 'input')
            
        Returns:
            ModerationResult with risk assessment
        """
        token_id = kwargs.get("token_id", "benchmark_user")
        event_id = kwargs.get("event_id", self.TEXT_EVENT_ID)
        
        payload = {
            "accessKey": self.config["access_key"],
            "appId": self.config["app_id"],
            "eventId": event_id,
            "type": self.TEXT_TYPE,
            "data": {
                "text": text,
                "tokenId": token_id,
            }
        }
        
        return self._call_api(
            url=self.config["text_url"],
            payload=payload,
            content_type=ContentType.TEXT,
        )
    
    def moderate_image(self, image_source: str, **kwargs) -> ModerationResult:
        """
        Moderate image content using Shumei API.
        
        Args:
            image_source: URL or local file path of the image to moderate
            token_id: User identifier (optional)
            event_id: Event type (optional, default: 'input')
            
        Returns:
            ModerationResult with risk assessment
        """
        token_id = kwargs.get("token_id", "benchmark_user")
        event_id = kwargs.get("event_id", self.IMAGE_EVENT_ID)
        
        # Check if it's a local file path
        img_data = self._prepare_image_data(image_source)
        
        payload = {
            "accessKey": self.config["access_key"],
            "appId": self.config["app_id"],
            "eventId": event_id,
            "type": self.IMAGE_TYPE,
            "data": {
                "img": img_data,
                "tokenId": token_id,
            }
        }
        
        return self._call_api(
            url=self.config["image_url"],
            payload=payload,
            content_type=ContentType.IMAGE,
        )
    
    def _prepare_image_data(self, image_source: str) -> str:
        """
        Prepare image data for API request.
        
        Args:
            image_source: URL or local file path
            
        Returns:
            URL string or BASE64 encoded image data
        """
        # Check if it's a URL
        if image_source.startswith(('http://', 'https://')):
            return image_source
        
        # Check if it's a local file
        path = Path(image_source)
        if path.exists() and path.is_file():
            try:
                with open(path, 'rb') as f:
                    img_bytes = f.read()
                    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                    logger.debug(f"Converted local image to BASE64: {path.name} ({len(img_bytes)} bytes)")
                    return img_base64
            except Exception as e:
                logger.error(f"Failed to read local image {image_source}: {e}")
                # Fall back to treating it as URL
                return image_source
        
        # Assume it's a URL or already BASE64
        return image_source
    
    def _call_api(
        self, 
        url: str, 
        payload: Dict[str, Any],
        content_type: ContentType,
    ) -> ModerationResult:
        """
        Make API call to Shumei with retry logic.
        
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
        
        for attempt in range(retry_times):
            try:
                start_time = time.time()
                
                # Log request details at DEBUG level
                logger.debug(f"\n{'='*60}")
                logger.debug(f">>> API REQUEST")
                logger.debug(f"{'='*60}")
                logger.debug(f"URL: {url}")
                logger.debug(f"Content Type: {content_type.value}")
                # Don't log accessKey and BASE64 data for security/readability
                safe_payload = {}
                for k, v in payload.items():
                    if k == 'accessKey':
                        safe_payload[k] = '***HIDDEN***'
                    elif k == 'data' and isinstance(v, dict):
                        safe_data = {}
                        for dk, dv in v.items():
                            if dk == 'img' and isinstance(dv, str) and len(dv) > 200 and not dv.startswith('http'):
                                safe_data[dk] = f"[BASE64 DATA - {len(dv)} chars]"
                            else:
                                safe_data[dk] = dv
                        safe_payload[k] = safe_data
                    else:
                        safe_payload[k] = v
                logger.debug(f"Payload:\n{json.dumps(safe_payload, ensure_ascii=False, indent=2)}")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
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
                    logger.debug(f"Risk Level: {data.get('riskLevel', 'N/A')}")
                    logger.debug(f"Risk Label: {data.get('riskLabel1', 'N/A')}")
                    logger.debug(f"Risk Description: {data.get('riskDescription', 'N/A')}")
                    logger.debug(f"Full Response:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    # Parse response
                    if data.get("code") == 1100:  # Success
                        self._parse_response(data, result)
                    else:
                        result.error = f"API error: {data.get('code')} - {data.get('message')}"
                        result.success = False
                    
                    break
                else:
                    result.error = f"HTTP {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                result.error = f"Request timeout (attempt {attempt + 1}/{retry_times})"
                logger.warning(f"Shumei API timeout: {result.error}")
                
            except requests.exceptions.RequestException as e:
                result.error = f"Network error: {str(e)}"
                logger.error(f"Shumei API network error: {result.error}")
                
            except Exception as e:
                result.error = f"Unexpected error: {str(e)}"
                logger.error(f"Shumei API error: {result.error}")
            
            # Wait before retry
            if attempt < retry_times - 1:
                time.sleep(1)
        
        return result
    
    def _parse_response(self, data: Dict[str, Any], result: ModerationResult) -> None:
        """
        Parse Shumei API response and populate result.
        
        Args:
            data: Raw API response
            result: ModerationResult to populate
        """
        # Parse risk level
        risk_level_str = data.get("riskLevel", "PASS")
        try:
            result.risk_level = RiskLevel(risk_level_str)
        except ValueError:
            result.risk_level = RiskLevel.PASS
        
        # Parse risk labels
        if result.risk_level == RiskLevel.PASS:
            result.risk_label = "正常"
            result.risk_labels = []
        else:
            labels = self._extract_risk_labels(data)
            result.risk_labels = labels
            result.risk_label = labels[0] if labels else "未知风险"
        
        # Extract confidence score if available
        score = data.get("score", 0)
        if isinstance(score, (int, float)):
            result.confidence = score / 100.0 if score > 1 else score
    
    def _extract_risk_labels(self, data: Dict[str, Any]) -> List[str]:
        """
        Extract and normalize risk labels from API response.
        
        Args:
            data: Raw API response
            
        Returns:
            List of normalized risk labels
        """
        labels = []
        
        try:
            # Get primary risk label (riskLabel1)
            risk_label1 = data.get("riskLabel1", "")
            if risk_label1:
                normalized = RISK_LABEL_MAPPING.get(risk_label1.lower(), risk_label1)
                labels.append(normalized)
            
            # Get risk description (contains Chinese labels)
            risk_desc = data.get("riskDescription", "")
            if risk_desc:
                parts = risk_desc.split(":")
                if parts and parts[0]:
                    if parts[0] not in labels:
                        labels.append(parts[0])
            
            # Get all labels from allLabels array
            all_labels = data.get("allLabels", [])
            for label_info in all_labels:
                label1 = label_info.get("riskLabel1", "")
                if label1:
                    normalized = RISK_LABEL_MAPPING.get(label1.lower(), label1)
                    if normalized not in labels:
                        labels.append(normalized)
                        
        except Exception as e:
            logger.error(f"Error extracting risk labels: {e}")
        
        return labels if labels else ["未知风险"]
