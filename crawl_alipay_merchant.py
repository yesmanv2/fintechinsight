#!/usr/bin/env python3
"""
支付宝服务商后台监控爬虫
=====================================================
登录支付宝服务商网页后台，定期快照关键页面，检测变化。

监控范围:
  - 政策/公告页面
  - 费率/结算规则页面
  - 接口/产品能力更新
  - 服务商排行/数据页面

工作原理:
  1. 使用已保存的 session 或 Cookie 登录服务商后台
  2. 依次访问配置的监控页面
  3. 提取页面关键内容（文本 + 结构化数据）
  4. 与上次快照对比，生成变化摘要
  5. 保存快照和变化记录

安全策略:
  - 页面间切换间隔 60-120 秒
  - 每个页面浏览 15-30 秒
  - 服务商后台是登录态，风险低于公域平台
  - 遇到重新登录提示立即停止

使用方式:
    python3 crawl_alipay_merchant.py              # 正常执行
    python3 crawl_alipay_merchant.py --login       # 打开浏览器手动登录
    python3 crawl_alipay_merchant.py --test        # 测试登录态
    python3 crawl_alipay_merchant.py --dry-run     # 只打印计划
    python3 crawl_alipay_merchant.py --list-pages  # 列出所有监控页面
"""
import asyncio
import json
import os
import re
import random
import difflib
import hashlib
import argparse
import sys
from datetime import datetime
from collections import defaultdict

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
except ImportError:
    print("❌ 需要安装: pip install playwright playwright-stealth")
    print("   然后运行: playwright install chromium")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'alipay_merchant_data.json')
SNAPSHOT_DIR = os.path.join(BASE_DIR, 'alipay_merchant_snapshots')
SESSION_FILE = os.path.join(BASE_DIR, '.alipay_session.json')
PROGRESS_FILE = os.path.join(BASE_DIR, '.crawl_alipay_progress.json')

# =====================================================================
# 安全配置
# =====================================================================
PAGE_SWITCH_DELAY_MIN = 60      # 页面间切换最小等待：1分钟
PAGE_SWITCH_DELAY_MAX = 120     # 页面间切换最大等待：2分钟
PAGE_BROWSE_MIN = 15            # 每个页面浏览最小时间
PAGE_BROWSE_MAX = 30            # 每个页面浏览最大时间
SCROLL_TIMES_MIN = 2            # 每页最少滚动
SCROLL_TIMES_MAX = 4            # 每页最多滚动
# =====================================================================

# 监控页面配置
# 注意: 具体 URL 需要根据用户实际的服务商后台确定
# 这里提供常见的支付宝开放平台/服务商后台 URL 模板
MONITOR_PAGES = {
    "公告通知": {
        "name": "公告通知",
        "urls": [
            "https://open.alipay.com/portal/forum/notice",
            "https://openhome.alipay.com/platform/notice.htm",
        ],
        "selectors": [
            "[class*='notice']", "[class*='announcement']", "[class*='bulletin']",
            ".ant-list", ".list-item", "table", ".content-area",
        ],
        "description": "支付宝开放平台公告和通知",
    },
    "产品能力": {
        "name": "产品能力",
        "urls": [
            "https://open.alipay.com/api",
            "https://openhome.alipay.com/platform/productIndex.htm",
        ],
        "selectors": [
            "[class*='product']", "[class*='capability']", "[class*='api']",
            ".ant-card", ".card-list", "table",
        ],
        "description": "API 和产品能力更新",
    },
    "费率规则": {
        "name": "费率规则",
        "urls": [
            "https://open.alipay.com/portal/forum/notice",
            "https://b.alipay.com/page/rate",
        ],
        "selectors": [
            "[class*='rate']", "[class*='fee']", "[class*='settle']",
            "table", ".ant-table", ".content",
        ],
        "description": "费率和结算规则",
    },
    "服务商中心": {
        "name": "服务商中心",
        "urls": [
            "https://b.alipay.com/page/isv-center",
            "https://mrchportal.alipay.com/",
        ],
        "selectors": [
            "[class*='rank']", "[class*='data']", "[class*='statistic']",
            ".ant-card", "table", ".dashboard",
        ],
        "description": "服务商数据和排名",
    },
    "开发文档更新": {
        "name": "开发文档更新",
        "urls": [
            "https://open.alipay.com/portal/forum/notice?type=1",
        ],
        "selectors": [
            "[class*='doc']", "[class*='change']", "[class*='update']",
            ".ant-list", "table", ".content",
        ],
        "description": "开发文档和接口变更",
    },
}


