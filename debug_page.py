import json, re

with open('netlify-deploy/index.html') as f:
    content = f.read()

# 提取 EMBEDDED_DATA
m = re.search(r'const EMBEDDED_DATA = ({.*?});', content, re.DOTALL)
data = json.loads(m.group(1))

# 检查每个平台
nbp = data.get('notes_by_platform', {})
for p in ['微信支付','支付宝','抖音支付','京东支付','美团支付','云闪付']:
    notes = nbp.get(p, [])
    if not notes:
        print(f'{p}: 0条 !!!')
        continue
    n = notes[0]
    has_cats = bool(n.get('categories'))
    empty_cats = sum(1 for n2 in notes if not n2.get('categories'))
    print(f'{p}: {len(notes)}条, 无categories: {empty_cats}/{len(notes)}')
    if has_cats:
        print(f'  示例categories: {n["categories"][:3]}')

# platforms_config
print('\n=== platforms_config ===')
pc = data.get('platforms_config', {})
for p in pc:
    cats = pc[p].get('categories', [])
    cats_cfg = pc[p].get('categories_config', {})
    print(f'{p}: categories={cats}, config={len(cats_cfg)}项')

# platform_stats
print('\n=== platform_stats ===')
ps = data.get('platform_stats', {})
for p in ps:
    print(f'{p}: total={ps[p].get("total",0)}, cats={list(ps[p].get("category_stats",{}).keys())}')

# 检查 dateFrom 默认值
print('\n=== dateFrom HTML ===')
idx = content.find('dateFrom')
for _ in range(3):
    if idx > 0:
        print(f'  ...{content[max(0,idx-30):idx+80]}...')
        idx = content.find('dateFrom', idx+1)
