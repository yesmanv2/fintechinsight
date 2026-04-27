"""Debug cookie 解密"""
import os, sqlite3, shutil, tempfile, subprocess
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2

# 获取Chrome密钥
result = subprocess.run(
    ['security', 'find-generic-password', '-w', '-s', 'Chrome Safe Storage', '-a', 'Chrome'],
    capture_output=True, text=True
)
key_password = result.stdout.strip()
print(f"Keychain 密钥长度: {len(key_password)}")

# 读取cookie
cp = os.path.expanduser('~/Library/Application Support/Google/Chrome/Default/Cookies')
tmp = '/tmp/chrome_cookies_debug.db'
shutil.copy2(cp, tmp)
conn = sqlite3.connect(tmp)
cur = conn.cursor()
cur.execute(
    "SELECT encrypted_value, value FROM cookies "
    "WHERE host_key LIKE '%xiaohongshu%' AND name = 'web_session'"
)
row = cur.fetchone()
conn.close()
os.unlink(tmp)

if row:
    ev, pv = row
    print(f"明文值: {repr(pv)}")
    print(f"加密值长度: {len(ev)} bytes")
    print(f"加密前3字节: {ev[:3]}")
    print(f"加密值 hex: {ev.hex()}")
    
    data = ev[3:]  # 去掉v10前缀
    print(f"\n去前缀后长度: {len(data)}")
    
    salt = b'saltysalt'
    iv = b' ' * 16
    key = PBKDF2(key_password.encode(), salt, dkLen=16, count=1003)
    cipher = AES.new(key, AES.MODE_CBC, IV=iv)
    dec = cipher.decrypt(data)
    
    print(f"\n解密后原始 ({len(dec)} bytes):")
    print(f"  hex: {dec.hex()}")
    print(f"  repr: {repr(dec)}")
    
    pad = dec[-1]
    print(f"\nPKCS7 padding: {pad}")
    unpadded = dec[:-pad] if 1 <= pad <= 16 else dec
    print(f"去padding后 ({len(unpadded)} bytes):")
    print(f"  hex: {unpadded.hex()}")
    print(f"  repr: {repr(unpadded)}")
    
    # 尝试不同的解读
    try:
        as_utf8 = unpadded.decode('utf-8', errors='replace')
        print(f"  utf-8: {as_utf8}")
    except:
        pass
    
    as_latin = unpadded.decode('latin-1')
    print(f"  latin-1: {as_latin}")
    
    # web_session 通常是什么格式？
    # 尝试提取所有可打印字符
    printable = ''.join(c for c in as_latin if c.isprintable())
    print(f"  可打印字符: {printable}")
else:
    print("未找到 web_session cookie")
