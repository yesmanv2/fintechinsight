"""测试小红书真实爬取 - 尝试多种接口"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills', 'xiaohongshutools', 'scripts'))
from request.web.xhs_session import create_xhs_session

async def test():
    print('正在创建游客会话...')
    try:
        xhs = await create_xhs_session(proxy=None, web_session=None)
        print('✅ 会话创建成功！\n')
    except Exception as e:
        print(f'❌ 会话创建失败: {e}')
        return

    # 测试1: 推荐页
    print('=== 测试1: 获取推荐页笔记 ===')
    try:
        res = await xhs.apis.note.get_recommend_notes()
        data = await res.json()
        code = data.get('code') if data else None
        print(f'业务code: {code}')
        if code == 0:
            items = data.get('data', {}).get('items', [])
            print(f'✅ 推荐页获取到 {len(items)} 条笔记')
            for i, item in enumerate(items[:5]):
                nc = item.get('note_card', item)
                title = nc.get('display_title', nc.get('title', ''))
                print(f'  [{i+1}] {title}')
        else:
            print(f'⚠️ 推荐页返回: {data.get("msg", "")}')
    except Exception as e:
        print(f'❌ 推荐页失败: {e}')

    print()

    # 测试2: 搜索（需要登录）
    print('=== 测试2: 搜索笔记（需要登录态） ===')
    try:
        res = await xhs.apis.note.search_notes('支付宝', page=1, page_size=5)
        data = await res.json()
        code = data.get('code') if data else None
        if code == 0:
            items = data.get('data', {}).get('items', [])
            print(f'✅ 搜索到 {len(items)} 条笔记')
        else:
            print(f'⚠️ 搜索需要登录: code={code}, msg={data.get("msg", "")}')
    except Exception as e:
        print(f'⚠️ 搜索接口需要登录态: {str(e)[:100]}')

    await xhs.close_session()
    print('\n测试完成！')

asyncio.run(test())
