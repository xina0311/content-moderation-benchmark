"""
Dataset configurations for different vendors.
Each vendor has different data formats and column names.
"""

import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from .loader import TestCase, ContentType

logger = logging.getLogger(__name__)


@dataclass
class DatasetConfig:
    """Configuration for a vendor's dataset."""
    name: str
    display_name: str
    text_files: List[Dict[str, Any]] = field(default_factory=list)
    image_files: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""


# 各供应商数据集配置
DATASET_CONFIGS = {
    "shumei": DatasetConfig(
        name="shumei",
        display_name="数美科技",
        description="数美测试数据集 - 文本18000条，图片2000张(URL)",
        text_files=[{
            "path": "data/01-数美/1127数美测试题.xlsx",
            "sheet": "文本测试题",
            "columns": {"content": "具体内容", "risk": "风险", "category": "类型", "id": "序号"},
        }],
        image_files=[{
            "path": "data/01-数美/1127数美测试题.xlsx",
            "sheet": "图片测试题",
            "columns": {"content": "具体内容", "risk": "风险", "category": "类型", "id": "序号"},
            "content_type": "url",
        }],
    ),
    "yidun": DatasetConfig(
        name="yidun",
        display_name="网易易盾",
        description="网易易盾测试数据集 - 文本20000条，图片2000张(URL)",
        text_files=[{
            "path": "data/02-网易云盾/文本20000.xlsx",
            "sheet": None,  # 只有一个sheet
            "columns": {"content": "内容", "risk": "分类", "id": "dataId"},
        }],
        image_files=[{
            "path": "data/02-网易云盾/图片2000张.xlsx",
            "sheet": None,
            "columns": {"content": "内容", "risk": "垃圾类别"},
            "content_type": "url",
        }],
    ),
    "juntong": DatasetConfig(
        name="juntong",
        display_name="君同未来",
        description="君同测试数据集 - 文本20000条，图片2000张(本地文件)",
        text_files=[
            {
                "path": "data/03-君同/文本样本/合规示例样本2000条.xlsx",
                "sheet": None,
                "columns": {"content": "text"},
                "default_risk": "正常",
                "default_category": "白样本",
            },
            {
                "path": "data/03-君同/文本样本/违规示例样本18000条.xlsx",
                "sheet": None,
                "columns": {"content": "text"},
                "default_risk": "违规",
                "default_category": "黑样本",
            },
        ],
        image_files=[{
            "path": "data/03-君同/图片负样本",
            "content_type": "local_dir",
            "default_risk": "违规",
            "default_category": "黑样本",
        }],
    ),
    "huoshan": DatasetConfig(
        name="huoshan",
        display_name="火山引擎",
        description="火山引擎测试数据集 - 文本1001条，图片500张(本地文件)",
        text_files=[{
            "path": "data/04-火山/文本测试用例.xlsx",
            "sheet": None,
            "columns": {"content": "用例", "risk": "类别", "category": "标签"},
        }],
        image_files=[
            {
                "path": "data/04-火山/黑样本图片400",
                "content_type": "local_dir",
                "default_risk": "违规",
                "default_category": "黑样本",
            },
            {
                "path": "data/04-火山/白样本图片100",
                "content_type": "local_dir",
                "default_risk": "正常",
                "default_category": "白样本",
            },
        ],
    ),
}


