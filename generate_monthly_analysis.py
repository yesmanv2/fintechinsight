"""
月度舆情分析数据预计算脚本
从 real_data.json 中按 年/月/平台 维度预计算统计数据和洞察文字，
输出 monthly_analysis.json，供 build_netlify.py 嵌入前端。
"""
import json, os, re
from collections import Counter, defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 1. 读取数据 ──
data_file = os.path.join(BASE_DIR, 'real_data.json')
if not os.path.exists(data_file):
    raise FileNotFoundError("找不到 real_data.json")

with open(data_file, 'r', encoding='utf-8') as f:
    raw = json.load(f)

notes = raw.get('notes', [])
print(f"读取 {len(notes)} 条笔记")

# ── 2. 辅助函数 ──
def parse_int(v):
    """安全解析数字（字符串或int）"""
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        v = v.replace(',', '').replace('万', '0000').replace('+', '')
        try:
            return int(float(v))
        except:
            return 0
    return 0

def get_year_month(time_str):
    """从时间字符串提取 (year, year-month)"""
    if not time_str:
        return None, None
    # 格式: "2026-03-16 17:35" 或 "2026-03-16"
    parts = time_str.split('-')
    if len(parts) >= 2:
        year = parts[0].strip()
        month = f"{parts[0].strip()}-{parts[1].strip()}"
        return year, month
    return None, None

def extract_chinese_words(text, min_len=2):
    """提取中文词"""
    if not text:
        return []
    return re.findall(r'[\u4e00-\u9fa5]{' + str(min_len) + r',}', text)

STOP_WORDS = {'支付宝', '微信支付', '微信', '抖音支付', '抖音', '美团支付', '美团',
              '京东支付', '京东', '云闪付', '银联', '小红书', '支付', '平台', '真的',
              '可以', '现在', '怎么', '什么', '为什么', '如何', '大家', '一个',
              '不是', '已经', '还是', '觉得', '知道', '就是', '没有', '这个',
              '那个', '他们', '自己', '我们', '而且', '但是', '所以', '因为',
              '如果', '或者', '以及', '不过', '虽然', '只是', '还有', '只要'}

def get_top_words(texts, n=10):
    """从文本列表中提取高频词"""
    counter = Counter()
    for t in texts:
        words = extract_chinese_words(t)
        for w in words:
            if w not in STOP_WORDS and len(w) >= 2:
                counter[w] += 1
    return counter.most_common(n)

def safe_rate(count, total):
    """安全计算百分比"""
    if total == 0:
        return 0.0
    return round(count / total * 100, 1)

def generate_platform_insights(platform, stats, top_cats, neg_words, top_liked, top_commented, vs_last=None):
    """基于数据特征自动生成平台月度洞察（3-5条）"""
    insights = []
    total = stats['total']
    neg_rate = safe_rate(stats['negative'], total)
    pos_rate = safe_rate(stats['positive'], total)

    # 洞察1: 负面率变化
    if vs_last and vs_last.get('neg_rate_last') is not None:
        delta = neg_rate - vs_last['neg_rate_last']
        if abs(delta) >= 1.0:
            direction = '上升' if delta > 0 else '下降'
            insights.append(f"本月负面率{neg_rate}%，较上月{direction}{abs(delta):.1f}个百分点，{'需重点关注' if delta > 0 else '舆情环境有所改善'}")

    # 洞察2: 负面高频词聚类
    if neg_words:
        top3 = [w[0] for w in neg_words[:3]]
        insights.append(f"负面舆情集中在「{'」「'.join(top3)}」等话题，建议针对性回应")

    # 洞察3: 声量变化
    if vs_last and vs_last.get('total_last'):
        change = (total - vs_last['total_last']) / vs_last['total_last'] * 100
        if abs(change) >= 20:
            direction = '增长' if change > 0 else '下降'
            insights.append(f"本月声量{total}条，环比{direction}{abs(change):.0f}%，{'关注度显著提升' if change > 0 else '话题热度有所回落'}")

    # 洞察4: 分类特征
    if top_cats:
        top_cat = top_cats[0]
        insights.append(f"「{top_cat[0]}」类话题占比最高（{top_cat[1]}条），是用户讨论的核心焦点")

    # 洞察5: 正面率特征
    if pos_rate >= 15:
        insights.append(f"正面内容占比达{pos_rate}%，品牌口碑表现较好")
    elif pos_rate <= 5 and total >= 50:
        insights.append(f"正面内容仅占{pos_rate}%，建议加强正面舆论引导")

    # 洞察6: 高互动内容
    if top_liked:
        liked = parse_int(top_liked.get('liked_count', 0))
        if liked >= 1000:
            title_short = top_liked.get('title', '')[:20]
            insights.append(f"爆款笔记「{title_short}...」获{liked}赞，{top_liked.get('sentiment','中性')}基调，影响力显著")

    return insights[:5]  # 最多5条

