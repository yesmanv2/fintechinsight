"""
安全爬虫 - 每天分散爬取，一周整理一次

核心策略：
1. 每天只爬1个平台 - 周一支付宝、周二微信...周六云闪付、周日休息+整理输出
2. 大幅降低频率 - 搜索间隔 15~30 秒，关键词间隔 30~60 秒
3. 模拟真人 - 穿插浏览推荐页、随机停顿、像人一样"闲逛"
4. 代理 IP 支持 - 可配置住宅代理，分散IP风险
5. 安全保底 - 遇到风控信号立即停止，宁可少爬不能封号
6. 断点续爬 - 中断后可从上次进度继续（--resume）
7. Session 健康检查 - 开始前自动检测 Cookie 是否有效
8. 自动构建 - 爬取完成后自动更新 Netlify 部署版（--auto-build）
9. 周日自动整理 - --weekly-build 仅执行数据整理+构建，不爬取

使用方式:
    # 每日模式（自动按星期分配平台，推荐！）
    python3 safe_crawler.py --session-file cookie.txt --auto-build

    # 指定爬某个平台
    python3 safe_crawler.py --session-file cookie.txt --platform 支付宝

    # 使用代理（强烈推荐！）
    python3 safe_crawler.py --session-file cookie.txt --proxy socks5://user:pass@host:port

    # 使用代理配置文件
    python3 safe_crawler.py --session-file cookie.txt --proxy-file proxy.txt

    # 一次爬完所有平台（慢速，约2~3小时，不推荐）
    python3 safe_crawler.py --session-file cookie.txt --all

    # 从上次中断的地方继续爬取
    python3 safe_crawler.py --session-file cookie.txt --resume

    # 周日整理模式（仅重新生成分析+构建，不爬取）
    python3 safe_crawler.py --weekly-build

    # 试运行（查看计划但不实际爬取）
    python3 safe_crawler.py --session-file cookie.txt --dry-run
"""
import asyncio
import sys
import os
import json
import time
import random
import argparse
from datetime import datetime, timedelta

# 添加技能路径
SKILL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills', 'xiaohongshutools', 'scripts')
sys.path.insert(0, SKILL_PATH)

from request.web.xhs_session import create_xhs_session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'real_data.json')
LOG_FILE = os.path.join(BASE_DIR, 'safe_crawl.log')
PROGRESS_FILE = os.path.join(BASE_DIR, 'safe_crawl_progress.json')  # 断点续爬进度

# ==================== 安全配置 ====================

