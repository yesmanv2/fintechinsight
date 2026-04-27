// 模拟浏览器环境
const document = { createElement: (t) => ({ set textContent(v) { this._t = v; }, get innerHTML() { return this._t || ''; }}) };

function esc(t) { return t || ''; }
function fmtNum(n) { const v = parseInt(n) || 0; return v.toString(); }
function getTimeAgo(t) { return '1天前'; }

function renderCard(note, catsCfg) {
    const cats=(note.categories||[]).map(cat=>{const cfg=catsCfg[cat]||{};return`<span class="category-tag" style="background:${cfg.color||'#6366f1'}20;color:${cfg.color||'#6366f1'}">${cfg.icon||'📌'} ${cat}</span>`}).join('');
    const sentMap={positive:'😊 正面',negative:'😡 负面',neutral:'😐 中性'};
    const s=note.sentiment||'neutral';
    const fc=catsCfg[(note.categories||[])[0]]?.color||'#6366f1';
    const isDel=note.is_deleted;
    const ta=getTimeAgo(note.time);
    const kwTags=(note.keyword_tags||[]).slice(0,5).map(t=>`<span class="note-kw-tag">${esc(t)}</span>`).join('');
    const noteData=encodeURIComponent(JSON.stringify(note));
    const deletedBadge=isDel?'<span class="deleted-badge"><span class="icon">🗑️</span>原帖已删</span>':'';
    const cardClass=`note-card ${isDel?'is-deleted':''}`;
    const displayTitle = note.title || note.search_keyword || (note.keyword_tags && note.keyword_tags[0]) || '无标题';
    const displayDesc = note.desc || '';
    const kwHtml=kwTags?'<div class="note-kw-tags">'+kwTags+'</div>':'';
    return`<div class="${cardClass}" onclick="openNoteDetail(this)" data-note="${noteData}"><div class="note-top-bar" style="background:${fc}"></div>${deletedBadge}<div class="note-header"><div class="note-categories">${cats}</div><span class="sentiment-tag ${s}">${sentMap[s]}</span></div><div class="note-title">${esc(displayTitle)}</div>${displayDesc?'<div class="note-desc">'+esc(displayDesc)+'</div>':''}${kwHtml}<div class="note-footer"><div class="note-author"><span class="author-avatar">${(note.author||'?')[0]}</span>${esc(note.author)}</div><div class="note-stats"><span>❤️ ${fmtNum(note.liked_count)}</span><span>💬 ${fmtNum(note.comment_count)}</span><span>⭐ ${fmtNum(note.collected_count)}</span></div></div><div class="note-time">📅 ${note.time||'未知'}${ta?` <span class="time-ago">· ${ta}</span>`:''}</div></div>`;
}

// 测试数据
const testNote = {
    title: "测试标题",
    desc: "测试描述 包含\"引号\"和'单引号'",
    author: "测试作者",
    categories: ["支付", "其他"],
    sentiment: "positive",
    time: "2026-03-16 17:35",
    liked_count: 100,
    comment_count: 50,
    collected_count: 30,
    keyword_tags: ["微信", "支付"],
    link: "https://example.com",
    note_id: "abc123"
};

const catsCfg = {
    "支付": { color: "#6366f1", icon: "💳" },
    "其他": { color: "#64748b", icon: "📌" }
};

try {
    const result = renderCard(testNote, catsCfg);
    console.log("renderCard 成功！长度:", result.length);
} catch(e) {
    console.error("renderCard 失败:", e.message);
}

// 测试有特殊字符的数据
const testNote2 = {
    title: '包含"双引号"和反引号`的标题',
    desc: "",
    author: "作者",
    categories: ["支付"],
    sentiment: "negative",
    time: "2026-01-01 00:00",
    liked_count: 0,
    keyword_tags: [],
};

try {
    const result2 = renderCard(testNote2, catsCfg);
    console.log("renderCard2 成功！长度:", result2.length);
} catch(e) {
    console.error("renderCard2 失败:", e.message);
}

// 测试含有data-note属性中有特殊字符
console.log("\n检测 noteData 中的引号问题...");
const noteWithQuotes = {
    title: 'He said "hello"',
    desc: "It's a test",
    author: "A&B",
    categories: ["支付"],
    sentiment: "neutral",
    time: "2025-06-01",
    liked_count: 5,
};
try {
    const result3 = renderCard(noteWithQuotes, catsCfg);
    // 检查 data-note 属性中是否有未转义的引号
    if (result3.includes('data-note="')) {
        const start = result3.indexOf('data-note="') + 11;
        const end = result3.indexOf('"', start + 1);
        // 如果 end 在一个很短的位置就说明引号被截断了
        console.log("data-note 属性值前50字符:", result3.substring(start, start+50));
    }
    console.log("renderCard3 成功！长度:", result3.length);
} catch(e) {
    console.error("renderCard3 失败:", e.message);
}
