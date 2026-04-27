#!/usr/bin/env python3
"""生成4个专题页面：自动续费、海外支付、AI支付、诈骗/盗刷"""
import json, os, html
from datetime import datetime

TOPICS = {
    "auto-renew": {
        "title": "自动续费 / 先用后付专题",
        "icon": "🔄",
        "keywords": ["自动续费", "免密支付", "先用后付", "先享后付", "自动扣费", "乱扣费", "偷偷扣", "自动续", "免密代扣", "连续包月"],
        "desc": "聚焦各平台自动续费、先用后付类客诉舆情，追踪用户反馈趋势"
    },
    "overseas": {
        "title": "海外 / 跨境支付专题",
        "icon": "🌏",
        "keywords": ["海外", "跨境", "境外", "WeChat Pay", "Alipay+", "留学", "外币", "汇款", "退税", "出境", "出国", "国外", "apple pay", "google pay", "免税", "签证"],
        "desc": "跨境支付、海外消费、退税汇款等国际化相关舆情汇总"
    },
    "ai-payment": {
        "title": "AI 支付 / 智能金融专题",
        "icon": "🤖",
        "keywords": ["AI", "人工智能", "混元", "蚂蚁", "智能客服", "风控", "数字人民币", "大模型", "ChatGPT", "deepseek", "机器人"],
        "desc": "AI技术在支付金融领域的应用、讨论和舆情趋势"
    },
    "fraud": {
        "title": "诈骗 / 盗刷客诉专题",
        "icon": "🚨",
        "keywords": ["诈骗", "盗刷", "盗号", "被骗", "追回", "资金安全", "风控误伤", "账户冻结", "封号", "冻结", "骗子", "钓鱼", "套路"],
        "desc": "诈骗盗刷、账户安全、风控误伤等高风险客诉舆情聚合"
    }
}

def match_topic(note, keywords):
    text = (note.get("title","") + " " + note.get("desc","")).lower()
    for kw in keywords:
        if kw.lower() in text:
            return True
    return False

def esc(s):
    return html.escape(str(s)) if s else ""

def generate_topic_page(topic_id, topic, notes):
    platform_stats = {}
    sentiment_stats = {"positive":0, "negative":0, "neutral":0}
    for n in notes:
        p = n.get("platform","未知")
        if p not in platform_stats:
            platform_stats[p] = 0
        platform_stats[p] += 1
        s = n.get("sentiment","neutral")
        if s in sentiment_stats:
            sentiment_stats[s] += 1
    
    top_notes = sorted(notes, key=lambda x: int(x.get("liked_count",0) or 0), reverse=True)[:10]
    
    h = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(topic['title'])} - 支付金融舆情洞察</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'PingFang SC','Microsoft YaHei','Noto Sans SC',sans-serif;background:#f5f5f5;color:#333;line-height:1.8}}
