"""修复 real_data.json 中的时间和链接问题"""
import json
from datetime import datetime

d = json.load(open('real_data.json'))
notes = d['notes']

fixed_time = 0
fixed_link = 0
failed_time = 0

for n in notes:
    nid = n['note_id']
    
    # 修复时间：从 note_id 前8位hex提取真实发布时间（MongoDB ObjectID格式）
    if nid and len(nid) == 24:
        try:
            ts = int(nid[:8], 16)
            if 1577836800 < ts < 1893456000:  # 2020~2030
                n['time'] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                fixed_time += 1
            else:
                failed_time += 1
        except Exception:
            failed_time += 1
    else:
        failed_time += 1
    
    # 修复链接：去掉 xsec_token，使用纯净链接
    if '?xsec_token=' in n.get('link', ''):
        n['link'] = n['link'].split('?')[0]
        fixed_link += 1

# 保存
with open('real_data.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print(f'✅ 修复时间: {fixed_time} 条, 无法修复: {failed_time} 条')
print(f'✅ 修复链接: {fixed_link} 条')

# 验证
times = [n['time'] for n in notes]
print(f'\n最早时间: {min(times)}')
print(f'最新时间: {max(times)}')

# 检查时间分布
from collections import Counter
months = Counter(t[:7] for t in times)
print(f'\n按月分布:')
for m in sorted(months.keys()):
    print(f'  {m}: {months[m]} 条')

# 验证链接
print(f'\n链接示例:')
for n in notes[:5]:
    print(f'  {n["time"]}  {n["link"][:55]}  {n["title"][:30]}')
