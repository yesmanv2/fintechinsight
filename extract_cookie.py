"""自动从浏览器提取小红书 web_session cookie"""
import os
import sys
import sqlite3
import shutil
import tempfile
import glob
import subprocess
import re

def get_browser_key_mac(service, account):
    """从 macOS Keychain 获取浏览器加密密钥"""
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
    """解密 Chromium cookie（macOS AES-128-CBC with PBKDF2）"""
    try:
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2

        # v10 前缀表示使用 Keychain 密钥加密
        if encrypted_value[:3] == b'v10':
            encrypted_value = encrypted_value[3:]
        elif encrypted_value[:3] == b'v11':
            encrypted_value = encrypted_value[3:]
        
        salt = b'saltysalt'
        iv = b' ' * 16
        key_length = 16
        iterations = 1003
        
        key = PBKDF2(key_password.encode('utf-8'), salt, dkLen=key_length, count=iterations)
        cipher = AES.new(key, AES.MODE_CBC, IV=iv)
        decrypted = cipher.decrypt(encrypted_value)
        
        # PKCS7 padding removal
        if len(decrypted) > 0:
            pad_len = decrypted[-1]
            if isinstance(pad_len, int) and 1 <= pad_len <= 16:
                # 验证所有 padding 字节一致
                if all(b == pad_len for b in decrypted[-pad_len:]):
                    decrypted = decrypted[:-pad_len]
        
        # 尝试 utf-8 解码
        try:
            result = decrypted.decode('utf-8')
        except UnicodeDecodeError:
            # 如果 utf-8 失败，用 latin-1
            result = decrypted.decode('latin-1')
        
        # 清理：只保留可打印 ASCII 字符
        # web_session 通常是 hex 字符串，如 "050069..." 
        clean = ''.join(c for c in result if c.isprintable() and ord(c) < 128)
        
        # 尝试提取 hex session（通常是40-64个hex字符）
        hex_match = re.search(r'([0-9a-f]{32,})', clean, re.IGNORECASE)
        if hex_match:
            return hex_match.group(1)
        
        # 返回清理后的值
        if len(clean) > 10:
            return clean
        
        # 直接从原始字节中提取 hex 部分
        raw_hex = decrypted.hex()
        print(f"    原始解密 hex: {raw_hex}")
        
        return None
    except ImportError:
        print("⚠️ 需要 pycryptodome: pip3 install pycryptodome --break-system-packages")
        return None
    except Exception as e:
        print(f"    解密异常: {e}")
        return None

def search_all_browsers():
    """搜索所有 Chromium 系浏览器"""
    browsers = []
    
    # Chrome
    chrome_paths = glob.glob(os.path.expanduser(
        '~/Library/Application Support/Google/Chrome/*/Cookies'))
    for p in chrome_paths:
        browsers.append(('Chrome', p, 'Chrome Safe Storage', 'Chrome'))
    
    # Edge
    edge_paths = glob.glob(os.path.expanduser(
        '~/Library/Application Support/Microsoft Edge/*/Cookies'))
    for p in edge_paths:
        browsers.append(('Edge', p, 'Microsoft Edge Safe Storage', 'Microsoft Edge'))
    
    # Arc
    arc_paths = glob.glob(os.path.expanduser(
        '~/Library/Application Support/Arc/User Data/*/Cookies'))
    for p in arc_paths:
        browsers.append(('Arc', p, 'Arc Safe Storage', 'Arc'))
    
    # Brave
    brave_paths = glob.glob(os.path.expanduser(
        '~/Library/Application Support/BraveSoftware/Brave-Browser/*/Cookies'))
    for p in brave_paths:
        browsers.append(('Brave', p, 'Brave Safe Storage', 'Brave'))
    
    return browsers

