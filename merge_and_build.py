#!/usr/bin/env python3
"""合并新爬取的数据到 clean_data.json 并重建页面"""
import json, os, sys, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
CLEAN = os.path.join(BASE, 'clean_data.json')
NEW = os.path.join(BASE, 'new_crawl_data2.json')

# 读已有数据
existing = []
if os.path.exists(CLEAN):
    with open(CLEAN) as f: existing = json.load(f).get('notes', [])
print(f"已有数据: {len(existing)} 条")

# 读新数据
new_notes = []
if os.path.exists(NEW):
    with open(NEW) as f: new_notes = json.load(f).get('notes', [])
print(f"新爬数据: {len(new_notes)} 条")

if not new_notes:
    print("❌ 没有新数据可合并"); sys.exit(1)

# 合并去重
ids = {n['note_id'] for n in existing if n.get('note_id')}
added = 0
for n in new_notes:
    nid = n.get('note_id', '')
    if nid and nid not in ids:
        existing.append(n); ids.add(nid); added += 1

print(f"新增: {added} 条, 合并后总计: {len(existing)} 条")

# 统计
plats = {}
sentiment = {"positive": 0, "negative": 0, "neutral": 0}
plat_stats = {}
for n in existing:
    p = n.get('platform', '未知')
    plats[p] = plats.get(p, 0) + 1
    if p not in plat_stats:
        plat_stats[p] = {"total": 0, "category_stats": {}, "sentiment_stats": {"positive":0,"negative":0,"neutral":0}}
    plat_stats[p]["total"] += 1
    for c in n.get("categories", []):
        plat_stats[p]["category_stats"][c] = plat_stats[p]["category_stats"].get(c, 0) + 1
    s = n.get("sentiment", "neutral")
    plat_stats[p]["sentiment_stats"][s] += 1
    sentiment[s] += 1

for p, c in sorted(plats.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c} 条")

CONFIGS = {
    "微信支付": {"icon":"💚","color":"#07C160"}, "支付宝": {"icon":"💙","color":"#1677FF"},
    "抖音支付": {"icon":"🖤","color":"#FE2C55"}, "美团支付": {"icon":"💛","color":"#FFC300"},
    "云闪付": {"icon":"🔴","color":"#E60012"}, "京东支付": {"icon":"💎","color":"#E4393C"},
}
cats = ["支付","贷款","理财","AI","海外","组织架构","客诉","其他"]
pcfg = {p: {"icon":c["icon"],"color":c["color"],"categories":cats} for p,c in CONFIGS.items()}

output = {
    "meta": {
        "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "total_notes": len(existing),
        "sentiment_stats": sentiment,
        "platform_stats": plat_stats,
        "platforms_config": pcfg,
        "deleted_stats": {"total_deleted": 0, "per_platform": {}},
        "is_demo": False,
        "data_range": "真实爬取数据",
        "note": "真实小红书数据，Playwright + Chrome Cookie + API拦截"
    },
    "notes": existing
}

with open(CLEAN, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n✅ 已保存到 {CLEAN}")

# 重建页面
print("\n🌐 重建页面...")
r = subprocess.run([sys.executable, os.path.join(BASE, 'build_netlify.py')], capture_output=True, text=True, cwd=BASE)
if r.returncode == 0:
    print("✅ 页面重建成功！")
    # 打印最后几行输出
    lines = r.stdout.strip().split('\n')
    for l in lines[-5:]: print(f"  {l}")
else:
    print(f"❌ 构建失败: {r.stderr[-300:]}")
