#!/usr/bin/env node
/* WorkBoard API —— Node 22 单文件后端（零 npm 依赖，内置 node:sqlite）
 * 适配服务器 Python 3.6 无法跑 FastAPI 的现实；功能与 Python 版一致。
 */
'use strict';
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { DatabaseSync } = require('node:sqlite');

const ROOT = __dirname;
const DB_PATH = process.env.WB_DB_PATH || path.join(ROOT, 'data', 'workboard.db');
const JWT_SECRET = process.env.WB_JWT_SECRET || 'dev-only-change-me';
const ADMIN_PASSWORD = process.env.WB_ADMIN_PASSWORD || 'workboard';
const ADMIN_HASH = process.env.WB_ADMIN_PASSWORD_HASH || '';
const JWT_TTL_H = parseInt(process.env.WB_JWT_TTL_HOURS || '168', 10);
const RATE_LIMIT = parseInt(process.env.WB_RATE_LIMIT || '300', 10);
const PORT = parseInt(process.env.WB_PORT || '8100', 10);
const HOST = process.env.WB_HOST || '127.0.0.1';

const TABLES = ['task','review','milestone','time','week','log','inbox','subtask'];
const LABELS = {task:'任务表',review:'复盘表',milestone:'阶段表',time:'时间表',
  week:'周计划表',log:'留痕表',inbox:'收集箱',subtask:'子任务表'};
const META_COLS = new Set(['record_id','_created_at','_updated_at','_origin',
  '_sync_status','_content_hash','_placeholder']);

const db = new DatabaseSync(DB_PATH);
db.exec('PRAGMA journal_mode=WAL');

