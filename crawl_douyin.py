#!/usr/bin/env python3
"""
抖音短视频爬虫 — 搜索支付/金融相关短视频 + 热门榜单
=====================================================
直接爬抖音网页端（www.douyin.com），抓取视频标题、描述、互动数据等。

安全策略（抖音反爬比小红书更严，延迟更长）:
  1. Playwright Stealth + Chrome Cookie 注入
  2. headless=True 无头模式
  3. 关键词间隔 120-240 秒（2-4分钟）
  4. 翻页/滚动加载间隔 30-60 秒
  5. 每页随机滚动 3-6 次，停顿 2-5 秒
  6. 遇到滑块验证码或风控立即停止
  7. 断点续爬 + 断网重试
  8. 每完成 3 个关键词自动保存一次
  9. 首次运行可 headless=False 让用户手动登录

数据独立存储: douyin_data.json（不与小红书数据混合）

使用方式:
    python3 crawl_douyin.py                    # 正常执行（断点续爬）
    python3 crawl_douyin.py --reset            # 重置进度从头开始
    python3 crawl_douyin.py --test             # 测试 cookie/浏览器可用性
    python3 crawl_douyin.py --dry-run          # 只打印计划，不实际爬取
    python3 crawl_douyin.py --login            # 打开浏览器让用户手动登录，保存 cookie
"""
import asyncio
import json
import os
import re
import random
import sqlite3
import shutil
import tempfile
import subprocess
import sys
import argparse
from datetime import datetime
from urllib.parse import quote

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
except ImportError:
    print("❌ 需要安装: pip install playwright playwright-stealth")
    print("   然后运行: playwright install chromium")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'douyin_data.json')
PROGRESS_FILE = os.path.join(BASE_DIR, '.crawl_douyin_progress.json')
SESSION_FILE = os.path.join(BASE_DIR, '.douyin_session.json')

# =====================================================================
# 🛡️ 安全配置 — 抖音反爬更严，延迟比小红书更保守
# =====================================================================
KEYWORD_DELAY_MIN = 120         # 关键词间最小等待：2分钟
KEYWORD_DELAY_MAX = 240         # 关键词间最大等待：4分钟
SCROLL_DELAY_MIN = 30           # 滚动加载最小等待：30秒
SCROLL_DELAY_MAX = 60           # 滚动加载最大等待：60秒
SCROLL_TIMES_MIN = 3            # 每次搜索最少滚动次数
SCROLL_TIMES_MAX = 6            # 每次搜索最多滚动次数
SCROLL_PAUSE_MIN = 2.0          # 滚动间最小停顿
SCROLL_PAUSE_MAX = 5.0          # 滚动间最大停顿
SAVE_EVERY_N_KEYWORDS = 3       # 每3个关键词保存一次
MAX_KEYWORDS_PER_RUN = 20       # 每次运行最多搜索20个关键词
# =====================================================================

# 搜索关键词配置（支付/金融方向）
SEARCH_KEYWORDS = [
    # 抖音支付相关
    ("抖音支付 吐槽", "支付", 3),
    ("抖音支付 问题", "支付", 2),
    ("抖音先用后付 坑", "客诉", 2),
    ("抖音钱包", "支付", 2),
    ("抖音免密支付", "支付", 2),
    # 放心借/贷款
    ("放心借 利息高", "贷款", 3),
    ("放心借 逾期", "贷款", 2),
    ("抖音月付 分期", "贷款", 2),
    ("DOU分期 坑", "贷款", 2),
    # 退款/客诉
    ("抖音退款 难", "客诉", 3),
    ("抖音乱扣费", "客诉", 2),
    ("抖音自动续费 取消", "客诉", 2),
    ("抖音投诉 客服", "客诉", 2),
    ("抖音封号", "客诉", 2),
    # 团购/外卖
    ("抖音团购 退款", "客诉", 2),
    ("抖音外卖 问题", "客诉", 2),
    # 豆包AI
    ("豆包AI 体验", "AI", 2),
    # 电商
    ("抖音商城 售后", "客诉", 2),
    ("抖音直播 付款 问题", "客诉", 2),
    # 对比
    ("抖音支付 vs 微信支付", "支付", 2),
]

