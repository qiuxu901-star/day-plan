#!/usr/bin/env python3
"""给源文件插入三个页面的 JS 逻辑（幂等）。"""
import pathlib
REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")

# 顺手修掉源文件里过时的离线提示
html = html.replace(
    "'数据服务未连接。请通过 WorkBuddy 资料库环境打开本页面，数据才能在线存储与多端同步。'",
    "'数据服务未连接，请检查网络后刷新。'")

js = r'''
  /* ========== APP Key / AI生成Key / 技能管理 ========== */
  function wbApi(path, opts){
    opts = opts || {};
    opts.headers = Object.assign({'Content-Type':'application/json',
      'Authorization':'Bearer '+(localStorage.getItem(TOKEN_KEY)||'')}, opts.headers||{});
    return fetch(API_BASE + path, opts).then(function(r){
      if(r.status===401){ localStorage.removeItem(TOKEN_KEY); wbShowLogin(); throw new Error('请先登录'); }
      if(!r.ok) return r.json().then(function(e){throw new Error(e.detail||('HTTP '+r.status));})
                              .catch(function(){throw new Error('HTTP '+r.status);});
      return r.json();
    });
  }
  function escHtml(s){
    return String(s==null?'':s).replace(/[&<>"']/g,function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function loadKeys(){
    if(!$('keyList')) return;
    wbApi('/keys').then(function(rows){
      var box=$('keyList'); box.innerHTML='';
      if(!rows.length){ box.innerHTML='<div style="color:#9a9086;font-size:13px">还没有 Key，生成一个吧。</div>'; return; }
      rows.forEach(function(k){
        var d=document.createElement('div');
        d.style.cssText='display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid #e6ddd2;border-radius:10px;background:#fff;flex-wrap:wrap';
        var status = k.revoked ? '<span style="color:#c0392b">已吊销</span>' : '<span style="color:#5a8a5a">有效</span>';
        d.innerHTML = '<code style="font-size:12px">'+escHtml(k.id)+'</code>'+
          '<span style="font-size:12px;color:#8a6f52">'+escHtml(k.scope)+'</span>'+status+
          '<span style="font-size:12px;color:#9a9086;flex:1">'+escHtml(k.note||'')+'</span>'+
          '<span style="font-size:11px;color:#b0a69b">'+escHtml((k.created_at||'').slice(0,10))+'</span>'+
          (k.revoked?'':'<button data-kid="'+escHtml(k.id)+'" class="keyRevoke" style="padding:4px 10px;border:1px solid #d9a8a0;border-radius:6px;background:#fff;color:#c0392b;cursor:pointer;font-size:12px">吊销</button>');
        box.appendChild(d);
      });
      Array.prototype.forEach.call(box.querySelectorAll('.keyRevoke'), function(b){
        b.onclick=function(){
          if(!window.confirm('确定吊销这个 Key？')) return;
          wbApi('/keys/'+encodeURIComponent(b.getAttribute('data-kid')),{method:'DELETE'})
            .then(function(){ toast('已吊销'); loadKeys(); }).catch(function(e){ toast(e.message,true); });
        };
      });
    }).catch(function(e){ toast(e.message,true); });
  }

  function loadSkills(){
    if(!$('skillList')) return;
    wbApi('/skills').then(function(rows){
      var box=$('skillList'); box.innerHTML='';
      if(!rows.length){ box.innerHTML='<div style="color:#9a9086;font-size:13px">还没有技能，点右上角新建。</div>'; return; }
      rows.forEach(function(s){
        var d=document.createElement('div');
        d.style.cssText='padding:14px;border:1px solid #e6ddd2;border-radius:12px;background:#fff;cursor:pointer;transition:.2s';
        var scripts=[]; try{ scripts=Object.keys(JSON.parse(s.scripts_json||'{}')); }catch(e){}
        var related=[]; try{ related=JSON.parse(s.related_json||'[]'); }catch(e){}
        var bodyLen=(s.content||'').length;
        var warn = (s.name==='workboard-database-write')
          ? '<div style="font-size:11px;color:#b44d43;margin-top:6px">⚠ 待校准：正文写平台旧版，双轨期保留原文</div>' : '';
        d.innerHTML='<div style="font-weight:600;margin-bottom:6px">'+escHtml(s.name)+'</div>'+
          '<div style="font-size:12px;color:#9a9086;line-height:1.5">'+escHtml(s.description||'（无描述）')+'</div>'+
          '<div style="font-size:11px;color:#627a67;margin-top:6px">正文 '+bodyLen+' 字 · 脚本 '+scripts.length+' 个</div>'+
          (related.length?'<div style="font-size:11px;color:#8a6f52;margin-top:4px">相关：'+related.map(function(r){return escHtml(r.replace("workboard-",""));}).join('、')+'</div>':'')+
          warn+
          '<div style="font-size:11px;color:#b0a69b;margin-top:8px">更新 '+(s.updated_at||'').slice(0,10)+'</div>';
        d.onclick=function(){ openSkillEditor(s); };
        box.appendChild(d);
      });
    }).catch(function(e){ toast(e.message,true); });
  }
  var editingSkillId=null;
  function openSkillEditor(s){
    editingSkillId = s ? s.id : null;
    $('skillEditTitle').textContent = s ? '编辑技能' : '新建技能';
    $('skillName').value = s ? (s.name||'') : '';
    $('skillDesc').value = s ? (s.description||'') : '';
    $('skillContent').value = s ? (s.content||'') : '';
    var preview=$('skillScripts');
    if(preview){
      var files=[]; try{ files=Object.keys(JSON.parse((s&&s.scripts_json)||'{}')); }catch(e){}
      preview.innerHTML = files.length
        ? '<b style="color:#8a6f52">附带脚本：</b>'+files.map(function(f){return escHtml(f);}).join(' · ')
        : '';
    }
    $('skillEditor').style.display='flex';
  }

  function wbOnViewChange(view){
    if(view==='keys') loadKeys();
    if(view==='skills') loadSkills();
  }

  function initFeaturePages(){
    var create=$('keyCreate');
    if(create) create.onclick=function(){
      var scope=$('keyScope').value, note=$('keyNote').value.trim();
      wbApi('/keys',{method:'POST',body:JSON.stringify({scope:scope,note:note})})
        .then(function(r){
          $('keyNewVal').textContent=r.key; $('keyNew').style.display='block';
          $('keyNote').value=''; toast('Key 已生成'); loadKeys();
        }).catch(function(e){ toast(e.message,true); });
    };
    var copy=$('keyCopy');
    if(copy) copy.onclick=function(){
      var t=$('keyNewVal').textContent;
      if(navigator.clipboard) navigator.clipboard.writeText(t).then(function(){toast('已复制');});
      else toast('请手动复制',true);
    };
    var snew=$('skillNew');
    if(snew) snew.onclick=function(){ openSkillEditor(null); };
    var scancel=$('skillCancel');
    if(scancel) scancel.onclick=function(){ $('skillEditor').style.display='none'; };
    var ssave=$('skillSave');
    if(ssave) ssave.onclick=function(){
      var body={name:$('skillName').value.trim(),description:$('skillDesc').value.trim(),content:$('skillContent').value};
      if(!body.name){ toast('名称不能为空',true); return; }
      var path = editingSkillId ? '/skills/'+encodeURIComponent(editingSkillId) : '/skills';
      wbApi(path,{method:editingSkillId?'PATCH':'POST',body:JSON.stringify(body)})
        .then(function(){ $('skillEditor').style.display='none'; toast('已保存'); loadSkills(); })
        .catch(function(e){ toast(e.message,true); });
    };
    // 切到对应视图时加载（由 switchView 内调用 wbOnViewChange）
  }

'''
marker = " /* ========== 视图切换 ========== */"
assert marker in html
if 'function initFeaturePages()' not in html:
    html = html.replace(marker, js + marker, 1)
# 在 init 末尾调用（挂在 refreshAll 后）
if 'initFeaturePages();' not in html:
    html = html.replace("    refreshAll();\n    initSelects()", "    refreshAll();\n    initFeaturePages();\n    initSelects()", 1)

# switchView 内调用 wbOnViewChange
if 'wbOnViewChange(view)' not in html:
    old_sv = "    window.scrollTo({ top: 0, behavior: 'smooth' });\n  }"
    new_sv = "    window.scrollTo({ top: 0, behavior: 'smooth' });\n    if (typeof wbOnViewChange === 'function') wbOnViewChange(view);\n  }"
    if old_sv in html: html = html.replace(old_sv,new_sv,1)

SRC.write_text(html, encoding="utf-8")
print("三个页面的 JS 逻辑已插入")
