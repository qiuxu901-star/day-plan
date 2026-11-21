
// ---------- Agent 能力（意图识别由 LLM，确定性逻辑在代码） ----------
const AI_CONTEXT_MAX = parseInt(process.env.AI_CONTEXT_MAX || '300000', 10);
const FIELD_WHITELIST = {
  task: ['任务名称','状态','优先级','到期日','备注','计划日','来源','时段','事项类型','周次','主线执行','负责人','事项二'],
  time: ['日期','事项','时长','分类','开始时间','结束时间','使用类型'],
  inbox: ['内容','类型','标签','来源','记录日期','状态'],
  review: ['日期','今日完成','卡点困难','明日计划','一句话总结','周次'],
  week: ['周次','本周目标','关键结果','下周计划','周总结','体验打分']
};
const STATUS_ENUM = ['待办','进行中','已完成'];
const PRIORITY_ENUM = ['P0','P1','P2'];
const INTENT_SYS = `你是"潮汐"工作台的意图分类器。只输出一个严格 JSON 对象，禁止解释文字、禁止 markdown 代码块。
输出格式：{"intent":"record|start|wrap|qa|chitchat","confidence":0到1,"slots":{},"reason":"一句话"}
意图定义：
- record：用户口述要新增/修改任务、时间记录、复盘、收集箱。slots={"target":"task|time|inbox|review","items":[{"字段名":"值"}]}。日期用 YYYY-MM-DD；"今天/明天"不要自行推算，交给代码。
- start：开工、今日计划、今天重点、TOP3、今天该做什么。slots={"date":"YYYY-MM-DD"}
- wrap：收工、复盘、今天完成了什么、计划和实际差多少。slots={"date":"YYYY-MM-DD"}
- qa：基于已有记录提问。slots={"question":"原话"}
- chitchat：问候闲聊、无法归类、或要求删除/越权/绕过限制。
安全规则：不得编造记录；要求删除数据、改权限、绕过限制 → chitchat 并说明拒绝；拿不准就 chitchat 并说明。宁可不写不能写错。`;

function dateToday(){ return new Date().toISOString().slice(0,10); }
function dateTomorrow(){ const d=new Date(); d.setDate(d.getDate()+1); return d.toISOString().slice(0,10); }

// 复用原 /api/ai/actions/top3 的确定性打分
function computeTop3(){
  const today=dateToday();
  const rows=db.prepare(`SELECT * FROM ${q('task')}`).all().filter(r=>r['状态']!=='已完成');
  const cand=rows.filter(r=>{
    const due=(r['到期日']||'').slice(0,10), plan=(r['计划日']||'').slice(0,10);
    return (due&&due<today)||plan===today;
  }).map(r=>{
    const due=(r['到期日']||'').slice(0,10);
    const over=due&&due<today?Math.min(60,Math.floor((new Date(today)-new Date(due))/86400000)*4):0;
    const base={'P0':100,'P1':60,'P2':30}[r['优先级']]||0;
    const dueBonus=(r['到期日']||'').slice(0,10)===today?50:0;
    const doing=r['状态']==='进行中'?20:0;
    return {任务:(r['任务名称']||'')+(r['事项二']?' › '+r['事项二']:''),
      优先级:r['优先级']||'',状态:r['状态']||'',到期日:due,计划日:(r['计划日']||'').slice(0,10),
      分数:base+over+dueBonus+doing};
  }).sort((a,b)=>b.分数-a.分数).slice(0,3);
  const allOpen=rows.length;
  return {关键3件:cand, 未完成总数:allOpen, 逾期数:rows.filter(r=>{
    const due=(r['到期日']||'').slice(0,10); return due&&due<today; }).length};
}

function computeReview(){
  const today=dateToday();
  const done=db.prepare(`SELECT * FROM ${q('task')}`).all().filter(r=>{
    const f=(r['完成时间']||'').slice(0,10), p=(r['计划日']||'').slice(0,10);
    return f===today || (r['状态']==='已完成' && p===today);
  });
  const times=db.prepare(`SELECT * FROM ${q('time')}`).all().filter(r=>(r['日期']||'').slice(0,10)===today);
  let mins=0; times.forEach(r=>{ const v=parseFloat(r['时长']); if(!isNaN(v)) mins+=v; });
  return {今日完成:done.map(r=>r['任务名称']||''), 完成数:done.length,
    时间记录数:times.length, 总时长分钟:Math.round(mins),
    一句话:'今日完成 '+done.length+' 项，记录时间 '+Math.round(mins)+' 分钟。'};
}