# 每个平台的搜索关键词（完整版，覆盖各维度）
PLATFORMS_SEARCH = {
    "支付宝": {
        "icon": "💙", "color": "#1677FF",
        "keywords": {
            "支付": ["支付宝支付", "支付宝扫码", "支付宝碰一下", "支付宝NFC", "支付宝刷脸",
                     "支付宝付款码", "支付宝红包", "支付宝消费券", "支付宝乘车码",
                     "支付宝数字人民币", "支付宝先用后付", "支付宝转账"],
            "贷款": ["花呗", "借呗", "蚂蚁借呗", "芝麻信用", "网商贷", "备用金",
                     "花呗分期", "花呗额度"],
            "理财": ["余额宝", "支付宝理财", "蚂蚁财富", "好医保", "基金定投 支付宝",
                     "支付宝保险", "支付宝养老金"],
            "AI":   ["支付宝AI", "蚂蚁AI", "蚂蚁阿福"],
            "海外": ["Alipay+ 境外", "支付宝出境", "支付宝退税", "支付宝海外"],
            "组织架构": ["蚂蚁集团", "蚂蚁金服"],
            "客诉": ["支付宝投诉", "支付宝问题", "花呗逾期", "支付宝冻结",
                     "支付宝乱扣费", "支付宝盗刷", "支付宝自动续费"],
            "其他": ["蚂蚁森林", "集五福 支付宝"],
        },
    },
    "微信支付": {
        "icon": "💚", "color": "#07C160",
        "keywords": {
            "支付": ["微信支付", "微信红包", "微信刷掌支付", "微信刷脸支付", "微信零钱",
                     "微信亲属卡", "微信AA付款", "微信群收款", "微信小程序支付",
                     "微信免密支付", "微信数字人民币", "微信先用后付", "微信转账"],
            "贷款": ["微粒贷", "微信分付", "微信支付分", "微信借钱"],
            "理财": ["零钱通", "理财通", "微保", "微信理财"],
            "AI":   ["腾讯混元", "微信AI助手", "微信AI"],
            "海外": ["WeChat Pay 境外", "微信跨境汇款"],
            "组织架构": ["财付通", "腾讯金融"],
            "客诉": ["微信支付投诉", "微信支付封号", "微信自动续费",
                     "微信乱扣费", "微信支付问题"],
        },
    },
    "抖音支付": {
        "icon": "🖤", "color": "#FE2C55",
        "keywords": {
            "支付": ["抖音支付", "抖音团购券", "抖音买单", "抖音外卖",
                     "抖音直播下单", "抖币充值", "抖音钱包"],
            "贷款": ["放心借", "抖音月付", "DOU分期", "抖音借钱"],
            "AI":   ["豆包AI", "豆包 聊天"],
            "海外": ["TikTok Shop 支付"],
            "组织架构": ["字节跳动 金融", "抖音电商"],
            "客诉": ["抖音退款", "抖音投诉", "抖音自动续费", "抖音封号",
                     "抖音乱扣费"],
            "其他": ["抖音商城", "抖音探店"],
        },
    },
    "美团支付": {
        "icon": "💛", "color": "#FFC300",
        "keywords": {
            "支付": ["美团支付", "美团买单", "美团外卖红包", "美团团购",
                     "美团闪购", "大众点评 支付"],
            "贷款": ["美团月付", "美团生意贷", "美团借钱"],
            "AI":   ["美团无人配送", "美团AI"],
            "海外": ["KeeTa 美团"],
            "组织架构": ["美团公司 裁员"],
            "客诉": ["美团投诉", "美团退款", "美团配送问题", "美团客服差",
                     "美团乱扣费"],
            "其他": ["美团酒店", "美团单车", "美团买菜"],
        },
    },
    "京东支付": {
        "icon": "🧡", "color": "#E4393C",
        "keywords": {
            "支付": ["京东支付", "京东白条闪付", "京东闪付", "京东钱包", "京东购物卡"],
            "贷款": ["京东白条", "京东金条", "京东分期", "白条额度"],
            "理财": ["京东小金库", "京东理财", "京东金融"],
            "AI":   ["京东AI"],
            "海外": ["京东国际 海外购"],
            "组织架构": ["京东科技"],
            "客诉": ["京东支付投诉", "京东白条纠纷", "京东退款", "白条盗刷",
                     "京东乱扣费"],
            "其他": ["京东618", "京东PLUS"],
        },
    },
    "云闪付": {
        "icon": "🔴", "color": "#E60012",
        "keywords": {
            "支付": ["云闪付", "银联支付", "Apple Pay 银联", "华为Pay",
                     "银联62节", "银联数字人民币", "云闪付公交", "银联NFC"],
            "海外": ["银联国际", "银联卡 境外", "银联退税"],
            "组织架构": ["中国银联"],
            "客诉": ["云闪付投诉", "云闪付闪退", "云闪付问题"],
        },
    },
}

# 星期几 -> 爬哪个平台（0=周一，6=周日）
WEEKDAY_SCHEDULE = {
    0: "支付宝",      # 周一
    1: "微信支付",     # 周二
    2: "抖音支付",     # 周三
    3: "美团支付",     # 周四
    4: "京东支付",     # 周五
    5: "云闪付",       # 周六
    6: None,           # 周日休息
}

# 分类识别规则
CLASSIFY_RULES = {
    "支付": ["支付", "付款", "扫码", "转账", "收款", "二维码", "刷脸", "碰一下", "碰一碰", "条码", "红包",
             "NFC", "团购", "外卖", "买单", "闪购", "免密", "数字人民币", "先用后付", "先享后付",
             "乘车码", "消费券", "购物卡", "充值"],
    "贷款": ["贷款", "花呗", "借呗", "借钱", "分期", "信用", "额度", "还款", "逾期", "催收",
             "微粒贷", "分付", "放心借", "月付", "白条", "金条", "网商贷", "备用金", "支付分",
             "芝麻信用", "生意贷"],
    "理财": ["理财", "余额宝", "基金", "投资", "收益", "定期", "蚂蚁财富", "股票", "保险", "零钱通",
             "理财通", "微保", "好医保", "小金库", "定投", "养老金", "京东金融"],
    "AI":   ["ai", "人工智能", "智能", "大模型", "混元", "豆包", "灵光", "无人配送", "机器人", "阿福"],
    "海外": ["海外", "出境", "境外", "国际", "alipay", "外币", "退税", "汇率", "出国", "跨境",
             "tiktok shop", "keeta", "wechat pay"],
    "组织架构": ["蚂蚁集团", "人事", "裁员", "组织", "蚂蚁金服", "上市", "ipo", "高管",
                "字节跳动", "中国银联", "京东科技", "财付通", "腾讯金融", "美团公司"],
    "客诉": ["投诉", "客服", "坑", "吐槽", "问题", "bug", "骗", "盗刷", "冻结", "封号", "垃圾",
             "差评", "难用", "退款", "乱扣费", "自动续费", "闪退", "纠纷"],
}