function now(){ return new Date().toISOString().replace(/\.\d{3}Z$/,'Z'); }
function q(n){ return '"' + String(n).replace(/"/g,'""') + '"'; }
function cols(table){
  return db.prepare(`PRAGMA table_info(${q(table)})`).all().map(r=>r.name);
}
function sha(s){ return crypto.createHash('sha256').update(s).digest('hex'); }

// ---------- JWT (HS256, 内置 crypto) ----------
function b64url(buf){ return Buffer.from(buf).toString('base64url'); }
function signJWT(){
  const header = b64url(JSON.stringify({alg:'HS256',typ:'JWT'}));
  const payload = b64url(JSON.stringify({sub:'admin',
    exp: Math.floor(Date.now()/1000)+JWT_TTL_H*3600,
    iat: Math.floor(Date.now()/1000)}));
  const sig = b64url(crypto.createHmac('sha256',JWT_SECRET)
    .update(header+'.'+payload).digest());
  return header+'.'+payload+'.'+sig;
}
function verifyJWT(token){
  try{
    const [h,p,s] = token.split('.');
    const expect = b64url(crypto.createHmac('sha256',JWT_SECRET).update(h+'.'+p).digest());
    if (s !== expect) return false;
    const payload = JSON.parse(Buffer.from(p,'base64url').toString());
    return payload.sub === 'admin' && payload.exp > Date.now()/1000;
  }catch(e){ return false; }
}
function checkPwd(pwd){
  if (ADMIN_HASH){
    const [salt, hex] = ADMIN_HASH.replace(/^pbkdf2\$/,'').split('$');
    const calc = crypto.pbkdf2Sync(pwd, Buffer.from(salt,'hex'), 200000, 32, 'sha256').toString('hex');
    return calc === hex;
  }
  return pwd === ADMIN_PASSWORD;
}

// ---------- 响应工具 ----------
function json(res, code, data){
  res.writeHead(code, {'Content-Type':'application/json; charset=utf-8',
    'Access-Control-Allow-Origin':'*',
    'Access-Control-Allow-Headers':'Content-Type, Authorization, X-API-Key',
    'Access-Control-Allow-Methods':'GET,POST,PATCH,DELETE,OPTIONS'});
  res.end(JSON.stringify(data));
}
function readBody(req){
  return new Promise((resolve,reject)=>{
    let buf='';
    req.on('data',c=>{ buf+=c; if(buf.length>5e6) req.destroy(); });
    req.on('end',()=>{ try{ resolve(buf?JSON.parse(buf):{}); }catch(e){ reject(e); } });
    req.on('error',reject);
  });
}
function auth(req){
  const m = (req.headers.authorization||'').match(/^Bearer\s+(.+)$/i);
  return m && verifyJWT(m[1]);
}
function apiKeyScope(req){
  const k = req.headers['x-api-key'];
  if (!k) return null;
  const row = db.prepare('SELECT scope,revoked FROM api_key WHERE key_hash=?').get(sha(k));
  return row && !row.revoked ? row.scope : null;
}
function audit(actor, action, table, rid, detail){
  db.prepare('INSERT INTO audit_log (ts,actor,action,table_name,record_id,detail) VALUES (?,?,?,?,?,?)')
    .run(now(), actor, action, table, rid, detail||'');
}
function enqueue(table, rid, op, payload){
  db.prepare('INSERT INTO sync_queue (ts,table_name,record_id,op,payload,status) VALUES (?,?,?,?,?,\'pending\')')
    .run(now(), table, rid, op, JSON.stringify(payload));
}
function bizHash(biz){
  return sha(JSON.stringify(Object.fromEntries(Object.entries(biz).sort())));
}

// ---------- CRUD ----------
function listRecords(table, opt){
  const c = cols(table);
  const where = [], params = [];
  Object.entries(opt.filters||{}).forEach(([k,v])=>{
    if (!c.includes(k)) return;
    if (v && typeof v==='object' && v.op){
      const ops = {eq:'=',ne:'!=',gt:'>',lt:'<',gte:'>=',lte:'<=',contains:'LIKE'};
      if (!ops[v.op]) return;
      where.push(`${q(k)} ${ops[v.op]} ?`);
      params.push(v.op==='contains'?`%${v.value}%`:v.value);
    } else { where.push(`${q(k)} = ?`); params.push(v); }
  });
  const wsql = where.length ? ' WHERE '+where.join(' AND ') : '';
  let orderSql = '';
  if (opt.sort && c.includes(opt.sort))
    orderSql = ` ORDER BY ${q(opt.sort)} ${String(opt.order||'desc').toUpperCase()}`;
  const total = db.prepare(`SELECT count(*) n FROM ${q(table)}${wsql}`).get(...params).n;
  const offset = Math.max(0,(opt.page-1)*opt.size);
  const rows = db.prepare(`SELECT * FROM ${q(table)}${wsql}${orderSql} LIMIT ? OFFSET ?`)
    .all(...params, opt.size, offset);
  const fields = c.filter(x=>!META_COLS.has(x));
  const items = rows.map(r=>{
    const o={}; fields.forEach(f=>o[f]=r[f]);
    o.record_id=r['record_id'];
    // 前端 UI 写操作（更新/删除/改状态）统一用 _id；平台时代是 _id，自托管后只有 record_id。
    // 这里同时输出 _id，兼容前端，避免 PATCH /api/v1/task/undefined。
    o._id=r['record_id'];
    return o;
  });
  return {items,total,page:opt.page,size:opt.size,
    has_more: offset+rows.length<total,
    next_page: offset+rows.length<total ? opt.page+1 : null};
}
function addRecord(table, payload, actor, enqueueSync=true){
  const c = cols(table);
  const biz = {};
  Object.entries(payload).forEach(([k,v])=>{
    if (c.includes(k) && !META_COLS.has(k) && v!==null && v!==undefined) biz[k]=unwrapOneof(v);
  });
  const rid = payload.record_id || crypto.createHash('sha1')
    .update(JSON.stringify(payload)+now()).digest('hex');
  const keys=[...Object.keys(biz),'record_id','_created_at','_updated_at','_origin','_sync_status','_content_hash'];
  const vals=[...Object.values(biz),rid,now(),now(),'local',enqueueSync?'pending':'synced',bizHash(biz)];
  db.prepare(`INSERT OR REPLACE INTO ${q(table)} (${keys.map(q).join(',')}) VALUES (${keys.map(()=>'?').join(',')})`).run(...vals);
  audit(actor,'add',table,rid);
  if (enqueueSync) enqueue(table,rid,'add',biz);
  return {record_id:rid};
}
// 兼容平台 oneof 格式：{text/select/date/number} → 裸值
function unwrapOneof(v){
  if(v && typeof v==='object' && !Array.isArray(v)){
    if(v.text!==undefined) return v.text;
    if(v.select!==undefined) return v.select;
    if(v.date!==undefined) return v.date;
    if(v.number!==undefined) return v.number;
  }
  return v;
}
function updateRecord(table, rid, payload, actor, enqueueSync=true){
  const existing = db.prepare(`SELECT * FROM ${q(table)} WHERE record_id=?`).get(rid);
  if (!existing) return null;
  const c = cols(table);
  const biz = {};
  Object.entries(payload).forEach(([k,v])=>{
    if (c.includes(k) && !META_COLS.has(k) && v!==null && v!==undefined) biz[k]=unwrapOneof(v);
  });
  if (Object.keys(biz).length){
    const sets=Object.keys(biz).map(k=>`${q(k)}=?`).join(',');
    const merged={...existing,...biz};
    const cleanBiz={}; Object.keys(biz).forEach(k=>cleanBiz[k]=merged[k]);
    db.prepare(`UPDATE ${q(table)} SET ${sets}, _updated_at=?, _origin='local', _sync_status=?, _content_hash=? WHERE record_id=?`)
      .run(...Object.values(biz),now(),enqueueSync?'pending':'synced',bizHash(cleanBiz),rid);
  }
  audit(actor,'update',table,rid,JSON.stringify(payload).slice(0,500));
  if (enqueueSync) enqueue(table,rid,'update',biz);
  return {record_id:rid,updated:Object.keys(biz).length};
}
function deleteRecord(table, rid, actor, enqueueSync=true){
  if (!db.prepare(`SELECT 1 FROM ${q(table)} WHERE record_id=?`).get(rid)) return null;
  db.prepare(`DELETE FROM ${q(table)} WHERE record_id=?`).run(rid);
  audit(actor,'delete',table,rid);
  if (enqueueSync) enqueue(table,rid,'delete',{});
  return {record_id:rid,deleted:true};
}

function metaTables(){
  const out={};
  TABLES.forEach(t=>{
    const fields=cols(t).filter(x=>!META_COLS.has(x)).map(f=>{
      const m=db.prepare('SELECT field_type,options_json FROM field_meta WHERE table_name=? AND field_name=?').get(t,f);
      const o={name:f,type:m?m.field_type:'text'};
      if (m&&m.options_json) o.config={options:JSON.parse(m.options_json)};
      return o;
    });
    out[t]={label:LABELS[t],properties:fields};
  });
  return out;
}

// ---------- AI 代理（可选） ----------
function getAIConfig(){
  let r=null;
  try{ r=db.prepare('SELECT base_url,api_key,model,context_max,updated_at FROM ai_config WHERE id=1').get(); }catch(e){}
  return {
    base_url: r ? (r.base_url||'') : (process.env.AI_BASE_URL||''),
    api_key:  r ? (r.api_key||'')  : (process.env.AI_API_KEY||''),
    model:    r ? (r.model||'')    : (process.env.AI_MODEL||''),
    context_max: r ? (parseInt(r.context_max,10)||300000) : (parseInt(process.env.AI_CONTEXT_MAX||'300000',10)),
    source: r ? 'database' : 'env',
    updated_at: r ? r.updated_at : ''
  };
}
function maskKey(k){
  if(!k) return '';
  if(k.length<=10) return k.slice(0,2)+'…'+k.slice(-2);
  return k.slice(0,6)+'…'+k.slice(-4);
}
// ===== Agent 全权限工具层 =====
// 设计：LLM 只负责选工具+填参数；所有参数校验、字段白名单、写库、审计都在代码里。
const AGENT_TOOLS = [
  // 8 张业务表：查询与 CRUD
  {name:'list_records', desc:'查询任意业务表的记录。可按字段过滤、排序、分页。', params:{table:'task|time|inbox|review|week|milestone|log|subtask', filters:'对象{字段名:值}', limit:'数字,默认50', sort:'字段名'}},
  {name:'add_record', desc:'新增一条业务记录（任务/时间/收集箱/复盘/周计划/阶段等）。', params:{table:'表名', fields:'对象{中文字段名:值}'}},
  {name:'update_record', desc:'按 record_id 修改一条业务记录的字段（改状态/改日期/改优先级等）。', params:{table:'表名', record_id:'记录ID', fields:'对象{字段名:值}'}},
  {name:'delete_record', desc:'删除一条业务记录。不可撤销的删除不会自动执行——需用户确认。', params:{table:'表名', record_id:'记录ID'}},
  // 快捷业务动作
  {name:'start_day', desc:'开工：返回 TOP3 与盘面。', params:{}},
  {name:'review_day', desc:'收工复盘：返回对账与时间分布。', params:{}},
  {name:'search_history', desc:'自然语言查历史：自动解析日期/关键词/类型。', params:{question:'用户原话'}},
  // 系统管理
  {name:'list_keys', desc:'列出 APP Key（id/权限/备注/状态）。', params:{}},
  {name:'create_key', desc:'生成 APP Key。明文只返回一次。', params:{scope:'read|write', note:'用途'}},
  {name:'revoke_key', desc:'吊销 APP Key。', params:{id:'Key ID'}},
  {name:'list_skills', desc:'列出所有技能（名称/描述/来源）。', params:{}},
  {name:'get_skill', desc:'读取某个技能的完整正文。', params:{name:'技能名'}},
  {name:'create_skill', desc:'新建技能（SKILL.md 格式）。', params:{name:'kebab-case', description:'触发描述', content:'SKILL.md正文'}},
  {name:'update_skill', desc:'修改技能的名称/描述/正文。', params:{name:'技能名', fields:'对象{name|description|content:值}'}},
  {name:'delete_skill', desc:'删除技能。', params:{name:'技能名'}},
  {name:'list_prompts', desc:'列出所有提示词及是否自定义。', params:{}},
  {name:'get_prompt', desc:'读取某段提示词全文。', params:{key:'intent|system|qa|strategic|coach|generator'}},
  {name:'set_prompt', desc:'修改某段提示词，保存即生效。', params:{key:'提示词key', content:'新内容'}},
  {name:'reset_prompt', desc:'恢复某段提示词为默认。', params:{key:'intent|qa|all'}},
  {name:'get_ai_config', desc:'查看当前大模型配置（密钥脱敏）。', params:{}},
  {name:'set_ai_config', desc:'修改大模型端点/模型名/上下文预算。', params:{base_url:'接口地址', model:'模型名', context_max:'字符数'}},
  {name:'test_ai', desc:'测试大模型连通性。', params:{}},
  {name:'sync_status', desc:'查看同步队列待处理条数。', params:{}},
];
const TOOL_NAMES = AGENT_TOOLS.map(t=>t.name);
const TOOL_TABLES = TABLES;

function toolAudit(action, detail){
  audit('agent-tool',action,'agent_tool','',JSON.stringify(detail||{}).slice(0,800));
  return db.prepare('SELECT last_insert_rowid() id').get().id;
}
// 工具结果 → 人类可读文本（确定性，不经 LLM）
function formatToolResult(tool, r){
  if(!r) return '工具执行完毕，无返回内容。';
  if(r.ok===false) return '执行失败：'+(r.error||'未知错误');
  try{
    switch(tool){
      case 'list_records': {
        const rows=r.items||[];
        if(!rows.length) return `${r.table} 没有匹配的记录（共 ${r.total} 条）。`;
        const keys=Object.keys(rows[0]).filter(k=>!k.startsWith('_')).slice(0,6);
        const lines=rows.slice(0,30).map(x=>keys.map(k=>`${k}: ${x[k]??''}`).join(' / '));
        return `${r.table} 命中 ${r.total} 条（显示前 ${lines.length} 条）\n`+lines.join('\n');
      }
      case 'sync_status': return `同步队列：待处理 ${r.pending} 条`+(r.by_table&&r.by_table.length?'\n'+r.by_table.map(x=>`${x.table_name} ${x.op}: ${x.n}`).join('\n'):'');
      case 'list_keys': return (r.length?r:[]).map(k=>`${k.id} | ${k.scope} | ${k.revoked?'已吊销':'有效'} | ${k.note||'无备注'}`).join('\n')||'当前没有 APP Key。';
      case 'list_skills': return (r||[]).map(s=>`${s.name} | ${s.description||''} | 来源 ${s.origin||'-'}`).join('\n')||'当前没有技能。';
      case 'get_skill': return `【${r.name}】${r.description||''}\n\n${r.content||''}`;
      case 'create_key': return `已生成 Key（${r.scope}）：${r.key}\n请立即保存，之后不再显示。id=${r.id}`;
      case 'create_skill': return `已创建技能「${r.name}」(id=${r.id})。`;
      case 'update_skill': return `技能已更新（${r.updated} 个字段）。`;
      case 'delete_skill': return '技能已删除。';
      case 'get_ai_config': return `当前模型：${r.model}\n接口：${r.base_url}\n上下文预算：${r.context_max}\n密钥：${r.api_key_masked||'未设置'}\n配置来源：${r.source}`;
      case 'set_ai_config': return '模型配置已更新：'+JSON.stringify(r);
      case 'test_ai': return `连接${r.ok?'成功':'失败'}（${r.ms||''}ms）：${r.reply||r.error||''}`;
      case 'list_prompts': return Object.keys(r).map(k=>`${k}: ${r[k].custom?'已自定义':'默认'}`).join('\n');
      case 'get_prompt': return `【${r.key}】\n${r.content}`;
      case 'set_prompt': return `提示词「${r.key}」已保存，立即生效。`;
      case 'reset_prompt': return `提示词已恢复：${r.reset}`;
      case 'add_record': return `已新增记录（${r.record_id}）。`;
      case 'update_record': return `已更新 ${r.updated} 个字段（${r.record_id}）。`;
      case 'delete_record': return `记录已删除，可用撤销恢复。`;
      case 'start_day': return `今日关键 3 件：\n`+(r.关键3件||[]).map((x,i)=>`${i+1}. [${x.优先级}] ${x.任务} (${x.分数}分)`).join('\n')+`\n未完成 ${r.未完成}，逾期 ${r.逾期}`;
      case 'review_day': return `复盘：${r.一句话||''}`;
      case 'search_history': return r.数据||'未命中记录。';
      default: return JSON.stringify(r).slice(0,1500);
    }
  }catch(e){ return JSON.stringify(r).slice(0,1500); }
}

// 确定性关键词路由：常见系统管理请求直接映射工具，不依赖 LLM 选择
function toolByKeyword(text){
  const t=String(text||'');
  if(/APP.?Key|api.?key|密钥|key列表|有哪些key|生成.{0,4}key|吊销/i.test(t))
    return /生成|新建|创建/.test(t)?{tool:'create_key',args:{scope:/写|write/i.test(t)?'write':'read'}}
      :/吊销|删除|撤销/.test(t)?null:{tool:'list_keys',args:{}};
  if(/同步队列|待同步|pending|积压/i.test(t)) return {tool:'sync_status',args:{}};
  if(/什么模型|哪个模型|模型名|模型配置|用的什么|deepseek|上下文预算/i.test(t))
    return /改|换|设置|配置成/.test(t)?null:{tool:'get_ai_config',args:{}};
  if(/列出.*技能|所有技能|技能列表|有哪些技能/i.test(t)) return {tool:'list_skills',args:{}};
  if(/提示词|prompt/i.test(t) && /查看|列出|有哪些/.test(t)) return {tool:'list_prompts',args:{}};
  if(/开工|今日重点|今天该做|TOP3/i.test(t)) return {tool:'start_day',args:{}};
  if(/收工|复盘今天/i.test(t)) return {tool:'review_day',args:{}};
  return null;
}

async function executeTool(name, args){
  const a=args||{};
  switch(name){
    case 'list_records': {
      const t=String(a.table||'task');
      if(!TOOL_TABLES.includes(t)) throw new Error('表名必须是: '+TOOL_TABLES.join(','));
      const limit=Math.min(Math.max(parseInt(a.limit,10)||50,1),500);
      const filters=(a.filters&&typeof a.filters==='object')?a.filters:null;
      const r=listRecords(t,{page:1,size:limit,filters,sort:a.sort});
      return {table:t,total:r.total,items:r.items.slice(0,limit)};
    }
    case 'add_record': {
      const t=String(a.table||'');
      if(!TOOL_TABLES.includes(t)) throw new Error('表名不合法');
      if(!a.fields||typeof a.fields!=='object'||!Object.keys(a.fields).length) throw new Error('缺少 fields');
      const r=addRecord(t,a.fields,'agent-tool');
      const aid=toolAudit('add_record',{table:t,fields:a.fields,created:[{table:t,record_id:r.record_id}]});
      return {ok:true,record_id:r.record_id,audit_id:aid};
    }
    case 'update_record': {
      const t=String(a.table||'');
      if(!TOOL_TABLES.includes(t)) throw new Error('表名不合法');
      if(!a.record_id) throw new Error('缺少 record_id');
      if(!a.fields||typeof a.fields!=='object') throw new Error('缺少 fields');
      const r=updateRecord(t,a.record_id,a.fields,'agent-tool');
      if(!r) throw new Error('记录不存在');
      const aid=toolAudit('update_record',{table:t,record_id:a.record_id,fields:a.fields});
      return {ok:true,record_id:a.record_id,updated:r.updated,audit_id:aid};
    }
    case 'delete_record': {
      const t=String(a.table||'');
      if(!TOOL_TABLES.includes(t)) throw new Error('表名不合法');
      if(!a.record_id) throw new Error('缺少 record_id');
      const before=db.prepare(`SELECT * FROM ${q(t)} WHERE record_id=?`).get(a.record_id);
      if(!before) throw new Error('记录不存在');
      const r=deleteRecord(t,a.record_id,'agent-tool');
      const aid=toolAudit('delete_record',{table:t,record_id:a.record_id,before,restorable:true});
      return {ok:true,deleted:1,audit_id:aid,note:'可用撤销恢复'};
    }
    case 'start_day': { const t=computeTop3(); return {关键3件:t.关键3件,未完成:t.未完成总数,逾期:t.逾期数}; }
    case 'review_day': { return computeReview(); }
    case 'search_history': {
      const r=historySearch(String(a.question||''));
      return r?{条件:r.params,命中:r.found,数据:r.text.slice(0,6000)}:{未命中:true};
    }
    case 'list_keys':
      return db.prepare('SELECT id,scope,revoked,note,created_at FROM api_key ORDER BY created_at DESC').all();
    case 'create_key': {
      const k=createApiKey(a.scope==='write'?'write':'read',String(a.note||''));
      const kaid=toolAudit('create_key',{id:k.id,scope:k.scope});
      return Object.assign({},k,{audit_id:kaid});
    }
    case 'revoke_key': {
      if(!a.id) throw new Error('缺少 id');
      const r=db.prepare('UPDATE api_key SET revoked=1 WHERE id=?').run(a.id);
      if(!r.changes) throw new Error('Key 不存在');
      toolAudit('revoke_key',{id:a.id});
      return {ok:true,revoked:1};
    }
    case 'list_skills':
      return db.prepare('SELECT id,name,description,origin,status,updated_at FROM skills ORDER BY name').all();
    case 'get_skill': {
      const r=db.prepare('SELECT name,description,content FROM skills WHERE name=?').get(String(a.name||''));
      if(!r) throw new Error('技能不存在');
      return r;
    }
    case 'create_skill': {
      const name=String(a.name||'').toLowerCase().trim();
      if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)||name.length<3||name.length>64) throw new Error('技能名不合法');
      if(db.prepare('SELECT 1 FROM skills WHERE name=?').get(name)) throw new Error('同名技能已存在');
      const content=String(a.content||'');
      if(!content) throw new Error('缺少正文');
      const id='s_'+crypto.randomBytes(8).toString('hex');
      db.prepare('INSERT INTO skills (id,name,description,content,status,source_sha,origin,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)')
        .run(id,name,String(a.description||''),content,'active',crypto.createHash('sha256').update(content).digest('hex'),'agent',now(),now());
      const aid=toolAudit('create_skill',{id,name,created:[{table:'skills',record_id:id}]});
      return {ok:true,id,name,audit_id:aid};
    }
    case 'update_skill': {
      if(!a.name) throw new Error('缺少 name');
      const cur=db.prepare('SELECT * FROM skills WHERE name=?').get(a.name);
      if(!cur) throw new Error('技能不存在');
      const fields=a.fields||{};
      const allowed=['name','description','content'];
      const sets=[],vals=[];
      allowed.forEach(k=>{ if(fields[k]!==undefined){ sets.push(k+'=?'); vals.push(String(fields[k])); } });
      if(!sets.length) throw new Error('没有可更新字段');
      if(fields.content) sets.push("source_sha=?"),vals.push(crypto.createHash('sha256').update(String(fields.content)).digest('hex'));
      db.prepare(`UPDATE skills SET ${sets.join(',')},updated_at=? WHERE name=?`).run(...vals,now(),a.name);
      toolAudit('update_skill',{name:a.name,fields});
      return {ok:true,updated:sets.length};
    }
    case 'delete_skill': {
      if(!a.name) throw new Error('缺少 name');
      const r=db.prepare('DELETE FROM skills WHERE name=?').run(a.name);
      if(!r.changes) throw new Error('技能不存在');
      toolAudit('delete_skill',{name:a.name});
      return {ok:true,deleted:1};
    }
    case 'list_prompts': {
      const out={}; PROMPT_KEYS.forEach(k=>{ const r=db.prepare('SELECT content,updated_at FROM prompts WHERE key=?').get(k);
        out[k]={custom:!!r, updated_at:r?r.updated_at:''}; }); return out;
    }
    case 'get_prompt': {
      const k=String(a.key||'');
      if(!PROMPT_KEYS.includes(k)) throw new Error('未知提示词');
      const cur=getPrompts(); return {key:k,content:cur[k]||''};
    }
    case 'set_prompt': {
      const k=String(a.key||'');
      if(!PROMPT_KEYS.includes(k)) throw new Error('未知提示词');
      const v=String(a.content||''); if(!v.trim()) throw new Error('内容不能为空');
      const prev=db.prepare('SELECT content FROM prompts WHERE key=?').get(k);
      db.prepare('INSERT OR REPLACE INTO prompts (key,content,updated_at) VALUES (?,?,?)').run(k,v,now());
      const paid=toolAudit('set_prompt',{key:k,prev_content:prev?prev.content:null,length:v.length});
      return {ok:true,key:k,saved:true,audit_id:paid};
    }
    case 'reset_prompt': {
      const k=String(a.key||'all');
      if(k==='all') db.prepare("DELETE FROM prompts WHERE key IN ('intent','qa')").run();
      else if(k==='intent'||k==='qa') db.prepare('DELETE FROM prompts WHERE key=?').run(k);
      else throw new Error('只能恢复 intent/qa/all');
      toolAudit('reset_prompt',{key:k}); return {ok:true,reset:k};
    }
    case 'get_ai_config': { const c=getAIConfig(); return {base_url:c.base_url,model:c.model,context_max:c.context_max,api_key_masked:maskKey(c.api_key),source:c.source}; }
    case 'set_ai_config': {
      const b={};
      if(a.base_url) b.base_url=String(a.base_url).trim().replace(/\/+$/,'');
      if(a.model) b.model=String(a.model).trim();
      if(a.context_max) b.context_max=parseInt(a.context_max,10);
      if(!Object.keys(b).length) throw new Error('没有可更新字段');
      const cur=getAIConfig();
      db.prepare('INSERT OR REPLACE INTO ai_config (id,base_url,api_key,model,context_max,updated_at) VALUES (1,?,?,?,?,?)')
        .run(b.base_url||cur.base_url,cur.api_key,b.model||cur.model,b.context_max||cur.context_max,now());
      toolAudit('set_ai_config',b); return {ok:true,...b};
    }
    case 'test_ai': {
      const c=getAIConfig();
      const r=await fetch(c.base_url.replace(/\/+$/,'')+'/chat/completions',{
        method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+c.api_key},
        body:JSON.stringify({model:c.model,messages:[{role:'user',content:'只回复两个字：正常'}]}),
        signal:AbortSignal.timeout(20000)});
      const d=await r.json();
      return {ok:r.ok,status:r.status,reply:(d.choices?.[0]?.message?.content||'').slice(0,50)};
    }
    case 'sync_status': {
      const rows=db.prepare("SELECT table_name,op,count(*) n FROM sync_queue WHERE status='pending' GROUP BY table_name,op").all();
      return {pending:rows.reduce((s,r)=>s+r.n,0),by_table:rows};
    }
    default: throw new Error('未知工具: '+name);
  }
}

