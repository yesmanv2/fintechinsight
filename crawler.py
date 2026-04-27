"""
支付行业小红书舆情爬虫 - 真实数据版
使用 xiaohongshutools 技能搜索多平台支付相关内容

使用方式:
    1. 无登录态（游客 + 推荐页）: python3 crawler.py
    2. 有登录态（搜索接口）:      python3 crawler.py --session YOUR_WEB_SESSION_COOKIE
    3. 从文件读取 cookie:         python3 crawler.py --session-file cookie.txt

获取 web_session cookie:
    1. 浏览器打开 https://www.xiaohongshu.com 并登录
    2. F12 → Application → Cookies → 找到 web_session 字段
    3. 复制其值
"""
import asyncio
import sys
import os
import json
import time
import random
import re
import argparse
from datetime import datetime

# 添加技能路径
SKILL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills', 'xiaohongshutools', 'scripts')
sys.path.insert(0, SKILL_PATH)

from request.web.xhs_session import create_xhs_session

# ==================== 配置 ====================

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')

# 多平台搜索关键词配置
PLATFORMS_SEARCH = {
    "支付宝": {
        "icon": "💙", "color": "#1677FF",
        "keywords": {
            "支付": ["支付宝支付", "支付宝扫码", "支付宝转账", "支付宝碰一碰"],
            "贷款": ["花呗", "借呗", "支付宝贷款", "蚂蚁借呗"],
            "理财": ["余额宝", "支付宝理财", "蚂蚁财富", "支付宝基金"],
            "AI":   ["支付宝AI", "蚂蚁AI", "支付宝智能"],
            "海外": ["支付宝海外", "Alipay+", "支付宝出境"],
            "组织架构": ["蚂蚁集团", "支付宝裁员", "蚂蚁金服"],
            "客诉": ["支付宝投诉", "支付宝客服", "支付宝问题"],
        },
    },
    "微信支付": {
        "icon": "💚", "color": "#07C160",
        "keywords": {
            "支付": ["微信支付", "微信扫码", "微信红包", "微信刷掌"],
            "贷款": ["微粒贷", "微信分付", "微信借钱"],
            "理财": ["零钱通", "微信理财"],
            "AI":   ["腾讯混元", "微信AI"],
            "客诉": ["微信支付投诉", "微信支付问题"],
        },
    },
    "抖音支付": {
        "icon": "🖤", "color": "#FE2C55",
        "keywords": {
            "支付": ["抖音支付", "抖音团购", "抖音外卖"],
            "贷款": ["放心借", "抖音借钱"],
            "AI":   ["豆包AI", "抖音AI"],
            "客诉": ["抖音退款", "抖音投诉"],
        },
    },
    "美团支付": {
        "icon": "💛", "color": "#FFC300",
        "keywords": {
            "支付": ["美团支付", "美团外卖", "美团买单", "美团闪购"],
            "贷款": ["美团月付", "美团借钱"],
            "AI":   ["美团AI", "美团无人配送"],
            "客诉": ["美团投诉", "美团退款"],
        },
    },
    "云闪付": {
        "icon": "🔴", "color": "#E60012",
        "keywords": {
            "支付": ["云闪付", "银联支付", "Apple Pay银联"],
            "海外": ["银联海外", "银联境外"],
            "客诉": ["云闪付投诉", "云闪付问题"],
        },
    },
}

