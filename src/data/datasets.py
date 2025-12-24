"""
Dataset configurations for different vendors.
Each vendor has different data formats and column names.

Features:
- Proportional sampling from multiple files/directories
- Random shuffle for single-file datasets
- Consistent sampling strategy across all vendors
"""

import base64
import random
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
    
    Sampling Strategy:
    - Single file: Random shuffle before sampling
    - Multiple files: Proportional sampling from each file
    - Multiple directories: Proportional sampling from each directory
    """
    
    def __init__(self, vendor: str, base_path: str = ".", seed: int = 42):
        """
        Initialize vendor data loader.
        
        Args:
            vendor: Vendor name (shumei, yidun, juntong, huoshan)
            base_path: Base path for data files
            seed: Random seed for reproducible sampling
        """
        if vendor not in DATASET_CONFIGS:
            raise ValueError(f"Unknown vendor: {vendor}. Available: {list(DATASET_CONFIGS.keys())}")
        
        self.vendor = vendor
        self.config = DATASET_CONFIGS[vendor]
        self.base_path = Path(base_path)
        self.seed = seed
        
        # Set random seed for reproducibility
        random.seed(seed)
        
        logger.info(f"VendorDataLoader initialized: {self.config.display_name}")
    
    def load_text_cases(self, limit: Optional[int] = None, shuffle: bool = True) -> List[TestCase]:
        """
        Load text test cases for this vendor with proportional sampling.
        
        Args:
            limit: Maximum number of cases to load
            shuffle: Whether to shuffle data (default True)
            
        Returns:
            List of TestCase objects
        """
        file_configs = self.config.text_files
        
        if len(file_configs) == 1:
            # Single file: load all, shuffle, then limit
            cases = self._load_single_file_cases(
                file_configs[0],
                ContentType.TEXT,
                shuffle=shuffle,
            )
            if limit and len(cases) > limit:
                cases = cases[:limit]
        else:
            # Multiple files: proportional sampling
            cases = self._load_proportional_cases(
                file_configs,
                ContentType.TEXT,
                limit=limit,
                shuffle=shuffle,
            )
        
        logger.info(f"Loaded {len(cases)} text cases for {self.vendor}")
        return cases
    
    def load_image_cases(self, limit: Optional[int] = None, shuffle: bool = True) -> List[TestCase]:
        """
        Load image test cases for this vendor with proportional sampling.
        
        Args:
            limit: Maximum number of cases to load
            shuffle: Whether to shuffle data (default True)
            
        Returns:
            List of TestCase objects
        """
        file_configs = self.config.image_files
        
        # Separate Excel files and directories
        excel_configs = [c for c in file_configs if c.get("content_type") != "local_dir"]
        dir_configs = [c for c in file_configs if c.get("content_type") == "local_dir"]
        
        cases = []
        
        if excel_configs and not dir_configs:
            # Only Excel files
            if len(excel_configs) == 1:
                cases = self._load_single_file_cases(
                    excel_configs[0],
                    ContentType.IMAGE,
                    shuffle=shuffle,
                )
                if limit and len(cases) > limit:
                    cases = cases[:limit]
            else:
                cases = self._load_proportional_cases(
                    excel_configs,
                    ContentType.IMAGE,
                    limit=limit,
                    shuffle=shuffle,
                )
        elif dir_configs and not excel_configs:
            # Only directories
            if len(dir_configs) == 1:
                cases = self._load_single_dir_images(
                    dir_configs[0],
                    shuffle=shuffle,
                )
                if limit and len(cases) > limit:
                    cases = cases[:limit]
            else:
                cases = self._load_proportional_dir_images(
                    dir_configs,
                    limit=limit,
                    shuffle=shuffle,
                )
        else:
            # Mixed: load all and combine proportionally
            all_cases = []
            for config in file_configs:
                if config.get("content_type") == "local_dir":
                    file_cases = self._load_single_dir_images(config, shuffle=False)
                else:
                    file_cases = self._load_single_file_cases(config, ContentType.IMAGE, shuffle=False)
                all_cases.append((config, file_cases))
            
            if shuffle:
                cases = self._proportional_sample(all_cases, limit)
            else:
                for _, fc in all_cases:
                    cases.extend(fc)
                if limit:
                    cases = cases[:limit]
        
        logger.info(f"Loaded {len(cases)} image cases for {self.vendor}")
        return cases
    
    def _load_single_file_cases(
        self,
        file_config: Dict[str, Any],
        content_type: ContentType,
        shuffle: bool = True,
    ) -> List[TestCase]:
        """Load cases from a single Excel file with optional shuffle."""
        file_path = self.base_path / file_config["path"]
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return []
        
        cases = self._load_excel_cases(
            file_path=file_path,
            sheet_name=file_config.get("sheet"),
            columns=file_config.get("columns", {}),
            content_type=content_type,
            default_risk=file_config.get("default_risk", "正常"),
            default_category=file_config.get("default_category", ""),
            limit=None,  # Load all first
        )
        
        if shuffle and cases:
            random.shuffle(cases)
            logger.debug(f"Shuffled {len(cases)} cases from {file_path.name}")
        
        return cases
    
    def _load_proportional_cases(
        self,
        file_configs: List[Dict[str, Any]],
        content_type: ContentType,
        limit: Optional[int],
        shuffle: bool = True,
    ) -> List[TestCase]:
        """
        Load cases from multiple files with proportional sampling.
        
        Example: If file1 has 2000 rows and file2 has 18000 rows,
        and limit=200, then sample 20 from file1 and 180 from file2.
        """
        # First, count total rows in each file
        file_cases_list = []
        total_count = 0
        
        for file_config in file_configs:
            file_path = self.base_path / file_config["path"]
            
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
            
            cases = self._load_excel_cases(
                file_path=file_path,
                sheet_name=file_config.get("sheet"),
                columns=file_config.get("columns", {}),
                content_type=content_type,
                default_risk=file_config.get("default_risk", "正常"),
                default_category=file_config.get("default_category", ""),
                limit=None,  # Load all
            )
            
            if shuffle and cases:
                random.shuffle(cases)
            
            file_cases_list.append((file_config, cases))
            total_count += len(cases)
        
        if not file_cases_list:
            return []
        
        # Calculate proportional samples
        return self._proportional_sample(file_cases_list, limit)
    
    def _proportional_sample(
        self,
        file_cases_list: List[tuple],
        limit: Optional[int],
    ) -> List[TestCase]:
        """
        Proportionally sample from multiple case lists.
        
        Args:
            file_cases_list: List of (config, cases) tuples
            limit: Total number to sample
            
        Returns:
            Combined and shuffled list of cases
        """
        total_count = sum(len(cases) for _, cases in file_cases_list)
        
        if not limit or limit >= total_count:
            # No limit or limit exceeds total - return all
            all_cases = []
            for _, cases in file_cases_list:
                all_cases.extend(cases)
            random.shuffle(all_cases)
            return all_cases
        
        # Calculate proportional samples
        sampled_cases = []
        remaining_limit = limit
        
        for i, (config, cases) in enumerate(file_cases_list):
            if not cases:
                continue
            
            proportion = len(cases) / total_count
            sample_size = int(limit * proportion)
            
            # Ensure at least 1 sample if there are cases
            if sample_size == 0 and cases:
                sample_size = 1
            
            # For last file, use remaining limit to handle rounding
            if i == len(file_cases_list) - 1:
                sample_size = min(remaining_limit, len(cases))
            else:
                sample_size = min(sample_size, len(cases), remaining_limit)
            
            sampled = cases[:sample_size]
            sampled_cases.extend(sampled)
            remaining_limit -= len(sampled)
            
            source = config.get("path", config.get("default_risk", "unknown"))
            logger.info(f"Sampled {len(sampled)}/{len(cases)} ({len(sampled)/len(cases)*100:.1f}%) from {source}")
        
        # Final shuffle to mix samples from different sources
        random.shuffle(sampled_cases)
        
        return sampled_cases
    
    def _load_single_dir_images(
        self,
        config: Dict[str, Any],
        shuffle: bool = True,
    ) -> List[TestCase]:
        """Load images from a single directory."""
        dir_path = self.base_path / config["path"]
        
        cases = self._load_local_images(
            dir_path=dir_path,
            default_risk=config.get("default_risk", "正常"),
            default_category=config.get("default_category", ""),
            limit=None,
        )
        
        if shuffle and cases:
            random.shuffle(cases)
        
        return cases
    
    def _load_proportional_dir_images(
        self,
        dir_configs: List[Dict[str, Any]],
        limit: Optional[int],
        shuffle: bool = True,
    ) -> List[TestCase]:
        """Load images from multiple directories with proportional sampling."""
        dir_cases_list = []
        
        for config in dir_configs:
            dir_path = self.base_path / config["path"]
            
            cases = self._load_local_images(
                dir_path=dir_path,
                default_risk=config.get("default_risk", "正常"),
                default_category=config.get("default_category", ""),
                limit=None,
            )
            
            if shuffle and cases:
                random.shuffle(cases)
            
            dir_cases_list.append((config, cases))
        
        return self._proportional_sample(dir_cases_list, limit)
    
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
