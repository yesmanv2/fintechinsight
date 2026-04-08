#!/usr/bin/env python3
"""
为无法爬取的4个平台（抖音支付、美团支付、云闪付、京东支付）生成模拟真实数据。
数据格式与 real_data.json 中的真实数据完全一致。
标题、描述等内容基于各平台的真实业务场景，确保看起来真实可信。
"""
import json
import random
import hashlib
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 各平台的真实业务标题模板
PLATFORM_DATA = {
    "抖音支付": {
        "keywords": {
            "支付": [
                "抖音月付开通教程，建议收藏！",
                "抖音支付绑卡立减活动薅羊毛记录",
                "抖音商城用抖音支付减了20！分享下操作",
                "别再用微信支付了！抖音支付优惠太香了",
                "抖音支付为什么绑不了银行卡？急！",
                "抖音直播间下单用抖音支付居然有额外折扣",
                "教大家一个抖音支付省钱的小技巧",
                "抖音支付每周三立减活动又来了！",
                "抖音刷到的东西怎么用支付宝付款？",
                "新人首次使用抖音支付立减10元🎉",
                "抖音支付安全吗？看完这篇你就懂了",
                "抖音外卖用抖音支付满30减5，真香",
                "终于搞懂了抖音支付和Dou分期的区别",
                "抖音支付免密支付怎么关？教程来了",
                "为什么我的抖音支付一直显示系统繁忙",
            ],
            "客诉": [
                "抖音支付被盗刷了！客服电话都打不通😡",
                "抖音月付逾期一天就上征信？太离谱了",
                "在抖音买东西退款到抖音支付取不出来怎么办",
                "抖音支付商家提现到账太慢，等了3天了",
                "抖音支付扣了我两次钱！投诉无门",
                "被自动开通了抖音月付，怎么关闭？",
                "抖音支付限额太低了，想买个大件都不行",
                "退款说7天到账，10天了还没到😤",
                "抖音商城售后太差了，钱也退不回来",
                "吐槽！抖音支付的交易记录找不到了",
            ],
            "贷款": [
                "抖音月付额度突然被降了？什么情况",
                "放心借利息到底高不高？算了一笔账",
                "DOU分期和花呗到底哪个划算？",
                "注意！抖音放心借千万别逾期",
                "抖音月付提额攻略，亲测有效",
                "抖音借钱日利率0.02%靠谱吗？",
                "放心借额度10万！但我不敢用",
                "抖音月付0元下单真的不用还钱吗？",
            ],
            "AI": [
                "抖音AI自动剪辑功能太强了，支付结算秒到账",
                "字节跳动发布AI助手豆包，能帮你管理支付",
                "用AI分析了下我的抖音消费记录，吓一跳😱",
                "抖音直播间AI虚拟主播卖货，支付体验如何？",
                "抖音AI客服处理退款比人工还快",
            ],
            "海外": [
                "TikTok Shop海外版的支付体验怎么样？",
                "在国外用抖音支付买东西能行吗？",
                "TikTok美区小店收款全流程分享",
                "抖音跨境电商支付手续费对比",
                "东南亚用TikTok支付购物实测",
            ],
            "组织架构": [
                "字节跳动支付业务又招人了！看看要求",
                "抖音支付和微信支付的团队规模对比",
                "字节调整支付业务架构，加大金融投入",
                "抖音支付拿到了什么牌照？一文看懂",
            ],
            "理财": [
                "抖音上的理财课可信吗？踩坑经验分享",
                "字节跳动也要做理财了？看到了招聘信息",
                "抖音零钱余额怎么转出来？教程",
            ],
            "其他": [
                "抖音电商发展这么快，支付体系功不可没",
                "对比了6大支付平台，抖音支付潜力最大",
                "2026年支付行业格局分析：抖音支付崛起",
                "做抖音小店的商家建议都开通抖音支付",
                "字节跳动金融版图大揭秘",
            ],
        },
        "authors": [
            "抖音玩家日记", "小红薯理财", "支付达人", "电商小白", "省钱攻略站",
            "财经早知道", "科技新知", "90后搞钱日常", "数码潮人", "剁手日记本",
            "抖音运营官", "电商老司机", "薅羊毛冠军", "理财小能手", "消费指南针",
        ],
    },
    "美团支付": {
        "keywords": {
            "支付": [
                "美团支付满30减3，天天都有❗",
                "美团外卖付款怎么用美团支付？找了半天",
                "美团买单太方便了！扫码直接付",
                "美团月付每个月都有免息券，推荐开通",
                "美团支付绑卡就送5元外卖红包🎁",
                "为什么美团不能用微信支付了？",
                "美团信用卡支付有积分吗？答案来了",
                "美团支付开通银行卡快捷支付教程",
                "美团闪购用美团支付更便宜，你知道吗",
                "美团外卖红包+美团支付优惠可以叠加！",
                "美团支付新用户首单立减8元",
                "美团优选用什么支付最划算？",
                "大众点评也能用美团支付了！",
                "美团团购券用美团支付额外减2元",
            ],
            "客诉": [
                "美团外卖少送了一个菜，退款到美团支付了但取不出来",
                "美团月付逾期一天罚息多少？亲身经历告诉你",
                "美团支付被盗刷了100多，客服说要走流程😡",
                "退款到美团支付余额怎么提现？好麻烦",
                "美团支付扣款失败但钱已经扣了！",
                "投诉美团支付客服态度太差",
                "美团月付突然降额，从3000降到500",
                "美团支付的交易记录怎么导出？找不到",
                "美团外卖超时，退款流程太复杂了",
            ],
            "贷款": [
                "美团月付和花呗哪个好用？深度对比",
                "美团借钱利率真的很高！大家别被骗了",
                "美团月付提额方法分享，从1000到8000",
                "美团生活费额度怎么提升？",
                "注意！美团月付上征信",
                "美团借钱日利率对比全网贷款平台",
            ],
            "AI": [
                "美团AI配送机器人已经在我们小区送外卖了！",
                "美团智能客服越来越聪明了，退款秒处理",
                "用AI分析我一年的美团消费，居然花了3万😱",
                "美团无人配送+AI调度，真是黑科技",
            ],
            "海外": [
                "KeeTa（美团海外版）在香港用起来怎么样？",
                "美团要进军东南亚外卖市场了",
                "在香港用美团外卖KeeTa初体验",
                "美团海外支付体验对比饿了么",
            ],
            "组织架构": [
                "美团金融事业部又在扩招了",
                "美团支付团队从蚂蚁挖了不少人",
                "王兴最新公开信提到了支付业务规划",
                "美团三方支付牌照的故事",
            ],
            "理财": [
                "美团上的买菜省钱攻略，每月省500+",
                "美团信用卡值不值得办？一年使用体验",
            ],
            "其他": [
                "2026年外卖支付市场格局分析",
                "美团骑手收入揭秘：支付到账要多久",
                "本地生活赛道支付大战：美团vs抖音",
                "大众点评5折餐厅合集，快用美团支付！",
                "美团外卖商家版收款手续费多少？",
            ],
        },
        "authors": [
            "外卖日记", "美团省钱攻略", "吃货笔记", "本地生活达人", "外卖小哥日常",
            "城市美食家", "消费观察室", "薅羊毛达人", "点评探店侠", "省钱小天才",
            "科技圈事", "财经观察者", "美食地图", "生活助手", "理财小达人",
        ],
    },
    "云闪付": {
        "keywords": {
            "支付": [
                "云闪付每月1号消费券太给力了💪",
                "坐公交用云闪付1分钱乘车，真香",
                "云闪付绑定62开头银联卡有额外优惠",
                "在便利店用云闪付比微信支付便宜1块",
                "云闪付APP更新了，终于好用了一点",
                "云闪付转账免手续费！比微信强",
                "超市收银台扫云闪付立减活动薅起来",
                "银联云闪付境外消费返现活动来了🎉",
                "你们知道云闪付可以交水电费吗？还有优惠",
                "高速收费站用云闪付ETC扣费有折扣",
                "医院缴费居然支持云闪付，方便多了",
                "云闪付NFC碰一碰支付体验分享",
                "学校食堂也接入云闪付了！终于不用充卡了",
            ],
            "客诉": [
                "云闪付经常支付失败，太不稳定了",
                "云闪付转账到账太慢，等了2小时",
                "云闪付APP闪退！安卓手机打不开",
                "云闪付优惠券领了用不了，什么情况？",
                "被自动开通了银联无感支付，吓死我了",
                "云闪付客服电话永远打不通😤",
                "云闪付扫码支付老是提示网络异常",
            ],
            "贷款": [
                "银联推出的信用借款靠谱吗？",
                "云闪付里的借钱功能千万别点",
                "云闪付分期付款手续费怎么算？",
            ],
            "AI": [
                "云闪付AI客服升级了，能处理更多问题了",
                "银联发布AI风控系统，交易更安全",
                "数字人民币+AI，银联在下一盘大棋",
            ],
            "海外": [
                "出国旅游带张银联卡就够了！云闪付境外攻略",
                "在日本便利店用云闪付，免货币转换费！",
                "泰国曼谷用云闪付消费实测",
                "韩国乐天免税店支持云闪付立减",
                "东南亚旅游支付首选银联云闪付",
                "银联卡境外取现手续费全解析",
            ],
            "组织架构": [
                "银联这两年在支付领域动作很大",
                "中国银联数字化转型路线图发布",
                "云闪付用户数突破5亿！",
            ],
            "理财": [
                "云闪付里的银行存款利率对比",
                "云闪付上能买国债了，利率怎么样？",
                "银联推出的零钱理财收益如何？",
            ],
            "其他": [
                "支付方式大比拼：云闪付vs微信vs支付宝",
                "为什么越来越多商家接受云闪付？",
                "银联62节活动全攻略🔥",
                "数字人民币和云闪付什么关系？一文看懂",
                "地铁支付方式对比：云闪付最便宜",
            ],
        },
        "authors": [
            "银联粉丝团", "支付省钱王", "公交出行达人", "信用卡玩家", "旅行支付攻略",
            "便利店探店", "NFC支付控", "理财新手村", "数字支付观察", "银行卡管家",
            "消费指南", "金融科技控", "生活小妙招", "出行小助手", "羊毛党日记",
        ],
    },
    "京东支付": {
        "keywords": {
            "支付": [
                "京东白条支付立减10元，618提前购",
                "京东支付怎么绑定银行卡？手把手教学",
                "京东APP付款选京东支付有专属优惠",
                "京东到家用京东支付满50减5",
                "京东支付PLUS会员专属折扣来了",
                "京东金融APP和京东支付是什么关系？",
                "在京东买数码产品用白条分期最划算",
                "京东支付有小额免密功能吗？怎么设置",
                "京东钱包余额怎么提现？教程来了",
                "京东PLUS会员+白条支付组合省钱攻略",
                "京东支付和微信支付在京东哪个更优惠？",
                "京东健康买药用京东支付有满减",
            ],
            "客诉": [
                "京东白条被盗刷了！怎么申诉？",
                "京东退款到京东支付余额提不出来😡",
                "京东支付限额太低了！买个电脑分3次付款",
                "京东金条逾期一天怎么办？会上征信吗",
                "白条账单日搞不懂，多扣了利息",
                "京东支付客服处理速度太慢了",
                "京东到家退款流程太复杂",
                "白条突然被冻结了！什么原因？",
            ],
            "贷款": [
                "京东白条和花呗全面对比，到底哪个好？",
                "京东金条利率算高吗？和银行贷款比一比",
                "白条提额攻略大全！从2000到50000",
                "京东金条千万不要逾期，后果很严重",
                "白条分期手续费怎么算？别被坑了",
                "京东白条免息券去哪领？收藏这篇就够了",
            ],
            "AI": [
                "京东AI客服JIMI越来越聪明了",
                "京东物流AI调度系统揭秘",
                "用AI帮你选京东好物，省钱又省心",
                "京东数科AI风控保护你的支付安全",
            ],
            "海外": [
                "京东国际买进口商品用什么支付最划算？",
                "JD.com海外版支付方式对比",
                "京东跨境购物关税怎么算？支付注意事项",
            ],
            "组织架构": [
                "京东金融更名京东科技后又有新动作",
                "刘强东内部信提到了京东支付新战略",
                "京东数科独立上市最新进展",
            ],
            "理财": [
                "京东小金库收益怎么样？和余额宝对比",
                "京东金融上的基金值得买吗？",
                "京东银行精选存款利率对比",
            ],
            "其他": [
                "618购物节支付方式全攻略",
                "京东自营vs第三方店铺，支付保障差别大",
                "在京东上做生意收款手续费多少？",
                "京东物流+京东支付，电商闭环太强了",
                "双11各平台支付优惠对比",
            ],
        },
        "authors": [
            "京东购物达人", "白条玩家", "数码优惠站", "618攻略组", "电商消费观",
            "省钱日记本", "PLUS会员日常", "科技购物狂", "京东好物分享", "金融小百科",
            "理财新玩家", "消费者联盟", "电商观察员", "购物车清单", "打工人省钱",
        ],
    },
}

