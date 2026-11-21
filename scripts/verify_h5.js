// 用 jsdom 回放 workboard.html，注入本地 API 的真实数据，验证渲染与登录逻辑。
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('/Users/qiuxu/.workbuddy/binaries/node/workspace/node_modules/jsdom');

const HTML = path.join(__dirname, '..', 'web', 'workboard.html');
const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push('jsdomError: ' + e.message));
vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));

let html = fs.readFileSync(HTML, 'utf8');

// 去掉 type=module 之类无谓资源；本页无外链
const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  url: 'http://localhost/workboard/',
  virtualConsole: vc,
  beforeParse(window) {
    // mock fetch：返回本地 API 的同构响应
    const TOKEN = 'fake-token';
    window.localStorage.setItem('wb_token', TOKEN);
    const taskRow = {
      '任务名称': '【回放验证】测试任务', '状态': '待办', '优先级': 'P1',
      '计划日': '2026-11-21T00:00:00Z', '到期日': '2026-11-21T00:00:00Z',
      record_id: 'replay-001'
    };
    const meta = {
      task: { label: '任务表', properties: [
        {name:'任务名称',type:'text'}, {name:'状态',type:'select',config:{options:[
          {id:'a',text:'待办',style:18},{id:'b',text:'进行中',style:20},{id:'c',text:'已完成',style:26}]}},
        {name:'优先级',type:'select',config:{options:[
          {id:'d',text:'P0',style:14},{id:'e',text:'P1',style:2},{id:'f',text:'P2',style:16}]}},
        {name:'计划日',type:'date'}, {name:'到期日',type:'date'}
      ]},
      review:{label:'复盘表',properties:[]}, milestone:{label:'阶段表',properties:[]},
      time:{label:'时间表',properties:[]}, week:{label:'周计划表',properties:[]},
      log:{label:'留痕表',properties:[]}, inbox:{label:'收集箱',properties:[]},
      subtask:{label:'子任务表',properties:[]}
    };
    window.fetch = function(url, opts) {
      opts = opts || {};
      let body = {};
      if (url.includes('/healthz')) body = {status:'ok', counts:{task:1}, ai_enabled:false};
      else if (url.includes('/meta/tables')) body = meta;
      else if (url.includes('/v1/task?')) body = {items:[taskRow], total:1, page:1, size:200, has_more:false, next_page:null};
      else if (/^\/workboard\/api\/v1\/\w+\?/.test(url)) body = {items:[], total:0, page:1, size:200, has_more:false, next_page:null};
      else if (url.includes('/api/keys')) body = url.includes('method') ? {id:'k_test',key:'wb_fake',scope:'read'} : [{id:'k_test',scope:'read',note:'测试',revoked:0,created_at:'2026-11-21'}];
      else if (url.includes('/api/skills')) body = [{id:'s_test',name:'测试技能',description:'_desc',content:'_content',updated_at:'2026-11-21'}];
      else if (url.includes('/api/agent/chat')) body = {ok:true,intent:'start',reply:'当前最重要的3件事',data:{top3:[{任务:'测试',优先级:'P1',分数:140}]},audit_ids:[],undoable:false};
      else body = {record_id:'new-1'};
      return Promise.resolve({ok:true, status:200, json:()=>Promise.resolve(body)});
    };
    // 精简版 alert/toast 静默
    window.alert = () => {};
  }
});

setTimeout(() => {
  const d = dom.window.document;
  const checks = [];
  checks.push(['登录框不阻塞(已有token)', !d.getElementById('wbLogin')]);
  checks.push(['页面标题存在', /工作计划台|今天，慢慢来/.test(d.body.textContent)]);
  checks.push(['侧边栏/导航渲染', !!d.querySelector('[data-view], .nav, .side, nav') || d.body.textContent.length > 500]);
  const bodyLen = d.body.textContent.replace(/\s+/g,'').length;
  checks.push(['DOM有实际内容('+bodyLen+'字)', bodyLen > 200]);
  checks.push(['无JS运行时错误', errors.length === 0]);
  checks.push(['APP Key 页面存在', !!d.getElementById('view-keys')]);
  checks.push(['AI生成Key页面已回退', !d.getElementById('view-aikey')]);
  checks.push(['技能管理页面存在', !!d.getElementById('view-skills')]);
  checks.push(['Agent对话区存在', !!d.getElementById('agentDock')]);
  checks.push(['鲸鱼SVG存在', !!d.querySelector('.wb-whale')]);
  checks.push(['快捷指令4个', d.querySelectorAll('#agentQuick button').length===4]);
  checks.push(['对话输入框存在', !!d.getElementById('agentInput')]);
  checks.push(['Agent为默认active页', !!d.querySelector('#view-agent.active')]);
  checks.push(['无ID选择器劫持视图', !/\.view#view-[a-z]+\s*\{[^}]*display\s*:/.test(html)]);
  checks.push(['仅一个active视图', d.querySelectorAll('.view.active').length===1]);
  checks.push(['新导航按钮存在', d.querySelectorAll('[data-view="keys"]').length>=2]);

  let pass = 0;
  console.log('\n=== H5 回放验证 ===');
  for (const [name, ok] of checks) {
    console.log((ok?'PASS':'FAIL') + '  ' + name);
    if (ok) pass++;
  }
  if (errors.length) console.log('\n错误:', errors.slice(0,5));
  console.log('\n结果: ' + pass + '/' + checks.length);
  process.exit(pass === checks.length ? 0 : 1);
}, 2500);
