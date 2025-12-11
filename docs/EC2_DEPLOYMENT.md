# AWS EC2 部署指南

本指南介绍如何在 AWS EC2（中国区）上部署和运行定时压测。

## 1. EC2 环境准备

### 1.1 创建 EC2 实例

推荐配置：
- **实例类型**: t3.medium 或更高（2 vCPU, 4GB RAM）
- **操作系统**: Amazon Linux 2023 或 Ubuntu 22.04
- **存储**: 20GB gp3
- **安全组**: 允许出站 HTTPS (443) 访问

### 1.2 安装依赖

```bash
# Amazon Linux 2023
sudo yum update -y
sudo yum install -y python3.11 python3.11-pip git

# Ubuntu 22.04
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git
```

## 2. 部署代码

### 2.1 克隆代码

```bash
cd ~
git clone https://github.com/xina0311/content-moderation-benchmark.git
cd content-moderation-benchmark
```

### 2.2 创建虚拟环境

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.3 配置 API 密钥

```bash
cp .env.example .env
nano .env  # 或 vim .env
```

编辑 `.env` 文件，填入你的 API 密钥：
```
SHUMEI_ACCESS_KEY=你的数美API密钥
SHUMEI_APP_ID=default
```

### 2.4 上传测试数据

将测试数据文件上传到 EC2：

```bash
# 在本地执行（从本地上传到EC2）
scp -i your-key.pem data/1127数美测试题.xlsx ec2-user@your-ec2-ip:~/content-moderation-benchmark/data/
```

或者使用 AWS S3：
```bash
# 在EC2上
aws s3 cp s3://your-bucket/1127数美测试题.xlsx data/
```

## 3. 运行测试

### 3.1 快速验证

```bash
source venv/bin/activate
python main.py quick-test -p shumei
```

### 3.2 单次压测

```bash
python main.py run -p shumei -d data/1127数美测试题.xlsx -l 100
```

### 3.3 定时压测（24小时）

**前台运行（用于测试）:**
```bash
python scheduled_benchmark.py \
    --provider shumei \
    --data data/1127数美测试题.xlsx \
    --duration 24 \
    --interval 2 \
    --text-limit 1000 \
    --image-limit 500
```

**后台运行（推荐）:**
```bash
nohup python scheduled_benchmark.py \
    --provider shumei \
    --data data/1127数美测试题.xlsx \
    --duration 24 \
    --interval 2 \
    --text-limit 1000 \
    --image-limit 500 \
    > scheduled_benchmark.log 2>&1 &

# 记录进程ID
echo $! > benchmark.pid
```

### 3.4 使用 Screen（防止SSH断开）

```bash
# 安装 screen
sudo yum install -y screen  # Amazon Linux
# 或
sudo apt install -y screen  # Ubuntu

# 创建新会话
screen -S benchmark

# 运行测试
python scheduled_benchmark.py --duration 24 --interval 2 --text-limit 1000 --image-limit 500

# 按 Ctrl+A 然后按 D 分离会话

# 重新连接会话
screen -r benchmark
```

## 4. 监控测试

### 4.1 查看实时日志

```bash
tail -f scheduled_benchmark.log
```

### 4.2 查看中间结果

```bash
cat reports/scheduled_benchmark_progress.json | python -m json.tool
```

### 4.3 检查进程状态

```bash
ps aux | grep scheduled_benchmark
```

### 4.4 停止测试

```bash
# 使用保存的PID
kill $(cat benchmark.pid)

# 或直接查找并停止
pkill -f scheduled_benchmark
```

## 5. 获取结果

### 5.1 查看报告

```bash
ls -la reports/
cat reports/scheduled_benchmark_summary_*.md
```

### 5.2 下载结果到本地

```bash
# 在本地执行
scp -i your-key.pem -r ec2-user@your-ec2-ip:~/content-moderation-benchmark/reports/ ./
```

### 5.3 上传到 S3

```bash
aws s3 sync reports/ s3://your-bucket/benchmark-reports/
```

## 6. 常见问题

### Q: 测试中断怎么办？
A: 中间结果会保存在 `reports/scheduled_benchmark_progress.json`，可以查看已完成的轮次数据。

### Q: 如何修改并发数？
A: 编辑 `.env` 文件：
```
MAX_WORKERS=20
REQUEST_INTERVAL=0.05
```

### Q: 内存不足怎么办？
A: 
1. 减少 `--text-limit` 和 `--image-limit`
2. 升级 EC2 实例类型
3. 添加 swap 空间

### Q: 网络超时怎么办？
A: 编辑 `.env` 文件增加超时时间：
```
REQUEST_TIMEOUT=60
RETRY_TIMES=5
```

## 7. 自动化脚本

创建启动脚本 `start_benchmark.sh`：

```bash
#!/bin/bash
cd ~/content-moderation-benchmark
source venv/bin/activate

echo "Starting benchmark at $(date)"

nohup python scheduled_benchmark.py \
    --provider shumei \
    --data data/1127数美测试题.xlsx \
    --duration 24 \
    --interval 2 \
    --text-limit 1000 \
    --image-limit 500 \
    > scheduled_benchmark_$(date +%Y%m%d_%H%M%S).log 2>&1 &

echo $! > benchmark.pid
echo "Benchmark started with PID: $(cat benchmark.pid)"
```

使用方式：
```bash
chmod +x start_benchmark.sh
./start_benchmark.sh