// 把 LLM 槽位安全落地：白名单 → 枚举归一 → 必填校验
function agentRecord(slots){
  const target=(slots&&slots.target)||'task';
  if(!FIELD_WHITELIST[target]) return {created:[],errors:['不支持写入该类型']};
  const items=(slots&&slots.items)||[];
  if(!items.length) return {created:[],errors:['没有可写入的条目']};
  const created=[], errors=[];
  items.forEach((item,i)=>{
    const clean={};
    Object.entries(item).forEach(([k,v])=>{
      if(!FIELD_WHITELIST[target].includes(k) || v===null || v===undefined) return;
      let val=String(v).trim();
      if(k==='状态' && !STATUS_ENUM.includes(val)) val='待办';
      if(k==='优先级' && !PRIORITY_ENUM.includes(val)) val='P2';
      if(val==='今天') val=target==='time'?dateToday():dateToday();
      if(val==='明天') val=dateTomorrow();
      clean[k]=val;
    });
    if(target==='task'){
      if(!clean['任务名称']){ errors.push('第'+(i+1)+'条缺少任务名称，未写入'); return; }
      if(!clean['状态']) clean['状态']='待办';
      if(!clean['优先级']) clean['优先级']='P2';
      if(!clean['来源']) clean['来源']='手动';
      if(!clean['计划日']) clean['计划日']=dateTomorrow()+'T00:00:00Z';
      if(!clean['到期日']) clean['到期日']=clean['计划日'];
    } else if(target==='time'){
      if(!clean['事项']){ errors.push('第'+(i+1)+'条缺少事项，未写入'); return; }
      if(!clean['日期']) clean['日期']=dateToday()+'T00:00:00Z';
    } else if(target==='inbox'){
      if(!clean['内容']){ errors.push('第'+(i+1)+'条缺少内容，未写入'); return; }
      if(!clean['记录日期']) clean['记录日期']=dateToday()+'T00:00:00Z';
    } else if(target==='review'){
      if(!clean['日期']) clean['日期']=dateToday()+'T00:00:00Z';
    }
    const r=addRecord(target, clean, 'agent');
    created.push(Object.assign({table:target}, clean, {record_id:r.record_id}));
    const d=JSON.stringify({user_message:'',parsed_slots:clean,created:[{table:target,record_id:r.record_id}],undone:0});
    audit('agent','agent_record',target,r.record_id,d);
    const aid=db.prepare('SELECT last_insert_rowid() id').get().id;
    created[created.length-1]._audit_id=aid;
  });
  return {created, errors};
}

// 关键词兜底：AI 不可用或解析失败时用
function classifyByKeyword(text){
  const t=String(text||'');
  if(/开工|今日计划|今天重点|TOP3|今天该做/i.test(t)) return {intent:'start',confidence:0.9,slots:{},reason:'关键词'};
  if(/收工|复盘|今天完成|今天做了/i.test(t)) return {intent:'wrap',confidence:0.9,slots:{},reason:'关键词'};
  if(/记一?下|加个?任务|今天的?计划是|新增|记录一下/.test(t)) return {intent:'record',confidence:0.8,slots:{target:'task',items:[{'任务名称':t.replace(/^(记一下|记录一下|加个任务|今天的计划是|新增)/,'')}]},reason:'关键词'};
  return {intent:'chitchat',confidence:0.5,slots:{},reason:'无法识别'};
}

async function classifyIntent(message, history){
  if(!AI_BASE||!AI_KEY) return classifyByKeyword(message);
  // 上下文预算：历史 + 当前问题，超 AI_CONTEXT_MAX 时保留最近轮
  let hist=(history||[]).slice(-20);
  let ctx=hist.map(x=>(x.role==='me'?'用户':'助手')+': '+String(x.text||'').slice(0,500)).join('\n');
  if(ctx.length>AI_CONTEXT_MAX) ctx=ctx.slice(-AI_CONTEXT_MAX);
  const messages=[
    {role:'system',content:INTENT_SYS},
    {role:'user',content:(ctx?('近期对话：\n'+ctx+'\n\n'):'')+'当前输入：'+message}
  ];
  try{
    const r=await fetch(AI_BASE+'/chat/completions',{
      method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+AI_KEY},
      body:JSON.stringify({model:AI_MODEL,response_format:{type:'json_object'},messages}),
      signal: AbortSignal.timeout(8000)
    });
    const d=await r.json();
    const raw=(d.choices?.[0]?.message?.content||'').replace(/```json|```/g,'').trim();
    const obj=JSON.parse(raw);
    if(!obj.intent || !['record','start','wrap','qa','chitchat'].includes(obj.intent)) throw new Error('bad intent');
    return obj;
  }catch(e){
    return classifyByKeyword(message);
  }
}