def extract_web_session():
    """主函数：提取 web_session"""
    print("=" * 50)
    print("🔍 自动搜索浏览器中的小红书 Cookie")
    print("=" * 50)
    
    browsers = search_all_browsers()
    if not browsers:
        print("❌ 未找到任何 Chromium 浏览器的 Cookie 文件")
        return None
    
    print(f"\n找到 {len(browsers)} 个浏览器 Cookie 文件:")
    for name, path, _, _ in browsers:
        profile = os.path.basename(os.path.dirname(path))
        print(f"  📁 {name} ({profile})")
    
    for name, cookie_path, key_service, key_account in browsers:
        profile = os.path.basename(os.path.dirname(cookie_path))
        print(f"\n--- 🔍 {name} ({profile}) ---")
        
        tmp = tempfile.mktemp(suffix='.db')
        shutil.copy2(cookie_path, tmp)
        
        try:
            conn = sqlite3.connect(tmp)
            cursor = conn.cursor()
            
            # 搜索所有小红书 cookie
            cursor.execute(
                "SELECT name, value, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%xiaohongshu%'"
            )
            all_rows = cursor.fetchall()
            
            if all_rows:
                print(f"  小红书 cookie 列表 ({len(all_rows)} 条):")
                for n, v, ev in all_rows:
                    if v:
                        print(f"    {n} = {v[:30]}... (明文)")
                    else:
                        print(f"    {n} = [加密]")
            
            # 专门查找 web_session
            cursor.execute(
                "SELECT name, value, encrypted_value FROM cookies "
                "WHERE host_key LIKE '%xiaohongshu%' AND name = 'web_session'"
            )
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                print(f"  ⚠️ 未找到 web_session cookie")
                continue
            
            for cookie_name, plain_value, encrypted_value in rows:
                if plain_value and len(plain_value) > 10:
                    print(f"  ✅ 找到明文 web_session!")
                    os.unlink(tmp)
                    return plain_value
                
                if encrypted_value:
                    print(f"  🔐 Cookie 已加密 ({len(encrypted_value)} bytes)")
                    key_password = get_browser_key_mac(key_service, key_account)
                    if key_password:
                        print(f"  🔑 获取到 Keychain 密钥")
                        decrypted = decrypt_chromium_cookie(encrypted_value, key_password)
                        if decrypted and len(decrypted) > 10:
                            print(f"  ✅ 解密成功: {decrypted[:20]}...")
                            os.unlink(tmp)
                            return decrypted
                        else:
                            print(f"  ⚠️ 解密结果无效")
                    else:
                        print(f"  ⚠️ 无法从 Keychain 获取密钥")
        
        except Exception as e:
            print(f"  ❌ 读取失败: {e}")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    
    return None

