"""
Configuration management for Content Moderation Benchmark.
Loads settings from environment variables and .env file.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """Central configuration management."""
    
    # ==========================================================================
    # Benchmark Settings
    # ==========================================================================
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "10"))
    REQUEST_INTERVAL: float = float(os.getenv("REQUEST_INTERVAL", "0.1"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    RETRY_TIMES: int = int(os.getenv("RETRY_TIMES", "3"))
    
    # Output directories
    OUTPUT_DIR: Path = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output")
    REPORT_DIR: Path = PROJECT_ROOT / os.getenv("REPORT_DIR", "reports")
    
    # ==========================================================================
    # Provider Configurations
    # ==========================================================================
    
    @classmethod
    def get_shumei_config(cls) -> Dict[str, Any]:
        """Get Shumei (数美) configuration."""
        return {
            "access_key": os.getenv("SHUMEI_ACCESS_KEY", ""),
            "app_id": os.getenv("SHUMEI_APP_ID", "default"),
            "text_url": os.getenv("SHUMEI_TEXT_URL", "https://api-text-bj.fengkongcloud.com/text/v4"),
            "image_url": os.getenv("SHUMEI_IMAGE_URL", "https://api-img-bj.fengkongcloud.com/image/v4"),
        }
    
    @classmethod
    def get_bytedance_config(cls) -> Dict[str, Any]:
        """Get Bytedance (字节跳动) configuration."""
        return {
            "access_key": os.getenv("BYTEDANCE_ACCESS_KEY", ""),
            "secret_key": os.getenv("BYTEDANCE_SECRET_KEY", ""),
            "text_url": os.getenv("BYTEDANCE_TEXT_URL", ""),
            "image_url": os.getenv("BYTEDANCE_IMAGE_URL", ""),
        }
    
    @classmethod
    def get_yidun_config(cls) -> Dict[str, Any]:
        """Get NetEase Yidun (网易易盾) configuration."""
        return {
            "secret_id": os.getenv("YIDUN_SECRET_ID", ""),
            "secret_key": os.getenv("YIDUN_SECRET_KEY", ""),
            "business_id": os.getenv("YIDUN_BUSINESS_ID", ""),
            "business_id_text": os.getenv("YIDUN_BUSINESS_ID_TEXT", os.getenv("YIDUN_BUSINESS_ID", "")),
            "business_id_image": os.getenv("YIDUN_BUSINESS_ID_IMAGE", os.getenv("YIDUN_BUSINESS_ID", "")),
        }
    
    @classmethod
    def get_juntong_config(cls) -> Dict[str, Any]:
        """Get JunTong (君同未来) configuration."""
        return {
            "text_api_key": os.getenv("JUNTONG_TEXT_API_KEY", ""),
            "image_api_key": os.getenv("JUNTONG_IMAGE_API_KEY", ""),
            "base_url": os.getenv("JUNTONG_BASE_URL", "http://121.40.172.175:8269"),
        }
    
    @classmethod
    def get_huoshan_config(cls) -> Dict[str, Any]:
        """Get Huoshan/Volcengine (火山引擎) LLM Shield configuration."""
        return {
            "access_key": os.getenv("HUOSHAN_ACCESS_KEY", ""),
            "secret_key": os.getenv("HUOSHAN_SECRET_KEY", ""),
            "app_id": os.getenv("HUOSHAN_APP_ID", ""),
            "region": os.getenv("HUOSHAN_REGION", "cn-beijing"),
            "custom_url": os.getenv("HUOSHAN_CUSTOM_URL", ""),
        }
    
    @classmethod
    def get_provider_config(cls, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific provider by name."""
        config_methods = {
            "shumei": cls.get_shumei_config,
            "bytedance": cls.get_bytedance_config,
            "yidun": cls.get_yidun_config,
            "juntong": cls.get_juntong_config,
            "huoshan": cls.get_huoshan_config,
        }
        
        method = config_methods.get(provider_name.lower())
        if method:
            return method()
        return None
    
    @classmethod
    def ensure_directories(cls):
        """Create output directories if they don't exist."""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORT_DIR.mkdir(parents=True, exist_ok=True)


# Risk label mappings (provider label -> standard label)
RISK_LABEL_MAPPING = {
    # Common labels
    "politics": "涉政",
    "porn": "色情",
    "sexy": "色情",
    "ad": "广告",
    "advert": "广告",
    "violence": "暴恐",
    "ban": "违禁",
    "abuse": "辱骂",
    "spam": "灌水",
    "flood": "灌水",
    "normal": "正常",
    "pass": "正常",
}


# Standard risk categories
RISK_CATEGORIES = [
    "正常",
    "涉政",
    "色情",
    "暴恐",
    "违禁",
    "辱骂",
    "广告",
    "灌水",
]
