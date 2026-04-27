// 模拟DOM - 不加载Chart
const els = {};
global.document = {
    getElementById(id) {
        if(!els[id]) els[id] = { innerHTML:'',textContent:'',style:{display:'',cssText:'',background:''},classList:{add(){},remove(){},contains(){return false}},dataset:{},value:'',getContext(){return{}} };
        return els[id];
    },
    querySelectorAll(){return{forEach(){}}},
    querySelector(){return{classList:{add(){},remove(){}}}},
    createElement(){return{set textContent(v){this._t=v},get innerHTML(){return this._t||''}}},
    addEventListener(){},
    body:{style:{overflow:''}},
    hidden:false
};
global.window={scrollTo(){},open(){},location:{href:''},_chartReady:false};
global.navigator={userAgent:'test'};
// 不定义 Chart！模拟 CDN 未加载
global.requestAnimationFrame=fn=>fn();
global.setTimeout=setTimeout;
global.clearTimeout=clearTimeout;

const fs=require('fs');
const c=fs.readFileSync('static_index.html','utf8');
const s1=c.indexOf('<script>\n// ==========');
const s2=c.indexOf('</script>',s1);
const js=c.substring(s1+8,s2);

try{
    eval(js);
    console.log('init成功(无Chart.js)');
    eval('selectPlatform("微信支付",null)');
    console.log('selectPlatform成功');
    const html=els['notesContainer']?.innerHTML||'';
    if(html.includes('notes-grid')) console.log('✅ 笔记渲染成功, 长度:', html.length);
    else if(html.includes('loading')) console.log('❌ 还在loading');
    else if(html.includes('错误')) console.log('❌ 错误:', html.substring(0,200));
    else console.log('内容:', html.substring(0,100));
    
    // 检查keywordGroups
    const kw=els['keywordGroups']?.innerHTML||'';
    if(kw.includes('keyword-tag')) console.log('✅ 关键词渲染成功, 长度:', kw.length);
    else console.log('❌ 关键词为空:', kw.substring(0,100));
    
    // 检查resultsCount
    console.log('结果数:', els['resultsCount']?.textContent);
}catch(e){
    console.error('执行失败:', e.message);
    console.error(e.stack?.split('\n').slice(0,5).join('\n'));
}
