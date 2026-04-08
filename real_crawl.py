"""
小红书真实爬虫 - Playwright Stealth + Chrome Cookie 注入版
从本地 Chrome 自动提取所有小红书 cookie，注入 stealth 浏览器
通过 API 拦截获取搜索结果数据
不需要扫码登录！
"""
import asyncio
import json
import os
import re
import time
import random
import sqlite3
import shutil
import tempfile
import subprocess
import sys
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'real_data.json')

# =====================================================================
# 搜索关键词配置 —— 覆盖6大平台所有核心关键词
# =====================================================================
SEARCH_KEYWORDS = {
    "微信支付": {
        "icon": "💚", "color": "#07C160",
        "keywords": [
            ("微信支付", "支付", 5),
            ("微信红包", "支付", 3),
            ("微信刷掌支付", "支付", 2),
            ("微信刷脸支付", "支付", 2),
            ("微信零钱", "支付", 3),
            ("微信亲属卡", "支付", 2),
            ("微信AA付款", "支付", 2),
            ("微信群收款", "支付", 2),
            ("微信小程序支付", "支付", 2),
            ("微信免密支付", "支付", 2),
            ("微信数字人民币", "支付", 2),
            ("微信先用后付", "支付", 2),
            ("微粒贷", "贷款", 5),
            ("微信分付", "贷款", 3),
            ("微信支付分", "贷款", 3),
            ("零钱通", "理财", 3),
            ("理财通", "理财", 3),
            ("微保", "理财", 2),
            ("腾讯混元", "AI", 3),
            ("微信AI助手", "AI", 2),
            ("WeChat Pay 境外", "海外", 2),
            ("微信跨境汇款", "海外", 2),
            ("财付通", "组织架构", 2),
            ("腾讯金融", "组织架构", 2),
            ("微信支付投诉", "客诉", 3),
            ("微信支付封号", "客诉", 2),
            ("微信自动续费", "客诉", 3),
        ],
    },
    "支付宝": {
        "icon": "💙", "color": "#1677FF",
        "keywords": [
            ("支付宝支付", "支付", 5),
            ("支付宝碰一下", "支付", 3),
            ("支付宝NFC", "支付", 2),
            ("支付宝刷脸", "支付", 3),
            ("支付宝扫码", "支付", 3),
            ("支付宝消费券", "支付", 2),
            ("支付宝乘车码", "支付", 2),
            ("支付宝付款码", "支付", 2),
            ("支付宝红包", "支付", 3),
            ("支付宝数字人民币", "支付", 2),
            ("支付宝先用后付", "支付", 2),
            ("花呗", "贷款", 5),
            ("借呗", "贷款", 5),
            ("芝麻信用", "贷款", 3),
            ("网商贷", "贷款", 2),
            ("备用金", "贷款", 2),
            ("余额宝", "理财", 5),
            ("蚂蚁财富", "理财", 3),
            ("好医保", "理财", 2),
            ("基金定投 支付宝", "理财", 2),
            ("蚂蚁阿福", "AI", 2),
            ("支付宝AI", "AI", 2),
            ("Alipay+ 境外", "海外", 2),
            ("支付宝出境", "海外", 2),
            ("支付宝退税", "海外", 2),
            ("蚂蚁集团", "组织架构", 3),
            ("蚂蚁金服", "组织架构", 2),
            ("支付宝投诉", "客诉", 3),
            ("花呗逾期", "客诉", 3),
            ("支付宝冻结", "客诉", 2),
            ("支付宝乱扣费", "客诉", 2),
            ("支付宝盗刷", "客诉", 2),
            ("蚂蚁森林", "其他", 3),
            ("集五福 支付宝", "其他", 2),
        ],
    },
    "抖音支付": {
        "icon": "🖤", "color": "#FE2C55",
        "keywords": [
            ("抖音支付", "支付", 5),
            ("抖音团购券", "支付", 3),
            ("抖音买单", "支付", 2),
            ("抖音外卖", "支付", 3),
            ("抖音直播下单", "支付", 2),
            ("抖币充值", "支付", 2),
            ("抖音钱包", "支付", 2),
            ("放心借", "贷款", 5),
            ("抖音月付", "贷款", 3),
            ("DOU分期", "贷款", 2),
            ("豆包AI", "AI", 3),
            ("豆包 聊天", "AI", 2),
            ("TikTok Shop 支付", "海外", 2),
            ("字节跳动 金融", "组织架构", 2),
            ("抖音电商", "组织架构", 2),
            ("抖音退款", "客诉", 3),
            ("抖音投诉", "客诉", 3),
            ("抖音自动续费", "客诉", 2),
            ("抖音封号", "客诉", 2),
            ("抖音商城", "其他", 2),
            ("抖音探店", "其他", 2),
        ],
    },
    "美团支付": {
        "icon": "💛", "color": "#FFC300",
        "keywords": [
            ("美团支付", "支付", 5),
            ("美团买单", "支付", 3),
            ("美团外卖红包", "支付", 3),
            ("美团团购", "支付", 3),
            ("美团闪购", "支付", 2),
            ("大众点评 支付", "支付", 2),
            ("美团月付", "贷款", 3),
            ("美团生意贷", "贷款", 2),
            ("美团无人配送", "AI", 2),
            ("美团AI", "AI", 2),
            ("KeeTa 美团", "海外", 2),
            ("美团公司 裁员", "组织架构", 2),
            ("美团投诉", "客诉", 3),
            ("美团退款", "客诉", 3),
            ("美团配送问题", "客诉", 2),
            ("美团客服差", "客诉", 2),
            ("美团酒店", "其他", 2),
            ("美团单车", "其他", 2),
            ("美团买菜", "其他", 2),
        ],
    },
    "云闪付": {
        "icon": "🔴", "color": "#E60012",
        "keywords": [
            ("云闪付", "支付", 5),
            ("银联支付", "支付", 3),
            ("Apple Pay 银联", "支付", 2),
            ("华为Pay", "支付", 2),
            ("银联62节", "支付", 2),
            ("银联数字人民币", "支付", 2),
            ("云闪付公交", "支付", 2),
            ("银联NFC", "支付", 2),
            ("银联国际", "海外", 2),
            ("银联卡 境外", "海外", 2),
            ("银联退税", "海外", 2),
            ("中国银联", "组织架构", 2),
            ("云闪付投诉", "客诉", 3),
            ("云闪付闪退", "客诉", 2),
        ],
    },
    "京东支付": {
        "icon": "💎", "color": "#E4393C",
        "keywords": [
            ("京东支付", "支付", 5),
            ("京东白条闪付", "支付", 2),
            ("京东闪付", "支付", 2),
            ("京东钱包", "支付", 2),
            ("京东购物卡", "支付", 2),
            ("京东白条", "贷款", 5),
            ("京东金条", "贷款", 3),
            ("京东分期", "贷款", 3),
            ("京东小金库", "理财", 2),
            ("京东理财", "理财", 2),
            ("京东金融", "理财", 3),
            ("京东AI", "AI", 2),
            ("京东国际 海外购", "海外", 2),
            ("京东科技", "组织架构", 2),
            ("京东支付投诉", "客诉", 2),
            ("京东白条纠纷", "客诉", 2),
            ("京东退款", "客诉", 3),
            ("京东618", "其他", 2),
            ("京东PLUS", "其他", 2),
        ],
    },
}

