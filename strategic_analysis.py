#!/usr/bin/env python3
"""
微信支付舆情战略分析 - 深度研究版
基于已有小红书数据 + 外部研究，产出5大分析模块
"""

import json
import re
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import math

# ========== 配置 ==========
DATA_FILE = "real_data.json"
MONTHLY_FILE = "monthly_analysis.json"
OUTPUT_FILE = "strategic_analysis_report.md"

# 平台列表
PLATFORMS = ["微信支付", "支付宝", "抖音支付", "美团支付", "京东支付", "云闪付"]

# ========== 关键词库 ==========

# 用户流失/迁移信号关键词
CHURN_KEYWORDS = {
    "强流失信号": [
        "再也不用", "卸载", "注销", "换成", "转用", "弃用", "已经换",
        "不用了", "告别", "拜拜", "再见", "永远不用", "果断弃", "果断换",
        "删了", "不想用", "烂透了", "垃圾平台", "坑人", "骗人"
    ],
    "弱流失信号": [
        "考虑换", "想换", "打算换", "犹豫", "还不如用", "不如用",
        "越来越差", "越来越烂", "失望", "伤心", "寒心", "心凉",
        "什么时候能", "为什么不能", "太难用", "体验差"
    ]
}

# 竞品被夸关键词（用户认可的优势点）
PRAISE_KEYWORDS = {
    "体验好": ["好用", "方便", "简单", "顺畅", "丝滑", "秒到", "快", "流畅", "便捷", "省心"],
    "安全感": ["安全", "放心", "靠谱", "信赖", "保障", "有保障"],
    "服务好": ["客服好", "服务好", "态度好", "解决了", "处理快", "秒回", "给力"],
    "费率低": ["免手续费", "费率低", "便宜", "优惠", "划算", "省钱", "补贴", "红包"],
    "功能强": ["功能全", "功能多", "好功能", "新功能", "升级", "更新"],
    "海外好": ["海外", "出国", "境外", "国外", "汇率好", "外币", "跨境"]
}

# 情绪强度关键词
EMOTION_INTENSITY = {
    "极度愤怒": ["投诉", "12315", "举报", "报警", "维权", "起诉", "曝光", "315", "消协",
                "工信部", "央行投诉", "银保监", "黑猫投诉", "法院", "律师"],
    "强烈不满": ["恶心", "无语", "崩溃", "气死", "坑爹", "垃圾", "废物", "恶意",
                "流氓", "强盗", "霸王", "诈骗", "偷钱", "抢劫", "欺骗"],
    "明显不满": ["差评", "难用", "麻烦", "投诉", "吐槽", "不爽", "烦", "无奈",
                "不满", "不开心", "不高兴", "不舒服"],
    "轻微不满": ["不太好", "一般", "还行吧", "有点", "稍微", "略微", "希望改进"]
}

# 痛点话题关键词（细化版）
PAIN_TOPICS = {
    "自动续费/免密支付": ["自动续费", "免密支付", "自动扣费", "自动扣款", "续费", "免密",
                        "扣费", "偷偷扣", "不知情扣", "莫名扣", "被扣"],
    "风控误伤/账户冻结": ["冻结", "限制", "风控", "封号", "封了", "限额", "降额",
                        "不能用了", "被封", "异常", "风险", "解封", "申诉"],
    "客服体验差": ["客服", "人工客服", "找不到客服", "机器人", "智能客服", "客服态度",
                  "没人管", "踢皮球", "推诿", "不解决"],
    "提现/手续费": ["提现", "手续费", "费率", "收费", "服务费", "扣手续费",
                  "提现手续费", "零钱提现"],
    "转账/安全问题": ["转账", "被骗", "诈骗", "盗刷", "盗号", "资金安全",
                    "钱没了", "钱丢了", "追回"],
    "分付/借贷": ["分付", "微粒贷", "借贷", "利息", "催收", "还款", "逾期",
                "贷款", "额度", "强制开通"],
    "商户问题": ["商户", "商家", "收款码", "经营", "结算", "到账慢", "手续费高"],
    "支付失败/Bug": ["支付失败", "付不了", "扫码失败", "闪退", "bug", "出错",
                    "系统错误", "网络异常", "无法支付"],
    "实名认证": ["实名", "认证", "人脸", "身份证", "核验", "绑卡失败"],
    "隐私/数据": ["隐私", "个人信息", "数据", "监控", "偷看", "泄露"]
}

# 问题传导链路模式
ESCALATION_PATTERNS = [
    ("自动续费/免密支付", "客服体验差", "用户反馈自动续费后联系客服被踢皮球"),
    ("风控误伤/账户冻结", "客服体验差", "账户被冻结后客服无法有效解决"),
    ("自动续费/免密支付", "转账/安全问题", "自动续费引发用户对资金安全的恐慌"),
    ("风控误伤/账户冻结", "提现/手续费", "账户受限导致提现困难"),
    ("分付/借贷", "风控误伤/账户冻结", "借贷产品引发的风控连锁反应"),
    ("商户问题", "提现/手续费", "商户对手续费和结算周期的不满"),
    ("支付失败/Bug", "客服体验差", "技术问题后客服无法有效处理"),
]


def load_data():
    """加载数据"""
    print("📂 加载数据...")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    notes = raw.get("notes", [])
    meta = raw.get("meta", {})

    with open(MONTHLY_FILE, "r", encoding="utf-8") as f:
        monthly = json.load(f)

    print(f"   ✅ 加载 {len(notes)} 条笔记, {len(monthly.get('available_months', []))} 个月份数据")
    return notes, meta, monthly


def classify_note_text(title, desc):
    """合并标题和描述为分析文本"""
    text = f"{title or ''} {desc or ''}"
    return text.lower()


