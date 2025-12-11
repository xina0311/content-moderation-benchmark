"""
Report generation for benchmark results.
Supports Markdown and JSON output formats.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .metrics import BenchmarkMetrics
from .runner import BenchmarkResult
from ..config import Config


class Reporter:
    """
    Generate benchmark reports in various formats.
    
    Supports:
        - Markdown reports
        - JSON data export
        - Console output
        - Multi-provider comparison reports
    
    Example:
        reporter = Reporter()
        reporter.generate_markdown(result, "report.md")
        reporter.generate_json(result, "results.json")
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize reporter.
        
        Args:
            output_dir: Directory for output files
        """
        self.output_dir = output_dir or Config.REPORT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_markdown(
        self,
        result: BenchmarkResult,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a Markdown benchmark report.
        
        Args:
            result: Benchmark result to report
            filename: Output filename (optional)
            
        Returns:
            Path to generated file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not filename:
            filename = f"benchmark_report_{result.provider}_{file_timestamp}.md"
        
        output_path = self.output_dir / filename
        
        lines = []
        lines.append(f"# Content Moderation Benchmark Report")
        lines.append(f"\n**Provider:** {result.provider}")
        lines.append(f"**Generated:** {timestamp}")
        lines.append(f"\n---\n")
        
        # Text metrics
        if result.text_metrics:
            lines.append(self._format_metrics_section(
                "Text Moderation", 
                result.text_metrics,
            ))
        
        # Image metrics
        if result.image_metrics:
            lines.append(self._format_metrics_section(
                "Image Moderation",
                result.image_metrics,
            ))
        
        # Summary
        lines.append("\n## Summary\n")
        lines.append(self._generate_summary(result))
        
        content = "\n".join(lines)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return str(output_path)
    
    def _format_metrics_section(
        self, 
        title: str, 
        metrics: BenchmarkMetrics,
    ) -> str:
        """Format a metrics section for Markdown."""
        lines = []
        lines.append(f"\n## {title}\n")
        
        # Overview table
        lines.append("### Overview\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Requests | {metrics.total_requests} |")
        lines.append(f"| Success Count | {metrics.success_count} |")
        lines.append(f"| Failed Count | {metrics.fail_count} |")
        lines.append(f"| Success Rate | {metrics.success_rate:.2f}% |")
        
        # Performance table
        lines.append("\n### Performance\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Average Response Time | {metrics.avg_response_time*1000:.0f}ms |")
        lines.append(f"| P50 Response Time | {metrics.p50_response_time*1000:.0f}ms |")
        lines.append(f"| P95 Response Time | {metrics.p95_response_time*1000:.0f}ms |")
        lines.append(f"| P99 Response Time | {metrics.p99_response_time*1000:.0f}ms |")
        lines.append(f"| Min Response Time | {metrics.min_response_time*1000:.0f}ms |")
        lines.append(f"| Max Response Time | {metrics.max_response_time*1000:.0f}ms |")
        lines.append(f"| QPS | {metrics.qps:.2f} |")
        lines.append(f"| Total Duration | {metrics.total_duration:.1f}s |")
        
        # Accuracy table
        lines.append("\n### Accuracy\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Accuracy | {metrics.accuracy:.2f}% |")
        lines.append(f"| Precision | {metrics.precision:.2f}% |")
        lines.append(f"| Recall | {metrics.recall:.2f}% |")
        lines.append(f"| F1 Score | {metrics.f1_score:.2f} |")
        
        # Confusion matrix
        lines.append("\n### Confusion Matrix\n")
        lines.append("| | Predicted Positive | Predicted Negative |")
        lines.append("|---|---|---|")
        lines.append(f"| **Actual Positive** | TP: {metrics.true_positive} | FN: {metrics.false_negative} |")
        lines.append(f"| **Actual Negative** | FP: {metrics.false_positive} | TN: {metrics.true_negative} |")
        
        # Errors
        if metrics.error_types:
            lines.append("\n### Errors\n")
            lines.append("| Error Type | Count |")
            lines.append("|------------|-------|")
            for error_type, count in metrics.error_types.items():
                lines.append(f"| {error_type} | {count} |")
        
        return "\n".join(lines)
    
    def _generate_summary(self, result: BenchmarkResult) -> str:
        """Generate summary section."""
        lines = []
        
        if result.text_metrics:
            tm = result.text_metrics
            lines.append(f"**Text Moderation:**")
            lines.append(f"- Processed {tm.total_requests} requests with {tm.success_rate:.1f}% success rate")
            lines.append(f"- Average response: {tm.avg_response_time*1000:.0f}ms, P99: {tm.p99_response_time*1000:.0f}ms")
            lines.append(f"- Accuracy: {tm.accuracy:.1f}%, Recall: {tm.recall:.1f}%, F1: {tm.f1_score:.1f}")
            lines.append("")
        
        if result.image_metrics:
            im = result.image_metrics
            lines.append(f"**Image Moderation:**")
            lines.append(f"- Processed {im.total_requests} requests with {im.success_rate:.1f}% success rate")
            lines.append(f"- Average response: {im.avg_response_time*1000:.0f}ms, P99: {im.p99_response_time*1000:.0f}ms")
            lines.append(f"- Accuracy: {im.accuracy:.1f}%, Recall: {im.recall:.1f}%, F1: {im.f1_score:.1f}")
        
        return "\n".join(lines)
    
    def generate_json(
        self,
        result: BenchmarkResult,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate JSON benchmark results.
        
        Args:
            result: Benchmark result to export
            filename: Output filename (optional)
            
        Returns:
            Path to generated file
        """
        file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not filename:
            filename = f"benchmark_results_{result.provider}_{file_timestamp}.json"
        
        output_path = self.output_dir / filename
        
        data = {
            "provider": result.provider,
            "generated_at": datetime.now().isoformat(),
            "text_metrics": result.text_metrics.to_dict() if result.text_metrics else None,
            "image_metrics": result.image_metrics.to_dict() if result.image_metrics else None,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(output_path)
    
    def generate_comparison_report(
        self,
        results: Dict[str, BenchmarkResult],
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a comparison report for multiple providers.
        
        Args:
            results: Dictionary mapping provider name to results
            filename: Output filename (optional)
            
        Returns:
            Path to generated file
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not filename:
            filename = f"benchmark_comparison_{file_timestamp}.md"
        
        output_path = self.output_dir / filename
        
        lines = []
        lines.append("# Content Moderation Provider Comparison")
        lines.append(f"\n**Generated:** {timestamp}")
        lines.append(f"**Providers:** {', '.join(results.keys())}")
        lines.append("\n---\n")
        
        # Text comparison
        text_results = {
            k: v.text_metrics for k, v in results.items() 
            if v.text_metrics
        }
        if text_results:
            lines.append(self._format_comparison_table(
                "Text Moderation Comparison",
                text_results,
            ))
        
        # Image comparison
        image_results = {
            k: v.image_metrics for k, v in results.items()
            if v.image_metrics
        }
        if image_results:
            lines.append(self._format_comparison_table(
                "Image Moderation Comparison",
                image_results,
            ))
        
        # Recommendations
        lines.append("\n## Recommendations\n")
        lines.append(self._generate_recommendations(results))
        
        content = "\n".join(lines)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return str(output_path)
    
    def _format_comparison_table(
        self,
        title: str,
        metrics_dict: Dict[str, BenchmarkMetrics],
    ) -> str:
        """Format a comparison table for multiple providers."""
        lines = []
        lines.append(f"\n## {title}\n")
        
        providers = list(metrics_dict.keys())
        
        # Performance comparison
        lines.append("### Performance\n")
        header = "| Metric |" + "|".join(f" {p} " for p in providers) + "|"
        separator = "|--------|" + "|".join("-------" for _ in providers) + "|"
        lines.append(header)
        lines.append(separator)
        
        rows = [
            ("Avg Response (ms)", lambda m: f"{m.avg_response_time*1000:.0f}"),
            ("P99 Response (ms)", lambda m: f"{m.p99_response_time*1000:.0f}"),
            ("Success Rate (%)", lambda m: f"{m.success_rate:.1f}"),
            ("QPS", lambda m: f"{m.qps:.1f}"),
        ]
        
        for label, getter in rows:
            row = f"| {label} |"
            for p in providers:
                row += f" {getter(metrics_dict[p])} |"
            lines.append(row)
        
        # Accuracy comparison
        lines.append("\n### Accuracy\n")
        lines.append(header)
        lines.append(separator)
        
        rows = [
            ("Accuracy (%)", lambda m: f"{m.accuracy:.1f}"),
            ("Precision (%)", lambda m: f"{m.precision:.1f}"),
            ("Recall (%)", lambda m: f"{m.recall:.1f}"),
            ("F1 Score", lambda m: f"{m.f1_score:.1f}"),
        ]
        
        for label, getter in rows:
            row = f"| {label} |"
            for p in providers:
                row += f" {getter(metrics_dict[p])} |"
            lines.append(row)
        
        return "\n".join(lines)
    
    def _generate_recommendations(
        self, 
        results: Dict[str, BenchmarkResult],
    ) -> str:
        """Generate recommendations based on results."""
        lines = []
        
        # Find best performers
        text_results = {
            k: v.text_metrics for k, v in results.items()
            if v.text_metrics
        }
        
        if text_results:
            # Best response time
            best_speed = min(
                text_results.items(),
                key=lambda x: x[1].avg_response_time,
            )
            lines.append(f"- **Fastest Response:** {best_speed[0]} ({best_speed[1].avg_response_time*1000:.0f}ms avg)")
            
            # Best accuracy
            best_accuracy = max(
                text_results.items(),
                key=lambda x: x[1].accuracy,
            )
            lines.append(f"- **Highest Accuracy:** {best_accuracy[0]} ({best_accuracy[1].accuracy:.1f}%)")
            
            # Best recall
            best_recall = max(
                text_results.items(),
                key=lambda x: x[1].recall,
            )
            lines.append(f"- **Highest Recall:** {best_recall[0]} ({best_recall[1].recall:.1f}%)")
        
        lines.append("\n### Use Case Recommendations\n")
        lines.append("| Use Case | Recommended Provider | Reason |")
        lines.append("|----------|---------------------|--------|")
        
        if text_results:
            best_speed_name = min(text_results.items(), key=lambda x: x[1].avg_response_time)[0]
            best_recall_name = max(text_results.items(), key=lambda x: x[1].recall)[0]
            best_f1_name = max(text_results.items(), key=lambda x: x[1].f1_score)[0]
            
            lines.append(f"| Real-time moderation | {best_speed_name} | Fastest response time |")
            lines.append(f"| High-risk content | {best_recall_name} | Highest recall (catches more violations) |")
            lines.append(f"| Balanced accuracy | {best_f1_name} | Best F1 score |")
        
        return "\n".join(lines)
    
    def print_summary(self, result: BenchmarkResult) -> None:
        """Print a summary to console."""
        print("\n" + "="*60)
        print(f"📊 Benchmark Summary: {result.provider}")
        print("="*60)
        
        if result.text_metrics:
            tm = result.text_metrics
            print(f"\n📝 Text Moderation:")
            print(f"   Total: {tm.total_requests} requests")
            print(f"   Success Rate: {tm.success_rate:.1f}%")
            print(f"   Avg Response: {tm.avg_response_time*1000:.0f}ms")
            print(f"   P99 Response: {tm.p99_response_time*1000:.0f}ms")
            print(f"   Accuracy: {tm.accuracy:.1f}%")
            print(f"   Recall: {tm.recall:.1f}%")
            print(f"   F1 Score: {tm.f1_score:.1f}")
        
        if result.image_metrics:
            im = result.image_metrics
            print(f"\n🖼️  Image Moderation:")
            print(f"   Total: {im.total_requests} requests")
            print(f"   Success Rate: {im.success_rate:.1f}%")
            print(f"   Avg Response: {im.avg_response_time*1000:.0f}ms")
            print(f"   P99 Response: {im.p99_response_time*1000:.0f}ms")
            print(f"   Accuracy: {im.accuracy:.1f}%")
            print(f"   Recall: {im.recall:.1f}%")
            print(f"   F1 Score: {im.f1_score:.1f}")
        
        print("\n" + "="*60)
