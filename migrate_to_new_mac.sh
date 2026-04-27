#!/bin/bash
# ============================================================
# 舆情项目 - 个人Mac一键迁移脚本
# 在个人Mac上运行此脚本即可完成全部迁移
# ============================================================

set -e
echo "🚀 舆情项目迁移工具"
echo "============================================================"

# ---- 配置 ----
GITHUB_TOKEN="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"
PROJECT_DIR="$HOME/CodeBuddy/fintechinsight"
FORTUNE_DIR="$HOME/CodeBuddy/fortune-telling"

# ---- Step 1: 检查基础环境 ----
echo ""
echo "📋 Step 1: 检查环境..."

# Python
if command -v python3 &>/dev/null; then
    echo "  ✅ Python3: $(python3 --version)"
else
    echo "  ❌ 未安装 Python3，请先安装: brew install python"
    exit 1
fi

# Git
if command -v git &>/dev/null; then
    echo "  ✅ Git: $(git --version)"
else
    echo "  ❌ 未安装 Git，请先安装: xcode-select --install"
    exit 1
fi

# Homebrew
if command -v brew &>/dev/null; then
    echo "  ✅ Homebrew 已安装"
else
    echo "  ⚠️ 未安装 Homebrew，建议安装: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
fi

# ---- Step 2: Clone 项目 ----
echo ""
echo "📦 Step 2: 下载项目..."

mkdir -p "$HOME/CodeBuddy"

if [ -d "$PROJECT_DIR" ]; then
    echo "  ⚠️ $PROJECT_DIR 已存在，跳过 clone（如需重新下载请先删除）"
else
    echo "  正在下载舆情项目..."
    git clone "https://${GITHUB_TOKEN}@github.com/yesmanv2/fintechinsight-backup.git" "$PROJECT_DIR"
    echo "  ✅ 舆情项目下载完成"
fi

if [ -d "$FORTUNE_DIR" ]; then
    echo "  ⚠️ $FORTUNE_DIR 已存在，跳过 clone"
else
    echo "  正在下载算命项目..."
    git clone "https://${GITHUB_TOKEN}@github.com/yesmanv2/fortune-telling-backup.git" "$FORTUNE_DIR"
    echo "  ✅ 算命项目下载完成"
fi

# ---- Step 3: 安装 Python 依赖 ----
echo ""
echo "🐍 Step 3: 安装 Python 依赖..."

pip3 install --quiet playwright playwright-stealth pycryptodome python-docx 2>/dev/null
echo "  ✅ Python 依赖安装完成"

echo "  安装 Chromium 浏览器..."
python3 -m playwright install chromium 2>/dev/null
echo "  ✅ Chromium 安装完成"

# ---- Step 4: 安装 Node.js 依赖（算命项目） ----
echo ""
echo "📦 Step 4: 安装算命项目依赖..."
if [ -f "$FORTUNE_DIR/package.json" ]; then
    cd "$FORTUNE_DIR" && npm install --silent 2>/dev/null
    echo "  ✅ Node 依赖安装完成"
else
    echo "  ⏭️ 无 package.json，跳过"
fi

# ---- Step 5: 配置 Git ----
echo ""
echo "🔧 Step 5: 配置 Git..."
cd "$PROJECT_DIR"
git config user.name "yesmanv2"
git config user.email "yesmanv2@users.noreply.github.com"
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/yesmanv2/fintechinsight-backup.git"

cd "$FORTUNE_DIR"
git config user.name "yesmanv2"
git config user.email "yesmanv2@users.noreply.github.com"
git remote set-url origin "https://${GITHUB_TOKEN}@github.com/yesmanv2/fortune-telling-backup.git"

echo "  ✅ Git 配置完成"

# ---- Step 6: 安装 GitHub CLI ----
echo ""
echo "🔧 Step 6: 安装 GitHub CLI..."
if command -v gh &>/dev/null; then
    echo "  ✅ gh CLI 已安装"
else
    if command -v brew &>/dev/null; then
        brew install gh 2>/dev/null
        echo "  ✅ gh CLI 安装完成"
    else
        echo "  ⚠️ 跳过 gh CLI（需要 Homebrew）"
    fi
fi

# ---- Step 7: 验证 ----
echo ""
echo "✅ Step 7: 验证迁移结果..."
echo ""

echo "  📁 舆情项目: $PROJECT_DIR"
echo "     文件数: $(find "$PROJECT_DIR" -type f | wc -l | tr -d ' ')"
if [ -f "$PROJECT_DIR/real_data.json" ]; then
    echo "     数据文件: ✅ real_data.json 存在"
else
    echo "     数据文件: ❌ real_data.json 不存在"
fi
if [ -f "$PROJECT_DIR/crawl_all.py" ]; then
    echo "     爬虫脚本: ✅ crawl_all.py 存在"
else
    echo "     爬虫脚本: ❌ crawl_all.py 不存在"
fi

echo ""
echo "  📁 算命项目: $FORTUNE_DIR"
echo "     文件数: $(find "$FORTUNE_DIR" -type f -not -path '*/node_modules/*' | wc -l | tr -d ' ')"

# ---- 完成 ----
echo ""
echo "============================================================"
echo "🎉 迁移完成！"
echo "============================================================"
echo ""
echo "📌 接下来你需要手动做的："
echo ""
echo "  1. 在 Chrome 登录小红书（爬虫需要 Cookie）"
echo "     → 用一个新号/备用号，别用被限制的大号"
echo ""
echo "  2. 测试爬虫能否正常工作："
echo "     cd $PROJECT_DIR"
echo "     python3 crawl_all.py --test"
echo ""
echo "  3. 本地预览网站："
echo "     cd $PROJECT_DIR/netlify-deploy"
echo "     python3 -m http.server 8080"
echo "     → 打开 http://localhost:8080"
echo ""
echo "  4. 同步代码到GitHub："
echo "     cd $PROJECT_DIR"
echo "     git add -A && git commit -m '更新' && git push"
echo ""
echo "  5. 更新公开网站（GitHub Pages）："
echo "     cp -r netlify-deploy/* docs/"
echo "     cd .. && git add docs && git commit -m '更新网站' && git push"
echo "     → 注意：公开repo是 yesmanv2/fintechinsight（不是backup）"
echo ""
