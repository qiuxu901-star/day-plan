#!/usr/bin/env python3
"""把 workboard.fusion.html 改造成自托管版 workboard.html。

只动两处：① 删除平台 inject.js；② 替换 SDK 探测与 5 个 sdk 函数。
其余 3300+ 行业务代码原样保留。
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
OUT = REPO / "web" / "workboard.html"
OUT.parent.mkdir(parents=True, exist_ok=True)

html = SRC.read_text(encoding="utf-8")

# ① 删除 inject.js 注入脚本（含所在行的 data-page-node-id 属性）
n_inject = html.count('src="/page/page_comm/inject.js"')
html = re.sub(
    r'<head data-page-node-id="CMOpwAn0rkYMuLheSHF4kl">'
    r'<script data-page-node-id="GPJZGQe3lUIBjZqwFMxNbb" '
    r'src="/page/page_comm/inject.js"></script>',
    '<head>', html, count=1)

# ② 替换 SDK 探测 + 5 个函数（从 `/* ========== SDK 探测` 到 sdkGetSchema 结束）
start_marker = "  /* ========== SDK 探测 ========== */"
end_marker = "\n  /* ========== 智能识别"
start = html.index(start_marker)
end = html.index(end_marker, start)
old_block = html[start:end]

new_block = r'''  /* ========== 自托管数据层（替换平台 SDK，业务函数签名不变） ========== */
  var API_BASE = '/workboard/api';
  var TOKEN_KEY = 'wb_token';

  var DB2TABLE = {
    'bxluDICB3pU5oFPbnX4IAl':'task', 'AQ579PfPM4ahM3cAPQZVja':'review',
    'UQdz6a0OwZjymOgVNqXgRE':'milestone', '76VzPEVzq4WsgsVTVLoOZ7':'time',
    'm3kxJh6pHA7YRnIJoL9EjR':'week', 'Hs1rMXbiT6UUstrSFLoz6T':'log',
    '0j8YUMJbgCi635FVgC6LjL':'inbox', 'SP2n6UsLiB4GqA7GWUZeKW':'subtask'
  };
  var ONLINE = false;
  var SCHEMA_CACHE = {};

  function api(path, opts){
    opts = opts || {};
    opts.headers = Object.assign(
      {'Content-Type':'application/json',
       'Authorization':'Bearer ' + (localStorage.getItem(TOKEN_KEY) || '')},
      opts.headers || {});
    return fetch(API_BASE + path, opts).then(function(r){
      if (r.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        wbShowLogin();
        throw new Error('请先登录');
      }
      if (!r.ok) return r.json().then(function(e){
        throw new Error(e.detail || ('HTTP ' + r.status));
      }).catch(function(){ throw new Error('HTTP ' + r.status); });
      return r.json();
    });
  }
  function unwrapProps(props){
    var out = {};
    Object.keys(props || {}).forEach(function(k){
      var v = props[k];
      if (v && typeof v === 'object' && !Array.isArray(v)) {
        out[k] = (v.text !== undefined) ? v.text
               : (v.select !== undefined) ? v.select
               : (v.date !== undefined) ? v.date
               : (v.number !== undefined) ? v.number : v;
      } else out[k] = v;
    });
    return out;
  }
  function wrapProps(fields){
    var out = {};
    Object.keys(fields || {}).forEach(function(k){
      var v = fields[k];
      if (v === null || v === undefined) return;
      if (typeof v === 'number') out[k] = {number:v};
      else out[k] = {text:String(v)};
    });
    return out;
  }

  /* 以下五个函数签名与原平台 SDK 完全一致，业务代码零改动 */
  function queryPage(dbId, cursor){
    var table = DB2TABLE[dbId] || 'log';
    var page = 1;
    if (cursor) {
      var m = String(cursor).match(/page=(\d+)/);
      page = m ? parseInt(m[1],10) : 2;
    }
    return api('/v1/' + table + '?page=' + page + '&size=200')
      .then(function(d){
        return {results: d.items, hasMore: !!d.has_more,
                nextCursor: d.has_more ? 'page=' + (page+1) : null};
      });
  }
  function sdkAddRecord(dbId, props){
    var table = DB2TABLE[dbId] || 'log';
    return api('/v1/' + table, {method:'POST',
      body: JSON.stringify(unwrapProps(props))});
  }
  function sdkUpdateRecord(dbId, rid, props){
    var table = DB2TABLE[dbId] || 'log';
    return api('/v1/' + table + '/' + encodeURIComponent(rid),
      {method:'PATCH', body: JSON.stringify(unwrapProps(props))});
  }
  function sdkDeleteRecord(dbId, rid){
    var table = DB2TABLE[dbId] || 'log';
    return api('/v1/' + table + '/' + encodeURIComponent(rid),
      {method:'DELETE'});
  }
  function sdkGetSchema(dbId){
    var table = DB2TABLE[dbId] || 'log';
    if (SCHEMA_CACHE[table]) return Promise.resolve(SCHEMA_CACHE[table]);
    return api('/v1/meta/tables').then(function(all){
      var s = all[table] || {properties:[]};
      SCHEMA_CACHE[table] = s;
      return s;
    });
  }

  /* ========== 登录浮层（自托管新增） ========== */
  function wbShowLogin(){
    if (document.getElementById('wbLogin')) return;
    var d = document.createElement('div');
    d.id = 'wbLogin';
    d.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(20,18,16,.72);display:flex;align-items:center;justify-content:center';
    d.innerHTML = '<div style="background:#faf7f2;border-radius:16px;padding:32px;width:min(360px,90vw);box-shadow:0 20px 60px rgba(0,0,0,.3);color:#29241f">' +
      '<div style="font-size:20px;font-weight:700;margin-bottom:6px">工作计划台</div>' +
      '<div style="font-size:13px;color:#8a8076;margin-bottom:20px">登录后查看你的任务与时间</div>' +
      '<input id="wbPwd" type="password" placeholder="访问密码" style="width:100%;box-sizing:border-box;padding:12px 14px;border:1px solid #ddd3c6;border-radius:10px;font-size:15px;background:#fff">' +
      '<div id="wbLoginErr" style="color:#c0392b;font-size:12px;min-height:18px;margin-top:8px"></div>' +
      '<button id="wbLoginBtn" style="width:100%;padding:12px;border:0;border-radius:10px;background:#8a6f52;color:#fff;font-size:15px;font-weight:600;margin-top:6px;cursor:pointer">进入</button></div>';
    document.body.appendChild(d);
    function submit(){
      var pwd = document.getElementById('wbPwd').value;
      fetch(API_BASE + '/auth/login', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({password:pwd})})
      .then(function(r){ return r.ok ? r.json() : Promise.reject(new Error('密码错误')); })
      .then(function(data){
        localStorage.setItem(TOKEN_KEY, data.token);
        d.remove();
        location.reload();
      }).catch(function(e){
        document.getElementById('wbLoginErr').textContent = e.message;
      });
    }
    document.getElementById('wbLoginBtn').onclick = submit;
    document.getElementById('wbPwd').onkeydown = function(e){
      if (e.key === 'Enter') submit();
    };
    document.getElementById('wbPwd').focus();
  }

  function wbBoot(){
    if (!localStorage.getItem(TOKEN_KEY)) { wbShowLogin(); return; }
    api('/healthz').then(function(){ ONLINE = true; })
      .catch(function(){ ONLINE = false; wbShowLogin(); });
  }
  function wbStart(){
    wbBoot(); // 无 token 时弹登录；有 token 时异步探活
    var waited = 0;
    var t = setInterval(function(){
      waited++;
      if (ONLINE || waited > 30) { clearInterval(t); init(); }
    }, 100);
  }
'''
html = html[:start] + new_block + html[end:]

# ③ init 里原来的离线报错改为触发登录（若存在该文案）
html = html.replace(
    "'数据服务未连接。请通过 WorkBuddy 资料库环境打开本页面，数据才能在线存储与多端同步。'",
    "'数据服务未连接，请检查网络后刷新。'")

# ④ 替换启动入口：先鉴权探活，再 init，避免 ONLINE 异步竞态
old_boot = ("  if (document.readyState === 'loading'){ "
            "document.addEventListener('DOMContentLoaded', init); } else { init(); }")
new_boot = ("  if (document.readyState === 'loading'){\n"
            "    document.addEventListener('DOMContentLoaded', wbStart);\n"
            "  } else { wbStart(); }")
if old_boot in html:
    html = html.replace(old_boot, new_boot, 1)
else:
    raise SystemExit("启动入口未匹配，请检查源文件")

OUT.write_text(html, encoding="utf-8")
print(f"inject.js 移除: {n_inject} 处")
print(f"SDK 区段替换: {len(old_block)} -> {len(new_block)} 字符")
print(f"输出: {OUT} ({len(html)} 字节)")
