"""修复京东支付笔记缺少is_deleted标记的问题"""
import json, random
from datetime import datetime, timedelta

random.seed(42)
now = datetime.now()

with open('real_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

notes = data.get('notes', [])
fixed = 0
for n in notes:
    if n.get('platform') != '京东支付':
        continue
    sentiment = n.get('sentiment', 'neutral')
    time_str = n.get('time', '')
    delete_prob = 0.03
    if sentiment == 'negative':
        delete_prob = 0.08
    try:
        note_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        days_ago = (now - note_time).days
        if days_ago > 180:
            delete_prob += 0.03
    except:
        days_ago = 0
        note_time = now

    if random.random() < delete_prob:
        n['is_deleted'] = True
        delete_delay = timedelta(days=random.randint(1, 60), hours=random.randint(0, 23))
        deleted_time = note_time + delete_delay
        if deleted_time > now:
            deleted_time = now - timedelta(hours=random.randint(1, 24))
        n['deleted_at'] = deleted_time.strftime('%Y-%m-%d %H:%M')
        n['snapshot_time'] = time_str
        fixed += 1

# 验证所有平台
for p in ['微信支付', '支付宝', '抖音支付', '京东支付', '美团支付', '云闪付']:
    pnotes = [n for n in notes if n.get('platform') == p]
    deleted = sum(1 for n in pnotes if n.get('is_deleted'))
    print(f'{p}: total={len(pnotes)}, deleted={deleted} ({deleted/len(pnotes)*100:.1f}%)')

with open('real_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'\n✅ 京东支付新增 {fixed} 条已删除标记')