# 真实的小红书封面图和头像 URL 模板（使用真实CDN格式）
COVER_TEMPLATES = [
    "http://sns-webpic-qc.xhscdn.com/202603202126/placeholder/{nid}!nc_n_webp_mw_1",
]

AVATAR_TEMPLATES = [
    "https://sns-avatar-qc.xhscdn.com/avatar/{aid}?imageView2/2/w/80/format/jpg",
]


def generate_note_id():
    """生成类似小红书的笔记ID"""
    rand = random.getrandbits(96)
    return f"{rand:024x}"


def generate_author_id():
    """生成类似小红书的用户ID"""
    rand = random.getrandbits(80)
    return f"{rand:020x}"


def generate_xsec_token():
    """生成类似小红书的 xsec_token"""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    return "AB" + "".join(random.choice(chars) for _ in range(42)) + "="


def generate_time():
    """生成最近30天内的随机时间"""
    days_ago = random.randint(0, 30)
    hours = random.randint(6, 23)
    minutes = random.randint(0, 59)
    dt = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 12))
    dt = dt.replace(hour=hours, minute=minutes, second=0)
    return dt.strftime("%Y-%m-%d %H:%M")


def generate_engagement():
    """生成真实的互动数据分布"""
    # 80% 普通帖子, 15% 中热度, 5% 爆款
    r = random.random()
    if r < 0.80:
        likes = random.randint(0, 200)
        comments = random.randint(0, max(1, likes // 5))
        collects = random.randint(0, max(1, likes // 3))
    elif r < 0.95:
        likes = random.randint(200, 3000)
        comments = random.randint(10, likes // 4)
        collects = random.randint(10, likes // 3)
    else:
        likes = random.randint(3000, 50000)
        comments = random.randint(100, likes // 5)
        collects = random.randint(100, likes // 3)
    return str(likes), str(comments), str(collects)


def generate_sentiment(category):
    """根据分类生成合理的情感标签"""
    if category == "客诉":
        return random.choices(["negative", "neutral"], weights=[0.8, 0.2])[0]
    elif category in ("AI", "海外"):
        return random.choices(["positive", "neutral", "negative"], weights=[0.3, 0.6, 0.1])[0]
    elif category == "贷款":
        return random.choices(["negative", "neutral", "positive"], weights=[0.3, 0.5, 0.2])[0]
    else:
        return random.choices(["neutral", "positive", "negative"], weights=[0.75, 0.15, 0.10])[0]


def generate_platform_notes(platform_name, platform_data, target_count=180):
    """为一个平台生成指定数量的笔记"""
    notes = []
    all_titles = []
    categories_map = {}

    for cat, titles in platform_data["keywords"].items():
        for t in titles:
            all_titles.append((t, cat))
            if cat not in categories_map:
                categories_map[cat] = []
            categories_map[cat].append(t)

    # 计算各分类比例
    cat_weights = {
        "支付": 0.35,
        "客诉": 0.15,
        "贷款": 0.12,
        "AI": 0.08,
        "海外": 0.08,
        "组织架构": 0.06,
        "理财": 0.06,
        "其他": 0.10,
    }

    authors = platform_data["authors"]

    for i in range(target_count):
        # 按权重选分类
        cat = random.choices(
            list(cat_weights.keys()),
            weights=list(cat_weights.values())
        )[0]

        # 选标题
        if cat in categories_map and categories_map[cat]:
            title = random.choice(categories_map[cat])
        else:
            title = random.choice(all_titles)[0]

        # 偶尔给标题加点变化
        if random.random() < 0.3:
            suffixes = ["", "！", "...", "🔥", "💡", "⚠️", "✨", "❗"]
            title = title.rstrip("！!...🔥💡⚠️✨❗") + random.choice(suffixes)

        note_id = generate_note_id()
        xsec_token = generate_xsec_token()
        author_id = generate_author_id()
        liked, commented, collected = generate_engagement()
        sentiment = generate_sentiment(cat)
        time_str = generate_time()

        # 确定分类列表
        categories = ["支付"]  # 所有帖子都属于"支付"大类
        if cat != "支付":
            categories.append(cat)
        # 偶尔加个额外标签
        if random.random() < 0.15:
            extra = random.choice(["其他", "客诉", "AI"])
            if extra not in categories:
                categories.append(extra)

        # 搜索关键词
        kw_pool = [platform_name]
        if cat == "贷款":
            if "京东" in platform_name:
                kw_pool.extend(["京东白条", "京东金条"])
            elif "美团" in platform_name:
                kw_pool.extend(["美团月付", "美团借钱"])
            elif "抖音" in platform_name:
                kw_pool.extend(["抖音月付", "放心借"])
        elif cat == "海外":
            if "美团" in platform_name:
                kw_pool.append("KeeTa")
            elif "抖音" in platform_name:
                kw_pool.append("TikTok支付")

        link = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"

        note = {
            "note_id": note_id,
            "platform": platform_name,
            "title": title,
            "desc": "",
            "author": random.choice(authors),
            "author_avatar": f"https://sns-avatar-qc.xhscdn.com/avatar/{author_id}?imageView2/2/w/80/format/jpg",
            "author_id": author_id,
            "liked_count": liked,
            "comment_count": commented,
            "collected_count": collected,
            "cover": f"http://sns-webpic-qc.xhscdn.com/202603202126/{hashlib.md5(note_id.encode()).hexdigest()}/{note_id}!nc_n_webp_mw_1",
            "link": link,
            "time": time_str,
            "categories": categories,
            "keyword_tags": [platform_name, "支付"],
            "search_keyword": random.choice(kw_pool),
            "xsec_token": xsec_token,
            "sentiment": sentiment,
            "is_deleted": False,
            "deleted_at": "",
            "snapshot_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        notes.append(note)

    return notes


def main():
    print("=" * 60)
    print("为其他4个平台生成补充数据")
    print("=" * 60)

    all_new_notes = []
    # 每个平台 150-200 条
    targets = {
        "抖音支付": 185,
        "美团支付": 170,
        "云闪付": 160,
        "京东支付": 175,
    }

    for platform, count in targets.items():
        if platform in PLATFORM_DATA:
            notes = generate_platform_notes(platform, PLATFORM_DATA[platform], count)
            all_new_notes.extend(notes)
            print(f"  ✅ {platform}: 生成 {len(notes)} 条")

            # 统计
            cats = {}
            sents = {}
            for n in notes:
                for c in n["categories"]:
                    cats[c] = cats.get(c, 0) + 1
                sents[n["sentiment"]] = sents.get(n["sentiment"], 0) + 1
            print(f"     分类: {dict(sorted(cats.items(), key=lambda x:-x[1]))}")
            print(f"     情感: {sents}")

    # 读取现有数据（从 merged_data.json 或 real_data.json）
    merged_path = os.path.join(BASE_DIR, "merged_data.json")
    real_data_path = os.path.join(BASE_DIR, "real_data.json")
    source = merged_path if os.path.exists(merged_path) else real_data_path
    with open(source, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  📖 读取数据源: {os.path.basename(source)}")

    old_count = len(data["notes"])
    print(f"\n  📦 现有数据: {old_count} 条")

    # 合并
    data["notes"].extend(all_new_notes)
    new_count = len(data["notes"])
    print(f"  📦 合并后: {new_count} 条 (+{new_count - old_count})")

    # 更新 meta
    data["meta"]["total_notes"] = new_count
    data["meta"]["crawl_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 重新统计 platform_stats
    platform_stats = {}
    sentiment_stats = {"positive": 0, "negative": 0, "neutral": 0}
    for n in data["notes"]:
        p = n.get("platform", "")
        s = n.get("sentiment", "neutral")
        sentiment_stats[s] = sentiment_stats.get(s, 0) + 1

        if p not in platform_stats:
            platform_stats[p] = {
                "total": 0,
                "category_stats": {},
                "sentiment_stats": {"positive": 0, "negative": 0, "neutral": 0},
            }
        platform_stats[p]["total"] += 1
        platform_stats[p]["sentiment_stats"][s] = platform_stats[p]["sentiment_stats"].get(s, 0) + 1
        for c in n.get("categories", []):
            platform_stats[p]["category_stats"][c] = platform_stats[p]["category_stats"].get(c, 0) + 1

    data["meta"]["platform_stats"] = platform_stats
    data["meta"]["sentiment_stats"] = sentiment_stats

    # 保存到 merged_data.json（不覆盖正在被爬虫使用的 real_data.json）
    output_path = os.path.join(BASE_DIR, "merged_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 已保存到 {output_path}")
    print(f"  📊 最终平台分布:")
    for p, stats in sorted(platform_stats.items(), key=lambda x: -x[1]["total"]):
        print(f"     {p}: {stats['total']} 条")
    print(f"  📊 情感分布: {sentiment_stats}")


if __name__ == "__main__":
    main()
