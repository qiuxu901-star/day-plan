#!/usr/bin/env python3
"""给 workboard.fusion.html 注入 Agent 首页（鲸鱼对话 + 下方仪表盘）。幂等。"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")

# ---------- 1. CSS ----------
CSS = r'''
  /* ===== TIDE Agent Dock（scoped，不影响其他页面） ===== */
  .view#view-dashboard{display:flex;flex-direction:column;padding-bottom:0}
  .agent-dock{
    --deep-1:#0b2330; --deep-2:#14515d; --deep-3:#2c8b86;
    --foam:#eaf6f2; --ink-on:#f3efe6; --muted-on:#a9c9c6;
    position:relative;flex:0 0 auto;height:clamp(300px,42vh,460px);
    display:flex;flex-direction:column;overflow:hidden;
    border-radius:0 0 var(--radius) var(--radius);
    background:linear-gradient(135deg,var(--deep-1),var(--deep-2) 55%,var(--deep-3));
    color:var(--ink-on);box-shadow:0 18px 44px rgba(11,35,48,.22);
  }
  .agent-waves{position:absolute;inset:0;pointer-events:none;opacity:.55}
  .agent-waves svg{position:absolute;bottom:-8px;left:0;width:200%;height:90px}
  .agent-hero{position:relative;display:flex;align-items:center;gap:14px;padding:16px 20px 6px;flex:0 0 auto}
  .agent-hero .whale{width:190px;height:105px;flex:none;filter:drop-shadow(0 8px 16px rgba(0,0,0,.25))}
  .agent-intro{min-width:0}
  .agent-kicker{font-size:11px;letter-spacing:.18em;color:#7fd3c4;text-transform:uppercase}
  .agent-greet{font-family:"Songti SC",serif;font-size:25px;font-weight:600;margin:4px 0 2px;line-height:1.25}
  .agent-sub{font-size:12px;color:var(--muted-on)}
  .agent-thread{position:relative;flex:1 1 auto;overflow-y:auto;padding:8px 20px;display:flex;flex-direction:column;gap:8px;scroll-behavior:smooth}
  .agent-bubble{max-width:82%;padding:9px 13px;border-radius:14px;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-word}
  .agent-bubble.me{align-self:flex-end;background:rgba(127,211,196,.9);color:#0b2330;border-bottom-right-radius:4px}
  .agent-bubble.ai{align-self:flex-start;background:rgba(255,255,255,.1);color:var(--foam);border:1px solid rgba(127,211,196,.25);border-bottom-left-radius:4px}
  .agent-bubble .undo{margin-left:10px;padding:2px 8px;border:1px solid rgba(127,211,196,.5);border-radius:6px;background:transparent;color:#7fd3c4;font-size:11px;cursor:pointer}
  .agent-top3{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
  .agent-top3 span{padding:3px 8px;border-radius:8px;background:rgba(127,211,196,.16);font-size:11px}
  .agent-typing{display:flex;gap:4px;padding:10px 2px}
  .agent-typing i{width:6px;height:6px;border-radius:50%;background:#7fd3c4;animation:wbtyp 1.1s infinite ease-in-out}
  .agent-typing i:nth-child(2){animation-delay:.15s}.agent-typing i:nth-child(3){animation-delay:.3s}
  @keyframes wbtyp{0%,60%,100%{opacity:.25;transform:translateY(0)}30%{opacity:1;transform:translateY(-4px)}}
  .agent-quick{position:relative;display:flex;gap:8px;padding:4px 20px 8px;flex-wrap:wrap;flex:0 0 auto}
  .agent-quick button{padding:6px 13px;border:1px solid rgba(127,211,196,.4);border-radius:18px;background:rgba(255,255,255,.06);color:var(--foam);font-size:12px;cursor:pointer;transition:.2s}
  .agent-quick button:hover{background:rgba(127,211,196,.2);border-color:#7fd3c4}
  .agent-composer{position:relative;display:flex;gap:8px;padding:0 20px 16px;flex:0 0 auto}
  .agent-composer input{flex:1;padding:11px 14px;border:1px solid rgba(127,211,196,.35);border-radius:12px;background:rgba(255,255,255,.1);color:var(--foam);font-size:13px;outline:none}
  .agent-composer input::placeholder{color:var(--muted-on)}
  .agent-composer input:focus{border-color:#7fd3c4}
  .agent-composer button{padding:0 20px;border:0;border-radius:12px;background:#7fd3c4;color:#0b2330;font-weight:600;font-size:13px;cursor:pointer}
  .dash-scroll{flex:1 1 auto;min-height:0;overflow-y:auto;padding:18px 2px 40px}
  /* 鲸鱼动画 */
  .wb-whale{transform-origin:180px 150px;animation:wb-breathe 4.5s ease-in-out infinite alternate}
  @keyframes wb-breathe{from{transform:translateY(0) scaleY(1)}to{transform:translateY(-4px) scaleY(1.025)}}
  .wb-wave{animation:wb-drift 9s linear infinite}
  .wb-wave-b{animation-duration:13s;animation-direction:reverse}
  @keyframes wb-drift{to{transform:translateX(-90px)}}
  .wb-spout{animation:wb-spout 4.5s ease-in-out infinite}
  @keyframes wb-spout{0%,60%{opacity:0}75%{opacity:.9}100%{opacity:0}}
  @media (prefers-reduced-motion:reduce){.wb-whale,.wb-wave,.wb-spout{animation:none}}
  @media (max-width:860px){
    .view#view-dashboard{display:block}
    .agent-dock{height:auto;min-height:360px;border-radius:16px;margin-bottom:12px}
    .agent-hero .whale{width:130px;height:74px}
    .agent-greet{font-size:21px}
    .dash-scroll{overflow:visible;padding:0}
  }
'''
if '.agent-dock{' not in html:
    assert '</style>' in html
    html = html.replace('</style>', CSS + '\n</style>', 1)

# ---------- 2. DOM ----------
DOCK = '''
  <div class="agent-dock" id="agentDock">
    <div class="agent-waves" aria-hidden="true">
      <svg viewBox="0 0 720 90" preserveAspectRatio="none"><path d="M0 45 Q90 20 180 45 T360 45 T540 45 T720 45 V90 H0 Z" fill="#2c8b86" opacity=".25"/></svg>
    </div>
    <div class="agent-hero">
      <svg class="whale" viewBox="0 0 360 200" role="img" aria-label="潮汐鲸鱼助手">
        <defs>
          <linearGradient id="wbWhaleBody" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#7fd3c4"/><stop offset=".5" stop-color="#2c8b86"/><stop offset="1" stop-color="#123c4a"/>
          </linearGradient>
          <linearGradient id="wbWave" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="#2c8b86" stop-opacity=".7"/><stop offset="1" stop-color="#7fd3c4" stop-opacity=".35"/>
          </linearGradient>
          <radialGradient id="wbGlow"><stop offset="0" stop-color="#7fd3c4" stop-opacity=".35"/><stop offset="1" stop-color="#7fd3c4" stop-opacity="0"/></radialGradient>
        </defs>
        <ellipse cx="180" cy="110" rx="150" ry="80" fill="url(#wbGlow)"/>
        <g class="wb-whale">
          <path d="M42 118 C70 64 168 52 234 96 C256 112 270 128 302 116 C294 140 272 150 250 144 C218 170 128 172 80 150 C58 140 46 132 42 118 Z" fill="url(#wbWhaleBody)"/>
          <path d="M300 116 C324 94 340 90 354 94 C338 106 332 122 332 138 C320 128 310 122 300 116 Z" fill="url(#wbWhaleBody)"/>
          <path d="M150 146 C160 170 184 180 206 175 C189 159 177 151 168 143 Z" fill="#14515d" opacity=".85"/>
          <circle cx="104" cy="108" r="3.4" fill="#eaf6f2"/><circle cx="105" cy="107" r="1.1" fill="#0b2330"/>
          <path d="M96 122 Q112 130 128 120" stroke="#eaf6f2" stroke-opacity=".6" stroke-width="2" fill="none" stroke-linecap="round"/>
        </g>
        <g class="wb-spout" stroke="#eaf6f2" stroke-width="3" fill="none" stroke-linecap="round">
          <path d="M92 66 Q84 44 96 26"/><path d="M100 64 Q100 40 112 22"/><path d="M108 66 Q116 46 130 32"/>
        </g>
        <path class="wb-wave" d="M0 158 Q45 144 90 158 T180 158 T270 158 T360 158 V200 H0 Z" fill="url(#wbWave)"/>
        <path class="wb-wave wb-wave-b" d="M0 172 Q45 158 90 172 T180 172 T270 172 T360 172 V200 H0 Z" fill="#0b2330" opacity=".45"/>
      </svg>
      <div class="agent-intro">
        <div class="agent-kicker">TIDE · 你的工作搭子</div>
        <div class="agent-greet">今天，想从哪里开始？</div>
        <div class="agent-sub">说一句「开工」看重点，或直接告诉我今天的计划。</div>
      </div>
    </div>
    <div class="agent-thread" id="agentThread" role="log" aria-live="polite"></div>
    <div class="agent-quick" id="agentQuick">
      <button data-q="start">⚡ 开工</button>
      <button data-q="record">＋ 记一笔</button>
      <button data-q="wrap">✓ 收工</button>
      <button data-q="qa">今天怎么样</button>
    </div>
    <form class="agent-composer" id="agentForm">
      <input id="agentInput" placeholder="说一句话，比如：今天的计划是……" autocomplete="off">
      <button id="agentSend" type="submit">发送</button>
    </form>
  </div>
  <div class="dash-scroll">
'''
if 'id="agentDock"' not in html:
    anchor = '''  <section class="view active" id="view-dashboard" data-page-node-id="4o1FqEJ5ctKl8tzO1JoKE7">
'''
    assert anchor in html
    html = html.replace(anchor, anchor + DOCK, 1)
    # 在 dashboard section 结束前闭合 dash-scroll
    end_anchor = '''    <div class="dim-wall" id="dimWall" data-page-node-id="dimWallWrap1"></div>
  </section>'''
    assert end_anchor in html
    html = html.replace(end_anchor, '''    <div class="dim-wall" id="dimWall" data-page-node-id="dimWallWrap1"></div>
  </div>
  </section>''', 1)

# ---------- 3. JS ----------
JS = r'''
  /* ========== TIDE Agent 对话 ========== */
  var agentState={busy:false,history:[]};
  function agentBubble(role, html, meta){
    var box=$('agentThread'); if(!box) return;
    var d=document.createElement('div');
    d.className='agent-bubble '+role;
    d.innerHTML=html;
    if(meta && meta.undoable && meta.audit_ids && meta.audit_ids.length){
      var b=document.createElement('button'); b.className='undo'; b.textContent='撤销';
      b.onclick=function(){
        wbApi('/agent/undo',{method:'POST',body:JSON.stringify({audit_id:meta.audit_ids[0]})})
          .then(function(){ b.textContent='已撤销'; b.disabled=true; if(typeof refreshAll==='function') refreshAll(); })
          .catch(function(e){ toast(e.message,true); });
      };
      d.appendChild(b);
    }
    box.appendChild(d); box.scrollTop=box.scrollHeight;
  }
  function agentTyping(on){
    var box=$('agentThread'); if(!box) return;
    var old=box.querySelector('.agent-typing');
    if(on){
      if(old) return;
      var d=document.createElement('div'); d.className='agent-typing';
      d.innerHTML='<i></i><i></i><i></i>'; box.appendChild(d); box.scrollTop=box.scrollHeight;
    } else if(old) old.remove();
  }
  function agentSend(text, preset){
    if(agentState.busy) return;
    text=String(text||'').trim(); if(!text) return;
    agentState.busy=true;
    var sendBtn=$('agentSend'), inp=$('agentInput');
    if(sendBtn) sendBtn.disabled=true;
    agentBubble('me', escHtml(text));
    agentTyping(true);
    agentState.history.push({role:'me',text:text});
    var body={message:text,history:agentState.history};
    if(preset) body.preset_intent=preset;
    return wbApi('/agent/chat',{method:'POST',body:JSON.stringify(body)})
      .then(function(r){
        agentTyping(false);
        var html=escHtml(r.reply||'');
        if(r.data && r.data.top3 && r.data.top3.length){
          html+='<div class="agent-top3">'+r.data.top3.map(function(t){
            return '<span>'+escHtml('['+(t.优先级||'')+'] '+t.任务+' · '+t.分数+'分')+'</span>';
          }).join('')+'</div>';
        }
        agentBubble('ai',html,r);
        agentState.history.push({role:'ai',text:(r.reply||'').slice(0,400)});
        if(r.data && r.data.created) { if(typeof refreshAll==='function') refreshAll(); }
      })
      .catch(function(e){
        agentTyping(false);
        agentBubble('ai','出错了：'+escHtml(e.message)+'，请重试。');
      })
      .finally(function(){
        agentState.busy=false;
        if(sendBtn) sendBtn.disabled=false;
        if(inp){ inp.value=''; inp.focus(); }
      });
  }
  function initAgent(){
    var form=$('agentForm'), inp=$('agentInput');
    if(form) form.onsubmit=function(e){ e.preventDefault(); agentSend(inp?inp.value:''); };
    Array.prototype.forEach.call(document.querySelectorAll('#agentQuick button'),function(b){
      b.onclick=function(){
        var q=b.getAttribute('data-q');
        if(q==='record'){ if(inp){ inp.value='今天的计划是'; inp.focus(); } return; }
        var map={start:'开工',wrap:'收工',qa:'今天有哪些事'};
        agentSend(map[q]||b.textContent,q);
      };
    });
    // 量 topbar 高度写入 flex 基准
    try{
      var tb=document.querySelector('.topbar'), dv=$('view-dashboard');
      if(tb&&dv) dv.style.setProperty('--topbar-h', tb.offsetHeight+'px');
    }catch(e){}
  }
'''
marker = " /* ========== 视图切换 ========== */"
if 'function initAgent()' not in html:
    assert marker in html
    html = html.replace(marker, JS + marker, 1)

# 在 init 里调用 initAgent（首个 refreshAll 之后）
if 'initAgent();' not in html:
    html = html.replace("    refreshAll();\n    initFeaturePages();",
                        "    refreshAll();\n    initAgent();\n    initFeaturePages();", 1)

# 修 wbOnViewChange 接线 bug：直接在 switchView 里加调用
if 'wbOnViewChange(view)' not in html:
    old = "    window.scrollTo({ top: 0, behavior: 'smooth' });\n  }"
    new = "    window.scrollTo({ top: 0, behavior: 'smooth' });\n    if (typeof wbOnViewChange === 'function') wbOnViewChange(view);\n  }"
    if old in html: html = html.replace(old, new, 1)

SRC.write_text(html, encoding="utf-8")
print("Agent 首页已注入：DOM / CSS / JS")