# 情感分析词库（复用小红书爬虫的模式）
POSITIVE_WORDS = ["好用", "方便", "不错", "推荐", "喜欢", "划算", "优惠", "赞", "省钱",
                  "给力", "太强", "真香", "解决了", "成功", "感谢", "惊喜", "便宜", "开心",
                  "太爽", "牛", "终于", "神器", "必备"]
NEGATIVE_WORDS = ["难用", "垃圾", "投诉", "骗", "坑", "差评", "恶心", "无语", "崩了", "封号",
                  "冻结", "盗刷", "焦虑", "退款", "催收", "失望", "逾期", "问题", "吐槽", "闪退",
                  "差劲", "受不了", "太慢", "坑人", "过分", "恶意", "套路", "利息高"]


def analyze_sentiment(text):
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    if neg > pos: return "negative"
    if pos > neg: return "positive"
    return "neutral"


def classify_video(text):
    """对视频内容进行分类"""
    RULES = {
        "支付": ["支付", "付款", "扫码", "转账", "收款", "红包", "钱包", "免密", "先用后付"],
        "贷款": ["贷款", "放心借", "借钱", "分期", "额度", "还款", "逾期", "催收", "月付", "利息", "利率", "DOU分期"],
        "客诉": ["投诉", "客服", "坑", "吐槽", "问题", "骗", "盗刷", "封号", "退款", "乱扣", "续费", "差评"],
        "AI": ["ai", "人工智能", "豆包", "大模型", "智能"],
        "电商": ["团购", "外卖", "直播", "商城", "购物", "探店", "售后"],
    }
    text_lower = text.lower()
    matched = []
    for cat, kws in RULES.items():
        for kw in kws:
            if kw in text_lower:
                matched.append(cat)
                break
    return matched if matched else ["其他"]


# =========================================================
# Cookie 提取
# =========================================================

def get_browser_key_mac():
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-w', '-s', 'Chrome Safe Storage', '-a', 'Chrome'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def decrypt_chromium_cookie(encrypted_value, key_password):
    try:
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2

        if encrypted_value[:3] in (b'v10', b'v11'):
            encrypted_value = encrypted_value[3:]

        salt = b'saltysalt'
        iv = b' ' * 16
        key = PBKDF2(key_password.encode('utf-8'), salt, dkLen=16, count=1003)
        cipher = AES.new(key, AES.MODE_CBC, IV=iv)
        decrypted = cipher.decrypt(encrypted_value)

        if len(decrypted) > 0:
            pad_len = decrypted[-1]
            if isinstance(pad_len, int) and 1 <= pad_len <= 16:
                if all(b == pad_len for b in decrypted[-pad_len:]):
                    decrypted = decrypted[:-pad_len]

        # 跳过垃圾首块
        if len(decrypted) > 16:
            try:
                decrypted[:16].decode('ascii')
                first_printable = all(c >= 32 and c < 127 for c in decrypted[:16])
            except:
                first_printable = False
            if not first_printable:
                start = 0
                for i in range(len(decrypted)):
                    if all(32 <= decrypted[j] < 127 for j in range(i, min(i+6, len(decrypted)))):
                        start = i
                        break
                if start > 0:
                    decrypted = decrypted[start:]

        try:
            result = decrypted.decode('utf-8')
        except UnicodeDecodeError:
            result = decrypted.decode('latin-1')

        clean = ''.join(c for c in result if c.isprintable() and ord(c) < 128)
        if len(clean) > 5:
            return clean
        return None
    except Exception:
        return None


