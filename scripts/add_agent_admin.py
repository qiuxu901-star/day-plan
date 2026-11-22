#!/usr/bin/env python3
"""一次性注入：把提示词编辑区从模型配置页迁到独立 Agent 管理页，并增强。幂等。"""
import pathlib
SRC = pathlib.Path(__file__).resolve().parent.parent / 'web' / 'workboard.fusion.html'
html = SRC.read_text(encoding='utf-8')
changes = []

# 1) 从 aiconfig 中删除旧提示词编辑区
if 'id="pmIntent"' in html and 'id="view-agentadmin"' not in html:
    start = html.find('    <!-- ===== Agent 提示词编辑 ===== -->')
    end = html.find('</section>', start)
    if start > 0 and end > start:
        html = html[:start] + html[end:]
        changes.append('移除旧提示词区')

# 2) 侧栏导航（在 aiconfig 之后）
if 'data-view="agentadmin"' not in html:
    old = '''    <button class="nav-item" data-view="aiconfig"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 3-2 4-2 6H7c0-2-2-3-2-6a7 7 0 0 1 7-7z"/><path d="M9 19h6m-5 3h4"/></svg>模型配置</button>
  </nav>'''
    new = '''    <button class="nav-item" data-view="aiconfig"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 3-2 4-2 6H7c0-2-2-3-2-6a7 7 0 0 1 7-7z"/><path d="M9 19h6m-5 3h4"/></svg>模型配置</button>
    <button class="nav-item" data-view="agentadmin"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 9h6M9 13h6M9 17h3"/></svg>Agent 管理</button>
  </nav>'''
    assert old in html, '侧栏锚点'
    html = html.replace(old, new, 1); changes.append('侧栏导航')

# 3) 移动导航
if html.count('data-view="agentadmin"') < 2:
    old = '''  <button data-view="aiconfig"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 3-2 4-2 6H7c0-2-2-3-2-6a7 7 0 0 1 7-7z"/><path d="M9 19h6m-5 3h4"/></svg>模型</button>
</nav>'''
    new = '''  <button data-view="aiconfig"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 3-2 4-2 6H7c0-2-2-3-2-6a7 7 0 0 1 7-7z"/><path d="M9 19h6m-5 3h4"/></svg>模型</button>
  <button data-view="agentadmin"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 9h6M9 13h6M9 17h3"/></svg>Agent</button>
</nav>'''
    assert old in html, '移动导航锚点'
    html = html.replace(old, new, 1); changes.append('移动导航')

# 4) VIEW_TITLES
if "agentadmin:'Agent 管理" not in html:
    old = "aiconfig:'模型配置 · 接上你的 AI'};"
    new = "aiconfig:'模型配置 · 接上你的 AI', agentadmin:'Agent 管理 · 提示词与技能'};"
    assert old in html
    html = html.replace(old, new, 1); changes.append('VIEW_TITLES')

