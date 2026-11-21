#!/usr/bin/env python3
"""统一潮汐品牌化：改名、加潮汐意象文案与克制的视觉修饰。幂等。"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")

if 'data-tide-brand="1"' in html:
    print("已品牌化，跳过")
    raise SystemExit(0)

# ---------- 1. title ----------
html = html.replace('<title>工作计划台</title>', '<title>潮汐 · 时间与精力的工作台</title>', 1)

# ---------- 2. CSS：品牌标记改为潮汐波纹 + 侧栏微渐变 ----------
CSS_ADD = '''  /* ===== 潮汐品牌修饰 ===== */
  .brand-mark{background:linear-gradient(140deg,#2c8b86,#14515d)!important;box-shadow:0 7px 18px rgba(20,81,93,.24)!important}
  .brand-mark svg{width:24px;height:24px;stroke:#eaf6f2;stroke-width:1.8;fill:none}
  .brand strong{letter-spacing:.12em!important;color:#1c4a52}
  .brand span{color:#6b8a88!important}
  .sidebar{background:linear-gradient(180deg,#eef2ec 0%,#ede6dc 42%)!important}
  .side-foot::before{content:"◌ ";color:var(--sage)}
  .topbar::after{content:"";position:absolute;left:0;right:0;bottom:-6px;height:6px;
    background:radial-gradient(ellipse at 30% 0,rgba(44,139,134,.10),transparent 60%);pointer-events:none}
'''
html = html.replace('</style>', CSS_ADD + '</style>', 1)

# ---------- 3. 品牌区 DOM ----------
old_brand = '''    <div class="brand-mark" data-page-node-id="UvNkmg7uauNQBVb7HYZinV">计</div>
    <div class="brand" data-page-node-id="Wj6DbvUBvMtBdTE3zTVnDK"><strong data-page-node-id="ZzBp8XxHUwHjPEnPiULiVT">工作计划台</strong><span data-page-node-id="Ra2FGEK73HlUHq4nkd2cxV">DAY PLAN · REVIEW · PROGRESS</span></div>'''
new_brand = '''    <div class="brand-mark" data-page-node-id="UvNkmg7uauNQBVb7HYZinV" data-tide-brand="1"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 14c3-2.6 5-2.6 8 0s5 2.6 8 0 4-2.6 4-2.6"/><path d="M2 18c3-2.6 5-2.6 8 0s5 2.6 8 0 4-2.6 4-2.6"/><circle cx="17" cy="6" r="2.5"/></svg></div>
    <div class="brand" data-page-node-id="Wj6DbvUBvMtBdTE3zTVnDK"><strong data-page-node-id="ZzBp8XxHUwHjPEnPiULiVT">潮汐</strong><span data-page-node-id="Ra2FGEK73HlUHq4nkd2cxV">TIDE · 随潮汐，管理你的时间与精力</span></div>'''
assert old_brand in html
html = html.replace(old_brand, new_brand, 1)

# 侧栏脚文案
html = html.replace('>数据在线存储 · 多端同步</div>', '>潮起潮落，事事有节 · 多端同步</div>', 1)

# ---------- 4. VIEW_TITLES 加潮汐诗意 ----------
old_titles = "var VIEW_TITLES = {agent:'TIDE · 和鲸鱼聊聊', dashboard:'今天，慢慢来', task:'日计划 · Day Plan', week:'全局 · 全部任务', calendar:'日历看板 · Month View', inbox:'收集箱 · Inbox', review:'每日复盘', milestone:'阶段进展', time:'时间记录', history:'历史追溯', keys:'APP Key 管理', skills:'技能管理'};"
new_titles = "var VIEW_TITLES = {agent:'潮起时，和鲸鱼聊聊', dashboard:'今天，慢慢来', task:'日计划 · 一段潮汐', week:'全局 · 潮线全景', calendar:'日历 · 月的盈亏', inbox:'收集箱 · 拾贝', review:'每日复盘 · 落潮时分', milestone:'阶段进展 · 礁石', time:'时间记录 · 潮痕', history:'历史追溯 · 旧潮', keys:'APP Key 管理', skills:'技能管理 · 岛屿'};"
assert old_titles in html
html = html.replace(old_titles, new_titles, 1)

# Agent kicker 与 sub 加潮汐意象
html = html.replace('<div class="agent-kicker">TIDE · 你的工作搭子</div>',
                    '<div class="agent-kicker">TIDE · 随潮汐而行</div>', 1)
html = html.replace('说一句「开工」看重点，或直接告诉我今天的计划。',
                    '潮水会带走杂念，留下要紧的事。说「开工」看重点，或直接告诉我今天的计划。', 1)

SRC.write_text(html, encoding="utf-8")
print("页面品牌化完成")

# ---------- 5. 生成脚本里的登录浮层文案 ----------
p = REPO / "scripts" / "make_h5.py"
s = p.read_text()
s = s.replace('<div style="font-size:20px;font-weight:700;margin-bottom:6px">工作计划台</div>',
              '<div style="font-size:20px;font-weight:700;margin-bottom:6px">潮汐</div>', 1)
s = s.replace('<div style="font-size:13px;color:#8a8076;margin-bottom:20px">登录后查看你的任务与时间</div>',
              '<div style="font-size:13px;color:#8a8076;margin-bottom:20px">潮起潮落，事事有节</div>', 1)
p.write_text(s)
print("登录浮层文案已改")

# ---------- 6. 后端 AI system prompt ----------
p = REPO / "server.js"
s = p.read_text()
s = s.replace("你是工作计划台助手。", "你是「潮汐」工作台助手。")
p.write_text(s)
print("AI prompt 已改")
