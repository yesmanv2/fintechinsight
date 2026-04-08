"""
合并多个爬虫输出为一个完整的 real_data.json
"""
import json, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 要合并的数据文件
files = [
    os.path.join(BASE_DIR, 'real_data.json'),
    os.path.join(BASE_DIR, 'other_platforms_data.json'),
]

ICONS = {"支付宝": "💙", "微信支付": "💚", "抖音支付": "🖤", "美团支付": "💛", "云闪付": "🔴", "京东支付": "💎"}
COLORS = {"支付宝": "#1677FF", "微信支付": "#07C160", "抖音支付": "#FE2C55", "美团支付": "#FFC300", "云闪付": "#E60012", "京东支付": "#E4393C"}

all_notes = []
seen_ids = set()
all_platforms_config = {}

for fpath in files:
    if not os.path.exists(fpath):
        print(f"⚠️ 跳过不存在的文件: {fpath}")
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    notes = data.get('notes', [])
    added = 0
    for n in notes:
        nid = n.get('note_id', '')
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            all_notes.append(n)
            added += 1
    print(f"✅ {os.path.basename(fpath)}: {len(notes)} 条, 新增 {added} 条 (去重后)")

    # 合并 platforms_config
    pc = data.get('meta', {}).get('platforms_config', {})
    all_platforms_config.update(pc)

# 确保所有平台都有配置
for p in set(n.get('platform', '') for n in all_notes):
    if p and p not in all_platforms_config:
        all_platforms_config[p] = {
            "icon": ICONS.get(p, "📌"),
            "color": COLORS.get(p, "#6366f1"),
            "categories": [],
        }

# 重新计算统计
platform_stats = {}
for note in all_notes:
    p = note.get('platform', '未知')
    if p not in platform_stats:
        platform_stats[p] = {"total": 0, "category_stats": {}, "sentiment_stats": {"positive": 0, "negative": 0, "neutral": 0}}
    platform_stats[p]["total"] += 1
    for cat in note.get("categories", []):
        platform_stats[p]["category_stats"][cat] = platform_stats[p]["category_stats"].get(cat, 0) + 1
    s = note.get("sentiment", "neutral")
    platform_stats[p]["sentiment_stats"][s] = platform_stats[p]["sentiment_stats"].get(s, 0) + 1

sentiment_stats = {"positive": 0, "negative": 0, "neutral": 0}
for ps in platform_stats.values():
    for k in sentiment_stats:
        sentiment_stats[k] += ps["sentiment_stats"].get(k, 0)

# 确保 platforms_config 里有所有分类
for p, pstat in platform_stats.items():
    if p in all_platforms_config:
        existing_cats = set(all_platforms_config[p].get('categories', []))
        data_cats = set(pstat.get('category_stats', {}).keys())
        all_platforms_config[p]['categories'] = list(existing_cats | data_cats)

output = {
    "meta": {
        "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "total_notes": len(all_notes),
        "sentiment_stats": sentiment_stats,
        "platform_stats": platform_stats,
        "platforms_config": all_platforms_config,
        "is_demo": False,
        "data_range": "真实爬取数据",
        "note": "真实小红书数据，Playwright Stealth + Chrome Cookie 注入 + API 拦截",
    },
    "notes": all_notes,
}

out_file = os.path.join(BASE_DIR, 'real_data.json')
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n{'=' * 60}")
print(f"🎉 合并完成！总计 {len(all_notes)} 条")
print(f"{'=' * 60}")
for p_name in sorted(platform_stats.keys()):
    icon = ICONS.get(p_name, "📌")
    total = platform_stats[p_name]['total']
    cats = ', '.join(f"{c}:{n}" for c, n in sorted(platform_stats[p_name]['category_stats'].items(), key=lambda x: -x[1])[:5])
    print(f"  {icon} {p_name}: {total} 条 ({cats})")
print(f"\n💾 已保存: {out_file}")