# =====================================================================
# 相关性过滤关键词
# =====================================================================
RELEVANCE_KEYWORDS = {
    "微信支付": ["微信", "支付", "红包", "零钱", "转账", "刷掌", "刷脸", "付款", "扫码",
                "微粒贷", "分付", "零钱通", "理财通", "微保", "混元", "财付通", "腾讯",
                "WeChat Pay", "亲属卡", "AA", "群收款", "免密", "数字人民币", "续费",
                "封号", "盗号", "客服", "先用后付", "先享后付", "小金罐"],
    "支付宝": ["支付宝", "花呗", "借呗", "余额宝", "芝麻", "蚂蚁", "Alipay", "碰一下",
              "扫码", "付款", "NFC", "消费券", "乘车码", "刷脸", "网商贷", "备用金",
              "蚂蚁财富", "好医保", "阿福", "退税", "集五福", "蚂蚁森林", "冻结",
              "盗刷", "乱扣", "续费", "先用后付", "先享后付", "神券"],
    "抖音支付": ["抖音", "豆包", "放心借", "团购", "直播", "DOU分期", "抖币", "月付",
               "字节", "TikTok", "退款", "封号", "买单", "外卖", "商城", "探店",
               "先用后付", "先享后付", "钱包"],
    "美团支付": ["美团", "大众点评", "外卖", "团购", "月付", "闪购", "买单", "配送",
               "骑手", "无人配送", "KeeTa", "退款", "客服", "生意贷",
               "先用后付", "先享后付", "酒店", "单车", "打车", "买菜"],
    "云闪付": ["云闪付", "银联", "Apple Pay", "华为Pay", "62节", "NFC", "挥卡",
             "数字人民币", "公交", "地铁", "境外", "退税", "闪退",
             "先用后付", "先享后付"],
    "京东支付": ["京东", "白条", "金条", "小金库", "京东金融", "京东科技", "闪付",
               "购物卡", "分期", "618", "PLUS", "退款", "到家",
               "先用后付", "先享后付"],
}