# 分类识别规则
CLASSIFY_RULES = {
    "支付": ["支付", "付款", "扫码", "转账", "收款", "二维码", "刷脸", "碰一碰", "条码", "红包", "NFC", "团购", "外卖", "买单", "闪购"],
    "贷款": ["贷款", "花呗", "借呗", "借钱", "分期", "信用", "额度", "还款", "逾期", "催收", "微粒贷", "分付", "放心借", "月付"],
    "理财": ["理财", "余额宝", "基金", "投资", "收益", "定期", "蚂蚁财富", "股票", "保险", "零钱通"],
    "AI":   ["ai", "人工智能", "智能", "大模型", "混元", "豆包", "灵光", "无人配送", "机器人"],
    "海外": ["海外", "出境", "境外", "国际", "alipay", "外币", "退税", "汇率", "出国"],
    "组织架构": ["蚂蚁集团", "人事", "裁员", "组织", "蚂蚁金服", "上市", "ipo", "高管"],
    "客诉": ["投诉", "客服", "坑", "吐槽", "问题", "bug", "骗", "盗刷", "冻结", "封号", "垃圾", "差评", "难用", "退款"],
}

# 情感分析关键词
SENTIMENT_POSITIVE = ["好用", "方便", "不错", "推荐", "喜欢", "划算", "优惠", "开心", "赞", "省钱", "给力",
                      "太爽了", "太强了", "牛", "真香", "解决了", "成功", "终于", "感谢", "惊喜", "便宜"]
SENTIMENT_NEGATIVE = ["难用", "垃圾", "投诉", "骗", "坑", "差评", "恶心", "无语", "崩了", "封号", "冻结",
                      "盗刷", "焦虑", "过分", "退款", "催收", "受不了", "太慢", "坑人", "失望", "逾期",
                      "问题", "吐槽", "差劲", "闪退"]


def classify_note(text: str) -> list:
    """根据笔记内容智能分类"""
    text_lower = text.lower()
    matched = []
    for category, keywords in CLASSIFY_RULES.items():
        for kw in keywords:
            if kw in text_lower:
                matched.append(category)
                break
    return matched if matched else ["其他"]


def analyze_sentiment(text: str) -> str:
    """简单情感分析"""
    text_lower = text.lower()
    pos_score = sum(1 for w in SENTIMENT_POSITIVE if w in text_lower)
    neg_score = sum(1 for w in SENTIMENT_NEGATIVE if w in text_lower)
    if neg_score > pos_score:
        return "negative"
    elif pos_score > neg_score:
        return "positive"
    return "neutral"


def detect_platform(text: str, search_keyword: str) -> str:
    """从文本和搜索关键词推断平台"""
    combined = f"{text} {search_keyword}".lower()
    platform_patterns = {
        "支付宝": ["支付宝", "花呗", "借呗", "余额宝", "蚂蚁", "alipay"],
        "微信支付": ["微信支付", "微信红包", "微粒贷", "零钱通", "微信扫码", "微信刷掌", "分付"],
        "抖音支付": ["抖音支付", "抖音团购", "放心借", "抖音外卖", "豆包"],
        "美团支付": ["美团支付", "美团外卖", "美团月付", "美团买单", "美团闪购"],
        "云闪付": ["云闪付", "银联", "apple pay"],
    }
    for platform, patterns in platform_patterns.items():
        for p in patterns:
            if p in combined:
                return platform
    return "支付宝"  # 默认


def parse_note_item(item: dict, search_keyword: str, platform_hint: str = "") -> dict:
    """解析单条笔记数据，输出格式兼容前端"""
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
    platform = platform_hint or detect_platform(full_text, search_keyword)

    # 笔记链接
    link = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec_token:
        link += f"?xsec_token={xsec_token}&xsec_source=pc_search"

    # 时间处理
    timestamp = note_card.get('time', 0) or item.get('time', 0)
    time_str = ''
    if timestamp:
        try:
            if timestamp > 1e12:
                timestamp = timestamp / 1000
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass

    # 封面图
    cover = ''
    image_list = note_card.get('image_list', []) or note_card.get('images_list', [])
    if image_list:
        first_img = image_list[0]
        if isinstance(first_img, dict):
            cover = first_img.get('url_default', '') or first_img.get('url', '')
            if not cover and first_img.get('info_list'):
                cover = first_img['info_list'][0].get('url', '')

    # 关键词标签
    keyword_tags = []
    if search_keyword:
        keyword_tags.append(search_keyword)
    # 从标题中提取关键词
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


