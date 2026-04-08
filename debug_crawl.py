#!/usr/bin/env python3
"""
诊断脚本 - 测试小红书搜索为什么拦截不到API数据
"""
import asyncio
import json
import os
import re
import random
import sqlite3
import shutil
import tempfile
import subprocess
import sys
from datetime import datetime

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
except ImportError:
    print("❌ 需要安装: pip install playwright playwright-stealth")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_browser_key_mac():
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-w', '-s', 'Chrome Safe Storage', '-a', 'Chrome'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None

def decrypt_chromium_cookie(encrypted_value, key_password):
    try:
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2
        if encrypted_value[:3] in (b'v10', b'v11'):
            encrypted_value = encrypted_value[3:]
        salt = b'saltysalt'
        iv = b' ' * 16
        key = PBKDF2(key_password.encode('utf-8'), salt, dkLen=16, count=1003)
        cipher = AES.new(key, AES.MODE_CBC, IV=iv)
        decrypted = cipher.decrypt(encrypted_value)
        if len(decrypted) > 0:
            pad_len = decrypted[-1]
            if isinstance(pad_len, int) and 1 <= pad_len <= 16:
                if all(b == pad_len for b in decrypted[-pad_len:]):
                    decrypted = decrypted[:-pad_len]
        try:
            result = decrypted.decode('utf-8')
        except UnicodeDecodeError:
            result = decrypted.decode('latin-1')
        clean = ''.join(c for c in result if c.isprintable() and ord(c) < 128)
        hex_match = re.search(r'([0-9a-f]{32,})', clean, re.IGNORECASE)
        if hex_match: return hex_match.group(1)
        if len(clean) > 5: return clean
        return None
    except Exception:
        return None

def extract_all_xhs_cookies():
    chrome_cookie_path = os.path.expanduser('~/Library/Application Support/Google/Chrome/Default/Cookies')
    if not os.path.exists(chrome_cookie_path):
        print("❌ 未找到 Chrome Cookie 数据库")
        return []
    key_password = get_browser_key_mac()
    if not key_password:
        print("❌ 无法获取 Chrome Keychain 密钥")
        return []
    tmp = tempfile.mktemp(suffix='.db')
    shutil.copy2(chrome_cookie_path, tmp)
    cookies = []
    try:
        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT host_key, name, value, encrypted_value, path, is_secure, "
            "is_httponly, samesite, expires_utc "
            "FROM cookies WHERE host_key LIKE '%xiaohongshu%'"
        )
        rows = cursor.fetchall()
        conn.close()
        for host, name, value, enc_val, path, secure, httponly, samesite, expires in rows:
            final_value = value
            if not final_value and enc_val:
                decrypted = decrypt_chromium_cookie(enc_val, key_password)
                if decrypted: final_value = decrypted
            if final_value:
                ss_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
                cookies.append({
                    "name": name, "value": final_value,
                    "domain": host if host.startswith('.') else f".{host.lstrip('.')}",
                    "path": path or "/", "secure": bool(secure),
                    "httpOnly": bool(httponly), "sameSite": ss_map.get(samesite, "Lax"),
                })
                if name == 'web_session':
                    print(f"  ✅ web_session = {final_value[:30]}...")
    except Exception as e:
        print(f"  ❌ 读取 Cookie 失败: {e}")
    finally:
        os.unlink(tmp)
    return cookies