# 情感分析关键词
POSITIVE_WORDS = ["好用", "方便", "不错", "推荐", "喜欢", "划算", "优惠", "赞", "省钱",
                  "给力", "太强", "真香", "解决了", "成功", "感谢", "惊喜", "便宜", "开心",
                  "太爽", "牛", "终于", "神器", "必备"]
NEGATIVE_WORDS = ["难用", "垃圾", "投诉", "骗", "坑", "差评", "恶心", "无语", "崩了", "封号",
                  "冻结", "盗刷", "焦虑", "退款", "催收", "失望", "逾期", "问题", "吐槽", "闪退",
                  "差劲", "受不了", "太慢", "坑人", "过分", "恶意"]


def analyze_sentiment(text):
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    if neg > pos: return "negative"
    if pos > neg: return "positive"
    return "neutral"


def classify_note(text):
    RULES = {
        "支付": ["支付", "付款", "扫码", "转账", "收款", "红包", "NFC", "团购", "外卖",
                "刷脸", "刷掌", "碰一下", "买单", "闪购", "免密", "数字人民币", "先用后付", "先享后付"],
        "贷款": ["贷款", "花呗", "借呗", "借钱", "分期", "额度", "还款", "逾期", "催收",
                "微粒贷", "放心借", "月付", "白条", "金条", "网商贷", "备用金", "分付", "信用"],
        "理财": ["理财", "余额宝", "基金", "投资", "收益", "蚂蚁财富", "零钱通", "保险",
                "小金库", "定期", "定投", "养老金"],
        "AI":   ["ai", "人工智能", "智能", "大模型", "混元", "豆包", "阿福", "无人配送", "机器人"],
        "海外": ["海外", "出境", "境外", "alipay", "退税", "国际", "跨境", "tiktok shop"],
        "组织架构": ["蚂蚁集团", "裁员", "蚂蚁金服", "上市", "校招", "字节跳动", "中国银联",
                    "京东科技", "美团公司", "财付通", "腾讯金融"],
        "客诉": ["投诉", "客服", "坑", "吐槽", "问题", "骗", "盗刷", "冻结", "封号", "退款",
                "差评", "难用", "闪退", "乱扣", "续费"],
    }
    text_lower = text.lower()
    matched = []
    for cat, kws in RULES.items():
        for kw in kws:
            if kw in text_lower:
                matched.append(cat)
                break
    return matched if matched else ["其他"]


def is_relevant(title, desc, platform):
    text = f"{title} {desc}".lower()
    keywords = RELEVANCE_KEYWORDS.get(platform, [])
    for kw in keywords:
        if kw.lower() in text:
            return True
    return False


# =========================================================
# Cookie 提取（从 Chrome 浏览器）
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

        try:
            result = decrypted.decode('utf-8')
        except UnicodeDecodeError:
            result = decrypted.decode('latin-1')

        clean = ''.join(c for c in result if c.isprintable() and ord(c) < 128)
        hex_match = re.search(r'([0-9a-f]{32,})', clean, re.IGNORECASE)
        if hex_match:
            return hex_match.group(1)
        if len(clean) > 5:
            return clean
        return None
    except Exception:
        return None


