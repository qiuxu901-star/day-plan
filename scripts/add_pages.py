#!/usr/bin/env python3
"""给 workboard.fusion.html 增加三个页面：APP Key 管理 / 技能管理。
在源文件上操作，幂等（重复运行会跳过已插入部分）。"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")

# ---------- 1. 侧栏导航（插在「复盘」按钮之后）----------
side_anchor = '''<button class="nav-item" data-view="review" data-page-node-id="BK8gmLR4dRbKKl4UjJBZIc"><svg data-page-node-id="1XCk8fYEJR2VoJdrEto6zY"><path d="M5 4h12a2 2 0 0 1 2-2H7a2 2 0 0 0-2 2v14h14V4a2 2 0 0 0-2-2" data-page-node-id="KPp6d9KyUT0xbCYF4NYrvy"/><path d="M5 4a2 2 0 0 1 2-2h10v18" data-page-node-id="TVlS49q722O0hIX4OEBGap"/></svg>复盘</button>'''
# 用更宽松的锚点：nav 结束前
side_end = '''  </nav>
  <div class="side-foot"'''
side_new = '''    <button class="nav-item" data-view="keys"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="15" r="4"/><path d="M11 12l8-8m-3 3l2 2m-5 1l2 2"/></svg>APP Key</button>
    <button class="nav-item" data-view="skills"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>技能管理</button>
  </nav>
  <div class="side-foot"'''
if 'data-view="keys"' not in html:
    assert side_end in html, "侧栏导航锚点未找到"
    html = html.replace(side_end, side_new, 1)

# ---------- 2. 移动端导航（插在 bottom nav 结束前）----------
mob_end = '''</nav>

<div class="modal-mask" id="modalMask"'''
mob_new = '''  <button data-view="keys"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="8" cy="15" r="4"/><path d="M11 12l8-8m-3 3l2 2"/></svg>Key</button>
  <button data-view="skills"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>技能</button>
</nav>

<div class="modal-mask" id="modalMask"'''
if html.count('data-view="keys"') == 1:  # 只有侧栏加了，移动还没
    assert mob_end in html, "移动导航锚点未找到"
    html = html.replace(mob_end, mob_new, 1)

# ---------- 3. VIEW_TITLES ----------
old_titles = "var VIEW_TITLES = {dashboard:'今天，慢慢来', task:'日计划 · Day Plan', week:'全局 · 全部任务', calendar:'日历看板 · Month View', inbox:'收集箱 · Inbox', review:'每日复盘', milestone:'阶段进展', time:'时间记录', history:'历史追溯'};"
new_titles = "var VIEW_TITLES = {dashboard:'今天，慢慢来', task:'日计划 · Day Plan', week:'全局 · 全部任务', calendar:'日历看板 · Month View', inbox:'收集箱 · Inbox', review:'每日复盘', milestone:'阶段进展', time:'时间记录', history:'历史追溯', keys:'APP Key 管理', skills:'技能管理'};"
if old_titles in html:
    html = html.replace(old_titles, new_titles, 1)

# ---------- 4. 三个 section（插在 </main> 前）----------
sections = '''
  <!-- ===== APP Key 管理 ===== -->
  <section class="view" id="view-keys" style="padding:24px;max-width:900px">
    <div class="panel" style="padding:20px">
      <div class="panel-head"><h2 style="margin:0 0 6px">APP Key</h2><span class="hint" style="color:#9a9086;font-size:13px">用于外部程序/AI 调用本系统接口 · 明文只在创建时显示一次</span></div>
      <div style="display:flex;gap:10px;margin:16px 0;flex-wrap:wrap">
        <select id="keyScope" style="padding:9px 12px;border:1px solid #ddd3c6;border-radius:9px;background:#fff"><option value="read">只读 read</option><option value="write">可写 write</option></select>
        <input id="keyNote" placeholder="用途说明，如：给自动化脚本读取任务" style="flex:1;min-width:200px;padding:9px 12px;border:1px solid #ddd3c6;border-radius:9px;background:#fff">
        <button id="keyCreate" style="padding:9px 18px;border:0;border-radius:9px;background:#8a6f52;color:#fff;cursor:pointer">生成 Key</button>
      </div>
      <div id="keyNew" style="display:none;background:#f0ebe3;border:1px dashed #b9a184;border-radius:10px;padding:14px;margin-bottom:16px">
        <div style="font-size:13px;color:#8a6f52;margin-bottom:6px">新 Key（请立即复制保存，之后不再显示）</div>
        <code id="keyNewVal" style="word-break:break-all;font-size:13px"></code>
        <button id="keyCopy" style="margin-left:10px;padding:4px 10px;border:1px solid #b9a184;border-radius:6px;background:#fff;cursor:pointer">复制</button>
      </div>
      <div id="keyList" style="display:flex;flex-direction:column;gap:8px"></div>
    </div>
  </section>

  <!-- ===== AI 对话生成 Key ===== -->
  <!-- ===== 技能管理 ===== -->
  <section class="view" id="view-skills" style="padding:24px;max-width:1100px">
    <div class="panel" style="padding:20px">
      <div class="panel-head" style="display:flex;justify-content:space-between;align-items:center"><h2 style="margin:0">技能管理</h2><button id="skillNew" style="padding:8px 16px;border:0;border-radius:9px;background:#8a6f52;color:#fff;cursor:pointer">+ 新建技能</button></div>
      <div id="skillList" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:16px"></div>
    </div>
    <div id="skillEditor" style="display:none;position:fixed;inset:0;z-index:200;background:rgba(30,26,22,.55);align-items:center;justify-content:center">
      <div style="background:#faf7f2;border-radius:16px;padding:24px;width:min(720px,94vw);max-height:90vh;overflow:auto;color:#29241f">
        <h3 id="skillEditTitle" style="margin:0 0 16px">编辑技能</h3>
        <label style="display:block;font-size:13px;color:#8a6f52;margin-bottom:4px">名称</label>
        <input id="skillName" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ddd3c6;border-radius:9px;margin-bottom:14px;background:#fff">
        <label style="display:block;font-size:13px;color:#8a6f52;margin-bottom:4px">触发描述 / 一句话说明</label>
        <input id="skillDesc" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ddd3c6;border-radius:9px;margin-bottom:14px;background:#fff">
        <label style="display:block;font-size:13px;color:#8a6f52;margin-bottom:4px">技能内容（Markdown）</label>
        <textarea id="skillContent" rows="14" style="width:100%;box-sizing:border-box;padding:12px;border:1px solid #ddd3c6;border-radius:9px;font-family:ui-monospace,monospace;font-size:13px;background:#fff"></textarea>
        <div id="skillScripts" style="margin-top:12px;font-size:12px;color:#746d63"></div>
        <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px">
          <button id="skillCancel" style="padding:9px 18px;border:1px solid #ddd3c6;border-radius:9px;background:#fff;cursor:pointer">取消</button>
          <button id="skillSave" style="padding:9px 18px;border:0;border-radius:9px;background:#8a6f52;color:#fff;cursor:pointer">保存</button>
        </div>
      </div>
    </div>
  </section>
</main>'''
if 'id="view-keys"' not in html:
    assert '</main>' in html, "main 结束锚点未找到"
    html = html.replace('</main>', sections, 1)

SRC.write_text(html, encoding="utf-8")
print("三个页面已插入源文件")
