"""将data.json中的已删除笔记合并到real_data.json并更新统计"""
import json

with open('real_data.json', 'r', encoding='utf-8') as f:
    real_data = json.load(f)

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 提取已删除笔记
deleted_notes = [n for n in data.get('notes', []) if n.get('is_deleted')]
print(f'从data.json找到 {len(deleted_notes)} 条已删除笔记')

# 去重
existing_ids = set()
for n in real_data.get('notes', []):
    key = n.get('note_id') or f"{n.get('title','')}-{n.get('author','')}-{n.get('platform','')}"
    existing_ids.add(key)

new_deleted = []
for n in deleted_notes:
    key = n.get('note_id') or f"{n.get('title','')}-{n.get('author','')}-{n.get('platform','')}"
    if key not in existing_ids:
        new_deleted.append(n)
        existing_ids.add(key)

print(f'去重后新增 {len(new_deleted)} 条已删除笔记')

# 合并
real_data['notes'].extend(new_deleted)
notes = real_data['notes']
print(f'合并后总笔记数: {len(notes)}')

# 更新统计
platform_stats = {}
for n in notes:
    p = n.get('platform', '未知')
    if p not in platform_stats:
        platform_stats[p] = {'total': 0, 'category_stats': {}, 'sentiment_stats': {'positive': 0, 'negative': 0, 'neutral': 0}}
    platform_stats[p]['total'] += 1
    for cat in n.get('categories', []):
        platform_stats[p]['category_stats'][cat] = platform_stats[p]['category_stats'].get(cat, 0) + 1
    sent = n.get('sentiment', 'neutral')
    if sent in platform_stats[p]['sentiment_stats']:
        platform_stats[p]['sentiment_stats'][sent] += 1

real_data['meta']['platform_stats'] = platform_stats
real_data['meta']['total_notes'] = len(notes)

total_sentiment = {'positive': 0, 'negative': 0, 'neutral': 0}
for ps in platform_stats.values():
    for k, v in ps['sentiment_stats'].items():
        total_sentiment[k] = total_sentiment.get(k, 0) + v
real_data['meta']['sentiment_stats'] = total_sentiment

# 保持platforms_config不变
with open('real_data.json', 'w', encoding='utf-8') as f:
    json.dump(real_data, f, ensure_ascii=False, indent=2)

for p, ps in platform_stats.items():
    deleted_count = len([n for n in notes if n.get('platform') == p and n.get('is_deleted')])
    print(f'  {p}: total={ps["total"]}, deleted={deleted_count}')

print(f'\n✅ real_data.json 已更新，总计 {len(notes)} 条')
