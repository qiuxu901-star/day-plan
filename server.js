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
const RATE_LIMIT = parseInt(process.env.WB_RATE_LIMIT || '60', 10);
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
    const o={}; fields.forEach(f=>o[f]=r[f]); o.record_id=r['record_id']; return o;
  });
  return {items,total,page:opt.page,size:opt.size,
    has_more: offset+rows.length<total,
    next_page: offset+rows.length<total ? opt.page+1 : null};
}
function addRecord(table, payload, actor, enqueueSync=true){
  const c = cols(table);
  const biz = {};
  Object.entries(payload).forEach(([k,v])=>{
    if (c.includes(k) && !META_COLS.has(k) && v!==null && v!==undefined) biz[k]=v;
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
function updateRecord(table, rid, payload, actor, enqueueSync=true){
  const existing = db.prepare(`SELECT * FROM ${q(table)} WHERE record_id=?`).get(rid);
  if (!existing) return null;
  const c = cols(table);
  const biz = {};
  Object.entries(payload).forEach(([k,v])=>{
    if (c.includes(k) && !META_COLS.has(k) && v!==null && v!==undefined) biz[k]=v;
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
const AI_BASE=process.env.AI_BASE_URL||'', AI_KEY=process.env.AI_API_KEY||'', AI_MODEL=process.env.AI_MODEL||'';
function buildContext(question){
  // 全表轻量上下文：默认排除留痕表（227 行），按日期/关键词粗过滤
  const parts=[];
  const tables=['task','time','inbox','review','week','milestone'];
  tables.forEach(t=>{
    const rows=db.prepare(`SELECT * FROM ${q(t)} LIMIT 200`).all();
    if (!rows.length) return;
    const c=cols(t).filter(x=>!META_COLS.has(x));
    const lines=rows.slice(0,120).map(r=>c.map(k=>`${k}:${r[k]??''}`).join(' | '));
    parts.push(`【${LABELS[t]} ${rows.length}条】\n${lines.join('\n')}`);
  });
  return parts.join('\n\n').slice(0, 30000);
}
async function callAI(messages, stream){
  const resp = await fetch(AI_BASE+'/chat/completions',{
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+AI_KEY},
    body:JSON.stringify({model:AI_MODEL,messages,stream:!!stream})
  });
  return resp;
}

// ---------- 路由 ----------
async function handle(req,res){
  const u=new URL(req.url,'http://localhost');
  const p=u.pathname, method=req.method;
  if (method==='OPTIONS') return json(res,200,{});

  if (method==='GET' && p==='/api/healthz'){
    const counts={}; TABLES.forEach(t=>counts[t]=db.prepare(`SELECT count(*) n FROM ${q(t)}`).get().n);
    return json(res,200,{status:'ok',uptime_s:Math.round(process.uptime()),counts,
      ai_enabled:!!(AI_BASE&&AI_KEY)});
  }
  if (method==='POST' && p==='/api/auth/login'){
    const b=await readBody(req);
    if (!checkPwd(String(b.password||''))) return json(res,401,{detail:'密码错误'});
    return json(res,200,{token:signJWT(),expires_hours:JWT_TTL_H});
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
    const seg=p.split('/').filter(Boolean); // api v1 [table] [rid?]
    const t=seg[2], rid=seg[3];
    if(!TABLES.includes(t)) return json(res,400,{detail:'未知表'});
    if(p==='/api/v1/meta/tables'&&method==='GET') return json(res,200,metaTables());
    if(p==='/api/v1/stats'&&method==='GET'){
      const s={}; TABLES.forEach(x=>s[x]=db.prepare(`SELECT count(*) n FROM ${q(x)}`).get().n); return json(res,200,s);
    }
    if(method==='GET' && !rid){
      let filters=null; try{ filters=u.searchParams.get('filters')?JSON.parse(u.searchParams.get('filters')):null; }catch(e){ return json(res,400,{detail:'filters 非法'}); }
      return json(res,200,listRecords(t,{page:parseInt(u.searchParams.get('page')||'1'),
        size:Math.min(parseInt(u.searchParams.get('size')||'200'),500),
        sort:u.searchParams.get('sort'),order:u.searchParams.get('order')||'desc',filters}));
    }
    if(method==='GET' && rid){
      const row=db.prepare(`SELECT * FROM ${q(t)} WHERE record_id=?`).get(rid);
      return row?json(res,200,row):json(res,404,{detail:'记录不存在'});
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
    if(!AI_BASE||!AI_KEY) return json(res,503,{detail:'AI 未配置'});
    const b=await readBody(req), qText=String(b.question||'');
    const sys='你是工作计划台助手。只使用提供的记录回答，字段为空就说空，绝不编造任务、日期或数值。';
    const messages=[{role:'system',content:sys+'\n\n'+buildContext(qText)},{role:'user',content:qText}];
    const resp=await callAI(messages,false);
    const data=await resp.json();
    const text=data.choices?.[0]?.message?.content||'（无返回）';
    return json(res,200,{answer:text});
  }
  if (p==='/api/ai/actions/top3' && method==='POST'){
    if(!auth(req)) return json(res,401,{detail:'未登录'});
    // 确定性打分（与 analyze_plan.py 同口径）：P0=100/P1=60/P2=30，逾期每天+4(上限60)，今日+50，进行中+20
    const today=new Date().toISOString().slice(0,10);
    const rows=db.prepare(`SELECT * FROM ${q('task')}`).all()
      .filter(r=>r['状态']!=='已完成');
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
    return json(res,200,{最关键3件:cand});
  }

  return json(res,404,{detail:'Not Found'});
}

const server=http.createServer((req,res)=>{
  handle(req,res).catch(e=>{
    console.error(e);
    try{ json(res,500,{detail:String(e.message||e)}); }catch(_){}
  });
});
// 简易限流
const buckets=new Map();
server.on('request',(req,res)=>{
  const k=req.headers['x-api-key']||req.socket.remoteAddress;
  const arr=(buckets.get(k)||[]).filter(t=>Date.now()-t<60000);
  if(arr.length>=RATE_LIMIT){ return json(res,429,{detail:'请求过于频繁'}); }
  arr.push(Date.now()); buckets.set(k,arr);
});
server.listen(PORT,HOST,()=>console.log(`WorkBoard API listening ${HOST}:${PORT}`));