SENTIMENT_POSITIVE = ["好用", "方便", "不错", "推荐", "喜欢", "划算", "优惠", "开心", "赞", "省钱", "给力",
                      "太爽了", "太强了", "牛", "真香", "解决了", "成功", "终于", "感谢", "惊喜", "便宜"]
SENTIMENT_NEGATIVE = ["难用", "垃圾", "投诉", "骗", "坑", "差评", "恶心", "无语", "崩了", "封号", "冻结",
                      "盗刷", "焦虑", "过分", "退款", "催收", "受不了", "太慢", "坑人", "失望", "逾期",
                      "问题", "吐槽", "差劲", "闪退"]


# ==================== 安全延迟 ====================

class HumanSimulator:
    """模拟真人行为的延迟控制器"""

    def __init__(self):
        self.request_count = 0
        self.session_start = time.time()
        self.last_request_time = 0

    async def think_before_search(self):
        """搜索前的'思考'时间 - 模拟人在想搜什么"""
        delay = random.uniform(3, 8)
        # 偶尔人会发呆久一点
        if random.random() < 0.15:
            delay += random.uniform(10, 25)
            log("  💭 (模拟人类犹豫中...)")
        await asyncio.sleep(delay)

    async def read_results(self):
        """翻页间的'阅读'时间 - 模拟人在看搜索结果"""
        delay = random.uniform(8, 18)
        # 偶尔人会仔细看某条内容
        if random.random() < 0.2:
            delay += random.uniform(15, 30)
            log("  👀 (模拟人类仔细阅读中...)")
        await asyncio.sleep(delay)

    async def switch_keyword(self):
        """切换关键词间的间隔 - 模拟人换了个搜索词"""
        delay = random.uniform(20, 45)
        # 偶尔人会去做别的事再回来
        if random.random() < 0.1:
            delay += random.uniform(30, 90)
            log("  ☕ (模拟人类小歇一下...)")
        await asyncio.sleep(delay)

    async def take_a_break(self):
        """每隔几个关键词休息一下 - 模拟人去喝水/上厕所"""
        delay = random.uniform(60, 180)
        log(f"  🧘 休息 {int(delay)} 秒... (模拟真人行为)")
        await asyncio.sleep(delay)

    async def browse_homefeed(self, xhs):
        """穿插浏览推荐页 - 让行为更像正常用户"""
        log("  📱 浏览推荐页... (让行为更自然)")
        try:
            from request.web.apis.note import HomeFeedCategory
            res = await xhs.apis.note.get_homefeed(
                category=HomeFeedCategory.RECOMMEND,
                cursor_score="",
                note_index=0
            )
            await res.json()  # 消费response
            await asyncio.sleep(random.uniform(5, 12))  # 假装在看
        except Exception:
            pass

    def should_take_break(self):
        """判断是否该休息了"""
        self.request_count += 1
        # 每 5~8 个关键词休息一次
        if self.request_count % random.randint(5, 8) == 0:
            return True
        return False

    def should_browse_homefeed(self):
        """判断是否该去看看推荐页"""
        # 大约 30% 概率穿插一次推荐页浏览
        return random.random() < 0.3


# ==================== 日志 ====================

