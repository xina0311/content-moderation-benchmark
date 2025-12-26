"""
Volcengine/Huoshan (火山引擎) LLM Shield content moderation provider implementation.
API Documentation: https://www.volcengine.com/docs/84990/1520618

Based on official test code provided by Volcengine.
"""

import time
import json
import base64
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
from ..benchmark.utils import is_base64_image

logger = logging.getLogger(__name__)

# Import volcenginesdkllmshield from project root
try:
    import sys
    import os
    # Add project root to path for volcenginesdkllmshield
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from volcenginesdkllmshield import ClientV2, ModerateV2Request, MessageV2, ContentTypeV2
    HAS_VOLCENGINE_SDK = True
except ImportError as e:
    HAS_VOLCENGINE_SDK = False
    logger.warning(f"volcenginesdkllmshield import failed: {e}")


# Label ID to name mapping (from common_tools.py)
LABEL_ID_MAP = {
    '10600000': '通用敏感话题',
    '10602001': '违规荐股',
    '10602002': '交易建议',
    '10602003': '预测行情与交易判断',
    '10602004': '承诺收益与模拟收益',
    '10602005': '适当性不匹配绕过',
    '10602006': '诱导性与规避合规',
    '10602007': '表达或转述不合规观点',
    '10602008': '代客理财',
    '10602009': '非公开信息泄漏或索取',
    '10602010': '越权调用或疑似假冒客户信息',
    '10602011': '非法金融活动',
    '10602012': '个人财务隐私',
    '10602013': '税务规避',
    '10602014': '保险欺诈',
    '10602015': '征信操作',
    '10602016': '外汇管制规避',
    '10602017': '竞品比较',
    '10310000': '电子邮箱',
    '10322000': '其他隐私数据',
    '10313000': '电话号码',
    '10304000': '身份证号',
    '10302000': '银行卡号',
    '10102000': '涉敏2',
    '10116000': '其他敏感内容',
    '10113002': '毒品',
    '10113003': '赌博',
    '10113004': '诈骗',
    '10112000': '歧视',
    '10109000': '商业违法',
    '10107000': '涉敏1',
    '10104000': '色情低俗',
    '10103005': '谩骂',
    '10701001': '高频相似样本',
    '10402003': '窃取提示词',
    '10401001': '角色扮演',
    '10401002': '权限提升',
    '10401003': '对抗前后缀',
    '10401004': '目标劫持',
    '10401005': '混淆和编码',
    '10401008': '少量示例攻击',
    '10400000': '提示词攻击默认标签'
}


def get_label_names(label_ids: List[str]) -> List[str]:
    """Convert label IDs to human-readable names."""
    return [LABEL_ID_MAP.get(label_id, label_id) for label_id in label_ids]


def parse_moderate_result(data: dict) -> dict:
    """
    Parse LLM Shield Moderate API response.
    
    Args:
        data: API response dict
        
    Returns:
        {
            "decision_type": int | None,  # 1=放行, 2=拦截
            "decision_type_str": str,  # "放行" or "拦截"
            "labels": list[str],  # Risk label names
            "words": list[str],  # Matched sensitive words
        }
    """
    result = {
        "decision_type": None,
        "decision_type_str": None,
        "labels": [],
        "words": []
    }
    
    if not isinstance(data, dict):
        return result
    
    # 1. DecisionType
    result["decision_type"] = (
        data.get("Result", {})
            .get("Decision", {})
            .get("DecisionType")
    )
    
    # Convert decision type to string
    if result["decision_type"] == 1:
        result["decision_type_str"] = "放行"
    elif result["decision_type"] == 2:
        result["decision_type_str"] = "拦截"
    
    # 2. Risks
    risks = (
        data.get("Result", {})
            .get("RiskInfo", {})
            .get("Risks", [])
    )
    
    label_ids = []
    for risk in risks:
        # Label
        label = risk.get("Label")
        if label is not None:
            label_ids.append(label)
        
        # Matches -> Word
        matches = risk.get("Matches", [])
        for match in matches:
            word = match.get("Word")
            if word is not None:
                result["words"].append(word)
    
    # Convert label IDs to names
    if label_ids:
        result["labels"] = get_label_names(label_ids)
    
    return result


