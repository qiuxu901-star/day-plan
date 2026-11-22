#!/usr/bin/env python3
"""一次性注入：AI 模型配置页（源文件→成品由 make_h5.py 生成）。幂等。"""
import pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")
changes = []

# 1) 侧栏导航（在 skills 之后）
old = '''    <button class="nav-item" data-view="skills"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>技能管理</button>
  </nav>'''
new = '''    <button class="nav-item" data-view="skills"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>技能管理</button>
    <button class="nav-item" data-view="aiconfig"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 3-2 4-2 6H7c0-2-2-3-2-6a7 7 0 0 1 7-7z"/><path d="M9 19h6m-5 3h4"/></svg>模型配置</button>
  </nav>'''
if 'data-view="aiconfig"' not in html:
    assert old in html, '侧栏导航锚点未找到'
    html = html.replace(old, new, 1); changes.append('侧栏导航')

# 2) 移动导航
old = '''  <button data-view="skills"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>技能</button>
</nav>'''
new = '''  <button data-view="skills"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>技能</button>
  <button data-view="aiconfig"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 3-2 4-2 6H7c0-2-2-3-2-6a7 7 0 0 1 7-7z"/><path d="M9 19h6m-5 3h4"/></svg>模型</button>
</nav>'''
if html.count('data-view="aiconfig"') < 2:
    assert old in html, '移动导航锚点未找到'
    html = html.replace(old, new, 1); changes.append('移动导航')

# 3) VIEW_TITLES 加键
if "aiconfig:'模型配置" not in html:
    old = "skills:'技能管理 · 岛屿'};"
    new = "skills:'技能管理 · 岛屿', aiconfig:'模型配置 · 接上你的 AI'};"
    assert old in html, 'VIEW_TITLES 锚点未找到'
    html = html.replace(old, new, 1); changes.append('VIEW_TITLES')

# 4) section（插在 view-skills 之后、下一个 section 或注释前）
if 'id="view-aiconfig"' not in html:
    section = '''
  <!-- ===== AI 模型配置 ===== -->
  <section class="view" id="view-aiconfig" style="padding:24px;max-width:900px">
    <div class="panel" style="padding:20px">
      <div class="panel-head"><h2 style="margin:0 0 6px">模型配置</h2><span class="hint" style="color:var(--muted);font-size:13px">接入你自己的大模型 · OpenAI 兼容接口 · 保存即生效，无需重启</span></div>
      <div id="aiCfgSource" style="font-size:12px;color:var(--muted);margin:12px 0 18px;padding:9px 12px;border-radius:9px;background:var(--paper)">读取配置中…</div>

      <div style="display:grid;grid-template-columns:1fr;gap:14px">
        <div><label style="display:block;font-size:13px;color:var(--muted);margin-bottom:6px">接口地址（OpenAI 兼容 base_url，不带 /chat/completions）</label>
          <input id="aiBaseUrl" placeholder="https://api.deepseek.com" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink);font-size:14px"></div>
        <div><label style="display:block;font-size:13px;color:var(--muted);margin-bottom:6px">模型名称</label>
          <input id="aiModel" placeholder="deepseek-chat" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink);font-size:14px"></div>
        <div><label style="display:block;font-size:13px;color:var(--muted);margin-bottom:6px">API Key（脱敏显示；要更换就整段粘贴新的，留空或原样不改则不覆盖）</label>
          <input id="aiKey" type="text" autocomplete="off" placeholder="sk-…" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink);font-size:14px"></div>
        <div><label style="display:block;font-size:13px;color:var(--muted);margin-bottom:6px">上下文预算（字符，受模型窗口上限约束）</label>
          <input id="aiCtxMax" type="number" min="1000" max="2000000" placeholder="300000" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink);font-size:14px"></div>
      </div>

      <div style="display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 10px">
        <button id="aiCfgTest" style="padding:10px 20px;border:1px solid var(--sage);border-radius:10px;background:var(--card);color:var(--sage);cursor:pointer;font-size:14px">测试连接</button>
        <button id="aiCfgSave" style="padding:10px 20px;border:0;border-radius:10px;background:var(--sage);color:#fff;cursor:pointer;font-size:14px">保存配置</button>
      </div>
      <div id="aiCfgMsg" style="font-size:13px;line-height:1.6;color:var(--muted);min-height:22px"></div>

      <div style="margin-top:20px;padding:14px;border-radius:11px;background:var(--paper);font-size:12px;color:var(--muted);line-height:1.8">
        <b style="color:var(--ink)">说明</b><br>
        · 支持任何 OpenAI 兼容接口：DeepSeek、通义、Moonshot、OpenAI、自建 Ollama/vLLM 等。<br>
        · 密钥只保存在你的服务器上，页面只显示脱敏形式，不回传完整密钥。<br>
        · 修改后立即生效，Agent 对话、问答、意图识别都会用新模型，无需重启。<br>
        · 「测试连接」只发一句短问验证连通，不会保存任何改动。
      </div>
    </div>
  </section>
'''
    # 插在 view-skills section 结束之后
    idx = html.find('<section class="view" id="view-skills"')
    assert idx > 0, 'view-skills 未找到'
    end = html.find('</section>', idx) + len('</section>')
    html = html[:end] + '\n' + section + html[end:]
    changes.append('section')