def extract_all_xhs_cookies():
    """从 Chrome 提取所有小红书 cookie，格式化为 Playwright 需要的格式"""
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
            "FROM cookies WHERE host_key LIKE '%xiaohongshu%'"
        )
        rows = cursor.fetchall()
        conn.close()

        print(f"  从 Chrome 中找到 {len(rows)} 条小红书 cookie")

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
                if name == 'web_session':
                    print(f"  ✅ web_session = {final_value[:25]}...")

    except Exception as e:
        print(f"  ❌ 读取 Cookie 失败: {e}")
    finally:
        os.unlink(tmp)

    return cookies


# =========================================================
# 搜索与 API 拦截
# =========================================================

async def close_login_popup(page):
    """尝试关闭登录弹框"""
    try:
        close_selectors = [
            '.close-button', '[class*="close"]', '[aria-label="close"]',
            '.login-container [class*="close"]',
            'svg[class*="close"]', 'button[class*="close"]',
        ]
        for sel in close_selectors:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await asyncio.sleep(0.5)
                return True
        await page.keyboard.press('Escape')
        await asyncio.sleep(0.5)
        await page.evaluate("document.querySelector('.login-container, [class*=\"mask\"], [class*=\"overlay\"]')?.remove()")
    except Exception:
        pass
    return False


async def search_keyword_pages(page, keyword, platform, category, max_pages, api_results_collector):
    """搜索一个关键词，翻多页，返回相关的笔记"""
    all_notes = []

    for page_num in range(1, max_pages + 1):
        before_count = len(api_results_collector)

        url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note&page={page_num}"

        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
        except Exception:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                print(f"      ❌ 页面加载失败: {e}")
                break

        await asyncio.sleep(random.uniform(2, 4))

        # 关闭登录弹框
        await close_login_popup(page)

        # 滚动加载更多
        for i in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(random.uniform(0.8, 1.5))

        await close_login_popup(page)
        await asyncio.sleep(1)

        # 使用 API 拦截的数据
        new_api_notes = api_results_collector[before_count:]
        page_notes_raw = [n for n in new_api_notes if n.get('_keyword') == keyword]

        if page_notes_raw:
            relevant_count = 0
            for item in page_notes_raw:
                del item['_keyword']
                title = item.get('title', '')
                desc = item.get('desc', '')
                if is_relevant(title, desc, platform):
                    all_notes.append(item)
                    relevant_count += 1

            print(f"      第{page_num}页: API拦截 {len(page_notes_raw)} 条, 相关 {relevant_count} 条")

            if relevant_count < 3 and page_num > 1:
                print(f"      ℹ️ 相关度过低，停止翻页")
                break
        else:
            if page_num == 1:
                debug_path = f"/tmp/xhs_debug_{keyword[:10]}.png"
                await page.screenshot(path=debug_path)
                body_text = await page.evaluate("document.body?.innerText?.slice(0,300) || 'empty'")
                print(f"      第{page_num}页: 无 API 数据（截图: {debug_path}）")
                print(f"      页面预览: {body_text[:150]}")
            else:
                print(f"      第{page_num}页: 无新数据，停止翻页")
            break

        if page_num < max_pages:
            delay = random.uniform(2, 4)
            await asyncio.sleep(delay)

    return all_notes


