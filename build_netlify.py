"""
构建 Netlify 部署版本
策略：直接从本地 index.html 复制全部 HTML/CSS/JS，
      只把 JS 中依赖后端 API 的部分替换为内嵌数据版。
"""
import json, os, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 1. 读取真实数据（real_data.json 优先，包含完整爬取数据） ──
real_file = os.path.join(BASE_DIR, 'real_data.json')
clean_file = os.path.join(BASE_DIR, 'clean_data.json')
data_file = real_file if os.path.exists(real_file) else clean_file

if not os.path.exists(data_file):
    raise FileNotFoundError("找不到数据文件！请先运行爬虫获取真实数据。")

with open(data_file, 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

meta = raw_data.get('meta', {})
notes = raw_data.get('notes', [])
print(f"从 {os.path.basename(data_file)} 读取 {len(notes)} 条真实爬取数据")
platform_stats = meta.get('platform_stats', {})

# platforms_config 从 meta 里取，并确保所有数据中出现的平台都有配置
platforms_config = meta.get('platforms_config', {})
ICONS = {"支付宝": "💙", "微信支付": "💚", "抖音支付": "🖤", "美团支付": "💛", "云闪付": "🔴", "京东支付": "💎"}
COLORS = {"支付宝": "#1677FF", "微信支付": "#07C160", "抖音支付": "#FE2C55", "美团支付": "#FFC300", "云闪付": "#E60012", "京东支付": "#E4393C"}
all_platforms_in_data = set(n.get('platform', '') for n in notes)
for pname in all_platforms_in_data:
    if pname and pname not in platforms_config:
        platforms_config[pname] = {
            "icon": ICONS.get(pname, "📌"),
            "color": COLORS.get(pname, "#6366f1"),
            "categories": [],
        }

# 按平台分组笔记，放入全部真实数据（按时间倒序排列）
notes_by_platform = {}
for note in notes:
    p = note.get('platform', '未知')
    notes_by_platform.setdefault(p, []).append(note)

# 排序（不截取，保留全部真实数据）
for p in notes_by_platform:
    notes_by_platform[p].sort(key=lambda x: x.get('time', ''), reverse=True)

# 用全部数据重新计算 platform_stats
platform_stats_new = {}
for p, pnotes in notes_by_platform.items():
    cat_stats = {}
    sent_stats = {"positive": 0, "negative": 0, "neutral": 0}
    for n in pnotes:
        for c in n.get('categories', []):
            cat_stats[c] = cat_stats.get(c, 0) + 1
        s = n.get('sentiment', 'neutral')
        if s in sent_stats:
            sent_stats[s] += 1
    platform_stats_new[p] = {
        "total": len(pnotes),
        "category_stats": cat_stats,
        "sentiment_stats": sent_stats,
    }
platform_stats = platform_stats_new

embedded = {
    "platforms_config": platforms_config,
    "platform_stats": platform_stats,
    "notes_by_platform": notes_by_platform,
}
embedded_json = json.dumps(embedded, ensure_ascii=False, separators=(',', ':'))
print(f"内嵌数据大小: {len(embedded_json)//1024} KB")

# ── 1b. 读取月度分析数据（如果存在） ──
monthly_file = os.path.join(BASE_DIR, 'monthly_analysis.json')
monthly_json = 'null'
if os.path.exists(monthly_file):
    with open(monthly_file, 'r', encoding='utf-8') as f:
        monthly_data = json.load(f)
    monthly_json = json.dumps(monthly_data, ensure_ascii=False, separators=(',', ':'))
    print(f"月度分析数据大小: {len(monthly_json)//1024} KB")
else:
    print("⚠️ monthly_analysis.json 不存在，跳过月度分析数据嵌入")

# ── 2. 读取本地 index.html（完美可用版） ──
with open(os.path.join(BASE_DIR, 'index.html'), 'r', encoding='utf-8') as f:
    html = f.read()

# ── 3. 提取主 <script>...</script> 之间的 JS 代码 ──
# 注意：index.html 有两个 <script> 标签，第一个是缩进的小脚本（switchInsight等），
# 第二个才是主脚本（行首无缩进）。只替换主脚本。
script_match = re.search(r'^<script>\n(.*?)\n</script>', html, re.DOTALL | re.MULTILINE)
if not script_match:
    raise RuntimeError("找不到主 <script> 标签（行首无缩进的）")

original_js = script_match.group(1)

# ── 4. 构造新的 JS ──
# 策略：保留原 JS 中的大部分函数，只替换 init / loadPlatformData / startPolling 等 API 相关部分
# 为了完全避免 f-string 的 { } 转义噩梦，我们直接用字符串拼接

# 4a. 从原 JS 中提取不需要修改的函数
# 需要替换的函数：fetchWithRetry, init, selectPlatform, loadPlatformData, loadRemainingData, startPolling, showToast
# 保留的函数：所有其他的

new_js_parts = []

# 添加内嵌数据声明
new_js_parts.append('// ========== Netlify 静态版 - 数据内嵌，无需后端 ==========')
new_js_parts.append('const EMBEDDED_DATA = ' + embedded_json + ';')
new_js_parts.append('const MONTHLY_DATA = ' + monthly_json + ';')
new_js_parts.append('')

# 保留变量声明，去掉 API 相关变量
new_js_parts.append('let allNotes=[], filteredNotes=[], displayedCount=0;')
new_js_parts.append('const PAGE_SIZE=50;')
new_js_parts.append('let currentCategory="all", currentSentiment=null, currentPlatform=null, filterDeletedOnly=false;')
new_js_parts.append('let platformsConfig={}, categoryChart=null, sentimentChart=null, trendChart=null;')
new_js_parts.append('let searchTimeout=null;')
new_js_parts.append('let currentCompareTab="yearly", monthlyCategoryChart=null;')
new_js_parts.append('')

# 提取 PLATFORM_LOGOS（平台真实Logo SVG）
logo_match = re.search(r'(// ========== 平台真实Logo.*?const PLATFORM_LOGOS=\{.*?\n\};)', original_js, re.DOTALL)
if logo_match:
    new_js_parts.append(logo_match.group(1))
    new_js_parts.append('')

# 提取 getPlatformLogo 函数
logo_func_match = re.search(r'(function getPlatformLogo\(.*?\n\})', original_js, re.DOTALL)
if logo_func_match:
    new_js_parts.append(logo_func_match.group(1))
    new_js_parts.append('')

# 提取 PLATFORM_KEYWORDS（从 const PLATFORM_KEYWORDS 到闭合的 };）
kw_match = re.search(r'(const PLATFORM_KEYWORDS=\{.*?\n\};)', original_js, re.DOTALL)
if kw_match:
    new_js_parts.append(kw_match.group(1))
    new_js_parts.append('')

# 提取 CAT_COLORS_MAP（月度分析用到的分类颜色映射）
cat_colors_match = re.search(r'(const CAT_COLORS_MAP=\{.*?\};)', original_js)
if cat_colors_match:
    new_js_parts.append(cat_colors_match.group(1))
    new_js_parts.append('')

# ── 静态版的 init 函数 ──
new_js_parts.append('''function init(){
    document.getElementById('dateTo').value=new Date().toISOString().split('T')[0];
    platformsConfig=EMBEDDED_DATA.platforms_config||{};
    const CATEGORY_COLORS={"支付":"#6366f1","贷款":"#f59e0b","理财":"#22c55e","AI":"#8b5cf6","海外":"#06b6d4","组织架构":"#ec4899","客诉":"#ef4444","其他":"#64748b"};
    const CATEGORY_ICONS={"支付":"💳","贷款":"💰","理财":"📈","AI":"🤖","海外":"🌏","组织架构":"🏢","客诉":"😤","其他":"📌"};
    for(const[pName,pCfg]of Object.entries(platformsConfig)){
        if(!pCfg.categories_config){
            pCfg.categories_config={};
            for(const cat of (pCfg.categories||[])){
                pCfg.categories_config[cat]={color:CATEGORY_COLORS[cat]||"#6366f1",icon:CATEGORY_ICONS[cat]||"📌"};
            }
        }
    }
    const ps=EMBEDDED_DATA.platform_stats||{};
    buildPlatformTabs(ps);
    buildWelcomeCards(ps);
    let total=0;for(const v of Object.values(ps))total+=v.total||0;
    var tb=document.getElementById('totalBadge');if(tb)tb.textContent=total+' 条数据';
    try{buildCrossCompare();}catch(e){console.error('buildCrossCompare error:',e);}
}''')
new_js_parts.append('')

# 提取 buildPlatformTabs, buildWelcomeCards, selectPlatformByName（不用改）
for func_name in ['buildPlatformTabs', 'buildWelcomeCards', 'selectPlatformByName']:
    pattern = rf'(function {func_name}\(.*?\n\}})'
    m = re.search(pattern, original_js, re.DOTALL)
    if m:
        new_js_parts.append(m.group(1))
        new_js_parts.append('')

# ── 静态版 selectPlatform（去掉 async/await） ──
new_js_parts.append('''function selectPlatform(name, tabEl){
    document.querySelectorAll('.platform-tab').forEach(t=>t.classList.remove('active'));
    if(tabEl)tabEl.classList.add('active');
    currentPlatform=name;
    currentCategory='all';
    currentSentiment=null;
    filterDeletedOnly=false;
    document.querySelectorAll('.sentiment-btn').forEach(b=>b.classList.remove('active'));
    document.getElementById('searchInput').value='';
    document.getElementById('welcomeSection').style.display='none';
    document.getElementById('platformContent').style.display='block';
    loadPlatformData(name);
    buildKeywordGroups(name);
    buildMonthlyAnalysis(name);
    buildReportArchive(name);
}''')
new_js_parts.append('')

# ── 静态版 loadPlatformData（从内嵌数据读取） ──
new_js_parts.append('''function loadPlatformData(platform){
    const notes=EMBEDDED_DATA.notes_by_platform[platform]||[];
    allNotes=notes.sort((a,b)=>(b.time||'').localeCompare(a.time||''));
    const ps=EMBEDDED_DATA.platform_stats[platform]||{};
    const catsCfg=platformsConfig[platform]?.categories_config||{};
    const meta={
        total_notes:ps.total||allNotes.length,
        category_stats:ps.category_stats||{},
        sentiment_stats:ps.sentiment_stats||{positive:0,negative:0,neutral:0},
    };
    updateStats(meta, catsCfg);
    buildCategoryFilters(meta.category_stats, catsCfg);
    buildCharts(meta, catsCfg);
    applyFilters();
    document.getElementById('refreshTime').textContent='数据快照 · ''' + meta.get('crawl_time', '') + '''';
    buildDigest(platform);
}''')
new_js_parts.append('')

# 提取所有不需要修改的函数（从 updateStats 到 init() 调用之前）
# 列出需要原样保留的函数
preserve_funcs = [
    'updateStats', 'buildCategoryFilters', 'buildKeywordGroups', 'buildCharts',
    'buildCategoryChart', 'buildSentimentChart',
    'filterCategory', 'filterSentiment', 'filterDeleted',
    'debounceSearch', 'searchKeyword', 'applyFilters', 'renderNotes',
    'loadMoreNotes', 'renderCard', 'getTimeAgo', 'esc', 'fmtNum',
    'openNoteDetail', 'closeModal', 'closeModalOutside',
    # 微信检测 + 舆情速览
    'isWechat', 'showWxGuide', 'dismissWxGuide', 'checkWechatEnv',
    'openOriginalNote', 'openInXhs', 'buildDigest',
    # 月度分析模块
    'buildCrossCompare', 'switchCompareTab', 'updateCompareOptions', 'changeCompareTime',
    'buildMonthlyAnalysis', 'changeMonthlyTime', 'renderMonthlyDetail',
    'monthlyStatCard', 'topNoteCard',
    # 关键发现 + 折叠分区 + 结论关联原帖
    'buildKeyFindings', 'toggleSection', 'scrollToSection', 'findRelatedNotes',
    # 客诉分析报告档案 - 不再原样保留，改为手动注入带在线阅读链接的版本
]

for func_name in preserve_funcs:
    # 匹配 function funcName(...)  到下一个顶层函数或文件末尾
    # 使用更精确的模式
    if func_name in ('esc', 'fmtNum', 'debounceSearch', 'searchKeyword', 'isWechat'):
        # 单行函数
        pattern = rf'^(function {func_name}\(.*?\}})$'
        m = re.search(pattern, original_js, re.MULTILINE)
    else:
        # 多行函数 - 找到函数开始，然后匹配到正确的闭合大括号
        # 用手动的括号匹配
        start_pattern = rf'function {func_name}\('
        m_start = re.search(start_pattern, original_js)
        if m_start:
            pos = m_start.start()
            # 找到第一个 {
            brace_start = original_js.index('{', pos)
            depth = 0
            i = brace_start
            while i < len(original_js):
                if original_js[i] == '{':
                    depth += 1
                elif original_js[i] == '}':
                    depth -= 1
                    if depth == 0:
                        func_body = original_js[pos:i+1]
                        new_js_parts.append(func_body)
                        new_js_parts.append('')
                        break
                i += 1
            m = True  # 标记已处理
        else:
            m = None
    
    if m and func_name in ('esc', 'fmtNum', 'debounceSearch', 'searchKeyword', 'isWechat'):
        new_js_parts.append(m.group(1))
        new_js_parts.append('')

# ── 注入时间选择器版的 buildReportArchive + switchReport ──
new_js_parts.append('''// 报告在线预览路径映射
const REPORT_URLS={
    "微信支付":{"2026-03":"reports/wxpay-2026-03.html"},
    "支付宝":{"2026-03":"reports/alipay-2026-03.html"},
    "抖音支付":{"2026-03":"reports/douyinpay-2026-03.html"},
    "美团支付":{"2026-03":"reports/meituanpay-2026-03.html"},
    "京东支付":{"2026-03":"reports/jdpay-2026-03.html"},
    "云闪付":{"2026-03":"reports/unionpay-2026-03.html"},
};

function buildReportArchive(platform){
    const section=document.getElementById('reportArchiveSection');
    const sel=document.getElementById('reportTimeSelect');
    if(!section||!sel)return;
    const shortName={"微信支付":"微信支付","支付宝":"支付宝","抖音支付":"抖音支付","京东支付":"京东支付","美团支付":"美团支付","云闪付":"云闪付"}[platform]||platform;
    const reports=[];
    const now=new Date();
    const startYear=2026, startMonth=3;
    let y=startYear, m=startMonth;
    while(y<now.getFullYear()||(y===now.getFullYear()&&m<=now.getMonth()+1)){
        const mStr=String(m).padStart(2,'0');
        const ym=y+'-'+mStr;
        const url=(REPORT_URLS[platform]&&REPORT_URLS[platform][ym])||null;
        reports.push({name:shortName+'客诉分析报告_'+y+'年'+mStr+'月', ym:ym, url:url, label:y+'年'+parseInt(mStr)+'月'});
        m++;if(m>12){m=1;y++;}
    }
    if(reports.length===0){section.style.display='none';return;}
    reports.reverse();
    sel.innerHTML=reports.map((r,i)=>'<option value="'+i+'">'+r.label+'</option>').join('');
    window._reportList=reports;
    switchReport('0');
    section.style.display='block';
}

function switchReport(idx){
    idx=parseInt(idx);
    const r=window._reportList&&window._reportList[idx];
    if(!r)return;
    const card=document.getElementById('reportCard');
    const title=document.getElementById('reportTitle');
    const action=document.getElementById('reportAction');
    if(r.url){
        card.href=r.url;card.target='_blank';
        title.textContent=r.name;
        action.textContent='查看→';action.style.color='#2980b9';
    }else{
        card.href='#';card.removeAttribute('target');
        title.textContent=r.name;
        action.textContent='待生成';action.style.color='var(--text-muted)';
    }
}''')
new_js_parts.append('')

# 提取 ESC 监听器
esc_match = re.search(r"(document\.addEventListener\('keydown'.*?\);)", original_js)
if esc_match:
    new_js_parts.append('// 支持ESC关闭')
    new_js_parts.append(esc_match.group(1))
    new_js_parts.append('')

# scrollToTopAndRefresh
new_js_parts.append('''function scrollToTopAndRefresh(){
    document.getElementById('newDataToast').classList.remove('show');
    window.scrollTo({top:0,behavior:'smooth'});
    applyFilters();
}''')
new_js_parts.append('')

# 最后调用 init
new_js_parts.append('checkWechatEnv();')
new_js_parts.append('init();')

new_js = '\n'.join(new_js_parts)

# ── 5. 替换 HTML 中的 script ──
new_html = html[:script_match.start()] + '<script>\n' + new_js + '\n</script>' + html[script_match.end() + len('\n</script>'):]

# 修复：script_match 包括了 <script> 和 </script> 标签的内容
# 重新做替换
new_html = html.replace(
    '<script>\n' + original_js + '\n</script>',
    '<script>\n' + new_js + '\n</script>'
)

# ── 5b. 注入 Open Graph 元数据（微信/社交平台分享卡片） ──
OG_TAGS = '''    <!-- Open Graph 元数据 - 微信/社交平台分享卡片 -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="小红书支付金融舆情洞察">
    <meta property="og:description" content="六大支付平台（微信支付/支付宝/抖音支付/美团支付/云闪付/京东支付）小红书用户舆情实时监测与深度分析">
    <meta property="og:image" content="https://img.icons8.com/color/480/xiaohongshu.png">
    <meta property="og:url" content="https://fintechinsight-wxp.netlify.app/">
    <meta property="og:site_name" content="支付金融舆情洞察">
    <meta property="og:locale" content="zh_CN">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="小红书支付金融舆情洞察">
    <meta name="twitter:description" content="六大支付平台小红书用户舆情实时监测与深度分析">
    <meta name="twitter:image" content="https://img.icons8.com/color/480/xiaohongshu.png">
    <meta name="description" content="六大支付平台（微信支付/支付宝/抖音支付/美团支付/云闪付/京东支付）小红书用户舆情实时监测与深度分析">
'''
if 'og:title' not in new_html:
    new_html = new_html.replace('<title>', OG_TAGS + '    <title>')
    print("✅ 已注入 Open Graph 社交分享元数据")

# ── 6. 输出 ──
out_dir = os.path.join(BASE_DIR, 'netlify-deploy')
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, 'index.html')
with open(out_file, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"\n✅ Netlify 部署版已生成!")
total_embedded = sum(len(ns) for ns in notes_by_platform.values())
print(f"📁 路径: {out_file}")
print(f"📏 文件大小: {len(new_html):,} bytes ({len(new_html)/1024/1024:.2f} MB)")
print(f"📊 内嵌 {total_embedded} 条真实笔记数据（全量）")
print(f"🏷️  覆盖平台: {', '.join(platform_stats.keys())}")
for p, ps in platform_stats.items():
    print(f"   {p}: {ps['total']}条")
print(f"\n👉 将 netlify-deploy/ 文件夹拖到 https://app.netlify.com/drop 即可部署")