def generate_cross_platform_summary(cross_data, time_label):
    """生成跨平台横向对比的总结点评"""
    if not cross_data:
        return "暂无数据"

    sorted_by_total = sorted(cross_data.items(), key=lambda x: x[1].get('total', 0), reverse=True)
    sorted_by_neg = sorted(cross_data.items(), key=lambda x: x[1].get('neg_rate', 0), reverse=True)

    top_volume = sorted_by_total[0] if sorted_by_total else None
    top_neg = sorted_by_neg[0] if sorted_by_neg else None

    parts = []
    if top_volume:
        parts.append(f"{time_label}，{top_volume[0]}以{top_volume[1]['total']}条声量领跑")
    if top_neg and top_neg[1].get('neg_rate', 0) >= 10:
        parts.append(f"{top_neg[0]}负面率最高达{top_neg[1]['neg_rate']}%，需重点关注")

    # 找正面率最高的
    sorted_by_pos = sorted(cross_data.items(), key=lambda x: x[1].get('pos_rate', 0), reverse=True)
    if sorted_by_pos and sorted_by_pos[0][1].get('pos_rate', 0) >= 10:
        parts.append(f"{sorted_by_pos[0][0]}正面率表现最优（{sorted_by_pos[0][1]['pos_rate']}%）")

    if not parts:
        return f"{time_label}各平台数据概览。"
    return '；'.join(parts) + '。'


# ── 3. 按时间和平台分组（过滤2022及之前的数据） ──
MIN_YEAR = '2023'  # 数据从2023年开始

# 结构: { "2026": { "2026-01": { "支付宝": [notes...], ... }, ... }, ... }
grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
year_grouped = defaultdict(lambda: defaultdict(list))
quarter_grouped = defaultdict(lambda: defaultdict(list))  # { "1Q26": { "支付宝": [notes...] } }

def get_quarter_key(year_str, month_str):
    """生成季度key，如 1Q26, 2Q25"""
    m = int(month_str.split('-')[1])
    q = (m - 1) // 3 + 1
    y_short = year_str[-2:]
    return f"{q}Q{y_short}"

for note in notes:
    year, ym = get_year_month(note.get('time', ''))
    if not year or not ym:
        continue
    if year < MIN_YEAR:
        continue  # 跳过2022及之前的数据
    platform = note.get('platform', '未知')
    grouped[year][ym][platform].append(note)
    year_grouped[year][platform].append(note)
    qk = get_quarter_key(year, ym)
    quarter_grouped[qk][platform].append(note)

# ── 4. 计算可用的年份、月份和季度 ──
available_years = sorted(y for y in grouped.keys() if y >= MIN_YEAR)
available_months = sorted(set(
    ym for year_data in grouped.values() for ym in year_data.keys()
    if ym[:4] >= MIN_YEAR
))
available_quarters = sorted(quarter_grouped.keys(), key=lambda q: (q[2:], q[0]), reverse=True)
print(f"可用年份: {available_years}")
print(f"可用月份: {available_months}")
print(f"可用季度: {available_quarters}")

ALL_PLATFORMS = ['支付宝', '微信支付', '抖音支付', '美团支付', '京东支付', '云闪付']

# ── 5. 计算月度数据 ──
monthly_data = {}

# 先计算所有月份的基础统计（用于环比）
monthly_stats_cache = {}  # { "2026-01": { "支付宝": {total, pos, neg, ...} } }

for ym in sorted(available_months):
    month_platforms = grouped.get(ym[:4], {}).get(ym, {})
    platform_stats = {}
    for p in ALL_PLATFORMS:
        p_notes = month_platforms.get(p, [])
        total = len(p_notes)
        pos = sum(1 for n in p_notes if n.get('sentiment') == 'positive')
        neg = sum(1 for n in p_notes if n.get('sentiment') == 'negative')
        neu = total - pos - neg
        platform_stats[p] = {
            'total': total, 'positive': pos, 'negative': neg, 'neutral': neu,
            'pos_rate': safe_rate(pos, total), 'neg_rate': safe_rate(neg, total)
        }
    monthly_stats_cache[ym] = platform_stats

