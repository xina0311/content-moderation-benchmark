#!/usr/bin/env python3
"""
Content Moderation Benchmark - CLI Entry Point

Usage:
    python main.py run --provider shumei --data test_data.xlsx --limit 100
    python main.py compare --providers shumei,yidun --data test_data.xlsx
    python main.py quick-test --provider shumei
"""

import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import Config
from src.providers import get_provider, list_providers, PROVIDERS
from src.data.loader import DataLoader, create_sample_data
from src.data.datasets import VendorDataLoader, DATASET_CONFIGS, list_datasets, get_dataset_info
from src.benchmark.runner import BenchmarkRunner, MultiProviderRunner
from src.benchmark.reporter import Reporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging level."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    
    # Also set level for our modules
    for module in ['src.providers', 'src.benchmark', 'src.data']:
        logging.getLogger(module).setLevel(level)


@click.group()
@click.version_option(version="1.0.0")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output (INFO level)')
@click.option('--debug', is_flag=True, help='Enable debug output (DEBUG level, shows request/response)')
@click.pass_context
def cli(ctx, verbose, debug):
    """
    Content Moderation Benchmark Tool
    
    A framework for benchmarking content moderation API providers.
    Compare performance, accuracy, and reliability across different vendors.
    
    Use -v for verbose output, --debug for detailed request/response logs.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['debug'] = debug
    setup_logging(verbose, debug)


@cli.command()
@click.option('--provider', '-p', required=True, help='Provider name (e.g., shumei)')
@click.option('--data', '-d', required=True, help='Path to test data file (Excel/JSON/CSV)')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of test cases')
@click.option('--text/--no-text', default=True, help='Run text moderation tests')
@click.option('--image/--no-image', default=True, help='Run image moderation tests')
@click.option('--output', '-o', default=None, help='Output report filename')
@click.option('--format', '-f', type=click.Choice(['md', 'json', 'both']), default='both', help='Output format')
def run(provider, data, limit, text, image, output, format):
    """
    Run benchmark for a single provider.
    
    Example:
        python main.py run -p shumei -d test_data.xlsx -l 100
    """
    console.print(f"\n[bold blue]Content Moderation Benchmark[/bold blue]")
    console.print(f"Provider: [cyan]{provider}[/cyan]")
    console.print(f"Data: [cyan]{data}[/cyan]")
    if limit:
        console.print(f"Limit: [cyan]{limit}[/cyan]")
    console.print("")
    
    # Get provider
    try:
        provider_instance = get_provider(provider)
        console.print(f"✅ Provider initialized: {provider_instance.display_name}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"Available providers: {', '.join(list_providers())}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error initializing provider: {e}[/red]")
        console.print("Make sure your .env file is configured correctly.")
        sys.exit(1)
    
    # Verify data file
    if not Path(data).exists():
        console.print(f"[red]Error: Data file not found: {data}[/red]")
        sys.exit(1)
    
    # Run benchmark
    runner = BenchmarkRunner(provider_instance)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running benchmark...", total=None)
        
        result = runner.run(
            data_file=data,
            limit=limit,
            test_text=text,
            test_image=image,
        )
        
        progress.update(task, completed=True)
    
    # Generate reports
    Config.ensure_directories()
    reporter = Reporter()
    
    if format in ['md', 'both']:
        md_path = reporter.generate_markdown(result, output)
        console.print(f"📄 Markdown report: [green]{md_path}[/green]")
    
    if format in ['json', 'both']:
        json_path = reporter.generate_json(result)
        console.print(f"📊 JSON results: [green]{json_path}[/green]")
    
    # Print summary
    reporter.print_summary(result)


@cli.command()
@click.option('--providers', '-p', required=True, help='Comma-separated provider names')
@click.option('--data', '-d', required=True, help='Path to test data file')
@click.option('--limit', '-l', default=None, type=int, help='Limit number of test cases')
@click.option('--text/--no-text', default=True, help='Run text moderation tests')
@click.option('--image/--no-image', default=True, help='Run image moderation tests')
def compare(providers, data, limit, text, image):
    """
    Compare multiple providers.
    
    Example:
        python main.py compare -p shumei,yidun -d test_data.xlsx -l 500
    """
    provider_names = [p.strip() for p in providers.split(',')]
    
    console.print(f"\n[bold blue]Content Moderation Provider Comparison[/bold blue]")
    console.print(f"Providers: [cyan]{', '.join(provider_names)}[/cyan]")
    console.print(f"Data: [cyan]{data}[/cyan]")
    console.print("")
    
    # Initialize providers
    multi_runner = MultiProviderRunner()
    
    for name in provider_names:
        try:
            provider_instance = get_provider(name)
            multi_runner.add_provider(provider_instance)
            console.print(f"✅ {name}: initialized")
        except Exception as e:
            console.print(f"[yellow]⚠️  {name}: {e}[/yellow]")
    
    if not multi_runner.providers:
        console.print("[red]No providers initialized. Exiting.[/red]")
        sys.exit(1)
    
    # Run comparison
    console.print("\n[bold]Running benchmarks...[/bold]\n")
    
    results = multi_runner.run_comparison(
        data_file=data,
        limit=limit,
        test_text=text,
        test_image=image,
    )
    
    # Generate comparison report
    Config.ensure_directories()
    reporter = Reporter()
    
    report_path = reporter.generate_comparison_report(results)
    console.print(f"\n📄 Comparison report: [green]{report_path}[/green]")
    
    # Print comparison table
    _print_comparison_table(results)


def _print_comparison_table(results):
    """Print comparison results as a table."""
    console.print("\n[bold]Comparison Summary[/bold]\n")
    
    # Text comparison table
    text_results = {k: v.text_metrics for k, v in results.items() if v.text_metrics}
    if text_results:
        table = Table(title="Text Moderation Comparison")
        table.add_column("Provider", style="cyan")
        table.add_column("Avg Response", justify="right")
        table.add_column("P99 Response", justify="right")
        table.add_column("Success Rate", justify="right")
        table.add_column("Accuracy", justify="right")
        table.add_column("Recall", justify="right")
        table.add_column("F1 Score", justify="right")
        
        for name, metrics in text_results.items():
            table.add_row(
                name,
                f"{metrics.avg_response_time*1000:.0f}ms",
                f"{metrics.p99_response_time*1000:.0f}ms",
                f"{metrics.success_rate:.1f}%",
                f"{metrics.accuracy:.1f}%",
                f"{metrics.recall:.1f}%",
                f"{metrics.f1_score:.1f}",
            )
        
        console.print(table)
    
    # Image comparison table
    image_results = {k: v.image_metrics for k, v in results.items() if v.image_metrics}
    if image_results:
        table = Table(title="Image Moderation Comparison")
        table.add_column("Provider", style="cyan")
        table.add_column("Avg Response", justify="right")
        table.add_column("P99 Response", justify="right")
        table.add_column("Success Rate", justify="right")
        table.add_column("Accuracy", justify="right")
        table.add_column("Recall", justify="right")
        table.add_column("F1 Score", justify="right")
        
        for name, metrics in image_results.items():
            table.add_row(
                name,
                f"{metrics.avg_response_time*1000:.0f}ms",
                f"{metrics.p99_response_time*1000:.0f}ms",
                f"{metrics.success_rate:.1f}%",
                f"{metrics.accuracy:.1f}%",
                f"{metrics.recall:.1f}%",
                f"{metrics.f1_score:.1f}",
            )
        
        console.print(table)


@cli.command('quick-test')
@click.option('--provider', '-p', required=True, help='Provider name')
@click.option('--samples', '-n', default=10, help='Number of test samples')
def quick_test(provider, samples):
    """
    Run a quick connectivity test.
    
    Example:
        python main.py quick-test -p shumei -n 5
    """
    console.print(f"\n[bold blue]Quick Connectivity Test[/bold blue]")
    console.print(f"Provider: [cyan]{provider}[/cyan]")
    console.print(f"Samples: [cyan]{samples}[/cyan]")
    console.print("")
    
    try:
        provider_instance = get_provider(provider)
        console.print(f"✅ Provider initialized: {provider_instance.display_name}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    
    # Run quick test
    runner = BenchmarkRunner(provider_instance)
    result = runner.run_quick_test(num_samples=samples)
    
    if result.text_metrics:
        tm = result.text_metrics
        console.print(f"\n[bold]Results:[/bold]")
        console.print(f"  Success Rate: {'[green]' if tm.success_rate > 90 else '[red]'}{tm.success_rate:.1f}%[/]")
        console.print(f"  Avg Response: {tm.avg_response_time*1000:.0f}ms")
        
        if tm.success_rate == 100:
            console.print("\n[green]✅ Provider is working correctly![/green]")
        else:
            console.print("\n[yellow]⚠️  Some requests failed. Check your configuration.[/yellow]")


@cli.command('list-providers')
def list_providers_cmd():
    """List available providers."""
    console.print("\n[bold]Available Providers:[/bold]\n")
    
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Display Name")
    table.add_column("Status")
    
    for name, provider_class in PROVIDERS.items():
        try:
            provider = provider_class()
            status = "[green]✅ Configured[/green]"
        except Exception as e:
            status = f"[red]❌ Not configured[/red]"
        
        table.add_row(name, provider_class.display_name, status)
    
    console.print(table)
    console.print("\nTo configure a provider, set the required environment variables in .env")


@cli.command('create-sample')
@click.option('--output', '-o', default='sample_data.json', help='Output filename')
@click.option('--format', '-f', type=click.Choice(['json', 'csv']), default='json', help='Output format')
def create_sample(output, format):
    """Create sample test data file."""
    create_sample_data(output, format)
    console.print(f"[green]✅ Sample data created: {output}[/green]")
    console.print("\nEdit this file to add your test cases.")


@cli.command('list-datasets')
def list_datasets_cmd():
    """List available vendor datasets."""
    console.print("\n[bold]Available Vendor Datasets:[/bold]\n")
    
    table = Table()
    table.add_column("Vendor", style="cyan")
    table.add_column("Display Name")
    table.add_column("Description")
    table.add_column("Text Files")
    table.add_column("Image Files")
    
    for name, config in DATASET_CONFIGS.items():
        text_count = len(config.text_files)
        image_count = len(config.image_files)
        table.add_row(
            name,
            config.display_name,
            config.description[:50] + "..." if len(config.description) > 50 else config.description,
            str(text_count),
            str(image_count),
        )
    
    console.print(table)
    console.print("\nUse: python main.py run-dataset -p <provider> -s <dataset> -l <limit>")


@cli.command('run-dataset')
@click.option('--provider', '-p', required=True, help='Provider name (e.g., shumei, yidun, juntong)')
@click.option('--dataset', '-s', required=True, help='Dataset name (e.g., shumei, yidun, juntong, huoshan)')
@click.option('--limit', '-l', default=100, type=int, help='Limit number of test cases per type')
@click.option('--text/--no-text', default=True, help='Run text moderation tests')
@click.option('--image/--no-image', default=True, help='Run image moderation tests')
@click.option('--output', '-o', default=None, help='Output report filename')
def run_dataset(provider, dataset, limit, text, image, output):
    """
    Run benchmark using a vendor's dataset.
    
    This command loads test data from pre-configured vendor datasets,
    making it easy to test any provider against any vendor's test data.
    
    Examples:
        # Test shumei provider with shumei dataset
        python main.py run-dataset -p shumei -s shumei -l 100
        
        # Test yidun provider with juntong dataset  
        python main.py run-dataset -p yidun -s juntong -l 200
        
        # Test all providers with the same dataset
        python main.py run-dataset -p shumei -s yidun -l 500
    """
    console.print(f"\n[bold blue]Content Moderation Benchmark (Dataset Mode)[/bold blue]")
    console.print(f"Provider: [cyan]{provider}[/cyan]")
    console.print(f"Dataset: [cyan]{dataset}[/cyan]")
    console.print(f"Limit: [cyan]{limit}[/cyan] per type")
    console.print("")
    
    # Validate dataset
    if dataset not in DATASET_CONFIGS:
        console.print(f"[red]Error: Unknown dataset '{dataset}'[/red]")
        console.print(f"Available datasets: {', '.join(DATASET_CONFIGS.keys())}")
        sys.exit(1)
    
    dataset_config = DATASET_CONFIGS[dataset]
    console.print(f"📁 Dataset: {dataset_config.display_name}")
    console.print(f"   {dataset_config.description}")
    
    # Get provider
    try:
        provider_instance = get_provider(provider)
        console.print(f"✅ Provider initialized: {provider_instance.display_name}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"Available providers: {', '.join(list_providers())}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error initializing provider: {e}[/red]")
        console.print("Make sure your .env file is configured correctly.")
        sys.exit(1)
    
    # Load data using VendorDataLoader
    console.print(f"\n[bold]Loading test data...[/bold]")
    
    try:
        data_loader = VendorDataLoader(dataset)
    except Exception as e:
        console.print(f"[red]Error loading dataset: {e}[/red]")
        sys.exit(1)
    
    text_cases = []
    image_cases = []
    
    if text:
        text_cases = data_loader.load_text_cases(limit=limit)
        console.print(f"  📝 Text cases: {len(text_cases)}")
    
    if image:
        image_cases = data_loader.load_image_cases(limit=limit)
        console.print(f"  🖼️  Image cases: {len(image_cases)}")
    
    if not text_cases and not image_cases:
        console.print("[yellow]⚠️  No test cases loaded. Check dataset configuration.[/yellow]")
        sys.exit(1)
    
    # Run benchmark
    runner = BenchmarkRunner(provider_instance)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running benchmark...", total=None)
        
        result = runner.run(
            text_cases=text_cases if text else None,
            image_cases=image_cases if image else None,
            test_text=text and bool(text_cases),
            test_image=image and bool(image_cases),
        )
        
        progress.update(task, completed=True)
    
    # Generate reports
    Config.ensure_directories()
    reporter = Reporter()
    
    # Add dataset info to result
    result.metadata = result.metadata or {}
    result.metadata['dataset'] = dataset
    result.metadata['dataset_name'] = dataset_config.display_name
    
    md_path = reporter.generate_markdown(result, output)
    console.print(f"📄 Markdown report: [green]{md_path}[/green]")
    
    json_path = reporter.generate_json(result)
    console.print(f"📊 JSON results: [green]{json_path}[/green]")
    
    # Print summary
    reporter.print_summary(result)


@cli.command('init')
def init():
    """Initialize a new benchmark project."""
    console.print("\n[bold blue]Initializing Benchmark Project[/bold blue]\n")
    
    # Create directories
    Config.ensure_directories()
    console.print(f"✅ Created output directory: {Config.OUTPUT_DIR}")
    console.print(f"✅ Created reports directory: {Config.REPORT_DIR}")
    
    # Check .env
    env_file = Path(".env")
    if not env_file.exists():
        console.print("\n[yellow]⚠️  No .env file found.[/yellow]")
        console.print("Copy .env.example to .env and configure your API credentials:")
        console.print("  cp .env.example .env")
    else:
        console.print("✅ .env file exists")
    
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Configure your API credentials in .env")
    console.print("2. Prepare your test data (Excel/JSON/CSV)")
    console.print("3. Run: python main.py run -p shumei -d your_data.xlsx")


if __name__ == "__main__":
    cli()
