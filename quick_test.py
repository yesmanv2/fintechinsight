"""
快速测试：用 CDP 连接已运行的 Chrome
需要先以 remote debugging 模式重启 Chrome
"""
import asyncio, os, json, subprocess, time, sys
from playwright.async_api import async_playwright

CDP_PORT = 9222

def start_chrome_with_debugging():
    """以 remote debugging 模式启动 Chrome"""
    # 先检查是否已有 Chrome 在 debugging 端口
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', CDP_PORT))
        s.close()
        print(f"✅ Chrome 已在 debugging 模式运行 (端口 {CDP_PORT})")
        return True
    except ConnectionRefusedError:
        s.close()
    
    print(f"⚠️ Chrome 未在 debugging 模式运行")
    print(f"\n请执行以下步骤:")
    print(f"  1. 完全退出 Chrome (Cmd+Q)")
    print(f"  2. 在终端运行:")
    print(f'     /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={CDP_PORT} &')
    print(f"  3. 等 Chrome 打开后，确认已登录小红书")
    print(f"  4. 重新运行本脚本")
    return False


async def main():
    print("=" * 50)
    print("🔍 CDP 连接测试 - 小红书爬取")
    print("=" * 50)
    
    if not start_chrome_with_debugging():
        return
    
    api_results = []
    
    async with async_playwright() as p:
        print(f"\n🔄 连接 Chrome (CDP: localhost:{CDP_PORT})...")
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        
        # 获取已有的 contexts
        contexts = browser.contexts
        print(f"  找到 {len(contexts)} 个 browser context")
        
        if not contexts:
            print("❌ 没有可用的 context")
            return
        
        ctx = contexts[0]
        pages = ctx.pages
        print(f"  已有 {len(pages)} 个标签页")
        
        # 创建新标签页
        page = await ctx.new_page()
        
        # 检查 cookies
        cookies = await ctx.cookies("https://www.xiaohongshu.com")
        names = [c['name'] for c in cookies]
        print(f"  Cookies ({len(cookies)}): {names[:10]}")
        has_ws = 'web_session' in names
        print(f"  web_session: {'✅' if has_ws else '❌'}")
        
        if has_ws:
            ws = next(c['value'] for c in cookies if c['name'] == 'web_session')
            print(f"  值: {ws[:30]}...")
        
        # 拦截 API 响应
        async def on_resp(response):
            url = response.url
            if 'search/notes' in url or 'search_notes' in url:
                try:
                    data = await response.json()
                    code = data.get('code', -1)
                    items = data.get('data', {}).get('items', [])
                    print(f"  🔥 API拦截! code={code}, items={len(items)}")
                    api_results.extend(items)
                except Exception as e:
                    print(f"  API解析失败: {e}")
        
        page.on("response", on_resp)
        
        # 搜索
        keyword = "支付宝"
        url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_note"
        print(f"\n🔍 搜索「{keyword}」...")
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
        except Exception:
            try:
                await page.goto(url, wait_until="load", timeout=15000)
            except Exception as e:
                print(f"  页面加载异常: {e}")
        
        await asyncio.sleep(5)
        
        # 截图
        await page.screenshot(path="/tmp/xhs_cdp_test.png", full_page=False)
        print("📸 截图: /tmp/xhs_cdp_test.png")
        
        # DOM提取
        dom_notes = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/explore/"]');
            const results = [];
            const seen = new Set();
            links.forEach(link => {
                const href = link.getAttribute('href') || '';
                const m = href.match(/\\/explore\\/([a-f0-9]+)/);
                if (m && !seen.has(m[1])) {
                    seen.add(m[1]);
                    // 找最近的包含标题的元素
                    const parent = link.closest('section') || link.parentElement;
                    const titleEl = parent ? parent.querySelector('[class*="title"], .title, span') : null;
                    results.push({
                        id: m[1],
                        title: titleEl ? titleEl.textContent.trim() : '',
                        href: href,
                    });
                }
            });
            return results;
        }""")
        
        print(f"DOM 提取: {len(dom_notes)} 条笔记链接")
        for i, n in enumerate(dom_notes[:5]):
            print(f"  [{i+1}] {n['title'][:50]} (id={n['id']})")
        
        # 页面标题
        title = await page.title()
        print(f"\n页面标题: {title}")
        
        page.remove_listener("response", on_resp)
        await page.close()
        # 不关闭 browser（因为是连接的用户 Chrome）
    
    print(f"\n{'=' * 50}")
    print(f"📊 API 拦截: {len(api_results)} 条")
    for i, item in enumerate(api_results[:5]):
        nc = item.get('note_card', item)
        t = nc.get('display_title', '')
        u = nc.get('user', {}).get('nickname', '')
        likes = nc.get('interact_info', {}).get('liked_count', '?')
        print(f"  [{i+1}] {t}")
        print(f"      👤 {u} | ❤️ {likes}")

asyncio.run(main())
