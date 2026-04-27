#!/usr/bin/env python3
"""
build_reports.py - 标准化平台月报生成器

从 monthly_analysis.json + real_data.json 生成统一结构的6份平台月报HTML。
每份报告包含5个固定模块：
  1. 本月结论（Executive Summary）
  2. 新增变化（与上月对比）
  3. 典型案例（代表性帖子）
  4. 值得关注的问题
  5. 横向对比一句话

用法: python3 build_reports.py [--month 2026-03] [--output-dir netlify-deploy/reports]
"""

import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PLATFORMS = ["微信支付", "支付宝", "抖音支付", "京东支付", "美团支付", "云闪付"]

PLATFORM_SLUG = {
    "微信支付": "wxpay",
    "支付宝": "alipay",
    "抖音支付": "douyinpay",
    "京东支付": "jdpay",
    "美团支付": "meituanpay",
    "云闪付": "unionpay",
}

PLATFORM_COLOR = {
    "微信支付": "#07C160",
    "支付宝": "#1677FF",
    "抖音支付": "#FE2C55",
    "京东支付": "#E2231A",
    "美团支付": "#FFD100",
    "云闪付": "#E60012",
}

PLATFORM_ACCENT_TEXT = {
    "美团支付": "#333",  # 黄底用深色文字
}


def load_data(month_key):
    """加载 monthly_analysis.json 和 real_data.json"""
    ma_path = os.path.join(BASE_DIR, "monthly_analysis.json")
    rd_path = os.path.join(BASE_DIR, "real_data.json")

    with open(ma_path, "r", encoding="utf-8") as f:
        monthly_analysis = json.load(f)

    with open(rd_path, "r", encoding="utf-8") as f:
        rd_raw = json.load(f)
    # real_data.json 结构: {"meta": ..., "notes": [...]}
    real_data = rd_raw.get("notes", rd_raw) if isinstance(rd_raw, dict) else rd_raw

    return monthly_analysis, real_data


def get_month_data(monthly_analysis, month_key):
    """获取指定月份的数据"""
    monthly = monthly_analysis.get("monthly", {})
    return monthly.get(month_key, {})


def get_prev_month_key(month_key):
    """计算上月 key"""
    y, m = month_key.split("-")
    y, m = int(y), int(m)
    if m == 1:
        return f"{y-1}-{12:02d}"
    return f"{y}-{m-1:02d}"


def filter_notes_by_platform(real_data, platform, month_key):
    """从 real_data 中按平台和月份筛选笔记"""
    notes = []
    for note in real_data:
        if note.get("platform") != platform:
            continue
        t = note.get("time", "")
        if t.startswith(month_key):
            notes.append(note)
    return notes


def get_top_notes(notes, key="liked_count", limit=5):
    """获取互动量最高的帖子"""
    def safe_int(n, k):
        v = n.get(k, 0)
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0
    sorted_notes = sorted(notes, key=lambda n: safe_int(n, key), reverse=True)
    return sorted_notes[:limit]


def get_complaint_notes(notes):
    """获取客诉类帖子（categories 含 '客诉'）"""
    result = []
    for n in notes:
        cats = n.get("categories", [])
        if isinstance(cats, str):
            cats = [cats]
        if "客诉" in cats:
            result.append(n)
    return result


def get_negative_notes(notes):
    """获取负面帖子"""
    return [n for n in notes if n.get("sentiment") == "negative"]


def format_number(n):
    """格式化数字"""
    try:
        n = int(n)
    except (ValueError, TypeError):
        return str(n)
    if n >= 10000:
        return f"{n/10000:.1f}万"
    return f"{n:,}"


