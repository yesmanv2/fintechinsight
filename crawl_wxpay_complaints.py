"""
微信支付客诉专项爬虫 - 安全版
=================================
安全策略:
  1. headless 无头浏览器（不会弹窗、不会闪）
  2. 关键词间隔 30-60 秒，翻页间隔 15-25 秒（模拟人类）
  3. 每次执行最多爬 3 个关键词（防止触发反爬）
  4. 断点续爬：记录已爬关键词，下次从上次停的地方继续
  5. 遇到 461 立即停止，不再继续请求
  6. 随机模拟滚动和等待行为

使用方式:
    python3 crawl_wxpay_complaints.py                  # 正常执行（每次3个关键词）
    python3 crawl_wxpay_complaints.py --max-keywords 5 # 指定本次最多爬几个关键词
    python3 crawl_wxpay_complaints.py --reset           # 重置断点，从头开始
    python3 crawl_wxpay_complaints.py --test             # 仅测试 session 是否可用
"""
import asyncio
import sys
import os
import json
import random
import argparse
from datetime import datetime

# 添加技能路径
SKILL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills', 'xiaohongshutools', 'scripts')
sys.path.insert(0, SKILL_PATH)

from request.web.xhs_session import create_xhs_session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'wxpay_complaints_raw.json')
COOKIE_FILE = os.path.join(BASE_DIR, 'cookie.txt')
PROGRESS_FILE = os.path.join(BASE_DIR, '.crawl_wxpay_progress.json')

# ===================== 安全配置 =====================
MAX_KEYWORDS_PER_RUN = 3          # 每次执行最多爬几个关键词
PAGE_DELAY_MIN = 15               # 翻页最小等待秒数
PAGE_DELAY_MAX = 25               # 翻页最大等待秒数
KEYWORD_DELAY_MIN = 30            # 关键词间最小等待秒数
KEYWORD_DELAY_MAX = 60            # 关键词间最大等待秒数
MAX_PAGES_PER_KEYWORD = 2         # 每个关键词最多爬几页
MAX_TOTAL_REQUESTS = 10           # 单次运行最大请求数
# ====================================================

# 微信支付客诉相关搜索关键词（按优先级排列）
WXPAY_COMPLAINT_KEYWORDS = [
    "微信支付",
    "微信扣款",
    "微信自动续费",
    "微信支付投诉",
    "微信乱扣费",
    "微信免密支付",
    "微信先用后付",
    "微信支付封号",
    "微信冻结",
    "微信退款",
    "微信客服投诉",
]

# 情感分析关键词
SENTIMENT_NEGATIVE = [
    "难用", "垃圾", "投诉", "骗", "坑", "差评", "恶心", "无语", "崩了", "封号", "冻结",
    "盗刷", "焦虑", "过分", "退款", "催收", "受不了", "太慢", "坑人", "失望", "逾期",
    "问题", "吐槽", "差劲", "闪退", "扣款", "乱扣", "被扣", "莫名其妙"
]
SENTIMENT_POSITIVE = [
    "好用", "方便", "不错", "推荐", "喜欢", "划算", "优惠", "开心", "赞", "省钱", "给力",
    "太爽了", "太强了", "牛", "真香", "解决了", "成功", "终于", "感谢", "惊喜", "便宜"
]

CLASSIFY_RULES = {
    "支付": ["支付", "付款", "扫码", "转账", "收款", "二维码", "刷脸", "红包", "NFC"],
    "贷款": ["贷款", "花呗", "借呗", "借钱", "分期", "信用", "额度", "还款", "逾期", "催收", "微粒贷", "分付"],
    "理财": ["理财", "基金", "投资", "收益", "定期", "零钱通"],
    "客诉": ["投诉", "客服", "坑", "吐槽", "问题", "bug", "骗", "盗刷", "冻结", "封号", "垃圾", "差评", "难用", "退款", "扣款", "乱扣"],
}


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


