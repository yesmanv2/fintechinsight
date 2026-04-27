"""
构建纯静态版 HTML - 数据精简后放外部 data.json，HTML 异步加载
从源 index.html 提取所有 JS 函数，只替换数据加载方式
"""
import json, os, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== 1. 读取原始数据并精简 ==========
f = 'real_data.json' if os.path.exists(os.path.join(BASE_DIR, 'real_data.json')) else 'data.json'
with open(os.path.join(BASE_DIR, f), 'r', encoding='utf-8') as fp:
    data = json.load(fp)

meta = data.get('meta', {})
notes = data.get('notes', [])
platforms_config = meta.get('platforms_config', {})
platform_stats = meta.get('platform_stats', {})

# 按平台分组
notes_by_platform = {}
for note in notes:
    p = note.get('platform', '支付宝')
    if p not in notes_by_platform:
        notes_by_platform[p] = []
    notes_by_platform[p].append(note)

# 精简笔记数据 - 短键名
compact_nbp = {}
for p, pnotes in notes_by_platform.items():
    compact_notes = []
    for n in pnotes:
        cn = {
            't': n.get('title', '') or '',
            'a': n.get('author', '') or '',
            'l': int(n.get('liked_count', 0) or 0),
            'm': int(n.get('comment_count', 0) or 0),
            'o': int(n.get('collected_count', 0) or 0),
            'i': n.get('note_id', ''),
            'T': n.get('time', '') or '',
            'c': n.get('categories', []),
        }
        s = n.get('sentiment', 'neutral')
        cn['s'] = 'p' if s == 'positive' else ('n' if s == 'negative' else 'u')
        kw = n.get('keyword_tags', [])
        if kw: cn['k'] = kw
        desc = n.get('desc', '')
        if desc: cn['d'] = desc
        sk = n.get('search_keyword', '')
        if sk: cn['sk'] = sk
        if n.get('is_deleted'):
            cn['D'] = 1
            if n.get('deleted_at'): cn['da'] = n['deleted_at']
            if n.get('snapshot_time'): cn['st'] = n['snapshot_time']
        compact_notes.append(cn)
    compact_nbp[p] = compact_notes

compact_data = {
    "platforms_config": platforms_config,
    "platform_stats": platform_stats,
    "notes_by_platform": compact_nbp,
}
compact_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
data_json_path = os.path.join(BASE_DIR, 'netlify-deploy', 'data.json')
with open(data_json_path, 'w', encoding='utf-8') as fp:
    fp.write(compact_json)
print(f"✅ data.json 大小: {len(compact_json)//1024} KB ({len(compact_json)/1024/1024:.2f} MB)")

# ========== 2. 读取源 HTML ==========
with open(os.path.join(BASE_DIR, 'index.html'), 'r', encoding='utf-8') as fp:
    html = fp.read()

# 找到主 script 标签（包含 EMBEDDED_DATA 或 init() 的那个）
embedded_pos = html.find('EMBEDDED_DATA')
if embedded_pos == -1:
    script_start = html.rfind('<script>\n')
else:
    script_start = html.rfind('<script>\n', 0, embedded_pos)
script_end = html.find('</script>', script_start) + len('</script>')

# 提取原始 script 内容
original_script = html[script_start + len('<script>\n'):script_end - len('</script>')]

# ========== 3. 从原始 script 中提取辅助函数 ==========
# 删除 EMBEDDED_DATA 行（巨大的内嵌数据）
lines = original_script.split('\n')
clean_lines = []
skip = False
for line in lines:
    # 跳过 EMBEDDED_DATA 赋值行（可能跨多行直到 ;）
    if 'const EMBEDDED_DATA' in line or 'var EMBEDDED_DATA' in line or 'let EMBEDDED_DATA' in line:
        skip = True
    if skip:
        if line.rstrip().endswith(';'):
            skip = False
        continue
    # 跳过 init(); 调用（我们会在loadData后调用）
    stripped = line.strip()
    if stripped == 'init();':
        continue
    # 跳过 checkWechatEnv(); 调用（我们会在loadData后调用）
    if stripped == 'checkWechatEnv();':
        continue
    clean_lines.append(line)