a{{color:#2980b9;text-decoration:none}}
a:hover{{text-decoration:underline}}
.top-bar{{position:sticky;top:0;z-index:100;background:linear-gradient(135deg,#1a5276,#2980b9);color:white;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 8px rgba(0,0,0,.15)}}
.top-bar h1{{font-size:16px;font-weight:600}}
.back-btn{{color:white;text-decoration:none;font-size:13px;display:flex;align-items:center;gap:4px;opacity:.9}}
.back-btn:hover{{opacity:1;text-decoration:none}}
.container{{max-width:800px;margin:0 auto;padding:24px 20px}}
.header{{text-align:center;padding:24px 0 20px;margin-bottom:24px;border-bottom:2px solid #1a5276}}
.header h2{{font-size:22px;color:#1a5276;margin-bottom:6px;display:flex;align-items:center;justify-content:center;gap:8px}}
.header p{{font-size:14px;color:#666}}
.stats-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}}
.stat-box{{flex:1;min-width:120px;background:white;border:1px solid #e5e7eb;border-radius:10px;padding:14px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.stat-box .val{{font-size:24px;font-weight:700;color:#1a5276}}
.stat-box .val.neg{{color:#c0392b}}
.stat-box .val.pos{{color:#27ae60}}
.stat-box .lbl{{font-size:12px;color:#888;margin-top:4px}}
.section-title{{font-size:17px;font-weight:700;color:#1a5276;margin:28px 0 14px;padding-bottom:8px;border-bottom:2px solid #1a5276;display:flex;align-items:center;gap:8px}}
.platform-dist{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px}}
.platform-chip{{padding:6px 14px;border-radius:20px;font-size:13px;background:rgba(26,82,118,0.08);border:1px solid rgba(26,82,118,0.15);color:#1a5276;font-weight:500}}
.note-card{{background:white;border:1px solid #e5e7eb;border-radius:10px;padding:14px;margin-bottom:10px;transition:box-shadow 0.15s;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.note-card:hover{{box-shadow:0 2px 8px rgba(0,0,0,.1)}}
.note-title{{font-size:14px;font-weight:600;margin-bottom:6px;color:#1a1a1a}}
.note-title a{{color:#1a5276}}
.note-meta{{font-size:12px;color:#888;display:flex;gap:12px;flex-wrap:wrap}}
.note-platform{{font-size:11px;padding:2px 8px;border-radius:10px;background:rgba(26,82,118,0.08);color:#1a5276;font-weight:500}}
.sentiment-pos{{color:#27ae60}} .sentiment-neg{{color:#c0392b}} .sentiment-neu{{color:#888}}
.watermark{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%) rotate(-30deg);font-size:60px;color:rgba(0,0,0,.03);pointer-events:none;z-index:1000;white-space:nowrap;font-weight:bold}}
@media(max-width:600px){{
.container{{padding:12px 8px}}
.stats-row{{gap:8px}}
.stat-box{{min-width:80px;padding:10px}}
.stat-box .val{{font-size:18px}}
.top-bar{{padding:10px 12px}}
.top-bar h1{{font-size:14px}}
}}
</style></head><body>
<div class="watermark">FintechInsight</div>
<div class="top-bar">
<a href="../index.html" class="back-btn">← 返回首页</a>
<h1>{topic['icon']} {esc(topic['title'])}</h1>
<span></span>
</div>
<div class="container">
<div class="header">
<h2>{topic['icon']} {esc(topic['title'])}</h2>
<p>{esc(topic['desc'])}</p>
<p style="margin-top:6px;font-size:12px;color:#999">数据截至 {datetime.now().strftime('%Y年%m月%d日')} · 共 {len(notes)} 条相关笔记</p>
</div>

<div class="stats-row">
<div class="stat-box"><div class="val">{len(notes)}</div><div class="lbl">相关笔记</div></div>
<div class="stat-box"><div class="val neg">{sentiment_stats['negative']}</div><div class="lbl">负面</div></div>
<div class="stat-box"><div class="val pos">{sentiment_stats['positive']}</div><div class="lbl">正面</div></div>
<div class="stat-box"><div class="val">{len(platform_stats)}</div><div class="lbl">涉及平台</div></div>
</div>

<div class="section-title">📊 平台分布</div>
<div class="platform-dist">"""
    for p, cnt in sorted(platform_stats.items(), key=lambda x:-x[1]):
        h += f'<span class="platform-chip">{esc(p)} {cnt}条</span>'
    
    h += '</div>\n<div class="section-title">🔥 热门笔记 TOP10</div>'
    
    smap = {"positive":"sentiment-pos","negative":"sentiment-neg","neutral":"sentiment-neu"}
    slabel = {"positive":"正面","negative":"负面","neutral":"中性"}
    for n in top_notes:
        s = n.get("sentiment","neutral")
        link = n.get("link","#")
        h += f"""<div class="note-card">
<div class="note-title"><a href="{esc(link)}" target="_blank">{esc(n.get('title','无标题'))}</a></div>
<div class="note-meta">
<span class="note-platform">{esc(n.get('platform',''))}</span>
<span class="{smap.get(s,'')}">{slabel.get(s,'')}</span>
<span>❤️ {n.get('liked_count',0)}</span>
<span>💬 {n.get('comment_count',0)}</span>
<span>📅 {esc(n.get('time',''))}</span>
<span>{esc(n.get('author',''))}</span>
</div></div>"""
    
    h += "\n</div></body></html>"
    return h

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base, "real_data.json")
    out_dir = os.path.join(base, "netlify-deploy", "reports")
    os.makedirs(out_dir, exist_ok=True)
    
    print("Loading data...")
    with open(data_path, "r") as f:
        data = json.load(f)
    
    all_notes = data.get("notes", [])
    # Ensure platform field exists
    for n in all_notes:
        if "platform" not in n:
            n["platform"] = "未知"
    
    print(f"Total notes: {len(all_notes)}")
    
    for tid, topic in TOPICS.items():
        matched = [n for n in all_notes if match_topic(n, topic["keywords"])]
        print(f"  {topic['title']}: {len(matched)} notes")
        page = generate_topic_page(tid, topic, matched)
        out_path = os.path.join(out_dir, f"topic-{tid}.html")
        with open(out_path, "w") as f:
            f.write(page)
        print(f"  -> {out_path}")
    
    print("Done!")

if __name__ == "__main__":
    main()
