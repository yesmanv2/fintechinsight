"""修复 real_data.json 的 platform_stats，使其与实际 notes 数据一致"""
import json
from collections import Counter

with open('real_data.json', 'r') as f:
    data = json.load(f)

notes = data.get('notes', [])
meta = data.get('meta', {})

# 重新计算 platform_stats
platform_stats = {}
for note in notes:
    p = note.get('platform', '支付宝')
    if p not in platform_stats:
        platform_stats[p] = {
            'total': 0,
            'category_stats': {},
            'sentiment_stats': {'positive': 0, 'negative': 0, 'neutral': 0}
        }
    ps = platform_stats[p]
    ps['total'] += 1

    cat = note.get('category', '其他') or '其他'
    ps['category_stats'][cat] = ps['category_stats'].get(cat, 0) + 1

    sent = note.get('sentiment', '中性')
    if sent in ['正面', 'positive']:
        ps['sentiment_stats']['positive'] += 1
    elif sent in ['负面', 'negative']:
        ps['sentiment_stats']['negative'] += 1
    else:
        ps['sentiment_stats']['neutral'] += 1

# 更新 meta
meta['platform_stats'] = platform_stats
meta['total_notes'] = len(notes)
data['meta'] = meta

print('=== 新的 platform_stats ===')
for p, ps in sorted(platform_stats.items(), key=lambda x: -x[1]['total']):
    print(f'  {p}: total={ps["total"]}, cats={ps["category_stats"]}')

with open('real_data.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 同步到 clean_data.json
with open('clean_data.json', 'r') as f:
    clean = json.load(f)
clean['meta']['platform_stats'] = platform_stats
clean['meta']['total_notes'] = len(notes)
with open('clean_data.json', 'w') as f:
    json.dump(clean, f, ensure_ascii=False, indent=2)

print(f'\n✅ 已更新 real_data.json 和 clean_data.json (总 {len(notes)} 条)')
