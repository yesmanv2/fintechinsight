"""
小红书支付行业舆情监控 - 多平台实时Web服务器
支持：支付宝、微信支付、抖音支付、美团支付、云闪付
"""
import http.server
import json
import os
import threading
import time
import random
import hashlib
import urllib.parse
import gzip
from datetime import datetime, timedelta

PORT = 9091
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

# ==================== 平台配置 ====================

PLATFORMS_CONFIG = {
    "微信支付": {
        "icon": "💚", "color": "#07C160",
        "categories": ["支付", "贷款", "理财", "AI", "海外", "组织架构", "客诉", "其他"],
    },
    "支付宝": {
        "icon": "💙", "color": "#1677FF",
        "categories": ["支付", "贷款", "理财", "AI", "海外", "组织架构", "客诉", "其他"],
    },
    "抖音支付": {
        "icon": "🖤", "color": "#FE2C55",
        "categories": ["支付", "贷款", "理财", "AI", "海外", "组织架构", "客诉", "其他"],
    },
    "美团支付": {
        "icon": "💛", "color": "#FFC300",
        "categories": ["支付", "贷款", "理财", "AI", "海外", "组织架构", "客诉", "其他"],
    },
    "云闪付": {
        "icon": "🔴", "color": "#E60012",
        "categories": ["支付", "AI", "海外", "组织架构", "客诉"],
    },
}

# ==================== 各平台实时注入模板 ====================

