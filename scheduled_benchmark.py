#!/usr/bin/env python3
"""
定时压测脚本
支持在指定时间段内按固定间隔执行压测任务

用法:
    # 24小时压测，每2小时一轮
    python scheduled_benchmark.py --duration 24 --interval 2 --text-limit 1000 --image-limit 500

    # 后台运行（推荐在EC2上使用）
    nohup python scheduled_benchmark.py --duration 24 --interval 2 --text-limit 1000 --image-limit 500 > benchmark.log 2>&1 &
"""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import click

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.providers import get_provider
from src.data.loader import DataLoader
from src.benchmark.runner import BenchmarkRunner
from src.benchmark.reporter import Reporter
from src.benchmark.metrics import BenchmarkMetrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scheduled_benchmark.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class ScheduledBenchmark:
    """定时压测执行器"""
    
    def __init__(
        self,
        provider_name: str,
        data_file: str,
        text_limit: int = 1000,
        image_limit: int = 500,
        duration_hours: int = 24,
        interval_hours: int = 2,
    ):
        """
        初始化定时压测
        
        Args:
            provider_name: 供应商名称
            data_file: 测试数据文件路径
            text_limit: 每轮文本测试数量
            image_limit: 每轮图片测试数量
            duration_hours: 总测试时长（小时）
            interval_hours: 测试间隔（小时）
        """
        self.provider_name = provider_name
        self.data_file = data_file
        self.text_limit = text_limit
        self.image_limit = image_limit
        self.duration_hours = duration_hours
        self.interval_hours = interval_hours
        
        # 初始化供应商
        self.provider = get_provider(provider_name)
        
        # 初始化数据加载器
        self.loader = DataLoader(data_file)
        
        # 确保输出目录存在
        Config.ensure_directories()
        
        # 存储所有轮次结果
        self.round_results: List[Dict[str, Any]] = []
        
        # 计算总轮次
        self.total_rounds = duration_hours // interval_hours
        
        logger.info(f"定时压测初始化完成")
        logger.info(f"  供应商: {self.provider.display_name}")
        logger.info(f"  测试时长: {duration_hours}小时")
        logger.info(f"  测试间隔: {interval_hours}小时")
        logger.info(f"  预计轮次: {self.total_rounds}轮")
        logger.info(f"  每轮文本: {text_limit}条")
        logger.info(f"  每轮图片: {image_limit}条")
    
    def run(self) -> None:
        """执行定时压测"""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=self.duration_hours)
        
        logger.info(f"="*60)
        logger.info(f"开始定时压测")
        logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"预计结束: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"="*60)
        
        round_num = 0
        
        while datetime.now() < end_time:
            round_num += 1
            round_start = datetime.now()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"第 {round_num}/{self.total_rounds} 轮测试开始")
            logger.info(f"时间: {round_start.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            try:
                # 执行单轮测试
                round_result = self._run_single_round(round_num)
                self.round_results.append(round_result)
                
                # 保存中间结果
                self._save_intermediate_results()
                
                logger.info(f"第 {round_num} 轮完成")
                
            except Exception as e:
                logger.error(f"第 {round_num} 轮测试出错: {e}")
                self.round_results.append({
                    "round": round_num,
                    "timestamp": round_start.isoformat(),
                    "error": str(e),
                })
            
            # 检查是否还需要继续
            next_round_time = round_start + timedelta(hours=self.interval_hours)
            
            if next_round_time >= end_time:
                logger.info("已达到预定结束时间，停止测试")
                break
            
            # 等待到下一轮
            wait_seconds = (next_round_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                logger.info(f"等待 {wait_seconds/3600:.1f} 小时后开始下一轮...")
                logger.info(f"下一轮预计时间: {next_round_time.strftime('%Y-%m-%d %H:%M:%S')}")
                time.sleep(wait_seconds)
        
        # 生成汇总报告
        self._generate_summary_report()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"定时压测完成")
        logger.info(f"实际轮次: {len(self.round_results)}")
        logger.info(f"总耗时: {datetime.now() - start_time}")
        logger.info(f"{'='*60}")
    
    def _run_single_round(self, round_num: int) -> Dict[str, Any]:
        """执行单轮测试"""
        timestamp = datetime.now()
        
        # 加载测试数据
        text_cases = self.loader.load_text_cases(limit=self.text_limit)
        image_cases = self.loader.load_image_cases(limit=self.image_limit)
        
        logger.info(f"加载测试数据: 文本 {len(text_cases)} 条, 图片 {len(image_cases)} 条")
        
        # 执行测试
        runner = BenchmarkRunner(self.provider)
        result = runner.run(
            text_cases=text_cases,
            image_cases=image_cases,
            test_text=len(text_cases) > 0,
            test_image=len(image_cases) > 0,
        )
        
        # 生成本轮报告
        reporter = Reporter()
        report_filename = f"round_{round_num:03d}_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        reporter.generate_markdown(result, report_filename)
        
        # 打印摘要
        reporter.print_summary(result)
        
        # 构造结果数据
        round_result = {
            "round": round_num,
            "timestamp": timestamp.isoformat(),
            "text_metrics": result.text_metrics.to_dict() if result.text_metrics else None,
            "image_metrics": result.image_metrics.to_dict() if result.image_metrics else None,
        }
        
        return round_result
    
    def _save_intermediate_results(self) -> None:
        """保存中间结果（防止意外中断丢失数据）"""
        output_file = Config.REPORT_DIR / "scheduled_benchmark_progress.json"
        
        data = {
            "provider": self.provider_name,
            "config": {
                "text_limit": self.text_limit,
                "image_limit": self.image_limit,
                "duration_hours": self.duration_hours,
                "interval_hours": self.interval_hours,
            },
            "completed_rounds": len(self.round_results),
            "total_rounds": self.total_rounds,
            "rounds": self.round_results,
            "updated_at": datetime.now().isoformat(),
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"中间结果已保存: {output_file}")
    
    def _generate_summary_report(self) -> None:
        """生成汇总报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 计算汇总统计
        text_stats = self._aggregate_metrics("text_metrics")
        image_stats = self._aggregate_metrics("image_metrics")
        
        # 生成Markdown报告
        lines = []
        lines.append("# 定时压测汇总报告")
        lines.append(f"\n**供应商:** {self.provider_name}")
        lines.append(f"**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**测试配置:**")
        lines.append(f"- 总时长: {self.duration_hours}小时")
        lines.append(f"- 测试间隔: {self.interval_hours}小时")
        lines.append(f"- 每轮文本: {self.text_limit}条")
        lines.append(f"- 每轮图片: {self.image_limit}条")
        lines.append(f"- 完成轮次: {len(self.round_results)}/{self.total_rounds}")
        lines.append("\n---\n")
        
        # 文本审核汇总
        if text_stats:
            lines.append("## 文本审核汇总\n")
            lines.append("| 指标 | 平均值 | 最小值 | 最大值 | 标准差 |")
            lines.append("|------|--------|--------|--------|--------|")
            lines.append(f"| 响应时间(ms) | {text_stats['avg_response_time']['mean']:.0f} | {text_stats['avg_response_time']['min']:.0f} | {text_stats['avg_response_time']['max']:.0f} | {text_stats['avg_response_time']['std']:.0f} |")
            lines.append(f"| 成功率(%) | {text_stats['success_rate']['mean']:.1f} | {text_stats['success_rate']['min']:.1f} | {text_stats['success_rate']['max']:.1f} | {text_stats['success_rate']['std']:.2f} |")
            lines.append(f"| 准确率(%) | {text_stats['accuracy']['mean']:.1f} | {text_stats['accuracy']['min']:.1f} | {text_stats['accuracy']['max']:.1f} | {text_stats['accuracy']['std']:.2f} |")
            lines.append(f"| 召回率(%) | {text_stats['recall']['mean']:.1f} | {text_stats['recall']['min']:.1f} | {text_stats['recall']['max']:.1f} | {text_stats['recall']['std']:.2f} |")
            lines.append("")
        
        # 图片审核汇总
        if image_stats:
            lines.append("## 图片审核汇总\n")
            lines.append("| 指标 | 平均值 | 最小值 | 最大值 | 标准差 |")
            lines.append("|------|--------|--------|--------|--------|")
            lines.append(f"| 响应时间(ms) | {image_stats['avg_response_time']['mean']:.0f} | {image_stats['avg_response_time']['min']:.0f} | {image_stats['avg_response_time']['max']:.0f} | {image_stats['avg_response_time']['std']:.0f} |")
            lines.append(f"| 成功率(%) | {image_stats['success_rate']['mean']:.1f} | {image_stats['success_rate']['min']:.1f} | {image_stats['success_rate']['max']:.1f} | {image_stats['success_rate']['std']:.2f} |")
            lines.append(f"| 准确率(%) | {image_stats['accuracy']['mean']:.1f} | {image_stats['accuracy']['min']:.1f} | {image_stats['accuracy']['max']:.1f} | {image_stats['accuracy']['std']:.2f} |")
            lines.append(f"| 召回率(%) | {image_stats['recall']['mean']:.1f} | {image_stats['recall']['min']:.1f} | {image_stats['recall']['max']:.1f} | {image_stats['recall']['std']:.2f} |")
            lines.append("")
        
        # 各轮次详情
        lines.append("## 各轮次详情\n")
        lines.append("| 轮次 | 时间 | 文本响应(ms) | 图片响应(ms) | 文本准确率 | 图片准确率 |")
        lines.append("|------|------|--------------|--------------|------------|------------|")
        
        for r in self.round_results:
            if "error" in r:
                lines.append(f"| {r['round']} | {r['timestamp'][:19]} | 错误 | 错误 | - | - |")
            else:
                text_resp = r.get("text_metrics", {}).get("avg_response_time_ms", "-") if r.get("text_metrics") else "-"
                img_resp = r.get("image_metrics", {}).get("avg_response_time_ms", "-") if r.get("image_metrics") else "-"
                text_acc = r.get("text_metrics", {}).get("accuracy", "-") if r.get("text_metrics") else "-"
                img_acc = r.get("image_metrics", {}).get("accuracy", "-") if r.get("image_metrics") else "-"
                
                text_resp_str = f"{text_resp:.0f}" if isinstance(text_resp, (int, float)) else text_resp
                img_resp_str = f"{img_resp:.0f}" if isinstance(img_resp, (int, float)) else img_resp
                text_acc_str = f"{text_acc:.1f}%" if isinstance(text_acc, (int, float)) else text_acc
                img_acc_str = f"{img_acc:.1f}%" if isinstance(img_acc, (int, float)) else img_acc
                
                lines.append(f"| {r['round']} | {r['timestamp'][:19]} | {text_resp_str} | {img_resp_str} | {text_acc_str} | {img_acc_str} |")
        
        # 保存报告
        report_file = Config.REPORT_DIR / f"scheduled_benchmark_summary_{timestamp}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        logger.info(f"汇总报告已生成: {report_file}")
        
        # 保存JSON结果
        json_file = Config.REPORT_DIR / f"scheduled_benchmark_results_{timestamp}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({
                "provider": self.provider_name,
                "config": {
                    "text_limit": self.text_limit,
                    "image_limit": self.image_limit,
                    "duration_hours": self.duration_hours,
                    "interval_hours": self.interval_hours,
                },
                "summary": {
                    "text": text_stats,
                    "image": image_stats,
                },
                "rounds": self.round_results,
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"JSON结果已保存: {json_file}")
    
    def _aggregate_metrics(self, metric_type: str) -> Optional[Dict[str, Any]]:
        """聚合多轮指标"""
        import statistics
        
        values = {
            "avg_response_time": [],
            "success_rate": [],
            "accuracy": [],
            "recall": [],
            "precision": [],
            "f1_score": [],
        }
        
        for r in self.round_results:
            metrics = r.get(metric_type)
            if metrics:
                values["avg_response_time"].append(metrics.get("avg_response_time_ms", 0))
                values["success_rate"].append(metrics.get("success_rate", 0))
                values["accuracy"].append(metrics.get("accuracy", 0))
                values["recall"].append(metrics.get("recall", 0))
                values["precision"].append(metrics.get("precision", 0))
                values["f1_score"].append(metrics.get("f1_score", 0))
        
        if not values["avg_response_time"]:
            return None
        
        result = {}
        for key, vals in values.items():
            if vals:
                result[key] = {
                    "mean": statistics.mean(vals),
                    "min": min(vals),
                    "max": max(vals),
                    "std": statistics.stdev(vals) if len(vals) > 1 else 0,
                }
        
        return result


@click.command()
@click.option('--provider', '-p', default='shumei', help='供应商名称')
@click.option('--data', '-d', default='data/1127数美测试题.xlsx', help='测试数据文件')
@click.option('--duration', type=int, default=24, help='测试总时长（小时）')
@click.option('--interval', type=int, default=2, help='测试间隔（小时）')
@click.option('--text-limit', type=int, default=1000, help='每轮文本测试数量')
@click.option('--image-limit', type=int, default=500, help='每轮图片测试数量')
def main(provider, data, duration, interval, text_limit, image_limit):
    """
    定时压测工具
    
    示例:
        # 24小时压测，每2小时一轮
        python scheduled_benchmark.py --duration 24 --interval 2 --text-limit 1000 --image-limit 500
        
        # 后台运行
        nohup python scheduled_benchmark.py --duration 24 --interval 2 > benchmark.log 2>&1 &
    """
    print(f"""
╔══════════════════════════════════════════════════════════╗
║              定时压测工具 - Scheduled Benchmark          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    print(f"配置:")
    print(f"  供应商: {provider}")
    print(f"  数据文件: {data}")
    print(f"  测试时长: {duration}小时")
    print(f"  测试间隔: {interval}小时")
    print(f"  每轮文本: {text_limit}条")
    print(f"  每轮图片: {image_limit}条")
    print(f"  预计轮次: {duration // interval}轮")
    print()
    
    confirm = input("确认开始测试？(yes/no): ").strip().lower()
    if confirm != 'yes':
        print("测试已取消")
        return
    
    benchmark = ScheduledBenchmark(
        provider_name=provider,
        data_file=data,
        text_limit=text_limit,
        image_limit=image_limit,
        duration_hours=duration,
        interval_hours=interval,
    )
    
    benchmark.run()


if __name__ == "__main__":
    main()