# 5) 新 section
if 'id="view-agentadmin"' not in html:
    section = '''
  <!-- ===== Agent 管理（独立页） ===== -->
  <section class="view" id="view-agentadmin" style="padding:24px;max-width:1100px">
    <div class="panel" style="padding:20px">
      <div class="panel-head"><h2 style="margin:0 0 6px">Agent 提示词</h2><span class="hint" style="color:var(--muted);font-size:13px">6 段提示词 · 保存即生效 · 主系统词/补充词来自 v1.0 套件</span></div>

      <div id="pmTabs" style="display:flex;gap:8px;flex-wrap:wrap;margin:14px 0"></div>
      <div id="pmDesc" style="font-size:12px;color:var(--muted);margin-bottom:10px;line-height:1.6"></div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span id="pmMeta" style="font-size:11px;color:var(--muted);flex:1"></span>
        <button id="pmResetCur" style="padding:5px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--muted);cursor:pointer;font-size:12px">恢复默认</button>
      </div>
      <textarea id="pmText" rows="16" spellcheck="false" style="width:100%;box-sizing:border-box;padding:12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink);font-family:ui-monospace,monospace;font-size:12px;line-height:1.6"></textarea>
      <div style="display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap">
        <button id="pmSave" style="padding:10px 20px;border:0;border-radius:10px;background:var(--sage);color:#fff;cursor:pointer;font-size:14px">保存提示词</button>
        <span id="pmMsg" style="font-size:13px"></span>
      </div>
    </div>

    <div class="panel" style="padding:20px;margin-top:18px">
      <div class="panel-head"><h2 style="margin:0 0 6px">技能库</h2><span class="hint" style="color:var(--muted);font-size:13px">6 个 v1.0 Skills · 点击查看正文与附带参考规则</span></div>
      <div id="kitSkillList" style="display:flex;flex-direction:column;gap:8px;margin-top:14px"></div>
      <div id="kitRefBox" style="display:none;margin-top:14px;padding:14px;border:1px solid var(--line);border-radius:11px;background:var(--paper)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <b id="kitRefTitle" style="font-size:13px;color:var(--ink)"></b>
          <button id="kitRefClose" style="border:0;background:none;color:var(--muted);cursor:pointer;font-size:16px">×</button>
        </div>
        <div id="kitRefContent" style="font-size:12px;color:var(--muted);line-height:1.7;white-space:pre-wrap;max-height:340px;overflow:auto"></div>
      </div>
    </div>

    <div class="panel" style="padding:20px;margin-top:18px">
      <div class="panel-head"><h2 style="margin:0 0 6px">验收用例</h2><span class="hint" style="color:var(--muted);font-size:13px">18 条事实红线测试 · 用于验证 Agent 是否可靠</span></div>
      <div id="kitTests" style="font-size:12px;color:var(--muted);line-height:1.7;white-space:pre-wrap;max-height:300px;overflow:auto;margin-top:12px"></div>
    </div>
  </section>
'''
    idx = html.find('<section class="view" id="view-aiconfig"')
    assert idx > 0
    end = html.find('</section>', idx) + len('</section>')
    html = html[:end] + '\n' + section + html[end:]
    changes.append('section')