REALTIME_TEMPLATES = {
    "微信支付": {
        "支付": [
            {"title": "微信刷掌太科幻了", "desc": "在地铁试了微信刷掌支付，手一伸就过闸机了，连手机都不用掏。", "sentiment": "positive"},
            {"title": "微信摇一摇摇到大红包", "desc": "周末在商场摇一摇微信，摇到了满200减80的券，赶紧去消费。", "sentiment": "positive"},
            {"title": "微信红包封面又出新款了", "desc": "抢到了新出的微信红包封面，发红包的时候太好看了，朋友都在问哪领的。", "sentiment": "positive"},
        ],
        "贷款": [
            {"title": "微粒贷给的额度还挺高", "desc": "今天看了下微粒贷，给了8万额度，日利率万2.5，比想象中低。", "sentiment": "positive"},
            {"title": "微信分付终于开通了", "desc": "等了好久终于有微信分付入口了，和花呗一样方便，额度5000。", "sentiment": "positive"},
        ],
        "理财": [
            {"title": "零钱通收益和余额宝差不多", "desc": "对比了微信零钱通和余额宝的7日年化，差距不大，看自己方便。", "sentiment": "neutral"},
        ],
        "客诉": [
            {"title": "微信支付被风控好无语", "desc": "转账给朋友3000块就被风控了，正常转账都要审核太过分了。", "sentiment": "negative"},
        ],
        "AI": [
            {"title": "微信AI助手推荐了好优惠", "desc": "微信支付的AI助手给我推荐了附近商店的优惠券，都是常去的店，很精准。", "sentiment": "positive"},
            {"title": "腾讯混元大模型接入微信了", "desc": "微信里可以直接用腾讯混元AI了，智能对话、写作、翻译都有，微信生态AI化加速。", "sentiment": "positive"},
        ],
    },
    "支付宝": {
        "支付": [
            {"title": "刚用支付宝碰一碰付了杯咖啡", "desc": "早上去咖啡店试了下支付宝碰一碰，手机贴一下就付款了，比扫码快太多了！", "sentiment": "positive"},
            {"title": "支付宝扫码又崩了？", "desc": "中午去食堂吃饭扫码付款，一直显示网络异常，等了好几分钟才成功。", "sentiment": "negative"},
            {"title": "支付宝数字人民币活动力度真大", "desc": "参加了支付宝数字人民币消费立减活动，买了200块的东西减了40。", "sentiment": "positive"},
            {"title": "支付宝神券节又来了！", "desc": "支付宝神券节开始了，到店消费满100减30，叠加消费券太划算了。", "sentiment": "positive"},
        ],
        "贷款": [
            {"title": "花呗账单日快到了好焦虑", "desc": "这个月花呗花了快8000，下周就是账单日了，看来又要分期了。", "sentiment": "negative"},
            {"title": "借呗利率突然降了！开心", "desc": "刚打开支付宝发现借呗利率从万4降到万3了，截图记录一下。", "sentiment": "positive"},
        ],
        "理财": [
            {"title": "余额宝今天收益又创新低了", "desc": "10万块放余额宝，今天收益才3.2元，7日年化1.18%。", "sentiment": "negative"},
            {"title": "支付宝定投第100天打卡", "desc": "沪深300定投第100天了，总额1万元，收益312元，坚持定投。", "sentiment": "positive"},
            {"title": "小荷包存钱计划达标了", "desc": "和闺蜜用小荷包攒旅行基金，三个月终于攒够了1万块！", "sentiment": "positive"},
        ],
        "海外": [
            {"title": "在泰国用支付宝买了街边小吃", "desc": "没想到曼谷路边摊都能用支付宝了，出国带个手机就够了。", "sentiment": "positive"},
        ],
        "组织架构": [
            {"title": "蚂蚁集团又在招人了", "desc": "看到蚂蚁集团放出了一批招聘岗位，主要是AI和海外方向。", "sentiment": "neutral"},
        ],
        "客诉": [
            {"title": "支付宝又弹广告了受不了", "desc": "打开支付宝付款，又弹了个全屏广告，强烈要求出纯净模式。", "sentiment": "negative"},
            {"title": "支付宝客服终于解决了我的问题", "desc": "之前投诉的自动扣费问题终于解决了，退了钱还给了补偿。", "sentiment": "positive"},
        ],
        "AI": [
            {"title": "支付宝阿福AI助手帮我查了账单", "desc": "用蚂蚁阿福AI助手查了上个月的消费明细，分析得很清楚，还给了省钱建议。", "sentiment": "positive"},
            {"title": "支付宝AI健康问诊回复挺快", "desc": "半夜用支付宝AI健康问诊咨询了感冒症状，几秒就给了用药建议，比等医院快多了。", "sentiment": "positive"},
            {"title": "灵光AI新功能上线了", "desc": "支付宝灵光AI更新了，新增了语音对话和图片识别功能，越来越强了。", "sentiment": "positive"},
        ],
    },
    "抖音支付": {
        "支付": [
            {"title": "抖音团购券到店好划算", "desc": "在抖音买了火锅的团购券，比到店直接吃便宜了一半，赚到了。", "sentiment": "positive"},
            {"title": "直播间又冲动消费了", "desc": "在直播间看得太嗨了不知不觉下了好几单，抖音的支付太顺滑了。", "sentiment": "negative"},
            {"title": "抖音外卖真的来了我们城市", "desc": "终于开通了抖音外卖，试了一下确实比美团便宜，配送也行。", "sentiment": "positive"},
        ],
        "贷款": [
            {"title": "抖音放心借利率还行", "desc": "开通了放心借，额度2万，利率万4左右，应急用还可以。", "sentiment": "neutral"},
        ],
        "客诉": [
            {"title": "抖音退款太慢了", "desc": "团购券过期申请退款一周了还在审核中，客服也联系不上。", "sentiment": "negative"},
        ],
        "AI": [
            {"title": "豆包AI帮我写了抖音文案", "desc": "用豆包AI写了一段商品文案，发抖音后播放量比平时高了好多，AI写作真的好用。", "sentiment": "positive"},
            {"title": "抖音AI特效又出新的了", "desc": "抖音新出了一批AI特效，一键就能把视频变成动画风格，太好玩了。", "sentiment": "positive"},
        ],
    },
    "美团支付": {
        "支付": [
            {"title": "美团满减叠加太爽了", "desc": "美团外卖叠加了好几个红包，30块的外卖只付了12块，天天薅。", "sentiment": "positive"},
            {"title": "美团买单到店又省了好多", "desc": "去餐厅用美团买单，叠加优惠券实际只付了6折，太划算了。", "sentiment": "positive"},
            {"title": "美团闪购半小时送到家", "desc": "深夜在美团闪购买了零食和药品，半小时就送到了，真方便。", "sentiment": "positive"},
        ],
        "贷款": [
            {"title": "美团月付还挺好用", "desc": "外卖用美团月付免息分期，月底统一还款很方便。", "sentiment": "positive"},
        ],
        "客诉": [
            {"title": "美团外卖洒了也不全赔", "desc": "外卖送来全洒了，申请赔偿只给了5元优惠券，太敷衍了。", "sentiment": "negative"},
        ],
        "AI": [
            {"title": "美团无人配送车又来送外卖了", "desc": "今天又是无人配送车送的外卖，感觉美团的AI技术越来越成熟了。", "sentiment": "positive"},
            {"title": "美团AI推荐的餐厅真不错", "desc": "美团AI推荐了一家新开的日料店，价格适中口味很好，AI推荐越来越准了。", "sentiment": "positive"},
        ],
    },
    "云闪付": {
        "支付": [
            {"title": "云闪付满减活动力度大", "desc": "在超市用云闪付付款满100减20，比微信支付宝的优惠都大。", "sentiment": "positive"},
            {"title": "Apple Pay刷银联卡太爽了", "desc": "NFC碰一下就付款了，速度比扫码快太多，用了就回不去了。", "sentiment": "positive"},
        ],
        "海外": [
            {"title": "银联卡在日本优惠好多", "desc": "日本旅游用银联卡消费有额外折扣，在免税店还能叠加优惠。", "sentiment": "positive"},
        ],
        "客诉": [
            {"title": "云闪付又闪退了", "desc": "打开云闪付领红包的时候又闪退了，最近更新后越来越不稳定。", "sentiment": "negative"},
        ],
        "AI": [
            {"title": "云闪付AI推荐优惠券挺精准的", "desc": "最近云闪付用AI推荐优惠券了，推的都是我常去的超市的券，比以前好用多了。", "sentiment": "positive"},
        ],
    },
}

