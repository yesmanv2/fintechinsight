"""
调试小红书搜索页面：
1. 查看 API 是否返回数据
2. 查看 DOM 结构
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auth.json')

async def main():
    api_responses = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
        )
        context = await browser.new_context(
            storage_state=AUTH_FILE,
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = await context.new_page()
        
        stealth = Stealth(
            navigator_platform_override="MacIntel",
            navigator_vendor_override="Google Inc.",
            navigator_user_agent_override="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        await stealth.apply_stealth_async(page)
        
        # 监听所有响应
        async def on_response(response):
            url = response.url
            if 'search' in url and 'api' in url:
                try:
                    data = await response.json()
                    api_responses.append({
                        "url": url[:200],
                        "status": response.status,
                        "data_preview": str(data)[:500],
                    })
                    print(f"\n🔥 API响应: {url[:100]}")
                    print(f"   状态: {response.status}")
                    print(f"   数据: {str(data)[:300]}")
                except Exception as e:
                    api_responses.append({"url": url[:200], "error": str(e)})
        
        page.on("response", on_response)
        
        # 打开搜索页
        print("正在打开搜索页...")
        url = "https://www.xiaohongshu.com/search_result?keyword=微信支付&source=web_search_result_note"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
        except Exception:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        await asyncio.sleep(5)
        
        # 截图
        await page.screenshot(path="/tmp/xhs_search_debug.png")
        print("📸 截图保存: /tmp/xhs_search_debug.png")
        
        # 分析 DOM
        print("\n=== DOM 分析 ===")
        
        # 获取页面 HTML 结构摘要
        dom_info = await page.evaluate("""() => {
            const result = {};
            
            // 查看 sections
            const sections = document.querySelectorAll('section');
            result.sections = sections.length;
            result.section_classes = Array.from(sections).slice(0, 5).map(s => s.className);
            
            // 查看 note 相关
            const noteItems = document.querySelectorAll('[class*="note"]');
            result.noteItems = noteItems.length;
            result.noteClasses = Array.from(noteItems).slice(0, 5).map(n => n.className + ' | tag:' + n.tagName);
            
            // 查看所有带 href 的链接
            const links = document.querySelectorAll('a[href*="/explore/"]');
            result.exploreLinks = links.length;
            result.exploreSamples = Array.from(links).slice(0, 3).map(a => ({
                href: a.getAttribute('href'),
                text: a.innerText?.slice(0, 100),
                class: a.className,
            }));
            
            // 查看搜索结果容器
            const feedsPage = document.querySelectorAll('[class*="feeds"], [class*="search-result"], [id*="search"]');
            result.feedContainers = feedsPage.length;
            result.feedClasses = Array.from(feedsPage).slice(0, 3).map(f => f.className + ' | tag:' + f.tagName);
            
            // body text preview
            result.bodyText = document.body?.innerText?.slice(0, 800) || 'empty';
            
            // all a tags count
            const allLinks = document.querySelectorAll('a');
            result.totalLinks = allLinks.length;
            
            // href patterns
            const hrefPatterns = {};
            allLinks.forEach(a => {
                const href = a.getAttribute('href') || '';
                const pattern = href.replace(/[a-f0-9]{24}/g, '{ID}').replace(/\\?.*/, '');
                if (!hrefPatterns[pattern]) hrefPatterns[pattern] = 0;
                hrefPatterns[pattern]++;
            });
            result.hrefPatterns = Object.entries(hrefPatterns)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 15)
                .map(([k, v]) => `${v}x ${k}`);
            
            return result;
        }""")
        
        print(json.dumps(dom_info, ensure_ascii=False, indent=2))
        
        # API 响应汇总
        print(f"\n=== API 响应 ({len(api_responses)} 条) ===")
        for r in api_responses:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
