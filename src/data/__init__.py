"""
Data loading and management package.
Supports multiple data formats: Excel, JSON, CSV.
"""

from .loader import DataLoader, TestCase

__all__ = ["DataLoader", "TestCase"]
