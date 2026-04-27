#!/usr/bin/env python3
"""
安静爬虫 - 纯 HTTP 请求，不开浏览器，不弹窗
直接用 Chrome cookie 调小红书 web 搜索 API
间隔 20-35 秒，降低风险
"""
import json, os, sys, time, random, hashlib, urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from real_crawl import (
    extract_all_xhs_cookies, SEARCH_KEYWORDS, RELEVANCE_KEYWORDS,
    analyze_sentiment, classify_note, is_relevant, build_output,
)

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests', '-q'])
    import requests

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'new_crawl_data2.json')
CLEAN = os.path.join(BASE, 'clean_data.json')
TARGETS = ["美团支付", "云闪付", "京东支付"]

# 进度文件，支持断点续传
PROGRESS_FILE = os.path.join(BASE, 'crawl_progress.json')


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed_keywords": [], "notes": []}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, ensure_ascii=False)


def build_cookie_string(cookies):
    """将 cookie 列表转为请求头字符串"""
    return '; '.join(f"{c['name']}={c['value']}" for c in cookies)


def search_notes_api(session, keyword, cookie_str, page=1):
    """直接调用小红书 web 搜索 API"""
    url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"

    payload = {
        "keyword": keyword,
        "page": page,
        "page_size": 20,
        "search_id": hashlib.md5(f"{keyword}{time.time()}".encode()).hexdigest(),
        "sort": "general",
        "note_type": 0,
        "ext_flags": [],
        "image_formats": ["jpg", "webp", "avif"],
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.xiaohongshu.com",
        "Referer": f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(keyword)}&source=web_search_result_note",
        "Cookie": cookie_str,
    }

    try:
        resp = session.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                return data.get('data', {}).get('items', [])
            elif data.get('code') == -100:
                print(f"    ⚠️ 未登录（cookie失效）")
                return None  # 表示需要重新获取cookie
            else:
                print(f"    ⚠️ API返回 code={data.get('code')}: {data.get('msg','')}")
                return []
        elif resp.status_code == 461:
            print(f"    ⚠️ 被风控(461)，需要等待更久...")
            return "rate_limited"
        else:
            print(f"    ⚠️ HTTP {resp.status_code}")
            return []
    except Exception as e:
        print(f"    ❌ 请求失败: {e}")
        return []


def search_via_web_page(session, keyword, cookie_str, page=1):
    """备选方案：通过访问搜索页面获取数据（从HTML中提取）"""
    url = f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(keyword)}&source=web_search_result_note&page={page}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": cookie_str,
        "Referer": "https://www.xiaohongshu.com/",
    }
    
    try:
        resp = session.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            import re
            # 小红书在 SSR 时会把初始数据放在 window.__INITIAL_STATE__ 中
            match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>', resp.text, re.DOTALL)
            if match:
                try:
                    state = json.loads(match.group(1).replace('undefined', 'null'))
                    notes_data = state.get('search', {}).get('notes', {}).get('items', [])
                    return notes_data
                except:
                    pass
            # 备选：查找 JSON 数据块
            matches = re.findall(r'"note_card":\s*\{[^}]{50,}?\}', resp.text)
            if matches:
                return matches  # 原始文本，后续需要解析
        return []
    except Exception as e:
        print(f"    ❌ 页面请求失败: {e}")
        return []


def parse_note_item(item, platform, category, keyword):
    """解析 API 返回的笔记数据"""
    nc = item.get('note_card', item)
    user_info = nc.get('user', {})
    nid = item.get('id', nc.get('note_id', ''))
    xsec = item.get('xsec_token', '')
    title = nc.get('display_title', '') or ''
    desc = nc.get('desc', '') or ''
    full_text = f"{title} {desc}"
    
    link = f"https://www.xiaohongshu.com/explore/{nid}?xsec_token={xsec}&xsec_source=pc_search" if nid else ''
    
    # 时间处理
    time_str = ''
    ts = nc.get('time', 0)
    if ts:
        try:
            if ts > 1e12: ts = ts / 1000
            time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
        except:
            pass
    if not time_str and nid and len(nid) == 24:
        try:
            ts_from_id = int(nid[:8], 16)
            if 1577836800 < ts_from_id < 1893456000:
                time_str = datetime.fromtimestamp(ts_from_id).strftime('%Y-%m-%d %H:%M')
        except:
            pass
    if not time_str:
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 封面图
    cover = ''
    imgs = nc.get('image_list', [])
    if imgs and isinstance(imgs[0], dict):
        cover = imgs[0].get('url_default', '') or imgs[0].get('url', '')
        if not cover and imgs[0].get('info_list'):
            cover = imgs[0]['info_list'][0].get('url', '')

    cats = [category] + [c for c in classify_note(full_text) if c != category]
    
    return {
        "note_id": nid,
        "platform": platform,
        "title": title,
        "desc": desc[:500],
        "link": link,
        "cover_url": cover,
        "author": user_info.get('nickname', '') or user_info.get('nick_name', ''),
        "author_id": user_info.get('user_id', ''),
        "likes": nc.get('interact_info', {}).get('liked_count', '0'),
        "time": time_str,
        "sentiment": analyze_sentiment(full_text),
        "categories": cats,
        "search_keyword": keyword,
        "note_type": "video" if nc.get('type') == 'video' else "image",
    }