def parse_note_item(item: dict, search_keyword: str) -> dict:
    """解析单条笔记数据"""
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

    keyword_tags = [search_keyword]
    for cat in categories:
        if cat not in keyword_tags and cat != "其他":
            keyword_tags.append(cat)

    return {
        "note_id": note_id,
        "title": title,
        "desc": desc[:500],
        "time": time_str,
        "author": user_info.get('nickname', '未知'),
        "liked_count": str(interact_info.get('liked_count', note_card.get('liked_count', '0'))),
        "comment_count": str(interact_info.get('comment_count', note_card.get('comment_count', '0'))),
        "collected_count": str(interact_info.get('collected_count', note_card.get('collected_count', '0'))),
        "sentiment": sentiment,
        "link": link,
        "keyword_tags": keyword_tags,
        "categories": categories,
        "category": categories[0] if categories else "其他",
    }


# ===================== 断点续爬 =====================

def load_progress() -> dict:
    """加载爬取进度"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed_keywords": [], "last_run": "", "total_runs": 0}


def save_progress(progress: dict):
    """保存爬取进度"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_pending_keywords(progress: dict) -> list:
    """获取还没爬过的关键词"""
    completed = set(progress.get("completed_keywords", []))
    return [kw for kw in WXPAY_COMPLAINT_KEYWORDS if kw not in completed]


# ===================== 安全爬取 =====================

async def safe_crawl_keyword(xhs, keyword: str, request_counter: dict) -> tuple:
    """
    安全爬取单个关键词
    返回: (notes_list, hit_limit: bool)
    hit_limit=True 表示触发了反爬，应立即停止
    """
    notes = []
    hit_limit = False

    for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
        # 检查总请求数限制
        if request_counter["count"] >= MAX_TOTAL_REQUESTS:
            print(f"  ⛔ 达到单次运行请求上限 ({MAX_TOTAL_REQUESTS})，安全停止")
            hit_limit = True
            break

        try:
            print(f"  📥 搜索: '{keyword}' 第 {page} 页 (总请求 #{request_counter['count']+1})...")
            request_counter["count"] += 1

            res = await xhs.apis.note.search_notes(
                keyword, page=page, page_size=20,
                sort="time_descending", note_type=0
            )
            data = await res.json()

            if not data or data.get('code') != 0:
                error_msg = data.get('msg', 'unknown') if data else 'empty response'
                print(f"  ⚠️ '{keyword}' 第 {page} 页返回异常: {error_msg}")
                break

            items = data.get('data', {}).get('items', [])
            if not items:
                print(f"  ℹ️ '{keyword}' 第 {page} 页无更多结果")
                break

            for item in items:
                try:
                    note = parse_note_item(item, keyword)
                    if note['title']:
                        notes.append(note)
                except Exception as e:
                    print(f"  ⚠️ 解析笔记失败: {e}")

            print(f"  ✅ '{keyword}' 第 {page} 页获取 {len(items)} 条")

            # 翻页等待（模拟人类阅读）
            if page < MAX_PAGES_PER_KEYWORD:
                delay = random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
                print(f"  ⏳ 模拟阅读，等待 {delay:.0f}s...")
                await asyncio.sleep(delay)

        except Exception as e:
            error_str = str(e)
            if '461' in error_str:
                print(f"  🛑 触发 461 反爬限制！立即停止，保护账号安全")
                hit_limit = True
                break
            if '-104' in error_str or '没有权限' in error_str:
                print(f"  🔒 搜索接口需要登录态！")
                hit_limit = True
                break
            print(f"  ❌ 搜索 '{keyword}' 第 {page} 页失败: {e}")
            hit_limit = True
            break

    return notes, hit_limit