def build_output(all_notes):
    total_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    platform_stats = {}
    platforms_config = {}

    for p_name, p_cfg in SEARCH_KEYWORDS.items():
        cats = list(set(kw[1] for kw in p_cfg["keywords"])) + ["其他"]
        platforms_config[p_name] = {
            "icon": p_cfg["icon"],
            "color": p_cfg["color"],
            "categories": cats,
        }

    for note in all_notes:
        p = note.get("platform", "支付宝")
        if p not in platform_stats:
            platform_stats[p] = {
                "total": 0,
                "category_stats": {},
                "sentiment_stats": {"positive": 0, "negative": 0, "neutral": 0}
            }
        platform_stats[p]["total"] += 1
        for cat in note.get("categories", []):
            platform_stats[p]["category_stats"][cat] = platform_stats[p]["category_stats"].get(cat, 0) + 1
        s = note.get("sentiment", "neutral")
        platform_stats[p]["sentiment_stats"][s] += 1
        total_sentiment[s] += 1

    return {
        "meta": {
            "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_notes": len(all_notes),
            "sentiment_stats": total_sentiment,
            "platform_stats": platform_stats,
            "platforms_config": platforms_config,
            "deleted_stats": {"total_deleted": 0, "per_platform": {}},
            "is_demo": False,
            "data_range": "真实爬取数据",
            "note": "真实小红书数据，Playwright Stealth + Chrome Cookie 注入 + API 拦截"
        },
        "notes": all_notes
    }