# ===================================================================
# 模块一：竞品攻防洞察
# ===================================================================
def analyze_competitive_intelligence(notes, meta, monthly):
    """竞品攻防洞察分析"""
    print("\n" + "="*60)
    print("📊 模块一：竞品攻防洞察")
    print("="*60)

    result = {}

    # 1. 各平台基础数据对比
    platform_data = {}
    for p in PLATFORMS:
        p_notes = [n for n in notes if n.get("platform") == p]
        total = len(p_notes)
        neg = sum(1 for n in p_notes if n.get("sentiment") == "negative")
        pos = sum(1 for n in p_notes if n.get("sentiment") == "positive")
        neu = total - neg - pos
        complaints = sum(1 for n in p_notes if n.get("category") == "客诉")
        platform_data[p] = {
            "total": total, "neg": neg, "pos": pos, "neu": neu,
            "neg_rate": round(neg/total*100, 1) if total else 0,
            "pos_rate": round(pos/total*100, 1) if total else 0,
            "complaint_rate": round(complaints/total*100, 1) if total else 0,
            "complaints": complaints,
            "notes": p_notes
        }

    result["platform_overview"] = platform_data

    # 2. 用户流失信号检测
    print("\n🔍 检测用户流失信号...")
    churn_signals = defaultdict(lambda: {"强流失": [], "弱流失": []})

    for note in notes:
        text = classify_note_text(note.get("title", ""), note.get("desc", ""))
        platform = note.get("platform", "")

        for level, keywords in CHURN_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    signal_level = "强流失" if level == "强流失信号" else "弱流失"
                    churn_signals[platform][signal_level].append({
                        "title": note.get("title", ""),
                        "keyword": kw,
                        "liked": int(note.get("liked_count", 0)),
                        "time": note.get("time", ""),
                        "link": note.get("link", "")
                    })
                    break

    result["churn_signals"] = {}
    for p in PLATFORMS:
        strong = churn_signals[p]["强流失"]
        weak = churn_signals[p]["弱流失"]
        # 去重（基于title）
        seen = set()
        strong_unique = []
        for s in strong:
            if s["title"] not in seen:
                seen.add(s["title"])
                strong_unique.append(s)
        weak_unique = []
        for w in weak:
            if w["title"] not in seen:
                seen.add(w["title"])
                weak_unique.append(w)

        result["churn_signals"][p] = {
            "strong_count": len(strong_unique),
            "weak_count": len(weak_unique),
            "total_signal_count": len(strong_unique) + len(weak_unique),
            "top_strong": sorted(strong_unique, key=lambda x: x["liked"], reverse=True)[:5],
            "top_weak": sorted(weak_unique, key=lambda x: x["liked"], reverse=True)[:5]
        }
        print(f"   {p}: 强流失信号 {len(strong_unique)} 条, 弱流失信号 {len(weak_unique)} 条")

    # 3. 竞品优势反推（各平台被夸什么）
    print("\n🏆 分析各平台用户好评维度...")
    praise_analysis = {}
    for p in PLATFORMS:
        p_notes = platform_data[p]["notes"]
        pos_notes = [n for n in p_notes if n.get("sentiment") == "positive"]
        dimension_counts = Counter()
        dimension_examples = defaultdict(list)

        for note in pos_notes:
            text = classify_note_text(note.get("title", ""), note.get("desc", ""))
            for dim, keywords in PRAISE_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        dimension_counts[dim] += 1
                        if len(dimension_examples[dim]) < 3:
                            dimension_examples[dim].append(note.get("title", ""))
                        break

        praise_analysis[p] = {
            "positive_count": len(pos_notes),
            "dimensions": dict(dimension_counts.most_common()),
            "examples": dict(dimension_examples)
        }
        top_dims = ", ".join([f"{d}({c})" for d, c in dimension_counts.most_common(3)])
        print(f"   {p}: 正面 {len(pos_notes)} 条, TOP优势维度: {top_dims}")

    result["praise_analysis"] = praise_analysis

    # 4. 攻防态势判定
    print("\n⚔️ 计算竞争攻防态势...")
    wxpay = platform_data["微信支付"]
    competitive_position = {}

    for p in PLATFORMS:
        if p == "微信支付":
            continue
        other = platform_data[p]

        # 计算威胁指数 = 对方正面率 - 微信正面率 + 微信负面率 - 对方负面率
        threat_index = (other["pos_rate"] - wxpay["pos_rate"]) + (wxpay["neg_rate"] - other["neg_rate"])

        # 流失风险 = 微信强流失信号 / 微信总笔记数
        wx_churn = result["churn_signals"]["微信支付"]["strong_count"]
        other_churn = result["churn_signals"][p]["strong_count"]

        # 对方被夸的 vs 微信被夸的 差异维度
        other_praise = set(praise_analysis[p]["dimensions"].keys())
        wx_praise = set(praise_analysis["微信支付"]["dimensions"].keys())
        gap_dimensions = other_praise - wx_praise  # 对方有微信没有
        shared_dimensions = other_praise & wx_praise  # 共有维度

        if threat_index > 5:
            stance = "🔴 高威胁"
        elif threat_index > 0:
            stance = "🟡 中等威胁"
        elif threat_index > -5:
            stance = "🟢 均势"
        else:
            stance = "💪 微信占优"

        competitive_position[p] = {
            "threat_index": round(threat_index, 1),
            "stance": stance,
            "gap_dimensions": list(gap_dimensions),
            "shared_dimensions": list(shared_dimensions),
            "other_pos_rate": other["pos_rate"],
            "wx_pos_rate": wxpay["pos_rate"],
            "other_neg_rate": other["neg_rate"],
            "wx_neg_rate": wxpay["neg_rate"]
        }
        print(f"   vs {p}: {stance} (威胁指数: {round(threat_index, 1)})")

    result["competitive_position"] = competitive_position

    return result


