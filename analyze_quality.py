import json
from collections import Counter

d = json.load(open('real_data.json'))
notes = d['notes']

high_quality = []
medium_quality = []
garbage = []

for n in notes:
    has_title = bool(n.get('title','').strip())
    has_author = bool(n.get('author','').strip())
    likes = int(n.get('liked_count','0') or 0)
    comments = int(n.get('comment_count','0') or 0)
    collected = int(n.get('collected_count','0') or 0)
    has_interactions = likes > 0 or comments > 0 or collected > 0
    
    if has_title and has_author and has_interactions:
        high_quality.append(n)
    elif has_title and (has_author or has_interactions):
        medium_quality.append(n)
    else:
        garbage.append(n)

print(f'总笔记: {len(notes)}')
print(f'高质量 (有标题+作者+互动): {len(high_quality)}')
print(f'中等 (有标题+部分信息): {len(medium_quality)}')
print(f'垃圾 (基本无信息): {len(garbage)}')

print(f'\n=== 垃圾数据样本 ===')
for n in garbage[:10]:
    print(f'  title:[{n.get("title","")}] author:[{n.get("author","")}] likes:{n.get("liked_count",0)} time:{n.get("time","")} kw:{n.get("search_keyword","")}')

crawl_time = [n for n in notes if n.get('time','').startswith('2026-03-19 16:')]
real_time = [n for n in notes if not n.get('time','').startswith('2026-03-19 16:')]
print(f'\n=== 时间分析 ===')
print(f'爬取时间(2026-03-19 16:xx): {len(crawl_time)}')
print(f'真实时间: {len(real_time)}')

# desc分析
has_desc = sum(1 for n in notes if n.get('desc','').strip())
print(f'\n有描述内容: {has_desc}/{len(notes)}')

# 检查哪些数据的note_id格式不是标准24位hex
bad_ids = [n for n in notes if len(n.get('note_id','')) != 24 or not all(c in '0123456789abcdef' for c in n.get('note_id',''))]
print(f'非标准note_id: {len(bad_ids)}')
for n in bad_ids[:5]:
    print(f'  id:[{n.get("note_id","")}] title:[{n.get("title","")[:30]}]')
