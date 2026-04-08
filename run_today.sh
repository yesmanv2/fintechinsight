#!/bin/bash
# 今日爬取任务：美团支付 + 云闪付 + 京东支付
# 安全执行脚本

set -e

cd "$(dirname "$0")"

echo "🔍 检查环境..."

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在，创建中..."
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 检查依赖
echo "📦 检查 Python 依赖..."
pip list | grep -q playwright || {
    echo "安装 playwright..."
    pip install playwright playwright-stealth
    playwright install chromium
}

# 检查 cookie 文件
if [ ! -f "cookie.txt" ] && [ ! -f ".env" ]; then
    echo "⚠️  警告：未找到 cookie 文件！"
    echo "请确认以下文件之一存在："
    echo "  - cookie.txt"
    echo "  - .env"
    read -p "是否继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 显示执行计划
echo ""
echo "📋 今日执行计划："
python3 crawl_tuesday.py --dry-run

echo ""
read -p "▶️  确认开始爬取？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 取消执行"
    exit 0
fi

# 开始执行
echo ""
echo "🚀 开始爬取（预计 5-6 小时）..."
echo "💡 可随时按 Ctrl+C 停止，进度会自动保存"
echo ""

python3 crawl_tuesday.py

echo ""
echo "✅ 爬取完成！"
echo "📊 数据保存在: real_data.json"