def log(msg):
    """同时输出到控制台和日志文件"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(full_msg + '\n')
    except Exception:
        pass


# ==================== 核心逻辑 ====================

def classify_note(text: str) -> list:
    text_lower = text.lower()
    matched = []
    for category, keywords in CLASSIFY_RULES.items():
        for kw in keywords:
            if kw in text_lower:
                matched.append(category)
                break
    return matched if matched else ["其他"]


def analyze_sentiment(text: str) -> str:
    text_lower = text.lower()
    pos_score = sum(1 for w in SENTIMENT_POSITIVE if w in text_lower)
    neg_score = sum(1 for w in SENTIMENT_NEGATIVE if w in text_lower)
    if neg_score > pos_score:
        return "negative"
    elif pos_score > neg_score:
        return "positive"
    return "neutral"


def parse_note_item(item: dict, search_keyword: str, platform_hint: str = "") -> dict:
    note_card = item.get('note_card', item)
    user_info = note_card.get('user', {})
    interact_info = note_card.get('interact_info', {})

    note_id = item.get('id', note_card.get('note_id', ''))
    xsec_token = item.get('xsec_token', '')

    title = note_card.get('display_title', '') or item.get('display_title', '') or ''
    desc = note_card.get('desc', '') or ''

    full_text = f"{title} {desc}"
    categories = classify_note(full_text)
    sentiment = analyze_sentiment(full_text)
    platform = platform_hint

    link = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec_token:
        link += f"?xsec_token={xsec_token}&xsec_source=pc_search"

    timestamp = note_card.get('time', 0) or item.get('time', 0)
    time_str = ''
    if timestamp:
        try:
            if timestamp > 1e12:
                timestamp = timestamp / 1000
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass

    cover = ''
    image_list = note_card.get('image_list', []) or note_card.get('images_list', [])
    if image_list:
        first_img = image_list[0]
        if isinstance(first_img, dict):
            cover = first_img.get('url_default', '') or first_img.get('url', '')
            if not cover and first_img.get('info_list'):
                cover = first_img['info_list'][0].get('url', '')

    keyword_tags = []
    if search_keyword:
        keyword_tags.append(search_keyword)
    for cat in categories:
        if cat not in keyword_tags and cat != "其他":
            keyword_tags.append(cat)

    return {
        "note_id": note_id,
        "platform": platform,
        "title": title,
        "desc": desc[:500],
        "author": user_info.get('nickname', '未知'),
        "author_avatar": user_info.get('avatar', ''),
        "author_id": user_info.get('user_id', ''),
        "liked_count": str(interact_info.get('liked_count', note_card.get('liked_count', '0'))),
        "comment_count": str(interact_info.get('comment_count', note_card.get('comment_count', '0'))),
        "collected_count": str(interact_info.get('collected_count', note_card.get('collected_count', '0'))),
        "cover": cover,
        "link": link,
        "time": time_str,
        "categories": categories,
        "keyword_tags": keyword_tags,
        "search_keyword": search_keyword,
        "xsec_token": xsec_token,
        "sentiment": sentiment,
        "is_deleted": False,
        "deleted_at": "",
        "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
    }


async def safe_search_keyword(xhs, keyword: str, human: HumanSimulator, max_pages: int = 1, existing_ids: set = None) -> list:
    """
    安全搜索单个关键词
    - 只爬 1 页（默认20条），不贪心
    - 遇到任何风控信号立即返回
    - 如果结果中大量已有笔记（>50%），提前停止（增量优化）
    """
    notes = []
    if existing_ids is None:
        existing_ids = set()

    for page in range(1, max_pages + 1):
        try:
            # 搜索前先"思考"
            await human.think_before_search()

            log(f"  📥 搜索: '{keyword}' 第 {page} 页...")
            res = await xhs.apis.note.search_notes(
                keyword, page=page, page_size=20, sort="time_descending", note_type=0
            )
            data = await res.json()

            if not data:
                log(f"  ⚠️ 空响应，可能有风控")
                return notes

            code = data.get('code', -1)

            # 风控信号检测
            if code == -100:
                log(f"  🚨 检测到未登录/session过期！立即停止")
                raise SessionExpiredError("Session expired")
            elif code == -101 or code == -104:
                log(f"  🚨 检测到权限限制(code={code})！可能被风控")
                raise RiskDetectedError(f"Risk detected: code={code}")
            elif code == 300012:
                log(f"  🚨 检测到滑块验证！立即停止")
                raise RiskDetectedError("Slider captcha detected")
            elif code != 0:
                msg = data.get('msg', 'unknown')
                log(f"  ⚠️ 异常响应 code={code}: {msg}")
                # 非严重错误，等一会再继续
                await asyncio.sleep(random.uniform(30, 60))
                return notes

            items = data.get('data', {}).get('items', [])
            if not items:
                log(f"  ℹ️ '{keyword}' 无结果")
                break

            for item in items:
                try:
                    note = parse_note_item(item, keyword)
                    if note['title']:
                        notes.append(note)
                except Exception as e:
                    pass

            # 增量检测：如果结果中大部分已存在，说明没有新内容了
            new_in_page = sum(1 for item in items
                            if item.get('id', item.get('note_card', {}).get('note_id', '')) not in existing_ids)
            dup_rate = 1 - (new_in_page / max(len(items), 1))
            if dup_rate >= 0.7 and existing_ids:
                log(f"  ⏩ '{keyword}' 重复率 {dup_rate:.0%}，已有数据充足，跳过后续页")
                break

            log(f"  ✅ '{keyword}' 获取 {len(items)} 条 (新{new_in_page}条)")

            # 如果要爬下一页，先"阅读"当前结果
            if page < max_pages:
                await human.read_results()

        except (SessionExpiredError, RiskDetectedError):
            raise
        except Exception as e:
            error_str = str(e)
            if '没有权限' in error_str or '-104' in error_str:
                log(f"  🚨 权限受限！停止爬取")
                raise RiskDetectedError(error_str)
            log(f"  ❌ 搜索 '{keyword}' 失败: {e}")
            await asyncio.sleep(random.uniform(15, 30))
            break

    return notes


class SessionExpiredError(Exception):
    pass

class RiskDetectedError(Exception):
    pass


# ==================== 断点续爬 ====================

def load_progress() -> dict:
    """加载上次的爬取进度"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                # 检查进度是否过期（超过24小时的进度自动清理）
                saved_time = progress.get('saved_at', '')
                if saved_time:
                    saved_dt = datetime.strptime(saved_time, '%Y-%m-%d %H:%M:%S')
                    if (datetime.now() - saved_dt) > timedelta(hours=24):
                        log("⏰ 上次进度已超过24小时，重新开始")
                        return {}
                return progress
        except Exception:
            pass
    return {}