def extract_douyin_cookies():
    """从 Chrome 提取抖音 cookie"""
    chrome_cookie_path = os.path.expanduser(
        '~/Library/Application Support/Google/Chrome/Default/Cookies'
    )
    if not os.path.exists(chrome_cookie_path):
        print("❌ 未找到 Chrome Cookie 数据库")
        return []

    key_password = get_browser_key_mac()
    if not key_password:
        print("❌ 无法获取 Chrome Keychain 密钥")
        return []

    tmp = tempfile.mktemp(suffix='.db')
    shutil.copy2(chrome_cookie_path, tmp)

    cookies = []
    try:
        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT host_key, name, value, encrypted_value, path, is_secure, "
            "is_httponly, samesite, expires_utc "
            "FROM cookies WHERE host_key LIKE '%douyin.com%'"
        )
        rows = cursor.fetchall()
        conn.close()

        print(f"  找到 {len(rows)} 条抖音 cookie")

        for host, name, value, enc_val, path, secure, httponly, samesite, expires in rows:
            final_value = value
            if not final_value and enc_val:
                decrypted = decrypt_chromium_cookie(enc_val, key_password)
                if decrypted:
                    final_value = decrypted

            if final_value:
                ss_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
                cookie = {
                    "name": name,
                    "value": final_value,
                    "domain": host if host.startswith('.') else f".{host.lstrip('.')}",
                    "path": path or "/",
                    "secure": bool(secure),
                    "httpOnly": bool(httponly),
                    "sameSite": ss_map.get(samesite, "Lax"),
                }
                cookies.append(cookie)

    except Exception as e:
        print(f"  ❌ 读取 Cookie 失败: {e}")
    finally:
        os.unlink(tmp)

    return cookies


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
# 模拟人类行为
# =========================================================

async def human_like_scroll(page):
    """模拟真人滚动浏览"""
    scroll_times = random.randint(SCROLL_TIMES_MIN, SCROLL_TIMES_MAX)
    for i in range(scroll_times):
        scroll_distance = random.randint(300, 800)
        await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
        await asyncio.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))

    if random.random() < 0.3:
        scroll_back = random.randint(100, 300)
        await page.evaluate(f"window.scrollBy(0, -{scroll_back})")
        await asyncio.sleep(random.uniform(0.5, 1.5))


async def human_like_move_mouse(page):
    """随机移动鼠标"""
    try:
        x = random.randint(200, 1200)
        y = random.randint(200, 700)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
    except Exception:
        pass


# =========================================================
# 抖音浏览器管理器
# =========================================================

