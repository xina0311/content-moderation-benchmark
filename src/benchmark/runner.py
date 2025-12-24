"""
Benchmark runner for executing performance tests.
"""

import csv
import time
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from ..providers.base import BaseProvider, ContentType, ModerationResult, RiskLevel
from ..data.loader import TestCase, DataLoader
from ..config import Config
from .metrics import MetricsCollector, BenchmarkMetrics
from .utils import get_report_subdir_name

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""
    max_workers: int = 10
    request_interval: float = 0.1
    limit: Optional[int] = None
    test_text: bool = True
    test_image: bool = True
    
    # Data source
    data_file: Optional[str] = None
    text_sheet: str = "文本测试题"
    image_sheet: str = "图片测试题"


@dataclass
class MismatchRecord:
    """Record of a mismatch between API result and ground truth."""
    case_id: str
    content: str
    content_type: str
    expected_risk: str
    actual_risk_level: str
    actual_risk_label: str
    risk_description: str
    response_time_ms: float
    raw_response: str


@dataclass
class BenchmarkResult:
    """Result of a complete benchmark run."""
    provider: str
    text_metrics: Optional[BenchmarkMetrics] = None
    image_metrics: Optional[BenchmarkMetrics] = None
    detailed_results: List[Dict[str, Any]] = field(default_factory=list)
    text_mismatches: List[MismatchRecord] = field(default_factory=list)
    image_mismatches: List[MismatchRecord] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "text_metrics": self.text_metrics.to_dict() if self.text_metrics else None,
            "image_metrics": self.image_metrics.to_dict() if self.image_metrics else None,
        }