// ===== 历史查询：按日期/关键词/类型定向检索 =====
function parseHistoryQuery(question){
  const t=String(question||'');
  const out={dateFrom:'',dateTo:'',keyword:'',tables:[],limit:60};
  // 日期：绝对 YYYY-MM-DD
  let m=t.match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if(m){ const d=m[1]+'-'+String(m[2]).padStart(2,'0')+'-'+String(m[3]).padStart(2,'0'); out.dateFrom=d; out.dateTo=d; }
  // 年月：2026年8月 / 8月
  if(!out.dateFrom){
    m=t.match(/(\d{4})年(\d{1,2})月/);
    if(m){ out.dateFrom=m[1]+'-'+String(m[2]).padStart(2,'0')+'-01';
      out.dateTo=m[1]+'-'+String(parseInt(m[2],10)+1).padStart(2,'0')+'-01'; }
    else { m=t.match(/(\d{1,2})月/);
      if(m){ const yr=new Date().getFullYear(); out.dateFrom=yr+'-'+String(m[1]).padStart(2,'0')+'-01';
        out.dateTo=yr+'-'+String(parseInt(m[1],10)+1).padStart(2,'0')+'-01'; } }
  }
  // 相对日：昨天/前天/今天/上周
  if(!out.dateFrom){
    const base=new Date();
    if(/上周/.test(t)){ const d=new Date(base); d.setDate(d.getDate()-7); out.dateFrom=d.toISOString().slice(0,10); out.dateTo=new Date().toISOString().slice(0,10); }
    else if(/前天/.test(t)){ const d=new Date(base); d.setDate(d.getDate()-2); out.dateFrom=d.toISOString().slice(0,10); out.dateTo=out.dateFrom; }
    else if(/昨天/.test(t)){ const d=new Date(base); d.setDate(d.getDate()-1); out.dateFrom=d.toISOString().slice(0,10); out.dateTo=out.dateFrom; }
    else if(/今天|今日/.test(t)){ out.dateFrom=new Date().toISOString().slice(0,10); out.dateTo=out.dateFrom; }
  }
  // 表类型提示词
  if(/时间|做了什么|花了|小时|分钟|时段|记录/.test(t)) out.tables.push('time');
  if(/想法|收集|问题|思考|点子/.test(t)) out.tables.push('inbox');
  if(/任务|待办|完成|计划|P0|P1|P2/i.test(t)) out.tables.push('task');
  if(/复盘|卡点|总结|明日计划/.test(t)) out.tables.push('review');
  if(/周目标|周计划|关键结果|本周|下周/.test(t)) out.tables.push('week');
  if(!out.tables.length) out.tables=['task','time','inbox','review','week'];
  // 关键词：去掉问句/日期/类型词后取最长中文片段
  let kw=t.replace(/\d{4}-\d{1,2}-\d{1,2}|\d{4}年\d{1,2}月|\d{1,2}月|上周|前天|昨天|今天|今日|我|的|了|吗|呢|什么|哪些|多少|有|查|看|问|下|关于|记录|时间|任务|计划|复盘|想法|收集|问题|思考|待办|完成|做了|花了|小时|分钟|时段|本周|下周|周目标|周计划|关键结果|P0|P1|P2/gi,' ').trim();
  kw=kw.split(/[，。？！、,\s]+/).filter(x=>x.length>=2).sort((a,b)=>b.length-a.length)[0]||'';
  out.keyword=kw.slice(0,20);
  return out;
}
function historySearch(question){
  const ps=parseHistoryQuery(question);
  const parts=[]; const found={};
  const dateCol={task:'计划日',time:'日期',inbox:'记录日期',review:'日期',week:'周次'};
  ps.tables.forEach(t=>{
    const cs=cols(t).filter(x=>!META_COLS.has(x));
    const where=[], args=[];
    const dc=dateCol[t];
    if(ps.dateFrom && cs.includes(dc)){ where.push(`substr(${q(dc)},1,10)>=?`); args.push(ps.dateFrom);
      if(ps.dateTo){ where.push(`substr(${q(dc)},1,10)<?`); args.push(ps.dateTo); } }
    if(ps.keyword){
      const kws=cs.filter(c=>/名称|内容|事项|备注|完成|困难|计划|目标|总结|结果|标签/.test(c));
      if(kws.length){ where.push('('+kws.map(c=>`${q(c)} LIKE ?`).join(' OR ')+')'); kws.forEach(()=>args.push('%'+ps.keyword+'%')); }
    }
    const sql=`SELECT * FROM ${q(t)}`+(where.length?' WHERE '+where.join(' AND '):'')+
      ` ORDER BY rowid DESC LIMIT ${ps.limit}`;
    let rows=[];
    try{ rows=db.prepare(sql).all(...args); }catch(e){ return; }
    if(!rows.length) return;
    found[t]=rows.length;
    const lines=rows.map(r=>cs.map(k=>`${k}:${r[k]??''}`).join(' | '));
    parts.push(`【${LABELS[t]} 命中${rows.length}条】\n${lines.join('\n')}`);
  });
  const head=`【历史查询条件】日期 ${ps.dateFrom||'不限'}~${ps.dateTo||'不限'}｜关键词 ${ps.keyword||'无'}｜查表 ${ps.tables.join('/')}\n`;
  const body=parts.length?parts.join('\n\n'):'【未命中任何记录】可适当放宽条件或说明无数据，不得编造。';
  return {text:(head+body).slice(0,30000), found, params:ps};
}
function buildContext(question){
  const r=historySearch(question);
  if(r){
    const hits=Object.values(r.found).reduce((a,b)=>a+b,0);
    // 命中过少时补充全表概览（宽泛问题的兜底）
    if(hits<3){
      const parts=[r.text];
      ['task','time','inbox','review','week'].forEach(t=>{
        const rows=db.prepare(`SELECT * FROM ${q(t)} ORDER BY rowid DESC LIMIT 30`).all();
        if(!rows.length) return;
        const cs=cols(t).filter(x=>!META_COLS.has(x));
        parts.push(`【${LABELS[t]} 概览(最近${rows.length}条)】\n`+rows.map(x=>cs.map(k=>`${k}:${x[k]??''}`).join(' | ')).join('\n'));
      });
      return parts.join('\n\n').slice(0,30000);
    }
    return r.text;
  }
  return '';
}
async function callAI(messages, stream){
  const cfg=getAIConfig();
  const resp = await fetch(cfg.base_url.replace(/\/+$/,'')+'/chat/completions',{
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+cfg.api_key},
    body:JSON.stringify({model:cfg.model,messages,stream:!!stream}),
    signal: AbortSignal.timeout(120000)
  });
  return resp;
}