def extract_domain_cookies(domain_pattern, label=""):
    """
    通用域名 Cookie 提取函数
    从 Chrome 浏览器提取指定域名的所有 cookie，返回 Playwright 兼容格式。
    
    Args:
        domain_pattern: SQL LIKE 模式，如 '%douyin%' 或 '%alipay%'
        label: 显示标签，如 "抖音" 或 "支付宝"
    Returns:
        list[dict]: Playwright 兼容的 cookie 列表
    """
    print(f"\n{'=' * 50}")
    print(f"🔍 提取 {label or domain_pattern} Cookie")
    print(f"{'=' * 50}")
    
    browsers = search_all_browsers()
    if not browsers:
        print("❌ 未找到任何 Chromium 浏览器的 Cookie 文件")
        return []
    
    # 获取 Keychain 密钥
    all_cookies = []
    
    for name, cookie_path, key_service, key_account in browsers:
        profile = os.path.basename(os.path.dirname(cookie_path))
        
        tmp = tempfile.mktemp(suffix='.db')
        shutil.copy2(cookie_path, tmp)
        
        try:
            key_password = get_browser_key_mac(key_service, key_account)
            if not key_password:
                continue
            
            conn = sqlite3.connect(tmp)
            cursor = conn.cursor()
            
            # 查询匹配域名的所有 cookie
            cursor.execute(
                "SELECT host_key, name, value, encrypted_value, path, is_secure, "
                "is_httponly, samesite, expires_utc "
                f"FROM cookies WHERE host_key LIKE ?"
            , (domain_pattern,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                continue
            
            print(f"  📁 {name} ({profile}): 找到 {len(rows)} 条 cookie")
            
            for host, cname, value, enc_val, path, secure, httponly, samesite, expires in rows:
                final_value = value
                if not final_value and enc_val:
                    decrypted = decrypt_chromium_cookie(enc_val, key_password)
                    if decrypted:
                        final_value = decrypted
                
                if final_value:
                    ss_map = {-1: "None", 0: "None", 1: "Lax", 2: "Strict"}
                    cookie = {
                        "name": cname,
                        "value": final_value,
                        "domain": host if host.startswith('.') else f".{host.lstrip('.')}",
                        "path": path or "/",
                        "secure": bool(secure),
                        "httpOnly": bool(httponly),
                        "sameSite": ss_map.get(samesite, "Lax"),
                    }
                    all_cookies.append(cookie)
            
            if all_cookies:
                # 找到了就用第一个浏览器的，不继续搜索
                break
                
        except Exception as e:
            print(f"  ❌ {name} 读取失败: {e}")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    
    if all_cookies:
        print(f"  ✅ 共提取 {len(all_cookies)} 条 {label} cookie")
    else:
        print(f"  ❌ 未找到任何 {label} cookie")
    
    return all_cookies


def extract_douyin_cookies():
    """从 Chrome 提取抖音域名的所有 cookie（.douyin.com）"""
    return extract_domain_cookies('%douyin.com%', '抖音')


def extract_alipay_cookies():
    """
    从 Chrome 提取支付宝相关域名的所有 cookie
    包括 .alipay.com、.antgroup.com、.ant.design 等
    """
    # 支付宝涉及多个域名，分别提取后合并
    domains = [
        ('%alipay.com%', '支付宝 alipay.com'),
        ('%antgroup.com%', '支付宝 antgroup.com'),
        ('%mybank.cn%', '网商银行 mybank.cn'),
    ]
    all_cookies = []
    for pattern, label in domains:
        cookies = extract_domain_cookies(pattern, label)
        all_cookies.extend(cookies)
    
    if all_cookies:
        print(f"\n  🎉 支付宝系列共提取 {len(all_cookies)} 条 cookie")
    return all_cookies


if __name__ == "__main__":
    import sys as _sys
    
    # 支持命令行参数选择提取哪个平台的 cookie
    target = _sys.argv[1] if len(_sys.argv) > 1 else "xiaohongshu"
    
    if target in ("douyin", "抖音"):
        cookies = extract_douyin_cookies()
        if cookies:
            print(f"\n🎉 抖音 Cookie 提取成功: {len(cookies)} 条")
            for c in cookies[:5]:
                print(f"   {c['name']} = {c['value'][:30]}...")
        else:
            print("\n❌ 抖音 Cookie 提取失败")
            print("💡 请先在 Chrome 中登录 www.douyin.com")
    
    elif target in ("alipay", "支付宝"):
        cookies = extract_alipay_cookies()
        if cookies:
            print(f"\n🎉 支付宝 Cookie 提取成功: {len(cookies)} 条")
            for c in cookies[:5]:
                print(f"   {c['name']} = {c['value'][:30]}...")
        else:
            print("\n❌ 支付宝 Cookie 提取失败")
            print("💡 请先在 Chrome 中登录支付宝服务商后台")
    
    else:
        # 默认提取小红书
        cookie = extract_web_session()
        if cookie:
            cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookie.txt')
            with open(cookie_file, 'w') as f:
                f.write(cookie.strip())
            print(f"\n🎉 Cookie 已保存到: {cookie_file}")
            print(f"   值: {cookie}")
        else:
            print("\n❌ 自动提取失败")
            print("\n💡 备选方案 - 手动获取:")
            print("   1. 浏览器打开 xiaohongshu.com (确认已登录)")
            print("   2. 按 F12 → Application → Cookies → xiaohongshu.com")
            print("   3. 找到 web_session，复制值")
            print("   4. 运行: python3 crawler.py --session 你的cookie值")