for ym in sorted(available_months):
    year = ym[:4]
    month_platforms = grouped.get(year, {}).get(ym, {})

    # 上月key
    y, m = int(ym[:4]), int(ym[5:7])
    if m == 1:
        prev_ym = f"{y-1}-12"
    else:
        prev_ym = f"{y}-{m-1:02d}"

    # --- 首页横向对比数据（简洁版） ---
    cross_platform = {}
    for p in ALL_PLATFORMS:
        p_notes = month_platforms.get(p, [])
        total = len(p_notes)
        pos = sum(1 for n in p_notes if n.get('sentiment') == 'positive')
        neg = sum(1 for n in p_notes if n.get('sentiment') == 'negative')
        # 客诉占比
        complaint = sum(1 for n in p_notes if '客诉' in n.get('categories', []))
        cross_platform[p] = {
            'total': total,
            'pos_rate': safe_rate(pos, total),
            'neg_rate': safe_rate(neg, total),
            'complaint_rate': safe_rate(complaint, total),
        }

    # 月份中文
    month_label = f"{y}年{m}月"
    summary = generate_cross_platform_summary(cross_platform, month_label)

    # --- 各平台完整版数据 ---
    platforms_detail = {}
    for p in ALL_PLATFORMS:
        p_notes = month_platforms.get(p, [])
        if not p_notes:
            platforms_detail[p] = None
            continue

        total = len(p_notes)
        pos = sum(1 for n in p_notes if n.get('sentiment') == 'positive')
        neg = sum(1 for n in p_notes if n.get('sentiment') == 'negative')
        neu = total - pos - neg

        # 分类统计 TOP5
        cat_counter = Counter()
        for n in p_notes:
            for c in n.get('categories', []):
                cat_counter[c] += 1
        top_categories = cat_counter.most_common(5)

        # 负面高频词
        neg_titles = [n.get('title', '') + ' ' + n.get('desc', '')[:100]
                      for n in p_notes if n.get('sentiment') == 'negative']
        neg_words = get_top_words(neg_titles, 5)

        # 最热笔记
        sorted_by_likes = sorted(p_notes, key=lambda x: parse_int(x.get('liked_count', 0)), reverse=True)
        sorted_by_comments = sorted(p_notes, key=lambda x: parse_int(x.get('comment_count', 0)), reverse=True)

        top_liked = None
        if sorted_by_likes:
            n = sorted_by_likes[0]
            top_liked = {
                'title': n.get('title', ''),
                'liked_count': parse_int(n.get('liked_count', 0)),
                'comment_count': parse_int(n.get('comment_count', 0)),
                'collected_count': parse_int(n.get('collected_count', 0)),
                'author': n.get('author', ''),
                'time': n.get('time', ''),
                'link': n.get('link', ''),
                'sentiment': n.get('sentiment', ''),
                'note_id': n.get('note_id', ''),
            }

        top_commented = None
        if sorted_by_comments:
            n = sorted_by_comments[0]
            top_commented = {
                'title': n.get('title', ''),
                'liked_count': parse_int(n.get('liked_count', 0)),
                'comment_count': parse_int(n.get('comment_count', 0)),
                'collected_count': parse_int(n.get('collected_count', 0)),
                'author': n.get('author', ''),
                'time': n.get('time', ''),
                'link': n.get('link', ''),
                'sentiment': n.get('sentiment', ''),
                'note_id': n.get('note_id', ''),
            }

        # 独立作者
        authors = [n.get('author', '') for n in p_notes if n.get('author')]
        unique_authors = len(set(authors))
        author_counter = Counter(authors)
        top3_authors = author_counter.most_common(3)

        # AI话题
        ai_notes = [n for n in p_notes if 'AI' in n.get('categories', [])]
        ai_count = len(ai_notes)

        # 海外话题
        overseas_notes = [n for n in p_notes if '海外' in n.get('categories', [])]
        overseas_count = len(overseas_notes)

        # 负面事件聚类（TOP3负面热帖标题）
        neg_notes_sorted = sorted(
            [n for n in p_notes if n.get('sentiment') == 'negative'],
            key=lambda x: parse_int(x.get('liked_count', 0)) + parse_int(x.get('comment_count', 0)),
            reverse=True
        )
        neg_clusters = [n.get('title', '')[:30] for n in neg_notes_sorted[:3]]

        # 环比数据
        vs_last_month = {}
        prev_stats = monthly_stats_cache.get(prev_ym, {}).get(p)
        if prev_stats and prev_stats['total'] > 0:
            total_change = (total - prev_stats['total']) / prev_stats['total'] * 100
            vs_last_month = {
                'total_last': prev_stats['total'],
                'total_change': f"{'+' if total_change >= 0 else ''}{total_change:.0f}%",
                'neg_rate_last': prev_stats['neg_rate'],
                'neg_rate_change': f"{'+' if safe_rate(neg, total) - prev_stats['neg_rate'] >= 0 else ''}{safe_rate(neg, total) - prev_stats['neg_rate']:.1f}pp",
                'pos_rate_last': prev_stats['pos_rate'],
                'pos_rate_change': f"{'+' if safe_rate(pos, total) - prev_stats['pos_rate'] >= 0 else ''}{safe_rate(pos, total) - prev_stats['pos_rate']:.1f}pp",
            }

        # 生成洞察
        insights = generate_platform_insights(
            p,
            {'total': total, 'positive': pos, 'negative': neg, 'neutral': neu},
            top_categories, neg_words, top_liked, top_commented,
            vs_last={'neg_rate_last': prev_stats['neg_rate'] if prev_stats else None,
                     'total_last': prev_stats['total'] if prev_stats else None} if prev_stats else None
        )

        platforms_detail[p] = {
            'stats': {
                'total': total,
                'positive': pos,
                'negative': neg,
                'neutral': neu,
                'pos_rate': safe_rate(pos, total),
                'neg_rate': safe_rate(neg, total),
            },
            'vs_last_month': vs_last_month,
            'top_categories': top_categories,
            'insights': insights,
            'top_liked': top_liked,
            'top_commented': top_commented,
            'authors': {
                'unique': unique_authors,
                'top3': top3_authors,
            },
            'ai_topic': {
                'count': ai_count,
                'rate': safe_rate(ai_count, total),
            },
            'overseas_topic': {
                'count': overseas_count,
            },
            'neg_clusters': neg_clusters,
            'neg_words': neg_words,
        }

    monthly_data[ym] = {
        'cross_platform': cross_platform,
        'summary': summary,
        'platforms': platforms_detail,
    }