def esc(text):
    """HTML转义"""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_report_html(platform, month_key, monthly_analysis, real_data):
    """为指定平台生成标准化月报HTML"""
    month_data = get_month_data(monthly_analysis, month_key)
    if not month_data:
        print(f"  [跳过] {platform}: 无 {month_key} 月度数据")
        return None

    platforms_data = month_data.get("platforms", {})
    pdata = platforms_data.get(platform, {})
    if not pdata:
        print(f"  [跳过] {platform}: 无平台详细数据")
        return None

    cross = month_data.get("cross_platform", {})
    summary = month_data.get("summary", "")
    stats = pdata.get("stats", {})
    vs = pdata.get("vs_last_month", {})
    insights = pdata.get("insights", [])
    neg_clusters = pdata.get("neg_clusters", [])
    top_liked = pdata.get("top_liked", {})
    top_commented = pdata.get("top_commented", {})
    top_cats = pdata.get("top_categories", [])
    neg_words = pdata.get("neg_words", [])

    # 获取本月笔记
    notes = filter_notes_by_platform(real_data, platform, month_key)
    neg_notes = get_negative_notes(notes)
    top_notes = get_top_notes(notes, "liked_count", 5)

    color = PLATFORM_COLOR.get(platform, "#6366F1")
    text_color = PLATFORM_ACCENT_TEXT.get(platform, "#fff")
    y, m = month_key.split("-")

    # 构建 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{platform}客诉分析报告_{y}年{int(m):02d}月 - 在线预览</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            -webkit-user-select: none; -moz-user-select: none; user-select: none;
            -webkit-touch-callout: none;
            font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
            background: #f5f5f5; color: #333; line-height: 1.8;
        }}
        .top-bar {{
            position: sticky; top: 0; z-index: 100;
            background: {color}; color: {text_color};
            padding: 12px 24px; display: flex; align-items: center; justify-content: space-between;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .top-bar h1 {{ font-size: 16px; font-weight: 600; }}
        .top-bar .badge {{ font-size: 11px; background: rgba(255,255,255,0.2); padding: 3px 12px; border-radius: 12px; }}
        .top-bar .back-btn {{
            color: {text_color}; text-decoration: none; font-size: 13px;
            padding: 6px 16px; border: 1px solid rgba(255,255,255,0.4); border-radius: 6px; transition: background 0.2s;
        }}
        .top-bar .back-btn:hover {{ background: rgba(255,255,255,0.15); }}
        .watermark {{
            position: fixed; top:0;left:0;right:0;bottom:0; pointer-events:none; z-index:50;
            background-image: repeating-linear-gradient(-45deg,transparent,transparent 200px,rgba(0,0,0,0.012) 200px,rgba(0,0,0,0.012) 201px);
        }}
        .watermark::after {{
            content: '仅供在线阅读 · FinTech Insight';
            position: fixed; top:50%;left:50%; transform:translate(-50%,-50%) rotate(-30deg);
            font-size: 48px; color: rgba(0,0,0,0.03); white-space: nowrap; pointer-events: none; font-weight: 700;
        }}
        .doc {{ max-width: 800px; margin: 24px auto; background: #fff; border-radius: 8px; box-shadow: 0 1px 6px rgba(0,0,0,0.08); padding: 48px 56px; position: relative; }}
        .doc h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 20px; color: #1a1a1a; border-bottom: 3px solid {color}; padding-bottom: 12px; }}
        .doc h2 {{ font-size: 20px; font-weight: 700; margin: 32px 0 14px; color: #1a1a1a; padding-left: 12px; border-left: 4px solid {color}; }}
        .doc h3 {{ font-size: 16px; font-weight: 600; margin: 20px 0 10px; color: #333; }}
        .doc p {{ margin-bottom: 10px; font-size: 14px; color: #444; text-align: justify; }}
        .doc p.center {{ text-align: center; }}
        .doc .spacer {{ height: 12px; }}
        .doc table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }}
        .doc th {{ background: #f0f2f5; padding: 10px 12px; border: 1px solid #ddd; font-weight: 600; text-align: left; }}
        .doc td {{ padding: 8px 12px; border: 1px solid #ddd; }}
        .doc tr:hover td {{ background: #fafafa; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }}
        .kpi {{ background: #f8f9fa; border-radius: 8px; padding: 16px; text-align: center; border: 1px solid #eee; }}
        .kpi .val {{ font-size: 24px; font-weight: 700; color: {color}; }}
        .kpi .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .kpi .change {{ font-size: 11px; margin-top: 2px; }}
        .kpi .change.up {{ color: #ef4444; }}
        .kpi .change.down {{ color: #22c55e; }}
        .note-card {{ background: #fafafa; border: 1px solid #eee; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; }}
        .note-card .title {{ font-size: 14px; font-weight: 600; color: #1a1a1a; margin-bottom: 4px; }}
        .note-card .meta {{ font-size: 12px; color: #888; }}
        .note-card .meta span {{ margin-right: 12px; }}
        .note-card a {{ color: {color}; text-decoration: none; font-size: 12px; }}
        .note-card a:hover {{ text-decoration: underline; }}
        .tag {{ display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-right: 4px; }}
        .tag.neg {{ background: rgba(239,68,68,0.1); color: #ef4444; }}
        .tag.pos {{ background: rgba(34,197,94,0.1); color: #22c55e; }}
        .tag.neu {{ background: rgba(156,163,175,0.1); color: #6b7280; }}
        .insight-box {{ background: #fffbeb; border-left: 3px solid #f59e0b; padding: 12px 16px; margin-bottom: 10px; border-radius: 0 8px 8px 0; font-size: 13px; color: #92400e; }}
        .neg-cluster {{ background: rgba(239,68,68,0.05); border-left: 3px solid #ef4444; padding: 10px 14px; margin-bottom: 8px; border-radius: 0 6px 6px 0; font-size: 13px; color: #991b1b; }}
        .section-nav {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; padding: 12px 16px; background: #f8f9fa; border-radius: 8px; }}
        .section-nav a {{ font-size: 12px; color: #666; text-decoration: none; padding: 4px 12px; border-radius: 16px; border: 1px solid #ddd; transition: all 0.15s; }}
        .section-nav a:hover {{ background: {color}; color: {text_color}; border-color: {color}; }}
        .footer-note {{ text-align: center; padding: 20px; font-size: 12px; color: #999; }}
        @media print {{ body {{ display: none !important; }} }}
        @media (max-width: 768px) {{
            .doc {{ margin: 12px; padding: 24px 20px; }}
            .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="top-bar">
        <div style="display:flex;align-items:center;gap:12px">
            <h1>📄 {platform}客诉分析报告_{y}年{int(m):02d}月</h1>
            <span class="badge">在线预览</span>
        </div>
        <a class="back-btn" href="../" onclick="history.back();return false;">← 返回</a>
    </div>
    <div class="watermark"></div>
    <div class="doc">
"""

    # 封面
    html += f"""
        <div class="spacer"></div>
        <p class="center"><span style="font-weight:700;color:rgb(26,60,110);font-size:28pt">{platform}客诉分析报告</span></p>
        <p class="center"><span style="color:#666">基于小红书舆情数据 · {y}年{int(m)}月</span></p>
        <div class="spacer"></div>
        <p class="center"><b>分析时间：</b><span style="color:{color}">{datetime.now().strftime('%Y年%m月%d日')}</span></p>
        <p class="center"><b>本月样本量：</b><span style="color:{color}">{stats.get('total', 0)}条</span></p>
        <p class="center"><b>负面率：</b><span style="color:{color}">{stats.get('neg_rate', 0)}%</span></p>
        <div class="spacer"></div>
"""

    # 快速导航
    html += """
        <div class="section-nav">
            <a href="#sec1">📋 本月结论</a>
            <a href="#sec2">📊 新增变化</a>
            <a href="#sec3">📝 典型案例</a>
            <a href="#sec4">⚠️ 值得关注</a>
            <a href="#sec5">🔀 横向对比</a>
        </div>
"""

    # === 模块 1: 本月结论 (Executive Summary) ===
    html += f'        <h2 id="sec1">一、本月结论</h2>\n'
    html += '        <div class="spacer"></div>\n'

    # KPI 卡片
    total = stats.get("total", 0)
    pos = stats.get("positive", 0)
    neg = stats.get("negative", 0)
    neu = stats.get("neutral", 0)
    pos_rate = stats.get("pos_rate", 0)
    neg_rate = stats.get("neg_rate", 0)

    total_change = vs.get("total_change", "")
    neg_change = vs.get("neg_rate_change", "")
    pos_change = vs.get("pos_rate_change", "")

    def change_class(c):
        if not c:
            return ""
        return "up" if c.startswith("+") else "down"

    html += '        <div class="kpi-grid">\n'
    html += f'            <div class="kpi"><div class="val">{total}</div><div class="label">本月声量</div>'
    if total_change:
        html += f'<div class="change {change_class(total_change)}">环比 {total_change}</div>'
    html += '</div>\n'
    html += f'            <div class="kpi"><div class="val" style="color:#ef4444">{neg}</div><div class="label">负面帖子</div>'
    if neg_change:
        html += f'<div class="change {change_class(neg_change)}">负面率变化 {neg_change}</div>'
    html += '</div>\n'
    html += f'            <div class="kpi"><div class="val" style="color:#22c55e">{pos}</div><div class="label">正面帖子</div>'
    if pos_change:
        html += f'<div class="change {change_class(pos_change)}">正面率变化 {pos_change}</div>'
    html += '</div>\n'
    html += f'            <div class="kpi"><div class="val" style="color:#6b7280">{neu}</div><div class="label">中性帖子</div></div>\n'
    html += '        </div>\n'

    # 关键洞察
    if insights:
        html += '        <h3>关键洞察</h3>\n'
        for ins in insights:
            html += f'        <div class="insight-box">{esc(ins)}</div>\n'

    # 话题分类
    if top_cats:
        html += '        <h3>话题分类 Top 5</h3>\n'
        html += '        <table><tr><th>分类</th><th>帖子数</th><th>占比</th></tr>\n'
        for cat, count in top_cats[:5]:
            pct = round(count / total * 100, 1) if total > 0 else 0
            html += f'        <tr><td>{esc(cat)}</td><td>{count}</td><td>{pct}%</td></tr>\n'
        html += '        </table>\n'

    # === 模块 2: 新增变化（与上月对比）===
    html += f'\n        <h2 id="sec2">二、新增变化（与上月对比）</h2>\n'
    html += '        <div class="spacer"></div>\n'

    total_last = vs.get("total_last", 0)
    neg_rate_last = vs.get("neg_rate_last", 0)
    pos_rate_last = vs.get("pos_rate_last", 0)

    if vs:
        html += '        <table>\n'
        html += '        <tr><th>指标</th><th>上月</th><th>本月</th><th>变化</th></tr>\n'
        html += f'        <tr><td>总声量</td><td>{total_last}</td><td>{total}</td><td>{total_change}</td></tr>\n'
        html += f'        <tr><td>负面率</td><td>{neg_rate_last}%</td><td>{neg_rate}%</td><td>{neg_change}</td></tr>\n'
        html += f'        <tr><td>正面率</td><td>{pos_rate_last}%</td><td>{pos_rate}%</td><td>{pos_change}</td></tr>\n'
        html += '        </table>\n'

        # 变化解读
        html += '        <h3>变化解读</h3>\n'
        if total_change and total_change.startswith("+"):
            html += f'        <p>本月声量{total}条，较上月{total_last}条<b>增长{total_change}</b>，关注度显著提升。</p>\n'
        elif total_change:
            html += f'        <p>本月声量{total}条，较上月{total_last}条变化{total_change}。</p>\n'

        if neg_change and neg_change.startswith("+"):
            html += f'        <p>负面率从{neg_rate_last}%升至{neg_rate}%（{neg_change}），<b style="color:#ef4444">负面情绪有所上升</b>，需重点关注。</p>\n'
        elif neg_change and neg_change.startswith("-"):
            html += f'        <p>负面率从{neg_rate_last}%降至{neg_rate}%（{neg_change}），<b style="color:#22c55e">负面情绪有所改善</b>。</p>\n'

        # 负面关键词
        if neg_words:
            html += '        <h3>本月负面高频词</h3>\n'
            html += '        <p>'
            for w, c in neg_words[:8]:
                html += f'<span class="tag neg">{esc(w)} ({c})</span> '
            html += '</p>\n'
    else:
        html += '        <p>暂无上月对比数据。</p>\n'

    # === 模块 3: 典型案例（代表性帖子）===
    html += f'\n        <h2 id="sec3">三、典型案例</h2>\n'
    html += '        <div class="spacer"></div>\n'

    # 最高赞帖子
    if top_liked:
        html += '        <h3>🔥 最高赞帖子</h3>\n'
        html += _build_note_card(top_liked, color)

    # 最高评论帖子
    if top_commented and top_commented.get("note_id") != top_liked.get("note_id"):
        html += '        <h3>💬 最热讨论帖子</h3>\n'
        html += _build_note_card(top_commented, color)

    # 本月互动 Top 5
    if top_notes:
        html += '        <h3>📊 本月互动量 Top 5</h3>\n'
        for i, note in enumerate(top_notes, 1):
            liked = note.get("liked_count", 0)
            comment = note.get("comment_count", 0)
            collected = note.get("collected_count", 0)
            title = note.get("title", "无标题")
            sent = note.get("sentiment", "neutral")
            sent_label = {"positive": "正面", "negative": "负面", "neutral": "中性"}.get(sent, "中性")
            sent_cls = {"positive": "pos", "negative": "neg", "neutral": "neu"}.get(sent, "neu")
            link = note.get("link") or f"https://www.xiaohongshu.com/explore/{note.get('note_id', '')}"

            html += f"""        <div class="note-card">
            <div class="title">{i}. {esc(title)}</div>
            <div class="meta">
                <span>👍 {format_number(liked)}</span>
                <span>💬 {format_number(comment)}</span>
                <span>⭐ {format_number(collected)}</span>
                <span class="tag {sent_cls}">{sent_label}</span>
            </div>
            <a href="{esc(link)}" target="_blank" rel="noopener">查看原帖 →</a>
        </div>\n"""

    # 负面典型案例
    if neg_notes:
        html += '        <h3>🚨 负面情绪代表帖</h3>\n'
        neg_top = get_top_notes(neg_notes, "liked_count", 3)
        for note in neg_top:
            html += _build_note_card(note, "#ef4444")

    # === 模块 4: 值得关注的问题 ===
    html += f'\n        <h2 id="sec4">四、值得关注的问题</h2>\n'
    html += '        <div class="spacer"></div>\n'

    if neg_clusters:
        html += '        <h3>负面热点聚类</h3>\n'
        for cluster in neg_clusters:
            html += f'        <div class="neg-cluster">{esc(cluster)}</div>\n'

    # AI/海外话题
    ai_topic = pdata.get("ai_topic", {})
    overseas = pdata.get("overseas_topic", {})
    if ai_topic.get("count", 0) > 0 or overseas.get("count", 0) > 0:
        html += '        <h3>热点话题追踪</h3>\n'
        html += '        <table><tr><th>话题</th><th>帖子数</th><th>占比</th></tr>\n'
        if ai_topic.get("count", 0) > 0:
            html += f'        <tr><td>🤖 AI相关</td><td>{ai_topic["count"]}</td><td>{ai_topic.get("rate", 0)}%</td></tr>\n'
        if overseas.get("count", 0) > 0:
            o_rate = round(overseas["count"] / total * 100, 1) if total > 0 else 0
            html += f'        <tr><td>🌏 海外/跨境</td><td>{overseas["count"]}</td><td>{o_rate}%</td></tr>\n'
        html += '        </table>\n'


    # === 模块 5: 横向对比一句话 ===
    html += f'\n        <h2 id="sec5">五、横向对比</h2>\n'
    html += '        <div class="spacer"></div>\n'

    if summary:
        html += f'        <div class="insight-box" style="background:#f0f9ff;border-color:#3b82f6;color:#1e40af">{esc(summary)}</div>\n'

    # 六平台对比表
    if cross:
        html += '        <table>\n'
        html += '        <tr><th>平台</th><th>声量</th><th>正面率</th><th>负面率</th><th>客诉率</th></tr>\n'
        for p in PLATFORMS:
            cp = cross.get(p, {})
            is_current = "★ " if p == platform else ""
            bold_s = ' style="font-weight:700;background:#f8f9fa"' if p == platform else ""
            html += f'        <tr{bold_s}><td>{is_current}{esc(p)}</td><td>{cp.get("total", 0)}</td>'
            html += f'<td>{cp.get("pos_rate", 0)}%</td><td>{cp.get("neg_rate", 0)}%</td><td>{cp.get("complaint_rate", 0)}%</td></tr>\n'
        html += '        </table>\n'

    # 页脚
    html += f"""
        <div class="spacer"></div>
        <div class="spacer"></div>
        <p class="center" style="color:#aaa;font-size:12px">— 报告结束 —</p>
        <p class="center" style="color:#bbb;font-size:11px">报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} | 数据源：小红书舆情爬取系统 | FinTech Insight</p>
    </div>
    <div class="footer-note">本报告由 FinTech Insight 自动生成，仅供内部研究参考</div>
</body>
</html>"""

    return html


def _build_note_card(note, color):
    """构建单个帖子卡片HTML"""
    title = note.get("title", "无标题")
    liked = note.get("liked_count", 0)
    comment = note.get("comment_count", 0)
    collected = note.get("collected_count", 0)
    author = note.get("author", "")
    time = note.get("time", "")
    link = note.get("link") or f"https://www.xiaohongshu.com/explore/{note.get('note_id', '')}"
    sent = note.get("sentiment", "neutral")
    sent_label = {"positive": "正面", "negative": "负面", "neutral": "中性"}.get(sent, "中性")
    sent_cls = {"positive": "pos", "negative": "neg", "neutral": "neu"}.get(sent, "neu")

    return f"""        <div class="note-card">
            <div class="title">{esc(title)}</div>
            <div class="meta">
                <span>👍 {format_number(liked)}</span>
                <span>💬 {format_number(comment)}</span>
                <span>⭐ {format_number(collected)}</span>
                <span>by {esc(author)}</span>
                <span>{esc(time)}</span>
                <span class="tag {sent_cls}">{sent_label}</span>
            </div>
            <a href="{esc(link)}" target="_blank" rel="noopener">查看原帖 →</a>
        </div>\n"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成标准化平台月报HTML")
    parser.add_argument("--month", default=None, help="月份，格式 YYYY-MM，默认取最新可用月份")
    parser.add_argument("--output-dir", default=None, help="输出目录，默认 netlify-deploy/reports 和 reports")
    parser.add_argument("--platform", default=None, help="指定单个平台，默认生成全部6个")
    args = parser.parse_args()

    output_dirs = []
    if args.output_dir:
        output_dirs = [args.output_dir]
    else:
        output_dirs = [
            os.path.join(BASE_DIR, "netlify-deploy", "reports"),
            os.path.join(BASE_DIR, "reports"),
        ]

    for d in output_dirs:
        os.makedirs(d, exist_ok=True)

    # 加载数据
    print("加载数据...")
    monthly_analysis, real_data_raw = load_data(None)

    # 确定月份
    month_key = args.month
    if not month_key:
        available = monthly_analysis.get("available_months", [])
        if available:
            month_key = available[-1]
        else:
            print("错误：无可用月份数据")
            sys.exit(1)
    print(f"目标月份: {month_key}")

    # 确定平台
    platforms = [args.platform] if args.platform else PLATFORMS

    # 生成报告
    count = 0
    for platform in platforms:
        slug = PLATFORM_SLUG.get(platform, platform.lower())
        y, m = month_key.split("-")
        filename = f"{slug}-{y}-{int(m):02d}.html"

        print(f"生成 {platform} 报告...")
        html = build_report_html(platform, month_key, monthly_analysis, real_data_raw)
        if not html:
            continue

        for d in output_dirs:
            filepath = os.path.join(d, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  -> {filepath}")
        count += 1

    print(f"\n完成！共生成 {count} 份标准化月报。")


if __name__ == "__main__":
    main()
