"""
Metrics collection and calculation for benchmarks.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from collections import defaultdict


@dataclass
class BenchmarkMetrics:
    """
    Aggregated benchmark metrics for a single test run.
    
    Contains both performance metrics and accuracy metrics.
    """
    # Identification
    provider: str = ""
    content_type: str = ""
    
    # Count metrics
    total_requests: int = 0
    success_count: int = 0
    fail_count: int = 0
    timeout_count: int = 0
    
    # Performance metrics (in seconds)
    response_times: List[float] = field(default_factory=list)
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p50_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # Throughput
    total_duration: float = 0.0
    qps: float = 0.0  # Queries per second
    
    # Accuracy metrics
    true_positive: int = 0   # Correctly identified as risky
    true_negative: int = 0   # Correctly identified as safe
    false_positive: int = 0  # Incorrectly flagged as risky
    false_negative: int = 0  # Missed risky content
    
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    
    # Error tracking
    error_types: Dict[str, int] = field(default_factory=dict)
    
    # Per-category breakdown
    category_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "provider": self.provider,
            "content_type": self.content_type,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "timeout_count": self.timeout_count,
            "success_rate": self.success_rate,
            "avg_response_time_ms": self.avg_response_time * 1000,
            "min_response_time_ms": self.min_response_time * 1000,
            "max_response_time_ms": self.max_response_time * 1000,
            "p50_response_time_ms": self.p50_response_time * 1000,
            "p95_response_time_ms": self.p95_response_time * 1000,
            "p99_response_time_ms": self.p99_response_time * 1000,
            "total_duration_sec": self.total_duration,
            "qps": self.qps,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "error_types": self.error_types,
        }
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.success_count / self.total_requests) * 100
    
    @property
    def timeout_rate(self) -> float:
        """Calculate timeout rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.timeout_count / self.total_requests) * 100


