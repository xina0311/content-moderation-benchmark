# Content Moderation Benchmark

A comprehensive framework for benchmarking content moderation API providers. Compare performance, accuracy, and reliability across different vendors like Shumei (数美), Bytedance (字节), NetEase Yidun (网易易盾), Juntong (君同), and more.

## Features

- 🚀 **Multi-provider Support**: Easily switch between and compare different content moderation providers
- 📊 **Comprehensive Metrics**: Track response time, QPS, accuracy, precision, recall, and F1 score
- 📈 **Performance Benchmarking**: Concurrent testing with configurable parallelism
- 📝 **Multiple Data Formats**: Support for Excel, JSON, and CSV test data
- 📋 **Detailed Reports**: Generate Markdown and JSON reports
- 🔄 **Provider Comparison**: Side-by-side comparison of multiple providers

## Supported Providers

| Provider | Status | Text | Image |
|----------|--------|------|-------|
| Shumei (数美科技) | ✅ Ready | ✅ | ✅ |
| Bytedance (字节跳动) | 🚧 Template | - | - |
| NetEase Yidun (网易易盾) | 🚧 Template | - | - |
| Juntong (君同) | 🚧 Template | - | - |

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/content-moderation-benchmark.git
cd content-moderation-benchmark

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API credentials
```

Configure your provider credentials in `.env`:

```env
# Shumei (数美科技)
SHUMEI_ACCESS_KEY=your_access_key_here
SHUMEI_APP_ID=default
```

### 3. Run Benchmark

```bash
# Initialize project directories
python main.py init

# Run a quick connectivity test
python main.py quick-test -p shumei

# Run full benchmark
python main.py run -p shumei -d your_test_data.xlsx -l 100
```

## Usage

### Run Benchmark for Single Provider

```bash
python main.py run --provider shumei --data test_data.xlsx --limit 100

# Options:
#   -p, --provider    Provider name (required)
#   -d, --data        Path to test data file (required)
#   -l, --limit       Limit number of test cases
#   --text/--no-text  Enable/disable text tests (default: enabled)
#   --image/--no-image Enable/disable image tests (default: enabled)
#   -o, --output      Output report filename
#   -f, --format      Output format: md, json, or both (default: both)
```

### Compare Multiple Providers

```bash
python main.py compare --providers shumei,yidun --data test_data.xlsx -l 500
```

### Quick Connectivity Test

```bash
python main.py quick-test --provider shumei --samples 10
```

### List Available Providers

```bash
python main.py list-providers
```

### Create Sample Test Data

```bash
python main.py create-sample --output sample_data.json --format json
```

## Test Data Format

### Excel Format

Create an Excel file with sheets named "文本测试题" and "图片测试题":

| 类型 | 序号 | 内容 | 预期风险 |
|------|------|------|----------|
| 黑样本 | 1 | 敏感内容... | 涉政 |
| 白样本 | 2 | 正常内容... | 正常 |

### JSON Format

```json
{
  "text": [
    {"id": "text_001", "content": "测试文本", "expected_risk": "正常", "category": "白样本"},
    {"id": "text_002", "content": "敏感内容", "expected_risk": "涉政", "category": "黑样本"}
  ],
  "image": [
    {"id": "img_001", "content": "https://example.com/image.jpg", "expected_risk": "正常"}
  ]
}
```

### CSV Format

```csv
id,content,expected_risk,category
text_001,测试文本,正常,白样本
text_002,敏感内容,涉政,黑样本
```

## Metrics Explained

### Performance Metrics

| Metric | Description |
|--------|-------------|
| Avg Response Time | Average API response time |
| P50/P95/P99 | Response time percentiles |
| QPS | Queries per second |
| Success Rate | Percentage of successful API calls |

### Accuracy Metrics

| Metric | Description |
|--------|-------------|
| Accuracy | Overall correct predictions |
| Precision | True positives / (True positives + False positives) |
| Recall | True positives / (True positives + False negatives) |
| F1 Score | Harmonic mean of precision and recall |

## Project Structure

```
content-moderation-benchmark/
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
├── README.md              # This file
│
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   │
│   ├── providers/         # Provider implementations
│   │   ├── __init__.py
│   │   ├── base.py        # Abstract base class
│   │   └── shumei.py      # Shumei provider
│   │
│   ├── data/              # Data loading
│   │   ├── __init__.py
│   │   └── loader.py      # Multi-format data loader
│   │
│   └── benchmark/         # Benchmark execution
│       ├── __init__.py
│       ├── runner.py      # Benchmark runner
│       ├── metrics.py     # Metrics collection
│       └── reporter.py    # Report generation
│
├── output/                # Test outputs (gitignored)
└── reports/               # Generated reports (gitignored)
```

## Adding a New Provider

1. Create a new file in `src/providers/`:

```python
# src/providers/myprovider.py
from .base import BaseProvider, ModerationResult, ContentType
from ..config import Config

class MyProvider(BaseProvider):
    name = "myprovider"
    display_name = "My Provider"
    
    def _load_config(self):
        return {
            "api_key": os.getenv("MYPROVIDER_API_KEY"),
            # ... other config
        }
    
    def moderate_text(self, text: str, **kwargs) -> ModerationResult:
        # Implement API call
        pass
    
    def moderate_image(self, image_url: str, **kwargs) -> ModerationResult:
        # Implement API call
        pass
```

2. Register in `src/providers/__init__.py`:

```python
from .myprovider import MyProvider

PROVIDERS = {
    "shumei": ShumeiProvider,
    "myprovider": MyProvider,  # Add this line
}
```

3. Add configuration to `.env.example`:

```env
# My Provider
MYPROVIDER_API_KEY=your_api_key_here
```

## Sample Output

### Console Output

```
Content Moderation Benchmark
Provider: shumei
Data: test_data.xlsx
Limit: 100

✅ Provider initialized: 数美科技

============================================================
📊 Benchmark Summary: shumei
============================================================

📝 Text Moderation:
   Total: 100 requests
   Success Rate: 100.0%
   Avg Response: 85ms
   P99 Response: 156ms
   Accuracy: 94.0%
   Recall: 92.5%
   F1 Score: 93.2

============================================================
```

### Markdown Report

Reports are generated in the `reports/` directory with detailed metrics, confusion matrices, and recommendations.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SHUMEI_ACCESS_KEY` | Shumei API access key | Yes (for Shumei) |
| `SHUMEI_APP_ID` | Shumei application ID | No (default: 'default') |
| `MAX_WORKERS` | Concurrent workers | No (default: 10) |
| `REQUEST_INTERVAL` | Delay between requests (seconds) | No (default: 0.1) |
| `REQUEST_TIMEOUT` | Request timeout (seconds) | No (default: 30) |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-provider`)
3. Commit your changes (`git commit -am 'Add new provider'`)
4. Push to the branch (`git push origin feature/new-provider`)
5. Create a Pull Request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built for comparing content moderation services in production environments
- Inspired by the need for standardized benchmarking across providers