class BenchmarkRunner:
    """
    Executes benchmarks against content moderation providers.
    
    Features:
        - Concurrent request execution
        - Configurable rate limiting
        - Progress callbacks
        - Comprehensive metrics collection
    
    Example:
        runner = BenchmarkRunner(provider)
        result = runner.run(
            data_file="test_data.xlsx",
            limit=100,
            test_text=True,
            test_image=True,
        )
    """
    
    def __init__(
        self, 
        provider: BaseProvider,
        config: Optional[BenchmarkConfig] = None,
    ):
        """
        Initialize benchmark runner.
        
        Args:
            provider: Content moderation provider to test
            config: Benchmark configuration
        """
        self.provider = provider
        self.config = config or BenchmarkConfig(
            max_workers=Config.MAX_WORKERS,
            request_interval=Config.REQUEST_INTERVAL,
        )
        
        # Callbacks
        self._on_progress: Optional[Callable[[int, int], None]] = None
        self._on_result: Optional[Callable[[TestCase, ModerationResult], None]] = None
    
    def on_progress(self, callback: Callable[[int, int], None]) -> "BenchmarkRunner":
        """
        Set progress callback.
        
        Args:
            callback: Function(completed, total) called on progress
        """
        self._on_progress = callback
        return self
    
    def on_result(self, callback: Callable[[TestCase, ModerationResult], None]) -> "BenchmarkRunner":
        """
        Set result callback.
        
        Args:
            callback: Function(test_case, result) called on each result
        """
        self._on_result = callback
        return self
    
    def run(
        self,
        data_file: Optional[str] = None,
        text_cases: Optional[List[TestCase]] = None,
        image_cases: Optional[List[TestCase]] = None,
        limit: Optional[int] = None,
        test_text: bool = True,
        test_image: bool = True,
    ) -> BenchmarkResult:
        """
        Run benchmark tests.
        
        Args:
            data_file: Path to test data file (Excel/JSON/CSV)
            text_cases: Pre-loaded text test cases
            image_cases: Pre-loaded image test cases
            limit: Maximum number of test cases per type
            test_text: Whether to run text tests
            test_image: Whether to run image tests
            
        Returns:
            BenchmarkResult with metrics and detailed results
        """
        result = BenchmarkResult(provider=self.provider.name)
        
        # Load test data if file provided
        if data_file:
            loader = DataLoader(data_file)
            if test_text and not text_cases:
                text_cases = loader.load_text_cases(
                    sheet_name=self.config.text_sheet,
                    limit=limit,
                )
            if test_image and not image_cases:
                image_cases = loader.load_image_cases(
                    sheet_name=self.config.image_sheet,
                    limit=limit,
                )
        
        # Apply limit
        if limit:
            if text_cases:
                text_cases = text_cases[:limit]
            if image_cases:
                image_cases = image_cases[:limit]
        
        # Run text benchmark
        if test_text and text_cases:
            logger.info(f"Starting text benchmark: {len(text_cases)} cases")
            result.text_metrics, result.text_mismatches = self._run_benchmark(
                text_cases, 
                ContentType.TEXT,
            )
            logger.info(f"Text benchmark complete: {result.text_metrics.success_rate:.1f}% success")
            if result.text_mismatches:
                logger.info(f"Text mismatches: {len(result.text_mismatches)} cases")
        
        # Run image benchmark
        if test_image and image_cases:
            logger.info(f"Starting image benchmark: {len(image_cases)} cases")
            result.image_metrics, result.image_mismatches = self._run_benchmark(
                image_cases,
                ContentType.IMAGE,
            )
            logger.info(f"Image benchmark complete: {result.image_metrics.success_rate:.1f}% success")
            if result.image_mismatches:
                logger.info(f"Image mismatches: {len(result.image_mismatches)} cases")
        
        # Export mismatches to CSV
        self._export_mismatches(result)
        
        return result
    
    def _run_benchmark(
        self,
        test_cases: List[TestCase],
        content_type: ContentType,
    ) -> tuple:
        """
        Run benchmark for a specific content type.
        
        Args:
            test_cases: List of test cases
            content_type: Type of content being tested
            
        Returns:
            Tuple of (BenchmarkMetrics, List[MismatchRecord])
        """
        collector = MetricsCollector(
            provider=self.provider.name,
            content_type=content_type.value,
        )
        
        mismatches: List[MismatchRecord] = []
        
        collector.start()
        
        # Use thread pool for concurrent execution
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all tasks
            futures = {}
            for test_case in test_cases:
                future = executor.submit(
                    self._moderate_single,
                    test_case,
                    content_type,
                )
                futures[future] = test_case
                
                # Rate limiting
                time.sleep(self.config.request_interval)
            
            # Collect results
            completed = 0
            total = len(test_cases)
            
            for future in as_completed(futures):
                test_case = futures[future]
                
                try:
                    mod_result = future.result()
                    
                    # Record metrics
                    collector.record(
                        mod_result,
                        test_case.expected_risk,
                        test_case.category,
                    )
                    
                    # Check for mismatch
                    mismatch = self._check_mismatch(test_case, mod_result, content_type)
                    if mismatch:
                        mismatches.append(mismatch)
                    
                    # Callback
                    if self._on_result:
                        self._on_result(test_case, mod_result)
                    
                except Exception as e:
                    logger.error(f"Error processing {test_case.id}: {e}")
                    # Record as failed
                    error_result = ModerationResult(
                        success=False,
                        error=str(e),
                        provider=self.provider.name,
                        content_type=content_type,
                    )
                    collector.record(
                        error_result,
                        test_case.expected_risk,
                        test_case.category,
                    )
                
                completed += 1
                
                # Progress callback
                if self._on_progress:
                    self._on_progress(completed, total)
                
                # Log progress
                if completed % 100 == 0 or completed == total:
                    logger.info(f"Progress: {completed}/{total}")
        
        collector.stop()
        return collector.calculate(), mismatches
    
    def _check_mismatch(
        self,
        test_case: TestCase,
        mod_result: ModerationResult,
        content_type: ContentType,
    ) -> Optional[MismatchRecord]:
        """
        Check if the moderation result matches the expected ground truth.
        
        Args:
            test_case: Test case with expected result
            mod_result: Actual moderation result
            content_type: Content type
            
        Returns:
            MismatchRecord if mismatch, None otherwise
        """
        if not mod_result.success:
            return None
        
        # Determine if results match
        expected_is_risk = test_case.expected_risk != "正常"
        actual_is_risk = mod_result.risk_level != RiskLevel.PASS
        
        # If both agree on risk/no-risk, no mismatch
        if expected_is_risk == actual_is_risk:
            return None
        
        # Create mismatch record
        import json
        raw_response_str = ""
        if mod_result.raw_response:
            try:
                raw_response_str = json.dumps(mod_result.raw_response, ensure_ascii=False)
            except:
                raw_response_str = str(mod_result.raw_response)
        
        return MismatchRecord(
            case_id=test_case.id,
            content=test_case.content[:500] if len(test_case.content) > 500 else test_case.content,
            content_type=content_type.value,
            expected_risk=test_case.expected_risk,
            actual_risk_level=mod_result.risk_level.value if mod_result.risk_level else "N/A",
            actual_risk_label=mod_result.risk_label or "N/A",
            risk_description=mod_result.raw_response.get("riskDescription", "") if mod_result.raw_response else "",
            response_time_ms=mod_result.response_time * 1000 if mod_result.response_time else 0,
            raw_response=raw_response_str,
        )
    
    def _export_mismatches(self, result: BenchmarkResult) -> None:
        """
        Export mismatch records to CSV files.
        
        Args:
            result: Benchmark result containing mismatches
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Use same subdirectory structure as Reporter (YYYYMMDD_region_ip)
        subdir_name = get_report_subdir_name()
        output_dir = Config.REPORT_DIR / subdir_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export text mismatches
        if result.text_mismatches:
            text_csv_path = output_dir / f"text_mismatches_{result.provider}_{timestamp}.csv"
            self._write_mismatch_csv(text_csv_path, result.text_mismatches)
            logger.info(f"Text mismatches exported to: {text_csv_path}")
        
        # Export image mismatches
        if result.image_mismatches:
            image_csv_path = output_dir / f"image_mismatches_{result.provider}_{timestamp}.csv"
            self._write_mismatch_csv(image_csv_path, result.image_mismatches)
            logger.info(f"Image mismatches exported to: {image_csv_path}")
    
    def _write_mismatch_csv(self, filepath: Path, mismatches: List[MismatchRecord]) -> None:
        """
        Write mismatch records to CSV file.
        
        Args:
            filepath: Output CSV file path
            mismatches: List of mismatch records
        """
        headers = [
            "case_id",
            "content",
            "content_type",
            "expected_risk",
            "actual_risk_level",
            "actual_risk_label",
            "risk_description",
            "response_time_ms",
            "raw_response",
        ]
        
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for m in mismatches:
                writer.writerow([
                    m.case_id,
                    m.content,
                    m.content_type,
                    m.expected_risk,
                    m.actual_risk_level,
                    m.actual_risk_label,
                    m.risk_description,
                    f"{m.response_time_ms:.0f}",
                    m.raw_response,
                ])
    
    def _moderate_single(
        self,
        test_case: TestCase,
        content_type: ContentType,
    ) -> ModerationResult:
        """
        Moderate a single test case.
        
        Args:
            test_case: Test case to moderate
            content_type: Content type
            
        Returns:
            ModerationResult
        """
        if content_type == ContentType.TEXT:
            return self.provider.moderate_text(
                test_case.content,
                token_id=f"benchmark_{test_case.id}",
            )
        else:
            return self.provider.moderate_image(
                test_case.content,
                token_id=f"benchmark_{test_case.id}",
            )
    
    def run_quick_test(self, num_samples: int = 10) -> BenchmarkResult:
        """
        Run a quick connectivity test with minimal samples.
        
        Args:
            num_samples: Number of test samples
            
        Returns:
            BenchmarkResult
        """
        # Generate simple test data
        text_cases = [
            TestCase(
                id=f"quick_text_{i}",
                content=f"This is test message {i}",
                content_type=ContentType.TEXT,
                expected_risk="正常",
            )
            for i in range(num_samples)
        ]
        
        return self.run(
            text_cases=text_cases,
            test_text=True,
            test_image=False,
        )


class MultiProviderRunner:
    """
    Run benchmarks across multiple providers for comparison.
    
    Example:
        runner = MultiProviderRunner()
        runner.add_provider(ShumeiProvider())
        runner.add_provider(YidunProvider())
        
        results = runner.run_comparison(
            data_file="test_data.xlsx",
            limit=1000,
        )
    """
    
    def __init__(self):
        """Initialize multi-provider runner."""
        self.providers: List[BaseProvider] = []
        self.results: Dict[str, BenchmarkResult] = {}
    
    def add_provider(self, provider: BaseProvider) -> "MultiProviderRunner":
        """Add a provider to test."""
        self.providers.append(provider)
        return self
    
    def run_comparison(
        self,
        data_file: str,
        limit: Optional[int] = None,
        test_text: bool = True,
        test_image: bool = True,
    ) -> Dict[str, BenchmarkResult]:
        """
        Run benchmark comparison across all providers.
        
        Args:
            data_file: Path to test data file
            limit: Maximum test cases per type
            test_text: Test text moderation
            test_image: Test image moderation
            
        Returns:
            Dictionary mapping provider name to results
        """
        # Load data once
        loader = DataLoader(data_file)
        text_cases = loader.load_text_cases(limit=limit) if test_text else None
        image_cases = loader.load_image_cases(limit=limit) if test_image else None
        
        logger.info(f"Running comparison across {len(self.providers)} providers")
        
        for provider in self.providers:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing provider: {provider.display_name}")
            logger.info(f"{'='*60}")
            
            runner = BenchmarkRunner(provider)
            result = runner.run(
                text_cases=text_cases,
                image_cases=image_cases,
                test_text=test_text,
                test_image=test_image,
            )
            
            self.results[provider.name] = result
        
        return self.results
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """
        Get a summary comparison of all providers.
        
        Returns:
            Summary dictionary with provider comparisons
        """
        summary = {
            "providers": [],
            "text_comparison": [],
            "image_comparison": [],
        }
        
        for name, result in self.results.items():
            provider_summary = {"name": name}
            
            if result.text_metrics:
                provider_summary["text"] = {
                    "avg_response_ms": result.text_metrics.avg_response_time * 1000,
                    "p99_response_ms": result.text_metrics.p99_response_time * 1000,
                    "success_rate": result.text_metrics.success_rate,
                    "accuracy": result.text_metrics.accuracy,
                    "recall": result.text_metrics.recall,
                    "f1_score": result.text_metrics.f1_score,
                }
                summary["text_comparison"].append({
                    "provider": name,
                    **provider_summary["text"],
                })
            
            if result.image_metrics:
                provider_summary["image"] = {
                    "avg_response_ms": result.image_metrics.avg_response_time * 1000,
                    "p99_response_ms": result.image_metrics.p99_response_time * 1000,
                    "success_rate": result.image_metrics.success_rate,
                    "accuracy": result.image_metrics.accuracy,
                    "recall": result.image_metrics.recall,
                    "f1_score": result.image_metrics.f1_score,
                }
                summary["image_comparison"].append({
                    "provider": name,
                    **provider_summary["image"],
                })
            
            summary["providers"].append(provider_summary)
        
        return summary
