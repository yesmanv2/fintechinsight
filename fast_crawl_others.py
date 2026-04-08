"""
快速爬虫 - 专门爬其他5个平台的核心关键词
每个平台 5-6 个核心关键词，每个 2 页
预计 15-20 分钟完成，获取每平台 100-200 条数据
"""
import asyncio, json, os, random, re, sys
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'other_platforms_data.json')

# ===== 其他5个平台的核心关键词 =====
SEARCH_KEYWORDS = {
    "支付宝": {
        "icon": "💙", "color": "#1677FF",
        "keywords": [
            ("支付宝", "支付", 3),
            ("花呗", "贷款", 3),
            ("借呗", "贷款", 2),
            ("余额宝", "理财", 2),
            ("芝麻信用", "支付", 2),
            ("蚂蚁集团", "组织架构", 2),
            ("支付宝投诉", "客诉", 2),
            ("碰一下支付", "支付", 2),
        ],
    },
    "抖音支付": {
        "icon": "🖤", "color": "#FE2C55",
        "keywords": [
            ("抖音支付", "支付", 3),
            ("抖音月付", "贷款", 2),
            ("DOU分期", "贷款", 2),
            ("抖音放心借", "贷款", 2),
            ("抖音电商支付", "支付", 2),
            ("抖音支付投诉", "客诉", 2),
        ],
    },
    "美团支付": {
        "icon": "💛", "color": "#FFC300",
        "keywords": [
            ("美团支付", "支付", 3),
            ("美团月付", "贷款", 2),
            ("美团借钱", "贷款", 2),
            ("美团买单", "支付", 2),
            ("大众点评支付", "支付", 2),
            ("美团支付投诉", "客诉", 2),
        ],
    },
    "云闪付": {
        "icon": "🔴", "color": "#E60012",
        "keywords": [
            ("云闪付", "支付", 3),
            ("银联云闪付", "支付", 2),
            ("数字人民币", "支付", 2),
            ("云闪付优惠", "支付", 2),
            ("云闪付投诉", "客诉", 2),
        ],
    },
    "京东支付": {
        "icon": "💎", "color": "#E4393C",
        "keywords": [
            ("京东支付", "支付", 3),
            ("京东白条", "贷款", 3),
            ("京东金条", "贷款", 2),
            ("京东金融", "理财", 2),
            ("京东支付投诉", "客诉", 2),
        ],
    },
}

# ===== 关键词匹配 =====
PLATFORM_KEYWORDS_MAP = {
    "支付宝": ["支付宝", "花呗", "借呗", "余额宝", "芝麻", "蚂蚁", "Alipay", "碰一下",
               "网商银行", "蚂蚁森林", "蚂蚁财富"],
    "抖音支付": ["抖音支付", "抖音月付", "DOU分期", "抖音放心借", "抖音电商", "抖音钱包",
                "字节跳动"],
    "美团支付": ["美团支付", "美团月付", "美团买单", "美团借钱", "大众点评", "美团金融"],
    "云闪付": ["云闪付", "银联", "数字人民币", "闪付", "UnionPay"],
    "京东支付": ["京东支付", "京东白条", "京东金条", "京东金融", "京东钱包"],
}


def is_relevant(text, platform):
    text_lower = text.lower()
    keywords = PLATFORM_KEYWORDS_MAP.get(platform, [])
    return any(kw.lower() in text_lower for kw in keywords)


def classify_note(text):
    categories = []
    text_lower = text.lower()
    rules = [
        ("客诉", ["投诉", "被骗", "坑人", "维权", "退款难", "扣费", "乱扣", "盗刷", "差评", "举报", "骗局"]),
        ("贷款", ["花呗", "借呗", "白条", "金条", "月付", "分期", "放心借", "借钱", "贷款", "信用额度", "还款", "逾期"]),
        ("理财", ["余额宝", "理财", "基金", "收益", "利息", "定期", "投资", "保险"]),
        ("AI", ["ai", "人工智能", "大模型", "智能", "gpt", "机器人"]),
        ("海外", ["境外", "海外", "跨境", "汇款", "外币", "visa", "mastercard"]),
        ("组织架构", ["集团", "上市", "ipo", "ceo", "总裁", "架构", "组织"]),
        ("支付", ["支付", "付款", "收款", "扫码", "转账", "红包", "碰一下"]),
    ]
    for cat, keywords in rules:
        if any(kw in text_lower for kw in keywords):
            categories.append(cat)
    if not categories:
        categories.append("其他")
    return categories