class VendorDataLoader:
    """
    Load test data for a specific vendor's dataset.
    Handles different data formats and column mappings.
    """
    
    def __init__(self, vendor: str, base_path: str = "."):
        """
        Initialize vendor data loader.
        
        Args:
            vendor: Vendor name (shumei, yidun, juntong, huoshan)
            base_path: Base path for data files
        """
        if vendor not in DATASET_CONFIGS:
            raise ValueError(f"Unknown vendor: {vendor}. Available: {list(DATASET_CONFIGS.keys())}")
        
        self.vendor = vendor
        self.config = DATASET_CONFIGS[vendor]
        self.base_path = Path(base_path)
        
        logger.info(f"VendorDataLoader initialized: {self.config.display_name}")
    
    def load_text_cases(self, limit: Optional[int] = None) -> List[TestCase]:
        """
        Load text test cases for this vendor.
        
        Args:
            limit: Maximum number of cases to load
            
        Returns:
            List of TestCase objects
        """
        cases = []
        
        for file_config in self.config.text_files:
            file_path = self.base_path / file_config["path"]
            
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
            
            file_cases = self._load_excel_cases(
                file_path=file_path,
                sheet_name=file_config.get("sheet"),
                columns=file_config.get("columns", {}),
                content_type=ContentType.TEXT,
                default_risk=file_config.get("default_risk", "正常"),
                default_category=file_config.get("default_category", ""),
                limit=limit - len(cases) if limit else None,
            )
            cases.extend(file_cases)
            
            if limit and len(cases) >= limit:
                break
        
        logger.info(f"Loaded {len(cases)} text cases for {self.vendor}")
        return cases[:limit] if limit else cases
    
    def load_image_cases(self, limit: Optional[int] = None) -> List[TestCase]:
        """
        Load image test cases for this vendor.
        
        Args:
            limit: Maximum number of cases to load
            
        Returns:
            List of TestCase objects
        """
        cases = []
        
        for file_config in self.config.image_files:
            content_type_str = file_config.get("content_type", "url")
            file_path = self.base_path / file_config["path"]
            
            if content_type_str == "local_dir":
                # Load images from directory
                file_cases = self._load_local_images(
                    dir_path=file_path,
                    default_risk=file_config.get("default_risk", "正常"),
                    default_category=file_config.get("default_category", ""),
                    limit=limit - len(cases) if limit else None,
                )
            else:
                # Load from Excel with URLs
                if not file_path.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue
                
                file_cases = self._load_excel_cases(
                    file_path=file_path,
                    sheet_name=file_config.get("sheet"),
                    columns=file_config.get("columns", {}),
                    content_type=ContentType.IMAGE,
                    default_risk=file_config.get("default_risk", "正常"),
                    default_category=file_config.get("default_category", ""),
                    limit=limit - len(cases) if limit else None,
                )
            
            cases.extend(file_cases)
            
            if limit and len(cases) >= limit:
                break
        
        logger.info(f"Loaded {len(cases)} image cases for {self.vendor}")
        return cases[:limit] if limit else cases
    
    def _load_excel_cases(
        self,
        file_path: Path,
        sheet_name: Optional[str],
        columns: Dict[str, str],
        content_type: ContentType,
        default_risk: str,
        default_category: str,
        limit: Optional[int],
    ) -> List[TestCase]:
        """Load cases from Excel file with column mapping."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required. Install with: pip install pandas openpyxl")
        
        cases = []
        
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
            
            content_col = columns.get("content", "内容")
            risk_col = columns.get("risk")
            category_col = columns.get("category")
            id_col = columns.get("id")
            
            for idx, row in df.iterrows():
                if limit and len(cases) >= limit:
                    break
                
                content = str(row.get(content_col, "")) if content_col in df.columns else ""
                
                if not content or content == "nan":
                    continue
                
                # Get risk label
                if risk_col and risk_col in df.columns:
                    risk = str(row.get(risk_col, default_risk))
                    if risk == "nan":
                        risk = default_risk
                else:
                    risk = default_risk
                
                # Get category
                if category_col and category_col in df.columns:
                    category = str(row.get(category_col, default_category))
                    if category == "nan":
                        category = default_category
                else:
                    category = default_category
                
                # Get ID
                if id_col and id_col in df.columns:
                    case_id = str(row.get(id_col, idx))
                else:
                    case_id = f"{content_type.value}_{idx}"
                
                case = TestCase(
                    id=case_id,
                    content=content,
                    content_type=content_type,
                    expected_risk=risk,
                    category=category,
                    metadata={"source_file": str(file_path), "row_index": idx},
                )
                cases.append(case)
            
            logger.info(f"Loaded {len(cases)} cases from {file_path.name}")
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
        
        return cases
    
    def _load_local_images(
        self,
        dir_path: Path,
        default_risk: str,
        default_category: str,
        limit: Optional[int],
    ) -> List[TestCase]:
        """Load images from local directory."""
        cases = []
        
        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            return cases
        
        # Supported image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        
        image_files = [
            f for f in dir_path.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]
        
        for idx, img_path in enumerate(sorted(image_files)):
            if limit and len(cases) >= limit:
                break
            
            case = TestCase(
                id=f"img_{img_path.stem}",
                content=str(img_path.absolute()),  # Store absolute path
                content_type=ContentType.IMAGE,
                expected_risk=default_risk,
                category=default_category,
                metadata={
                    "source_dir": str(dir_path),
                    "filename": img_path.name,
                    "is_local": True,
                },
            )
            cases.append(case)
        
        logger.info(f"Loaded {len(cases)} images from {dir_path.name}")
        return cases


def list_datasets() -> Dict[str, DatasetConfig]:
    """List all available datasets."""
    return DATASET_CONFIGS


def get_dataset_info(vendor: str) -> Optional[DatasetConfig]:
    """Get dataset info for a vendor."""
    return DATASET_CONFIGS.get(vendor)


def image_to_base64(image_path: str) -> Optional[str]:
    """
    Convert local image file to base64 string.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Base64 encoded string or None if failed
    """
    try:
        with open(image_path, 'rb') as img_file:
            img_data = img_file.read()
            return base64.b64encode(img_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to read image {image_path}: {e}")
        return None
