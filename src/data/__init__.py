"""
Data loading and management package.
Supports multiple data formats: Excel, JSON, CSV.
"""

from .loader import DataLoader, TestCase, ContentType, create_sample_data
from .datasets import (
    VendorDataLoader,
    DatasetConfig,
    DATASET_CONFIGS,
    list_datasets,
    get_dataset_info,
    image_to_base64,
)

__all__ = [
    "DataLoader",
    "TestCase",
    "ContentType",
    "create_sample_data",
    "VendorDataLoader",
    "DatasetConfig",
    "DATASET_CONFIGS",
    "list_datasets",
    "get_dataset_info",
    "image_to_base64",
]