class MetricsCollector:
    """
    Collects metrics during benchmark execution.
    
    Usage:
        collector = MetricsCollector("shumei", "text")
        
        for test_case in test_cases:
            result = provider.moderate(test_case.content)
            collector.record(result, test_case.expected_risk)
        
        metrics = collector.calculate()
    """
    
    def __init__(self, provider: str, content_type: str):
        """
        Initialize metrics collector.
        
        Args:
            provider: Provider name
            content_type: Content type being tested
        """
        self.provider = provider
        self.content_type = content_type
        
        # Raw data collection
        self.response_times: List[float] = []
        self.results: List[Dict[str, Any]] = []
        
        # Counters
        self.success_count = 0
        self.fail_count = 0
        self.timeout_count = 0
        
        # Confusion matrix
        self.true_positive = 0
        self.true_negative = 0
        self.false_positive = 0
        self.false_negative = 0
        
        # Error tracking
        self.error_types: Dict[str, int] = defaultdict(int)
        
        # Per-category tracking
        self.category_results: Dict[str, List[Dict]] = defaultdict(list)
        
        # Timing
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def start(self) -> None:
        """Mark the start of benchmark."""
        self.start_time = time.time()
    
    def stop(self) -> None:
        """Mark the end of benchmark."""
        self.end_time = time.time()
    
    def record(
        self, 
        result: Any,  # ModerationResult
        expected_risk: str,
        category: str = "",
    ) -> None:
        """
        Record a single moderation result.
        
        Args:
            result: ModerationResult from provider
            expected_risk: Expected risk label
            category: Test category (optional)
        """
        # Record basic result
        record = {
            "success": result.success,
            "response_time": result.response_time,
            "expected": expected_risk,
            "actual": result.risk_label,
            "risk_level": result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level),
            "error": result.error,
        }
        self.results.append(record)
        
        # Update counters
        if result.success:
            self.success_count += 1
            self.response_times.append(result.response_time)
        else:
            self.fail_count += 1
            if result.error and "timeout" in result.error.lower():
                self.timeout_count += 1
            
            # Track error types
            error_type = self._categorize_error(result.error)
            self.error_types[error_type] += 1
        
        # Update confusion matrix
        is_positive_expected = expected_risk != "正常"
        is_positive_actual = result.risk_label != "正常"
        
        if is_positive_expected and is_positive_actual:
            self.true_positive += 1
        elif not is_positive_expected and not is_positive_actual:
            self.true_negative += 1
        elif not is_positive_expected and is_positive_actual:
            self.false_positive += 1
        else:  # is_positive_expected and not is_positive_actual
            self.false_negative += 1
        
        # Track by category
        if category:
            self.category_results[category].append(record)
    
    def _categorize_error(self, error: Optional[str]) -> str:
        """Categorize error for aggregation."""
        if not error:
            return "Unknown"
        
        error_lower = error.lower()
        if "timeout" in error_lower:
            return "Timeout"
        elif "network" in error_lower or "connection" in error_lower:
            return "Network Error"
        elif "http" in error_lower:
            return "HTTP Error"
        elif "api" in error_lower:
            return "API Error"
        else:
            return "Other"
    
    def calculate(self) -> BenchmarkMetrics:
        """
        Calculate aggregated metrics.
        
        Returns:
            BenchmarkMetrics with all calculated values
        """
        metrics = BenchmarkMetrics(
            provider=self.provider,
            content_type=self.content_type,
            total_requests=len(self.results),
            success_count=self.success_count,
            fail_count=self.fail_count,
            timeout_count=self.timeout_count,
            true_positive=self.true_positive,
            true_negative=self.true_negative,
            false_positive=self.false_positive,
            false_negative=self.false_negative,
            error_types=dict(self.error_types),
        )
        
        # Calculate response time percentiles
        if self.response_times:
            sorted_times = sorted(self.response_times)
            n = len(sorted_times)
            
            metrics.response_times = sorted_times
            metrics.avg_response_time = sum(sorted_times) / n
            metrics.min_response_time = sorted_times[0]
            metrics.max_response_time = sorted_times[-1]
            metrics.p50_response_time = self._percentile(sorted_times, 50)
            metrics.p95_response_time = self._percentile(sorted_times, 95)
            metrics.p99_response_time = self._percentile(sorted_times, 99)
        
        # Calculate duration and QPS
        if self.start_time and self.end_time:
            metrics.total_duration = self.end_time - self.start_time
            if metrics.total_duration > 0:
                metrics.qps = metrics.success_count / metrics.total_duration
        
        # Calculate accuracy metrics
        total_predictions = (
            self.true_positive + self.true_negative + 
            self.false_positive + self.false_negative
        )
        
        if total_predictions > 0:
            metrics.accuracy = (
                (self.true_positive + self.true_negative) / total_predictions
            ) * 100
        
        # Precision: TP / (TP + FP)
        if self.true_positive + self.false_positive > 0:
            metrics.precision = (
                self.true_positive / (self.true_positive + self.false_positive)
            ) * 100
        
        # Recall: TP / (TP + FN)
        if self.true_positive + self.false_negative > 0:
            metrics.recall = (
                self.true_positive / (self.true_positive + self.false_negative)
            ) * 100
        
        # F1 Score
        if metrics.precision + metrics.recall > 0:
            metrics.f1_score = (
                2 * metrics.precision * metrics.recall / 
                (metrics.precision + metrics.recall)
            )
        
        # Calculate per-category metrics
        for category, results in self.category_results.items():
            category_success = sum(1 for r in results if r["success"])
            category_match = sum(
                1 for r in results 
                if r["success"] and self._is_match(r["expected"], r["actual"])
            )
            
            metrics.category_metrics[category] = {
                "total": len(results),
                "success": category_success,
                "match_count": category_match,
                "match_rate": (category_match / len(results) * 100) if results else 0,
            }
        
        return metrics
    
    def _percentile(self, sorted_data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not sorted_data:
            return 0.0
        
        n = len(sorted_data)
        index = int(n * percentile / 100)
        index = min(index, n - 1)
        
        return sorted_data[index]
    
    def _is_match(self, expected: str, actual: str) -> bool:
        """Check if expected and actual labels match."""
        # Exact match
        if expected == actual:
            return True
        
        # Both indicate "safe"
        if expected == "正常" and actual == "正常":
            return True
        
        # Both indicate "risky" (relaxed matching)
        if expected != "正常" and actual != "正常":
            # Check if actual contains expected or vice versa
            if expected in actual or actual in expected:
                return True
        
        return False
