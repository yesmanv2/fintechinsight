#!/usr/bin/env python3
"""支付宝续爬 - 从上次断点继续，浏览器绝不重建
   ✅ 跳过已爬过的关键词
   ✅ 浏览器只启动一次，断了就停（绝不重建，不闪）
   ✅ 间隔25-40秒，比之前更保守
"""
import asyncio, json, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from real_crawl import (
    extract_all_xhs_cookies, search_keyword_pages,
    BrowserManager, build_output, SEARCH_KEYWORDS,
)

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'alipay_crawl_data2.json')
PREV = os.path.join(BASE, 'alipay_crawl_data.json')

# 已经爬过的关键词（上一轮完成的）
DONE_KEYWORDS = {
    "支付宝支付", "支付宝碰一下", "支付宝NFC", "支付宝刷脸",
    "支付宝扫码", "支付宝消费券", "支付宝乘车码", "支付宝付款码",
    "支付宝红包", "支付宝数字人民币", "网商贷",
}

async def main():
    cfg = SEARCH_KEYWORDS["支付宝"]
    remaining = [(kw, cat, mp) for kw, cat, mp in cfg["keywords"] if kw not in DONE_KEYWORDS]
    
    print("=" * 55)
    print("💙 支付宝续爬 - 只爬剩余关键词")
    print(f"   已完成: {len(DONE_KEYWORDS)} 个关键词")
    print(f"   剩余: {len(remaining)} 个关键词")
    print("   间隔: 25-40秒（更保守）")
    print("   ⚠️ 浏览器只启动一次，断了就停，绝不重建！")
    print("=" * 55 + "\n")

    xhs_cookies = extract_all_xhs_cookies()
    if not xhs_cookies:
        print("❌ 无法提取Cookie！"); return
    ws = [c for c in xhs_cookies if c['name']=='web_session' and len(c.get('value',''))>10]
    if not ws:
        print("❌ 没有有效web_session"); return
    print(f"✅ 提取到 {len(xhs_cookies)} 条cookie")

    # 加载之前爬到的note_id做去重
    seen = set()
    if os.path.exists(PREV):
        with open(PREV) as f:
            for n in json.load(f).get('notes', []):
                if n.get('note_id'): seen.add(n['note_id'])
        print(f"已有 {len(seen)} 个note_id（跳过重复）")

    total = len(remaining)
    print(f"计划爬取: {total} 个关键词\n")
    for kw, cat, mp in remaining:
        print(f"  待爬: {kw} ({cat}, {mp}页)")

    notes, api_buf = [], []
    mgr = BrowserManager(xhs_cookies, api_buf)
    try:
        await mgr.create_browser()
        print("\n✅ 浏览器就绪（如需扫码请在浏览器窗口操作）")
        print("   扫码完成后将自动开始爬取...\n")

        # 等10秒让cookie生效
        await asyncio.sleep(10)

        cur = 0
        for kw, cat, mp in remaining:
            cur += 1
            actual_mp = min(mp, 3)
            print(f"\n  [{cur}/{total}] 🔍 {kw} (最多{actual_mp}页)")

            # 检查浏览器是否存活——如果断了，直接停！不重建！
            alive = await mgr.is_alive()
            if not alive:
                print("\n  ❌ 浏览器已断开！为避免反复弹窗，直接停止。")
                print(f"  💾 已保存 {len(notes)} 条数据")
                break

            mgr._current_keyword = kw
            mgr._current_platform = "支付宝"
            mgr._current_category = cat
            try:
                res = await search_keyword_pages(mgr.page, kw, "支付宝", cat, actual_mp, api_buf)
                nc = 0
                for n in res:
                    if n['note_id'] and n['note_id'] not in seen:
                        seen.add(n['note_id']); notes.append(n); nc += 1
                print(f"    ✅ +{nc} 条 (本轮累计{len(notes)})")
            except Exception as e:
                err_msg = str(e)[:80]
                print(f"    ❌ 出错: {err_msg}")
                # 检查是否是浏览器崩溃
                if 'closed' in err_msg.lower() or 'destroyed' in err_msg.lower():
                    print("\n  ❌ 浏览器崩溃！直接停止，不重建。")
                    break

            # 每5个关键词保存一次
            if cur % 5 == 0 and notes:
                with open(OUT, 'w') as f:
                    json.dump(build_output(notes), f, ensure_ascii=False)
                print(f"    💾 已保存 {len(notes)} 条到 {os.path.basename(OUT)}")

            # 间隔 25-40 秒（更保守）
            delay = random.uniform(25, 40)
            print(f"    ⏳ 等待 {delay:.0f}s...")
            await asyncio.sleep(delay)

    finally:
        await mgr.cleanup_all()

    if not notes:
        print("\n❌ 未获取新数据"); return

    with open(OUT, 'w') as f:
        json.dump(build_output(notes), f, ensure_ascii=False, indent=2)
    print(f"\n{'='*55}")
    print(f"🎉 续爬完成！本轮新增 {len(notes)} 条")
    print(f"   保存到: {OUT}")
    print(f"{'='*55}")

if __name__ == "__main__":
    asyncio.run(main())