// 生成 APP Key：明文只返回一次，库里只存 sha256
function createApiKey(scope, note){
  const raw = 'wb_' + crypto.randomBytes(24).toString('hex');
  const id = 'k_' + crypto.randomBytes(8).toString('hex');
  db.prepare('INSERT INTO api_key (id,key_hash,scope,created_at,revoked,note) VALUES (?,?,?,?,0,?)')
    .run(id, sha(raw), scope, now(), note||'');
  audit('api','create_key','api_key',id,note||'');
  return {id, key:raw, scope, note:note||'', created_at:now()};
}

// ---------- Agent 能力（意图识别由 LLM，确定性逻辑在代码） ----------
function aiContextMax(){ return getAIConfig().context_max; }
const FIELD_WHITELIST = {
  task: ['任务名称','状态','优先级','到期日','备注','计划日','来源','时段','事项类型','周次','主线执行','负责人','事项二'],
  time: ['日期','事项','时长','分类','开始时间','结束时间','使用类型'],
  inbox: ['内容','类型','标签','来源','记录日期','状态'],
  review: ['日期','今日完成','卡点困难','明日计划','一句话总结','周次'],
  week: ['周次','本周目标','关键结果','下周计划','周总结','体验打分']
};
// LLM 常见英文/别名键 → 中文字段名（兜底，防止 prompt 约束失效时丢数据）
const FIELD_ALIAS={title:'任务名称',name:'任务名称',task:'任务名称',事项名:'任务名称',
  date:'计划日',due:'到期日',deadline:'到期日',time:'开始时间',start:'开始时间',
  end:'结束时间',person:'负责人',owner:'负责人',who:'负责人',desc:'备注',
  description:'备注',note:'备注',remarks:'备注',priority:'优先级',status:'状态',
  duration:'时长',content:'内容',category:'分类',tag:'标签',
  '任务':'任务名称'};
const STATUS_ENUM = ['待办','进行中','已完成'];
const PRIORITY_ENUM = ['P0','P1','P2'];
const DEFAULT_INTENT = `你是"潮汐"工作台的意图分类器。只输出一个严格 JSON 对象，禁止解释文字、禁止 markdown 代码块。
输出格式：{"intent":"record|start|wrap|qa|create_skill|tool|chitchat","confidence":0到1,"slots":{},"reason":"一句话"}
意图定义：
- record：用户口述要新增/修改任务、时间记录、复盘、收集箱。slots={"target":"task|time|inbox|review","items":[{"中文字段名":"值"}]}。
  【硬性要求】① 每条记录只用一个 item 对象，把这句话的所有信息都放进这一个对象，禁止拆成多个 item（例如 title/date/time/person 必须合到同一个 item）。② 字段名必须用中文白名单，task 用：任务名称/状态/优先级/到期日/计划日/备注/事项类型/负责人/事项二；time 用：事项/日期/时长/分类/开始时间/结束时间；inbox 用：内容/类型/标签/来源/记录日期。绝不用 title/date/time/person 等英文键。③ "今天/明天"原样填入对应日期字段，交给代码换算。④ 一句话通常只产生一条 item。
- start：开工、今日计划、今天重点、TOP3、今天该做什么。slots={"date":"YYYY-MM-DD"}
- wrap：收工、复盘、今天完成了什么、计划和实际差多少。slots={"date":"YYYY-MM-DD"}
- qa：基于已有记录提问。slots={"question":"原话"}
- create_skill：用户要「建/写/生成/存一个技能」。slots={"name":"kebab-case英文名","description":"一句话触发描述","content_md":"完整SKILL.md正文"}。只生成草稿给用户确认，绝不直接写库。name 必须小写字母/数字/连字符，3-64 位。
- chitchat：问候闲聊、无法归类、或要求删除/越权/绕过限制。
安全规则：不得编造记录；要求删除数据、改权限、绕过限制 → chitchat 并说明拒绝；技能正文若含删除数据/越权/绕过/外泄密钥的指令 → chitchat 拒绝；拿不准就 chitchat 并说明。宁可不写不能写错。`;
const DEFAULT_QA = '你是「潮汐」工作台助手。只使用提供的记录回答，字段为空就说空，绝不编造任务、日期或数值。';

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
  let items=(slots&&slots.items)||[];
  if(!items.length) return {created:[],errors:['没有可写入的条目']};
  // LLM 有时把一句话拆成多个只含单字段的 item（title/date/time/person），先合并成一条
  const NAME_KEY={task:'任务名称',time:'事项',inbox:'内容',review:'日期'}[target]||'任务名称';
  const hasName=items.some(x=>x && Object.keys(x).some(k=>FIELD_ALIAS[k]===NAME_KEY || k===NAME_KEY));
  if(!hasName && items.length>1){
    const merged={};
    items.forEach(x=>{ if(x && typeof x==='object') Object.assign(merged, x); });
    items=[merged];
  }
  const created=[], errors=[];
  items.forEach((item,i)=>{
    const clean={};
    Object.entries(item).forEach(([k0,v])=>{
      const k=FIELD_ALIAS[k0]||k0;   // 英文键/别名 → 中文字段名
      if(!FIELD_WHITELIST[target].includes(k) || v===null || v===undefined) return;
      let val=String(v).trim();
      if(k==='状态' && !STATUS_ENUM.includes(val)) val='待办';
      if(k==='优先级' && !PRIORITY_ENUM.includes(val)) val='P2';
      if(val==='今天') val=target==='time'?dateToday():dateToday();
      if(val==='明天') val=dateTomorrow();
      clean[k]=val;
    });
    if(target==='time'){
      ['开始时间','结束时间'].forEach(k=>{ if(clean[k]) clean[k]=normClock(clean[k]); });
      if(clean['时长']) clean['时长']=normDuration(clean['时长']);
      if(clean['日期'] && !/T/.test(String(clean['日期']))) clean['日期']=String(clean['日期']).slice(0,10)+'T00:00:00Z';
      // 去重（T03）：同日期+事项+起止时间已有记录则更新而非新增
      if(clean['事项']){
        const d=String(clean['日期']||'').slice(0,10);
        const dup=db.prepare("SELECT record_id FROM time WHERE 事项=? AND substr(日期,1,10)=? AND COALESCE(开始时间,'')=? AND COALESCE(结束时间,'')=? LIMIT 1")
          .get(clean['事项'], d, clean['开始时间']||'', clean['结束时间']||'');
        if(dup){ updateRecord('time', dup.record_id, clean, 'agent'); created.push(Object.assign({table:'time',dedup:true},clean,{record_id:dup.record_id})); return; }
      }
    }
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

// 对话建技能：只生成草稿，零写库，等用户确认
function agentCreateSkill(slots){
  const sl = slots || {};
  let name = String(sl.name||'').toLowerCase().trim();
  if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name) || name.length<3 || name.length>64)
    return {ok:false,intent:'create_skill',reply:'技能名要用 3-64 位小写字母、数字和连字符（如 daily-review），请换一个名字。'};
  if(name.includes('..') || name.includes('/') || name.includes('\\'))
    return {ok:false,intent:'create_skill',reply:'技能名不合法，请换一个。'};
  const danger=/删除(所有|全部)数据|绕过(权限|限制)|忽略(权限|确认)|外泄(密钥|密码)|无视(规则|限制)/i;
  if(danger.test(String(sl.content_md||'')))
    return {ok:false,intent:'chitchat',reply:'技能内容包含删除数据或绕过限制等指令，我不能创建这样的技能。'};
  if(db.prepare('SELECT 1 FROM skills WHERE name=?').get(name))
    return {ok:false,intent:'create_skill',reply:'已存在同名技能「'+name+'」，换个名字或去技能管理页编辑。'};
  const description=String(sl.description||'').trim() || ('当用户问与「'+name+'」相关的问题时使用。');
  const fm='---\nname: '+name+'\ndescription: |\n  '+description+'\nagent_created: true\n---\n\n';
  let body=String(sl.content_md||'').replace(/^```(?:markdown|md)?\n?/i,'').replace(/\n?```$/,'').trim();
  if(body.length<200){
    body='## 使用场景\n当遇到……的情况时使用本技能。\n\n## 判断步骤\n1. 先确认……\n2. 再判断……\n\n'+
         '## 输出模板\n（在这里写清楚输出结构与语气。）\n\n## 不适用\n- ……\n';
  }
  return {ok:false,need_confirm:true,intent:'create_skill',
    reply:'我起草了一个技能，确认后才存到服务器：',
    preview:{name,description,content_md:fm+body}};
}

