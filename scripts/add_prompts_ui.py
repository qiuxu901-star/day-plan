#!/usr/bin/env python3
"""一次性注入：在 view-aiconfig 页底部追加 Agent 提示词编辑区。幂等。"""
import pathlib
SRC = pathlib.Path(__file__).resolve().parent.parent / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")
changes = []

# 1) 在 aiconfig section 的结尾 </section> 之前插入编辑区
if 'id="pmIntent"' not in html:
    ui = '''
    <!-- ===== Agent 提示词编辑 ===== -->
    <div class="panel" style="padding:20px;margin-top:18px">
      <div class="panel-head"><h2 style="margin:0 0 6px">Agent 提示词</h2><span class="hint" style="color:var(--muted);font-size:13px">控制 Agent 如何理解你的话、如何回答 · 保存即生效 · 可恢复默认</span></div>

      <div id="pmSaved" style="font-size:12px;color:var(--muted);margin:12px 0 18px"></div>

      <div style="margin-bottom:18px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
          <label style="font-size:13px;color:var(--ink);font-weight:600">① 意图识别提示词</label>
          <span id="pmIntentMeta" style="font-size:11px;color:var(--muted)"></span>
        </div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px">决定「开工 / 记计划 / 收工 / 问答 / 建技能」的判断与字段抽取。修改不当会导致记错库，请谨慎。</div>
        <textarea id="pmIntent" rows="12" spellcheck="false" style="width:100%;box-sizing:border-box;padding:12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink);font-family:ui-monospace,monospace;font-size:12px;line-height:1.6"></textarea>
        <button class="pm-reset" data-key="intent" style="margin-top:6px;padding:5px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--muted);cursor:pointer;font-size:12px">恢复默认</button>
      </div>

      <div style="margin-bottom:18px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
          <label style="font-size:13px;color:var(--ink);font-weight:600">② 问答系统提示词</label>
          <span id="pmQaMeta" style="font-size:11px;color:var(--muted)"></span>
        </div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px">控制 Agent 基于你的记录回答时的语气与规则（如"不编造"）。</div>
        <textarea id="pmQa" rows="5" spellcheck="false" style="width:100%;box-sizing:border-box;padding:12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink);font-family:ui-monospace,monospace;font-size:12px;line-height:1.6"></textarea>
        <button class="pm-reset" data-key="qa" style="margin-top:6px;padding:5px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--muted);cursor:pointer;font-size:12px">恢复默认</button>
      </div>

      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <button id="pmSave" style="padding:10px 20px;border:0;border-radius:10px;background:var(--sage);color:#fff;cursor:pointer;font-size:14px">保存提示词</button>
        <button id="pmResetAll" style="padding:10px 20px;border:1px solid var(--terra);border-radius:10px;background:var(--card);color:var(--terra);cursor:pointer;font-size:14px">全部恢复默认</button>
        <span id="pmMsg" style="font-size:13px"></span>
      </div>
    </div>
'''
    idx = html.find('<section class="view" id="view-aiconfig"')
    assert idx > 0, 'view-aiconfig 未找到'
    end = html.find('</section>', idx)
    html = html[:end] + ui + html[end:]
    changes.append('编辑区DOM')

# 2) JS 函数插在 loadAIConfig 之前
if 'function loadPrompts' not in html:
    js = '''
  function loadPrompts(){
    if(!$('pmIntent')) return;
    wbApi('/prompts').then(function(p){
      $('pmIntent').value=p.intent.content||'';
      $('pmQa').value=p.qa.content||'';
      $('pmIntentMeta').textContent=p.intent.custom?('已自定义 · '+(p.intent.updated_at||'').slice(0,16).replace('T',' ')):'使用默认';
      $('pmQaMeta').textContent=p.qa.custom?('已自定义 · '+(p.qa.updated_at||'').slice(0,16).replace('T',' ')):'使用默认';
      $('pmSaved').textContent='共 2 段提示词 · 意图识别（决定写入逻辑）与问答语气';
    }).catch(function(e){ $('pmSaved').textContent='读取失败：'+e.message; });
  }
  function pmFlash(text,bad){
    var m=$('pmMsg'); if(!m) return;
    m.textContent=text; m.style.color=bad?'var(--terra)':'var(--sage)';
  }
'''
    anchor = '  function loadAIConfig(){'
    assert anchor in html, 'loadAIConfig 锚点未找到'
    html = html.replace(anchor, js+anchor, 1); changes.append('JS函数')

    # wbOnViewChange 加 loadPrompts
    old = "    if(view==='aiconfig') loadAIConfig();"
    new = "    if(view==='aiconfig'){ loadAIConfig(); loadPrompts(); }"
    assert old in html, '视图加载锚点未找到'
    html = html.replace(old, new, 1); changes.append('视图加载')

    # initFeaturePages 里绑定（在 aiTest 绑定之后）
    bind = '''
    var pmSave=$('pmSave');
    if(pmSave) pmSave.onclick=function(){
      pmFlash('保存中…',false);
      wbApi('/prompts',{method:'POST',body:JSON.stringify({intent:$('pmIntent').value,qa:$('pmQa').value})})
        .then(function(){ pmFlash('✓ 已保存，下次对话即生效。',false); loadPrompts(); })
        .catch(function(e){ pmFlash('保存失败：'+e.message,true); });
    };
    Array.prototype.forEach.call(document.querySelectorAll('.pm-reset'),function(b){
      b.onclick=function(){
        var k=b.getAttribute('data-key');
        if(!window.confirm('确认恢复「'+(k==='intent'?'意图识别':'问答')+'」为默认提示词？')) return;
        wbApi('/prompts/reset',{method:'POST',body:JSON.stringify({key:k})})
          .then(function(){ pmFlash('✓ 已恢复默认。',false); loadPrompts(); })
          .catch(function(e){ pmFlash('恢复失败：'+e.message,true); });
      };
    });
    var pmAll=$('pmResetAll');
    if(pmAll) pmAll.onclick=function(){
      if(!window.confirm('确认把两段提示词都恢复为默认？你做的修改会丢失。')) return;
      wbApi('/prompts/reset',{method:'POST',body:JSON.stringify({key:'all'})})
        .then(function(){ pmFlash('✓ 已全部恢复默认。',false); loadPrompts(); })
        .catch(function(e){ pmFlash('恢复失败：'+e.message,true); });
    };
'''
    # 找 initFeaturePages 函数体结尾
    start = html.find('  function initFeaturePages(){')
    assert start > 0
    end = html.find('\n  }', start)
    assert end > 0
    html = html[:end] + '\n' + bind + html[end:]
    changes.append('事件绑定')

SRC.write_text(html, encoding='utf-8')
print('注入完成:', ' / '.join(changes) if changes else '无变化（已注入过）')