# 5) JS：loadAIConfig + 绑定
if 'function loadAIConfig' not in html:
    js = '''
  function loadAIConfig(){
    if(!$('aiBaseUrl')) return;
    wbApi('/ai/config').then(function(c){
      $('aiBaseUrl').value=c.base_url||'';
      $('aiModel').value=c.model||'';
      $('aiCtxMax').value=c.context_max||300000;
      $('aiKey').value=c.api_key_masked||'';
      $('aiKey').setAttribute('data-masked', c.api_key_set?'1':'0');
      var src=c.source==='database'?'当前配置保存在服务器（网页可改）':'当前使用服务器环境变量初始值（保存后转为网页管理）';
      $('aiCfgSource').textContent=src+(c.updated_at?(' · 更新于 '+String(c.updated_at).slice(0,16).replace('T',' ')):'');
    }).catch(function(e){ $('aiCfgSource').textContent='读取失败：'+e.message; });
  }
  function aiCfgPayload(){
    return {base_url:$('aiBaseUrl').value.trim(), model:$('aiModel').value.trim(),
      api_key:$('aiKey').value.trim(), context_max:parseInt($('aiCtxMax').value,10)||300000};
  }
  function aiCfgMsg(text, bad){
    var m=$('aiCfgMsg'); if(!m) return;
    m.textContent=text; m.style.color=bad?'var(--terra)':'var(--sage)';
  }
'''
    # 插在 wbOnViewChange 函数之前
    anchor = '  function wbOnViewChange(view){'
    assert anchor in html, 'wbOnViewChange 锚点未找到'
    html = html.replace(anchor, js + anchor, 1); changes.append('JS函数')

    # wbOnViewChange 加加载
    old = "    if(view==='skills') loadSkills();\n  }"
    new = "    if(view==='skills') loadSkills();\n    if(view==='aiconfig') loadAIConfig();\n  }"
    assert old in html, 'wbOnViewChange 内容锚点未找到'
    html = html.replace(old, new, 1); changes.append('视图加载')

    # initFeaturePages 加绑定（在末尾的 } 前）
    bind = '''
    var aiSave=$('aiCfgSave');
    if(aiSave) aiSave.onclick=function(){
      aiCfgMsg('保存中…',false);
      wbApi('/ai/config',{method:'POST',body:JSON.stringify(aiCfgPayload())})
        .then(function(r){
          aiCfgMsg('✓ 已保存'+(r.key_changed?'（密钥已更新）':'（密钥保持不变）')+'，新配置立即生效。',false);
          loadAIConfig();
        }).catch(function(e){ aiCfgMsg('保存失败：'+e.message,true); });
    };
    var aiTest=$('aiCfgTest');
    if(aiTest) aiTest.onclick=function(){
      aiCfgMsg('正在连接模型…',false); aiTest.disabled=true;
      wbApi('/ai/config/test',{method:'POST',body:JSON.stringify(aiCfgPayload())})
        .then(function(r){
          aiTest.disabled=false;
          if(r.ok) aiCfgMsg('✓ 连接成功（'+r.ms+'ms，'+r.model+'）。模型回复：'+r.reply,false);
          else aiCfgMsg('✗ 连接失败：'+(r.error||('HTTP '+r.status))+'（'+r.ms+'ms）',true);
        }).catch(function(e){ aiTest.disabled=false; aiCfgMsg('测试失败：'+e.message,true); });
    };
'''
    # 找到 initFeaturePages 函数体结尾：从定义处往后找第一个独立的 "\n  }"
    start = html.find('  function initFeaturePages(){')
    assert start > 0
    end = html.find('\n  }', start)
    assert end > 0
    html = html[:end] + '\n' + bind + html[end:]
    changes.append('事件绑定')

SRC.write_text(html, encoding='utf-8')
print('注入完成:', ' / '.join(changes) if changes else '无变化（已注入过）')