def save_progress(platform: str, completed_keywords: list, total_new_notes: int):
    """保存当前爬取进度（用于断点续爬）"""
    progress = {
        'platform': platform,
        'completed_keywords': completed_keywords,
        'total_new_notes': total_new_notes,
        'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def clear_progress():
    """清除进度文件（爬取完成后调用）"""
    if os.path.exists(PROGRESS_FILE):
        try:
            os.remove(PROGRESS_FILE)
        except Exception:
            pass


# ==================== Cookie 健康检查 ====================

async def check_session_health(xhs) -> bool:
    """检查 session 是否有效（通过请求推荐页测试）"""
    try:
        from request.web.apis.note import HomeFeedCategory
        res = await xhs.apis.note.get_homefeed(
            category=HomeFeedCategory.RECOMMEND,
            cursor_score="",
            note_index=0
        )
        data = await res.json()
        if not data:
            return False
        code = data.get('code', -1)
        if code == 0:
            items = data.get('data', {}).get('items', [])
            log(f"✅ Session 有效（推荐页返回 {len(items)} 条）")
            return True
        elif code in (-100, -101, -104):
            log(f"🚨 Session 无效 (code={code})")
            return False
        else:
            log(f"⚠️ Session 状态不确定 (code={code}: {data.get('msg', '')})")
            return True  # 不确定时继续尝试
    except Exception as e:
        log(f"⚠️ Session 检查异常: {e}")
        return True  # 网络问题不算session失效


# ==================== 自动构建部署版 ====================

def auto_build_netlify():
    """爬取完成后自动构建 Netlify 部署版（含月度分析数据更新）"""
    # 先运行月度分析预计算
    analysis_script = os.path.join(BASE_DIR, 'generate_monthly_analysis.py')
    if os.path.exists(analysis_script):
        log("📊 重新生成月度分析数据...")
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, analysis_script],
                capture_output=True, text=True, cwd=BASE_DIR, timeout=120
            )
            if result.returncode == 0:
                log("  ✅ 月度分析数据已更新")
            else:
                log(f"  ⚠️ 月度分析生成失败: {result.stderr[:200]}")
        except Exception as e:
            log(f"  ⚠️ 月度分析异常: {e}")

    # 再构建 Netlify 部署版
    build_script = os.path.join(BASE_DIR, 'build_netlify.py')
    if not os.path.exists(build_script):
        log("⚠️ build_netlify.py 不存在，跳过自动构建")
        return False
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, build_script],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=60
        )
        if result.returncode == 0:
            # 提取关键输出
            for line in result.stdout.strip().split('\n'):
                if any(k in line for k in ['✅', '📊', '📁', '📏']):
                    log(f"  {line.strip()}")
            log("🏗️  Netlify 部署版已自动更新！")
        else:
            log(f"⚠️ 构建失败: {result.stderr[:200]}")
            return False
    except Exception as e:
        log(f"⚠️ 自动构建异常: {e}")
        return False

    # 自动部署到 Netlify
    deploy_dir = os.path.join(BASE_DIR, 'netlify-deploy')
    if not os.path.isdir(deploy_dir):
        log("⚠️ netlify-deploy/ 目录不存在，跳过部署")
        return False
    try:
        log("🚀 自动部署到 Netlify...")
        deploy_result = subprocess.run(
            ['netlify', 'deploy', f'--dir={deploy_dir}', '--prod'],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=300
        )
        if deploy_result.returncode == 0:
            log("✅ Netlify 部署成功！")
            for line in deploy_result.stdout.split('\n'):
                if 'Website URL' in line or 'Unique Deploy URL' in line or 'Website url' in line:
                    log(f"  {line.strip()}")
            return True
        else:
            log(f"⚠️ Netlify 部署失败: {deploy_result.stderr[:300]}")
            return False
    except FileNotFoundError:
        log("⚠️ netlify CLI 未找到，跳过自动部署（请确认 PATH 包含 /opt/homebrew/bin）")
        return False
    except subprocess.TimeoutExpired:
        log("⚠️ Netlify 部署超时（>300秒），跳过")
        return False
    except Exception as e:
        log(f"⚠️ 自动部署异常: {e}")
        return False


