#!/usr/bin/env python3
"""深度分析 2026年数据 - 周度趋势、情感变化率、热点事件识别"""
import json, re
from datetime import datetime, timedelta
from collections import defaultdict, Counter

with open('real_data.json','r') as f:
    data = json.load(f)

notes = data['notes']
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

# 1. 3月 vs 1-2月的变化分析
print("="*60)
print("📊 3月 vs 1-2月变化对比分析")
print("="*60)
plat_list = ['支付宝','微信支付','抖音支付','美团支付','京东支付','云闪付']
for plat in plat_list:
    jan_feb = [n for n in filtered if n['platform']==plat and n['_dt'].month <= 2]
    mar = [n for n in filtered if n['platform']==plat and n['_dt'].month == 3]
    
    if not jan_feb or not mar:
        continue
    
    jf_neg_rate = sum(1 for n in jan_feb if n.get('sentiment')=='negative') / len(jan_feb) * 100
    m_neg_rate = sum(1 for n in mar if n.get('sentiment')=='negative') / len(mar) * 100
    
    jf_daily = len(jan_feb) / 60  # ~60 days
    m_daily = len(mar) / 21  # ~21 days to Mar 21
    
    change = m_neg_rate - jf_neg_rate
    vol_change = (m_daily - jf_daily) / jf_daily * 100
    
    print(f"\n{plat}:")
    print(f"  1-2月: {len(jan_feb)}条, 日均{jf_daily:.1f}条, 负面率{jf_neg_rate:.1f}%")
    print(f"  3月:   {len(mar)}条, 日均{m_daily:.1f}条, 负面率{m_neg_rate:.1f}%")
    print(f"  变化:  声量{'↑' if vol_change>0 else '↓'}{abs(vol_change):.0f}%, 负面率{'↑' if change>0 else '↓'}{abs(change):.1f}pp")

# 2. 各平台核心议题分析
print("\n")
print("="*60)
print("🔍 各平台核心议题（按分类+高频词组合）")
print("="*60)
for plat in plat_list:
    pnotes = [n for n in filtered if n['platform']==plat]
    if not pnotes: continue
    
    # 按分类统计每个分类的典型标题
    cats = defaultdict(list)
    for n in pnotes:
        cat = n.get('category','')
        if cat:
            cats[cat].append(n)
    
    print(f"\n--- {plat} ---")
    for cat, cnotes in sorted(cats.items(), key=lambda x: -len(x[1])):
        # Get top note
        top = max(cnotes, key=lambda x: int(x.get('liked_count','0') or '0'))
        neg_count = sum(1 for n in cnotes if n.get('sentiment')=='negative')
        print(f"  [{cat}] {len(cnotes)}条 (负面{neg_count})")
        print(f"    热门: {top['title'][:60]} (赞{top['liked_count']})")

# 3. 负面舆情事件聚类
print("\n")
print("="*60)
print("⚠️ 负面舆情热点事件（高互动负面笔记 TOP5/平台）")
print("="*60)
for plat in plat_list:
    neg_notes = [n for n in filtered if n['platform']==plat and n.get('sentiment')=='negative']
    if not neg_notes: continue
    
    # Sort by engagement
    neg_notes.sort(key=lambda x: int(x.get('liked_count','0') or '0') + int(x.get('comment_count','0') or '0'), reverse=True)
    
    print(f"\n--- {plat} TOP5负面 ---")
    for n in neg_notes[:5]:
        engagement = int(n.get('liked_count','0') or '0') + int(n.get('comment_count','0') or '0') + int(n.get('collected_count','0') or '0')
        print(f"  [{n['time'][:10]}] {n['title'][:50]}")
        print(f"    赞{n['liked_count']} 评{n['comment_count']} 藏{n['collected_count']} | 分类: {n.get('category','')}")

# 4. AI话题在各平台的分布
print("\n")
print("="*60)
print("🤖 AI话题分析（2026年新兴热点）")
print("="*60)
ai_notes = [n for n in filtered if 'AI' in n.get('categories', [])]
print(f"总量: {len(ai_notes)}条")
ai_by_plat = Counter(n['platform'] for n in ai_notes)
for plat, cnt in ai_by_plat.most_common():
    pct = cnt / len([n for n in filtered if n['platform']==plat]) * 100
    print(f"  {plat}: {cnt}条 (占该平台{pct:.1f}%)")

# AI topic top notes
ai_notes.sort(key=lambda x: int(x.get('liked_count','0') or '0'), reverse=True)
print("\nAI话题最热笔记TOP5:")
for n in ai_notes[:5]:
    print(f"  [{n['platform']}] {n['title'][:50]} (赞{n['liked_count']})")

# 5. 海外话题
print("\n")
print("="*60)
print("🌏 海外话题分析")
print("="*60)
overseas = [n for n in filtered if '海外' in n.get('categories', [])]
print(f"总量: {len(overseas)}条")
ov_by_plat = Counter(n['platform'] for n in overseas)
for plat, cnt in ov_by_plat.most_common():
    print(f"  {plat}: {cnt}条")

overseas.sort(key=lambda x: int(x.get('liked_count','0') or '0'), reverse=True)
print("\n海外话题最热笔记TOP5:")
for n in overseas[:5]:
    print(f"  [{n['platform']}] {n['title'][:50]} (赞{n['liked_count']})")
