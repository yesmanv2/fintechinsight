#!/bin/bash
# ============================================================
# 每日分散爬虫脚本 - 每天爬1个平台，周日整理输出
# 
# 策略说明：
#   周一=支付宝  周二=微信支付  周三=抖音支付
#   周四=美团支付  周五=京东支付  周六=云闪付
#   周日=休息 + 自动整理构建
#
# 使用方式：
#   1. 手动运行（自动根据星期几决定爬哪个平台）:
#      bash run_daily_crawl.sh
#
#   2. 配置 crontab 每天定时运行（推荐上午10点）:
#      crontab -e
#      0 10 * * * /Users/zimyin/CodeBuddy/20260317215615/run_daily_crawl.sh >> /Users/zimyin/CodeBuddy/20260317215615/cron_crawl.log 2>&1
#
#   3. 也可以随机时间运行（更像真人）:
#      # 每天10-12点之间随机时间运行（见下方 crontab 写法）
#      0 10 * * * sleep $((RANDOM \% 7200)) && /Users/zimyin/CodeBuddy/20260317215615/run_daily_crawl.sh >> /Users/zimyin/CodeBuddy/20260317215615/cron_crawl.log 2>&1
#
# 注意事项：
#   - 需要先配置 cookie.txt（小红书 web_session）
#   - Cookie 大约 7 天过期，需定期更新
#   - 建议配置 proxy.txt（代理IP池），详见 SETUP_GUIDE.md
#   - 每天只爬 ~25 个关键词，约 30-60 分钟即可完成
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 今天星期几
DAY_OF_WEEK=$(date +%u)  # 1=周一 ... 7=周日
WEEKDAY_NAME=("" "周一" "周二" "周三" "周四" "周五" "周六" "周日")

echo ""
echo "=========================================="
echo "🛡️  每日分散爬虫"
echo "⏰ $(date '+%Y-%m-%d %H:%M:%S') ${WEEKDAY_NAME[$DAY_OF_WEEK]}"
echo "=========================================="

# 检查 Python3
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "❌ 未找到 Python3！"
    exit 1
fi

# ---- 周日：仅整理构建，不爬取 ----
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    echo "😴 今天是周日 - 休息日"
    echo "📊 执行周度整理：重新生成分析 + 构建部署版..."
    echo ""
    $PYTHON safe_crawler.py --weekly-build
    EXIT_CODE=$?
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ 周度整理完成！($(date '+%H:%M:%S'))"
    else
        echo "⚠️ 整理异常 code=$EXIT_CODE"
    fi
    echo "=========================================="
    exit $EXIT_CODE
fi

# ---- 周一~周六：爬取当天对应平台 ----

# 检查 cookie 文件
if [ ! -f "cookie.txt" ]; then
    echo "❌ cookie.txt 不存在！请先配置"
    echo "   详见 SETUP_GUIDE.md 的 Cookie 获取教程"
    exit 1
fi

COOKIE_CONTENT=$(cat cookie.txt | tr -d '[:space:]')
if [ -z "$COOKIE_CONTENT" ]; then
    echo "❌ cookie.txt 为空！请填入 web_session"
    exit 1
fi

echo "🔑 Cookie: ${COOKIE_CONTENT:0:8}...${COOKIE_CONTENT: -4}"
echo "🐍 Python: $PYTHON"

# 显示代理状态
if [ -f "proxy.txt" ]; then
    PROXY_COUNT=$(grep -v '^#' proxy.txt | grep -v '^$' | wc -l | tr -d ' ')
    echo "🌐 代理池: $PROXY_COUNT 个代理可用"
else
    echo "⚠️  代理: 未配置（建议创建 proxy.txt）"
fi

# 显示当前数据量
if [ -f "real_data.json" ]; then
    CURRENT_COUNT=$($PYTHON -c "import json;print(len(json.load(open('real_data.json'))['notes']))" 2>/dev/null)
    echo "📊 当前数据量: ${CURRENT_COUNT:-?} 条"
fi

# 运行爬虫（自动按星期分配平台，增量模式）
echo ""
echo "🚀 开始今日爬取..."
$PYTHON safe_crawler.py \
    --session-file cookie.txt \
    --resume \
    --auto-build

EXIT_CODE=$?

# 显示更新后的数据量
if [ -f "real_data.json" ]; then
    NEW_COUNT=$($PYTHON -c "import json;print(len(json.load(open('real_data.json'))['notes']))" 2>/dev/null)
    echo ""
    echo "📊 更新后数据量: ${NEW_COUNT:-?} 条 (之前: ${CURRENT_COUNT:-?})"
fi

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 今日爬取完成 ($(date '+%H:%M:%S'))"
else
    echo "⚠️ 爬虫异常退出 code=$EXIT_CODE ($(date '+%H:%M:%S'))"
    echo "   💡 使用 --resume 参数可以断点续爬"
fi
echo "=========================================="
