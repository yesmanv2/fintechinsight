#!/usr/bin/env python3
"""合并支付宝新数据：删除旧的192条，换上新爬的1554条"""
import json, os
from datetime import datetime
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))

# 读取 clean_data
with open(os.path.join(BASE, 'clean_data.json')) as f:
    clean = json.load(f)

old_notes = clean['notes']
print(f'旧数据总量: {len(old_notes)}')

# 去掉旧的支付宝数据
non_alipay = [n for n in old_notes if n.get('platform') != '支付宝']
old_alipay = [n for n in old_notes if n.get('platform') == '支付宝']
print(f'去掉旧支付宝: {len(old_alipay)} 条')
print(f'其他平台保留: {len(non_alipay)} 条')

# 读取两轮新数据
new_notes = []
seen = set()
for fname in ['alipay_crawl_data.json', 'alipay_crawl_data2.json']:
    fpath = os.path.join(BASE, fname)
    if not os.path.exists(fpath):
        print(f'⚠️ {fname} 不存在，跳过')
        continue
    with open(fpath) as f:
        data = json.load(f)
    for n in data.get('notes', []):
        nid = n.get('note_id')
        if nid and nid not in seen:
            seen.add(nid)
            new_notes.append(n)
    print(f'{fname}: {len(data.get("notes",[]))} 条 (去重后累计 {len(new_notes)})')

# 合并
all_notes = non_alipay + new_notes
print(f'\n合并后总量: {len(all_notes)}')

# 统计
platforms = Counter(n.get('platform', '') for n in all_notes)
print('各平台分布:')
for p, c in platforms.most_common():
    print(f'  {p}: {c}')

sentiments = Counter(n.get('sentiment', '中性') for n in all_notes)

clean['notes'] = all_notes
clean['meta']['total_notes'] = len(all_notes)
clean['meta']['crawl_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
clean['meta']['sentiment_stats'] = dict(sentiments)

with open(os.path.join(BASE, 'clean_data.json'), 'w') as f:
    json.dump(clean, f, ensure_ascii=False, indent=2)
print(f'\n✅ 已保存到 clean_data.json: {len(all_notes)} 条')