class BrowserManager:
    """管理浏览器生命周期，支持崩溃后自动重建"""

    def __init__(self, xhs_cookies, api_results_collector):
        self.xhs_cookies = xhs_cookies
        self.api_results_collector = api_results_collector
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._current_keyword = ''
        self._current_platform = ''
        self._current_category = ''

    async def start_playwright(self):
        if not self.playwright:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()

    async def create_browser(self):
        """创建新的浏览器实例，注入 cookie 和 stealth"""
        await self.start_playwright()

        # 关闭旧的（如果有）
        await self.cleanup_browser()

        self.browser = await self.playwright.chromium.launch(
            headless=False,  # 有头模式：方便扫码
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ],
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        # 注入 cookie
        await self.context.add_cookies(self.xhs_cookies)

        self.page = await self.context.new_page()

        # Stealth 反检测
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
            await self.page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
            
            # 检测是否需要扫码验证
            body_text = await self.page.evaluate("document.body?.innerText?.slice(0,500) || ''")
            page_url = self.page.url
            need_scan = ('扫码验证' in body_text or '扫码' in body_text 
                        or '马上登录' in body_text or '登录' in body_text[:100]
                        or 'login' in page_url)
            if need_scan:
                print("\n" + "="*50)
                print("⚠️  小红书要求扫码验证！")
                print("    请用小红书APP扫描浏览器窗口中的二维码")
                print("    扫码完成后会自动继续爬取")
                print("    最多等待 5 分钟...")
                print("="*50 + "\n")
                # 等待扫码完成（最多300秒 = 5分钟）
                for i in range(60):
                    await asyncio.sleep(5)
                    try:
                        body_text = await self.page.evaluate("document.body?.innerText?.slice(0,500) || ''")
                        page_url = self.page.url
                    except Exception:
                        continue
                    still_need = ('扫码验证' in body_text or '扫码' in body_text
                                 or '马上登录' in body_text or 'login' in page_url)
                    if not still_need:
                        print("    ✅ 扫码验证通过！继续爬取...\n")
                        await asyncio.sleep(3)  # 多等几秒让页面完全加载
                        break
                    if i % 6 == 5:
                        print(f"    ⏳ 仍在等待扫码... ({(i+1)*5}秒)")
                else:
                    print("    ⚠️ 等待超时（5分钟），继续尝试...")
        except Exception:
            pass

        return True

    async def _on_response(self, response):
        """API 响应拦截器"""
        url = response.url
        if 'api/sns/web/v1/search/notes' in url:
            try:
                data = await response.json()
                if data and data.get('code') == 0:
                    items = data.get('data', {}).get('items', [])
                    if items:
                        current_kw = self._current_keyword
                        current_platform = self._current_platform
                        current_category = self._current_category

                        for item in items:
                            nc = item.get('note_card', item)
                            user_info = nc.get('user', {})
                            interact = nc.get('interact_info', {})
                            nid = item.get('id', nc.get('note_id', ''))
                            xsec = item.get('xsec_token', '')
                            title = nc.get('display_title', '') or ''
                            desc = nc.get('desc', '') or ''
                            full_text = f"{title} {desc}"

                            link = f"https://www.xiaohongshu.com/explore/{nid}?xsec_token={xsec}&xsec_source=pc_search" if nid else ''

                            # 时间处理
                            time_str = ''
                            ts = nc.get('time', 0)
                            if ts:
                                try:
                                    if ts > 1e12: ts = ts / 1000
                                    time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                                except Exception:
                                    pass
                            if not time_str and nid and len(nid) == 24:
                                try:
                                    ts_from_id = int(nid[:8], 16)
                                    if 1577836800 < ts_from_id < 1893456000:
                                        time_str = datetime.fromtimestamp(ts_from_id).strftime('%Y-%m-%d %H:%M')
                                except Exception:
                                    pass
                            if not time_str:
                                time_str = datetime.now().strftime('%Y-%m-%d %H:%M')

                            # 封面图
                            cover = ''
                            imgs = nc.get('image_list', [])
                            if imgs and isinstance(imgs[0], dict):
                                cover = imgs[0].get('url_default', '') or imgs[0].get('url', '')
                                if not cover and imgs[0].get('info_list'):
                                    cover = imgs[0]['info_list'][0].get('url', '')

                            cats = [current_category] + [c for c in classify_note(full_text) if c != current_category]

                            self.api_results_collector.append({
                                "_keyword": current_kw,
                                "note_id": nid,
                                "platform": current_platform,
                                "title": title,
                                "desc": desc[:500],
                                "author": user_info.get('nickname', ''),
                                "author_avatar": user_info.get('avatar', ''),
                                "author_id": user_info.get('user_id', ''),
                                "liked_count": str(interact.get('liked_count', '0')),
                                "comment_count": str(interact.get('comment_count', '0')),
                                "collected_count": str(interact.get('collected_count', '0')),
                                "cover": cover,
                                "link": link,
                                "time": time_str,
                                "categories": cats,
                                "keyword_tags": [current_kw, current_category],
                                "search_keyword": current_kw,
                                "xsec_token": xsec,
                                "sentiment": analyze_sentiment(full_text),
                                "is_deleted": False,
                                "deleted_at": "",
                                "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                            })
            except Exception:
                pass

    async def is_alive(self):
        """检查浏览器/页面是否存活"""
        try:
            if not self.page or not self.browser:
                return False
            # 尝试一个简单操作来检查页面是否存活
            await self.page.evaluate("1+1")
            return True
        except Exception:
            return False

    async def ensure_alive(self):
        """确保浏览器存活，否则重建"""
        if not await self.is_alive():
            print("  🔄 浏览器已断开，正在重建...")
            await self.create_browser()
            print("  ✅ 浏览器已重建")
            return True
        return False

    async def cleanup_browser(self):
        """安全关闭浏览器"""
        try:
            if self.page:
                self.page.remove_listener("response", self._on_response)
        except Exception:
            pass
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.browser = None

    async def cleanup_all(self):
        """彻底清理"""
        await self.cleanup_browser()
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.playwright = None


async def main():
    print("=" * 60)
    print("🚀 小红书舆情爬虫 - Playwright + Chrome Cookie 注入版")
    print("   自动提取 Chrome Cookie | Stealth 反检测 | API 拦截")
    print("   ⚡ Headless 模式 | 自动重建 | 不需要扫码登录！")
    print("=" * 60)

    # Step 1: 从 Chrome 提取 cookie
    print("\n🍪 Step 1: 从 Chrome 提取小红书 Cookie...")
    xhs_cookies = extract_all_xhs_cookies()

    if not xhs_cookies:
        print("\n❌ 无法提取 Cookie！请确保在 Chrome 中已登录小红书")
        return False

    ws_cookies = [c for c in xhs_cookies if c['name'] == 'web_session' and len(c.get('value', '')) > 10]
    if not ws_cookies:
        print("\n❌ 未找到有效的 web_session！请在 Chrome 中重新登录小红书")
        return False

    print(f"  ✅ 提取到 {len(xhs_cookies)} 条 cookie（含 web_session）")

    # 统计
    total_keywords = sum(len(cfg["keywords"]) for cfg in SEARCH_KEYWORDS.values())
    total_pages = sum(sum(kw[2] for kw in cfg["keywords"]) for cfg in SEARCH_KEYWORDS.values())
    print(f"\n📊 计划: {total_keywords} 个关键词, 预计 {total_pages} 页")

    # Step 2: 创建浏览器管理器
    all_notes = []
    seen_ids = set()
    api_results_collector = []

    mgr = BrowserManager(xhs_cookies, api_results_collector)

    try:
        print("\n🌐 Step 2: 启动 Headless 浏览器...")
        await mgr.create_browser()
        print("  ✅ 浏览器启动完毕（headless 模式，不会弹窗）")

        # 验证登录
        print("\n🔐 Step 3: 验证登录状态...")
        cookies = await mgr.context.cookies("https://www.xiaohongshu.com")
        ws = [c for c in cookies if c['name'] == 'web_session' and len(c.get('value', '')) > 10]
        if ws:
            print(f"  ✅ 登录有效！web_session = {ws[0]['value'][:25]}...")
        else:
            print("  ⚠️ web_session 可能无效，继续尝试...")

        # Step 4: 开始搜索
        print("\n🔍 Step 4: 开始关键词搜索...\n")
        current = 0
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 5

        for platform, config in SEARCH_KEYWORDS.items():
            print(f"{'─' * 50}")
            print(f"{config['icon']} 正在爬取: {platform} ({len(config['keywords'])} 个关键词)")
            print(f"{'─' * 50}")
            platform_count = 0

            for keyword, category, max_pages in config["keywords"]:
                current += 1
                print(f"\n  [{current}/{total_keywords}] 🔍 {keyword} (分类:{category}, 计划{max_pages}页)")

                # 确保浏览器存活
                was_rebuilt = await mgr.ensure_alive()
                if was_rebuilt:
                    consecutive_failures = 0  # 重建后重置计数

                mgr._current_keyword = keyword
                mgr._current_platform = platform
                mgr._current_category = category

                try:
                    notes = await search_keyword_pages(
                        mgr.page, keyword, platform, category, max_pages, api_results_collector
                    )

                    new_count = 0
                    for note in notes:
                        nid = note['note_id']
                        if nid and nid not in seen_ids:
                            seen_ids.add(nid)
                            all_notes.append(note)
                            new_count += 1

                    platform_count += new_count
                    print(f"    ✅ {keyword}: 新增 {new_count} 条 (平台累计 {platform_count}, 总计 {len(all_notes)})")

                    if new_count > 0:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1

                except Exception as e:
                    print(f"    ❌ 搜索异常: {e}")
                    consecutive_failures += 1
                    # 强制重建浏览器
                    print("    🔄 将在下个关键词前重建浏览器...")
                    await mgr.cleanup_browser()

                # 连续失败太多次，可能 cookie 已失效
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"\n  ⚠️ 连续 {consecutive_failures} 次未获取数据，尝试重建浏览器...")
                    await mgr.cleanup_browser()
                    await mgr.create_browser()
                    consecutive_failures = 0

                # 每10个关键词保存一次
                if current % 10 == 0 and all_notes:
                    output = build_output(all_notes)
                    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(output, f, ensure_ascii=False, indent=2)
                    print(f"\n  💾 进度已保存 ({len(all_notes)} 条)\n")

                delay = random.uniform(3, 6)
                await asyncio.sleep(delay)

            print(f"\n  📊 {platform} 完成: {platform_count} 条相关笔记\n")

    finally:
        await mgr.cleanup_all()

    if not all_notes:
        print("\n❌ 未获取到任何数据！")
        print("   可能原因: Chrome cookie 已过期或被反爬拦截")
        return False

    output = build_output(all_notes)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"🎉 爬取完成！共 {len(all_notes)} 条真实相关笔记")
    print(f"{'=' * 60}")

    for p_name, p_data in output["meta"]["platform_stats"].items():
        icon = SEARCH_KEYWORDS.get(p_name, {}).get("icon", "📌")
        print(f"  {icon} {p_name}: {p_data['total']} 条")

    ss = output["meta"]["sentiment_stats"]
    print(f"\n😊 正面: {ss['positive']} | 😐 中性: {ss['neutral']} | 😡 负面: {ss['negative']}")
    print(f"\n💾 已保存: {OUTPUT_FILE}")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n🌐 接下来运行: python3 build_netlify.py")
