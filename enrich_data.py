"""
数据增强脚本：
1. 清理垃圾数据（无效note_id、完全空白数据）
2. 对有效笔记批量访问详情页，获取正文内容(desc)、完整标题
"""
import asyncio
import json
import os
import re
import time
import random
import sqlite3
import shutil
import tempfile
import subprocess
import sys
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'real_data.json')
ENRICHED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'real_data.json')  # 直接覆盖


def get_browser_key_mac(service, account):
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-w', '-s', service, '-a', account],
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
        if hex_match:
            return hex_match.group(1)
        if len(clean) > 5:
            return clean
        return None
    except Exception:
        return None


def extract_all_xhs_cookies():
    chrome_cookie_path = os.path.expanduser(
        '~/Library/Application Support/Google/Chrome/Default/Cookies'
    )
    if not os.path.exists(chrome_cookie_path):
        print("❌ 未找到 Chrome Cookie 数据库")
        return []
    key_password = get_browser_key_mac('Chrome Safe Storage', 'Chrome')
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
        print(f"  从 Chrome 中找到 {len(rows)} 条小红书 cookie")
        for host, name, value, enc_val, path, secure, httponly, samesite, expires in rows:
            final_value = value
            if not final_value and enc_val:
                decrypted = decrypt_chromium_cookie(enc_val, key_password)
                if decrypted:
                    final_value = decrypted
            if final_value:
                ss_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
                cookie = {
                    "name": name, "value": final_value,
                    "domain": host if host.startswith('.') else f".{host.lstrip('.')}",
                    "path": path or "/", "secure": bool(secure),
                    "httpOnly": bool(httponly), "sameSite": ss_map.get(samesite, "Lax"),
                }
                cookies.append(cookie)
    except Exception as e:
        print(f"  ❌ 读取 Cookie 失败: {e}")
    finally:
        os.unlink(tmp)
    return cookies


async def fetch_note_detail(page, note_id, retry=2):
    """访问单篇笔记详情页，提取标题和正文"""
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    
    for attempt in range(retry + 1):
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            if resp and resp.status == 404:
                return None, None, None, None
            
            await asyncio.sleep(random.uniform(1.5, 3.0))
            
            # 尝试关闭登录弹窗
            close_btn = await page.query_selector('[class*="close-button"], [class*="login"] [class*="close"]')
            if close_btn:
                try:
                    await close_btn.click()
                    await asyncio.sleep(0.5)
                except:
                    pass
            
            # 提取详情
            detail = await page.evaluate("""() => {
                const result = {title: '', desc: '', author: '', authorAvatar: ''};
                
                // 标题 - 多种选择器
                const titleSels = [
                    '#detail-title', '.title', '[class*="title"]',
                    'h1', '.note-text > span:first-child'
                ];
                for (const sel of titleSels) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim().length > 2) {
                        result.title = el.textContent.trim();
                        break;
                    }
                }
                
                // 正文 - 多种选择器
                const descSels = [
                    '#detail-desc', '.desc', '.note-text', 
                    '[class*="desc"]', '[class*="content"]',
                    '.note-scroller .note-text'
                ];
                for (const sel of descSels) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const text = el.textContent.trim();
                        // 排除只有标题的情况
                        if (text.length > 10 && text !== result.title) {
                            result.desc = text.slice(0, 1000);
                            break;
                        }
                    }
                }
                
                // 作者
                const authorSels = [
                    '.user-info .username', '[class*="author"] .name',
                    '[class*="nickname"]', '.info .name'
                ];
                for (const sel of authorSels) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        result.author = el.textContent.trim();
                        break;
                    }
                }
                
                // 作者头像
                const avatarEl = document.querySelector('.user-info img, [class*="avatar"] img');
                if (avatarEl) {
                    result.authorAvatar = avatarEl.src || '';
                }
                
                return result;
            }""")
            
            title = detail.get('title', '').strip()
            desc = detail.get('desc', '').strip()
            author = detail.get('author', '').strip()
            avatar = detail.get('authorAvatar', '').strip()
            
            if title or desc:
                return title, desc, author, avatar
            
            if attempt < retry:
                await asyncio.sleep(2)
                
        except Exception as e:
            if attempt < retry:
                await asyncio.sleep(2)
            else:
                print(f"    ❌ 获取详情失败 {note_id}: {e}")
    
    return None, None, None, None


