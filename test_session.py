"""快速测试 cookie 是否可用"""
import asyncio, sys, os, json
sys.path.insert(0, 'skills/xiaohongshutools/scripts')
from request.web.xhs_session import create_xhs_session

async def test():
    with open('cookie.txt') as f:
        session = f.read().strip()
    print(f'🔑 Cookie: {session[:15]}...')
    
    xhs = await create_xhs_session(proxy=None, web_session=session)
    print('✅ 会话创建成功, 测试搜索「支付宝支付」...')
    
    res = await xhs.apis.note.search_notes('支付宝支付', page=1, page_size=5, sort='general', note_type=0)
    data = await res.json()
    code = data.get('code', -1) if data else -1
    print(f'响应 code: {code}')
    
    if code == 0:
        # 打印完整数据结构来debug
        data_keys = list(data.get('data', {}).keys()) if data.get('data') else []
        print(f'data 顶级 keys: {data_keys}')
        
        items = data.get('data', {}).get('items', [])
        if not items:
            # 可能 items 在其他位置
            notes_list = data.get('data', {}).get('notes', [])
            print(f'notes_list: {len(notes_list)} 条')
            # 打印前500字符看结构
            print(json.dumps(data, ensure_ascii=False)[:1500])
        else:
            print(f'🎉 成功！获取到 {len(items)} 条真实笔记:')
            for i, item in enumerate(items[:5]):
                nc = item.get('note_card', item)
                title = nc.get('display_title', '')
                user = nc.get('user', {}).get('nickname', '')
                likes = nc.get('interact_info', {}).get('liked_count', '?')
                print(f'  [{i+1}] {title}')
                print(f'      👤 {user} | ❤️ {likes}')
    else:
        msg = data.get('msg', '') if data else ''
        print(f'❌ 失败: code={code}, msg={msg}')
        print(json.dumps(data, ensure_ascii=False)[:800])
    
    await xhs.close_session()

asyncio.run(test())