NICKNAMES = [
    "小财迷酱", "理财达人", "生活观察家", "支付测评师", "科技宅小明",
    "旅行博主Lucy", "搞钱女孩", "职场打工人", "吐槽王阿杰", "财经小助手",
    "海外生活圈", "消费维权君", "数码极客", "投资笔记本", "生活日记",
    "大厂观察员", "信用管理师", "省钱攻略组", "金融科普", "互联网圈内人",
    "打工人日记", "薅羊毛专家", "消费降级中", "存钱罐子", "信用卡老司机",
    "基金小韭菜", "真诚分享中", "宝妈日常", "大学生小李", "退休阿姨",
]


class RealtimeDataEngine:
    """多平台实时数据引擎"""

    def __init__(self, data_file):
        self.data_file = data_file
        self.lock = threading.Lock()
        self._load_data()
        self._running = True

    def _load_data(self):
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {
                "meta": {
                    "crawl_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "total_notes": 0,
                    "sentiment_stats": {"positive": 0, "negative": 0, "neutral": 0},
                    "platform_stats": {},
                    "platforms_config": {},
                    "is_demo": True,
                    "data_range": "2023-01-01 至今",
                },
                "notes": []
            }

    def _generate_new_note(self):
        """生成一条新的实时笔记，随机选平台"""
        platform = random.choice(list(REALTIME_TEMPLATES.keys()))
        cats = list(REALTIME_TEMPLATES[platform].keys())
        category = random.choice(cats)
        templates = REALTIME_TEMPLATES[platform][category]
        tmpl = random.choice(templates)

        now = datetime.now()
        minutes_ago = random.randint(1, 120)
        note_time = now - timedelta(minutes=minutes_ago)
        time_str = note_time.strftime('%Y-%m-%d %H:%M')

        note_id = hashlib.md5(f"{platform}_{tmpl['title']}_{time_str}_{random.randint(0,999999)}".encode()).hexdigest()[:16]

        liked = random.randint(1, 200)
        comments = random.randint(0, max(1, liked // 5))
        collected = random.randint(0, max(1, liked // 4))

        categories = [category]
        platform_cats = PLATFORMS_CONFIG.get(platform, {}).get("categories", [])
        if random.random() < 0.15:
            other = [c for c in platform_cats if c != category]
            if other:
                categories.append(random.choice(other))

        return {
            "note_id": note_id,
            "platform": platform,
            "title": tmpl["title"],
            "desc": tmpl["desc"],
            "author": random.choice(NICKNAMES),
            "author_avatar": "",
            "author_id": f"user_{random.randint(100000, 999999)}",
            "liked_count": str(liked),
            "comment_count": str(comments),
            "collected_count": str(collected),
            "cover": "",
            "link": f"https://www.xiaohongshu.com/explore/{note_id}",
            "time": time_str,
            "categories": categories,
            "keyword_tags": [],
            "search_keyword": f"{platform}{category}",
            "xsec_token": "",
            "sentiment": tmpl["sentiment"],
            "is_new": True,
        }

    def inject_new_notes(self):
        with self.lock:
            count = random.randint(1, 3)
            new_notes = []
            existing_ids = {n["note_id"] for n in self._data.get("notes", [])}

            for _ in range(count):
                note = self._generate_new_note()
                if note["note_id"] not in existing_ids:
                    new_notes.append(note)
                    existing_ids.add(note["note_id"])

            if new_notes:
                self._data["notes"] = new_notes + self._data.get("notes", [])
                self._recalculate_stats()
                # 不再写回文件，保护历史日期数据，仅在内存中注入
                platforms = set(n["platform"] for n in new_notes)
                print(f"📥 [{datetime.now().strftime('%H:%M:%S')}] 注入 {len(new_notes)} 条 ({', '.join(platforms)}) (总计 {len(self._data['notes'])})")

    def _recalculate_stats(self):
        total_sentiment = {"positive": 0, "negative": 0, "neutral": 0}
        platform_stats = {}

        for note in self._data.get("notes", []):
            p = note.get("platform", "支付宝")
            if p not in platform_stats:
                platform_stats[p] = {"total": 0, "category_stats": {}, "sentiment_stats": {"positive": 0, "negative": 0, "neutral": 0}}

            platform_stats[p]["total"] += 1
            for cat in note.get("categories", []):
                platform_stats[p]["category_stats"][cat] = platform_stats[p]["category_stats"].get(cat, 0) + 1
            s = note.get("sentiment", "neutral")
            platform_stats[p]["sentiment_stats"][s] += 1
            total_sentiment[s] += 1

        self._data["meta"]["sentiment_stats"] = total_sentiment
        self._data["meta"]["platform_stats"] = platform_stats
        self._data["meta"]["total_notes"] = len(self._data["notes"])
        self._data["meta"]["crawl_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存数据失败: {e}")

    def get_data(self, platform=None, since=None, limit=None):
        """获取数据，支持按平台和时间过滤，支持limit分页"""
        with self.lock:
            notes = self._data.get("notes", [])

            # 按平台过滤
            if platform:
                notes = [n for n in notes if n.get("platform") == platform]

            # 增量查询
            if since:
                new_notes = [n for n in notes if n.get("time", "") > since]
                # 计算该平台的统计
                meta = dict(self._data.get("meta", {}))
                if platform and platform in meta.get("platform_stats", {}):
                    p_stats = meta["platform_stats"][platform]
                    meta["category_stats"] = p_stats["category_stats"]
                    meta["sentiment_stats"] = p_stats["sentiment_stats"]
                    meta["total_notes"] = p_stats["total"]
                return {
                    "meta": meta,
                    "notes": new_notes,
                    "is_incremental": True,
                    "new_count": len(new_notes),
                }
            else:
                meta = dict(self._data.get("meta", {}))
                if platform and platform in meta.get("platform_stats", {}):
                    p_stats = meta["platform_stats"][platform]
                    meta["category_stats"] = p_stats["category_stats"]
                    meta["sentiment_stats"] = p_stats["sentiment_stats"]
                    meta["total_notes"] = p_stats["total"]
                total_count = len(notes)
                if limit and limit > 0:
                    notes = notes[:limit]
                return {
                    "meta": meta,
                    "notes": notes,
                    "total_count": total_count,
                    "returned_count": len(notes),
                }

    def start_injection_loop(self, interval_range=(30, 90)):
        def loop():
            while self._running:
                interval = random.randint(*interval_range)
                time.sleep(interval)
                if self._running:
                    self.inject_new_notes()

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        print(f"🔄 实时数据注入已启动（每 {interval_range[0]}-{interval_range[1]} 秒）")

    def stop(self):
        self._running = False


# 全局数据引擎
engine = None


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/api/data':
            platform = query.get('platform', [None])[0]
            since = query.get('since', [None])[0]
            limit_str = query.get('limit', [None])[0]
            limit = int(limit_str) if limit_str else None
            self.send_json_response(platform, since, limit)
        elif path == '/api/stats':
            self.send_stats_response()
        elif path == '/api/monthly':
            self.send_monthly_response()
        elif path == '/api/platforms':
            self.send_platforms_response()
        elif path == '/' or path == '/index.html':
            self.path = '/index.html'
            super().do_GET()
        else:
            super().do_GET()

    def _send_gzip_json(self, data_dict):
        """发送gzip压缩的JSON响应"""
        raw = json.dumps(data_dict, ensure_ascii=False).encode('utf-8')
        accept_encoding = self.headers.get('Accept-Encoding', '')
        if 'gzip' in accept_encoding and len(raw) > 1024:
            compressed = gzip.compress(raw, compresslevel=6)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Content-Length', len(compressed))
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Content-Length', len(raw))
            self.end_headers()
            self.wfile.write(raw)

    def send_json_response(self, platform=None, since=None, limit=None):
        try:
            global engine
            data = engine.get_data(platform=platform, since=since, limit=limit)
            self._send_gzip_json(data)
        except Exception as e:
            self.send_error(500, str(e))

    def send_stats_response(self):
        try:
            global engine
            data = engine.get_data()
            stats = {
                "total": data["meta"]["total_notes"],
                "platform_stats": data["meta"].get("platform_stats", {}),
                "sentiment_stats": data["meta"]["sentiment_stats"],
                "crawl_time": data["meta"]["crawl_time"],
            }
            self._send_gzip_json(stats)
        except Exception as e:
            self.send_error(500, str(e))

    def send_platforms_response(self):
        try:
            global engine
            meta = engine._data.get("meta", {})
            self._send_gzip_json({
                "platforms_config": meta.get("platforms_config", {}),
                "platform_stats": meta.get("platform_stats", {}),
            })
        except Exception as e:
            self.send_error(500, str(e))

    def send_monthly_response(self):
        """返回月度分析数据（从 monthly_analysis.json 加载）"""
        try:
            monthly_file = os.path.join(BASE_DIR, 'monthly_analysis.json')
            if os.path.exists(monthly_file):
                with open(monthly_file, 'r', encoding='utf-8') as f:
                    monthly_data = json.load(f)
                self._send_gzip_json(monthly_data)
            else:
                self._send_gzip_json({"error": "monthly_analysis.json not found"})
        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    # 优先使用真实爬取数据
    real_data_file = os.path.join(BASE_DIR, 'real_data.json')
    use_real_data = False
    if os.path.exists(real_data_file):
        engine = RealtimeDataEngine(real_data_file)
        use_real_data = True
        print("📂 使用真实爬取数据: real_data.json")
    else:
        engine = RealtimeDataEngine(DATA_FILE)
        print("⚠️ 未找到真实数据，使用 data.json")

    import socketserver
    import socket

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
        address_family = socket.AF_INET

    with ReusableTCPServer(("0.0.0.0", PORT), RequestHandler) as httpd:
        total = engine._data['meta']['total_notes']
        p_stats = engine._data['meta'].get('platform_stats', {})
        # 获取局域网IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "localhost"
        print(f"\n🌐 支付行业舆情监控实时服务已启动:")
        print(f"   💻 电脑访问: http://localhost:{PORT}")
        print(f"   📱 手机访问: http://{local_ip}:{PORT}")
        print(f"📊 当前数据量: {total} 条笔记")
        for p_name, p_data in p_stats.items():
            icon = PLATFORMS_CONFIG.get(p_name, {}).get("icon", "📌")
            print(f"   {icon} {p_name}: {p_data['total']} 条")
        if use_real_data:
            print("📅 数据类型: 真实爬取数据（不注入假数据）")
        else:
            print("📅 数据类型: 演示数据")
            # 只有使用非真实数据时才启动注入（可选）
            # engine.start_injection_loop()
        print("按 Ctrl+C 停止服务\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            engine.stop()
            print("\n🛑 服务已停止")