# ===================================================================
# 模块二：舆情预警雷达
# ===================================================================
def analyze_early_warning(notes, meta, monthly):
    """舆情预警雷达分析"""
    print("\n" + "="*60)
    print("🚨 模块二：舆情预警雷达")
    print("="*60)

    result = {}

    # 1. 按周统计各平台声量
    print("\n📈 计算周度声量趋势...")
    weekly_stats = defaultdict(lambda: defaultdict(lambda: {"total": 0, "neg": 0, "pos": 0}))

    for note in notes:
        time_str = note.get("time", "")
        platform = note.get("platform", "")
        sentiment = note.get("sentiment", "neutral")

        if not time_str or not platform:
            continue

        try:
            dt = datetime.strptime(time_str[:10], "%Y-%m-%d")
            # 计算ISO周
            year, week, _ = dt.isocalendar()
            week_key = f"{year}-W{week:02d}"
        except:
            continue

        weekly_stats[platform][week_key]["total"] += 1
        if sentiment == "negative":
            weekly_stats[platform][week_key]["neg"] += 1
        elif sentiment == "positive":
            weekly_stats[platform][week_key]["pos"] += 1

    # 2. 异常波动检测（Z-score方法）
    print("\n⚡ 异常波动检测...")
    anomalies = {}

    for platform in PLATFORMS:
        weeks = sorted(weekly_stats[platform].keys())
        if len(weeks) < 4:
            continue

        totals = [weekly_stats[platform][w]["total"] for w in weeks]
        negs = [weekly_stats[platform][w]["neg"] for w in weeks]

        # 计算最近4周的均值和标准差
        recent_4 = totals[-4:] if len(totals) >= 4 else totals
        mean_total = sum(recent_4) / len(recent_4)
        std_total = max((sum((x - mean_total) ** 2 for x in recent_4) / len(recent_4)) ** 0.5, 1)

        # 最新一周相对于之前的 Z-score
        latest_total = totals[-1] if totals else 0
        z_score_total = (latest_total - mean_total) / std_total

        # 负面率趋势
        neg_rates = [negs[i] / max(totals[i], 1) * 100 for i in range(len(weeks))]
        recent_neg_rates = neg_rates[-4:] if len(neg_rates) >= 4 else neg_rates

        # 负面率是否连续上升
        neg_rate_trend = "stable"
        if len(recent_neg_rates) >= 3:
            if all(recent_neg_rates[i] < recent_neg_rates[i + 1] for i in range(len(recent_neg_rates) - 1)):
                neg_rate_trend = "连续上升 ⚠️"
            elif all(recent_neg_rates[i] > recent_neg_rates[i + 1] for i in range(len(recent_neg_rates) - 1)):
                neg_rate_trend = "连续下降 ✅"

        alert_level = "正常"
        if z_score_total > 2:
            alert_level = "🔴 声量异常激增"
        elif z_score_total > 1.5:
            alert_level = "🟡 声量明显上升"
        elif neg_rate_trend == "连续上升 ⚠️":
            alert_level = "🟠 负面率持续恶化"

        anomalies[platform] = {
            "latest_week": weeks[-1] if weeks else "",
            "latest_volume": latest_total,
            "avg_volume": round(mean_total, 1),
            "z_score": round(z_score_total, 2),
            "latest_neg_rate": round(neg_rates[-1], 1) if neg_rates else 0,
            "neg_rate_trend": neg_rate_trend,
            "alert_level": alert_level,
            "weekly_volumes": {w: weekly_stats[platform][w] for w in weeks[-8:]}
        }
        print(f"   {platform}: {alert_level} | Z-score={round(z_score_total, 2)} | 负面率趋势: {neg_rate_trend}")

    result["anomalies"] = anomalies

    # 3. 话题增长率检测（月度环比）
    print("\n📊 话题增长率检测...")
    monthly_topics = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for note in notes:
        time_str = note.get("time", "")
        platform = note.get("platform", "")
        text = classify_note_text(note.get("title", ""), note.get("desc", ""))

        if not time_str:
            continue

        month_key = time_str[:7]  # "2026-03"

        for topic, keywords in PAIN_TOPICS.items():
            for kw in keywords:
                if kw in text:
                    monthly_topics[platform][month_key][topic] += 1
                    break

    # 计算环比增长
    topic_growth = {}
    for platform in PLATFORMS:
        months = sorted(monthly_topics[platform].keys())
        if len(months) < 2:
            continue

        latest_month = months[-1]
        prev_month = months[-2]

        growth_data = {}
        for topic in PAIN_TOPICS:
            curr = monthly_topics[platform][latest_month].get(topic, 0)
            prev = monthly_topics[platform][prev_month].get(topic, 0)
            if prev > 0:
                growth_pct = round((curr - prev) / prev * 100, 1)
            elif curr > 0:
                growth_pct = 9999  # 从0到有,标记为新增
            else:
                growth_pct = 0

            # 判断是否有意义的增长(上月至少有2条才算真正的环比)
            is_meaningful = prev >= 2

            growth_data[topic] = {
                "current": curr,
                "previous": prev,
                "growth_pct": growth_pct,
                "is_new_topic": prev == 0 and curr > 0,
                "is_meaningful": is_meaningful,
                "alert": "🆕" if (prev == 0 and curr >= 2) else ("🔴" if growth_pct > 100 and is_meaningful else ("🟡" if growth_pct > 50 and is_meaningful else ""))
            }

        # 排序找出增长最快的话题
        sorted_growth = sorted(growth_data.items(), key=lambda x: x[1]["growth_pct"], reverse=True)
        # 优先排真正有意义的增长（上月>=2），新增话题排后面
        meaningful_growth = [(t, d) for t, d in sorted_growth if d.get("is_meaningful") and d["growth_pct"] > 0]
        new_topics = [(t, d) for t, d in sorted_growth if d.get("is_new_topic") and d["current"] >= 2]
        sorted_growth_display = meaningful_growth + new_topics

        topic_growth[platform] = {
            "prev_month": prev_month,
            "latest_month": latest_month,
            "topics": growth_data,
            "fastest_growing": sorted_growth_display[:3]
        }

        parts = []
        for t, d in sorted_growth_display[:3]:
            if d.get("is_new_topic"):
                parts.append(f"{t}(新增{d['current']}条)")
            else:
                parts.append(f"{t}(+{d['growth_pct']}%)")
        top3_str = ", ".join(parts)
        if top3_str:
            print(f"   {platform} 增长最快: {top3_str}")

    result["topic_growth"] = topic_growth

    # 4. 新词/新话题检测
    print("\n🆕 新词检测...")
    # 按月份收集标题高频词
    import jieba
    jieba.setLogLevel(20)

    monthly_words = defaultdict(lambda: defaultdict(Counter))
    for note in notes:
        platform = note.get("platform", "")
        time_str = note.get("time", "")
        title = note.get("title", "")

        if not time_str or not title:
            continue

        month_key = time_str[:7]
        words = jieba.lcut(title)
        words = [w for w in words if len(w) >= 2 and not w.isdigit()
                 and w not in {"微信", "支付", "支付宝", "抖音", "美团", "京东", "云闪付",
                              "怎么", "什么", "为什么", "如何", "可以", "就是", "这个",
                              "一个", "不是", "没有", "还是", "已经", "真的", "竟然"}]
        monthly_words[platform][month_key].update(words)

    new_keywords = {}
    for platform in PLATFORMS:
        months = sorted(monthly_words[platform].keys())
        if len(months) < 2:
            continue

        latest_month = months[-1]
        latest_words = set(w for w, c in monthly_words[platform][latest_month].most_common(100))
        prev_words = set()
        for m in months[:-1]:
            prev_words.update(w for w, c in monthly_words[platform][m].most_common(200))

        # 最新月份有但之前没出现过的高频词
        truly_new = latest_words - prev_words
        # 过滤掉太短或无意义的
        truly_new = [w for w in truly_new if len(w) >= 2]

        new_keywords[platform] = {
            "new_words": truly_new[:15],
            "count": len(truly_new)
        }
        if truly_new:
            print(f"   {platform} 新词: {', '.join(list(truly_new)[:8])}")

    result["new_keywords"] = new_keywords

    return result


