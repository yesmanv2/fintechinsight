"""
小红书登录工具 - 保存登录状态到 auth.json
运行后会打开浏览器，让你手动登录小红书
登录成功后自动保存 storage_state，后续爬虫直接复用

⚠️ 这个脚本只做一件事：打开浏览器 → 你登录 → 保存状态
   绝不会自动刷新或跳转页面
"""
import asyncio
import os
import time
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auth.json')
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookie.txt')


async def main():
    print("=" * 60)
    print("🔑 小红书登录工具（稳定版）")
    print("   打开浏览器 → 手动登录 → 自动保存登录状态")
    print("   ⚠️ 页面不会自动刷新，请放心操作")
    print("=" * 60)

    # 如果旧的 auth.json 存在，先删掉，从干净状态开始
    if os.path.exists(AUTH_FILE):
        os.remove(AUTH_FILE)
        print(f"\n🗑️ 已清除旧的 auth.json")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ],
        )

        # 全新的 context，不加载任何旧状态
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        page = await context.new_page()

        # 应用 stealth 反检测
        stealth = Stealth(
            navigator_platform_override="MacIntel",
            navigator_vendor_override="Google Inc.",
            navigator_user_agent_override="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        await stealth.apply_stealth_async(page)
        print("\n🛡️ Stealth 反检测已启用")

        # 打开小红书首页（只打开一次，绝不自动刷新）
        print("🌐 正在打开小红书...")
        try:
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  ⚠️ 页面加载超时，但不影响操作: {e}")

        # 等页面稳定
        await asyncio.sleep(3)

        print("\n" + "=" * 50)
        print("👉 请在浏览器窗口中登录小红书！")
        print("   支持: 小红书 APP 扫码 / 手机号验证码")
        print("")
        print("   🔴 页面不会自动刷新，请放心操作")
        print("   🔴 登录成功后脚本会自动检测并保存")
        print("   🔴 最多等待 5 分钟")
        print("=" * 50)

        # 轮询等待登录，只检查 cookie，绝不操作页面
        start = time.time()
        timeout = 300
        last_print = 0

        while time.time() - start < timeout:
            try:
                cookies = await context.cookies("https://www.xiaohongshu.com")
                ws = [c for c in cookies if c['name'] == 'web_session' and len(c.get('value', '')) > 10]
                if ws:
                    print(f"\n🎉 检测到登录成功！web_session = {ws[0]['value'][:25]}...")
                    break
            except Exception:
                pass  # 忽略任何错误，不干扰用户操作

            # 每 15 秒打印一次等待提示
            elapsed = int(time.time() - start)
            if elapsed - last_print >= 15:
                remaining = timeout - elapsed
                print(f"  ⏳ 等待登录中... 已等 {elapsed}s，还剩 {remaining}s")
                last_print = elapsed

            await asyncio.sleep(2)
        else:
            print("\n❌ 登录超时（5分钟），请重试")
            await browser.close()
            return

        # 登录成功！等几秒让页面完全加载
        print("\n⏳ 登录成功，等待 5 秒让状态完全同步...")
        await asyncio.sleep(5)

        # 保存 storage_state（包含 cookies + localStorage）
        await context.storage_state(path=AUTH_FILE)
        print(f"💾 登录状态已保存到: {AUTH_FILE}")

        # 同时保存 web_session 到 cookie.txt 备用
        cookies = await context.cookies("https://www.xiaohongshu.com")
        ws = [c for c in cookies if c['name'] == 'web_session']
        if ws:
            with open(COOKIE_FILE, 'w') as f:
                f.write(ws[0]['value'])
            print(f"💾 web_session 已保存到: {COOKIE_FILE}")

        print("\n" + "=" * 50)
        print("✅ 全部完成！现在可以运行爬虫了:")
        print("   python3 real_crawl.py")
        print("=" * 50)

        # 关闭浏览器
        await browser.close()
        print("🔒 浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(main())