original_functions = '\n'.join(clean_lines)

# ========== 4. 构建数据解码器和异步加载器 ==========
data_loader = '''
// ========== 纯静态版v4 - 外部数据加载 ==========
let EMBEDDED_DATA = null;

// 短键名解码：将精简数据还原为完整对象
function expandNote(n) {
    const sentMap = {p:'positive', n:'negative', u:'neutral'};
    return {
        title: n.t || '',
        desc: n.d || '',
        author: n.a || '',
        liked_count: String(n.l || 0),
        comment_count: String(n.m || 0),
        collected_count: String(n.o || 0),
        note_id: n.i || '',
        link: n.i ? 'https://www.xiaohongshu.com/explore/' + n.i : '',
        time: n.T || '',
        categories: n.c || [],
        keyword_tags: n.k || [],
        search_keyword: n.sk || '',
        sentiment: sentMap[n.s] || 'neutral',
        is_deleted: !!n.D,
        deleted_at: n.da || '',
        snapshot_time: n.st || '',
    };
}

// 异步加载数据
async function loadData() {
    try {
        const nc = document.getElementById('notesContainer');
        if (nc) nc.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在加载数据...</span></div>';
        const resp = await fetch('data.json?v=' + Date.now());
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        EMBEDDED_DATA = await resp.json();
        // 展开所有笔记的短键名
        for (const [p, notes] of Object.entries(EMBEDDED_DATA.notes_by_platform)) {
            EMBEDDED_DATA.notes_by_platform[p] = notes.map(expandNote);
        }
        init();
        if (typeof checkWechatEnv === 'function') checkWechatEnv();
    } catch(e) {
        console.error('数据加载失败:', e);
        const nc = document.getElementById('notesContainer');
        if (nc) nc.innerHTML = '<div style="color:red;padding:40px;text-align:center"><div style="font-size:24px;margin-bottom:12px">⚠️</div>数据加载失败: ' + e.message + '<br><br><button onclick="loadData()" style="padding:8px 24px;border-radius:8px;border:1px solid #e2e4e9;cursor:pointer">重试</button></div>';
    }
}
'''

# ========== 5. 确保 logo 正确 ==========
# 检查原始脚本中的 logo，确保微信支付和抖音支付 logo 正确
CORRECT_WECHAT_LOGO = '`<svg viewBox="38 12 44 38" width="1em" height="1em"><path d="M54.7867 35.6905C54.6142 35.7776 54.4195 35.8281 54.2128 35.8281C53.735 35.8281 53.3191 35.5646 53.1008 35.1759L53.0175 34.9927L49.5359 27.3531C49.4984 27.2702 49.4749 27.1763 49.4749 27.0847C49.4749 26.7324 49.7604 26.4471 50.1125 26.4471C50.2555 26.4471 50.3874 26.4941 50.494 26.5739L54.6018 29.4988C54.9024 29.6951 55.2607 29.8102 55.6465 29.8102C55.8769 29.8102 56.0959 29.7676 56.3007 29.6929L75.6211 21.0937C72.1581 17.012 66.4546 14.3447 60.0001 14.3447C49.438 14.3447 40.8765 21.4795 40.8765 30.2814C40.8765 35.0835 43.4523 39.4062 47.4839 42.3275C47.8078 42.5585 48.0194 42.9376 48.0194 43.366C48.0194 43.5074 47.9893 43.6373 47.9524 43.7721C47.6302 44.9734 47.1149 46.8967 47.0902 46.9868C47.0505 47.1373 46.9876 47.2946 46.9876 47.453C46.9876 47.8046 47.2732 48.0902 47.6253 48.0902C47.7637 48.0902 47.8765 48.0389 47.9935 47.9715L52.1802 45.5544C52.4952 45.3725 52.8286 45.2602 53.1956 45.2602C53.3912 45.2602 53.5801 45.2901 53.7577 45.3444C55.7109 45.9061 57.818 46.2183 60.0001 46.2183C70.5617 46.2183 79.1236 39.0831 79.1236 30.2814C79.1236 27.6155 78.3342 25.1046 76.9457 22.8966L54.9262 35.61L54.7867 35.6905Z" fill="#14AB39"/></svg>`'

