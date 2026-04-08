#!/bin/bash
# ============================================================
# 安全爬虫定时任务脚本 - 一周一次全量增量更新
# 
# 使用方式：
#   1. 手动运行:
#      bash run_safe_crawl.sh
#
#   2. 配置 crontab 定时运行（每周六上午10点）:
#      crontab -e
#      0 10 * * 6 /Users/zimyin/CodeBuddy/20260317215615/run_safe_crawl.sh >> /Users/zimyin/CodeBuddy/20260317215615/cron_crawl.log 2>&1
#
#   3. macOS launchd 定时任务:
#      见项目目录下的 com.fintech.crawler.plist
#
# 策略说明：
#   - 每周六一次性爬取所有6个平台的最新数据
#   - 增量模式：只新增未爬过的笔记，已有数据不动
#   - 模拟人类行为：随机延迟、穿插浏览推荐页、休息
#   - 爬完后自动：重新生成月度分析 + 构建 Netlify 部署版
#   - 预计耗时 2~3 小时（因为模拟人类行为+大量延迟）
#
# 注意事项：
#   - 需要先配置 cookie.txt（小红书 web_session）
#   - cookie 大约 7 天过期，需定期更新
#   - 建议配置代理IP以降低风控风险
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=========================================="
echo "🛡️  安全爬虫 - 每周增量更新"
echo "⏰ $(date '+%Y-%m-%d %H:%M:%S %A')"
echo "=========================================="

# 检查 cookie 文件
if [ ! -f "cookie.txt" ]; then
    echo "❌ cookie.txt 不存在！请先配置"
    exit 1
fi

COOKIE_CONTENT=$(cat cookie.txt | tr -d '[:space:]')
if [ -z "$COOKIE_CONTENT" ]; then
    echo "❌ cookie.txt 为空！请填入 web_session"
    exit 1
fi

echo "🔑 Cookie: ${COOKIE_CONTENT:0:8}...${COOKIE_CONTENT: -4}"

# 检查 Python3
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "❌ 未找到 Python3！"
    exit 1
fi

echo "🐍 Python: $PYTHON"
echo "📂 数据文件: $SCRIPT_DIR/real_data.json"

# 显示当前数据量
if [ -f "real_data.json" ]; then
    CURRENT_COUNT=$($PYTHON -c "import json;print(len(json.load(open('real_data.json'))['notes']))" 2>/dev/null)
    echo "📊 当前数据量: ${CURRENT_COUNT:-?} 条"
fi

# 运行安全爬虫（全平台增量爬取 + 自动构建）
# --all: 爬取所有6个平台
# --resume: 如果上次中断了会自动续爬
# --auto-build: 爬完自动更新月度分析+Netlify部署版
echo ""
echo "🚀 开始增量爬取（全平台）..."
$PYTHON safe_crawler.py \
    --session-file cookie.txt \
    --all \
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
    echo "✅ 周度更新完成 ($(date '+%H:%M:%S'))"
else
    echo "⚠️ 爬虫任务异常退出 code=$EXIT_CODE ($(date '+%H:%M:%S'))"
fi
echo "=========================================="
