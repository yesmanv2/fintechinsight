#!/usr/bin/env python3
"""
只保留真实爬取的数据，修复所有链接（确保xsec_token正确拼接）。
删除所有伪造/生成的数据。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 读取真实爬取数据（不从merged_data.json读，那个被污染了）
real_file = os.path.join(BASE_DIR, "real_data.json")
with open(real_file, "r", encoding="utf-8") as f:
    data = json.load(f)

notes = data["notes"]
print(f"📖 从 real_data.json 读取 {len(notes)} 条数据")

# 统计平台分布
platforms = {}
for n in notes:
    p = n.get("platform", "")
    platforms[p] = platforms.get(p, 0) + 1
print("平台分布:")
for p, c in sorted(platforms.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

# 修复链接：确保 xsec_token 正确拼接
fixed_links = 0
no_xsec = 0
for n in notes:
    link = n.get("link", "")
    xsec = n.get("xsec_token", "")
    note_id = n.get("note_id", "")

    if not link and note_id:
        # 没有链接，用 note_id 构建
        if xsec:
            n["link"] = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec}&xsec_source=pc_search"
            fixed_links += 1
        else:
            n["link"] = f"https://www.xiaohongshu.com/explore/{note_id}"
            no_xsec += 1
    elif link and xsec and "xsec_token" not in link:
        # 有链接但缺少 xsec_token
        sep = "&" if "?" in link else "?"
        n["link"] = f"{link}{sep}xsec_token={xsec}&xsec_source=pc_search"
        fixed_links += 1
    elif link and not xsec:
        no_xsec += 1

print(f"\n🔧 修复了 {fixed_links} 条链接（加上xsec_token）")
print(f"⚠️  {no_xsec} 条没有xsec_token（链接可能打不开）")

# 验证链接
has_xsec_in_link = sum(1 for n in notes if "xsec_token" in n.get("link", ""))
print(f"✅ 链接中包含 xsec_token: {has_xsec_in_link}/{len(notes)}")

# 展示几条修复后的链接
print("\n示例链接:")
for n in notes[:3]:
    print(f"  [{n['platform']}] {n['link'][:120]}")

# 保存到 clean_data.json（纯净的真实数据）
output_file = os.path.join(BASE_DIR, "clean_data.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n✅ 已保存到 clean_data.json，{len(notes)} 条纯真实数据")
