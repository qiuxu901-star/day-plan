#!/usr/bin/env python3
"""一次性重构：修视图 bug + 拆出独立 Agent 页 + 浅色改版。
直接改 workboard.fusion.html 源文件；只允许运行一次（幂等守卫）。"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")

if 'id="view-agent"' in html:
    print("已重构过，跳过")
    raise SystemExit(0)

# ---------- 1. 替换 Agent CSS 整块（658-712）----------
css_start = html.index("  /* ===== TIDE Agent Dock")
css_end = html.index("\n</style>", css_start)
NEW_CSS = '''  /* ===== TIDE Agent · 浅色独立页（显示只由 .view/.view.active 控制） ===== */
  .view.view-agent.active{display:flex;flex-direction:column;
    height:calc(100dvh - var(--topbar-h,104px));min-height:520px;overflow:hidden}
  .agent-dock{flex:1 1 auto;display:flex;flex-direction:column;min-height:0;
    background:var(--paper);color:var(--ink);position:relative}
  .agent-dock svg{stroke:none}                 /* 抵消全局 svg{stroke:currentColor} */
  .agent-waves{position:absolute;inset:0;pointer-events:none;opacity:.18}
  .agent-waves svg{position:absolute;bottom:0;left:0;width:100%;height:64px}
  .agent-hero{position:relative;display:flex;align-items:center;gap:12px;padding:18px 24px 6px;flex:0 0 auto}
  .agent-hero .whale{width:64px;height:40px;flex:none}
  .agent-dock .wb-spout{stroke:var(--sage);stroke-width:2.5;fill:none;stroke-linecap:round}
  .agent-intro{min-width:0}
  .agent-kicker{font-size:11px;letter-spacing:.16em;color:var(--terra);text-transform:uppercase}
  .agent-sub{font-size:13px;color:var(--muted);margin-top:3px}
  .agent-thread{position:relative;flex:1 1 auto;min-height:0;overflow-y:auto;
    padding:16px 24px;display:flex;flex-direction:column;gap:12px;scroll-behavior:smooth}
  .agent-bubble{max-width:92%;padding:12px 16px;border-radius:16px;
    font-size:15.5px;line-height:1.7;white-space:pre-wrap;word-break:break-word}
  .agent-bubble.me{align-self:flex-end;background:var(--sage-soft);color:var(--ink);
    border:1px solid var(--sage);border-bottom-right-radius:5px}
  .agent-bubble.ai{align-self:flex-start;background:var(--card);color:var(--ink);
    border:1px solid var(--line);border-bottom-left-radius:5px}
  .agent-bubble .undo{margin-left:10px;padding:3px 9px;border:1px solid var(--terra);
    border-radius:6px;background:transparent;color:var(--terra);font-size:12px;cursor:pointer}
  .agent-top3{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
  .agent-top3 span{padding:5px 10px;border-radius:8px;background:var(--terra-soft);
    color:var(--terra);font-size:12px}
  .agent-typing{display:flex;gap:4px;padding:10px 2px}
  .agent-typing i{width:6px;height:6px;border-radius:50%;background:var(--sage);animation:wbtyp 1.1s infinite ease-in-out}
  .agent-typing i:nth-child(2){animation-delay:.15s}.agent-typing i:nth-child(3){animation-delay:.3s}
  @keyframes wbtyp{0%,60%,100%{opacity:.25;transform:translateY(0)}30%{opacity:1;transform:translateY(-4px)}}
  .agent-quick{position:relative;display:flex;gap:8px;padding:4px 24px 10px;flex-wrap:wrap;flex:0 0 auto}
  .agent-quick button{padding:7px 15px;border:1px solid var(--line);border-radius:18px;
    background:var(--card);color:var(--ink);font-size:13px;cursor:pointer;transition:.2s}
  .agent-quick button:hover{border-color:var(--terra);background:var(--terra-soft)}
  .agent-composer{position:sticky;bottom:0;display:flex;gap:8px;padding:12px 24px 20px;
    flex:0 0 auto;background:var(--paper)}
  .agent-composer input{flex:1;padding:12px 15px;border:1px solid var(--line);border-radius:12px;
    background:var(--card);color:var(--ink);font-size:14px;outline:none}
  .agent-composer input::placeholder{color:var(--muted)}
  .agent-composer input:focus{border-color:var(--terra)}
  .agent-composer button{padding:0 22px;border:0;border-radius:12px;background:var(--terra);
    color:#fff;font-weight:600;font-size:14px;cursor:pointer}
  /* 技能草稿预览卡 */
  .skill-preview{border:1px solid var(--line);border-left:3px solid var(--terra);
    background:var(--card);border-radius:14px;padding:14px 16px;margin-top:10px;
    max-width:92%;align-self:flex-start;width:92%}
  .skill-preview h4{margin:0 0 6px;font-size:15px;color:var(--terra)}
  .skill-preview .sp-desc{font-size:13px;color:var(--muted);margin-bottom:10px}
  .skill-preview textarea{width:100%;box-sizing:border-box;min-height:180px;
    font:13px/1.6 ui-monospace,monospace;border:1px solid var(--line);
    border-radius:8px;padding:10px;background:#faf6ef;color:var(--ink)}
  .sp-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:10px}
  .sp-ok{background:var(--terra);color:#fff;border:0;border-radius:9px;padding:8px 16px;cursor:pointer;font-size:13px}
  .sp-cancel{border:1px solid var(--line);background:var(--card);border-radius:9px;padding:8px 16px;cursor:pointer;font-size:13px}
  /* 鲸鱼动画（克制） */
  .wb-whale{transform-origin:180px 150px;animation:wb-breathe 4.5s ease-in-out infinite alternate}
  @keyframes wb-breathe{from{transform:translateY(0)}to{transform:translateY(-3px)}}
  .wb-spout{animation:wb-spout 4.5s ease-in-out infinite}
  @keyframes wb-spout{0%,60%{opacity:0}75%{opacity:.9}100%{opacity:0}}
  @media (prefers-reduced-motion:reduce){.wb-whale,.wb-spout{animation:none}}
  @media (max-width:860px){
    .view.view-agent.active{height:auto;min-height:calc(100dvh - 68px)}
    .agent-hero .whale{width:48px;height:30px}
    .agent-thread{padding:12px 14px}
    .agent-composer{padding:10px 14px 16px}
    .agent-quick{padding:4px 14px 8px}
    .agent-bubble{max-width:100%;font-size:15px}
    .skill-preview{max-width:100%;width:100%}
  }'''
html = html[:css_start] + NEW_CSS + html[css_end:]

# ---------- 2. DOM：把 agent-dock 从 dashboard 搬到新 section ----------
# 精确切出 agent-dock（从 <div class="agent-dock" 到其闭合 </div>，紧接 <div class="dash-scroll">）
dock_start = html.index('  <div class="agent-dock" id="agentDock">')
dock_end = html.index('  <div class="dash-scroll">', dock_start)
dock = html[dock_start:dock_end]
html = html[:dock_start] + html[dock_end:]  # 从 dashboard 移除

# 移除 dash-scroll 的闭合 </div>（dim-wall 后那个）
close_anchor = '    <div class="dim-wall" id="dimWall" data-page-node-id="dimWallWrap1"></div>\n  </div>\n  </section>'
assert close_anchor in html
html = html.replace(close_anchor,
    '    <div class="dim-wall" id="dimWall" data-page-node-id="dimWallWrap1"></div>\n  </section>', 1)

# dashboard 去掉 active
html = html.replace('<section class="view active" id="view-dashboard"',
                    '<section class="view" id="view-dashboard"', 1)

# 精简 hero：删重复问候，改 sub，波浪简化，鲸鱼已由 CSS 缩小
dock = dock.replace('<div class="agent-greet">今天，想从哪里开始？</div>\n        ', '')
dock = dock.replace('说一句「开工」看重点，或直接告诉我今天的计划。',
                    '说一句「开工」看重点，或直接告诉我今天的计划。')
# 波浪：去掉第二层 + 第一层改 sage
dock = dock.replace('<path class="wb-wave wb-wave-b" d="M0 172 Q45 158 90 172 T180 172 T270 172 T360 172 V200 H0 Z" fill="#0b2330" opacity=".45"/>\n        ', '')
dock = dock.replace('fill="url(#wbWave)"', 'fill="var(--sage)" opacity=".25"')

# 新 section 插到 dashboard </section> 后
agent_section = '\n  <!-- Agent · 独立页（默认） -->\n  <section class="view view-agent active" id="view-agent">\n' + dock + '  </section>\n'
anchor = '    <div class="dim-wall" id="dimWall" data-page-node-id="dimWallWrap1"></div>\n  </section>\n'
assert anchor in html
html = html.replace(anchor, anchor + agent_section, 1)

# ---------- 3. 导航与标题 ----------
side_anchor = '  <button class="nav-item active" data-view="dashboard"'
side_agent = '''  <button class="nav-item active" data-view="agent"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12c3-4 9-4 12 0 3 4-3 7-6 7s-9-3-6-7z"/><circle cx="9" cy="12" r="1"/></svg>Agent</button>
'''
assert side_anchor in html
html = html.replace(side_anchor, side_agent + '  <button class="nav-item" data-view="dashboard"', 1)

mob_anchor = '<button class="active" data-view="dashboard"'
mob_agent = '''<button class="active" data-view="agent"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12c3-4 9-4 12 0 3 4-3 7-6 7s-9-3-6-7z"/><circle cx="9" cy="12" r="1"/></svg>Agent</button>
  '''
assert mob_anchor in html
html = html.replace(mob_anchor, mob_agent + '<button data-view="dashboard"', 1)

html = html.replace("var VIEW_TITLES = {dashboard:", "var VIEW_TITLES = {agent:'TIDE · 和鲸鱼聊聊', dashboard:", 1)

# ---------- 4. switchView 接线 + --topbar-h 写根 ----------
if 'wbOnViewChange(view)' not in html:
    old = "    window.scrollTo({ top: 0, behavior: 'smooth' });\n  }"
    new = "    window.scrollTo({ top: 0, behavior: 'smooth' });\n    if (typeof wbOnViewChange === 'function') wbOnViewChange(view);\n  }"
    assert old in html
    html = html.replace(old, new, 1)
html = html.replace("dv.style.setProperty('--topbar-h', tb.offsetHeight+'px');",
                    "document.documentElement.style.setProperty('--topbar-h', tb.offsetHeight+'px');")
html = html.replace("var tb=document.querySelector('.topbar'), dv=$('view-dashboard');\n      if(tb&&dv)",
                    "var tb=document.querySelector('.topbar');\n      if(tb)")
# 移除旧的 dv 变量引用残留
html = html.replace("      var tb=document.querySelector('.topbar'), dv=$('view-dashboard');",
                    "      var tb=document.querySelector('.topbar');")

SRC.write_text(html, encoding="utf-8")
print("重构完成：修 bug + 拆 Agent 独立页 + 浅色改版")
