#!/bin/bash
# ============================================================
# 一键安装/卸载 launchd 定时爬虫任务
#
# 用法:
#   bash install_launchd.sh          # 安装
#   bash install_launchd.sh install   # 安装
#   bash install_launchd.sh uninstall # 卸载
#   bash install_launchd.sh status    # 查看状态
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.fintech.daily-crawler"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

ACTION="${1:-install}"

case "$ACTION" in
    install)
        echo "🚀 安装每日爬虫定时任务..."
        echo ""

        # 检查源文件
        if [ ! -f "$PLIST_SRC" ]; then
            echo "❌ 找不到 $PLIST_SRC"
            exit 1
        fi

        # 检查 cookie.txt
        if [ ! -f "$SCRIPT_DIR/cookie.txt" ]; then
            echo "⚠️  警告: cookie.txt 不存在！安装后需要配置才能运行"
            echo "   请将小红书 web_session 写入 cookie.txt"
            echo ""
        fi

        # 检查 netlify CLI
        if ! command -v netlify &> /dev/null; then
            echo "⚠️  警告: netlify CLI 未安装"
            echo "   运行: npm install -g netlify-cli"
            echo ""
        fi

        # 确保目标目录存在
        mkdir -p "$HOME/Library/LaunchAgents"

        # 如果已存在旧任务，先卸载
        if [ -f "$PLIST_DST" ]; then
            echo "📋 发现已有任务，先卸载旧版本..."
            launchctl unload "$PLIST_DST" 2>/dev/null
        fi

        # 复制 plist
        cp "$PLIST_SRC" "$PLIST_DST"
        echo "📄 已复制 plist 到 ~/Library/LaunchAgents/"

        # 加载任务
        launchctl load "$PLIST_DST"
        if [ $? -eq 0 ]; then
            echo "✅ 定时任务已安装并激活！"
        else
            echo "❌ 加载任务失败，请检查 plist 格式"
            exit 1
        fi

        echo ""
        echo "📋 任务配置:"
        echo "   名称: $PLIST_NAME"
        echo "   时间: 每天上午 10:00"
        echo "   开机: 如果错过了上次运行，登录时自动补运行"
        echo "   脚本: $SCRIPT_DIR/run_daily_crawl.sh"
        echo "   日志: $SCRIPT_DIR/cron_crawl.log"
        echo "   错误: $SCRIPT_DIR/cron_crawl_error.log"
        echo ""
        echo "💡 提示:"
        echo "   - 每 ~7 天更新一次 cookie.txt 中的 web_session"
        echo "   - 查看状态: bash install_launchd.sh status"
        echo "   - 卸载: bash install_launchd.sh uninstall"
        ;;

    uninstall)
        echo "🗑️  卸载定时任务..."
        if [ -f "$PLIST_DST" ]; then
            launchctl unload "$PLIST_DST" 2>/dev/null
            rm "$PLIST_DST"
            echo "✅ 定时任务已卸载"
        else
            echo "ℹ️  任务未安装，无需卸载"
        fi
        ;;

    status)
        echo "📊 定时任务状态"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        if [ -f "$PLIST_DST" ]; then
            echo "📄 Plist: ✅ 已安装"
        else
            echo "📄 Plist: ❌ 未安装"
            echo "   运行 'bash install_launchd.sh install' 安装"
            exit 0
        fi

        # 检查是否已加载
        if launchctl list | grep -q "$PLIST_NAME"; then
            echo "⚙️  状态: ✅ 已加载运行中"
            launchctl list "$PLIST_NAME" 2>/dev/null | head -5
        else
            echo "⚙️  状态: ⚠️ 已安装但未加载"
            echo "   尝试: launchctl load $PLIST_DST"
        fi

        echo ""
        # Cookie 状态
        if [ -f "$SCRIPT_DIR/cookie.txt" ]; then
            COOKIE=$(cat "$SCRIPT_DIR/cookie.txt" | tr -d '[:space:]')
            if [ -n "$COOKIE" ]; then
                echo "🔑 Cookie: ✅ 已配置 (${COOKIE:0:8}...)"
            else
                echo "🔑 Cookie: ❌ 文件为空"
            fi
        else
            echo "🔑 Cookie: ❌ 未配置"
        fi

        # Netlify 状态
        if command -v netlify &> /dev/null; then
            echo "🌐 Netlify: ✅ CLI 已安装"
        else
            echo "🌐 Netlify: ❌ CLI 未安装"
        fi

        # 数据状态
        if [ -f "$SCRIPT_DIR/real_data.json" ]; then
            PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
            COUNT=$($PYTHON -c "import json;print(len(json.load(open('$SCRIPT_DIR/real_data.json'))['notes']))" 2>/dev/null)
            echo "📊 数据量: ${COUNT:-?} 条"
        else
            echo "📊 数据量: 0 条（尚未开始爬取）"
        fi

        # 最后运行日志
        if [ -f "$SCRIPT_DIR/cron_crawl.log" ]; then
            echo ""
            echo "📜 最近日志 (最后5行):"
            tail -5 "$SCRIPT_DIR/cron_crawl.log"
        fi
        ;;

    *)
        echo "用法: bash install_launchd.sh [install|uninstall|status]"
        exit 1
        ;;
esac