class DouyinBrowserManager:
    """抖音专用浏览器管理器 — headless 模式 + stealth"""

    def __init__(self, douyin_cookies, api_results_collector):
        self.douyin_cookies = douyin_cookies
        self.api_results_collector = api_results_collector
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._current_keyword = ''
        self._current_category = ''
        self._hit_captcha = False

    async def start(self, headless=True):
        self.playwright = await async_playwright().start()
        await self._create_browser(headless=headless)

    async def _create_browser(self, headless=True):
        """创建浏览器"""
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
                '--disable-gpu',
            ],
        )

        # 如果有保存的 session state，优先使用
        storage_state = None
        if os.path.exists(SESSION_FILE):
            try:
                storage_state = SESSION_FILE
                print(f"  📂 加载已保存的 session: {SESSION_FILE}")
            except Exception:
                storage_state = None

        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            storage_state=storage_state,
        )

        # 如果没有 session state，注入 cookie
        if not storage_state and self.douyin_cookies:
            await self.context.add_cookies(self.douyin_cookies)

        self.page = await self.context.new_page()
        stealth = Stealth(
            navigator_platform_override="MacIntel",
            navigator_vendor_override="Google Inc.",
            navigator_user_agent_override="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        await stealth.apply_stealth_async(self.page)

        # 注册 API 拦截器
        self.page.on("response", self._on_response)

        # 访问首页激活 cookie
        try:
            await self.page.goto("https://www.douyin.com", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(random.uniform(3, 6))
        except Exception as e:
            print(f"  ⚠️ 首页访问异常: {e}")

    async def _on_response(self, response):
        """拦截抖音搜索 API 响应"""
        url = response.url
        # 抖音搜索 API 端点
        if '/aweme/v1/web/search/' in url or '/aweme/v1/web/general/search/' in url:
            try:
                data = await response.json()
                if data and data.get('status_code') == 0:
                    aweme_list = data.get('data', [])
                    # 搜索结果可能在不同位置
                    if not aweme_list:
                        aweme_list = data.get('aweme_list', [])
                    if not aweme_list:
                        aweme_list = data.get('data', {}).get('aweme_list', []) if isinstance(data.get('data'), dict) else []
                    
                    for item in (aweme_list if isinstance(aweme_list, list) else []):
                        aweme = item.get('aweme_info', item)
                        vid = aweme.get('aweme_id', '')
                        desc = aweme.get('desc', '') or ''
                        
                        # 作者信息
                        author_info = aweme.get('author', {})
                        author = author_info.get('nickname', '')
                        author_id = author_info.get('uid', '') or author_info.get('sec_uid', '')
                        
                        # 互动数据
                        stats = aweme.get('statistics', {})
                        like_count = stats.get('digg_count', 0)
                        comment_count = stats.get('comment_count', 0)
                        share_count = stats.get('share_count', 0)
                        play_count = stats.get('play_count', 0)
                        
                        # 发布时间
                        create_time = aweme.get('create_time', 0)
                        time_str = ''
                        if create_time:
                            try:
                                time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M')
                            except: pass
                        if not time_str:
                            time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
                        
                        # 封面
                        cover = ''
                        cover_info = aweme.get('video', {}).get('cover', {})
                        if cover_info:
                            url_list = cover_info.get('url_list', [])
                            cover = url_list[0] if url_list else ''
                        
                        # 视频链接
                        video_url = f"https://www.douyin.com/video/{vid}" if vid else ''
                        
                        full_text = f"{desc}"
                        
                        self.api_results_collector.append({
                            "_keyword": self._current_keyword,
                            "video_id": vid,
                            "title": desc[:100] if desc else '',
                            "desc": desc[:500],
                            "author": author,
                            "author_id": str(author_id),
                            "like_count": like_count,
                            "comment_count": comment_count,
                            "share_count": share_count,
                            "play_count": play_count,
                            "publish_time": time_str,
                            "url": video_url,
                            "cover": cover,
                            "categories": classify_video(full_text),
                            "sentiment": analyze_sentiment(full_text),
                            "search_keyword": self._current_keyword,
                            "source": "search",
                            "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                        })
            except Exception:
                pass

        # 热榜 API
        elif '/aweme/v1/web/hot/search/' in url or 'hot_search_list' in url:
            try:
                data = await response.json()
                hot_list = data.get('data', {}).get('word_list', [])
                if not hot_list:
                    hot_list = data.get('word_list', [])
                for item in (hot_list if isinstance(hot_list, list) else []):
                    word = item.get('word', '')
                    if word:
                        # 检查是否和支付/金融相关
                        finance_keywords = ['支付', '花呗', '借呗', '放心借', '月付', '抖音', '退款',
                                           '扣费', '分期', '红包', '钱包', '豆包', '金融', '银行']
                        if any(kw in word for kw in finance_keywords):
                            self.api_results_collector.append({
                                "_keyword": "__hot_topic__",
                                "video_id": f"hot_{hash(word) % 10**10}",
                                "title": word,
                                "desc": f"抖音热搜话题: {word}",
                                "author": "抖音热榜",
                                "author_id": "",
                                "like_count": item.get('hot_value', 0),
                                "comment_count": 0,
                                "share_count": 0,
                                "play_count": 0,
                                "publish_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                                "url": f"https://www.douyin.com/search/{quote(word)}",
                                "cover": "",
                                "categories": classify_video(word),
                                "sentiment": analyze_sentiment(word),
                                "search_keyword": "热门话题",
                                "source": "hot_topic",
                                "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                            })
            except Exception:
                pass

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

    async def save_session(self):
        """保存当前 session state（cookie + localStorage）"""
        try:
            state = await self.context.storage_state()
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print(f"  💾 Session 已保存: {SESSION_FILE}")
        except Exception as e:
            print(f"  ⚠️ 保存 session 失败: {e}")

    async def cleanup(self):
        try:
            if self.page:
                self.page.remove_listener("response", self._on_response)
        except: pass
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
# 搜索和数据采集
# =========================================================

async def check_for_captcha(page):
    """检查是否触发验证码或风控"""
    try:
        body_text = await page.evaluate("document.body?.innerText?.slice(0,500) || ''")
        current_url = page.url
        
        # 检查验证码/风控特征
        risk_signals = ['验证', 'captcha', '滑块', '安全验证', '请完成验证', 
                       '访问过于频繁', '请稍后再试', '系统繁忙']
        for signal in risk_signals:
            if signal.lower() in body_text.lower() or signal.lower() in current_url.lower():
                return True
    except Exception:
        pass
    return False


async def search_douyin_keyword(page, keyword, category, max_scrolls, api_results_collector):
    """搜索抖音关键词并通过滚动加载更多结果"""
    all_videos = []
    before_count = len(api_results_collector)
    
    encoded_kw = quote(keyword)
    url = f"https://www.douyin.com/search/{encoded_kw}?type=video"
    
    # 页面加载（带重试）
    page_loaded = False
    for retry in range(3):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page_loaded = True
            break
        except Exception as e:
            err_str = str(e)
            if 'DISCONNECTED' in err_str or 'ERR_INTERNET' in err_str or 'net::' in err_str:
                wait = random.uniform(30, 60)
                print(f"      🔌 网络断开，等待 {wait:.0f}s 后重试 ({retry+1}/3)...")
                await asyncio.sleep(wait)
                continue
            if retry == 2:
                print(f"      ❌ 页面加载失败: {e}")
            break
    
    if not page_loaded:
        print(f"      ❌ 重试3次仍失败，跳过")
        return all_videos
    
    # 等待页面渲染
    await asyncio.sleep(random.uniform(4, 8))
    
    # 检查验证码
    if await check_for_captcha(page):
        print(f"      🛑 触发验证码/风控！立即停止")
        return all_videos
    
    # 模拟滚动浏览（抖音搜索页是瀑布流，滚动触发加载）
    for scroll_round in range(max_scrolls):
        await human_like_scroll(page)
        await human_like_move_mouse(page)
        
        # 随机"走神"暂停
        if random.random() < 0.10:
            extra = random.uniform(15, 30)
            print(f"      ☕ 模拟走神 {extra:.0f}s...")
            await asyncio.sleep(extra)
        
        # 检查是否触发风控
        if await check_for_captcha(page):
            print(f"      🛑 滚动中触发验证码，停止")
            break
        
        # 滚动间等待
        if scroll_round < max_scrolls - 1:
            delay = random.uniform(SCROLL_DELAY_MIN, SCROLL_DELAY_MAX)
            print(f"      ⏳ 滚动等待 {delay:.0f}s (第{scroll_round+1}/{max_scrolls}轮)...")
            await asyncio.sleep(delay)
    
    # 收集 API 拦截到的数据
    new_api_videos = api_results_collector[before_count:]
    keyword_videos = [v for v in new_api_videos if v.get('_keyword') == keyword]
    
    if keyword_videos:
        for item in keyword_videos:
            del item['_keyword']
            all_videos.append(item)
        print(f"      API 拦截: {len(keyword_videos)} 条视频")
    
    # 如果 API 拦截失败，尝试 DOM 解析作为降级
    if not keyword_videos:
        print(f"      API 无数据，尝试 DOM 解析...")
        try:
            # 抖音搜索结果的视频卡片
            video_cards = await page.query_selector_all('[class*="search-result-card"], [class*="video-card"], li[class*="result"]')
            
            for card in video_cards[:20]:  # 最多取20条
                try:
                    # 提取标题/描述
                    title_el = await card.query_selector('[class*="title"], [class*="desc"], a[title]')
                    title = ''
                    if title_el:
                        title = await title_el.inner_text() or await title_el.get_attribute('title') or ''
                    
                    # 提取链接
                    link_el = await card.query_selector('a[href*="/video/"]')
                    video_url = ''
                    vid = ''
                    if link_el:
                        href = await link_el.get_attribute('href') or ''
                        if '/video/' in href:
                            vid_match = re.search(r'/video/(\d+)', href)
                            if vid_match:
                                vid = vid_match.group(1)
                                video_url = f"https://www.douyin.com/video/{vid}"
                    
                    # 提取作者
                    author_el = await card.query_selector('[class*="author"], [class*="nickname"]')
                    author = ''
                    if author_el:
                        author = (await author_el.inner_text()).strip()
                    
                    # 提取互动数据
                    like_el = await card.query_selector('[class*="like"], [class*="digg"]')
                    like_count = 0
                    if like_el:
                        like_text = await like_el.inner_text()
                        like_count = _parse_count(like_text)
                    
                    if title and vid:
                        full_text = title
                        all_videos.append({
                            "video_id": vid,
                            "title": title[:100],
                            "desc": title[:500],
                            "author": author,
                            "author_id": "",
                            "like_count": like_count,
                            "comment_count": 0,
                            "share_count": 0,
                            "play_count": 0,
                            "publish_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                            "url": video_url,
                            "cover": "",
                            "categories": classify_video(full_text),
                            "sentiment": analyze_sentiment(full_text),
                            "search_keyword": keyword,
                            "source": "search_dom",
                            "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                        })
                except Exception:
                    continue
            
            if all_videos:
                print(f"      DOM 解析: {len(all_videos)} 条视频")
        except Exception as e:
            print(f"      DOM 解析失败: {e}")
    
    return all_videos


async def fetch_hot_topics(page, api_results_collector):
    """获取抖音热榜中支付/金融相关的话题"""
    before_count = len(api_results_collector)
    
    print(f"\n  🔥 抓取抖音热榜...")
    
    try:
        await page.goto("https://www.douyin.com/hot", wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(random.uniform(4, 8))
        await human_like_scroll(page)
        await asyncio.sleep(random.uniform(3, 5))
    except Exception as e:
        print(f"    ⚠️ 热榜页面加载异常: {e}")
    
    # 收集 API 拦截到的热搜
    new_items = api_results_collector[before_count:]
    hot_items = [v for v in new_items if v.get('_keyword') == '__hot_topic__']
    
    # 如果 API 拦截没有数据，尝试 DOM 解析
    if not hot_items:
        try:
            hot_cards = await page.query_selector_all('[class*="hot-list"] li, [class*="hot-item"], [class*="trending"]')
            for card in hot_cards[:30]:
                try:
                    text_el = await card.query_selector('[class*="title"], [class*="word"], span')
                    if text_el:
                        word = (await text_el.inner_text()).strip()
                        finance_keywords = ['支付', '花呗', '借呗', '放心借', '月付', '抖音', '退款',
                                          '扣费', '分期', '红包', '钱包', '豆包', '金融', '银行']
                        if any(kw in word for kw in finance_keywords):
                            hot_items.append({
                                "video_id": f"hot_{hash(word) % 10**10}",
                                "title": word,
                                "desc": f"抖音热搜话题: {word}",
                                "author": "抖音热榜",
                                "author_id": "",
                                "like_count": 0,
                                "comment_count": 0,
                                "share_count": 0,
                                "play_count": 0,
                                "publish_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                                "url": f"https://www.douyin.com/search/{quote(word)}",
                                "cover": "",
                                "categories": classify_video(word),
                                "sentiment": analyze_sentiment(word),
                                "search_keyword": "热门话题",
                                "source": "hot_topic",
                                "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                            })
                except Exception:
                    continue
        except Exception:
            pass
    
    # 清理 _keyword 标记
    result = []
    for item in hot_items:
        if '_keyword' in item:
            del item['_keyword']
        result.append(item)
    
    print(f"    📊 发现 {len(result)} 条支付/金融相关热搜")
    return result


def _parse_count(text):
    """解析互动数据文本（如 '1.2万'、'324'）"""
    text = text.strip()
    try:
        if '万' in text:
            return int(float(text.replace('万', '')) * 10000)
        elif '亿' in text:
            return int(float(text.replace('亿', '')) * 100000000)
        else:
            return int(re.sub(r'[^\d]', '', text) or 0)
    except (ValueError, TypeError):
        return 0


def build_output(all_videos):
    """构建输出数据"""
    total_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    category_stats = {}
    source_stats = {"search": 0, "search_dom": 0, "hot_topic": 0}

    for video in all_videos:
        s = video.get("sentiment", "neutral")
        total_sentiment[s] += 1
        for cat in video.get("categories", []):
            category_stats[cat] = category_stats.get(cat, 0) + 1
        source = video.get("source", "search")
        source_stats[source] = source_stats.get(source, 0) + 1

    return {
        "meta": {
            "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "platform": "抖音",
            "total_videos": len(all_videos),
            "sentiment_stats": total_sentiment,
            "category_stats": category_stats,
            "source_stats": source_stats,
            "is_demo": False,
            "data_source": "抖音网页端直接爬取",
        },
        "videos": all_videos
    }


# =========================================================
# 主流程
# =========================================================

async def main():
    parser = argparse.ArgumentParser(description='抖音短视频爬虫 — 支付/金融方向')
    parser.add_argument('--reset', action='store_true', help='重置断点进度，从头开始')
    parser.add_argument('--test', action='store_true', help='测试 cookie/浏览器可用性')
    parser.add_argument('--dry-run', action='store_true', help='只打印计划，不实际爬取')
    parser.add_argument('--login', action='store_true', help='打开浏览器让用户手动登录')
    args = parser.parse_args()

    start_time = datetime.now()
    print("=" * 60)
    print("🎵 抖音短视频爬虫 — 支付/金融方向")
    print(f"📅 {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛡️ 安全模式: Playwright Stealth + headless + 超保守延迟")
    print(f"⏱️ 关键词间隔: {KEYWORD_DELAY_MIN}-{KEYWORD_DELAY_MAX}s")
    print(f"⏱️ 滚动间隔: {SCROLL_DELAY_MIN}-{SCROLL_DELAY_MAX}s")
    print(f"📁 数据文件: {OUTPUT_FILE}")
    print("=" * 60)

    # Dry-run 模式
    if args.dry_run:
        print(f"\n📊 计划: {len(SEARCH_KEYWORDS)} 个关键词 + 热榜")
        for kw, cat, scrolls in SEARCH_KEYWORDS:
            print(f"    {kw} ({cat}, {scrolls}轮滚动)")
        est_minutes = len(SEARCH_KEYWORDS) * 3 + 5
        print(f"\n⏱️ 预计耗时: ~{est_minutes} 分钟 ({est_minutes/60:.1f} 小时)")
        return

    # Step 1: 获取 Cookie
    print("\n🍪 Step 1: 获取抖音 Cookie...")
    douyin_cookies = extract_douyin_cookies()
    has_session = os.path.exists(SESSION_FILE)

    if not douyin_cookies and not has_session:
        if not args.login:
            print("❌ 无法获取抖音 Cookie，也没有保存的 session")
            print("💡 请先运行: python3 crawl_douyin.py --login")
            print("   或在 Chrome 中登录 www.douyin.com 后重试")
            return
    else:
        if has_session:
            print(f"  ✅ 发现已保存的 session 文件")
        if douyin_cookies:
            print(f"  ✅ 从 Chrome 提取了 {len(douyin_cookies)} 条 cookie")

    # --login 模式：打开浏览器让用户手动登录
    if args.login:
        print("\n🌐 打开抖音登录页面，请手动登录...")
        api_collector = []
        mgr = DouyinBrowserManager(douyin_cookies, api_collector)
        try:
            await mgr.start(headless=False)
            print("  📱 请在浏览器中完成登录")
            print("  ⏳ 登录完成后按回车继续...")
            await asyncio.get_event_loop().run_in_executor(None, input)
            await mgr.save_session()
            print("  ✅ 登录成功！session 已保存，后续运行将自动使用")
        finally:
            await mgr.cleanup()
        return

    # Step 2: 断点续爬
    progress = load_progress()
    if args.reset:
        progress = {"completed": [], "last_run": "", "total_runs": 0}
        save_progress(progress)
        print("\n🔄 已重置断点进度")

    completed_set = set(progress.get("completed", []))

    # --test 模式
    if args.test:
        print("\n🧪 测试浏览器和 Cookie...")
        api_collector = []
        mgr = DouyinBrowserManager(douyin_cookies, api_collector)
        try:
            await mgr.start()
            alive = await mgr.is_alive()
            if alive:
                print("  ✅ 浏览器正常!")
                # 尝试访问搜索页
                try:
                    await mgr.page.goto("https://www.douyin.com/search/抖音支付?type=video",
                                       wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(5)
                    if await check_for_captcha(mgr.page):
                        print("  ⚠️ 触发验证码，Cookie 可能已失效")
                    else:
                        print("  ✅ 搜索页面正常，可以开始爬取!")
                except Exception as e:
                    print(f"  ⚠️ 搜索测试异常: {e}")
            else:
                print("  ❌ 浏览器异常")
        finally:
            await mgr.cleanup()
        return

    # Step 3: 加载已有数据
    existing_videos = []
    existing_ids = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            existing_videos = existing_data.get('videos', [])
            existing_ids = {v.get('video_id', '') for v in existing_videos}
            print(f"\n📂 已有数据: {len(existing_videos)} 条视频")
        except Exception:
            pass

    # Step 4: 开始爬取
    api_results_collector = []
    mgr = DouyinBrowserManager(douyin_cookies, api_results_collector)
    all_new_videos = []
    seen_ids = set(existing_ids)
    keywords_done = 0
    hit_captcha = False

    try:
        print("\n🌐 Step 4: 启动 headless 浏览器...")
        await mgr.start()
        print("  ✅ 浏览器就绪\n")

        # 先抓热榜
        hot_videos = await fetch_hot_topics(mgr.page, api_results_collector)
        for v in hot_videos:
            vid = v['video_id']
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                all_new_videos.append(v)
        
        if hot_videos:
            await asyncio.sleep(random.uniform(60, 120))

        # 搜索关键词
        for kw_idx, (keyword, category, max_scrolls) in enumerate(SEARCH_KEYWORDS):
            if keywords_done >= MAX_KEYWORDS_PER_RUN:
                print(f"\n  📋 已达单次运行上限 ({MAX_KEYWORDS_PER_RUN} 个关键词)，安全停止")
                break

            kw_key = keyword
            if kw_key in completed_set:
                print(f"  [{kw_idx+1}/{len(SEARCH_KEYWORDS)}] ⏭️ {keyword} (已完成，跳过)")
                continue

            print(f"\n  [{kw_idx+1}/{len(SEARCH_KEYWORDS)}] 🔍 {keyword} (分类:{category}, {max_scrolls}轮)")

            await mgr.ensure_alive()
            mgr._current_keyword = keyword
            mgr._current_category = category

            try:
                videos = await search_douyin_keyword(
                    mgr.page, keyword, category, max_scrolls, api_results_collector
                )

                new_count = 0
                for video in videos:
                    vid = video['video_id']
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        all_new_videos.append(video)
                        new_count += 1

                keywords_done += 1
                print(f"    ✅ 新增 {new_count} 条 (本轮总 {len(all_new_videos)})")

                # 记录进度
                completed_set.add(kw_key)
                progress["completed"] = list(completed_set)
                progress["last_run"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_progress(progress)

            except Exception as e:
                err_str = str(e)
                if '验证' in err_str or 'captcha' in err_str.lower():
                    print(f"    🛑 触发验证码！立即停止")
                    hit_captcha = True
                    break
                print(f"    ❌ 异常: {e}")
                await mgr.ensure_alive()

            # 定期保存
            if keywords_done % SAVE_EVERY_N_KEYWORDS == 0 and all_new_videos:
                merged = existing_videos + all_new_videos
                output = build_output(merged)
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
                print(f"\n  💾 进度已保存 (新增 {len(all_new_videos)}, 总 {len(merged)} 条)\n")

            # 关键词间等待
            if kw_idx < len(SEARCH_KEYWORDS) - 1:
                delay = random.uniform(KEYWORD_DELAY_MIN, KEYWORD_DELAY_MAX)
                print(f"    ⏳ 安全间隔 {delay:.0f}s...")
                await asyncio.sleep(delay)

        # 保存 session 以备下次使用
        await mgr.save_session()

    finally:
        await mgr.cleanup()

    # Step 5: 保存最终数据
    if all_new_videos:
        merged = existing_videos + all_new_videos
        output = build_output(merged)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n{'=' * 60}")
    print(f"🎉 抖音爬取完成！")
    print(f"{'=' * 60}")
    print(f"  ⏱️ 耗时: {elapsed/60:.1f} 分钟")
    print(f"  📝 本次新增: {len(all_new_videos)} 条")
    print(f"  📁 数据总量: {len(existing_videos) + len(all_new_videos)} 条")
    print(f"  🔑 关键词完成: {keywords_done} 个")

    if hit_captcha:
        print(f"  ⚠️ 因验证码/风控提前停止，下次执行将从断点继续")

    remaining = sum(1 for kw, _, _ in SEARCH_KEYWORDS if kw not in completed_set)
    if remaining > 0:
        print(f"  📋 剩余: {remaining} 个关键词待爬")
    else:
        print(f"  ✅ 全部关键词已爬完！")
        progress["completed"] = []
        progress["total_runs"] = progress.get("total_runs", 0) + 1
        save_progress(progress)

    print(f"\n💾 数据已保存: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