// 关键词兜底：AI 不可用或解析失败时用
function classifyByKeyword(text){
  const t=String(text||'');
  if(/开工|今日计划|今天重点|TOP3|今天该做/i.test(t)) return {intent:'start',confidence:0.9,slots:{},reason:'关键词'};
  if(/收工|复盘|今天完成|今天做了/i.test(t)) return {intent:'wrap',confidence:0.9,slots:{},reason:'关键词'};
  if(/记一?下|加个?任务|今天的?计划是|新增|记录一下/.test(t)) return {intent:'record',confidence:0.8,slots:{target:'task',items:[{'任务名称':t.replace(/^(记一下|记录一下|加个任务|今天的计划是|新增)/,'').replace(/^[：:，,\s]+/,'').trim()}]},reason:'关键词'};
  if(/建(个|一个)?技能|生成技能|写成技能|存成技能|做个技能/i.test(t)) return {intent:'create_skill',confidence:0.75,slots:{},reason:'关键词'};
  if(/帮我改|帮我删|新建.*技能|改.*提示词|查.*队列|生成.*key|吊销|新增.*周计划|标记.*完成/.test(t)) return {intent:'tool',confidence:0.7,slots:{},reason:'关键词'};
  if(/有哪些事|什么状态|几?条任务|查一下|现在怎么样/.test(t)) return {intent:'qa',confidence:0.8,slots:{question:t},reason:'关键词'};
  return {intent:'chitchat',confidence:0.5,slots:{},reason:'无法识别'};
}

// 意图识别 Skill：优先从技能库读取（可在 Agent 管理页编辑），回落 prompts.intent
function getIntentSystem(){
  try{
    const r=db.prepare("SELECT content FROM skills WHERE name=? AND status=?").get('intent-router','active');
    if(r && r.content && r.content.length>100) return r.content;
  }catch(e){}
  return getPrompts().intent;
}
// 自由兜底回复：让 Agent 自然接话，不再固定自我介绍
async function freeReply(message, history){
  try{
    const cfg=getAIConfig();
    if(!cfg.base_url||!cfg.api_key) return null;
    let ctx=(history||[]).slice(-10).map(x=>(x.role==='me'?'用户':'助手')+': '+String(x.text||'').slice(0,300)).join('\n');
    const sys=getPrompts().system||'你是潮汐，用户的时间与精力助手。';
    const r=await fetch(cfg.base_url.replace(/\/+$/,'')+'/chat/completions',{
      method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+cfg.api_key},
      body:JSON.stringify({model:cfg.model,messages:[
        {role:'system',content:sys+'\n\n你是自然对话的助手。用中文、简洁（1-3句）。可以自我介绍、回应问候、澄清用户想做什么，但不要固定套话。若用户在问信息，引导ta具体说要查什么（任务/时间/想法/复盘）。'},
        {role:'user',content:(ctx?('近期对话：\n'+ctx+'\n\n'):'')+message}
      ]}),signal:AbortSignal.timeout(15000)
    });
    const d=await r.json();
    return (d.choices?.[0]?.message?.content||'').trim() || null;
  }catch(e){ return null; }
}

async function classifyIntent(message, history){
  const cfg=getAIConfig();
  if(!cfg.base_url||!cfg.api_key) return classifyByKeyword(message);
  // 上下文预算：历史 + 当前问题，超 context_max 时保留最近轮
  let hist=(history||[]).slice(-20);
  let ctx=hist.map(x=>(x.role==='me'?'用户':'助手')+': '+String(x.text||'').slice(0,500)).join('\n');
  const ctxMax=cfg.context_max;
  if(ctx.length>ctxMax) ctx=ctx.slice(-ctxMax);
  const messages=[
    {role:'system',content:getIntentSystem()},
    {role:'user',content:(ctx?('近期对话：\n'+ctx+'\n\n'):'')+'当前输入：'+message}
  ];
  try{
    const r=await fetch(cfg.base_url.replace(/\/+$/,'')+'/chat/completions',{
      method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+cfg.api_key},
      body:JSON.stringify({model:cfg.model,response_format:{type:'json_object'},messages}),
      signal: AbortSignal.timeout(25000)
    });
    const d=await r.json();
    const raw=(d.choices?.[0]?.message?.content||'').replace(/```json|```/g,'').trim();
    const obj=JSON.parse(raw);
    if(!obj.intent || !['record','start','wrap','qa','create_skill','tool','chitchat'].includes(obj.intent)) throw new Error('bad intent');
    return obj;
  }catch(e){
    // 超时/解析失败不要静默降级为关键词（会误判成 chitchat 显得死板）
    // 交给调用方走自由回复，至少能自然接话
    return {intent:'qa',confidence:0.5,slots:{question:message},reason:'识别降级',degraded:true};
  }
}

// AI 配置表（网页可改，替代只能改 env 文件）
try{ db.exec(`CREATE TABLE IF NOT EXISTS ai_config (
  id INTEGER PRIMARY KEY CHECK (id=1), base_url TEXT, api_key TEXT,
  model TEXT, context_max INTEGER, updated_at TEXT)`); }catch(e){}
// Agent 提示词表（网页可编辑，可恢复默认）
try{ db.exec(`CREATE TABLE IF NOT EXISTS prompts (
  key TEXT PRIMARY KEY, content TEXT, updated_at TEXT)`); }catch(e){}
const PROMPT_KEYS=['intent','qa','system','strategic','coach','generator'];
const DEFAULT_PROMPTS={intent:DEFAULT_INTENT, qa:DEFAULT_QA, system:'', strategic:'', coach:'', generator:''};
function getPrompts(){
  const out=Object.assign({},DEFAULT_PROMPTS);
  try{
    db.prepare('SELECT key,content FROM prompts').all().forEach(r=>{
      if(PROMPT_KEYS.includes(r.key)) out[r.key]=r.content;
    });
  }catch(e){}
  return out;
}
// ===== 技能与提示词按意图装配（v1.0 套件运行链路）=====
const INTENT_SKILL={start:'day-kickoff', wrap:'day-review', record:'activity-capture',
  qa:'activity-capture', create_skill:'_generator', chitchat:''};
function loadSkill(name){
  if(!name) return '';
  try{ const r=db.prepare('SELECT content FROM skills WHERE name=? AND status=?').get(name,'active');
    return r ? r.content : ''; }catch(e){ return ''; }
}
function loadSkillRefs(name, limit){
  if(!name) return '';
  try{
    const rows=db.prepare('SELECT ref_key,content FROM skill_refs WHERE skill_name=? ORDER BY ref_key').all(name);
    // 参考规则只取关键红线摘要（套件建议按需读取，不整篇塞进上下文）
    const DIGEST={
      taxonomy:'四维度独立：domain/cognitive_type/value_type/task_status；认知类型是行为性质非价值；灵感用 IdeaEvent 不重复计时长；重叠区间取并集不累加；completed_confirmed 须有明示证据。',
      runtime:'解析意图→检查记录与权限→核对→分析→授权写入→验证→简短确认；工具不可用只输出待保存内容，不声称已保存。'
    };
    const core=rows.filter(r=>/taxonomy|runtime/.test(r.ref_key));
    return (core.length?core:rows).slice(0,limit||2)
      .map(r=>'【参考:'+r.ref_key+'】'+(DIGEST[r.ref_key]||String(r.content).slice(0,600))).join('\n');
  }catch(e){ return ''; }
}
function buildAgentSystem(intent, slots){
  const pr=getPrompts();
  const parts=[];
  // 主系统词（套件必装）
  if(pr.system) parts.push(pr.system);
  // 按意图追加补充提示词
  if((intent==='start'||intent==='wrap'||intent==='record') && pr.coach) parts.push('【执行教练模式】\n'+pr.coach);
  if((intent==='qa'||intent==='wrap'||intent==='start') && pr.strategic) parts.push('【战略军师模式】\n'+pr.strategic);
  if(intent==='create_skill' && pr.generator) parts.push('【技能生成专家】\n'+pr.generator);
  // 按意图加载技能正文（真正让技能参与运行）
  let skillName=INTENT_SKILL[intent]||'';
  if(intent==='record' && slots && slots.target==='task') skillName='task-planning';
  const skill=loadSkill(skillName);
  if(skill) parts.push('【本次调用的技能：'+skillName+'】\n'+skill);
  const refs=loadSkillRefs(skillName);
  if(refs) parts.push(refs);
  parts.push('【输出纪律】只使用下面提供的事实数据，不得编造任何任务、时间、数值或结论；按上面技能的输出模板简洁表述。');
  return parts.join('\n\n---\n\n');
}
// 让 LLM 按技能模板重述确定性数据；失败返回 null 由调用方兜底
async function renderWithSkill(intent, slots, facts, fallback){
  try{
    const cfg=getAIConfig();
    if(!cfg.base_url||!cfg.api_key) return null;
    const sys=buildAgentSystem(intent, slots);
    const r=await fetch(cfg.base_url.replace(/\/+$/,'')+'/chat/completions',{
      method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+cfg.api_key},
      body:JSON.stringify({model:cfg.model,messages:[
        {role:'system',content:sys},
        {role:'user',content:'以下是已从数据库核验的事实数据（JSON），请严格据此按技能模板输出；不得新增任何事实：\n'+JSON.stringify(facts,null,1)+'\n\n用户原话：'+String(slots&&slots.__raw||'')}
      ]}),
      signal:AbortSignal.timeout(20000)
    });
    const d=await r.json();
    const text=(d.choices?.[0]?.message?.content||'').trim();
    return text || null;
  }catch(e){ return null; }
}