def merge_with_existing(new_notes: list) -> list:
    """与已有数据合并，去重"""
    existing_notes = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing_notes = data.get("notes", [])
                log(f"📂 已有数据: {len(existing_notes)} 条")
        except Exception:
            pass

    existing_ids = {n["note_id"] for n in existing_notes}
    added = 0
    for note in new_notes:
        if note["note_id"] not in existing_ids:
            existing_notes.append(note)
            existing_ids.add(note["note_id"])
            added += 1

    log(f"📊 新增 {added} 条 (去重后), 跳过 {len(new_notes) - added} 条重复")
    return existing_notes


def build_output(all_notes: list) -> dict:
    """构建输出数据"""
    total_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    platform_stats = {}
    platforms_config = {}

    for p_name, p_cfg in PLATFORMS_SEARCH.items():
        all_cats = list(p_cfg["keywords"].keys()) + ["其他"]
        platforms_config[p_name] = {
            "icon": p_cfg["icon"],
            "color": p_cfg["color"],
            "categories": all_cats,
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

    deleted_count = sum(1 for n in all_notes if n.get("is_deleted"))

    return {
        "meta": {
            "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_notes": len(all_notes),
            "sentiment_stats": total_sentiment,
            "platform_stats": platform_stats,
            "platforms_config": platforms_config,
            "deleted_stats": {
                "total_deleted": deleted_count,
                "per_platform": {},
            },
            "is_demo": False,
            "data_range": "真实爬取数据",
            "note": "安全爬虫 - 每日分散爬取"
        },
        "notes": all_notes
    }


def get_today_platform():
    """根据今天星期几返回应该爬的平台"""
    weekday = datetime.now().weekday()
    return WEEKDAY_SCHEDULE.get(weekday)


async def main():
    parser = argparse.ArgumentParser(description='安全爬虫 - 模拟真人行为')
    parser.add_argument('--session', type=str, default=None, help='web_session cookie')
    parser.add_argument('--session-file', type=str, default=None, help='cookie 文件')
    parser.add_argument('--platform', type=str, default=None, help='指定平台（默认按星期分配）')
    parser.add_argument('--all', action='store_true', help='爬全部平台（慢速，约2~3小时）')
    parser.add_argument('--proxy', type=str, default=None, help='代理地址 socks5://user:pass@host:port')
    parser.add_argument('--proxy-file', type=str, default=None, help='代理配置文件（每行一个代理地址，随机选取）')
    parser.add_argument('--pages', type=int, default=1, help='每关键词搜索页数（默认1，建议不超过2）')
    parser.add_argument('--dry-run', action='store_true', help='试运行，不实际爬取')
    parser.add_argument('--resume', action='store_true', help='从上次中断的地方继续')
    parser.add_argument('--auto-build', action='store_true', help='爬取完成后自动构建 Netlify 部署版')
    parser.add_argument('--weekly-build', action='store_true', help='仅执行周度整理（重新生成分析+构建），不爬取')
    parser.add_argument('--skip-health-check', action='store_true', help='跳过 session 健康检查')
    args = parser.parse_args()

    # 周日整理模式：只构建不爬取
    if args.weekly_build:
        log("=" * 60)
        log("📊 周度整理模式 - 仅重新生成分析+构建部署版")
        log("=" * 60)
        auto_build_netlify()
        log("✅ 周度整理完成！")
        return

    # 获取 web_session
    web_session = args.session
    if args.session_file:
        try:
            with open(args.session_file, 'r') as f:
                web_session = f.read().strip()
        except Exception as e:
            log(f"❌ 读取 session 文件失败: {e}")
            return

    if not web_session:
        log("❌ 必须提供 web_session！安全爬虫不支持游客模式")
        log("   用法: python3 safe_crawler.py --session-file cookie.txt")
        return

    # 读取代理配置（支持代理池随机选取）
    proxy = args.proxy
    if args.proxy_file:
        try:
            with open(args.proxy_file, 'r') as f:
                proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            if proxies:
                proxy = random.choice(proxies)
                log(f"🎲 从代理池中随机选取: {proxy[:30]}...")
            else:
                log("⚠️ 代理文件为空，将不使用代理")
        except Exception as e:
            log(f"⚠️ 读取代理文件失败: {e}")
    elif not proxy:
        # 检查默认代理文件
        default_proxy_file = os.path.join(BASE_DIR, 'proxy.txt')
        if os.path.exists(default_proxy_file):
            try:
                with open(default_proxy_file, 'r') as f:
                    proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                if proxies:
                    proxy = random.choice(proxies)
                    log(f"🎲 从 proxy.txt 自动加载代理: {proxy[:30]}...")
            except Exception:
                pass

    # 加载断点续爬进度
    resume_progress = {}
    if args.resume:
        resume_progress = load_progress()
        if resume_progress:
            log(f"📋 找到上次进度：平台={resume_progress.get('platform', '?')}，"
                f"已完成 {len(resume_progress.get('completed_keywords', []))} 个关键词")
        else:
            log("ℹ️  没有找到可恢复的进度，从头开始")

    # 确定今天爬哪个平台
    if args.all:
        platforms_to_crawl = list(PLATFORMS_SEARCH.keys())
        log("⚠️ 全量模式：将爬取所有平台（预计2~3小时）")
    elif args.platform:
        if args.platform not in PLATFORMS_SEARCH:
            log(f"❌ 未知平台: {args.platform}")
            log(f"   可选: {', '.join(PLATFORMS_SEARCH.keys())}")
            return
        platforms_to_crawl = [args.platform]
    elif resume_progress and resume_progress.get('platform'):
        # 断点续爬时沿用上次的平台
        platforms_to_crawl = [resume_progress['platform']]
        log(f"📋 续爬上次平台: {resume_progress['platform']}")
    else:
        today_platform = get_today_platform()
        if today_platform is None:
            log("😴 今天是周日，休息日！不爬取")
            log("   如需强制爬取，使用 --platform 或 --all 参数")
            return
        platforms_to_crawl = [today_platform]

    log("=" * 60)
    log("🛡️  安全爬虫 - 模拟真人行为")
    log("=" * 60)
    log(f"📅 日期: {datetime.now().strftime('%Y-%m-%d %A')}")
    log(f"🎯 目标平台: {', '.join(platforms_to_crawl)}")
    log(f"🔑 Session: {web_session[:8]}...{web_session[-4:]}")
    log(f"🌐 代理: {proxy or '无（建议配置proxy.txt！）'}")
    log(f"📄 每关键词页数: {args.pages}")
    log(f"🔄 断点续爬: {'是' if args.resume and resume_progress else '否'}")
    log(f"🏗️  自动构建: {'是' if args.auto_build else '否'}")
    log("")

    if not proxy:
        log("⚠️  警告: 未配置代理IP！强烈建议配置 proxy.txt")
        log("   创建 proxy.txt 文件，每行一个代理地址：")
        log("   socks5://user:pass@host:port")
        log("")

    if args.dry_run:
        log("🧪 试运行模式 - 只显示计划，不实际爬取")
        for p_name in platforms_to_crawl:
            config = PLATFORMS_SEARCH[p_name]
            keywords = [kw for kws in config['keywords'].values() for kw in kws]
            log(f"\n  {config['icon']} {p_name}: {len(keywords)} 个关键词")
            for cat, kws in config['keywords'].items():
                log(f"    {cat}: {', '.join(kws)}")
        return

    # 创建会话
    log("📡 初始化会话...")
    try:
        xhs = await create_xhs_session(proxy=proxy, web_session=web_session)
        log("✅ 会话创建成功")
    except Exception as e:
        log(f"❌ 会话创建失败: {e}")
        return

    # Session 健康检查
    if not args.skip_health_check:
        log("🔍 检查 Session 状态...")
        is_healthy = await check_session_health(xhs)
        if not is_healthy:
            log("🚨 Session 已失效！请更新 cookie.txt 后重试")
            log("   步骤：")
            log("   1. 在浏览器中打开 xiaohongshu.com 并登录")
            log("   2. 从 Cookie 中复制 web_session 值")
            log("   3. 粘贴到 cookie.txt 文件中")
            await xhs.close_session()
            return

    human = HumanSimulator()
    all_new_notes = []
    risk_detected = False
    completed_keywords_all = set(resume_progress.get('completed_keywords', []))

    # 预加载已有数据的 note_id 集合（增量优化：避免重复爬取）
    existing_note_ids = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_note_ids = {n['note_id'] for n in existing_data.get('notes', []) if n.get('note_id')}
                log(f"📂 已有 {len(existing_note_ids)} 条笔记（增量模式：只爬新数据）")
        except Exception:
            pass

    for p_idx, platform_name in enumerate(platforms_to_crawl):
        if risk_detected:
            log(f"\n🚨 风控已触发，跳过剩余平台")
            break

        config = PLATFORMS_SEARCH[platform_name]
        keywords = [(cat, kw) for cat, kws in config['keywords'].items() for kw in kws]

        # 断点续爬：过滤掉已完成的关键词
        if args.resume and completed_keywords_all:
            original_count = len(keywords)
            keywords = [(cat, kw) for cat, kw in keywords if kw not in completed_keywords_all]
            skipped = original_count - len(keywords)
            if skipped > 0:
                log(f"⏩ 跳过 {skipped} 个已完成的关键词")

        if not keywords:
            log(f"✅ {platform_name} 所有关键词已完成！")
            continue

        log(f"\n{'━' * 50}")
        log(f"{config['icon']} 开始爬取: {platform_name} ({len(keywords)} 个关键词)")
        log(f"{'━' * 50}")

        # 开始前先浏览一下推荐页，让行为自然
        log("  📱 先浏览推荐页热身...")
        await human.browse_homefeed(xhs)

        for kw_idx, (category, keyword) in enumerate(keywords):
            if risk_detected:
                break

            try:
                # 偶尔穿插浏览推荐页
                if human.should_browse_homefeed():
                    await human.browse_homefeed(xhs)

                # 是否该休息了
                if human.should_take_break():
                    await human.take_a_break()

                # 搜索
                notes = await safe_search_keyword(xhs, keyword, human, max_pages=args.pages, existing_ids=existing_note_ids)

                for note in notes:
                    note['platform'] = platform_name
                    if category not in note['categories']:
                        note['categories'].insert(0, category)
                    all_new_notes.append(note)

                log(f"  📊 [{kw_idx+1}/{len(keywords)}] '{keyword}' → {len(notes)} 条")

                # 记录已完成的关键词并保存进度
                completed_keywords_all.add(keyword)
                save_progress(platform_name, list(completed_keywords_all), len(all_new_notes))

                # 关键词间间隔
                if kw_idx < len(keywords) - 1:
                    await human.switch_keyword()

            except SessionExpiredError:
                log(f"\n🚨 Session 过期！请更新 cookie.txt")
                log(f"💡 已保存进度，下次使用 --resume 参数可断点续爬")
                risk_detected = True
                break
            except RiskDetectedError as e:
                log(f"\n🚨 风控检测！停止爬取: {e}")
                log(f"   ⏸️  建议等待 24 小时后再试")
                log(f"💡 已保存进度，下次使用 --resume 参数可断点续爬")
                risk_detected = True
                break
            except Exception as e:
                log(f"  ❌ 意外错误: {e}")
                await asyncio.sleep(random.uniform(15, 30))

        # 平台间间隔（如果是全量模式）
        if len(platforms_to_crawl) > 1 and p_idx < len(platforms_to_crawl) - 1:
            rest_time = random.uniform(120, 300)
            log(f"\n  🧘 平台间休息 {int(rest_time)} 秒...")
            await asyncio.sleep(rest_time)

    # 关闭会话
    await xhs.close_session()

    if not all_new_notes:
        log("\n⚠️ 本次未获取到新数据")
        if risk_detected:
            log("   原因: 风控触发，请检查账号状态")
        return

    # 去重合并
    log(f"\n📦 合并数据...")
    all_notes = merge_with_existing(all_new_notes)

    # 保存
    output = build_output(all_notes)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 统计
    log(f"\n{'=' * 60}")
    log(f"✅ 爬取完成！本次新增 {len(all_new_notes)} 条，总计 {len(all_notes)} 条")
    log(f"{'=' * 60}")

    for p_name, p_data in output["meta"]["platform_stats"].items():
        icon = PLATFORMS_SEARCH.get(p_name, {}).get("icon", "📌")
        log(f"  {icon} {p_name}: {p_data['total']} 条")

    ss = output["meta"]["sentiment_stats"]
    log(f"\n😊 正面 {ss['positive']} | 😐 中性 {ss['neutral']} | 😡 负面 {ss['negative']}")
    log(f"\n💾 数据已保存到: {OUTPUT_FILE}")

    if risk_detected:
        log(f"\n⚠️ 注意: 爬取过程中触发了风控，数据可能不完整")
        log(f"   建议: 等待24小时后使用 --resume 断点续爬剩余关键词")
    else:
        # 完全成功，清除进度
        clear_progress()

    # 自动构建 Netlify 部署版
    if args.auto_build:
        log(f"\n🏗️  自动构建 Netlify 部署版...")
        auto_build_netlify()

    log(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