def analyze_sentiment(text):
    pos_words = ["好用", "方便", "推荐", "不错", "优秀", "惊喜", "棒", "赞", "安全", "放心", "优惠", "省钱"]
    neg_words = ["垃圾", "投诉", "坑人", "差评", "骗", "恶心", "难用", "bug", "扣费", "维权", "被盗", "坑"]
    text_lower = text.lower()
    pos = sum(1 for w in pos_words if w in text_lower)
    neg = sum(1 for w in neg_words if w in text_lower)
    if neg >= 2 or (neg > 0 and pos == 0):
        return "negative"
    if pos >= 2 or (pos > 0 and neg == 0):
        return "positive"
    return "neutral"


def extract_all_xhs_cookies():
    """从 Chrome 浏览器提取小红书 cookie（复用 real_crawl.py 的逻辑）"""
    sys.path.insert(0, BASE_DIR)
    from real_crawl import extract_all_xhs_cookies as _extract
    return _extract()


async def search_keyword_pages(page, keyword, platform, category, max_pages, api_collector):
    """搜索一个关键词的多页结果"""
    results = []
    for pg in range(1, max_pages + 1):
        try:
            before_count = len(api_collector)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
            if pg > 1:
                search_url += f"&page={pg}"

            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)

            # 滚动触发加载
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(0.8)

            await asyncio.sleep(2)

            new_items = api_collector[before_count:]
            relevant = [item for item in new_items if is_relevant(
                f"{item.get('title', '')} {item.get('desc', '')}", platform
            )]

            print(f"      第{pg}页: API拦截 {len(new_items)} 条, 相关 {len(relevant)} 条")
            results.extend(relevant)

            if len(new_items) == 0:
                print(f"      第{pg}页: 无新数据，停止翻页")
                break

        except Exception as e:
            print(f"      第{pg}页异常: {e}")
            break

    return results


def build_output(all_notes):
    """构建输出数据"""
    platform_stats = {}
    platforms_config = {}
    for p_name, p_cfg in SEARCH_KEYWORDS.items():
        platforms_config[p_name] = {
            "icon": p_cfg["icon"],
            "color": p_cfg["color"],
            "categories": list(set(kw[1] for kw in p_cfg["keywords"])),
        }

    for note in all_notes:
        p = note.get('platform', '未知')
        if p not in platform_stats:
            platform_stats[p] = {"total": 0, "category_stats": {}, "sentiment_stats": {"positive": 0, "negative": 0, "neutral": 0}}
        platform_stats[p]["total"] += 1
        for cat in note.get("categories", []):
            platform_stats[p]["category_stats"][cat] = platform_stats[p]["category_stats"].get(cat, 0) + 1
        s = note.get("sentiment", "neutral")
        platform_stats[p]["sentiment_stats"][s] = platform_stats[p]["sentiment_stats"].get(s, 0) + 1

    sentiment_stats = {"positive": 0, "negative": 0, "neutral": 0}
    for ps in platform_stats.values():
        for k in sentiment_stats:
            sentiment_stats[k] += ps["sentiment_stats"].get(k, 0)

    return {
        "meta": {
            "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "total_notes": len(all_notes),
            "sentiment_stats": sentiment_stats,
            "platform_stats": platform_stats,
            "platforms_config": platforms_config,
            "is_demo": False,
            "data_range": "真实爬取数据",
        },
        "notes": all_notes,
    }