CORRECT_DOUYIN_LOGO = '`<svg viewBox="0 0 48 48" width="1em" height="1em"><rect x="0" y="0" width="48" height="48" rx="10" fill="#000"/><g transform="translate(14,7)"><path d="M13 2c0-1 0-2 0-2h-3v20c0 2.8-2.2 5-5 5s-5-2.2-5-5 2.2-5 5-5c.5 0 1 .1 1.5.2V12c-.5-.1-1-.1-1.5-.1C2.2 11.9 0 14.6 0 18s2.5 6.5 5.5 6.5S11 21.2 11 18V9.5c1.5 1.3 3.5 2 5.5 2V8.5c-2.5 0-3.5-3-3.5-6.5z" fill="#fff"/><path d="M10.5 2c-.3 1.2-1.2 2.5-2.5 3.2 1.2.8 2.8 1.4 4.5 1.5V3.8C11.8 3.5 11 3 10.5 2z" fill="#25F4EE" opacity=".6"/><path d="M5 15c-2.8 0-5 2.2-5 5s2.2 5 5 5c.3 0 .5 0 .8 0-2-.5-3.3-2.4-3.3-4.5 0-2.8 2.2-5 5-5 .5 0 1 .1 1.5.2V13.5c-.5-.1-1-.2-1.5-.2-.8 0-1.7.2-2.5.5z" fill="#FE2C55" opacity=".6"/></g></svg>`'

# 验证 logo
if 'viewBox="38 12 44 38"' not in original_functions:
    print("⚠️ 警告: 微信支付logo可能需要修复!")
if '#25F4EE' not in original_functions:
    print("⚠️ 警告: 抖音支付logo可能需要修复!")

# ========== 6. 组装新的 script ==========
new_script_content = data_loader + '\n' + original_functions + '\n\n// 启动加载\nloadData();\n'
new_script = '<script>\n' + new_script_content + '</script>'

# 替换 script
new_html = html[:script_start] + new_script + html[script_end:]

# Chart.js 改为非阻塞
new_html = new_html.replace(
    '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>',
    '<script>window._chartReady=false;</script>\n    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js" async onload="window._chartReady=true;if(typeof rebuildChartsIfNeeded===\'function\')rebuildChartsIfNeeded();" onerror="console.warn(\'Chart.js加载失败，图表不可用\')"></script>'
)

# 写出
out_file = os.path.join(BASE_DIR, 'netlify-deploy', 'index.html')
with open(out_file, 'w', encoding='utf-8') as fp:
    fp.write(new_html)

print(f"\n✅ 静态版已生成: netlify-deploy/index.html")
print(f"   HTML 大小: {len(new_html)//1024} KB ({len(new_html)/1024/1024:.2f} MB)")
print(f"   data.json: {len(compact_json)//1024} KB ({len(compact_json)/1024/1024:.2f} MB)")
print(f"   总计: {(len(new_html)+len(compact_json))//1024} KB")

# 验证 logo
if 'viewBox="38 12 44 38"' in new_html and 'fill="#14AB39"' in new_html:
    print("✅ 微信支付logo正确 (绿色气泡)")
else:
    print("❌ 微信支付logo可能有问题!")

if '#25F4EE' in new_html and '#FE2C55' in new_html and 'translate(14,7)' in new_html:
    print("✅ 抖音支付logo正确 (黑底+彩色点缀)")
else:
    print("❌ 抖音支付logo可能有问题!")