async def diagnose():
    print("=" * 60)
    print("🔬 诊断模式 - 测试小红书搜索API拦截")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 提取 Cookie
    print("\n📋 Step 1: 提取 Cookie...")
    xhs_cookies = extract_all_xhs_cookies()
    print(f"  共提取 {len(xhs_cookies)} 条 Cookie")
    ws = [c for c in xhs_cookies if c['name'] == 'web_session']
    if not ws:
        print("  ❌ 无 web_session！Cookie 可能过期")
        return
    
    # 2. 启动浏览器
    api_intercepted = []
    all_responses = []
    
    async def on_response(response):
        url = response.url
        # 记录所有 API 请求
        if 'api/sns' in url or 'edith' in url or 'search' in url:
            status = response.status
            all_responses.append(f"[{status}] {url[:120]}")
        # 拦截搜索 API
        if 'api/sns/web/v1/search/notes' in url:
            try:
                data = await response.json()
                api_intercepted.append(data)
                code = data.get('code', '?')
                items = data.get('data', {}).get('items', [])
                print(f"  🎯 拦截到搜索 API! code={code}, items={len(items)}")
            except Exception as e:
                print(f"  ⚠️ 拦截到 API 但解析失败: {e}")
    
    print("\n📋 Step 2: 启动浏览器...")
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage'],
    )
    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        locale="zh-CN", timezone_id="Asia/Shanghai",
    )
    await context.add_cookies(xhs_cookies)
    page = await context.new_page()
    stealth = Stealth(
        navigator_platform_override="MacIntel",
        navigator_vendor_override="Google Inc.",
        navigator_user_agent_override="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    await stealth.apply_stealth_async(page)
    page.on("response", on_response)
    
    # 3. 先访问首页，测试 Cookie 是否有效
    print("\n📋 Step 3: 访问首页测试 Cookie...")
    try:
        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(5)
        # 检查是否被要求登录
        page_content = await page.evaluate("document.body?.innerText?.slice(0,500) || ''")
        if '登录' in page_content[:100] and '注册' in page_content[:100]:
            print(f"  ⚠️ 页面可能要求登录！前100字: {page_content[:100]}")
        else:
            print(f"  ✅ 首页加载成功，前80字: {page_content[:80]}")
        
        # 检查 Cookie 是否被浏览器正确接收
        browser_cookies = await context.cookies("https://www.xiaohongshu.com")
        ws_browser = [c for c in browser_cookies if c['name'] == 'web_session']
        print(f"  浏览器中的 Cookie 数量: {len(browser_cookies)}, web_session: {'✅ 有' if ws_browser else '❌ 无'}")
    except Exception as e:
        print(f"  ❌ 首页访问失败: {e}")
    
    # 4. 测试搜索
    print("\n📋 Step 4: 测试搜索 '美团支付'...")
    all_responses.clear()
    api_intercepted.clear()
    
    try:
        url = "https://www.xiaohongshu.com/search_result?keyword=美团支付&source=web_search_result_note"
        await page.goto(url, wait_until="networkidle", timeout=25000)
        await asyncio.sleep(8)
        
        # 检查页面内容
        page_text = await page.evaluate("document.body?.innerText?.slice(0,1000) || ''")
        print(f"\n  📄 页面内容前200字:")
        print(f"  {page_text[:200]}")
        
        # 检查是否有 461 或异常
        if '461' in page_text or '异常' in page_text[:100]:
            print(f"\n  🛑 检测到反爬/异常！")
        
        # 检查是否有搜索结果DOM
        has_results = await page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[class*="note-item"], [class*="search-result"], section[class*="note"]');
                const feeds = document.querySelectorAll('[class*="feeds"], [class*="masonry"]');
                return {
                    cards: cards.length,
                    feeds: feeds.length,
                    bodyClasses: document.body.className.slice(0, 200),
                    title: document.title,
                };
            }
        """)
        print(f"\n  🔍 DOM 分析:")
        print(f"    title: {has_results.get('title', '?')}")
        print(f"    note cards: {has_results.get('cards', 0)}")
        print(f"    feed containers: {has_results.get('feeds', 0)}")
        
        # 模拟滚动
        print(f"\n  📜 滚动页面...")
        for i in range(3):
            await page.evaluate(f"window.scrollBy(0, {random.randint(300, 600)})")
            await asyncio.sleep(2)
        await asyncio.sleep(3)
        
    except Exception as e:
        print(f"  ❌ 搜索页面加载失败: {e}")
    
    # 5. 报告
    print(f"\n📋 Step 5: 诊断报告")
    print(f"  拦截到的 API 调用总数: {len(all_responses)}")
    print(f"  搜索 API 拦截数: {len(api_intercepted)}")
    
    if all_responses:
        print(f"\n  所有拦截到的 API:")
        for resp in all_responses[:20]:
            print(f"    {resp}")
    else:
        print(f"\n  ⚠️ 没有拦截到任何 API 请求！可能原因:")
        print(f"    1. Cookie 无效/过期 → 页面没有发出搜索请求")
        print(f"    2. 搜索结果通过 SSR (服务端渲染) 返回，不走独立 API")
        print(f"    3. 反爬导致请求被拦截")
    
    if api_intercepted:
        for i, data in enumerate(api_intercepted):
            code = data.get('code', '?')
            items = data.get('data', {}).get('items', [])
            print(f"\n  搜索API #{i+1}: code={code}, items={len(items)}")
            if items:
                print(f"    第一条: {items[0].get('note_card', {}).get('display_title', '?')[:50]}")
    
    # 6. 额外测试：直接用 page.evaluate 发 fetch 请求
    print(f"\n📋 Step 6: 直接 fetch 测试...")
    try:
        fetch_result = await page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('https://edith.xiaohongshu.com/api/sns/web/v1/search/notes', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            keyword: '美团支付',
                            page: 1,
                            page_size: 20,
                            search_id: '',
                            sort: 'general',
                            note_type: 0,
                        }),
                        credentials: 'include',
                    });
                    const status = resp.status;
                    const text = await resp.text();
                    return { status, text: text.slice(0, 500) };
                } catch(e) {
                    return { error: e.message };
                }
            }
        """)
        print(f"  直接 fetch 结果: status={fetch_result.get('status', '?')}")
        text = fetch_result.get('text', '')
        if text:
            try:
                data = json.loads(text)
                print(f"  code={data.get('code', '?')}, success={data.get('success', '?')}")
                if data.get('code') != 0:
                    print(f"  ⚠️ API 返回错误! msg={data.get('msg', '?')}")
            except:
                print(f"  响应前200字: {text[:200]}")
        if fetch_result.get('error'):
            print(f"  ❌ fetch 错误: {fetch_result['error']}")
    except Exception as e:
        print(f"  ❌ evaluate fetch 失败: {e}")
    
    # 清理
    await context.close()
    await browser.close()
    await pw.stop()
    print("\n✅ 诊断完成")


if __name__ == "__main__":
    asyncio.run(diagnose())
