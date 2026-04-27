#!/usr/bin/env python3
"""
微信支付客诉数据分析脚本
从 real_data.json 和 clean_data.json 中提取微信支付"客诉"分类的帖子
时间范围: 2025年1月1日至今
"""

import json
from datetime import datetime
from collections import Counter, defaultdict

def load_data():
    """加载所有数据源"""
    all_notes = []
    
    for filepath in ['real_data.json', 'clean_data.json', 'merged_data.json', 'new_crawl_data.json', 'new_crawl_data2.json']:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                notes = data.get('notes', [])
                all_notes.extend(notes)
                print(f"  {filepath}: {len(notes)} 条笔记")
        except Exception as e:
            print(f"  {filepath}: 加载失败 - {e}")
    
    return all_notes

def filter_wxpay_complaints(notes):
    """筛选微信支付客诉相关帖子，2025年1月1日以来"""
    cutoff = datetime(2025, 1, 1)
    results = []
    seen_ids = set()
    
    for note in notes:
        # 去重
        nid = note.get('note_id', '')
        if nid in seen_ids:
            continue
        seen_ids.add(nid)
        
        # 筛选平台
        platform = note.get('platform', '')
        if platform != '微信支付':
            continue
        
        # 筛选分类 - 客诉类
        category = note.get('category', '')
        categories = note.get('categories', [])
        is_complaint = (category == '客诉') or ('客诉' in categories)
        
        if not is_complaint:
            continue
        
        # 筛选时间
        time_str = note.get('time', '')
        if not time_str:
            continue
        try:
            note_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        except:
            try:
                note_time = datetime.strptime(time_str.split(' ')[0], '%Y-%m-%d')
            except:
                continue
        
        if note_time < cutoff:
            continue
        
        results.append({
            'note_id': nid,
            'title': note.get('title', ''),
            'desc': note.get('desc', ''),
            'time': time_str,
            'author': note.get('author', ''),
            'liked_count': note.get('liked_count', '0'),
            'comment_count': note.get('comment_count', '0'),
            'collected_count': note.get('collected_count', '0'),
            'sentiment': note.get('sentiment', ''),
            'link': note.get('link', ''),
            'keyword_tags': note.get('keyword_tags', []),
            'categories': categories,
            'category': category,
        })
    
    return results

def analyze_complaints(complaints):
    """对客诉数据进行话题分类和分析"""
    
    # 定义关键词到话题的映射
    topic_keywords = {
        '转账/收款问题': ['转账', '收款', '转不了', '收不到', '到账', '转钱', '付款码', '收款码', '二维码', '扫码'],
        '账户冻结/限制': ['冻结', '限制', '封号', '封禁', '被封', '限额', '风控', '解冻', '解封', '账户异常', '账号异常', '不能用', '被限'],
        '手续费/费率争议': ['手续费', '费率', '扣费', '收费', '提现费', '服务费', '佣金', '抽成', '费用'],
        '提现问题': ['提现', '到银行卡', '提不出', '提不了', '到账慢', '提现慢', '体现', '取钱'],
        '退款纠纷': ['退款', '不退', '退钱', '退不了', '退回', '没退', '退费'],
        '客服体验差': ['客服', '投诉', '举报', '人工', '申诉', '没人管', '没人回', '态度', '推诿', '踢皮球'],
        '商户问题': ['商户', '商家', '开通', '资质', '审核', '营业', '收单', '入驻', '签约'],
        '安全/盗刷': ['盗刷', '安全', '被盗', '诈骗', '欺诈', '未授权', '不是我', '被骗', '钓鱼'],
        '红包/优惠': ['红包', '优惠', '券', '活动', '补贴', '返现', '奖励', '减免', '满减'],
        '分期/借贷': ['分期', '借钱', '贷款', '利息', '还款', '逾期', '催收', '微粒贷', '借款', '分付'],
        '实名认证': ['实名', '认证', '身份证', '人脸', '验证', '绑卡'],
        '零钱/零钱通': ['零钱', '零钱通', '余额', '钱不见', '钱没了', '少了钱'],
        '支付失败/异常': ['支付失败', '付不了', '付款失败', '无法支付', '支付异常', '支付不了', '下单失败', '交易失败'],
        '绑卡问题': ['绑卡', '银行卡', '解绑', '换卡', '卡号', '储蓄卡', '信用卡'],
        '隐私/数据': ['隐私', '信息泄露', '数据', '个人信息', '偷偷'],
    }
    
    # 分类结果
    topic_notes = defaultdict(list)
    unclassified = []
    
    for c in complaints:
        text = (c['title'] + ' ' + c['desc']).lower()
        matched = False
        
        for topic, keywords in topic_keywords.items():
            for kw in keywords:
                if kw in text:
                    topic_notes[topic].append(c)
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            unclassified.append(c)
    
    return topic_notes, unclassified