def main():
    print("🤫 安静爬虫 - 纯HTTP请求，不开浏览器")
    print(f"   目标平台: {', '.join(TARGETS)}")
    print(f"   请求间隔: 20-35秒（降低风险）\n")

    # 提取 cookie
    xhs_cookies = extract_all_xhs_cookies()
    if not xhs_cookies:
        print("❌ 无法提取Cookie"); return
    
    ws = [c for c in xhs_cookies if c['name'] == 'web_session' and len(c.get('value', '')) > 10]
    if not ws:
        print("❌ 没有有效web_session"); return
    
    cookie_str = build_cookie_string(xhs_cookies)
    print(f"✅ Cookie就绪 ({len(xhs_cookies)}条)\n")
    
    # 加载已有数据，避免重复
    seen = set()
    if os.path.exists(CLEAN):
        with open(CLEAN) as f:
            for n in json.load(f).get('notes', []):
                if n.get('note_id'): seen.add(n['note_id'])
    print(f"已有 {len(seen)} 条（跳过重复）")
    
    # 加载进度
    progress = load_progress()
    completed_kws = set(progress.get("completed_keywords", []))
    notes = progress.get("notes", [])
    for n in notes:
        if n.get('note_id'): seen.add(n['note_id'])
    if notes:
        print(f"恢复进度: 已有 {len(notes)} 条新数据\n")
    
    # 构建关键词列表
    kws = []
    for plat in TARGETS:
        if plat in SEARCH_KEYWORDS:
            cfg = SEARCH_KEYWORDS[plat]
            for kw, cat, mp in cfg["keywords"]:
                kws.append((plat, kw, cat, mp, cfg.get("icon", "")))
    
    total = len(kws)
    skipped = sum(1 for p, kw, *_ in kws if f"{p}:{kw}" in completed_kws)
    print(f"计划: {total} 个关键词 (已完成{skipped}个)\n")
    
    session = requests.Session()
    consecutive_fails = 0
    api_works = None  # None=未知, True=API可用, False=API不可用
    
    for idx, (plat, kw, cat, max_pages, icon) in enumerate(kws):
        kw_key = f"{plat}:{kw}"
        if kw_key in completed_kws:
            continue
        
        # 显示平台分隔
        if idx == 0 or kws[idx-1][0] != plat:
            print(f"{'─'*40}")
            print(f"{icon} {plat}")
            print(f"{'─'*40}")
        
        print(f"  [{idx+1}/{total}] 🔍 {kw}")
        
        kw_notes = 0
        for page_num in range(1, min(max_pages, 3) + 1):  # 最多3页，减少请求量
            items = search_notes_api(session, kw, cookie_str, page_num)
            
            if items == "rate_limited":
                # 被限流，等更久
                wait = random.uniform(60, 90)
                print(f"    ⏳ 风控限流，等待 {wait:.0f}s...")
                time.sleep(wait)
                items = search_notes_api(session, kw, cookie_str, page_num)
                if items == "rate_limited":
                    print(f"    ⚠️ 仍被限流，跳过此关键词")
                    break
            
            if items is None:
                # cookie失效，重新提取
                print("  🔄 Cookie失效，重新提取...")
                xhs_cookies = extract_all_xhs_cookies()
                if xhs_cookies:
                    cookie_str = build_cookie_string(xhs_cookies)
                    print("  ✅ Cookie已刷新")
                    time.sleep(5)
                    items = search_notes_api(session, kw, cookie_str, page_num)
                else:
                    print("  ❌ 无法提取Cookie，停止")
                    save_progress({"completed_keywords": list(completed_kws), "notes": notes})
                    return
            
            if not items or items == "rate_limited":
                if page_num == 1:
                    consecutive_fails += 1
                break
            
            relevant = 0
            for item in items:
                try:
                    note = parse_note_item(item, plat, cat, kw)
                    nid = note['note_id']
                    if nid and nid not in seen:
                        title = note.get('title', '')
                        desc = note.get('desc', '')
                        if is_relevant(title, desc, plat):
                            seen.add(nid)
                            notes.append(note)
                            kw_notes += 1
                            relevant += 1
                except:
                    pass
            
            print(f"    第{page_num}页: {len(items)}条 → 相关{relevant}条")
            consecutive_fails = 0
            
            if relevant < 2 and page_num > 1:
                break
            
            if page_num < max_pages:
                delay = random.uniform(15, 25)
                time.sleep(delay)
        
        print(f"    ✅ +{kw_notes} (总{len(notes)})")
        completed_kws.add(kw_key)
        
        # 定期保存
        if (idx + 1) % 3 == 0:
            save_progress({"completed_keywords": list(completed_kws), "notes": notes})
            print(f"  💾 进度已保存 ({len(notes)}条)")
        
        # 连续失败检测
        if consecutive_fails >= 3:
            print("\n  ⚠️ 连续失败，暂停60秒后继续...")
            time.sleep(60)
            # 重新提取cookie
            xhs_cookies = extract_all_xhs_cookies()
            if xhs_cookies:
                cookie_str = build_cookie_string(xhs_cookies)
            consecutive_fails = 0
        
        # 关键词间隔 20-35 秒
        delay = random.uniform(20, 35)
        time.sleep(delay)
    
    # 保存最终结果
    if notes:
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(build_output(notes), f, ensure_ascii=False, indent=2)
        print(f"\n🎉 完成！新增 {len(notes)} 条，保存到 {OUT}")
        print("接下来运行: python3 merge_and_build.py")
    else:
        print("\n⚠️ 未获取到新数据")
    
    # 清理进度文件
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)


if __name__ == "__main__":
    main()
