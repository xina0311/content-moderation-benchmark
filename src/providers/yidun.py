"""
NetEase Yidun (网易易盾) content moderation provider implementation.
API Documentation: https://support.dun.163.com/documents/588434200783982592
"""

import time
import json
import hashlib
import logging
import requests
import uuid
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


class YidunProvider(BaseProvider):
    """
    NetEase Yidun (网易易盾) content moderation provider.
    
    Supports:
        - Text moderation (v5 sync API)
        - Image moderation (v5 sync API)
    
    Configuration (via environment variables):
        - YIDUN_SECRET_ID: Secret ID for authentication
        - YIDUN_SECRET_KEY: Secret Key for signature
        - YIDUN_BUSINESS_ID_TEXT: Business ID for text moderation
        - YIDUN_BUSINESS_ID_IMAGE: Business ID for image moderation
    """
    
    name = "yidun"
    display_name = "网易易盾"
    
    # API endpoints
    TEXT_URL = "http://as.dun.163.com/v5/text/check"
    IMAGE_URL = "http://as.dun.163.com/v5/image/check"
    
    # Label mapping (Yidun label -> Chinese label)
    LABEL_MAPPING = {
        0: "正常",
        100: "色情",
        200: "广告",
        260: "广告法",
        300: "暴恐",
        400: "违禁",
        500: "涉政",
        600: "谩骂",
        700: "灌水",
        900: "其他",
        1100: "涉价值观",
    }
    
    def _load_config(self) -> Dict[str, Any]:
        """Load Yidun configuration from environment."""
        return Config.get_yidun_config()
    
    def _validate_config(self) -> None:
        """Validate Yidun configuration."""
        if not self.config.get("secret_id") or not self.config.get("secret_key"):
            raise ConfigurationError(
                "YIDUN_SECRET_ID and YIDUN_SECRET_KEY are required. "
                "Please set them in your .env file."
            )
    
    def _gen_signature(self, params: Dict[str, str]) -> str:
        """
        Generate MD5 signature for Yidun API.
        
        Algorithm:
        1. Sort params by key (ASCII order)
        2. Concatenate key+value pairs
        3. Append secret_key
        4. MD5 hash
        """
        # Sort by key
        sorted_keys = sorted(params.keys())
        
        # Concatenate
        param_str = ""
        for key in sorted_keys:
            param_str += str(key) + str(params[key])
        
        # Append secret key
        param_str += self.config["secret_key"]
        
        # MD5 hash
        return hashlib.md5(param_str.encode("utf-8")).hexdigest()
    
    def moderate_text(self, text: str, **kwargs) -> ModerationResult:
        """
        Moderate text content using Yidun API.
        
        Args:
            text: Text content to moderate
            
        Returns:
            ModerationResult with risk assessment
        """
        params = {
            "secretId": self.config["secret_id"],
            "businessId": self.config.get("business_id_text", self.config.get("business_id", "")),
            "version": "v5.3",
            "timestamp": str(int(time.time() * 1000)),
            "nonce": str(uuid.uuid4().hex),
            "dataId": str(uuid.uuid4().hex[:16]),
            "content": text,
        }
        
        # Generate signature
        params["signature"] = self._gen_signature(params)
        
        return self._call_api(
            url=self.TEXT_URL,
            params=params,
            content_type=ContentType.TEXT,
        )
    
    def moderate_image(self, image_url: str, **kwargs) -> ModerationResult:
        """
        Moderate image content using Yidun API.
        
        Args:
            image_url: URL of the image to moderate
            
        Returns:
            ModerationResult with risk assessment
        """
        params = {
            "secretId": self.config["secret_id"],
            "businessId": self.config.get("business_id_image", self.config.get("business_id", "")),
            "version": "v5.3",
            "timestamp": str(int(time.time() * 1000)),
            "nonce": str(uuid.uuid4().hex),
            "dataId": str(uuid.uuid4().hex[:16]),
            "images": json.dumps([{"name": image_url, "type": 1, "data": image_url}]),
        }
        
        # Generate signature
        params["signature"] = self._gen_signature(params)
        
        return self._call_api(
            url=self.IMAGE_URL,
            params=params,
            content_type=ContentType.IMAGE,
        )
    
    def _call_api(
        self, 
        url: str, 
        params: Dict[str, Any],
        content_type: ContentType,
    ) -> ModerationResult:
        """
        Make API call to Yidun with retry logic.
        """
        result = ModerationResult(
            provider=self.name,
            content_type=content_type,
        )
        
        retry_times = Config.RETRY_TIMES
        timeout = Config.REQUEST_TIMEOUT
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        for attempt in range(retry_times):
            try:
                start_time = time.time()
                
                # Log request at DEBUG level
                logger.debug(f"\n{'='*60}")
                logger.debug(f">>> API REQUEST")
                logger.debug(f"{'='*60}")
                logger.debug(f"URL: {url}")
                logger.debug(f"Content Type: {content_type.value}")
                # Don't log full params to avoid exposing secrets
                logger.debug(f"DataId: {params.get('dataId')}")
                
                response = requests.post(
                    url,
                    data=params,
                    headers=headers,
                    timeout=timeout,
                )
                
                result.response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    result.raw_response = data
                    
                    # Log response at DEBUG level
                    logger.debug(f"\n{'='*60}")
                    logger.debug(f"<<< API RESPONSE")
                    logger.debug(f"{'='*60}")
                    logger.debug(f"Response Time: {result.response_time*1000:.0f}ms")
                    logger.debug(f"Full Response:\n{json.dumps(data, ensure_ascii=False, indent=2)}")
                    
                    if data.get("code") == 200:
                        result.success = True
                        if content_type == ContentType.TEXT:
                            self._parse_text_response(data, result)
                        else:
                            self._parse_image_response(data, result)
                    else:
                        result.error = f"API error: {data.get('code')} - {data.get('msg')}"
                        result.success = False
                    
                    break
                else:
                    result.error = f"HTTP {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                result.error = f"Request timeout (attempt {attempt + 1}/{retry_times})"
                logger.warning(f"Yidun API timeout: {result.error}")
                
            except requests.exceptions.RequestException as e:
                result.error = f"Network error: {str(e)}"
                logger.error(f"Yidun API network error: {result.error}")
                
            except Exception as e:
                result.error = f"Unexpected error: {str(e)}"
                logger.error(f"Yidun API error: {result.error}")
            
            if attempt < retry_times - 1:
                time.sleep(1)
        
        return result
    
    def _parse_text_response(self, data: Dict[str, Any], result: ModerationResult) -> None:
        """
        Parse Yidun text API response.
        
        Response structure:
        {
            "code": 200,
            "result": {
                "antispam": {
                    "suggestion": 0/1/2,  // 0通过, 1嫌疑, 2不通过
                    "label": 100/200/500/...,
                    "labels": [...]
                }
            }
        }
        """
        antispam = data.get("result", {}).get("antispam", {})
        
        suggestion = antispam.get("suggestion", 0)
        label = antispam.get("label", 0)
        labels = antispam.get("labels", [])
        
        # Map suggestion to RiskLevel
        if suggestion == 0:
            result.risk_level = RiskLevel.PASS
            result.risk_label = "正常"
            result.risk_labels = []
        elif suggestion == 1:
            result.risk_level = RiskLevel.REVIEW
            result.risk_label = self.LABEL_MAPPING.get(label, "嫌疑")
            result.risk_labels = [self.LABEL_MAPPING.get(l.get("label", 0), "嫌疑") for l in labels]
        else:  # suggestion == 2
            result.risk_level = RiskLevel.REJECT
            result.risk_label = self.LABEL_MAPPING.get(label, "违规")
            result.risk_labels = [self.LABEL_MAPPING.get(l.get("label", 0), "违规") for l in labels]
        
        # Get confidence from first label if available
        if labels:
            result.confidence = labels[0].get("rate", 0.0)
    
    def _parse_image_response(self, data: Dict[str, Any], result: ModerationResult) -> None:
        """
        Parse Yidun image API response.
        """
        antispam = data.get("result", {}).get("antispam", {})
        
        # Image API returns results in 'images' array
        images = antispam.get("images", [])
        if images:
            img_result = images[0]
            suggestion = img_result.get("suggestion", 0)
            label = img_result.get("label", 0)
            labels = img_result.get("labels", [])
            
            if suggestion == 0:
                result.risk_level = RiskLevel.PASS
                result.risk_label = "正常"
                result.risk_labels = []
            elif suggestion == 1:
                result.risk_level = RiskLevel.REVIEW
                result.risk_label = self.LABEL_MAPPING.get(label, "嫌疑")
                result.risk_labels = [self.LABEL_MAPPING.get(l.get("label", 0), "嫌疑") for l in labels]
            else:
                result.risk_level = RiskLevel.REJECT
                result.risk_label = self.LABEL_MAPPING.get(label, "违规")
                result.risk_labels = [self.LABEL_MAPPING.get(l.get("label", 0), "违规") for l in labels]
            
            if labels:
                result.confidence = labels[0].get("rate", 0.0)
        else:
            result.risk_level = RiskLevel.PASS
            result.risk_label = "正常"