// 时间/时长规范化：把中文口语转成机器可读格式
function normClock(v){
  let s=String(v==null?'':v).trim();
  if(!s) return '';
  // 中文数字时段：下午2点 / 上午9点半 / 晚上8点 / 中午12点
  let m=s.match(/(上午|早上|早晨|中午|下午|晚上|傍晚|凌晨)?\s*(\d{1,2})\s*[:：点]\s*(\d{1,2})?\s*(半|分)?/);
  if(m){
    let h=parseInt(m[2],10), mi=m[3]?parseInt(m[3],10):(m[4]==='半'?30:0);
    const ap=m[1]||'';
    if((ap==='下午'||ap==='晚上'||ap==='傍晚') && h<12) h+=12;
    if(ap==='凌晨' && h===12) h=0;
    if(ap==='中午' && h<11) h+=12;
    if(h>=0&&h<24&&mi<60) return String(h).padStart(2,'0')+':'+String(mi).padStart(2,'0');
  }
  // 纯数字 1330 / 930
  m=s.match(/^(\d{3,4})$/);
  if(m){ const n=m[1].padStart(4,'0'); const h=parseInt(n.slice(0,2),10), mi=parseInt(n.slice(2),10);
    if(h<24&&mi<60) return n.slice(0,2)+':'+n.slice(2); }
  return s; // 无法解析则原样保留，不臆造
}
function normDuration(v){
  const s=String(v==null?'':v).trim();
  let m=s.match(/(\d+(?:\.\d+)?)\s*(小时|时|h)/i);
  if(m) return Math.round(parseFloat(m[1])*60);
  m=s.match(/(\d+(?:\.\d+)?)\s*(分钟|分|min)/i);
  if(m) return Math.round(parseFloat(m[1]));
  m=s.match(/^(一|两|半|\d+)\s*个?小时$/);
  if(m){ return {'一':60,'两':120,'半':30}[m[1]] || parseInt(m[1],10)*60; }
  m=s.match(/^(\d+(?:\.\d+)?)$/);
  if(m) return Math.round(parseFloat(m[1]));
  return s;
}

// 确保 skills 表存在（兼容旧库）
try{ db.exec(`CREATE TABLE IF NOT EXISTS skills (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, content TEXT, status TEXT DEFAULT 'active', created_at TEXT, updated_at TEXT)`); }catch(e){}
// 旧库平滑加列（幂等）
try{
  const exist = new Set(db.prepare('PRAGMA table_info(skills)').all().map(r=>r.name));
  ['scripts_json','related_json','source_sha','origin'].forEach(c=>{
    if(!exist.has(c)) db.exec('ALTER TABLE skills ADD COLUMN '+c+' TEXT');
  });
}catch(e){ console.error('skills 加列失败:',e.message); }

