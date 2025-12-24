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
from .utils import get_machine_info, get_report_subdir_name
from ..config import Config


class Reporter:
    """
    Generate benchmark reports in various formats.
    
    Supports:
        - Markdown reports
        - JSON data export
        - Console output
        - Multi-provider comparison reports
    
    Reports are organized by date, region and IP address:
        reports/YYYYMMDD_region_ip/
    
    Example:
        reporter = Reporter()
        reporter.generate_markdown(result, "report.md")
        reporter.generate_json(result, "results.json")
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize reporter.
        
        Args:
            output_dir: Base directory for output files (default: Config.REPORT_DIR)
        """
        base_dir = output_dir or Config.REPORT_DIR
        
        # Create subdirectory with date_region_ip format
        subdir_name = get_report_subdir_name()
        self.output_dir = base_dir / subdir_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache machine info for this reporter instance
        self._machine_info = get_machine_info()
    
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
        
        # Use cached machine info
        machine_info = self._machine_info
        
        lines = []
        lines.append(f"# 内容审核性能测试报告")
        lines.append(f"\n**供应商:** {result.provider}")
        lines.append(f"**生成时间:** {timestamp}")
        lines.append(f"\n---\n")
        
        # Machine info section
        lines.append("## 测试环境\n")
        lines.append("| 项目 | 信息 |")
        lines.append("|------|------|")
        lines.append(f"| 区域 (Region) | {machine_info['region']} |")
        lines.append(f"| 可用区 (AZ) | {machine_info['availability_zone']} |")
        lines.append(f"| 实例ID | {machine_info['instance_id']} |")
        lines.append(f"| 主机名 | {machine_info['hostname']} |")
        lines.append(f"| IP地址 | {machine_info['ip_address']} |")
        lines.append(f"| 操作系统 | {machine_info['platform']} |")
        lines.append(f"\n---\n")
        
        # Text metrics
        if result.text_metrics:
            lines.append(self._format_metrics_section(
                "文本审核", 
                result.text_metrics,
            ))
        
        # Image metrics
        if result.image_metrics:
            lines.append(self._format_metrics_section(
                "图片审核",
                result.image_metrics,
            ))
        
        # Summary
        lines.append("\n## 总结\n")
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
        lines.append("### 概览\n")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 请求总数 | {metrics.total_requests} |")
        lines.append(f"| 成功数 | {metrics.success_count} |")
        lines.append(f"| 失败数 | {metrics.fail_count} |")
        lines.append(f"| 成功率 | {metrics.success_rate:.2f}% |")
        
        # Performance table
        lines.append("\n### 性能指标\n")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 平均响应时间 | {metrics.avg_response_time*1000:.0f}ms |")
        lines.append(f"| P50响应时间 | {metrics.p50_response_time*1000:.0f}ms |")
        lines.append(f"| P95响应时间 | {metrics.p95_response_time*1000:.0f}ms |")
        lines.append(f"| P99响应时间 | {metrics.p99_response_time*1000:.0f}ms |")
        lines.append(f"| 最小响应时间 | {metrics.min_response_time*1000:.0f}ms |")
        lines.append(f"| 最大响应时间 | {metrics.max_response_time*1000:.0f}ms |")
        lines.append(f"| QPS (每秒查询数) | {metrics.qps:.2f} |")
        lines.append(f"| 总耗时 | {metrics.total_duration:.1f}秒 |")
        
        # Accuracy table
        lines.append("\n### 准确性指标\n")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 准确率 | {metrics.accuracy:.2f}% |")
        lines.append(f"| 精确率 | {metrics.precision:.2f}% |")
        lines.append(f"| 召回率 | {metrics.recall:.2f}% |")
        lines.append(f"| F1分数 | {metrics.f1_score:.2f} |")
        
        # Confusion matrix
        lines.append("\n### 混淆矩阵\n")
        lines.append("| | 预测为违规 | 预测为正常 |")
        lines.append("|---|---|---|")
        lines.append(f"| **实际违规** | TP: {metrics.true_positive} | FN: {metrics.false_negative} |")
        lines.append(f"| **实际正常** | FP: {metrics.false_positive} | TN: {metrics.true_negative} |")
        
        # Errors
        if metrics.error_types:
            lines.append("\n### 错误统计\n")
            lines.append("| 错误类型 | 数量 |")
            lines.append("|----------|------|")
            for error_type, count in metrics.error_types.items():
                lines.append(f"| {error_type} | {count} |")
        
        return "\n".join(lines)
    
    def _generate_summary(self, result: BenchmarkResult) -> str:
        """Generate summary section."""
        lines = []
        
        if result.text_metrics:
            tm = result.text_metrics
            lines.append(f"**文本审核:**")
            lines.append(f"- 处理 {tm.total_requests} 个请求，成功率 {tm.success_rate:.1f}%")
            lines.append(f"- 平均响应时间: {tm.avg_response_time*1000:.0f}ms，P99: {tm.p99_response_time*1000:.0f}ms")
            lines.append(f"- 准确率: {tm.accuracy:.1f}%，召回率: {tm.recall:.1f}%，F1: {tm.f1_score:.1f}")
            lines.append("")
        
        if result.image_metrics:
            im = result.image_metrics
            lines.append(f"**图片审核:**")
            lines.append(f"- 处理 {im.total_requests} 个请求，成功率 {im.success_rate:.1f}%")
            lines.append(f"- 平均响应时间: {im.avg_response_time*1000:.0f}ms，P99: {im.p99_response_time*1000:.0f}ms")
            lines.append(f"- 准确率: {im.accuracy:.1f}%，召回率: {im.recall:.1f}%，F1: {im.f1_score:.1f}")
        
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
        
        # Use cached machine info
        machine_info = self._machine_info
        
        data = {
            "provider": result.provider,
            "generated_at": datetime.now().isoformat(),
            "test_environment": {
                "region": machine_info["region"],
                "availability_zone": machine_info["availability_zone"],
                "instance_id": machine_info["instance_id"],
                "hostname": machine_info["hostname"],
                "ip_address": machine_info["ip_address"],
                "platform": machine_info["platform"],
            },
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
        lines.append("# 内容审核供应商对比报告")
        lines.append(f"\n**生成时间:** {timestamp}")
        lines.append(f"**对比供应商:** {', '.join(results.keys())}")
        lines.append("\n---\n")
        
        # Text comparison
        text_results = {
            k: v.text_metrics for k, v in results.items() 
            if v.text_metrics
        }
        if text_results:
            lines.append(self._format_comparison_table(
                "文本审核对比",
                text_results,
            ))
        
        # Image comparison
        image_results = {
            k: v.image_metrics for k, v in results.items()
            if v.image_metrics
        }
        if image_results:
            lines.append(self._format_comparison_table(
                "图片审核对比",
                image_results,
            ))
        
        # Recommendations
        lines.append("\n## 建议\n")
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
        lines.append("### 性能对比\n")
        header = "| 指标 |" + "|".join(f" {p} " for p in providers) + "|"
        separator = "|------|" + "|".join("------" for _ in providers) + "|"
        lines.append(header)
        lines.append(separator)
        
        rows = [
            ("平均响应(ms)", lambda m: f"{m.avg_response_time*1000:.0f}"),
            ("P99响应(ms)", lambda m: f"{m.p99_response_time*1000:.0f}"),
            ("成功率(%)", lambda m: f"{m.success_rate:.1f}"),
            ("QPS", lambda m: f"{m.qps:.1f}"),
        ]
        
        for label, getter in rows:
            row = f"| {label} |"
            for p in providers:
                row += f" {getter(metrics_dict[p])} |"
            lines.append(row)
        
        # Accuracy comparison
        lines.append("\n### 准确性对比\n")
        lines.append(header)
        lines.append(separator)
        
        rows = [
            ("准确率(%)", lambda m: f"{m.accuracy:.1f}"),
            ("精确率(%)", lambda m: f"{m.precision:.1f}"),
            ("召回率(%)", lambda m: f"{m.recall:.1f}"),
            ("F1分数", lambda m: f"{m.f1_score:.1f}"),
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
            lines.append(f"- **响应最快:** {best_speed[0]} (平均 {best_speed[1].avg_response_time*1000:.0f}ms)")
            
            # Best accuracy
            best_accuracy = max(
                text_results.items(),
                key=lambda x: x[1].accuracy,
            )
            lines.append(f"- **准确率最高:** {best_accuracy[0]} ({best_accuracy[1].accuracy:.1f}%)")
            
            # Best recall
            best_recall = max(
                text_results.items(),
                key=lambda x: x[1].recall,
            )
            lines.append(f"- **召回率最高:** {best_recall[0]} ({best_recall[1].recall:.1f}%)")
        
        lines.append("\n### 场景推荐\n")
        lines.append("| 使用场景 | 推荐供应商 | 原因 |")
        lines.append("|----------|------------|------|")
        
        if text_results:
            best_speed_name = min(text_results.items(), key=lambda x: x[1].avg_response_time)[0]
            best_recall_name = max(text_results.items(), key=lambda x: x[1].recall)[0]
            best_f1_name = max(text_results.items(), key=lambda x: x[1].f1_score)[0]
            
            lines.append(f"| 实时审核 | {best_speed_name} | 响应速度最快 |")
            lines.append(f"| 高风险内容 | {best_recall_name} | 召回率最高，漏检最少 |")
            lines.append(f"| 综合平衡 | {best_f1_name} | F1分数最优 |")
        
        return "\n".join(lines)
    
    def print_summary(self, result: BenchmarkResult) -> None:
        """Print a summary to console."""
        print("\n" + "="*60)
        print(f"📊 测试报告摘要: {result.provider}")
        print("="*60)
        
        if result.text_metrics:
            tm = result.text_metrics
            print(f"\n📝 文本审核:")
            print(f"   请求总数: {tm.total_requests}")
            print(f"   成功率: {tm.success_rate:.1f}%")
            print(f"   平均响应: {tm.avg_response_time*1000:.0f}ms")
            print(f"   P99响应: {tm.p99_response_time*1000:.0f}ms")
            print(f"   准确率: {tm.accuracy:.1f}%")
            print(f"   召回率: {tm.recall:.1f}%")
            print(f"   F1分数: {tm.f1_score:.1f}")
        
        if result.image_metrics:
            im = result.image_metrics
            print(f"\n🖼️  图片审核:")
            print(f"   请求总数: {im.total_requests}")
            print(f"   成功率: {im.success_rate:.1f}%")
            print(f"   平均响应: {im.avg_response_time*1000:.0f}ms")
            print(f"   P99响应: {im.p99_response_time*1000:.0f}ms")
            print(f"   准确率: {im.accuracy:.1f}%")
            print(f"   召回率: {im.recall:.1f}%")
            print(f"   F1分数: {im.f1_score:.1f}")
        
        print("\n" + "="*60)