# ── 6. 计算年度数据（仅2023及之后） ──
yearly_data = {}
for year in available_years:
    year_platforms = year_grouped.get(year, {})
    cross_platform = {}
    for p in ALL_PLATFORMS:
        p_notes = year_platforms.get(p, [])
        total = len(p_notes)
        pos = sum(1 for n in p_notes if n.get('sentiment') == 'positive')
        neg = sum(1 for n in p_notes if n.get('sentiment') == 'negative')
        complaint = sum(1 for n in p_notes if '客诉' in n.get('categories', []))
        cross_platform[p] = {
            'total': total,
            'pos_rate': safe_rate(pos, total),
            'neg_rate': safe_rate(neg, total),
            'complaint_rate': safe_rate(complaint, total),
        }

    year_label = f"{year}年"
    summary = generate_cross_platform_summary(cross_platform, year_label)

    yearly_data[year] = {
        'cross_platform': cross_platform,
        'summary': summary,
    }

# ── 6b. 计算季度数据 ──
quarterly_data = {}
for qk in available_quarters:
    q_platforms = quarter_grouped.get(qk, {})
    cross_platform = {}
    for p in ALL_PLATFORMS:
        p_notes = q_platforms.get(p, [])
        total = len(p_notes)
        pos = sum(1 for n in p_notes if n.get('sentiment') == 'positive')
        neg = sum(1 for n in p_notes if n.get('sentiment') == 'negative')
        complaint = sum(1 for n in p_notes if '客诉' in n.get('categories', []))
        cross_platform[p] = {
            'total': total,
            'pos_rate': safe_rate(pos, total),
            'neg_rate': safe_rate(neg, total),
            'complaint_rate': safe_rate(complaint, total),
        }

    quarter_label = qk  # 如 "1Q26"
    summary = generate_cross_platform_summary(cross_platform, quarter_label)

    quarterly_data[qk] = {
        'cross_platform': cross_platform,
        'summary': summary,
    }

# ── 7. 输出 ──
result = {
    'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'available_years': available_years,
    'available_months': available_months,
    'available_quarters': available_quarters,
    'yearly': yearly_data,
    'quarterly': quarterly_data,
    'monthly': monthly_data,
}

out_file = os.path.join(BASE_DIR, 'monthly_analysis.json')
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

file_size = os.path.getsize(out_file)
print(f"\n✅ monthly_analysis.json 已生成!")
print(f"📏 文件大小: {file_size:,} bytes ({file_size/1024:.1f} KB)")
print(f"📅 年份: {available_years}")
print(f"📅 季度: {available_quarters}")
print(f"📅 月份: {available_months}")
for ym, md in monthly_data.items():
    total_notes = sum(v['total'] for v in md['cross_platform'].values())
    platforms_with_data = sum(1 for v in md['platforms'].values() if v is not None)
    print(f"   {ym}: {total_notes}条笔记, {platforms_with_data}个平台有数据")