# ===================================================================
# 模块三：用户痛点演化图谱
# ===================================================================
def analyze_pain_point_evolution(notes, meta, monthly):
    """痛点演化图谱分析"""
    print("\n" + "="*60)
    print("🔬 模块三：用户痛点演化图谱")
    print("="*60)

    result = {}

    # 1. 痛点分类统计（微信支付专项）
    print("\n📋 微信支付痛点分类...")
    wx_notes = [n for n in notes if n.get("platform") == "微信支付"]
    neg_notes = [n for n in wx_notes if n.get("sentiment") == "negative"
                 or n.get("category") == "客诉"]

    pain_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0, "notes": []})

    for note in neg_notes:
        text = classify_note_text(note.get("title", ""), note.get("desc", ""))
        engagement = int(note.get("liked_count", 0)) + int(note.get("comment_count", 0))
        matched_topics = []

        for topic, keywords in PAIN_TOPICS.items():
            for kw in keywords:
                if kw in text:
                    matched_topics.append(topic)
                    break

        if not matched_topics:
            matched_topics = ["其他/未分类"]

        for topic in matched_topics:
            pain_stats[topic]["count"] += 1
            pain_stats[topic]["total_engagement"] += engagement
            if len(pain_stats[topic]["notes"]) < 10:
                pain_stats[topic]["notes"].append({
                    "title": note.get("title", ""),
                    "engagement": engagement,
                    "time": note.get("time", ""),
                    "sentiment": note.get("sentiment", "")
                })

    # 按数量排序，排除"其他/未分类"
    sorted_pains = sorted(
        [(t, d) for t, d in pain_stats.items() if t != "其他/未分类"],
        key=lambda x: x[1]["count"], reverse=True
    )
    result["pain_stats"] = {
        topic: {
            "count": data["count"],
            "avg_engagement": round(data["total_engagement"] / max(data["count"], 1), 1),
            "top_notes": sorted(data["notes"], key=lambda x: x["engagement"], reverse=True)[:5]
        }
        for topic, data in sorted_pains
    }
    result["unclassified_count"] = pain_stats.get("其他/未分类", {}).get("count", 0)

    for topic, data in sorted_pains[:8]:
        pct = round(data["count"] / len(neg_notes) * 100, 1) if neg_notes else 0
        avg_eng = round(data["total_engagement"] / max(data["count"], 1), 1)
        print(f"   {topic}: {data['count']}条 ({pct}%) | 平均互动: {avg_eng}")

    # 2. 话题共现分析（哪些问题总是一起出现）
    print("\n🔗 话题共现分析...")
    co_occurrence = Counter()
    note_topics_map = []

    for note in neg_notes:
        text = classify_note_text(note.get("title", ""), note.get("desc", ""))
        matched = []
        for topic, keywords in PAIN_TOPICS.items():
            for kw in keywords:
                if kw in text:
                    matched.append(topic)
                    break

        note_topics_map.append(matched)

        # 两两组合
        if len(matched) >= 2:
            for i in range(len(matched)):
                for j in range(i + 1, len(matched)):
                    pair = tuple(sorted([matched[i], matched[j]]))
                    co_occurrence[pair] += 1

    result["co_occurrence"] = {
        f"{p[0]} ↔ {p[1]}": count
        for p, count in co_occurrence.most_common(10)
    }

    print("   TOP 共现话题对:")
    for pair, count in co_occurrence.most_common(5):
        print(f"   「{pair[0]}」↔「{pair[1]}」: {count}次")

    # 3. 情绪强度分级
    print("\n😡 情绪强度分级...")
    emotion_stats = defaultdict(lambda: {"count": 0, "notes": []})

    for note in neg_notes:
        text = classify_note_text(note.get("title", ""), note.get("desc", ""))
        max_level = "轻微不满"

        for level in ["极度愤怒", "强烈不满", "明显不满", "轻微不满"]:
            found = False
            for kw in EMOTION_INTENSITY[level]:
                if kw in text:
                    max_level = level
                    found = True
                    break
            if found:
                break

        emotion_stats[max_level]["count"] += 1
        if len(emotion_stats[max_level]["notes"]) < 5:
            emotion_stats[max_level]["notes"].append(note.get("title", ""))

    result["emotion_intensity"] = {
        level: {
            "count": emotion_stats[level]["count"],
            "pct": round(emotion_stats[level]["count"] / max(len(neg_notes), 1) * 100, 1),
            "examples": emotion_stats[level]["notes"][:3]
        }
        for level in ["极度愤怒", "强烈不满", "明显不满", "轻微不满"]
    }

    for level in ["极度愤怒", "强烈不满", "明显不满", "轻微不满"]:
        data = result["emotion_intensity"][level]
        print(f"   {level}: {data['count']}条 ({data['pct']}%)")

    # 4. 问题传导链路验证
    print("\n🔀 验证问题传导链路...")
    escalation_evidence = []

    for pattern in ESCALATION_PATTERNS:
        source_topic, target_topic, description = pattern
        # 计算同时包含两个话题关键词的帖子数
        co_count = 0
        for note in neg_notes:
            text = classify_note_text(note.get("title", ""), note.get("desc", ""))
            has_source = any(kw in text for kw in PAIN_TOPICS.get(source_topic, []))
            has_target = any(kw in text for kw in PAIN_TOPICS.get(target_topic, []))
            if has_source and has_target:
                co_count += 1

        source_count = pain_stats[source_topic]["count"] if source_topic in pain_stats else 0
        escalation_rate = round(co_count / max(source_count, 1) * 100, 1)

        escalation_evidence.append({
            "source": source_topic,
            "target": target_topic,
            "description": description,
            "co_occurrence": co_count,
            "escalation_rate": escalation_rate,
            "severity": "🔴 高" if escalation_rate > 30 else ("🟡 中" if escalation_rate > 15 else "🟢 低")
        })
        print(f"   {source_topic} → {target_topic}: 共现 {co_count}条, 传导率 {escalation_rate}% {escalation_evidence[-1]['severity']}")

    result["escalation_evidence"] = escalation_evidence

    # 5. 痛点月度演化
    print("\n📅 痛点月度演化...")
    monthly_pain = defaultdict(lambda: defaultdict(int))
    for note in neg_notes:
        time_str = note.get("time", "")
        if not time_str:
            continue
        month_key = time_str[:7]
        text = classify_note_text(note.get("title", ""), note.get("desc", ""))
        for topic, keywords in PAIN_TOPICS.items():
            for kw in keywords:
                if kw in text:
                    monthly_pain[month_key][topic] += 1
                    break

    # 识别哪些痛点在增长
    months_sorted = sorted(monthly_pain.keys())
    pain_trends = {}
    if len(months_sorted) >= 2:
        latest = months_sorted[-1]
        prev = months_sorted[-2]
        for topic in PAIN_TOPICS:
            curr = monthly_pain[latest].get(topic, 0)
            prev_val = monthly_pain[prev].get(topic, 0)
            if prev_val > 0:
                change = round((curr - prev_val) / prev_val * 100, 1)
            elif curr > 0:
                change = 999
            else:
                change = 0
            pain_trends[topic] = {
                "current_month": curr,
                "prev_month": prev_val,
                "change_pct": change,
                "trend": "📈 增长" if change > 20 else ("📉 下降" if change < -20 else "➡️ 平稳")
            }

    result["pain_trends"] = pain_trends
    growing = [(t, d) for t, d in pain_trends.items() if d["change_pct"] > 20]
    if growing:
        print(f"   增长中的痛点:")
        for t, d in sorted(growing, key=lambda x: x[1]["change_pct"], reverse=True)[:5]:
            print(f"     {t}: {d['prev_month']}→{d['current_month']} (+{d['change_pct']}%)")

    return result