async def crawl_keyword(xhs, keyword: str, max_pages: int = 2) -> list:
    """爬取单个关键词的笔记"""
    notes = []
    for page in range(1, max_pages + 1):
        try:
            print(f"  📥 搜索: '{keyword}' 第 {page} 页...")
            res = await xhs.apis.note.search_notes(keyword, page=page, page_size=20, sort="general", note_type=0)
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
            await asyncio.sleep(random.uniform(2, 5))

        except Exception as e:
            error_str = str(e)
            if '-104' in error_str or '没有权限' in error_str:
                print(f"  🔒 搜索接口需要登录态！请提供 web_session cookie")
                return notes
            print(f"  ❌ 搜索 '{keyword}' 第 {page} 页失败: {e}")
            await asyncio.sleep(random.uniform(3, 6))
            break

    return notes


async def crawl_homefeed(xhs, max_pages: int = 5) -> list:
    """通过推荐页获取笔记（游客模式可用）"""
    from request.web.apis.note import HomeFeedCategory
    notes = []
    cursor_score = ""
    note_index = 0

    for page in range(max_pages):
        try:
            print(f"  📥 推荐页 第 {page + 1} 页...")
            res = await xhs.apis.note.get_homefeed(
                category=HomeFeedCategory.RECOMMEND,
                cursor_score=cursor_score,
                note_index=note_index
            )
            data = await res.json()

            if not data or data.get('code') != 0:
                error_msg = data.get('msg', 'unknown') if data else 'empty'
                print(f"  ⚠️ 推荐页第 {page+1} 页返回异常: {error_msg}")
                break

            items = data.get('data', {}).get('items', [])
            if not items:
                print(f"  ℹ️ 推荐页第 {page+1} 页无更多结果")
                break

            cursor_score = data.get('data', {}).get('cursor_score', '')
            note_index += len(items)

            for item in items:
                try:
                    note = parse_note_item(item, "推荐页")
                    if note['title']:
                        notes.append(note)
                except Exception as e:
                    print(f"  ⚠️ 解析推荐笔记失败: {e}")

            print(f"  ✅ 推荐页第 {page+1} 页获取 {len(items)} 条")
            await asyncio.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"  ❌ 推荐页第 {page+1} 页失败: {e}")
            break

    return notes


def build_output(all_notes: list) -> dict:
    """构建输出数据，完全兼容前端格式"""
    total_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
    platform_stats = {}

    # 各平台的分类配置
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

    # 已删除统计
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
            "note": "真实小红书数据，通过 xiaohongshutools 爬取"
        },
        "notes": all_notes
    }