async def test_session(web_session: str) -> bool:
    """测试 session 是否可用（只发1个请求）"""
    print("🧪 测试 session 可用性...")
    try:
        xhs = await create_xhs_session(proxy=None, web_session=web_session)
        res = await xhs.apis.note.search_notes("微信", page=1, page_size=1, sort="general", note_type=0)
        data = await res.json()
        await xhs.close_session()

        code = data.get('code', -1) if data else -1
        items = data.get('data', {}).get('items', []) if data else []

        if code == 0 and items:
            print("✅ Session 正常可用！可以安全爬取")
            return True
        elif code == 0:
            print("⚠️ Session 有效但搜索可能仍在限流中")
            return False
        else:
            print(f"❌ Session 异常: code={code}")
            return False
    except Exception as e:
        if '461' in str(e):
            print("❌ 仍处于 461 限流中，请等几小时后再试")
        else:
            print(f"❌ 测试失败: {e}")
        return False


def load_existing_data() -> list:
    """加载现有数据"""
    existing = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = existing.get('notes', []) if isinstance(existing, dict) else []
        except Exception as e:
            print(f"⚠️ 读取已有数据失败: {e}")
    return existing


def merge_and_save(new_notes: list, existing_notes: list) -> int:
    """基于 link 去重合并"""
    existing_links = {n.get('link', '') for n in existing_notes}
    added = 0
    for note in new_notes:
        link = note.get('link', '')
        if link and link not in existing_links:
            existing_notes.append(note)
            existing_links.add(link)
            added += 1

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing_notes, f, ensure_ascii=False, indent=2)

    return added