async def main():
    print("=" * 60)
    print("🚀 快速爬虫 - 爬取其他 5 个支付平台核心关键词")
    print("=" * 60)

    # 从 cookie.txt 读取
    xhs_cookies = extract_all_xhs_cookies()
    if not xhs_cookies:
        print("❌ cookie.txt 不存在或为空")
        return False

    ws = [c for c in xhs_cookies if c['name'] == 'web_session']
    if not ws:
        print("❌ 无 web_session")
        return False
    print(f"✅ Cookie 加载成功 ({len(xhs_cookies)} 条)")

    total_keywords = sum(len(cfg["keywords"]) for cfg in SEARCH_KEYWORDS.values())
    print(f"📊 计划: {len(SEARCH_KEYWORDS)} 平台, {total_keywords} 关键词\n")

    all_notes = []
    seen_ids = set()
    api_results_collector = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-gpu'],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        await context.add_cookies(xhs_cookies)
        page = await context.new_page()

        stealth = Stealth(
            navigator_platform_override="MacIntel",
            navigator_vendor_override="Google Inc.",
            navigator_user_agent_override="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        await stealth.apply_stealth_async(page)

        _current_kw = ''
        _current_platform = ''
        _current_category = ''

        async def on_response(response):
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

                                cover = ''
                                imgs = nc.get('image_list', [])
                                if imgs and isinstance(imgs[0], dict):
                                    cover = imgs[0].get('url_default', '') or imgs[0].get('url', '')
                                    if not cover and imgs[0].get('info_list'):
                                        cover = imgs[0]['info_list'][0].get('url', '')

                                cats = [_current_category] + [c for c in classify_note(full_text) if c != _current_category]

                                api_results_collector.append({
                                    "_keyword": _current_kw,
                                    "note_id": nid,
                                    "platform": _current_platform,
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
                                    "keyword_tags": [_current_kw, _current_category],
                                    "search_keyword": _current_kw,
                                    "xsec_token": xsec,
                                    "sentiment": analyze_sentiment(full_text),
                                    "is_deleted": False,
                                    "deleted_at": "",
                                    "snapshot_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
                                })
                except Exception:
                    pass

        page.on("response", on_response)

        # 访问首页激活 cookie
        try:
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
        except Exception:
            pass

        current = 0
        for platform, config in SEARCH_KEYWORDS.items():
            print(f"\n{'─' * 50}")
            print(f"{config['icon']} {platform} ({len(config['keywords'])} 个关键词)")
            print(f"{'─' * 50}")
            platform_count = 0

            for keyword, category, max_pages in config["keywords"]:
                current += 1
                print(f"\n  [{current}/{total_keywords}] 🔍 {keyword} (分类:{category}, {max_pages}页)")

                _current_kw = keyword
                _current_platform = platform
                _current_category = category

                try:
                    notes = await search_keyword_pages(page, keyword, platform, category, max_pages, api_results_collector)
                    new_count = 0
                    for note in notes:
                        nid = note['note_id']
                        if nid and nid not in seen_ids:
                            seen_ids.add(nid)
                            all_notes.append(note)
                            new_count += 1
                    platform_count += new_count
                    print(f"    ✅ {keyword}: 新增 {new_count} 条 (平台 {platform_count}, 总计 {len(all_notes)})")
                except Exception as e:
                    print(f"    ❌ 异常: {e}")

                delay = random.uniform(2, 4)
                await asyncio.sleep(delay)

            print(f"\n  📊 {platform}: {platform_count} 条\n")

        page.remove_listener("response", on_response)
        await context.close()
        await browser.close()

    if not all_notes:
        print("\n❌ 未获取到数据")
        return False

    output = build_output(all_notes)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"🎉 完成！{len(all_notes)} 条数据")
    print(f"{'=' * 60}")
    for p_name, p_data in output["meta"]["platform_stats"].items():
        print(f"  {SEARCH_KEYWORDS[p_name]['icon']} {p_name}: {p_data['total']} 条")
    print(f"\n💾 保存到: {OUTPUT_FILE}")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