// ---------- 路由 ----------
async function handle(req,res){
  const u=new URL(req.url,'http://localhost');
  const p=u.pathname, method=req.method;
  if (method==='OPTIONS') return json(res,200,{});

  if (method==='GET' && p==='/api/healthz'){
    const counts={}; TABLES.forEach(t=>counts[t]=db.prepare(`SELECT count(*) n FROM ${q(t)}`).get().n);
    return json(res,200,{status:'ok',uptime_s:Math.round(process.uptime()),counts,
      ai_enabled:!!(getAIConfig().base_url&&getAIConfig().api_key)});
  }
  if (method==='POST' && p==='/api/auth/login'){
    const b=await readBody(req);
    if (!checkPwd(String(b.password||''))) return json(res,401,{detail:'密码错误'});
    return json(res,200,{token:signJWT(),expires_hours:JWT_TTL_H});
  }

  // ===== Agent 提示词（需 JWT）=====
  if (p==='/api/prompts' && method==='GET'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    db.exec(`CREATE TABLE IF NOT EXISTS prompts (key TEXT PRIMARY KEY, content TEXT, updated_at TEXT)`);
    const cur=getPrompts();
    const rows=db.prepare('SELECT key,updated_at FROM prompts').all();
    const meta={}; rows.forEach(r=>meta[r.key]=r.updated_at);
    const out={};
    PROMPT_KEYS.forEach(k=>{ out[k]={content:cur[k]||'',custom:!!meta[k],updated_at:meta[k]||''}; });
    // 附带资料（验收用例/README）供 Agent 管理页展示
    ['__tests','__readme'].forEach(k=>{
      const row=db.prepare('SELECT content FROM prompts WHERE key=?').get(k);
      if(row) out[k]={content:row.content||'',custom:false,updated_at:''};
    });
    return json(res,200,out);
  }
  if (p==='/api/prompts' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req);
    db.exec(`CREATE TABLE IF NOT EXISTS prompts (key TEXT PRIMARY KEY, content TEXT, updated_at TEXT)`);
    PROMPT_KEYS.forEach(k=>{
      if(b[k]!==undefined){
        const v=String(b[k]);
        if(v.trim()) db.prepare('INSERT OR REPLACE INTO prompts (key,content,updated_at) VALUES (?,?,?)').run(k,v,now());
      }
    });
    audit('api','update_prompts','prompts','1',JSON.stringify({keys:Object.keys(b)}));
    return json(res,200,{ok:true});
  }
  if (p==='/api/prompts/reset' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req), k=String(b.key||'all');
    db.exec(`CREATE TABLE IF NOT EXISTS prompts (key TEXT PRIMARY KEY, content TEXT, updated_at TEXT)`);
    if(k==='all') db.prepare("DELETE FROM prompts WHERE key IN ('intent','qa')").run();
    else if(k==='intent'||k==='qa') db.prepare('DELETE FROM prompts WHERE key=?').run(k);
    else if(PROMPT_KEYS.includes(k)) return json(res,400,{detail:'该提示词由套件导入，请用编辑保存修改，不能恢复默认'});
    else return json(res,400,{detail:'未知提示词'});
    audit('api','reset_prompts','prompts','1',k);
    return json(res,200,{ok:true,reset:k});
  }

  // ===== AI 模型配置（需 JWT）=====
  if (p==='/api/ai/config' && method==='GET'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const c=getAIConfig();
    return json(res,200,{base_url:c.base_url, model:c.model, context_max:c.context_max,
      api_key_masked:maskKey(c.api_key), api_key_set:!!c.api_key,
      source:c.source, updated_at:c.updated_at});
  }
  if (p==='/api/ai/config' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req), cur=getAIConfig();
    const base_url=String(b.base_url!==undefined?b.base_url:cur.base_url).trim().replace(/\/+$/,'');
    const model=String(b.model!==undefined?b.model:cur.model).trim();
    const cm=b.context_max!==undefined?parseInt(b.context_max,10):cur.context_max;
    const context_max=(cm>0&&cm<=2000000)?cm:300000;
    // 空 key = 不覆盖（脱敏回显的值原样提交也视为不覆盖）
    let api_key=cur.api_key;
    if(b.api_key!==undefined && String(b.api_key).trim()){
      const v=String(b.api_key).trim();
      if(!v.includes('…')) api_key=v;   // 含省略号 = 脱敏占位，忽略
    }
    if(!base_url) return json(res,400,{detail:'接口地址不能为空'});
    db.prepare('INSERT OR REPLACE INTO ai_config (id,base_url,api_key,model,context_max,updated_at) VALUES (1,?,?,?,?,?)')
      .run(base_url,api_key,model,context_max,now());
    audit('api','update_ai_config','ai_config','1',JSON.stringify({base_url,model,context_max,key_changed:api_key!==cur.api_key}));
    return json(res,200,{ok:true,base_url,model,context_max,api_key_masked:maskKey(api_key),key_changed:api_key!==cur.api_key});
  }
  if (p==='/api/ai/config/test' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req), cur=getAIConfig();
    const base_url=String(b.base_url!==undefined?b.base_url:cur.base_url).trim().replace(/\/+$/,'');
    const model=String(b.model!==undefined?b.model:cur.model).trim();
    let api_key=cur.api_key;
    if(b.api_key!==undefined && String(b.api_key).trim()){
      const v=String(b.api_key).trim();
      if(!v.includes('…')) api_key=v;
    }
    if(!base_url||!api_key||!model) return json(res,400,{detail:'请先填全接口地址、密钥和模型名'});
    const t0=Date.now();
    try{
      const r=await fetch(base_url+'/chat/completions',{
        method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+api_key},
        body:JSON.stringify({model,messages:[{role:'user',content:'只回复两个字：正常'}],max_tokens:10}),
        signal:AbortSignal.timeout(20000)
      });
      const d=await r.json();
      if(!r.ok) return json(res,200,{ok:false,status:r.status,error:(d.error&&d.error.message)||JSON.stringify(d).slice(0,200),ms:Date.now()-t0});
      const text=(d.choices?.[0]?.message?.content||'').trim();
      return json(res,200,{ok:true,reply:text.slice(0,50),ms:Date.now()-t0,model});
    }catch(e){ return json(res,200,{ok:false,error:String(e.message||e).slice(0,200),ms:Date.now()-t0}); }
  }

  // ===== APP Key 管理（需 JWT）=====
  if (p==='/api/keys' && method==='GET'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const rows=db.prepare('SELECT id,scope,created_at,revoked,note FROM api_key ORDER BY created_at DESC').all();
    return json(res,200,rows);
  }
  if (p==='/api/keys' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req);
    const scope = b.scope==='write' ? 'write' : 'read';
    return json(res,200,createApiKey(scope, String(b.note||'')));
  }
  if (p.startsWith('/api/keys/') && method==='DELETE'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const id=p.split('/')[3];
    const r=db.prepare('UPDATE api_key SET revoked=1 WHERE id=?').run(id);
    if(!r.changes) return json(res,404,{detail:'Key 不存在'});
    audit('api','revoke_key','api_key',id);
    return json(res,200,{revoked:1});
  }

  // ===== 技能管理（需 JWT）=====
  if (p==='/api/skills' && method==='GET'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    return json(res,200,db.prepare('SELECT * FROM skills ORDER BY updated_at DESC').all());
  }
  if (p==='/api/skills' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req);
    const name=String(b.name||'').toLowerCase().trim();
    if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)||name.length<3||name.length>64)
      return json(res,400,{detail:'技能名不合法（需 3-64 位小写字母/数字/连字符）'});
    if(db.prepare('SELECT 1 FROM skills WHERE name=?').get(name))
      return json(res,409,{detail:'同名技能已存在'});
    const content=String(b.content||'');
    const id='s_'+crypto.randomBytes(8).toString('hex');
    const source_sha=crypto.createHash('sha256').update(content).digest('hex');
    db.prepare(`INSERT INTO skills (id,name,description,content,status,source_sha,related_json,scripts_json,origin,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)`)
      .run(id,name,String(b.description||''),content,String(b.status||'active'),source_sha,
           String(b.related_json||'[]'),String(b.scripts_json||'{}'),
           String(b.origin||(b.agent_created?'agent':'manual')),now(),now());
    audit(String(b.origin||'manual'),'agent_create_skill','skills',id,
      JSON.stringify({created:[{table:'skills',record_id:id}],name,origin:b.origin||'manual'}));
    const aid=db.prepare('SELECT last_insert_rowid() id').get().id;
    return json(res,200,{id,audit_id:aid,name,source_sha});
  }
  if (p.startsWith('/api/skills/') && method==='PATCH'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const id=p.split('/')[3], b=await readBody(req);
    const cur=db.prepare('SELECT * FROM skills WHERE id=?').get(id);
    if(!cur) return json(res,404,{detail:'技能不存在'});
    const fields=['name','description','content','status','scripts_json','related_json'].filter(k=>b[k]!==undefined);
    if(fields.length){
      const sets=fields.map(k=>k+'=?').join(',');
      const vals=fields.map(k=>String(b[k]));
      const extra = fields.includes('content')
        ? ", source_sha='"+crypto.createHash('sha256').update(String(b.content)).digest('hex')+"'" : "";
      db.prepare(`UPDATE skills SET ${sets}${extra}, updated_at=? WHERE id=?`).run(...vals,now(),id);
    }
    return json(res,200,{updated:fields.length});
  }
  if (p.startsWith('/api/skills/') && method==='DELETE'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const id=p.split('/')[3];
    const r=db.prepare('DELETE FROM skills WHERE id=?').run(id);
    return r.changes?json(res,200,{deleted:1}):json(res,404,{detail:'技能不存在'});
  }

  // 同步接口（需 JWT）
  if (p==='/api/sync/pending' && method==='GET'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    return json(res,200,db.prepare(`SELECT id,table_name,record_id,op,payload,status,attempts FROM sync_queue WHERE status='pending' ORDER BY id`).all());
  }
  if (p==='/api/sync/ack' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req); const ids=b.ids||[];
    if(!ids.length) return json(res,200,{acked:0});
    db.prepare(`UPDATE sync_queue SET status='synced' WHERE id IN (${ids.map(()=>'?').join(',')})`).run(...ids);
    return json(res,200,{acked:ids.length});
  }
  if (p==='/api/sync/push' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req), t=b.table, recs=b.records||[];
    if(!TABLES.includes(t)||!Array.isArray(recs)) return json(res,400,{detail:'参数非法'});
    let pushed=0, skipped=0;
    recs.forEach(r=>{
      const rid=r.record_id; if(!rid) return;
      const pending=db.prepare(`SELECT count(*) n FROM sync_queue WHERE table_name=? AND record_id=? AND status='pending'`).get(t,rid).n;
      if(pending){ skipped++; return; }
      const c=cols(t), biz={};
      Object.entries(r).forEach(([k,v])=>{ if(c.includes(k)&&!META_COLS.has(k)) biz[k]=v; });
      const keys=[...Object.keys(biz),'record_id','_created_at','_updated_at','_origin','_sync_status','_content_hash'];
      const vals=[...Object.values(biz),rid,now(),now(),'workbuddy','synced',bizHash(biz)];
      db.prepare(`INSERT OR REPLACE INTO ${q(t)} (${keys.map(q).join(',')}) VALUES (${keys.map(()=>'?').join(',')})`).run(...vals);
      pushed++;
    });
    return json(res,200,{pushed,skipped_pending:skipped});
  }

  // 开放 API（X-API-Key）
  if (p.startsWith('/api/external/v1/')){
    const t=p.split('/')[4];
    if(!TABLES.includes(t)) return json(res,400,{detail:'未知表'});
    const scope=apiKeyScope(req);
    if(!scope) return json(res,401,{detail:'缺少或无效 X-API-Key'});
    if(method==='GET') return json(res,200,listRecords(t,{page:parseInt(u.searchParams.get('page')||'1'),size:Math.min(parseInt(u.searchParams.get('size')||'200'),500)}));
    if(method==='POST'){
      if(scope!=='write') return json(res,403,{detail:'该 Key 无写权限'});
      return json(res,200,addRecord(t,await readBody(req),'external'));
    }
  }

  // 业务 API（JWT）
  if (p.startsWith('/api/v1/')){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    // 特殊路由必须在表白名单校验之前：否则 seg[2]='meta'/'stats' 被误判未知表
    if(p==='/api/v1/meta/tables'&&method==='GET') return json(res,200,metaTables());
    if(p==='/api/v1/stats'&&method==='GET'){
      const s={}; TABLES.forEach(x=>s[x]=db.prepare(`SELECT count(*) n FROM ${q(x)}`).get().n); return json(res,200,s);
    }
    const seg=p.split('/').filter(Boolean); // api v1 [table] [rid?]
    const t=seg[2], rid=seg[3];
    if(!TABLES.includes(t)) return json(res,400,{detail:'未知表'});
    if(method==='GET' && !rid){
      let filters=null; try{ filters=u.searchParams.get('filters')?JSON.parse(u.searchParams.get('filters')):null; }catch(e){ return json(res,400,{detail:'filters 非法'}); }
      return json(res,200,listRecords(t,{page:parseInt(u.searchParams.get('page')||'1'),
        size:Math.min(parseInt(u.searchParams.get('size')||'200'),500),
        sort:u.searchParams.get('sort'),order:u.searchParams.get('order')||'desc',filters}));
    }
    if(method==='GET' && rid){
      const row=db.prepare(`SELECT * FROM ${q(t)} WHERE record_id=?`).get(rid);
      if(!row) return json(res,404,{detail:'记录不存在'});
      return json(res,200,Object.assign({},row,{_id:row['record_id']}));
    }
    if(method==='POST' && !rid) return json(res,200,addRecord(t,await readBody(req),'web'));
    if(method==='PATCH' && rid){
      const r=updateRecord(t,rid,await readBody(req),'web');
      return r?json(res,200,r):json(res,404,{detail:'记录不存在'});
    }
    if(method==='DELETE' && rid){
      const r=deleteRecord(t,rid,'web');
      return r?json(res,200,r):json(res,404,{detail:'记录不存在'});
    }
    if(method==='POST' && rid==='batch'){
      const b=await readBody(req), ops=b.ops||[];
      if(!Array.isArray(ops)||ops.length>100) return json(res,400,{detail:'ops 非法'});
      const results=ops.map(op=>{
        if(op.op==='add') return addRecord(t,op.fields||{},'batch');
        if(op.op==='update') return updateRecord(t,op.record_id,op.fields||{},'batch')||{record_id:op.record_id,skipped:true};
        if(op.op==='delete') return deleteRecord(t,op.record_id,'batch')||{record_id:op.record_id,skipped:true};
        return {skipped:true};
      });
      return json(res,200,{count:results.length,results});
    }
  }

  // AI 问答（可选）
  if (p==='/api/ai/chat' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    if(!getAIConfig().base_url||!getAIConfig().api_key) return json(res,503,{detail:'AI 未配置'});
    const b=await readBody(req), qText=String(b.question||'');
    const pr=getPrompts();
    const sys=(pr.system?pr.system+'\n\n---\n\n':'')+pr.qa;
    const messages=[{role:'system',content:sys+'\n\n'+buildContext(qText)},{role:'user',content:qText}];
    const resp=await callAI(messages,false);
    const data=await resp.json();
    const text=data.choices?.[0]?.message?.content||'（无返回）';
    return json(res,200,{answer:text});
  }
  // ===== Agent 对话（意图识别 + 确定性执行）=====
  if (p==='/api/agent/chat' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req);
    const message=String(b.message||'').trim();
    if(!message) return json(res,400,{detail:'消息不能为空'});
    let intent;
    if(b.preset_intent==='tool' && b.slots && b.slots.tool_call && b.slots.tool_call.tool){
      intent={intent:'tool',confidence:1,slots:b.slots,reason:'指定工具'};
    } else if(b.preset_intent && ['record','start','wrap','qa'].includes(b.preset_intent)){
      // 快捷指令：跳过 LLM，纯确定性
      intent={intent:b.preset_intent,confidence:1,slots:b.slots||{},reason:'快捷指令'};
      if(b.preset_intent==='record'){
        const qm=message.replace(/^(今天的计划是|记一下|记录一下|加个任务|新增)/,'').replace(/^[：:，,\s]+/,'').trim();
        intent.slots={target:'task',items:[{'任务名称':qm||message}]};
      }
    } else if(b.preset_intent==='create_skill' && b.slots && Object.keys(b.slots).length){
      // 已有明确槽位（如前端预览后重试）：直接用
      intent={intent:'create_skill',confidence:1,slots:b.slots,reason:'指定槽位'};
    } else {
      intent=await classifyIntent(message,b.history);
      if(b.preset_intent==='create_skill') intent.intent='create_skill';
    }
    const conf=Number(intent.confidence)||0;
    if(intent.intent==='record' && conf<0.6){
      return json(res,200,{ok:false,intent:'unclear',reply:'没太确定要记什么，能说得更具体一点吗？（比如「记一下：明天下午开会」）',need_confirm:true});
    }
    let reply='', data={}, audit_ids=[];
    if(intent.intent==='record'){
      const r=agentRecord(intent.slots);
      data.created=r.created;
      audit_ids=r.created.map(x=>x._audit_id).filter(Boolean);
      const lines=r.created.map((x,i)=>(i+1)+'. '+Object.entries(x).filter(([k,v])=>v&&typeof v==='string'&&['任务名称','事项','内容','状态','优先级','计划日','开始时间'].includes(k)).map(([,v])=>v).slice(0,3).join(' / '));
      const fallback='已记下 '+r.created.length+' 条：\n'+(lines.join('\n')||'（无）')+
            (r.errors.length?'\n未写入：'+r.errors.join('；'):'')+'\n数据已保存，稍后同步到其他端。';
      const rendered=await renderWithSkill('record',Object.assign({__raw:message},intent.slots||{}),
        {写入结果:r.created,未写入:r.errors}, fallback);
      reply=rendered||fallback;
    } else if(intent.intent==='start'){
      const t=computeTop3();
      data.top3=t.关键3件; data.summary={未完成:t.未完成总数,逾期:t.逾期数};
      const lines=t.关键3件.map((x,i)=>(i+1)+'. ['+x.优先级+'] '+x.任务+'（'+(x.状态||'待办')+'，'+x.分数+'分）');
      const fallback='当前最重要的 3 件事：\n'+(lines.join('\n')||'暂无逾期或今日到期事项')+
            '\n未完成 '+t.未完成总数+' 项，其中逾期 '+t.逾期数+' 项。';
      const rendered=await renderWithSkill('start',{__raw:message},
        {日期:dateToday(),关键3件:t.关键3件,未完成:t.未完成总数,逾期:t.逾期数}, fallback);
      reply=rendered||fallback;
    } else if(intent.intent==='wrap'){
      const rv=computeReview();
      data.summary=rv;
      const fallback=rv.一句话+'\n完成：'+(rv.今日完成.join('、')||'无')+'。';
      const rendered=await renderWithSkill('wrap',{__raw:message},rv,fallback);
      reply=rendered||fallback;
    } else if(intent.intent==='qa' && /APP.?Key|密钥|技能|提示词|模型配置|什么模型|哪个模型|模型名|同步队列|待同步|吊销|生成.{0,4}key/i.test(message)){
      // 保险：系统管理对象不在业务表里，qa 查不到 → 强制走工具
      intent=Object.assign({},intent,{intent:'tool',slots:{tool_call:{tool:'',args:{}}},reason:'qa转tool'});
      let tc=intent.slots.tool_call;
      if(!tc || !tc.tool) tc=toolByKeyword(message);
      const cfg=getAIConfig();
      const sys='从工具清单选一个最合适的工具完成请求，只输出严格JSON：{"tool":"工具名","args":{参数}}，不要解释。\n'+
        AGENT_TOOLS.map(t=>'- '+t.name+': '+t.desc+' | '+JSON.stringify(t.params)).join('\n')+'\n请求：'+message;
      if(!tc){ try{
        const r=await fetch(cfg.base_url.replace(/\/+$/,'')+'/chat/completions',{
          method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+cfg.api_key},
          body:JSON.stringify({model:cfg.model,response_format:{type:'json_object'},messages:[{role:'system',content:sys},{role:'user',content:message}]}),
          signal:AbortSignal.timeout(25000)});
        const d=await r.json();
        let raw=(d.choices?.[0]?.message?.content||'').replace(/```json|```/g,'').trim();
        const m=raw.match(/\{[\s\S]*\}/); tc=JSON.parse(m?m[0]:raw);
      }catch(e){} }
      if(tc && TOOL_NAMES.includes(tc.tool)){
        try{
          const result=await executeTool(tc.tool,tc.args||{});
          data={tool:tc.tool,result};
          reply=formatToolResult(tc.tool,result);
          return json(res,200,{ok:true,intent:'tool',confidence:conf,reply,data,audit_ids:result.audit_id?[result.audit_id]:[],undoable:!!result.audit_id});
        }catch(e){ reply='工具执行失败：'+String(e.message||e).slice(0,150); return json(res,200,{ok:false,intent:'tool',reply,data:{}}); }
      }
      reply='没找到合适的工具，能说具体点吗？'; return json(res,200,{ok:false,intent:'tool',reply,data:{}});
    } else if(intent.intent==='qa'){
      // 意图识别超时降级：直接自由回复，不再叠加大上下文查询（避免二次超时）
      if(intent.degraded){
        reply=(await freeReply(message,b.history)) || '我刚才没太理解你的意思，能再说具体一点吗？';
        data.answer=reply; data.degraded=true;
      } else {
        if(!getAIConfig().base_url||!getAIConfig().api_key) return json(res,503,{detail:'AI 未配置'});
        const sys=buildAgentSystem('qa',{__raw:message})+'\n\n'+getPrompts().qa;
        const resp=await callAI([{role:'system',content:sys+'\n\n'+buildContext(message)},{role:'user',content:message}],false);
        const d=await resp.json();
        reply=d.choices?.[0]?.message?.content||'（无返回）';
        data.answer=reply;
      }
    } else if(intent.intent==='tool'){
      // 全权限工具调用：LLM 选工具+参数，代码严格校验执行
      let tc=intent.slots&&intent.slots.tool_call;
      if(!tc || !tc.tool) tc=toolByKeyword(message);
      if(!tc){
        const cfg=getAIConfig();
        const sys='你是潮汐工作台的 Agent。从工具清单里选一个最合适的工具完成用户请求，只输出严格 JSON：{"tool":"工具名","args":{参数}}，不要解释文字。\n可用工具（名称:说明 参数）:\n'+
          AGENT_TOOLS.map(t=>'- '+t.name+': '+t.desc+' | 参数 '+JSON.stringify(t.params)).join('\n')+
          '\n用户当前请求：'+message;
        try{
          const r=await fetch(cfg.base_url.replace(/\/+$/,'')+'/chat/completions',{
            method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+cfg.api_key},
            body:JSON.stringify({model:cfg.model,response_format:{type:'json_object'},messages:[{role:'system',content:sys},{role:'user',content:message}]}),
            signal:AbortSignal.timeout(25000)});
          const d=await r.json();
          let raw=(d.choices?.[0]?.message?.content||'').replace(/```json|```/g,'').trim();
          console.error('[tool-select] raw:',raw.slice(0,300));
          const m=raw.match(/\{[\s\S]*\}/);
          tc=JSON.parse(m?m[0]:raw);
        }catch(e){ console.error('[tool-select] fail:',e.message); return json(res,200,{ok:false,intent:'tool',reply:'工具选择失败，请再说一次具体要做什么。'}); }
      }
      if(!tc || !TOOL_NAMES.includes(tc.tool)) return json(res,200,{ok:false,intent:'tool',reply:'没找到合适的工具，能说具体点吗？'});
      try{
        const result=await executeTool(tc.tool,tc.args||{});
        data={tool:tc.tool,result};
        // 工具结果直接格式化为可读文本，禁止 LLM 重写（否则会忽略事实自由发挥）
        reply=formatToolResult(tc.tool,result);
        return json(res,200,{ok:true,intent:'tool',confidence:conf,reply,data,audit_ids:result.audit_id?[result.audit_id]:[],undoable:!!result.audit_id});
      }catch(e){
        return json(res,200,{ok:false,intent:'tool',reply:'工具执行失败：'+String(e.message||e).slice(0,150)});
      }
    } else if(intent.intent==='create_skill'){
      return json(res,200,agentCreateSkill(intent.slots));
    } else {
      reply=(await freeReply(message,b.history)) ||
        '我是潮汐，你的时间与精力助手。可以说「开工」看今天重点，或直接告诉我今天的计划，我帮你记下来。';
    }
    return json(res,200,{ok:true,intent:intent.intent,confidence:conf,reply,data,audit_ids,undoable:audit_ids.length>0});
  }
  if (p==='/api/agent/undo' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const b=await readBody(req), aid=b.audit_id;
    const row=db.prepare('SELECT detail FROM audit_log WHERE id=?').get(aid);
    if(!row) return json(res,404,{detail:'未找到该操作'});
    let det; try{ det=JSON.parse(row.detail); }catch(e){ return json(res,400,{detail:'操作记录格式错误'}); }
    if(det.undone) return json(res,200,{ok:true,undone:0,note:'已撤销过'});
    let n=0;
    // 撤销新增：删除创建的记录
    (det.created||[]).forEach(c=>{
      if(c.table==='skills'){
        if(db.prepare('DELETE FROM skills WHERE id=?').run(c.record_id).changes) n++;
      } else if(TOOL_TABLES.includes(c.table) && deleteRecord(c.table,c.record_id,'agent',false)) n++;
    });
    // 撤销删除：恢复原记录（工具层 delete_record 记录 before 快照）
    if(det.before && TOOL_TABLES.includes(det.table) && det.record_id){
      const b=det.before, cs=cols(det.table);
      const ks=Object.keys(b).filter(k=>cs.includes(k));
      db.prepare(`INSERT OR REPLACE INTO ${q(det.table)} (${ks.map(q).join(',')}) VALUES (${ks.map(()=>'?').join(',')})`)
        .run(...ks.map(k=>b[k]));
      n++;
    }
    // 撤销提示词修改：恢复修改前内容
    if(det.key && det.prev_content!==undefined){
      if(det.prev_content===null) db.prepare('DELETE FROM prompts WHERE key=?').run(det.key);
      else db.prepare('INSERT OR REPLACE INTO prompts (key,content,updated_at) VALUES (?,?,?)').run(det.key,det.prev_content,now());
      n++;
    }
    // 撤销 Key 生成
    if(det.id && String(det.id).startsWith('k_')){
      if(db.prepare('UPDATE api_key SET revoked=1 WHERE id=?').run(det.id).changes) n++;
    }
    db.prepare('UPDATE audit_log SET detail=? WHERE id=?').run(JSON.stringify(Object.assign(det,{undone:1})),aid);
    return json(res,200,{ok:true,undone:n});
  }

  if (p==='/api/ai/actions/top3' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    const t=computeTop3();
    return json(res,200,{最关键3件:t.关键3件});
  }

  return json(res,404,{detail:'Not Found'});
}

// 简易限流：必须在唯一的请求入口里执行，不能另挂 'request' listener
// （createServer 回调与 on('request') 会对同一请求各触发一次 → 重复写响应 ERR_HTTP_HEADERS_SENT）
const buckets=new Map();
function rateLimited(req){
  const k=req.headers['x-api-key']||req.socket.remoteAddress;
  const arr=(buckets.get(k)||[]).filter(t=>Date.now()-t<60000);
  if(arr.length>=RATE_LIMIT) return true;
  arr.push(Date.now()); buckets.set(k,arr);
  return false;
}
const server=http.createServer((req,res)=>{
  if(rateLimited(req)) return json(res,429,{detail:'请求过于频繁，请稍后再试'});
  handle(req,res).catch(e=>{
    console.error(e);
    // 响应可能已发出（如流式中途失败），必须先检查，避免二次 writeHead
    if(!res.headersSent){ try{ json(res,500,{detail:String(e.message||e)}); }catch(_){} }
  });
});
server.listen(PORT,HOST,()=>console.log(`WorkBoard API listening ${HOST}:${PORT}`));