# =========================================================
# 断点续爬
# =========================================================

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed": [], "last_run": "", "total_runs": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# =========================================================
# 快照和对比
# =========================================================

def get_snapshot_dir(date_str=None):
    """获取快照目录（按月份组织）"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m')
    snap_dir = os.path.join(SNAPSHOT_DIR, date_str)
    os.makedirs(snap_dir, exist_ok=True)
    return snap_dir


def save_snapshot(page_name, content, date_str=None):
    """保存页面快照"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    snap_dir = get_snapshot_dir(date_str[:7])
    safe_name = re.sub(r'[^\w\-]', '_', page_name)
    filename = f"{safe_name}_{date_str}.json"
    filepath = os.path.join(snap_dir, filename)
    
    snapshot = {
        "page_name": page_name,
        "snapshot_date": date_str,
        "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "content_hash": hashlib.md5(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "content": content,
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    
    return filepath


def load_latest_snapshot(page_name, before_date=None):
    """加载最近的快照"""
    if before_date is None:
        before_date = datetime.now().strftime('%Y-%m-%d')
    
    safe_name = re.sub(r'[^\w\-]', '_', page_name)
    
    # 搜索所有月份目录
    if not os.path.exists(SNAPSHOT_DIR):
        return None
    
    all_snapshots = []
    for month_dir in sorted(os.listdir(SNAPSHOT_DIR), reverse=True):
        month_path = os.path.join(SNAPSHOT_DIR, month_dir)
        if not os.path.isdir(month_path):
            continue
        for fname in os.listdir(month_path):
            if fname.startswith(safe_name) and fname.endswith('.json'):
                # 提取日期
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
                if date_match:
                    snap_date = date_match.group(1)
                    if snap_date < before_date:
                        all_snapshots.append((snap_date, os.path.join(month_path, fname)))
    
    if not all_snapshots:
        return None
    
    # 取最近的
    all_snapshots.sort(key=lambda x: x[0], reverse=True)
    latest_path = all_snapshots[0][1]
    
    try:
        with open(latest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def compare_snapshots(old_snapshot, new_content, page_name):
    """对比两次快照，生成变化摘要"""
    changes = []
    
    if old_snapshot is None:
        # 首次快照，记录为全新
        changes.append({
            "page_name": page_name,
            "change_type": "initial",
            "change_summary": f"首次快照 — {page_name}",
            "old_content": "",
            "new_content": json.dumps(new_content, ensure_ascii=False)[:500],
            "detected_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "snapshot_date": datetime.now().strftime('%Y-%m-%d'),
        })
        return changes
    
    old_content = old_snapshot.get("content", {})
    old_hash = old_snapshot.get("content_hash", "")
    new_hash = hashlib.md5(json.dumps(new_content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    
    if old_hash == new_hash:
        # 没有变化
        return changes
    
    # 文本级对比
    old_text = old_content.get("text", "")
    new_text = new_content.get("text", "")
    
    if old_text != new_text:
        # 使用 difflib 生成差异
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=''))
        
        added_lines = [l[1:] for l in diff if l.startswith('+') and not l.startswith('+++')]
        removed_lines = [l[1:] for l in diff if l.startswith('-') and not l.startswith('---')]
        
        if added_lines:
            changes.append({
                "page_name": page_name,
                "change_type": "added",
                "change_summary": f"新增 {len(added_lines)} 行内容",
                "old_content": "",
                "new_content": "\n".join(added_lines[:10]),  # 只取前10行
                "detected_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "snapshot_date": datetime.now().strftime('%Y-%m-%d'),
            })
        
        if removed_lines:
            changes.append({
                "page_name": page_name,
                "change_type": "removed",
                "change_summary": f"删除 {len(removed_lines)} 行内容",
                "old_content": "\n".join(removed_lines[:10]),
                "new_content": "",
                "detected_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "snapshot_date": datetime.now().strftime('%Y-%m-%d'),
            })
    
    # 表格数据对比
    old_tables = old_content.get("tables", [])
    new_tables = new_content.get("tables", [])
    
    if len(new_tables) != len(old_tables):
        changes.append({
            "page_name": page_name,
            "change_type": "modified",
            "change_summary": f"表格数量变化: {len(old_tables)} → {len(new_tables)}",
            "old_content": f"{len(old_tables)} 个表格",
            "new_content": f"{len(new_tables)} 个表格",
            "detected_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "snapshot_date": datetime.now().strftime('%Y-%m-%d'),
        })
    
    # 标题/列表对比
    old_headings = old_content.get("headings", [])
    new_headings = new_content.get("headings", [])
    
    new_h = set(new_headings) - set(old_headings)
    removed_h = set(old_headings) - set(new_headings)
    
    if new_h:
        changes.append({
            "page_name": page_name,
            "change_type": "added",
            "change_summary": f"新增标题/栏目: {', '.join(list(new_h)[:5])}",
            "old_content": "",
            "new_content": ", ".join(list(new_h)[:10]),
            "detected_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "snapshot_date": datetime.now().strftime('%Y-%m-%d'),
        })
    
    if removed_h:
        changes.append({
            "page_name": page_name,
            "change_type": "removed",
            "change_summary": f"移除标题/栏目: {', '.join(list(removed_h)[:5])}",
            "old_content": ", ".join(list(removed_h)[:10]),
            "new_content": "",
            "detected_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "snapshot_date": datetime.now().strftime('%Y-%m-%d'),
        })
    
    return changes


# =========================================================
# 浏览器管理器
# =========================================================

class AlipayBrowserManager:
    """支付宝服务商后台浏览器管理器"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self, headless=True):
        self.playwright = await async_playwright().start()
        await self._create_browser(headless=headless)

    async def _create_browser(self, headless=True):
        if self.context:
            try: await self.context.close()
            except: pass
        if self.browser:
            try: await self.browser.close()
            except: pass

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ],
        )

        # 加载保存的 session state
        storage_state = None
        if os.path.exists(SESSION_FILE):
            storage_state = SESSION_FILE
            print(f"  📂 加载已保存的 session")

        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            storage_state=storage_state,
        )

        self.page = await self.context.new_page()
        stealth = Stealth(
            navigator_platform_override="MacIntel",
            navigator_vendor_override="Google Inc.",
        )
        await stealth.apply_stealth_async(self.page)

    async def check_login(self):
        """检查是否已登录"""
        try:
            # 尝试访问服务商后台页面
            await self.page.goto("https://open.alipay.com/portal/forum/notice",
                               wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
            
            current_url = self.page.url
            body_text = await self.page.evaluate("document.body?.innerText?.slice(0,500) || ''")
            
            # 检查是否被重定向到登录页
            if 'login' in current_url.lower() or '登录' in body_text[:100]:
                return False
            return True
        except Exception:
            return False

    async def save_session(self):
        try:
            state = await self.context.storage_state()
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print(f"  💾 Session 已保存")
        except Exception as e:
            print(f"  ⚠️ 保存 session 失败: {e}")

    async def is_alive(self):
        try:
            if not self.page or not self.browser:
                return False
            await self.page.evaluate("1+1")
            return True
        except:
            return False

    async def ensure_alive(self):
        if not await self.is_alive():
            print("  🔄 浏览器断开，正在重建...")
            await self._create_browser()
            return True
        return False

    async def cleanup(self):
        try:
            if self.context: await self.context.close()
        except: pass
        try:
            if self.browser: await self.browser.close()
        except: pass
        try:
            if self.playwright: await self.playwright.stop()
        except: pass


# =========================================================
# 页面内容提取
# =========================================================

async def extract_page_content(page, page_config):
    """提取页面的关键内容"""
    content = {
        "title": "",
        "text": "",
        "headings": [],
        "tables": [],
        "lists": [],
        "links": [],
        "raw_html_length": 0,
    }
    
    try:
        # 页面标题
        content["title"] = await page.title() or ""
        
        # 页面主体文本
        body_text = await page.evaluate("""
            () => {
                const main = document.querySelector('main, .content, .main-content, #content, [role="main"]')
                    || document.body;
                return main ? main.innerText : '';
            }
        """)
        content["text"] = body_text[:10000]  # 限制大小
        
        # 提取标题
        headings = await page.evaluate("""
            () => {
                const hs = document.querySelectorAll('h1, h2, h3, h4, [class*="title"], [class*="heading"]');
                return Array.from(hs).slice(0, 50).map(h => h.innerText.trim()).filter(t => t.length > 0 && t.length < 200);
            }
        """)
        content["headings"] = headings or []
        
        # 提取表格数据
        tables = await page.evaluate("""
            () => {
                const tables = document.querySelectorAll('table');
                return Array.from(tables).slice(0, 10).map(table => {
                    const rows = [];
                    table.querySelectorAll('tr').forEach(tr => {
                        const cells = [];
                        tr.querySelectorAll('th, td').forEach(cell => {
                            cells.push(cell.innerText.trim());
                        });
                        if (cells.length > 0) rows.push(cells);
                    });
                    return rows;
                });
            }
        """)
        content["tables"] = tables or []
        
        # 提取列表
        lists = await page.evaluate("""
            () => {
                const items = document.querySelectorAll('li, [class*="list-item"], [class*="notice-item"]');
                return Array.from(items).slice(0, 50).map(li => li.innerText.trim().slice(0, 200)).filter(t => t.length > 5);
            }
        """)
        content["lists"] = lists or []
        
        # 提取链接
        links = await page.evaluate("""
            () => {
                const anchors = document.querySelectorAll('a[href]');
                return Array.from(anchors).slice(0, 100).map(a => ({
                    text: a.innerText.trim().slice(0, 100),
                    href: a.href,
                })).filter(l => l.text.length > 0);
            }
        """)
        content["links"] = links or []
        
        # HTML 长度（用于粗略判断页面是否加载完整）
        html_len = await page.evaluate("document.documentElement.outerHTML.length")
        content["raw_html_length"] = html_len
        
    except Exception as e:
        print(f"      ⚠️ 内容提取异常: {e}")
    
    return content


async def human_browse_page(page):
    """模拟人浏览页面"""
    scroll_times = random.randint(SCROLL_TIMES_MIN, SCROLL_TIMES_MAX)
    for _ in range(scroll_times):
        dist = random.randint(200, 600)
        await page.evaluate(f"window.scrollBy(0, {dist})")
        await asyncio.sleep(random.uniform(2, 4))
    
    # 偶尔滚回去
    if random.random() < 0.3:
        await page.evaluate(f"window.scrollBy(0, -{random.randint(100, 300)})")
        await asyncio.sleep(random.uniform(1, 2))


# =========================================================
# 主流程
# =========================================================

async def main():
    parser = argparse.ArgumentParser(description='支付宝服务商后台监控爬虫')
    parser.add_argument('--login', action='store_true', help='打开浏览器手动登录')
    parser.add_argument('--test', action='store_true', help='测试登录态')
    parser.add_argument('--dry-run', action='store_true', help='只打印计划')
    parser.add_argument('--list-pages', action='store_true', help='列出所有监控页面')
    parser.add_argument('--reset', action='store_true', help='重置进度')
    args = parser.parse_args()

    start_time = datetime.now()
    print("=" * 60)
    print("💙 支付宝服务商后台监控爬虫")
    print(f"📅 {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛡️ 安全模式: Playwright Stealth + session 注入")
    print(f"📁 快照目录: {SNAPSHOT_DIR}")
    print(f"📁 数据文件: {OUTPUT_FILE}")
    print("=" * 60)

    # --list-pages
    if args.list_pages:
        print(f"\n📋 监控页面配置 ({len(MONITOR_PAGES)} 个):")
        for key, cfg in MONITOR_PAGES.items():
            print(f"\n  📌 {cfg['name']} — {cfg['description']}")
            for url in cfg['urls']:
                print(f"     {url}")
        return

    # --dry-run
    if args.dry_run:
        print(f"\n📊 计划: 监控 {len(MONITOR_PAGES)} 个页面")
        for key, cfg in MONITOR_PAGES.items():
            print(f"    {cfg['name']}: {cfg['urls'][0]}")
        est_minutes = len(MONITOR_PAGES) * 2.5
        print(f"\n⏱️ 预计耗时: ~{est_minutes:.0f} 分钟")
        return

    # --login 模式
    if args.login:
        print("\n🌐 打开支付宝服务商登录页面...")
        mgr = AlipayBrowserManager()
        try:
            await mgr.start(headless=False)
            await mgr.page.goto("https://open.alipay.com", wait_until="domcontentloaded", timeout=30000)
            print("  📱 请在浏览器中完成登录")
            print("  ⏳ 登录完成后按回车继续...")
            await asyncio.get_event_loop().run_in_executor(None, input)
            await mgr.save_session()
            print("  ✅ 登录成功！session 已保存")
        finally:
            await mgr.cleanup()
        return

    # 检查 session
    if not os.path.exists(SESSION_FILE):
        print("❌ 未找到已保存的 session")
        print("💡 请先运行: python3 crawl_alipay_merchant.py --login")
        return

    # --test 模式
    mgr = AlipayBrowserManager()
    if args.test:
        print("\n🧪 测试登录态...")
        try:
            await mgr.start()
            logged_in = await mgr.check_login()
            if logged_in:
                print("  ✅ 登录态有效!")
            else:
                print("  ❌ 登录态已失效，请重新登录:")
                print("     python3 crawl_alipay_merchant.py --login")
        finally:
            await mgr.cleanup()
        return

    # 断点续爬
    progress = load_progress()
    if args.reset:
        progress = {"completed": [], "last_run": "", "total_runs": 0}
        save_progress(progress)
        print("\n🔄 已重置进度")
    completed_set = set(progress.get("completed", []))

    # 加载已有变化记录
    all_changes = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            all_changes = existing_data.get('changes', [])
            print(f"\n📂 已有变化记录: {len(all_changes)} 条")
        except Exception:
            pass

    # 开始监控
    new_changes = []
    pages_done = 0

    try:
        print("\n🌐 启动浏览器...")
        await mgr.start()
        
        # 验证登录态
        logged_in = await mgr.check_login()
        if not logged_in:
            print("❌ 登录态已失效，请重新运行 --login")
            return
        print("  ✅ 登录态有效\n")

        today = datetime.now().strftime('%Y-%m-%d')

        for page_key, page_config in MONITOR_PAGES.items():
            if page_key in completed_set:
                print(f"  ⏭️ {page_config['name']} (已完成，跳过)")
                continue

            print(f"\n  📌 监控: {page_config['name']}")
            
            await mgr.ensure_alive()
            
            page_content = None
            
            # 尝试配置中的每个 URL
            for url in page_config['urls']:
                try:
                    print(f"    🌐 访问: {url}")
                    await mgr.page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    await asyncio.sleep(random.uniform(4, 8))
                    
                    # 检查是否需要重新登录
                    current_url = mgr.page.url
                    if 'login' in current_url.lower():
                        print(f"    ⚠️ 被重定向到登录页，跳过此 URL")
                        continue
                    
                    # 模拟浏览
                    await human_browse_page(mgr.page)
                    
                    # 提取内容
                    page_content = await extract_page_content(mgr.page, page_config)
                    
                    if page_content and len(page_content.get("text", "")) > 50:
                        print(f"    ✅ 内容提取成功 (文本 {len(page_content['text'])} 字, "
                              f"{len(page_content['headings'])} 标题, "
                              f"{len(page_content['tables'])} 表格)")
                        break
                    else:
                        print(f"    ⚠️ 内容过少，尝试下一个 URL")
                        page_content = None
                        
                except Exception as e:
                    print(f"    ❌ 访问失败: {e}")
                    continue
            
            if page_content:
                # 保存快照
                snap_path = save_snapshot(page_key, page_content, today)
                print(f"    💾 快照已保存: {os.path.basename(snap_path)}")
                
                # 与上次快照对比
                old_snapshot = load_latest_snapshot(page_key, today)
                changes = compare_snapshots(old_snapshot, page_content, page_config['name'])
                
                if changes:
                    new_changes.extend(changes)
                    for c in changes:
                        change_icon = {"added": "🆕", "removed": "🗑️", "modified": "✏️", "initial": "📋"}.get(c['change_type'], "📋")
                        print(f"    {change_icon} {c['change_summary']}")
                else:
                    print(f"    ✅ 无变化")
                
                pages_done += 1
                
                # 记录进度
                completed_set.add(page_key)
                progress["completed"] = list(completed_set)
                progress["last_run"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_progress(progress)
            else:
                print(f"    ❌ 所有 URL 均失败")
            
            # 页面间等待
            if page_key != list(MONITOR_PAGES.keys())[-1]:
                delay = random.uniform(PAGE_SWITCH_DELAY_MIN, PAGE_SWITCH_DELAY_MAX)
                print(f"    ⏳ 页面切换等待 {delay:.0f}s...")
                await asyncio.sleep(delay)

        # 保存 session
        await mgr.save_session()

    finally:
        await mgr.cleanup()

    # 保存变化记录
    all_changes.extend(new_changes)
    output = {
        "meta": {
            "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "platform": "支付宝服务商后台",
            "total_changes": len(all_changes),
            "this_run_changes": len(new_changes),
            "pages_monitored": pages_done,
        },
        "changes": all_changes,
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n{'=' * 60}")
    print(f"🎉 支付宝服务商后台监控完成！")
    print(f"{'=' * 60}")
    print(f"  ⏱️ 耗时: {elapsed/60:.1f} 分钟")
    print(f"  📌 监控页面: {pages_done}/{len(MONITOR_PAGES)} 个")
    print(f"  🔄 本次变化: {len(new_changes)} 条")
    print(f"  📁 累计变化: {len(all_changes)} 条")

    remaining = sum(1 for k in MONITOR_PAGES if k not in completed_set)
    if remaining > 0:
        print(f"  📋 剩余: {remaining} 个页面待监控")
    else:
        print(f"  ✅ 全部页面监控完成！")
        progress["completed"] = []
        progress["total_runs"] = progress.get("total_runs", 0) + 1
        save_progress(progress)

    print(f"\n💾 数据已保存: {OUTPUT_FILE}")
    print(f"📸 快照目录: {SNAPSHOT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