def safe_int(val):
    """安全转换为整数"""
    try:
        return int(str(val).replace(',', ''))
    except:
        return 0

def main():
    print("=" * 80)
    print("微信支付客诉数据提取与分析")
    print("数据来源: 小红书舆情数据 | 时间范围: 2025年1月1日至今")
    print("=" * 80)
    
    # 加载数据
    print("\n📂 加载数据文件...")
    all_notes = load_data()
    print(f"\n共加载 {len(all_notes)} 条笔记")
    
    # 筛选
    print("\n🔍 筛选微信支付客诉数据...")
    complaints = filter_wxpay_complaints(all_notes)
    print(f"筛选出 {len(complaints)} 条微信支付客诉帖子")
    
    if not complaints:
        print("没有找到符合条件的数据！")
        # 打印一些调试信息
        print("\n调试信息 - 各平台各分类数量:")
        platform_cat = defaultdict(lambda: defaultdict(int))
        for note in all_notes:
            p = note.get('platform', '未知')
            c = note.get('category', '未知')
            platform_cat[p][c] += 1
        for p, cats in sorted(platform_cat.items()):
            print(f"  {p}:")
            for c, count in sorted(cats.items(), key=lambda x: -x[1]):
                print(f"    {c}: {count}")
        
        # 扩大搜索 - 也看看负面情绪的帖子
        print("\n\n扩大搜索 - 查看微信支付负面情绪帖子(含所有分类)...")
        cutoff = datetime(2025, 1, 1)
        seen = set()
        negative_notes = []
        complaint_keywords = ['投诉', '客诉', '吐槽', '垃圾', '坑', '骗', '坑人', '问题', '故障', 'bug', 
                              '失败', '不能', '冻结', '封', '扣', '费', '退款', '盗', '被', '怎么办',
                              '求助', '无语', '太差', '差评', '恶心', '离谱', '难用', '不好用']
        
        for note in all_notes:
            nid = note.get('note_id', '')
            if nid in seen:
                continue
            seen.add(nid)
            
            if note.get('platform', '') != '微信支付':
                continue
            
            time_str = note.get('time', '')
            if not time_str:
                continue
            try:
                note_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            except:
                continue
            if note_time < cutoff:
                continue
            
            # 负面情绪 或 标题/内容含客诉关键词
            text = (note.get('title', '') + ' ' + note.get('desc', '')).lower()
            is_negative = note.get('sentiment', '') == 'negative'
            has_complaint_keyword = any(kw in text for kw in complaint_keywords)
            
            if is_negative or has_complaint_keyword:
                negative_notes.append({
                    'note_id': nid,
                    'title': note.get('title', ''),
                    'desc': note.get('desc', ''),
                    'time': time_str,
                    'author': note.get('author', ''),
                    'liked_count': note.get('liked_count', '0'),
                    'comment_count': note.get('comment_count', '0'),
                    'collected_count': note.get('collected_count', '0'),
                    'sentiment': note.get('sentiment', ''),
                    'link': note.get('link', ''),
                    'keyword_tags': note.get('keyword_tags', []),
                    'categories': note.get('categories', []),
                    'category': note.get('category', ''),
                })
        
        print(f"找到 {len(negative_notes)} 条微信支付负面/客诉相关帖子")
        complaints = negative_notes
    
    if not complaints:
        print("仍然没有数据，退出。")
        return
    
    # 按时间排序
    complaints.sort(key=lambda x: x['time'], reverse=True)
    
    # 话题分类
    print("\n📊 进行话题分类...")
    topic_notes, unclassified = analyze_complaints(complaints)
    
    # ==================== 输出报告 ====================
    report_lines = []
    def pr(text=""):
        report_lines.append(text)
        print(text)
    
    pr("\n" + "=" * 80)
    pr("📋 微信支付客诉分析报告")
    pr(f"数据来源: 小红书舆情爬取 | 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pr(f"数据范围: 2025年1月1日 至 今")
    pr(f"总计客诉相关帖子: {len(complaints)} 条")
    pr("=" * 80)
    
    # 情绪分布
    sentiments = Counter(c['sentiment'] for c in complaints)
    pr(f"\n📈 情绪分布: 负面 {sentiments.get('negative', 0)} | 中性 {sentiments.get('neutral', 0)} | 正面 {sentiments.get('positive', 0)}")
    
    # 月份分布
    month_dist = Counter()
    for c in complaints:
        try:
            dt = datetime.strptime(c['time'], '%Y-%m-%d %H:%M')
            month_dist[dt.strftime('%Y-%m')] += 1
        except:
            pass
    pr("\n📅 月份分布:")
    for month in sorted(month_dist.keys()):
        bar = '█' * (month_dist[month] // 2) if month_dist[month] > 0 else '▏'
        pr(f"  {month}: {month_dist[month]:>4} 条 {bar}")
    
    # ==================== 话题分类详情 ====================
    pr("\n" + "=" * 80)
    pr("🔍 话题分类详情")
    pr("=" * 80)
    
    # 按数量排序
    sorted_topics = sorted(topic_notes.items(), key=lambda x: -len(x[1]))
    
    for rank, (topic, notes) in enumerate(sorted_topics, 1):
        total_likes = sum(safe_int(n['liked_count']) for n in notes)
        total_comments = sum(safe_int(n['comment_count']) for n in notes)
        avg_likes = total_likes // len(notes) if notes else 0
        
        pr(f"\n{'─' * 70}")
        pr(f"【TOP {rank}】{topic}  ({len(notes)} 条帖子 | 总点赞 {total_likes} | 平均点赞 {avg_likes})")
        pr(f"{'─' * 70}")
        
        # 展示该话题下的代表性帖子(按点赞排序取前5)
        sorted_notes = sorted(notes, key=lambda x: safe_int(x['liked_count']), reverse=True)
        for i, n in enumerate(sorted_notes[:8], 1):
            title = n['title'][:60] if n['title'] else '(无标题)'
            pr(f"  {i}. [{n['time']}] {title}")
            pr(f"     👍{n['liked_count']} 💬{n['comment_count']} ⭐{n['collected_count']} | {n['sentiment']}")
            if n['desc']:
                desc_preview = n['desc'][:120].replace('\n', ' ')
                pr(f"     📝 {desc_preview}...")
    
    # 未分类
    if unclassified:
        pr(f"\n{'─' * 70}")
        pr(f"【其他/未分类】({len(unclassified)} 条)")
        pr(f"{'─' * 70}")
        sorted_unc = sorted(unclassified, key=lambda x: safe_int(x['liked_count']), reverse=True)
        for i, n in enumerate(sorted_unc[:10], 1):
            title = n['title'][:60] if n['title'] else '(无标题)'
            pr(f"  {i}. [{n['time']}] {title}")
            pr(f"     👍{n['liked_count']} 💬{n['comment_count']} | {n['sentiment']}")
            if n['desc']:
                desc_preview = n['desc'][:100].replace('\n', ' ')
                pr(f"     📝 {desc_preview}...")
    
    # 热度排行(全局)
    pr(f"\n{'=' * 80}")
    pr("🔥 互动量TOP 20帖子（最受关注的客诉）")
    pr(f"{'=' * 80}")
    
    hot = sorted(complaints, key=lambda x: safe_int(x['liked_count']) + safe_int(x['comment_count']), reverse=True)
    for i, n in enumerate(hot[:20], 1):
        title = n['title'][:55] if n['title'] else '(无标题)'
        engagement = safe_int(n['liked_count']) + safe_int(n['comment_count'])
        pr(f"  {i:>2}. [{n['time']}] {title}")
        pr(f"      👍{n['liked_count']} 💬{n['comment_count']} ⭐{n['collected_count']} | 分类: {n['category']}")
        if n['desc']:
            desc_preview = n['desc'][:100].replace('\n', ' ')
            pr(f"      📝 {desc_preview}")
    
    # 输出所有标题，方便全局查看
    pr(f"\n{'=' * 80}")
    pr("📑 所有客诉帖子标题一览（按时间倒序）")
    pr(f"{'=' * 80}")
    for i, c in enumerate(complaints, 1):
        title = c['title'] if c['title'] else '(无标题)'
        pr(f"  {i:>3}. [{c['time']}] [{c['category']}] {title} | 👍{c['liked_count']}")
    
    # 保存报告
    with open('wxpay_complaint_report.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    print(f"\n✅ 报告已保存至 wxpay_complaint_report.txt")
    
    # 保存原始数据
    with open('wxpay_complaints_raw.json', 'w', encoding='utf-8') as f:
        json.dump(complaints, f, ensure_ascii=False, indent=2)
    print(f"✅ 原始数据已保存至 wxpay_complaints_raw.json")

if __name__ == '__main__':
    main()
