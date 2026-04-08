"""根据 search_keyword 重新分配 category"""
import json

PLATFORM_KEYWORDS = {
    "微信支付": {
        "支付": ["微信支付","刷掌","刷脸","摇一摇","摇优惠","红包","零钱","亲属卡","数字人民币","免密","红包封面"],
        "贷款": ["分付","微粒贷","微信支付分","信用卡分期","先享后付"],
        "理财": ["零钱通","理财通","微保","黄金红包","微信基金"],
        "AI": ["微信AI","腾讯混元","AI客服","AI风控","AI小程序","AI支付推荐"],
        "海外": ["WeChat Pay","WeChat Pay HK","跨境汇款","境外支付"],
        "组织架构": ["腾讯金融","财付通","微信支付团队"],
        "客诉": ["风控","封号","自动续费","客服难找","盗号"],
        "其他": ["AA付款","群收款","城市服务","小程序支付"],
    },
    "支付宝": {
        "支付": ["支付宝支付","碰一下","NFC","刷脸","扫码","消费券","神券节","数字人民币","乘车码","免密支付","医保码","付款码","红包","支付宝"],
        "贷款": ["花呗","借呗","芝麻信用","网商贷","备用金","信用购","芝麻分","先用后付"],
        "理财": ["余额宝","余利宝","蚂蚁财富","攒着","小荷包","黄金","好医保","帮你投","养老金","基金定投"],
        "AI": ["蚂蚁阿福","阿福","灵光","AI付","AI健康","AI问诊","AI理财","AI客服","AI风控","AI生活助手","支付宝AI"],
        "海外": ["Alipay+","泰国","日本","新加坡","韩国","欧洲","港澳","退税","汇率","支付宝海外","出境"],
        "组织架构": ["蚂蚁集团","蚂蚁金服","校招","离职","薪资","OceanBase","股权回购"],
        "客诉": ["账户冻结","乱扣费","自动续费","广告","闪退","盗刷","客服","隐私","支付宝投诉","支付宝封号"],
        "其他": ["蚂蚁森林","集五福","蚂蚁庄园","相互宝","支付宝小程序"],
    },
    "抖音支付": {
        "支付": ["抖音支付","抖音月付","DOU分期","红包","免密支付","抖音钱包"],
        "贷款": ["抖音月付","DOU分期","放心借","抖音借钱"],
        "理财": ["抖音理财"],
        "AI": ["豆包","抖音AI","AI客服"],
        "海外": ["TikTok","海外支付","TikTok Shop"],
        "组织架构": ["字节跳动","抖音金融","字节薪资"],
        "客诉": ["风控","自动扣费","盗刷","客服","投诉"],
        "其他": ["抖音","抖音团购","抖音电商","抖音打赏"],
    },
    "美团支付": {
        "支付": ["美团支付","美团月付","美团买单","红包","代金券","美团券"],
        "贷款": ["美团月付","美团生活费","美团借钱"],
        "理财": ["美团理财"],
        "AI": ["美团AI","AI配送","AI客服"],
        "海外": ["美团海外","KeeTa"],
        "组织架构": ["美团金融","美团薪资","美团裁员"],
        "客诉": ["杀熟","大数据杀熟","自动续费","客服","投诉","退款"],
        "其他": ["美团外卖","美团优选","美团闪购","美团买菜","美团打车","美团"],
    },
    "云闪付": {
        "支付": ["云闪付","银联","闪付","挥卡","银联二维码","手机闪付","银联支付"],
        "贷款": ["银联分期"],
        "理财": ["银联理财"],
        "AI": ["银联AI"],
        "海外": ["银联国际","UnionPay","云闪付海外","境外"],
        "组织架构": ["中国银联","银联薪资"],
        "客诉": ["云闪付投诉","客服"],
        "其他": ["云闪付优惠","云闪付活动","云闪付红包"],
    },
    "京东支付": {
        "支付": ["京东支付","京东白条","京东E卡","京东红包","京东券"],
        "贷款": ["京东白条","京东金条","京东金融借钱"],
        "理财": ["京东理财","京东金融理财","小金库"],
        "AI": ["京东AI","AIGC","AI客服"],
        "海外": ["京东海外","京东国际"],
        "组织架构": ["京东金融","京东科技","京东数科","京东薪资"],
        "客诉": ["京东投诉","客服","盗刷","自动续费","退款难"],
        "其他": ["京东","京东商城","京东物流","京东PLUS"],
    },
}

def classify_note(note):
    """根据 search_keyword 和 title 推断 category"""
    platform = note.get('platform', '')
    keyword = note.get('search_keyword', '') or ''
    title = note.get('title', '') or ''
    text = keyword + ' ' + title

    kw_map = PLATFORM_KEYWORDS.get(platform, {})
    
    # 先精确匹配 search_keyword
    for cat, keywords in kw_map.items():
        for kw in keywords:
            if kw.lower() in keyword.lower():
                return cat
    
    # 再用 title 模糊匹配
    for cat, keywords in kw_map.items():
        for kw in keywords:
            if kw.lower() in title.lower():
                return cat
    
    return '其他'


with open('real_data.json', 'r') as f:
    data = json.load(f)

notes = data['notes']
from collections import Counter

# 分类
cat_counter = Counter()
platform_cats = {}
for note in notes:
    cat = classify_note(note)
    note['category'] = cat
    cat_counter[cat] += 1
    p = note.get('platform', '')
    if p not in platform_cats:
        platform_cats[p] = Counter()
    platform_cats[p][cat] += 1

print('=== 分类结果 ===')
for cat, cnt in cat_counter.most_common():
    print(f'  {cat}: {cnt}')

print('\n=== 各平台分类 ===')
for p in sorted(platform_cats.keys()):
    print(f'\n  {p}:')
    for cat, cnt in platform_cats[p].most_common():
        print(f'    {cat}: {cnt}')

# 重新计算 platform_stats
platform_stats = {}
for note in notes:
    p = note.get('platform', '')
    if p not in platform_stats:
        platform_stats[p] = {
            'total': 0,
            'category_stats': {},
            'sentiment_stats': {'positive': 0, 'negative': 0, 'neutral': 0}
        }
    ps = platform_stats[p]
    ps['total'] += 1
    cat = note.get('category', '其他')
    ps['category_stats'][cat] = ps['category_stats'].get(cat, 0) + 1
    sent = note.get('sentiment', '中性')
    if sent in ['正面', 'positive']:
        ps['sentiment_stats']['positive'] += 1
    elif sent in ['负面', 'negative']:
        ps['sentiment_stats']['negative'] += 1
    else:
        ps['sentiment_stats']['neutral'] += 1

data['meta']['platform_stats'] = platform_stats
data['meta']['total_notes'] = len(notes)

with open('real_data.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 同步到 clean_data.json
with open('clean_data.json', 'r') as f:
    clean = json.load(f)
clean['notes'] = notes
clean['meta'] = data['meta']
with open('clean_data.json', 'w') as f:
    json.dump(clean, f, ensure_ascii=False, indent=2)

print(f'\n✅ 已更新分类并保存 (总 {len(notes)} 条)')
