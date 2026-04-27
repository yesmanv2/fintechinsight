#!/usr/bin/env python3
"""重新爬取支付宝 - 有头浏览器扫码一次后安静爬取
   ✅ 浏览器只启动一次
   ✅ 扫码验证后安静运行
   ✅ 间隔20-35秒
"""
import asyncio, json, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from real_crawl import (
    extract_all_xhs_cookies, search_keyword_pages,
    BrowserManager, build_output, SEARCH_KEYWORDS,
)

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'alipay_crawl_data.json')
TARGETS = ["支付宝"]

async def main():
    print("=" * 55)
    print("💙 重新爬取支付宝 - 有头浏览器扫码后安静运行")
    print(f"   关键词数: {len(SEARCH_KEYWORDS['支付宝']['keywords'])}")
    print("   间隔: 20-35秒（降低风险）")
    print("   浏览器只启动一次，不会反复弹窗")
    print("=" * 55 + "\n")

    xhs_cookies = extract_all_xhs_cookies()
    if not xhs_cookies:
        print("❌ 无法提取Cookie！请确保Chrome中已登录小红书"); return
    ws = [c for c in xhs_cookies if c['name']=='web_session' and len(c.get('value',''))>10]
    if not ws:
        print("❌ 没有有效web_session"); return
    print(f"✅ 提取到 {len(xhs_cookies)} 条cookie")

    # 不做去重——这是重爬，要全新的数据
    seen = set()

    kws = {p: SEARCH_KEYWORDS[p] for p in TARGETS if p in SEARCH_KEYWORDS}
    total = sum(len(c["keywords"]) for c in kws.values())
    print(f"计划: {total} 个关键词\n")

    notes, api_buf = [], []
    mgr = BrowserManager(xhs_cookies, api_buf)
    try:
        await mgr.create_browser()
        print("✅ 浏览器就绪（如需扫码请在浏览器窗口操作）")
        print("   扫码完成后将自动开始爬取...\n")

        cur, fails_in_row = 0, 0
        for plat, cfg in kws.items():
            print(f"\n{'─'*50}")
            print(f"{cfg['icon']} {plat} ({len(cfg['keywords'])}词)")
            print(f"{'─'*50}")
            pc = 0
            for kw, cat, mp in cfg["keywords"]:
                cur += 1
                actual_mp = min(mp, 3)  # 每个关键词最多3页，多爬点
                print(f"\n  [{cur}/{total}] 🔍 {kw} (最多{actual_mp}页)")

                # 检查浏览器是否存活
                alive = await mgr.is_alive()
                if not alive:
                    print("  ⚠️ 浏览器已断开，尝试重建...")
                    await mgr.create_browser()
                    print("  ⚠️ 如需重新扫码请在浏览器窗口操作")

                mgr._current_keyword = kw
                mgr._current_platform = plat
                mgr._current_category = cat
                try:
                    res = await search_keyword_pages(mgr.page, kw, plat, cat, actual_mp, api_buf)
                    nc = 0
                    for n in res:
                        if n['note_id'] and n['note_id'] not in seen:
                            seen.add(n['note_id']); notes.append(n); nc += 1
                    pc += nc
                    print(f"    ✅ +{nc} 条 (平台累计{pc}, 总计{len(notes)})")
                    if nc > 0:
                        fails_in_row = 0
                    else:
                        fails_in_row += 1
                except Exception as e:
                    err_msg = str(e)[:80]
                    print(f"    ❌ 出错: {err_msg}")
                    fails_in_row += 1

                # 连续失败太多次就重建浏览器
                if fails_in_row >= 8:
                    print("\n  ⚠️ 连续8次失败，可能session已过期")
                    print("  ⚠️ 尝试重建浏览器（可能需要重新扫码）...")
                    await mgr.cleanup_browser()
                    await mgr.create_browser()
                    fails_in_row = 0

                # 定期保存
                if cur % 5 == 0 and notes:
                    with open(OUT, 'w') as f:
                        json.dump(build_output(notes), f, ensure_ascii=False)
                    print(f"    💾 已保存 {len(notes)} 条到 {os.path.basename(OUT)}")

                # 间隔 20-35 秒
                delay = random.uniform(20, 35)
                print(f"    ⏳ 等待 {delay:.0f}s...")
                await asyncio.sleep(delay)

            print(f"\n  📊 {plat} 完成: {pc} 条")

    finally:
        await mgr.cleanup_all()

    if not notes:
        print("\n❌ 未获取新数据"); return

    with open(OUT, 'w') as f:
        json.dump(build_output(notes), f, ensure_ascii=False, indent=2)
    print(f"\n{'='*55}")
    print(f"🎉 支付宝重爬完成！新增 {len(notes)} 条")
    print(f"   保存到: {OUT}")
    print(f"{'='*55}")

if __name__ == "__main__":
    asyncio.run(main())
