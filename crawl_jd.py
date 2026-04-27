"""
只爬取京东支付相关数据，合并到 real_data.json
"""
import json, asyncio, random, os, re, sys
from datetime import datetime
from real_crawl import (
    extract_all_xhs_cookies, classify_note, analyze_sentiment,
    search_keyword, build_output, SEARCH_KEYWORDS
)

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
except ImportError:
    print("❌ 缺少 playwright 或 playwright_stealth")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'real_data.json')

# 只爬京东支付
JD_CONFIG = SEARCH_KEYWORDS.get("京东支付")
if not JD_CONFIG:
    print("❌ real_crawl.py 中没有京东支付配置")
    sys.exit(1)


async def main():
    print("=" * 60)
    print("🚀 京东支付专项爬取")
    print("=" * 60)

    # 读取现有数据
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        existing = json.load(f)
    existing_notes = existing.get('notes', [])
    existing_ids = set(n.get('note_id', '') for n in existing_notes)
    print(f"📊 现有数据: {len(existing_notes)} 条笔记")

    # 提取 cookie
    print("\n📦 提取 Chrome Cookie...")
    xhs_cookies = extract_all_xhs_cookies()
    has_ws = any(c['name'] == 'web_session' for c in xhs_cookies)
    if not has_ws:
        print("⚠️ 未找到 web_session，可能受限")
    print(f"  共 {len(xhs_cookies)} 条 cookie")

    all_notes = []
    api_results_collector = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        if xhs_cookies:
            await context.add_cookies(xhs_cookies)

        page = await context.new_page()
        stealth = Stealth(
            navigator_platform_override="MacIntel",
            navigator_vendor_override="Google Inc.",
        )
        await stealth.apply_stealth_async(page)

        # API 拦截
        async def on_response(response):
            url = response.url
            if 'api/sns/web/v1/search/notes' in url:
                try:
                    data = await response.json()
                    if data and data.get('code') == 0:
                        items = data.get('data', {}).get('items', [])
                        current_kw = getattr(page, '_current_keyword', '')
                        current_platform = getattr(page, '_current_platform', '')
                        current_category = getattr(page, '_current_category', '')
                        for item in items:
                            nc = item.get('note_card', item)
                            user_info = nc.get('user', {})
                            interact = nc.get('interact_info', {})
                            nid = item.get('id', nc.get('note_id', ''))
                            xsec = item.get('xsec_token', '')
                            title = nc.get('display_title', '') or ''
                            desc = nc.get('desc', '') or ''
                            full_text = f"{title} {desc}"
                            link = f"https://www.xiaohongshu.com/explore/{nid}" if nid else ''
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
                            cats = [current_category] + [c for c in classify_note(full_text) if c != current_category]
                            api_results_collector.append({
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

        page.on("response", on_response)

        # 访问首页让 cookie 生效
        print("  🏠 访问小红书首页...")
        try:
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
        except Exception:
            pass

        cookies_check = await context.cookies("https://www.xiaohongshu.com")
        ws_check = [c for c in cookies_check if c['name'] == 'web_session']
        if ws_check:
            print(f"  ✅ web_session 已注入: {ws_check[0]['value'][:20]}...")

        # 爬取京东支付关键词
        print(f"\n🔍 开始爬取京东支付 ({len(JD_CONFIG['keywords'])} 个关键词)...")
        seen_ids = set()

        for i, (keyword, category) in enumerate(JD_CONFIG["keywords"]):
            print(f"\n[{i+1}/{len(JD_CONFIG['keywords'])}] 搜索: {keyword} ({category})")
            page._current_keyword = keyword
            page._current_platform = "京东支付"
            page._current_category = category

            notes = await search_keyword(page, keyword, "京东支付", category, api_results_collector)

            for note in notes:
                nid = note['note_id']
                if nid and nid not in seen_ids and nid not in existing_ids:
                    seen_ids.add(nid)
                    all_notes.append(note)

            print(f"  ✅ {keyword}: 新增 {len(notes)} 条 (京东累计 {len(all_notes)})")

            delay = random.uniform(3, 6)
            print(f"  ⏳ 等待 {delay:.1f}s...")
            await asyncio.sleep(delay)

        page.remove_listener("response", on_response)
        await context.close()
        await browser.close()

    print(f"\n📊 京东支付新爬取: {len(all_notes)} 条")

    if all_notes:
        # 合并到现有数据
        merged_notes = existing_notes + all_notes
        output = build_output(merged_notes)

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"✅ 已合并！总计: {len(merged_notes)} 条笔记")
        for p_name, p_data in output["meta"]["platform_stats"].items():
            icon = SEARCH_KEYWORDS.get(p_name, {}).get("icon", "📌")
            print(f"  {icon} {p_name}: {p_data['total']} 条")
        return True
    else:
        print("⚠️ 未爬到京东支付数据，尝试确保 platform_stats 中有京东支付...")
        # 即使没爬到数据，也确保 platform_stats 中有京东支付
        meta = existing.get('meta', {})
        ps = meta.get('platform_stats', {})
        if '京东支付' not in ps:
            ps['京东支付'] = {"total": 0, "category_stats": {}, "sentiment_stats": {"positive": 0, "negative": 0, "neutral": 0}}
        # 确保 platforms_config 中有京东支付
        pc = meta.get('platforms_config', {})
        if '京东支付' not in pc:
            pc['京东支付'] = {"icon": "💎", "color": "#E4393C", "categories": ["支付", "贷款", "理财", "AI", "海外", "组织架构", "客诉", "其他"]}
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print("✅ 已更新 platform_stats，但数据仍为 0")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("\n🎉 完成！请重新运行 build_netlify.py 构建部署版")