async def main():
    print("=" * 60)
    print("📊 数据增强脚本 - 获取帖子正文内容")
    print("=" * 60)
    
    # 加载数据
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    notes = data['notes']
    print(f"原始笔记数: {len(notes)}")
    
    # Step 1: 清理垃圾数据
    print("\n🧹 Step 1: 清理垃圾数据...")
    clean_notes = []
    removed = 0
    for n in notes:
        nid = n.get('note_id', '')
        # 过滤掉非标准note_id（UUID格式的无效数据）
        if '-' in nid or '#' in nid or len(nid) != 24:
            removed += 1
            continue
        # 过滤掉完全没有任何信息的数据
        has_title = bool(n.get('title', '').strip())
        has_author = bool(n.get('author', '').strip())
        has_likes = int(n.get('liked_count', '0') or 0) > 0
        if not has_title and not has_author and not has_likes:
            removed += 1
            continue
        clean_notes.append(n)
    
    print(f"  移除 {removed} 条垃圾数据，剩余 {len(clean_notes)} 条")
    
    # 找出需要补充信息的笔记（没有desc的）
    needs_detail = [n for n in clean_notes if not n.get('desc', '').strip()]
    print(f"  需要获取详情: {len(needs_detail)} 条")
    
    # Step 2: 提取 Cookie
    print("\n📦 Step 2: 提取 Chrome Cookie...")
    xhs_cookies = extract_all_xhs_cookies()
    print(f"  共提取 {len(xhs_cookies)} 条 cookie")
    
    # Step 3: 批量获取详情
    print("\n🌐 Step 3: 启动浏览器获取帖子详情...")
    
    # 限制处理数量，避免太长时间
    MAX_FETCH = min(len(needs_detail), 200)  # 最多处理200条
    to_fetch = needs_detail[:MAX_FETCH]
    print(f"  本次处理: {MAX_FETCH} 条（优先处理有标题的高质量数据）")
    
    # 按优先级排序：有标题有互动的优先
    to_fetch.sort(key=lambda n: (
        -int(n.get('liked_count', '0') or 0),
        -int(n.get('collected_count', '0') or 0),
        0 if n.get('title','').strip() else 1
    ))
    
    enriched_count = 0
    failed_count = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ],
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
        
        # 先访问首页激活cookie
        try:
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
        except:
            pass
        
        # API 拦截 - 从详情页API获取数据
        api_detail_cache = {}
        
        async def on_response(response):
            url = response.url
            # 拦截笔记详情API
            if 'api/sns/web/v1/feed' in url or 'api/sns/web/v2/note' in url:
                try:
                    data = await response.json()
                    if data and data.get('code') == 0:
                        items = data.get('data', {}).get('items', [])
                        if not items:
                            # v2 格式
                            note_data = data.get('data', {})
                            if note_data.get('note_id') or note_data.get('id'):
                                items = [{'note_card': note_data}]
                        
                        for item in items:
                            nc = item.get('note_card', item)
                            nid = nc.get('note_id', '') or item.get('id', '')
                            title = nc.get('display_title', '') or nc.get('title', '') or ''
                            desc = nc.get('desc', '') or ''
                            user = nc.get('user', {})
                            interact = nc.get('interact_info', {})
                            
                            if nid and (title or desc):
                                api_detail_cache[nid] = {
                                    'title': title,
                                    'desc': desc[:1000],
                                    'author': user.get('nickname', ''),
                                    'author_avatar': user.get('avatar', ''),
                                    'liked_count': str(interact.get('liked_count', 0)),
                                    'comment_count': str(interact.get('comment_count', 0)),
                                    'collected_count': str(interact.get('collected_count', 0)),
                                }
                except:
                    pass
        
        page.on("response", on_response)
        
        # 批量获取
        for i, note in enumerate(to_fetch):
            nid = note['note_id']
            
            if (i + 1) % 10 == 0 or i == 0:
                print(f"\n  [{i+1}/{MAX_FETCH}] 处理中...")
            
            # 先检查API缓存
            if nid in api_detail_cache:
                cached = api_detail_cache[nid]
                if cached.get('desc'):
                    note['desc'] = cached['desc']
                if cached.get('title') and not note.get('title','').strip():
                    note['title'] = cached['title']
                if cached.get('author') and not note.get('author','').strip():
                    note['author'] = cached['author']
                enriched_count += 1
                continue
            
            # 访问详情页
            title, desc, author, avatar = await fetch_note_detail(page, nid)
            
            # 检查API拦截是否获取到了
            if nid in api_detail_cache:
                cached = api_detail_cache[nid]
                if cached.get('desc'):
                    desc = cached['desc']
                if cached.get('title'):
                    title = cached['title'] if not title else title
                if cached.get('author'):
                    author = cached['author'] if not author else author
                # 更新互动数据
                if cached.get('liked_count') and int(cached['liked_count']) > 0:
                    note['liked_count'] = cached['liked_count']
                if cached.get('comment_count') and int(cached['comment_count']) > 0:
                    note['comment_count'] = cached['comment_count']
                if cached.get('collected_count') and int(cached['collected_count']) > 0:
                    note['collected_count'] = cached['collected_count']
            
            if desc:
                note['desc'] = desc[:1000]
                enriched_count += 1
                if (enriched_count % 20 == 0):
                    print(f"    ✅ 已获取 {enriched_count} 条正文")
            else:
                failed_count += 1
            
            if title and not note.get('title', '').strip():
                note['title'] = title
            if author and not note.get('author', '').strip():
                note['author'] = author
            if avatar and not note.get('author_avatar', '').strip():
                note['author_avatar'] = avatar
            
            # 反爬延迟 - 每5条稍微久一点
            if (i + 1) % 5 == 0:
                delay = random.uniform(4, 7)
            else:
                delay = random.uniform(1.5, 3.0)
            await asyncio.sleep(delay)
            
            # 每50条保存一次进度
            if (i + 1) % 50 == 0:
                data['notes'] = clean_notes
                data['meta']['total_notes'] = len(clean_notes)
                with open(ENRICHED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"    💾 进度已保存 ({i+1}/{MAX_FETCH})")
        
        page.remove_listener("response", on_response)
        await context.close()
        await browser.close()
    
    # 最终保存
    data['notes'] = clean_notes
    data['meta']['total_notes'] = len(clean_notes)
    data['meta']['enriched_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with open(ENRICHED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'=' * 60}")
    print(f"🎉 数据增强完成！")
    print(f"  清理后总笔记: {len(clean_notes)}")
    print(f"  成功获取正文: {enriched_count}")
    print(f"  获取失败: {failed_count}")
    print(f"  保存至: {ENRICHED_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