# 6) JS：替换旧的 loadPrompts，新增 Agent 管理逻辑
if 'function initAgentAdmin' not in html:
    js = '''
  var PM_KEYS=[['intent','意图识别 · JSON','结构化分类器：判断开工/记计划/收工/问答，并抽取字段'],
    ['system','主系统词 · 套件','时间与精力管理 Agent 的角色、事实红线与思考顺序'],
    ['qa','问答词','基于记录回答时的语气与规则'],
    ['strategic','军师模式 · 套件','目标优先级、取舍与机会成本判断'],
    ['coach','教练模式 · 套件','开工/推进/阻塞时的最小行动拆解'],
    ['generator','技能生成 · 套件','把可重复流程写成 SKILL.md 的元提示词']];
  var pmCur='intent', pmData={};
  function pmSelect(k){
    pmCur=k;
    var meta=pmData[k]||{};
    var box=$('pmTabs'); if(!box) return;
    box.innerHTML='';
    PM_KEYS.forEach(function(p){
      var b=document.createElement('button');
      b.textContent=p[0]===pmCur?'● '+p[1]:p[1];
      b.style.cssText='padding:7px 13px;border:1px solid '+(p[0]===pmCur?'var(--sage)':'var(--line)')+';border-radius:9px;background:'+(p[0]===pmCur?'var(--sage-soft)':'var(--card)')+';color:'+(p[0]===pmCur?'var(--sage)':'var(--muted)')+';cursor:pointer;font-size:12px';
      b.onclick=function(){ pmSelect(p[0]); };
      box.appendChild(b);
    });
    var desc=PM_KEYS.filter(function(p){return p[0]===k;})[0];
    $('pmDesc').textContent=desc?desc[2]:'';
    $('pmText').value=meta.content||'';
    $('pmMeta').textContent=meta.custom?('已自定义 · '+(meta.updated_at||'').slice(0,16).replace('T',' ')):'使用默认/套件原版';
    $('pmResetCur').style.display=meta.custom?'':'none';
    $('pmMsg').textContent='';
  }
  function loadPrompts(){
    if(!$('pmTabs')) return;
    wbApi('/prompts').then(function(p){
      pmData=p; pmSelect(pmCur);
    }).catch(function(e){ $('pmDesc').textContent='读取失败：'+e.message; });
  }
  function pmFlash(text,bad){
    var m=$('pmMsg'); if(!m) return;
    m.textContent=text; m.style.color=bad?'var(--terra)':'var(--sage)';
  }
  function loadKitSkills(){
    if(!$('kitSkillList')) return;
    wbApi('/skills').then(function(rows){
      var box=$('kitSkillList'); box.innerHTML='';
      rows.forEach(function(s){
        var d=document.createElement('div');
        d.style.cssText='padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:var(--card);cursor:pointer;transition:.2s';
        var refs=[]; try{ refs=JSON.parse(s.related_json||'[]'); }catch(e){}
        d.innerHTML='<div style="font-weight:600;font-size:13px;color:var(--ink)">'+escHtml(s.name)+'</div>'+
          '<div style="font-size:12px;color:var(--muted);margin-top:4px;line-height:1.5">'+escHtml(s.description||'（无描述）')+'</div>'+
          '<div style="font-size:11px;color:var(--sage);margin-top:5px">正文 '+(s.content||'').length+' 字 · 附带参考 '+refs.length+' 份 · 点击查看</div>';
        d.onclick=function(){ showKitSkill(s); };
        box.appendChild(d);
      });
    }).catch(function(e){ $('kitSkillList').textContent='读取失败：'+e.message; });
  }
  function showKitSkill(s){
    var box=$('kitRefBox');
    $('kitRefTitle').textContent=s.name+' · 正文与附带参考';
    var txt='【SKILL.md 正文】\\n'+(s.content||'');
    var refs=[]; try{ refs=JSON.parse(s.related_json||'[]'); }catch(e){}
    if(refs.length) txt+='\\n\\n【附带参考规则】'+refs.join('、')+'（见套件 reference/ 目录）';
    $('kitRefContent').textContent=txt;
    box.style.display='block';
  }
  function initAgentAdmin(){
    var save=$('pmSave');
    if(save) save.onclick=function(){
      var body={}; body[pmCur]=$('pmText').value;
      pmFlash('保存中…',false);
      wbApi('/prompts',{method:'POST',body:JSON.stringify(body)})
        .then(function(){ pmFlash('✓ 已保存，下次对话即生效。',false); loadPrompts(); })
        .catch(function(e){ pmFlash('保存失败：'+e.message,true); });
    };
    var reset=$('pmResetCur');
    if(reset) reset.onclick=function(){
      if(!window.confirm('确认恢复「'+pmCur+'」为默认？')) return;
      wbApi('/prompts/reset',{method:'POST',body:JSON.stringify({key:pmCur})})
        .then(function(){ pmFlash('✓ 已恢复默认。',false); loadPrompts(); })
        .catch(function(e){ pmFlash('恢复失败：'+e.message,true); });
    };
    var close=$('kitRefClose');
    if(close) close.onclick=function(){ $('kitRefBox').style.display='none'; };
    wbApi('/prompts',{method:'GET'}).then(function(p){
      var t=p.__tests; if(t&&t.content) $('kitTests').textContent=t.content.slice(0,4000);
    }).catch(function(){});
  }
'''
    anchor = '  function loadAIConfig(){'
    assert anchor in html
    html = html.replace(anchor, js+anchor, 1); changes.append('JS函数')

    # wbOnViewChange: 旧的 aiconfig 只 loadAIConfig，agentadmin 加载新页
    html = html.replace("    if(view==='aiconfig'){ loadAIConfig(); loadPrompts(); }",
                        "    if(view==='aiconfig') loadAIConfig();\n    if(view==='agentadmin'){ loadPrompts(); loadKitSkills(); }",1)
    changes.append('视图加载')

    # initFeaturePages 里调用 initAgentAdmin
    start = html.find('  function initFeaturePages(){')
    end = html.find('\n  }', start)
    html = html[:end] + '\n    initAgentAdmin();' + html[end:]
    changes.append('初始化调用')

SRC.write_text(html, encoding='utf-8')
print('注入完成:', ' / '.join(changes) if changes else '无变化')