async def main():
    parser = argparse.ArgumentParser(description='微信支付客诉安全爬虫')
    parser.add_argument('--max-keywords', type=int, default=MAX_KEYWORDS_PER_RUN,
                        help=f'本次最多爬几个关键词 (默认{MAX_KEYWORDS_PER_RUN})')
    parser.add_argument('--reset', action='store_true',
                        help='重置断点进度，从头开始')
    parser.add_argument('--test', action='store_true',
                        help='仅测试 session 是否可用，不爬取')
    args = parser.parse_args()

    print("=" * 60)
    print("🔍 微信支付客诉安全爬虫 - 小红书")
    print(f"📅 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛡️ 安全模式: 每次最多 {args.max_keywords} 个关键词")
    print(f"⏱️ 关键词间隔: {KEYWORD_DELAY_MIN}-{KEYWORD_DELAY_MAX}s")
    print(f"⏱️ 翻页间隔: {PAGE_DELAY_MIN}-{PAGE_DELAY_MAX}s")
    print("=" * 60)

    # 读取 cookie
    web_session = None
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r') as f:
                web_session = f.read().strip()
            print(f"🔑 web_session: {web_session[:8]}...{web_session[-4:]}")
        except Exception as e:
            print(f"⚠️ 读取 cookie 失败: {e}")

    if not web_session:
        print("❌ 未找到 web_session cookie！")
        print("💡 请在 cookie.txt 中放入小红书 web_session 值")
        return 0

    # 仅测试模式
    if args.test:
        ok = await test_session(web_session)
        return 1 if ok else 0

    # 断点进度管理
    progress = load_progress()
    if args.reset:
        progress = {"completed_keywords": [], "last_run": "", "total_runs": 0}
        save_progress(progress)
        print("🔄 已重置爬取进度")

    pending = get_pending_keywords(progress)
    if not pending:
        print("🎉 所有关键词已爬取完毕！")
        print("💡 使用 --reset 可重新从头开始")
        # 重置进度，下次从头循环
        progress["completed_keywords"] = []
        save_progress(progress)
        return 0

    # 本次要爬的关键词
    keywords_this_run = pending[:args.max_keywords]
    print(f"\n📋 待爬关键词 ({len(pending)} 个剩余):")
    for i, kw in enumerate(keywords_this_run):
        print(f"   {i+1}. {kw}")
    remaining_after = len(pending) - len(keywords_this_run)
    if remaining_after > 0:
        print(f"   ... 还有 {remaining_after} 个留到下次")

    # 先测试 session
    session_ok = await test_session(web_session)
    if not session_ok:
        print("\n❌ Session 不可用，跳过本次爬取")
        print("💡 请等待限流解除后再执行（通常需要数小时）")
        return 0

    # 测试通过后等一段时间再开始爬
    pre_delay = random.uniform(10, 20)
    print(f"\n⏳ 测试通过，等待 {pre_delay:.0f}s 后开始正式爬取...\n")
    await asyncio.sleep(pre_delay)

    # 加载已有数据
    existing_notes = load_existing_data()
    print(f"📂 已有数据: {len(existing_notes)} 条帖子")

    # 创建会话
    print("📡 正在初始化会话...")
    try:
        xhs = await create_xhs_session(proxy=None, web_session=web_session)
        print("✅ 会话创建成功\n")
    except Exception as e:
        print(f"❌ 会话创建失败: {e}")
        return 0

    # 爬取
    all_new_notes = []
    seen_ids = set()
    request_counter = {"count": 0}
    completed_this_run = []
    stopped_early = False

    for i, keyword in enumerate(keywords_this_run):
        print(f"\n{'─' * 50}")
        print(f"[{i+1}/{len(keywords_this_run)}] 🔎 {keyword}")
        print(f"{'─' * 50}")

        notes, hit_limit = await safe_crawl_keyword(xhs, keyword, request_counter)

        for note in notes:
            if note['note_id'] and note['note_id'] not in seen_ids:
                seen_ids.add(note['note_id'])
                all_new_notes.append(note)

        completed_this_run.append(keyword)
        print(f"  📊 '{keyword}' 获取 {len(notes)} 条")

        if hit_limit:
            print(f"\n🛑 触发限制，安全停止。已完成 {len(completed_this_run)} 个关键词")
            stopped_early = True
            break

        # 关键词间长等待（核心安全措施）
        if i < len(keywords_this_run) - 1:
            delay = random.uniform(KEYWORD_DELAY_MIN, KEYWORD_DELAY_MAX)
            print(f"  ⏳ 安全间隔，等待 {delay:.0f}s...")
            await asyncio.sleep(delay)

    # 关闭会话
    try:
        await xhs.close_session()
    except Exception:
        pass

    # 更新进度
    progress["completed_keywords"].extend(completed_this_run)
    progress["last_run"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    progress["total_runs"] = progress.get("total_runs", 0) + 1
    if stopped_early:
        # 如果提前停止，最后一个关键词可能没爬完，标记下次重试
        if completed_this_run:
            last_kw = completed_this_run[-1]
            # 如果是因为461停的，这个关键词可能数据不全，下次重新爬
            if hit_limit and last_kw in progress["completed_keywords"]:
                progress["completed_keywords"].remove(last_kw)
    save_progress(progress)

    # 合并并保存
    print(f"\n{'=' * 60}")
    print(f"📊 本次爬取: {len(all_new_notes)} 条笔记 (去自身重复)")
    print(f"📡 总请求数: {request_counter['count']}")

    if all_new_notes:
        added = merge_and_save(all_new_notes, existing_notes)
        print(f"✅ 新增: {added} 条 (基于link去重)")
        print(f"📁 总计: {len(existing_notes)} 条帖子")
        print(f"💾 已保存: {OUTPUT_FILE}")
    else:
        print("⚠️ 本次未获取到新数据")

    # 进度总览
    remaining = get_pending_keywords(progress)
    print(f"\n📋 爬取进度: {len(progress['completed_keywords'])}/{len(WXPAY_COMPLAINT_KEYWORDS)} 个关键词")
    if remaining:
        print(f"   剩余: {', '.join(remaining[:5])}{'...' if len(remaining) > 5 else ''}")
        print(f"💡 下次执行将自动从断点继续")
    else:
        print("🎉 所有关键词已完成！")

    if stopped_early:
        print(f"\n⚠️ 本次因反爬限制提前停止，建议等待 2-4 小时后再执行")

    print("=" * 60)
    return len(all_new_notes)


if __name__ == "__main__":
    result = asyncio.run(main())
