"""
从本地 Chrome 浏览器直接提取小红书 web_session cookie
不需要打开浏览器，不需要扫码登录
前提：你在 Chrome 中登录过小红书
"""
import os
import re
import sqlite3
import shutil
import tempfile
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, 'cookie.txt')


def get_browser_key_mac():
    """从 macOS Keychain 获取 Chrome 加密密钥"""
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
    """解密 Chrome cookie"""
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
    except Exception as e:
        print(f"  解密失败: {e}")
        return None


def extract_web_session():
    """从 Chrome 提取小红书 web_session"""
    chrome_cookie_path = os.path.expanduser(
        '~/Library/Application Support/Google/Chrome/Default/Cookies'
    )
    
    if not os.path.exists(chrome_cookie_path):
        print("❌ 未找到 Chrome Cookie 数据库")
        print("   路径: ~/Library/Application Support/Google/Chrome/Default/Cookies")
        return None

    key_password = get_browser_key_mac()
    if not key_password:
        print("❌ 无法获取 Chrome Keychain 密钥")
        return None

    print("✅ 已获取 Chrome 加密密钥")

    # 复制数据库（避免锁定）
    tmp = tempfile.mktemp(suffix='.db')
    shutil.copy2(chrome_cookie_path, tmp)

    web_session = None
    all_xhs_cookies = []

    try:
        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT host_key, name, value, encrypted_value "
            "FROM cookies WHERE host_key LIKE '%xiaohongshu%'"
        )
        rows = cursor.fetchall()
        conn.close()

        print(f"📋 找到 {len(rows)} 条小红书相关 cookie")

        for host, name, value, enc_val in rows:
            final_value = value
            if not final_value and enc_val:
                final_value = decrypt_chromium_cookie(enc_val, key_password)

            if final_value:
                all_xhs_cookies.append((name, final_value[:30]))
                if name == 'web_session' and len(final_value) > 10:
                    web_session = final_value
                    print(f"  ✅ web_session = {final_value[:25]}...")

    except Exception as e:
        print(f"❌ 读取失败: {e}")
    finally:
        os.unlink(tmp)

    if not web_session:
        print("\n❌ 未找到有效的 web_session！")
        print("   请先在 Chrome 浏览器中登录 www.xiaohongshu.com")
        print(f"\n   已找到的 cookie 名: {[c[0] for c in all_xhs_cookies]}")

    return web_session


if __name__ == "__main__":
    print("=" * 50)
    print("🍪 从 Chrome 提取小红书 cookie")
    print("=" * 50)

    ws = extract_web_session()
    if ws:
        with open(COOKIE_FILE, 'w') as f:
            f.write(ws)
        print(f"\n💾 已保存到: {COOKIE_FILE}")
        print(f"\n✅ 现在可以运行爬虫:")
        print(f"   python3 real_crawl.py")
    else:
        print("\n💡 替代方案：")
        print("   1. 在 Chrome 中打开 www.xiaohongshu.com 并登录")
        print("   2. F12 → Application → Cookies → 找到 web_session")
        print("   3. 把值粘贴到 cookie.txt 文件中")
