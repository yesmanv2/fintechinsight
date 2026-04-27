#!/usr/bin/env python3
"""
月度全量爬虫 - 6大支付平台
===============================================
微信支付 / 支付宝 / 抖音支付 / 云闪付 / 美团支付 / 京东支付

每月执行一次，6个平台全量爬取

安全策略（极致模拟真人，宁可慢也绝不被封）:
  1. Playwright Stealth + Chrome Cookie 注入（和你平时浏览器一模一样）
  2. headless=True 无头模式，不弹窗不闪烁
  3. 关键词间隔 90-180 秒（1.5-3分钟，模拟人搜索下一个词）
  4. 翻页间隔 25-45 秒（模拟人仔细浏览一页内容）
  5. 每页随机滚动 4-8 次，停顿 1.5-4 秒，模拟真人阅读
  6. 平台切换间休息 180-360 秒（3-6分钟，模拟人休息）
  7. 随机"走神"暂停（10%概率额外等 15-30 秒，模拟看手机/喝水）
  8. 遇到 461 / 异常立即停止，已爬数据自动保存
  9. 断点续爬：记录已完成的关键词，下次从断点继续
  10. 每爬完 5 个关键词自动保存一次数据（防崩溃丢失）

预计耗时: 约 12-16 小时（全量 ~198 个关键词，不急，稳为主）
使用方式:
    python3 crawl_all.py                         # 正常执行（从断点续爬）
    python3 crawl_all.py --reset                 # 重置进度从头开始
    python3 crawl_all.py --test                  # 仅测试 cookie/浏览器是否可用
    python3 crawl_all.py --dry-run               # 只打印计划，不实际爬取
    python3 crawl_all.py --only "美团支付,京东支付"  # 只爬指定平台
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

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
except ImportError:
    print("❌ 需要安装: pip install playwright playwright-stealth")
    print("   然后运行: playwright install chromium")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'real_data.json')
PROGRESS_FILE = os.path.join(BASE_DIR, '.crawl_all_progress.json')

# =====================================================================
# 🛡️ 安全配置 —— 极致模拟真人，宁可慢也不能被封！
# =====================================================================
KEYWORD_DELAY_MIN = 90          # 关键词间最小等待：1.5分钟
KEYWORD_DELAY_MAX = 180         # 关键词间最大等待：3分钟
PAGE_DELAY_MIN = 25             # 翻页最小等待：25秒
PAGE_DELAY_MAX = 45             # 翻页最大等待：45秒
PLATFORM_SWITCH_DELAY_MIN = 180 # 平台切换最小等待：3分钟
PLATFORM_SWITCH_DELAY_MAX = 360 # 平台切换最大等待：6分钟
SCROLL_TIMES_MIN = 4            # 每页最少滚动次数
SCROLL_TIMES_MAX = 8            # 每页最多滚动次数
SCROLL_PAUSE_MIN = 1.5          # 滚动间最小停顿
SCROLL_PAUSE_MAX = 4.0          # 滚动间最大停顿
SAVE_EVERY_N_KEYWORDS = 5       # 每5个关键词保存一次
MAX_CONSECUTIVE_EMPTY = 3       # 连续3个关键词无数据就重建浏览器
# =====================================================================

# 6大平台 —— 按顺序爬取
ALL_PLATFORMS = ["微信支付", "支付宝", "抖音支付", "云闪付", "美团支付", "京东支付"]

# =====================================================================
# 完整关键词配置（合并 crawl_friday + crawl_tuesday）
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
            ("微信转账", "支付", 3),
            ("微信收款码", "支付", 2),
            ("微信支付商家", "支付", 2),
            ("微信乘车码", "支付", 2),
            ("微信消费券", "支付", 2),
            ("微信支付分先享后付", "支付", 2),
            ("微信商家券", "支付", 2),
            ("微粒贷", "贷款", 5),
            ("微信分付", "贷款", 3),
            ("微信支付分", "贷款", 3),
            ("零钱通", "理财", 3),
            ("理财通", "理财", 3),
            ("微保", "理财", 2),
            ("微信小金罐", "理财", 2),
            ("微信保险", "理财", 2),
            ("腾讯混元", "AI", 3),
            ("微信AI助手", "AI", 2),
            ("微信AI支付", "AI", 2),
            ("腾讯元宝", "AI", 2),
            ("WeChat Pay 境外", "海外", 2),
            ("微信跨境汇款", "海外", 2),
            ("微信支付境外", "海外", 2),
            ("财付通", "组织架构", 2),
            ("腾讯金融", "组织架构", 2),
            ("微信支付投诉", "客诉", 3),
            ("微信支付封号", "客诉", 2),
            ("微信自动续费", "客诉", 3),
            ("微信支付乱扣费", "客诉", 2),
            ("微信支付盗刷", "客诉", 2),
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
            ("支付宝转账", "支付", 3),
            ("支付宝收款码", "支付", 2),
            ("支付宝免密支付", "支付", 2),
            ("支付宝亲情卡", "支付", 2),
            ("支付宝神券节", "支付", 2),
            ("花呗", "贷款", 5),
            ("借呗", "贷款", 5),
            ("芝麻信用", "贷款", 3),
            ("网商贷", "贷款", 2),
            ("备用金", "贷款", 2),
            ("花呗分期", "贷款", 3),
            ("花呗套现", "客诉", 2),
            ("余额宝", "理财", 5),
            ("蚂蚁财富", "理财", 3),
            ("好医保", "理财", 2),
            ("基金定投 支付宝", "理财", 2),
            ("支付宝理财", "理财", 2),
            ("支付宝保险", "理财", 2),
            ("蚂蚁阿福", "AI", 2),
            ("支付宝AI", "AI", 2),
            ("Alipay+ 境外", "海外", 2),
            ("支付宝出境", "海外", 2),
            ("支付宝退税", "海外", 2),
            ("支付宝海外版", "海外", 2),
            ("蚂蚁集团", "组织架构", 3),
            ("蚂蚁金服", "组织架构", 2),
            ("支付宝投诉", "客诉", 3),
            ("花呗逾期", "客诉", 3),
            ("支付宝冻结", "客诉", 2),
            ("支付宝乱扣费", "客诉", 2),
            ("支付宝盗刷", "客诉", 2),
            ("支付宝自动续费", "客诉", 2),
            ("支付宝扣款", "客诉", 2),
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
            ("抖音支付优惠", "支付", 2),
            ("抖音先用后付", "支付", 2),
            ("抖音零钱", "支付", 2),
            ("抖音红包", "支付", 2),
            ("放心借", "贷款", 5),
            ("抖音月付", "贷款", 3),
            ("DOU分期", "贷款", 2),
            ("放心借利息", "贷款", 2),
            ("抖音借钱", "贷款", 2),
            ("豆包AI", "AI", 3),
            ("豆包 聊天", "AI", 2),
            ("豆包AI搜索", "AI", 2),
            ("TikTok Shop 支付", "海外", 2),
            ("字节跳动 金融", "组织架构", 2),
            ("抖音电商", "组织架构", 2),
            ("字节跳动 裁员", "组织架构", 2),
            ("抖音退款", "客诉", 3),
            ("抖音投诉", "客诉", 3),
            ("抖音自动续费", "客诉", 2),
            ("抖音封号", "客诉", 2),
            ("抖音乱扣费", "客诉", 2),
            ("抖音盗号", "客诉", 2),
            ("抖音商城", "其他", 2),
            ("抖音探店", "其他", 2),
            ("抖音超市", "其他", 2),
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
            ("云闪付红包", "支付", 2),
            ("云闪付优惠", "支付", 3),
            ("云闪付乘车码", "支付", 2),
            ("银联闪付", "支付", 2),
            ("银联刷卡", "支付", 2),
            ("云闪付转账", "支付", 2),
            ("银联云支付", "支付", 2),
            ("银联国际", "海外", 2),
            ("银联卡 境外", "海外", 2),
            ("银联退税", "海外", 2),
            ("中国银联", "组织架构", 2),
            ("云闪付投诉", "客诉", 3),
            ("云闪付闪退", "客诉", 2),
            ("云闪付难用", "客诉", 2),
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
            ("美团红包", "支付", 2),
            ("美团优选", "支付", 2),
            ("美团先用后付", "支付", 2),
            ("美团免密支付", "支付", 2),
            ("美团月付", "贷款", 3),
            ("美团生意贷", "贷款", 2),
            ("美团借钱", "贷款", 2),
            ("KeeTa 美团", "海外", 2),
            ("美团投诉", "客诉", 3),
            ("美团退款", "客诉", 3),
            ("美团乱扣费", "客诉", 2),
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
            ("京东红包", "支付", 2),
            ("京东支付优惠", "支付", 2),
            ("京东先用后付", "支付", 2),
            ("京东白条", "贷款", 5),
            ("京东金条", "贷款", 3),
            ("京东分期", "贷款", 3),
            ("京东免息", "贷款", 2),
            ("白条逾期", "客诉", 3),
            ("京东小金库", "理财", 2),
            ("京东理财", "理财", 2),
            ("京东金融", "理财", 3),
            ("京东AI", "AI", 2),
            ("京东国际 海外购", "海外", 2),
            ("京东科技", "组织架构", 2),
            ("京东支付投诉", "客诉", 2),
            ("京东白条纠纷", "客诉", 2),
            ("京东退款", "客诉", 3),
            ("京东金融骗局", "客诉", 2),
            ("京东618", "其他", 2),
            ("京东PLUS", "其他", 2),
            ("京东到家", "其他", 2),
            ("京东双11", "其他", 2),
        ],
    },
}

# =====================================================================
# 相关性过滤关键词（合并）
# =====================================================================
RELEVANCE_KEYWORDS = {
    "微信支付": ["微信", "支付", "红包", "零钱", "转账", "刷掌", "刷脸", "付款", "扫码",
                "微粒贷", "分付", "零钱通", "理财通", "微保", "混元", "财付通", "腾讯",
                "WeChat Pay", "亲属卡", "AA", "群收款", "免密", "数字人民币", "续费",
                "封号", "盗号", "客服", "先用后付", "先享后付", "小金罐", "收款码",
                "乘车码", "消费券", "商家券", "元宝", "AI支付", "境外", "乱扣", "盗刷",
                "保险", "商家"],
    "支付宝": ["支付宝", "花呗", "借呗", "余额宝", "芝麻", "蚂蚁", "Alipay", "碰一下",
              "扫码", "付款", "NFC", "消费券", "乘车码", "刷脸", "网商贷", "备用金",
              "蚂蚁财富", "好医保", "阿福", "退税", "集五福", "蚂蚁森林", "冻结",
              "盗刷", "乱扣", "续费", "先用后付", "先享后付", "神券", "转账", "收款码",
              "免密", "亲情卡", "分期", "套现", "理财", "保险", "海外版", "扣款",
              "自动续费"],
    "抖音支付": ["抖音", "豆包", "放心借", "团购", "直播", "DOU分期", "抖币", "月付",
               "字节", "TikTok", "退款", "封号", "买单", "外卖", "商城", "探店",
               "先用后付", "先享后付", "钱包", "优惠", "零钱", "红包", "利息",
               "借钱", "AI搜索", "裁员", "乱扣", "盗号", "超市"],
    "美团支付": ["美团", "大众点评", "外卖", "团购", "月付", "闪购", "买单", "配送",
               "骑手", "无人配送", "KeeTa", "退款", "客服", "生意贷",
               "先用后付", "先享后付", "酒店", "单车", "打车", "买菜", "红包",
               "优选", "免密", "借钱", "乱扣", "保险", "商家"],
    "云闪付": ["云闪付", "银联", "Apple Pay", "华为Pay", "62节", "NFC", "挥卡",
             "数字人民币", "公交", "地铁", "境外", "退税", "闪退",
             "先用后付", "先享后付", "红包", "优惠", "乘车码", "闪付",
             "刷卡", "转账", "云支付", "难用"],
    "京东支付": ["京东", "白条", "金条", "小金库", "京东金融", "京东科技", "闪付",
               "购物卡", "分期", "618", "PLUS", "退款", "到家",
               "先用后付", "先享后付", "红包", "优惠", "免息", "逾期",
               "骗局", "双11"],
}

# =====================================================================
# 情感分析词（合并取并集）
# =====================================================================
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
                "微粒贷", "放心借", "月付", "白条", "金条", "网商贷", "备用金", "分付", "信用", "生意贷"],
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
    return any(kw.lower() in text for kw in keywords)


# =========================================================
# Chrome Cookie 提取
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
        # 跳过前面的非ASCII垃圾字节
        if len(decrypted) > 16:
            first_block = decrypted[:16]
            try:
                first_block.decode('ascii')
                first_printable = all(c >= 32 and c < 127 for c in first_block)
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


def extract_all_xhs_cookies():
    """从 Chrome 提取所有小红书 cookie"""
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
        for host, name, value, enc_val, path, secure, httponly, samesite, expires in rows:
            final_value = value
            if not final_value and enc_val:
                decrypted = decrypt_chromium_cookie(enc_val, key_password)
                if decrypted:
                    final_value = decrypted
            if final_value:
                ss_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
                cookie = {
                    "name": name, "value": final_value,
                    "domain": host if host.startswith('.') else f".{host.lstrip('.')}",
                    "path": path or "/", "secure": bool(secure),
                    "httpOnly": bool(httponly), "sameSite": ss_map.get(samesite, "Lax"),
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
    try:
        x = random.randint(200, 1200)
        y = random.randint(200, 700)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
    except Exception:
        pass


async def human_browse_note_detail(page):
    """随机点进一个笔记详情页，浏览几秒后返回 —— 模拟真人好奇点击行为"""
    try:
        # 找搜索结果中的笔记链接
        note_links = await page.query_selector_all('a[href*="/explore/"], a[href*="/discovery/item/"], section.note-item a, div[class*="note"] a[href*="/search_result/"]')
        if not note_links:
            note_links = await page.query_selector_all('a[href*="xhslink"], div[class*="note-item"], section[class*="note"]')
        if not note_links or len(note_links) == 0:
            return
        # 随机选一个
        target = random.choice(note_links[:min(8, len(note_links))])
        # 先滚动到它附近
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        # 悬停
        await target.hover()
        await asyncio.sleep(random.uniform(0.3, 0.8))
        # 点击
        await target.click()
        await asyncio.sleep(random.uniform(3, 8))  # 在详情页停留3-8秒，模拟阅读
        # 在详情页滚动一下
        for _ in range(random.randint(1, 3)):
            await page.evaluate(f"window.scrollBy(0, {random.randint(100, 400)})")
            await asyncio.sleep(random.uniform(1, 2.5))
        # 返回
        await page.go_back(timeout=10000)
        await asyncio.sleep(random.uniform(1, 3))
        print(f"        👀 模拟浏览笔记详情后返回")
    except Exception:
        # 如果点击导致页面跳转异常，尝试返回
        try:
            await page.go_back(timeout=5000)
            await asyncio.sleep(1)
        except Exception:
            pass


async def human_browse_profile(page):
    """随机点进一个用户主页，浏览几秒后返回 —— 模拟真人查看作者"""
    try:
        # 找用户头像或名字链接
        profile_links = await page.query_selector_all('a[href*="/user/profile/"], a[class*="author"], span[class*="author"], div[class*="author"] a')
        if not profile_links:
            profile_links = await page.query_selector_all('a[href*="/user/"]')
        if not profile_links or len(profile_links) == 0:
            return
        target = random.choice(profile_links[:min(5, len(profile_links))])
        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.3, 1.0))
        await target.hover()
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await target.click()
        await asyncio.sleep(random.uniform(3, 6))  # 在主页停留3-6秒
        # 在主页滚动
        for _ in range(random.randint(1, 2)):
            await page.evaluate(f"window.scrollBy(0, {random.randint(150, 350)})")
            await asyncio.sleep(random.uniform(0.8, 2.0))
        # 返回
        await page.go_back(timeout=10000)
        await asyncio.sleep(random.uniform(1, 2))
        print(f"        👤 模拟浏览用户主页后返回")
    except Exception:
        try:
            await page.go_back(timeout=5000)
            await asyncio.sleep(1)
        except Exception:
            pass


async def close_login_popup(page):
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


# =========================================================
# 搜索与 API 拦截
# =========================================================

async def search_keyword_pages(page, keyword, platform, category, max_pages, api_results_collector):
    """搜索一个关键词，翻多页，返回相关笔记"""
    all_notes = []
    for page_num in range(1, max_pages + 1):
        before_count = len(api_results_collector)
        url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note&page={page_num}"

        # 断网重试逻辑：最多重试3次
        page_loaded = False
        for retry in range(3):
            try:
                await page.goto(url, wait_until="networkidle", timeout=20000)
                page_loaded = True
                break
            except Exception:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    page_loaded = True
                    break
                except Exception as e:
                    err_str = str(e)
                    if '461' in err_str:
                        print(f"      🛑 触发 461 反爬！立即停止")
                        return all_notes
                    if 'DISCONNECTED' in err_str or 'ERR_INTERNET' in err_str or 'net::' in err_str:
                        wait = random.uniform(30, 60)
                        print(f"      🔌 网络断开，等待 {wait:.0f}s 后重试 ({retry+1}/3)...")
                        await asyncio.sleep(wait)
                        continue
                    print(f"      ❌ 页面加载失败: {e}")
                    break
        if not page_loaded:
            print(f"      ❌ 重试3次仍失败，跳过此关键词")
            break

        await asyncio.sleep(random.uniform(3, 7))
        await close_login_popup(page)
        await asyncio.sleep(random.uniform(1, 3))
        await human_like_scroll(page)
        await human_like_move_mouse(page)

        # 随机点进笔记详情浏览后返回（30%概率）
        if random.random() < 0.30:
            await human_browse_note_detail(page)

        # 随机点进用户主页浏览后返回（15%概率）
        if random.random() < 0.15:
            await human_browse_profile(page)

        # 随机"走神"暂停
        if random.random() < 0.10:
            extra = random.uniform(15, 30)
            print(f"      ☕ 模拟走神 {extra:.0f}s...")
            await asyncio.sleep(extra)

        await close_login_popup(page)
        await asyncio.sleep(random.uniform(1, 3))

        # 检查 461
        try:
            body_text = await page.evaluate("document.body?.innerText?.slice(0,200) || ''")
            if '461' in body_text or '异常' in body_text[:50]:
                print(f"      🛑 页面检测到 461 异常，立即停止")
                return all_notes
        except Exception:
            pass

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
            print(f"      第{page_num}页: 拦截 {len(page_notes_raw)} 条, 相关 {relevant_count} 条")
            if relevant_count < 2 and page_num > 1:
                print(f"      ℹ️ 相关度过低，停止翻页")
                break
        else:
            # 无API数据 — 多级重试策略
            if page_num == 1:
                got_data = False
                # 第一级：reload 重试（最多2次）
                for reload_attempt in range(2):
                    wait_time = random.uniform(8, 15) * (reload_attempt + 1)
                    print(f"      第{page_num}页: 无 API 数据，等待 {wait_time:.0f}s 后 reload 重试 ({reload_attempt+1}/2)...")
                    await asyncio.sleep(wait_time)
                    retry_before = len(api_results_collector)
                    try:
                        await page.reload(wait_until="networkidle", timeout=20000)
                    except Exception:
                        try:
                            await page.reload(wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                    await asyncio.sleep(random.uniform(5, 10))
                    await human_like_scroll(page)
                    await asyncio.sleep(random.uniform(3, 5))
                    retry_notes = api_results_collector[retry_before:]
                    retry_raw = [n for n in retry_notes if n.get('_keyword') == keyword]
                    if retry_raw:
                        relevant_count = 0
                        for item in retry_raw:
                            del item['_keyword']
                            if is_relevant(item.get('title', ''), item.get('desc', ''), platform):
                                all_notes.append(item)
                                relevant_count += 1
                        print(f"      reload 重试成功! 拦截 {len(retry_raw)} 条, 相关 {relevant_count} 条")
                        got_data = True
                        break

                if not got_data:
                    # 第二级：重新 goto（用不同的 URL 参数绕过缓存）
                    print(f"      reload 无效，尝试重新 goto...")
                    await asyncio.sleep(random.uniform(10, 20))
                    retry_before2 = len(api_results_collector)
                    cache_bust = f"&t={int(datetime.now().timestamp())}"
                    try:
                        await page.goto(url + cache_bust, wait_until="networkidle", timeout=20000)
                    except Exception:
                        try:
                            await page.goto(url + cache_bust, wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                    await asyncio.sleep(random.uniform(5, 10))
                    await human_like_scroll(page)
                    await asyncio.sleep(random.uniform(3, 5))
                    retry_notes2 = api_results_collector[retry_before2:]
                    retry_raw2 = [n for n in retry_notes2 if n.get('_keyword') == keyword]
                    if retry_raw2:
                        relevant_count = 0
                        for item in retry_raw2:
                            del item['_keyword']
                            if is_relevant(item.get('title', ''), item.get('desc', ''), platform):
                                all_notes.append(item)
                                relevant_count += 1
                        print(f"      goto 重试成功! 拦截 {len(retry_raw2)} 条, 相关 {relevant_count} 条")
                    else:
                        print(f"      所有重试均无数据，跳过此关键词")
                        break
            else:
                print(f"      第{page_num}页: 无新数据，停止翻页")
                break

        if page_num < max_pages:
            delay = random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
            print(f"      ⏳ 翻页等待 {delay:.0f}s...")
            await asyncio.sleep(delay)

    return all_notes


def build_output(all_notes):
    """构建输出数据"""
    total_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    platform_stats = {}
    platforms_config = {}

    for p_name, p_cfg in SEARCH_KEYWORDS.items():
        cats = list(set(kw[1] for kw in p_cfg.get("keywords", []) if len(kw) >= 2)) + ["其他"]
        if not cats or cats == ["其他"]:
            cats = ["支付", "贷款", "理财", "AI", "海外", "组织架构", "客诉", "其他"]
        platforms_config[p_name] = {
            "icon": p_cfg.get("icon", "📌"),
            "color": p_cfg.get("color", "#6366f1"),
            "categories": cats,
        }

    for note in all_notes:
        p = note.get("platform", "")
        if not p:
            continue
        if p not in platform_stats:
            platform_stats[p] = {
                "total": 0, "category_stats": {},
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
            "note": "月度全量爬取：6大支付平台"
        },
        "notes": all_notes
    }


class SafeBrowserManager:
    """安全浏览器管理器 - headless 模式"""

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

    async def start(self):
        self.playwright = await async_playwright().start()
        await self._create_browser()

    async def _create_browser(self):
        if self.context:
            try: await self.context.close()
            except: pass
        if self.browser:
            try: await self.browser.close()
            except: pass

        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN", timezone_id="Asia/Shanghai",
        )
        await self.context.add_cookies(self.xhs_cookies)
        self.page = await self.context.new_page()
        stealth = Stealth(
            navigator_platform_override="MacIntel",
            navigator_vendor_override="Google Inc.",
            navigator_user_agent_override="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        await stealth.apply_stealth_async(self.page)
        self.page.on("response", self._on_response)
        try:
            await self.page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(random.uniform(3, 5))
        except Exception:
            pass

    async def _on_response(self, response):
        url = response.url
        if 'api/sns/web/v1/search/notes' in url:
            try:
                data = await response.json()
                if data and data.get('code') == 0:
                    items = data.get('data', {}).get('items', [])
                    if items:
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

                            time_str = ''
                            ts = nc.get('time', 0)
                            if ts:
                                try:
                                    if ts > 1e12: ts = ts / 1000
                                    time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                                except: pass
                            if not time_str and nid and len(nid) == 24:
                                try:
                                    ts_from_id = int(nid[:8], 16)
                                    if 1577836800 < ts_from_id < 1893456000:
                                        time_str = datetime.fromtimestamp(ts_from_id).strftime('%Y-%m-%d %H:%M')
                                except: pass
                            if not time_str:
                                time_str = datetime.now().strftime('%Y-%m-%d %H:%M')

                            cover = ''
                            imgs = nc.get('image_list', [])
                            if imgs and isinstance(imgs[0], dict):
                                cover = imgs[0].get('url_default', '') or imgs[0].get('url', '')
                                if not cover and imgs[0].get('info_list'):
                                    cover = imgs[0]['info_list'][0].get('url', '')

                            cats = [self._current_category] + [c for c in classify_note(full_text) if c != self._current_category]

                            self.api_results_collector.append({
                                "_keyword": self._current_keyword,
                                "note_id": nid, "platform": self._current_platform,
                                "title": title, "desc": desc[:500],
                                "author": user_info.get('nickname', ''),
                                "author_avatar": user_info.get('avatar', ''),
                                "author_id": user_info.get('user_id', ''),
                                "liked_count": str(interact.get('liked_count', '0')),
                                "comment_count": str(interact.get('comment_count', '0')),
                                "collected_count": str(interact.get('collected_count', '0')),
                                "cover": cover, "link": link, "time": time_str,
                                "categories": cats,
                                "keyword_tags": [self._current_keyword, self._current_category],
                                "search_keyword": self._current_keyword,
                                "xsec_token": xsec,
                                "sentiment": analyze_sentiment(full_text),
                                "is_deleted": False, "deleted_at": "",
                                "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                            })
            except: pass

    async def is_alive(self):
        try:
            if not self.page or not self.browser: return False
            await self.page.evaluate("1+1")
            return True
        except: return False

    async def ensure_alive(self):
        if not await self.is_alive():
            print("  🔄 浏览器断开，正在重建...")
            await self._create_browser()
            return True
        return False

    async def cleanup(self):
        try:
            if self.page: self.page.remove_listener("response", self._on_response)
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


async def main():
    parser = argparse.ArgumentParser(description='月度全量爬虫 - 6大支付平台')
    parser.add_argument('--reset', action='store_true', help='重置断点进度，从头开始')
    parser.add_argument('--test', action='store_true', help='仅测试 cookie/浏览器是否可用')
    parser.add_argument('--dry-run', action='store_true', help='只打印计划，不实际爬取')
    parser.add_argument('--only', type=str, help='只爬指定平台，逗号分隔，如: 美团支付,京东支付')
    args = parser.parse_args()

    start_time = datetime.now()
    print("=" * 60)
    print("🚀 月度全量爬虫 - 6大支付平台")
    print(f"📅 {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛡️ 安全模式: Playwright Stealth + headless + 模拟人类")
    print(f"⏱️ 关键词间隔: {KEYWORD_DELAY_MIN}-{KEYWORD_DELAY_MAX}s")
    print(f"⏱️ 翻页间隔: {PAGE_DELAY_MIN}-{PAGE_DELAY_MAX}s")
    print(f"⏱️ 平台切换间隔: {PLATFORM_SWITCH_DELAY_MIN}-{PLATFORM_SWITCH_DELAY_MAX}s")
    print("=" * 60)

    # --only 平台过滤
    active_platforms = ALL_PLATFORMS
    if args.only:
        only_set = [p.strip() for p in args.only.split(',')]
        active_platforms = [p for p in ALL_PLATFORMS if p in only_set]
        if not active_platforms:
            print(f"❌ 没有匹配的平台! 可选: {', '.join(ALL_PLATFORMS)}")
            return
        print(f"🎯 仅爬取: {', '.join(active_platforms)}")

    total_keywords = sum(len(SEARCH_KEYWORDS[p]["keywords"]) for p in active_platforms)
    total_pages = sum(sum(kw[2] for kw in SEARCH_KEYWORDS[p]["keywords"]) for p in active_platforms)
    print(f"\n📊 计划: {len(active_platforms)} 个平台, {total_keywords} 个关键词, 预计 {total_pages} 页")

    if args.dry_run:
        for platform in active_platforms:
            config = SEARCH_KEYWORDS[platform]
            print(f"\n{config['icon']} {platform}: {len(config['keywords'])} 个关键词")
            for kw, cat, pages in config["keywords"]:
                print(f"    {kw} ({cat}, {pages}页)")
        est_minutes = total_keywords * 1.2 + total_pages * 0.2 + len(active_platforms) * 2.5
        print(f"\n⏱️ 预计耗时: {est_minutes:.0f} 分钟 ({est_minutes/60:.1f} 小时)")
        return

    # Cookie 提取
    print("\n🍪 提取 Chrome Cookie...")
    xhs_cookies = extract_all_xhs_cookies()
    if not xhs_cookies:
        print("❌ 无法提取 Cookie！请确保在 Chrome 中已登录小红书")
        return
    ws_cookies = [c for c in xhs_cookies if c['name'] == 'web_session' and len(c.get('value', '')) > 10]
    if not ws_cookies:
        print("❌ 未找到有效的 web_session！请在 Chrome 中重新登录小红书")
        return
    print(f"  ✅ {len(xhs_cookies)} 条 cookie（含 web_session）")

    # 断点续爬
    progress = load_progress()
    if args.reset:
        progress = {"completed": [], "last_run": "", "total_runs": 0}
        save_progress(progress)
        print("\n🔄 已重置断点进度")
    completed_set = set(progress.get("completed", []))

    # 测试模式
    if args.test:
        print("\n🧪 测试浏览器和 Cookie...")
        api_collector = []
        mgr = SafeBrowserManager(xhs_cookies, api_collector)
        try:
            await mgr.start()
            cookies = await mgr.context.cookies("https://www.xiaohongshu.com")
            ws = [c for c in cookies if c['name'] == 'web_session' and len(c.get('value', '')) > 10]
            if ws:
                print(f"  ✅ Cookie 注入成功! web_session = {ws[0]['value'][:25]}...")
            else:
                print("  ❌ Cookie 注入失败")
                return
            mgr._current_keyword = "微信支付"
            mgr._current_platform = "微信支付"
            mgr._current_category = "支付"
            notes = await search_keyword_pages(mgr.page, "微信支付", "微信支付", "支付", 1, api_collector)
            if notes:
                print(f"  ✅ 搜索测试成功! 获取 {len(notes)} 条结果")
            else:
                print("  ⚠️ 搜索无结果（可能限流中）")
        finally:
            await mgr.cleanup()
        return

    # 加载已有数据
    existing_notes = []
    existing_ids = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            existing_notes = existing_data.get('notes', [])
            existing_ids = {n.get('note_id', '') for n in existing_notes}
            print(f"\n📂 已有数据: {len(existing_notes)} 条笔记")
        except Exception:
            pass

    # 开始爬取
    api_results_collector = []
    mgr = SafeBrowserManager(xhs_cookies, api_results_collector)
    all_new_notes = []
    seen_ids = set(existing_ids)
    keywords_done_this_run = 0
    hit_461 = False
    consecutive_empty = 0

    try:
        print("\n🌐 启动 headless 浏览器...")
        await mgr.start()
        print("  ✅ 浏览器就绪\n")

        keyword_index = 0
        for platform_idx, platform in enumerate(active_platforms):
            config = SEARCH_KEYWORDS[platform]
            print(f"\n{'═' * 55}")
            print(f"{config['icon']} 开始爬取: {platform} ({len(config['keywords'])} 个关键词)")
            print(f"{'═' * 55}")
            platform_count = 0

            for kw_idx, (keyword, category, max_pages) in enumerate(config["keywords"]):
                keyword_index += 1
                kw_key = f"{platform}::{keyword}"
                if kw_key in completed_set:
                    print(f"  [{keyword_index}/{total_keywords}] ⏭️ {keyword} (已完成，跳过)")
                    continue

                # 连续无数据检测 → 重建浏览器
                if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                    print(f"\n  ⚠️ 连续 {consecutive_empty} 个关键词无数据！重建浏览器...")
                    await mgr.cleanup()
                    await asyncio.sleep(random.uniform(15, 30))
                    fresh_cookies = extract_all_xhs_cookies()
                    if fresh_cookies:
                        xhs_cookies = fresh_cookies
                    mgr = SafeBrowserManager(xhs_cookies, api_results_collector)
                    await mgr.start()
                    consecutive_empty = 0
                    print(f"  ✅ 浏览器已重建，继续爬取\n")

                print(f"\n  [{keyword_index}/{total_keywords}] 🔍 {keyword} (分类:{category}, 计划{max_pages}页)")
                await mgr.ensure_alive()
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
                            all_new_notes.append(note)
                            new_count += 1
                    platform_count += new_count
                    keywords_done_this_run += 1

                    if new_count == 0 and len(notes) == 0:
                        consecutive_empty += 1
                    else:
                        consecutive_empty = 0

                    print(f"    ✅ 新增 {new_count} 条 (平台累计 {platform_count}, 本轮总 {len(all_new_notes)}{f', ⚠️连续空{consecutive_empty}' if consecutive_empty > 0 else ''})")

                    completed_set.add(kw_key)
                    progress["completed"] = list(completed_set)
                    progress["last_run"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    save_progress(progress)

                except Exception as e:
                    err_str = str(e)
                    if '461' in err_str:
                        print(f"    🛑 触发 461 反爬！立即停止保护账号")
                        hit_461 = True
                        break
                    print(f"    ❌ 异常: {e}")
                    consecutive_empty += 1
                    await mgr.ensure_alive()

                # 定期保存
                if keywords_done_this_run % SAVE_EVERY_N_KEYWORDS == 0 and all_new_notes:
                    merged = existing_notes + all_new_notes
                    output = build_output(merged)
                    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(output, f, ensure_ascii=False, indent=2)
                    print(f"\n  💾 进度已保存 (新增 {len(all_new_notes)}, 总 {len(merged)} 条)\n")

                # 关键词间安全等待
                is_last_of_platform = (kw_idx == len(config["keywords"]) - 1)
                if not is_last_of_platform:
                    delay = random.uniform(KEYWORD_DELAY_MIN, KEYWORD_DELAY_MAX)
                    print(f"    ⏳ 安全间隔 {delay:.0f}s...")
                    await asyncio.sleep(delay)

            if hit_461:
                break

            # 平台切换长等待
            if platform_idx < len(active_platforms) - 1 and not hit_461:
                delay = random.uniform(PLATFORM_SWITCH_DELAY_MIN, PLATFORM_SWITCH_DELAY_MAX)
                print(f"\n  🔄 平台切换，休息 {delay:.0f}s...\n")
                await asyncio.sleep(delay)

            print(f"\n  📊 {platform} 完成: 新增 {platform_count} 条")

    finally:
        await mgr.cleanup()

    # 保存最终数据
    if all_new_notes:
        merged = existing_notes + all_new_notes
        output = build_output(merged)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n{'=' * 60}")
    print(f"🎉 月度爬取完成！")
    print(f"{'=' * 60}")
    print(f"  ⏱️ 耗时: {elapsed/60:.1f} 分钟")
    print(f"  📝 本次新增: {len(all_new_notes)} 条")
    print(f"  📁 数据总量: {len(existing_notes) + len(all_new_notes)} 条")
    print(f"  🔑 关键词完成: {keywords_done_this_run} 个")

    if hit_461:
        print(f"  ⚠️ 因 461 反爬提前停止，下次执行将从断点继续")

    remaining = sum(1 for p in active_platforms for kw, _, _ in SEARCH_KEYWORDS[p]["keywords"]
                    if f"{p}::{kw}" not in completed_set)
    if remaining > 0:
        print(f"  📋 剩余: {remaining} 个关键词待爬")
    else:
        print(f"  ✅ 所有平台全部关键词已爬完！")
        progress["completed"] = []
        progress["total_runs"] = progress.get("total_runs", 0) + 1
        save_progress(progress)

    print(f"\n💾 数据已保存: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