# ===================================================================
# 模块四：行动建议引擎
# ===================================================================
def generate_action_recommendations(competitive, warning, pain_evolution):
    """基于前三个模块的数据生成行动建议"""
    print("\n" + "="*60)
    print("🎯 模块四：行动建议引擎")
    print("="*60)

    recommendations = {
        "should_do": [],      # 应该做
        "should_not_do": [],  # 不应该做
        "urgent": [],         # 紧急
        "strategic": [],      # 战略级
    }

    # === 基于痛点数据生成建议 ===
    pain_stats = pain_evolution.get("pain_stats", {})
    sorted_pains = sorted(pain_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    # TOP1 痛点 → 紧急建议
    if sorted_pains:
        top_pain = sorted_pains[0]
        recommendations["urgent"].append({
            "title": f"【紧急】立即优化「{top_pain[0]}」体验",
            "reason": f"「{top_pain[0]}」以 {top_pain[1]['count']} 条投诉位居第一，平均互动量 {top_pain[1]['avg_engagement']}，影响面最广",
            "action": _generate_specific_action(top_pain[0]),
            "expected_impact": f"预计可减少 25-35% 的 {top_pain[0]} 相关投诉"
        })

    # 基于传导链路 → 根因治理建议
    escalations = pain_evolution.get("escalation_evidence", [])
    high_escalations = [e for e in escalations if "高" in e.get("severity", "")]
    for esc in high_escalations:
        recommendations["should_do"].append({
            "title": f"治理「{esc['source']}」→「{esc['target']}」传导链",
            "reason": f"{esc['description']}，传导率 {esc['escalation_rate']}%。解决源头问题可同时缓解下游投诉",
            "action": f"优先解决「{esc['source']}」的根因，而非仅在「{esc['target']}」层面打补丁",
            "expected_impact": f"打断传导链后预计可同时减少两类投诉 15-25%"
        })

    # 基于竞品分析 → 战略建议
    comp_positions = competitive.get("competitive_position", {})
    for rival, data in comp_positions.items():
        if "高威胁" in data.get("stance", ""):
            gap_dims = data.get("gap_dimensions", [])
            recommendations["strategic"].append({
                "title": f"应对「{rival}」的竞争威胁",
                "reason": f"{rival} 威胁指数 {data['threat_index']}（正面率 {data['other_pos_rate']}% vs 微信 {data['wx_pos_rate']}%）",
                "action": f"重点对标 {rival} 在{'、'.join(gap_dims) if gap_dims else '用户体验'}方面的优势",
                "expected_impact": f"缩小与 {rival} 的口碑差距"
            })

    # 基于情绪强度 → 风险预警建议
    emotion = pain_evolution.get("emotion_intensity", {})
    extreme_anger = emotion.get("极度愤怒", {})
    if extreme_anger.get("count", 0) > 0:
        recommendations["should_not_do"].append({
            "title": "【警告】不要忽视极端情绪用户",
            "reason": f"有 {extreme_anger['count']} 条帖子包含「投诉12315」「举报」「起诉」等极端维权信号（占负面的 {extreme_anger.get('pct', 0)}%）",
            "action": "建立极端情绪帖子的快速响应机制，48小时内主动联系用户解决",
            "expected_impact": "防止个案升级为公关危机"
        })

    # 基于流失信号 → 用户留存建议
    churn = competitive.get("churn_signals", {}).get("微信支付", {})
    if churn.get("strong_count", 0) > 10:
        recommendations["urgent"].append({
            "title": "【紧急】遏制用户流失趋势",
            "reason": f"检测到 {churn['strong_count']} 条强流失信号（'再也不用''注销''卸载'等），{churn.get('weak_count', 0)} 条弱流失信号",
            "action": "分析流失用户的共同痛点，针对性推出留存策略（如降低手续费、优化客服通道）",
            "expected_impact": "降低月度用户流失率"
        })

    # 基于话题增长 → 提前预判建议
    topic_growth = warning.get("topic_growth", {}).get("微信支付", {})
    fastest = topic_growth.get("fastest_growing", [])
    for topic, data in fastest[:2]:
        if data["growth_pct"] > 50:
            recommendations["should_do"].append({
                "title": f"提前应对「{topic}」话题爆发",
                "reason": f"该话题环比增长 {data['growth_pct']}%（{data['previous']}→{data['current']}条），趋势明显",
                "action": _generate_specific_action(topic),
                "expected_impact": f"在话题进一步发酵前控制负面声量"
            })

    # 基于新词检测 → 前瞻性建议
    new_kws = warning.get("new_keywords", {}).get("微信支付", {})
    if new_kws.get("new_words"):
        recommendations["should_do"].append({
            "title": "关注新出现的舆情话题",
            "reason": f"最新一个月出现 {new_kws['count']} 个新高频词：{', '.join(new_kws['new_words'][:8])}",
            "action": "评估这些新话题是否与产品变更或市场变化相关，判断是否需要专项回应",
            "expected_impact": "提前感知舆情方向变化"
        })

    # === 基于外部研究的战略建议 ===
    recommendations["strategic"].extend([
        {
            "title": "应对2026年支付新规的合规压力",
            "reason": "央行2026年推行统一风控、穿透式监管，所有支付渠道执行同一套规则。反洗钱监管精细化，FATF第五轮评估在即",
            "action": "1) 提前优化风控模型降低误伤率；2) 加强实名认证流程的用户体验；3) 准备合规宣传材料主动引导用户预期",
            "expected_impact": "避免因监管政策变化引发的大规模用户恐慌和投诉"
        },
        {
            "title": "对标抖音生服生态的支付闭环",
            "reason": "抖音生服2025年支付GMV超8500亿（+59%），2026年目标增速50%。内容+支付闭环对微信支付的线下场景构成直接威胁",
            "action": "强化微信视频号+小程序的支付闭环，在内容电商和本地生活场景中建立差异化优势",
            "expected_impact": "守住社交支付+小程序生态的核心壁垒"
        },
        {
            "title": "利用「免密支付骗局」热点做正面品牌传播",
            "reason": "近期大量新闻报道「关闭免密支付」骗局，微信官方已有提醒但声量不够。这是难得的正面传播机会",
            "action": "主动做科普传播（免密支付不收费、如何识别骗局），提升品牌安全感形象",
            "expected_impact": "将危机转化为品牌信任度提升"
        },
        {
            "title": "自动续费合规前置 — 行业自律先手",
            "reason": "黑猫投诉2025年自动续费投诉达69201件，三年连续增长。监管关注度持续升温。22万累计投诉是行业性问题",
            "action": "微信支付率先执行「续费前5日主动提醒+一键取消」，做行业合规标杆，反而获得用户好感",
            "expected_impact": "从行业最大痛点中脱颖而出，形成差异化口碑优势"
        }
    ])

    # 不应该做
    recommendations["should_not_do"].extend([
        {
            "title": "不要在客服流程未优化前推广新金融产品",
            "reason": "客服体验差已是核心痛点之一，新产品推广会带来更多客服压力，恶性循环",
            "action": "优先提升客服能力（增加人工客服入口、赋予客服更多解决权限），再推新产品",
            "expected_impact": "避免新产品变成新的投诉增长点"
        },
        {
            "title": "不要用复杂流程阻止用户取消自动续费",
            "reason": "取消流程越复杂 → 用户越愤怒 → 投诉升级到12315/黑猫 → 品牌受损。短期留存的收益远小于长期口碑损失",
            "action": "简化取消流程，用户体验>短期营收",
            "expected_impact": "降低极端情绪投诉占比，减少监管风险"
        }
    ])

    # 打印摘要
    for category, label in [("urgent", "🚨 紧急行动"), ("should_do", "🟢 应该做"),
                           ("should_not_do", "🔴 不应该做"), ("strategic", "🎯 战略级建议")]:
        items = recommendations[category]
        if items:
            print(f"\n{label}（{len(items)}条）:")
            for item in items:
                print(f"   • {item['title']}")

    return recommendations


def _generate_specific_action(topic):
    """根据痛点话题生成具体行动建议"""
    actions = {
        "自动续费/免密支付": "1) 在支付页面增加一键查看/关闭所有免密服务入口；2) 续费前5天发送明确提醒；3) 首次开通时强化提示",
        "风控误伤/账户冻结": "1) 优化风控模型降低误判率；2) 增加快速申诉通道；3) 冻结时给出明确原因和解冻时间预期",
        "客服体验差": "1) 增加人工客服入口的可见性；2) 赋予一线客服更多解决权限；3) 设立VIP升级通道处理复杂问题",
        "提现/手续费": "1) 透明化手续费计算方式；2) 对小额高频商户提供费率优惠；3) 提供手续费明细账单",
        "转账/安全问题": "1) 强化转账前的风险提示；2) 增加延迟到账选项的推广；3) 与公安反诈中心深化合作",
        "分付/借贷": "1) 杜绝强制开通；2) 利率展示更透明；3) 还款提醒更人性化",
        "商户问题": "1) 优化商户结算周期；2) 提供更清晰的费率说明；3) 增强商户端客服支持",
        "支付失败/Bug": "1) 加强支付通道稳定性监控；2) 失败后给出明确错误原因和解决方案；3) 建立自动重试机制",
        "实名认证": "1) 简化认证流程步骤；2) 提供更多认证方式选择；3) 认证失败时给出清晰指引",
        "隐私/数据": "1) 增加隐私设置的可见性和控制力；2) 定期发布隐私保护报告；3) 数据使用更透明"
    }
    return actions.get(topic, "深入调研该话题的用户诉求，制定针对性优化方案")


# ===================================================================
# 模块五：战略简报输出
# ===================================================================
def generate_strategic_report(competitive, warning, pain_evolution, recommendations):
    """生成最终的战略简报 Markdown"""
    print("\n" + "="*60)
    print("📝 模块五：生成战略简报")
    print("="*60)

    now = datetime.now()
    month_str = f"{now.year}年{now.month}月"

    lines = []
    lines.append(f"# 微信支付舆情战略简报 · {month_str}")
    lines.append(f"\n> 生成时间：{now.strftime('%Y-%m-%d %H:%M')} | 数据来源：小红书全平台舆情监控 | 分析范围：6大支付平台 7162条笔记")
    lines.append(f"\n> ⚠️ 本报告为内部研究文档，仅供团队参考\n")

    # ============ 一、核心发现 ============
    lines.append("---\n")
    lines.append("## 📌 一、本月核心发现\n")

    # 从痛点数据提取核心发现
    pain_stats = pain_evolution.get("pain_stats", {})
    sorted_pains = sorted(pain_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    if sorted_pains:
        lines.append(f"### 1. 微信支付第一大痛点：{sorted_pains[0][0]}")
        lines.append(f"- 投诉量 **{sorted_pains[0][1]['count']}** 条，平均互动量 {sorted_pains[0][1]['avg_engagement']}")
        if len(sorted_pains) > 1:
            lines.append(f"- 第二大痛点：{sorted_pains[1][0]}（{sorted_pains[1][1]['count']}条）")
        if len(sorted_pains) > 2:
            lines.append(f"- 第三大痛点：{sorted_pains[2][0]}（{sorted_pains[2][1]['count']}条）\n")

    # 流失信号
    churn = competitive.get("churn_signals", {}).get("微信支付", {})
    if churn:
        lines.append(f"### 2. 用户流失风险")
        lines.append(f"- 检测到 **{churn['strong_count']}** 条强流失信号（\"再也不用\"\"注销\"\"卸载\"等）")
        lines.append(f"- **{churn['weak_count']}** 条弱流失信号（\"越来越差\"\"想换\"\"失望\"等）")
        if churn.get("top_strong"):
            lines.append(f"- 最高互动流失贴：「{churn['top_strong'][0]['title'][:40]}」({churn['top_strong'][0]['liked']}赞)\n")

    # 竞品威胁
    comp = competitive.get("competitive_position", {})
    threats = [(k, v) for k, v in comp.items() if "威胁" in v.get("stance", "")]
    if threats:
        lines.append("### 3. 竞争态势警报")
        for rival, data in sorted(threats, key=lambda x: x[1]["threat_index"], reverse=True):
            lines.append(f"- **{rival}** {data['stance']}（威胁指数 {data['threat_index']}）"
                        f" — 正面率 {data['other_pos_rate']}% vs 微信 {data['wx_pos_rate']}%")
        lines.append("")

    # ============ 二、竞品攻防洞察 ============
    lines.append("---\n")
    lines.append("## ⚔️ 二、竞品攻防洞察\n")

    # 平台总览表
    lines.append("### 2.1 六大平台全景对比\n")
    lines.append("| 平台 | 笔记总数 | 正面率 | 负面率 | 客诉占比 | 态势 |")
    lines.append("|------|---------|--------|--------|---------|------|")

    overview = competitive.get("platform_overview", {})
    for p in PLATFORMS:
        d = overview.get(p, {})
        stance = "—"
        if p != "微信支付" and p in comp:
            stance = comp[p]["stance"]
        elif p == "微信支付":
            stance = "📍 主视角"
        lines.append(f"| {p} | {d.get('total', 0)} | {d.get('pos_rate', 0)}% | {d.get('neg_rate', 0)}% | {d.get('complaint_rate', 0)}% | {stance} |")
    lines.append("")

    # 各平台优势维度
    lines.append("### 2.2 各平台用户认可的优势维度\n")
    praise = competitive.get("praise_analysis", {})
    lines.append("| 平台 | 正面笔记 | TOP1 优势 | TOP2 优势 | TOP3 优势 |")
    lines.append("|------|---------|-----------|-----------|-----------|")
    for p in PLATFORMS:
        pd = praise.get(p, {})
        dims = list(pd.get("dimensions", {}).items())
        pos_count = pd.get("positive_count", 0)
        d1 = f"{dims[0][0]}({dims[0][1]})" if len(dims) > 0 else "—"
        d2 = f"{dims[1][0]}({dims[1][1]})" if len(dims) > 1 else "—"
        d3 = f"{dims[2][0]}({dims[2][1]})" if len(dims) > 2 else "—"
        lines.append(f"| {p} | {pos_count} | {d1} | {d2} | {d3} |")
    lines.append("")

    # 微信支付 vs 竞品差距
    lines.append("### 2.3 微信支付 vs 竞品的差距维度\n")
    lines.append("> 以下维度是竞品被用户称赞但微信支付尚未获得认可的方向\n")
    for rival, data in comp.items():
        gaps = data.get("gap_dimensions", [])
        if gaps:
            lines.append(f"- **vs {rival}**: 需追赶「{'」「'.join(gaps)}」")
    lines.append("")

    # 用户流失信号详情
    lines.append("### 2.4 用户流失信号对比\n")
    lines.append("| 平台 | 强流失信号 | 弱流失信号 | 总信号 |")
    lines.append("|------|----------|----------|--------|")
    churn_all = competitive.get("churn_signals", {})
    for p in PLATFORMS:
        cd = churn_all.get(p, {})
        lines.append(f"| {p} | {cd.get('strong_count', 0)} | {cd.get('weak_count', 0)} | {cd.get('total_signal_count', 0)} |")
    lines.append("")

    # 微信支付流失信号典型案例
    wx_churn = churn_all.get("微信支付", {})
    if wx_churn.get("top_strong"):
        lines.append("**微信支付 TOP 流失信号帖子：**\n")
        for item in wx_churn["top_strong"][:5]:
            lines.append(f"- 「{item['title'][:50]}」— {item['liked']}赞 | 关键词: {item['keyword']} | {item['time']}")
        lines.append("")

    # ============ 三、舆情预警雷达 ============
    lines.append("---\n")
    lines.append("## 🚨 三、舆情预警雷达\n")

    # 异常波动
    lines.append("### 3.1 平台声量异常检测\n")
    lines.append("| 平台 | 最新周声量 | 周均声量 | Z-Score | 负面率趋势 | 预警级别 |")
    lines.append("|------|----------|---------|---------|-----------|---------|")
    anomalies = warning.get("anomalies", {})
    for p in PLATFORMS:
        ad = anomalies.get(p, {})
        lines.append(f"| {p} | {ad.get('latest_volume', 0)} | {ad.get('avg_volume', 0)} | {ad.get('z_score', 0)} | {ad.get('neg_rate_trend', '—')} | {ad.get('alert_level', '—')} |")
    lines.append("")

    # 话题增长率
    lines.append("### 3.2 微信支付话题增长率（月环比）\n")
    tg = warning.get("topic_growth", {}).get("微信支付", {})
    if tg:
        lines.append(f"> 对比月份：{tg.get('prev_month', '')} → {tg.get('latest_month', '')}\n")
        lines.append("| 话题 | 上月 | 本月 | 环比变化 | 预警 |")
        lines.append("|------|------|------|---------|------|")
        topics_sorted = sorted(tg.get("topics", {}).items(), key=lambda x: x[1]["growth_pct"], reverse=True)
        for topic, td in topics_sorted:
            if td["current"] > 0 or td["previous"] > 0:
                if td.get("is_new_topic"):
                    growth_str = f"新增({td['current']}条)"
                elif td["growth_pct"] > 0:
                    growth_str = f"+{td['growth_pct']}%"
                else:
                    growth_str = f"{td['growth_pct']}%"
                lines.append(f"| {topic} | {td['previous']} | {td['current']} | {growth_str} | {td['alert']} |")
        lines.append("")

    # 新词检测
    lines.append("### 3.3 新出现的舆情关键词\n")
    new_kws = warning.get("new_keywords", {})
    for p in PLATFORMS:
        nk = new_kws.get(p, {})
        words = nk.get("new_words", [])
        if words:
            lines.append(f"- **{p}**: {', '.join(words[:10])}")
    lines.append("")

    # ============ 四、痛点演化图谱 ============
    lines.append("---\n")
    lines.append("## 🔬 四、痛点演化图谱（微信支付专项）\n")

    # 痛点分布
    lines.append("### 4.1 痛点分类分布\n")
    lines.append("| 排名 | 痛点话题 | 投诉数 | 平均互动量 | 趋势 |")
    lines.append("|------|---------|--------|-----------|------|")
    pain_trends = pain_evolution.get("pain_trends", {})
    for i, (topic, data) in enumerate(sorted_pains[:10], 1):
        trend = pain_trends.get(topic, {}).get("trend", "—")
        lines.append(f"| {i} | {topic} | {data['count']} | {data['avg_engagement']} | {trend} |")
    lines.append("")

    # 情绪强度分布
    lines.append("### 4.2 情绪强度分布\n")
    emotion = pain_evolution.get("emotion_intensity", {})
    lines.append("| 情绪等级 | 数量 | 占比 | 典型表达 |")
    lines.append("|---------|------|------|---------|")
    for level in ["极度愤怒", "强烈不满", "明显不满", "轻微不满"]:
        ed = emotion.get(level, {})
        examples = "、".join(ed.get("examples", [])[:2])
        if len(examples) > 40:
            examples = examples[:40] + "…"
        lines.append(f"| {level} | {ed.get('count', 0)} | {ed.get('pct', 0)}% | {examples} |")
    lines.append("")

    # 话题共现网络
    lines.append("### 4.3 话题共现网络（同一帖子涉及多个问题）\n")
    lines.append("> 共现频率越高，说明两个问题越可能是同一系统性问题的不同表现\n")
    co_occ = pain_evolution.get("co_occurrence", {})
    lines.append("| 话题对 | 共现次数 | 解读 |")
    lines.append("|--------|---------|------|")
    for pair, count in list(co_occ.items())[:8]:
        interpretation = _interpret_co_occurrence(pair)
        lines.append(f"| {pair} | {count} | {interpretation} |")
    lines.append("")

    # 传导链路
    lines.append("### 4.4 问题传导链路\n")
    lines.append("> 问题A引发问题B的传导路径，根因治理比表面修补更有效\n")
    lines.append("| 源头问题 | → | 下游问题 | 传导率 | 严重度 | 解读 |")
    lines.append("|---------|---|---------|--------|--------|------|")
    for esc in pain_evolution.get("escalation_evidence", []):
        lines.append(f"| {esc['source']} | → | {esc['target']} | {esc['escalation_rate']}% | {esc['severity']} | {esc['description']} |")
    lines.append("")

    # ============ 五、行动建议 ============
    lines.append("---\n")
    lines.append("## 🎯 五、行动建议\n")

    # 紧急行动
    lines.append("### 🚨 紧急行动（建议1周内推进）\n")
    for item in recommendations.get("urgent", []):
        lines.append(f"#### {item['title']}")
        lines.append(f"- **依据**：{item['reason']}")
        lines.append(f"- **建议**：{item['action']}")
        lines.append(f"- **预期效果**：{item['expected_impact']}\n")

    # 应该做
    lines.append("### 🟢 应该做（建议1个月内推进）\n")
    for item in recommendations.get("should_do", []):
        lines.append(f"#### {item['title']}")
        lines.append(f"- **依据**：{item['reason']}")
        lines.append(f"- **建议**：{item['action']}")
        lines.append(f"- **预期效果**：{item['expected_impact']}\n")

    # 不应该做
    lines.append("### 🔴 不应该做（风险警示）\n")
    for item in recommendations.get("should_not_do", []):
        lines.append(f"#### {item['title']}")
        lines.append(f"- **依据**：{item['reason']}")
        lines.append(f"- **建议**：{item['action']}")
        lines.append(f"- **预期效果**：{item['expected_impact']}\n")

    # 战略级建议
    lines.append("### 🎯 战略级建议（中长期布局）\n")
    for item in recommendations.get("strategic", []):
        lines.append(f"#### {item['title']}")
        lines.append(f"- **依据**：{item['reason']}")
        lines.append(f"- **建议**：{item['action']}")
        lines.append(f"- **预期效果**：{item['expected_impact']}\n")

    # ============ 六、外部环境研判 ============
    lines.append("---\n")
    lines.append("## 🌐 六、外部环境研判\n")
    lines.append("### 6.1 2026年支付行业监管趋势\n")
    lines.append("""
| 政策方向 | 具体内容 | 对微信支付的影响 |
|---------|---------|----------------|
| 统一风控模型 | 央行要求所有支付机构接入统一风控系统，实时报送交易数据 | 风控误伤问题将成为全行业话题，微信需提前优化降低用户感知 |
| 穿透式监管 | 从严实施支付机构穿透式监管，打击涉诈涉赌资金链 | 合规成本上升，但也是体现大平台安全优势的机会 |
| 反洗钱升级 | FATF第五轮评估在即，反洗钱措施"颗粒度"要求提高 | 实名认证、大额交易核验流程可能更复杂，需做好体验兜底 |
| 现金支付保障 | 《人民币现金收付规定》2026.2.1起施行，线下必须支持现金 | 移动支付扩张空间可能受限，需在效率和合规之间找平衡 |
""")

    lines.append("### 6.2 竞争格局变化\n")
    lines.append("""
| 竞品 | 2026年关键动态 | 对微信支付的启示 |
|------|--------------|----------------|
| 支付宝 | 海外支付持续扩张，与全球银行及支付机构合作加深；跨境支付成功率和服务口碑领先 | 微信支付在海外场景存在明显短板，需加速境外支付体验对标 |
| 抖音支付 | 生服支付GMV超8500亿（+59%），2026目标+50%；商家扶持政策升级，扩大免佣 | 内容+支付闭环对微信线下场景构成直接威胁，需强化视频号+小程序支付生态 |
| 美团支付 | 深耕本地生活，在餐饮、外卖场景建立强支付粘性 | 垂直场景的支付心智难以撼动，微信需在更多场景建立支付习惯 |
| 云闪付 | 与各大银行合作深化，用户数持续增长 | 银行系支付在合规和安全上有天然优势，微信需强化安全感建设 |
| 京东支付 | 依托京东电商生态，在购物场景有深度绑定 | 场景绑定是护城河，微信需巩固自身社交支付的不可替代性 |
""")

    lines.append("### 6.3 自动续费行业性问题（重要背景）\n")
    lines.append("""
> 📊 **黑猫投诉数据**：2025年自动续费投诉达 **69,201件**，近三年连续增长，累计超 **22万条**。
>
> 这是全行业性问题，但微信支付作为最大支付平台首当其冲。
>
> **核心矛盾**：平台/商家的续费留存诉求 vs 用户的知情权和选择权
>
> **机会窗口**：如果微信支付率先落实"续费前5日提醒+一键取消"，可以把行业痛点变成品牌优势。
> 工信部已有明确规定，但执行层面仍有大量灰色空间，主动合规是差异化竞争的战略选择。
""")

    # ============ 七、总结 ============
    lines.append("---\n")
    lines.append("## 📊 七、一句话总结\n")

    # 动态生成总结
    top_pain_name = sorted_pains[0][0] if sorted_pains else "未知"
    top_threat = max(comp.items(), key=lambda x: x[1]["threat_index"])[0] if comp else "未知"
    strong_churn = churn.get("strong_count", 0) if churn else 0

    lines.append(f"> **微信支付当前处于「防守+优化」态势**。")
    lines.append(f"> 首要矛盾是「{top_pain_name}」引发的用户信任危机（{strong_churn}条强流失信号），")
    lines.append(f"> 最大外部威胁来自「{top_threat}」的口碑追赶。")
    lines.append(f"> 建议采取「内修体验、外树安全」策略 —— 对内优先解决自动续费和客服痛点，")
    lines.append(f"> 对外利用免密支付骗局科普+合规先手建立品牌安全感。\n")

    lines.append("---\n")
    lines.append(f"*报告由舆情分析系统自动生成 · {now.strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def _interpret_co_occurrence(pair_str):
    """解读话题共现的含义"""
    interpretations = {
        "客服体验差": "用户在遇到问题后联系客服不满意，形成二次投诉",
        "自动续费/免密支付": "自动续费是投诉的最常见触发点",
        "风控误伤/账户冻结": "风控问题容易引发连锁投诉",
        "提现/手续费": "费用问题与其他问题叠加会加剧不满",
        "转账/安全问题": "安全问题是用户最敏感的方向",
        "分付/借贷": "金融产品问题容易与其他问题交叉",
    }
    for key, interp in interpretations.items():
        if key in pair_str:
            return interp
    return "多问题交叉显示系统性体验缺陷"


# ===================================================================
# 主流程
# ===================================================================
def main():
    print("🚀 微信支付舆情战略分析 - 深度研究版")
    print("=" * 60)

    # 加载数据
    notes, meta, monthly = load_data()

    # 模块一：竞品攻防洞察
    competitive = analyze_competitive_intelligence(notes, meta, monthly)

    # 模块二：舆情预警雷达
    warning = analyze_early_warning(notes, meta, monthly)

    # 模块三：痛点演化图谱
    pain_evolution = analyze_pain_point_evolution(notes, meta, monthly)

    # 模块四：行动建议引擎
    recommendations = generate_action_recommendations(competitive, warning, pain_evolution)

    # 模块五：生成战略简报
    report = generate_strategic_report(competitive, warning, pain_evolution, recommendations)

    # 保存报告
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n{'='*60}")
    print(f"✅ 战略简报已生成: {OUTPUT_FILE}")
    print(f"📏 报告长度: {len(report)} 字符")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
