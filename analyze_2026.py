#!/usr/bin/env python3
"""分析 2026年1月1日至今的小红书支付金融舆情数据"""
import json, re
from datetime import datetime
from collections import defaultdict, Counter

with open('real_data.json','r') as f:
    data = json.load(f)

notes = data['notes']

# Filter 2026-01-01 onwards
cutoff = datetime(2026, 1, 1)
filtered = []
for n in notes:
    try:
        t = datetime.strptime(n['time'], '%Y-%m-%d %H:%M')
        if t >= cutoff:
            n['_dt'] = t
            filtered.append(n)
    except:
        pass

print(f'=== 总数据: {len(notes)}, 2026年1月1日至今: {len(filtered)} ===')
if not filtered:
    print("没有2026年的数据！")
    # 看看时间范围
    times = []
    for n in notes:
        try:
            times.append(datetime.strptime(n['time'], '%Y-%m-%d %H:%M'))
        except:
            pass
    if times:
        print(f'数据实际时间范围: {min(times)} ~ {max(times)}')
    exit()

print(f'时间范围: {min(n["time"] for n in filtered)} ~ {max(n["time"] for n in filtered)}')
print()

# Per platform stats
platforms = defaultdict(lambda: {
    'total': 0, 'positive': 0, 'negative': 0, 'neutral': 0,
    'categories': Counter(), 'keywords': Counter(),
    'monthly': Counter(),
    'top_liked': None, 'top_liked_count': 0,
    'top_commented': None, 'top_commented_count': 0,
    'authors': Counter(), 'neg_titles': [],
    'monthly_neg': Counter(), 'monthly_pos': Counter(),
})

for n in filtered:
    p = n['platform']
    d = platforms[p]
    d['total'] += 1
    s = n.get('sentiment','neutral')
    if s in d: d[s] += 1
    
    for c in n.get('categories', []):
        d['categories'][c] += 1
    
    for k in n.get('keyword_tags', []):
        d['keywords'][k] += 1
    
    month_key = n['_dt'].strftime('%Y-%m')
    d['monthly'][month_key] += 1
    if s == 'negative': d['monthly_neg'][month_key] += 1
    if s == 'positive': d['monthly_pos'][month_key] += 1
    
    liked = int(n.get('liked_count','0') or '0')
    commented = int(n.get('comment_count','0') or '0')
    if liked > d['top_liked_count']:
        d['top_liked_count'] = liked
        d['top_liked'] = n
    if commented > d['top_commented_count']:
        d['top_commented_count'] = commented
        d['top_commented'] = n
    
    d['authors'][n.get('author','')] += 1
    if s == 'negative':
        d['neg_titles'].append(n.get('title',''))

# Print stats per platform
for plat in ['支付宝','微信支付','抖音支付','美团支付','京东支付','云闪付']:
    d = platforms[plat]
    if d['total'] == 0:
        continue
    neg_rate = d['negative']/d['total']*100
    pos_rate = d['positive']/d['total']*100
    print(f'{"="*15} {plat} {"="*15}')
    print(f'  笔记数: {d["total"]}')
    print(f'  正面: {d["positive"]} ({pos_rate:.1f}%) | 负面: {d["negative"]} ({neg_rate:.1f}%) | 中性: {d["neutral"]}')
    print(f'  分类: {dict(d["categories"].most_common(8))}')
    print(f'  月度:')
    for m in sorted(d['monthly'].keys()):
        t = d['monthly'][m]
        neg = d['monthly_neg'].get(m, 0)
        pos = d['monthly_pos'].get(m, 0)
        print(f'    {m}: {t}条 (正面{pos} 负面{neg} 负面率{neg/t*100:.1f}%)')
    print(f'  独立作者: {len(d["authors"])}人')
    print(f'  高频作者TOP3: {d["authors"].most_common(3)}')
    if d['top_liked']:
        tl = d['top_liked']
        print(f'  最热(赞): [{tl["title"][:50]}] 赞{tl["liked_count"]} 评{tl["comment_count"]} 藏{tl["collected_count"]}')
    if d['top_commented']:
        tc = d['top_commented']
        print(f'  最热(评): [{tc["title"][:50]}] 赞{tc["liked_count"]} 评{tc["comment_count"]} 藏{tc["collected_count"]}')
    
    # Negative title keywords
    neg_words = Counter()
    for title in d['neg_titles']:
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', title)
        for w in words:
            if len(w) >= 2 and w != plat:
                neg_words[w] += 1
    if neg_words:
        print(f'  负面高频词TOP10: {neg_words.most_common(10)}')
    print()

# Overall
print('='*50)
print('整体月度趋势')
print('='*50)
monthly_all = Counter()
monthly_neg = Counter()
monthly_pos = Counter()
for n in filtered:
    mk = n['_dt'].strftime('%Y-%m')
    monthly_all[mk] += 1
    s = n.get('sentiment','neutral')
    if s == 'negative': monthly_neg[mk] += 1
    if s == 'positive': monthly_pos[mk] += 1

for m in sorted(monthly_all.keys()):
    t = monthly_all[m]
    neg = monthly_neg[m]
    pos = monthly_pos[m]
    print(f'  {m}: 总{t}, 正面{pos}({pos/t*100:.1f}%), 负面{neg}({neg/t*100:.1f}%)')

print()
print('='*50)
print('整体分类分布')
print('='*50)
cat_all = Counter()
cat_neg = Counter()
cat_pos = Counter()
for n in filtered:
    cat = n.get('category','')
    if cat:
        cat_all[cat] += 1
        if n.get('sentiment') == 'negative': cat_neg[cat] += 1
        if n.get('sentiment') == 'positive': cat_pos[cat] += 1

for cat, cnt in cat_all.most_common():
    neg = cat_neg[cat]
    pos = cat_pos[cat]
    print(f'  {cat}: {cnt} (正面{pos}/{pos/cnt*100:.1f}%, 负面{neg}/{neg/cnt*100:.1f}%)')

print()
print('='*50)
print('高频关键词TOP20')
print('='*50)
kw_all = Counter()
for n in filtered:
    for k in n.get('keyword_tags', []):
        kw_all[k] += 1
for k, c in kw_all.most_common(20):
    print(f'  {k}: {c}')

print()
print('='*50)
print('负面笔记标题高频词TOP30')
print('='*50)
neg_words_all = Counter()
for n in filtered:
    if n.get('sentiment') == 'negative':
        title = n.get('title','')
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', title)
        for w in words:
            neg_words_all[w] += 1
for w, c in neg_words_all.most_common(30):
    print(f'  {w}: {c}')

# Platform cross-comparison
print()
print('='*50)
print('平台横向对比（2026年）')
print('='*50)
plat_list = ['支付宝','微信支付','抖音支付','美团支付','京东支付','云闪付']
print(f'{"平台":<8} {"笔记数":>6} {"正面率":>7} {"负面率":>7} {"客诉占比":>8} {"独立作者":>8}')
for plat in plat_list:
    d = platforms[plat]
    if d['total'] == 0: continue
    pos_r = d['positive']/d['total']*100
    neg_r = d['negative']/d['total']*100
    kesu = d['categories'].get('客诉', 0)
    kesu_r = kesu/d['total']*100
    auth = len(d['authors'])
    print(f'{plat:<8} {d["total"]:>6} {pos_r:>6.1f}% {neg_r:>6.1f}% {kesu_r:>7.1f}% {auth:>8}')
