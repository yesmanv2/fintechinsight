#!/bin/bash
# 小红书舆情爬虫 - 一键启动脚本
# 用法: ./start_real_crawl.sh [web_session_cookie]

set -e
cd "$(dirname "$0")"

echo "============================================="
echo "🔍 小红书舆情爬虫 - 一键启动"
echo "============================================="

# 获取 web_session
WEB_SESSION=""

if [ -n "$1" ]; then
    WEB_SESSION="$1"
    echo "🔑 使用命令行参数传入的 cookie"
elif [ -f "cookie.txt" ]; then
    WEB_SESSION=$(cat cookie.txt | tr -d '\n')
    echo "📄 从 cookie.txt 读取 cookie"
else
    echo ""
    echo "❌ 未找到 web_session cookie!"
    echo ""
    echo "获取方式:"
    echo "  1. 浏览器打开 https://www.xiaohongshu.com 并登录"
    echo "  2. F12 → Application → Cookies"
    echo "  3. 找到 web_session，复制值"
    echo ""
    echo "使用方式:"
    echo "  方法1: ./start_real_crawl.sh 你的cookie值"
    echo "  方法2: 把cookie写入 cookie.txt 文件后再运行"
    echo "  方法3: python3 get_cookie.py (交互式获取)"
    echo ""
    exit 1
fi

echo "🔑 Cookie: ${WEB_SESSION:0:8}...${WEB_SESSION: -4}"
echo ""

# Step 1: 爬取数据
echo "📥 Step 1: 开始爬取真实数据..."
python3 crawler.py --session "$WEB_SESSION" --pages 2

# Step 2: 启动服务器
echo ""
echo "🌐 Step 2: 启动舆情监控服务器..."
# 杀掉旧进程
lsof -ti :8765 | xargs kill -9 2>/dev/null || true
sleep 1
python3 server.py &
SERVER_PID=$!
sleep 2

echo ""
echo "============================================="
echo "✅ 一切就绪！"
echo "   💻 打开: http://localhost:8765"
echo "   📱 手机: http://$(ipconfig getifaddr en0 2>/dev/null || echo 'localhost'):8765"
echo "   🛑 停止: kill $SERVER_PID"
echo "============================================="