class HuoshanProvider(BaseProvider):
    """
    Volcengine/Huoshan (火山引擎) LLM Shield content moderation provider.
    
    Uses the volcenginesdkllmshield SDK for API calls.
    Based on official test code provided by Volcengine.
    
    Supports:
        - Text moderation (LLM Shield API)
        - Image moderation (LLM Shield API with BASE64)
    
    Configuration (via environment variables):
        - HUOSHAN_ACCESS_KEY: Volcengine Access Key (AK)
        - HUOSHAN_SECRET_KEY: Volcengine Secret Key (SK)
        - HUOSHAN_APP_ID: LLM Shield AppID
        - HUOSHAN_REGION: Region (cn-beijing or cn-shanghai)
        - HUOSHAN_CUSTOM_URL: Custom API URL (optional)
    """
    
    name = "huoshan"
    display_name = "火山引擎"
    
    # Decision type mapping
    DECISION_MAPPING = {
        1: ("PASS", "放行"),
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
                "volcenginesdkllmshield SDK is not available. "
                "Please ensure the volcenginesdkllmshield directory exists in the project root."
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
    
    def _get_client(self) -> ClientV2:
        """Create and return LLM Shield client."""
        region = self.config.get("region", "cn-beijing")
        
        # Use custom URL if provided, otherwise construct from region
        custom_url = self.config.get("custom_url")
        if custom_url:
            url = custom_url
        else:
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
        
        Based on 文本校验测试.py from Volcengine test code.
        
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
                logger.debug(f">>> HUOSHAN TEXT API REQUEST")
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
                        content_type=ContentTypeV2.TEXT
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
                logger.debug(f"<<< HUOSHAN TEXT API RESPONSE")
                logger.debug(f"{'='*60}")
                logger.debug(f"Response Time: {result.response_time*1000:.0f}ms")
                logger.debug(f"Full Response:\n{json.dumps(raw_response, ensure_ascii=False, indent=2)}")
                
                # Parse result using common_tools logic
                parsed = parse_moderate_result(raw_response)
                decision_type = parsed["decision_type"]
                
                if decision_type == 1:  # 放行
                    result.risk_level = RiskLevel.PASS
                    result.risk_label = "正常"
                    result.risk_labels = []
                elif decision_type == 2:  # 拦截
                    result.risk_level = RiskLevel.REJECT
                    result.risk_labels = parsed["labels"]
                    result.risk_label = parsed["labels"][0] if parsed["labels"] else "拦截"
                else:
                    result.risk_level = RiskLevel.PASS
                    result.risk_label = "正常"
                    result.risk_labels = []
                
                result.confidence = 1.0 if decision_type == 2 else 0.0
                
                break
                
            except Exception as e:
                result.error = f"API error: {str(e)}"
                logger.error(f"Huoshan Text API error: {result.error}")
                
                if attempt < retry_times - 1:
                    time.sleep(1)
        
        return result
    
    def moderate_image(self, image_url: str, **kwargs) -> ModerationResult:
        """
        Moderate image content using Huoshan LLM Shield API.
        
        Based on 图片校验测试-黑样本.py from Volcengine test code.
        
        Image is sent as BASE64 encoded string.
        
        Args:
            image_url: URL of the image to moderate, or BASE64 encoded image data
            
        Returns:
            ModerationResult with risk assessment
        """
        result = ModerationResult(
            provider=self.name,
            content_type=ContentType.IMAGE,
        )
        
        role = kwargs.get("role", "user")
        retry_times = Config.RETRY_TIMES
        
        for attempt in range(retry_times):
            try:
                start_time = time.time()
                
                # Get image as BASE64
                if is_base64_image(image_url):
                    # Already BASE64
                    image_base64 = image_url
                elif image_url.startswith(('http://', 'https://')):
                    # Download and convert to BASE64
                    import requests
                    response = requests.get(image_url, timeout=30)
                    response.raise_for_status()
                    image_base64 = base64.b64encode(response.content).decode('utf-8')
                elif os.path.isfile(image_url):
                    # Local file - read and convert to BASE64
                    with open(image_url, 'rb') as f:
                        image_base64 = base64.b64encode(f.read()).decode('utf-8')
                else:
                    result.error = f"Invalid image source: {image_url[:50]}..."
                    result.success = False
                    return result
                
                # Log request
                logger.debug(f"\n{'='*60}")
                logger.debug(f">>> HUOSHAN IMAGE API REQUEST")
                logger.debug(f"{'='*60}")
                logger.debug(f"AppID: {self.config['app_id']}")
                logger.debug(f"Role: {role}")
                logger.debug(f"Image BASE64 length: {len(image_base64)}")
                
                # Create client and request
                client = self._get_client()
                request = ModerateV2Request(
                    scene=self.config["app_id"],
                    message=MessageV2(
                        role=role,
                        content=image_base64,
                        content_type=ContentTypeV2.IMAGE
                    )
                )
                
                # Make API call
                response = client.Moderate(request)
                
                result.response_time = time.time() - start_time
                result.success = True
                
                # Parse response
                raw_response = json.loads(response.model_dump_json(by_alias=True))
                result.raw_response = raw_response
                
                # Log response (hide base64 data)
                logger.debug(f"\n{'='*60}")
                logger.debug(f"<<< HUOSHAN IMAGE API RESPONSE")
                logger.debug(f"{'='*60}")
                logger.debug(f"Response Time: {result.response_time*1000:.0f}ms")
                logger.debug(f"Full Response:\n{json.dumps(raw_response, ensure_ascii=False, indent=2)}")
                
                # Parse result using common_tools logic
                parsed = parse_moderate_result(raw_response)
                decision_type = parsed["decision_type"]
                
                if decision_type == 1:  # 放行
                    result.risk_level = RiskLevel.PASS
                    result.risk_label = "正常"
                    result.risk_labels = []
                elif decision_type == 2:  # 拦截
                    result.risk_level = RiskLevel.REJECT
                    result.risk_labels = parsed["labels"]
                    result.risk_label = parsed["labels"][0] if parsed["labels"] else "拦截"
                else:
                    result.risk_level = RiskLevel.PASS
                    result.risk_label = "正常"
                    result.risk_labels = []
                
                result.confidence = 1.0 if decision_type == 2 else 0.0
                
                break
                
            except Exception as e:
                result.error = f"API error: {str(e)}"
                logger.error(f"Huoshan Image API error: {result.error}")
                
                if attempt < retry_times - 1:
                    time.sleep(1)
        
        return result