def merge_with_existing(new_notes: list, existing_file: str) -> list:
    """与已有数据合并，避免重复"""
    existing_notes = []
    if os.path.exists(existing_file):
        try:
            with open(existing_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing_notes = data.get("notes", [])
                print(f"📂 已有数据: {len(existing_notes)} 条")
        except Exception:
            pass

    existing_ids = {n["note_id"] for n in existing_notes}
    added = 0
    for note in new_notes:
        if note["note_id"] not in existing_ids:
            existing_notes.append(note)
            existing_ids.add(note["note_id"])
            added += 1

    print(f"📊 新增 {added} 条 (去重后), 跳过 {len(new_notes) - added} 条重复")
    return existing_notes


async def main():
    parser = argparse.ArgumentParser(description='小红书舆情爬虫 - 真实数据')
    parser.add_argument('--session', type=str, default=None,
                        help='小红书 web_session cookie 值')
    parser.add_argument('--session-file', type=str, default=None,
                        help='存放 web_session cookie 的文件路径')
    parser.add_argument('--pages', type=int, default=2,
                        help='每个关键词搜索页数 (默认2)')
    parser.add_argument('--platforms', type=str, nargs='*', default=None,
                        help='指定爬取的平台 (默认全部)')
    parser.add_argument('--no-merge', action='store_true',
                        help='不与已有数据合并，全新覆盖')
    args = parser.parse_args()

    # 获取 web_session
    web_session = args.session
    if args.session_file:
        try:
            with open(args.session_file, 'r') as f:
                web_session = f.read().strip()
                print(f"📄 从文件读取 web_session: {web_session[:8]}...{web_session[-4:]}")
        except Exception as e:
            print(f"❌ 读取 session 文件失败: {e}")
            return

    print("=" * 60)
    print("🔍 支付行业小红书舆情爬虫 - 真实数据版")
    print("=" * 60)

    if web_session:
        print(f"🔑 使用登录态模式 (session: {web_session[:8]}...)")
    else:
        print("👤 使用游客模式（仅能获取推荐页数据）")
        print("💡 提示: 提供 --session 参数可使用搜索接口获取更多数据")

    # 创建会话
    print("\n📡 正在初始化小红书会话...")
    try:
        xhs = await create_xhs_session(proxy=None, web_session=web_session)
        print("✅ 会话创建成功\n")
    except Exception as e:
        print(f"❌ 会话创建失败: {e}")
        return

    all_notes = []
    seen_ids = set()

    if web_session:
        # ========== 有登录态：使用搜索接口 ==========
        platforms = args.platforms or list(PLATFORMS_SEARCH.keys())
        for platform_name in platforms:
            if platform_name not in PLATFORMS_SEARCH:
                print(f"⚠️ 未知平台: {platform_name}, 跳过")
                continue
            config = PLATFORMS_SEARCH[platform_name]
            print(f"\n{'─' * 50}")
            print(f"{config['icon']} 正在爬取: {platform_name}")
            print(f"{'─' * 50}")

            for category, keywords in config['keywords'].items():
                for keyword in keywords:
                    notes = await crawl_keyword(xhs, keyword, max_pages=args.pages)
                    for note in notes:
                        if note['note_id'] not in seen_ids:
                            seen_ids.add(note['note_id'])
                            # 确保平台正确
                            note['platform'] = platform_name
                            if category not in note['categories']:
                                note['categories'].insert(0, category)
                            all_notes.append(note)

                    # 关键词间间隔
                    await asyncio.sleep(random.uniform(2, 5))
    else:
        # ========== 游客模式：使用推荐页 ==========
        print("📱 正在从推荐页获取笔记...")
        homefeed_notes = await crawl_homefeed(xhs, max_pages=8)
        for note in homefeed_notes:
            if note['note_id'] not in seen_ids:
                seen_ids.add(note['note_id'])
                all_notes.append(note)

    # 关闭会话
    await xhs.close_session()

    if not all_notes:
        print("\n⚠️ 未获取到任何笔记！")
        if not web_session:
            print("💡 游客模式可能受限，建议提供 web_session cookie:")
            print("   python3 crawler.py --session YOUR_COOKIE_VALUE")
        return

    # 合并或覆盖
    if not args.no_merge:
        all_notes = merge_with_existing(all_notes, OUTPUT_FILE)

    # 构建输出
    output = build_output(all_notes)

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 输出统计
    print(f"\n{'=' * 60}")
    print(f"📊 爬取完成！共 {len(all_notes)} 条笔记")
    print(f"{'=' * 60}")

    for p_name, p_data in output["meta"]["platform_stats"].items():
        icon = PLATFORMS_SEARCH.get(p_name, {}).get("icon", "📌")
        print(f"  {icon} {p_name}: {p_data['total']} 条")

    ss = output["meta"]["sentiment_stats"]
    print(f"\n😊 情感分布: 正面 {ss['positive']} | 😐 中性 {ss['neutral']} | 😡 负面 {ss['negative']}")
    print(f"\n💾 数据已保存到: {OUTPUT_FILE}")
    print(f"🌐 启动服务器: python3 server.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
