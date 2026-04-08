// 模拟DOM
const elements = {};
const doc = {
    getElementById(id) {
        if (!elements[id]) elements[id] = { 
            innerHTML: '', textContent: '', 
            style: { display: '', cssText: '', background: '' },
            classList: { add(){}, remove(){}, contains(){ return false; } },
            dataset: {},
            value: '',
            querySelectorAll() { return []; },
            getContext() { return { /* canvas context mock */ }; }
        };
        return elements[id];
    },
    querySelectorAll() { return { forEach(){} }; },
    querySelector() { return { classList: { add(){}, remove(){} } }; },
    createElement(t) { return { set textContent(v) { this._t = v; }, get innerHTML() { return this._t || ''; } }; },
    addEventListener() {},
    body: { style: { overflow: '' } },
    hidden: false,
};
global.document = doc;
global.window = { scrollTo(){}, open(){}, location: { href: '' } };
global.navigator = { userAgent: 'test' };
global.Chart = class Chart { constructor(){} destroy(){} };
global.requestAnimationFrame = (fn) => fn();
global.Date = Date;
global.setTimeout = setTimeout;
global.clearTimeout = clearTimeout;

// 读取并执行JS
const fs = require('fs');
const content = fs.readFileSync('/Users/zimyin/CodeBuddy/20260317215615/netlify-deploy/index.html', 'utf8');

// 提取JS
const scriptStart = content.indexOf('<script>\n// ==========');
const scriptEnd = content.indexOf('</script>', scriptStart);
const js = content.substring(scriptStart + 8, scriptEnd);

console.log('JS 代码长度:', js.length);

try {
    eval(js);
    console.log('\n=== init() 执行成功 ===');
    console.log('platformsConfig 平台数:', Object.keys(elements).length, '个DOM元素被访问');
    
    // 模拟点击微信支付
    console.log('\n=== 模拟选择微信支付 ===');
    try {
        // 需要 selectPlatform 函数
        eval('selectPlatform("微信支付", null)');
        console.log('selectPlatform 成功!');
        console.log('notesContainer 内容前200字符:', (elements['notesContainer']?.innerHTML || '').substring(0, 200));
        
        if (elements['notesContainer']?.innerHTML?.includes('loading') || elements['notesContainer']?.innerHTML?.includes('spinner')) {
            console.log('!!! 还在loading !!!');
        } else if (elements['notesContainer']?.innerHTML?.includes('notes-grid')) {
            console.log('✅ notes-grid 渲染成功!');
        } else if (elements['notesContainer']?.innerHTML?.includes('错误')) {
            console.log('!!! 有错误信息 !!!');
        }
    } catch(e) {
        console.error('selectPlatform 失败:', e.message);
        console.error('Stack:', e.stack?.split('\n').slice(0,5).join('\n'));
    }
} catch(e) {
    console.error('JS 执行失败:', e.message);
    console.error('Stack:', e.stack?.split('\n').slice(0,5).join('\n'));
}
