#!/usr/bin/env python3
"""分析数据真实性"""
import json

with open('merged_data.json') as f:
    data = json.load(f)

print('=== merged_data.json 完整分析 ===')
print(f'总条数: {len(data["notes"])}')

# 区分真实 vs 生成
real_notes = []
gen_notes = []
for n in data['notes']:
    if n.get('note_id','').startswith('gen_'):
        gen_notes.append(n)
    else:
        real_notes.append(n)

print(f'\n真实爬取: {len(real_notes)} 条')
print(f'AI生成: {len(gen_notes)} 条')

# 按平台统计
print('\n--- 按平台分布 ---')
platforms = {}
for n in data['notes']:
    p = n.get('platform','')
    is_gen = n.get('note_id','').startswith('gen_')
    if p not in platforms:
        platforms[p] = {'real': 0, 'gen': 0}
    if is_gen:
        platforms[p]['gen'] += 1
    else:
        platforms[p]['real'] += 1

for p, counts in sorted(platforms.items(), key=lambda x: -(x[1]['real']+x[1]['gen'])):
    total = counts['real'] + counts['gen']
    print(f'  {p}: 真实={counts["real"]}, 生成={counts["gen"]}, 总计={total}')

# 检查真实数据链接
print('\n--- 真实数据链接分析 ---')
for n in real_notes[:3]:
    link = n.get('link','')
    print(f'  note_id: {n["note_id"]}')
    print(f'  title: {n.get("title","")[:50]}')
    print(f'  link: {link[:150]}')
    print(f'  platform: {n.get("platform","")}')
    print()

# 检查链接格式问题
print('\n--- 链接格式统计 ---')
has_xsec = sum(1 for n in real_notes if 'xsec_token' in n.get('link',''))
has_explore = sum(1 for n in real_notes if '/explore/' in n.get('link',''))
has_discovery = sum(1 for n in real_notes if '/discovery/' in n.get('link',''))
no_link = sum(1 for n in real_notes if not n.get('link',''))
print(f'  含 xsec_token: {has_xsec}')
print(f'  /explore/ 格式: {has_explore}')
print(f'  /discovery/ 格式: {has_discovery}')
print(f'  无链接: {no_link}')

# 同时检查 real_data.json
with open('real_data.json') as f:
    real_data = json.load(f)
print(f'\n--- real_data.json ---')
print(f'条数: {len(real_data["notes"])}')
rp = {}
for n in real_data['notes']:
    p = n.get('platform','')
    rp[p] = rp.get(p, 0) + 1
for p, c in sorted(rp.items(), key=lambda x: -x[1]):
    print(f'  {p}: {c}')

# 看看 real_data 里的链接
print('\nreal_data.json 链接示例:')
for n in real_data['notes'][:2]:
    print(f'  {n.get("link","")[:150]}')
