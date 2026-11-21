#!/usr/bin/env python3
"""信息密度优化：长文本截断+展开、重复信息合并、假按钮修复、日历监听清理。幂等。"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")

if 'function expandableText' in html:
    print("已优化，跳过")
    raise SystemExit(0)

# ---------- 1. CSS：截断与展开 ----------
CSS = '''  /* ===== 长文本截断 + 展开 ===== */
  .exp-text{position:relative}
  .exp-text .exp-body{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;line-height:1.6}
  .exp-text.open .exp-body{-webkit-line-clamp:unset;display:block;overflow:visible}
  .exp-text .exp-more{display:inline-block;margin-top:3px;padding:1px 7px;border:0;border-radius:6px;
    background:var(--sage-soft);color:var(--sage);font-size:11px;cursor:pointer}
  .exp-text.open .exp-more{background:var(--terra-soft);color:var(--terra)}
  .gv-meta{flex-wrap:wrap!important}
  .gv-meta .gv-tag-secondary{opacity:.72;font-size:11px}
'''
html = html.replace('</style>', CSS + '</style>', 1)

# ---------- 2. JS：通用 expandableText ----------
JS_FN = '''  // 长文本：两行截断 + 展开/收起（安全：textContent）
  function expandableText(text, cls, limit){
    var box=document.createElement('div');
    box.className='exp-text'+(cls?(' '+cls):'');
    var body=document.createElement('div'); body.className='exp-body';
    body.textContent=String(text||'');
    box.appendChild(body);
    var full=String(text||'');
    if(full.length > (limit||80)){
      var btn=document.createElement('button'); btn.className='exp-more'; btn.type='button'; btn.textContent='展开全文';
      btn.onclick=function(){
        var open=box.classList.toggle('open');
        btn.textContent=open?'收起':'展开全文';
      };
      box.appendChild(btn);
    }
    return box;
  }

'''
marker = "  function bind(node, dbId){"
if marker in html:
    html = html.replace(marker, JS_FN + marker, 1)
else:
    # 找一个稳定的 JS 起点
    marker2 = "  function twoLine(t, mainCls){"
    assert marker2 in html
    html = html.replace(marker2, JS_FN + marker2, 1)

# ---------- 3. 替换长文本渲染点 ----------
# 任务备注（taskCard + gvTaskRow）+ 本周目标
html = html.replace(
  "if (t['备注']){ var note = document.createElement('div'); note.className = 't-note'; note.textContent = t['备注']; bind(note, DB_TASK); card.appendChild(note); }",
  "if (t['备注']){ var note = expandableText(t['备注'], 't-note', 80); bind(note, DB_TASK); card.appendChild(note); }")
html = html.replace(
  "if (t['备注']){ var note = document.createElement('div'); note.className = 'gv-note'; note.textContent = t['备注']; bind(note, DB_TASK); body.appendChild(note); }",
  "if (t['备注']){ var note = expandableText(t['备注'], 'gv-note', 80); bind(note, DB_TASK); body.appendChild(note); }")
html = html.replace(
  "if (w['本周目标']){ var goal = document.createElement('div'); goal.className='t-note'; goal.textContent = w['本周目标']; bind(goal, DB_WEEK); card.appendChild(goal); }",
  "if (w['本周目标']){ var goal = expandableText(w['本周目标'], 't-note', 80); bind(goal, DB_WEEK); card.appendChild(goal); }")

# 收集箱内容
old_ib = "txt.textContent = r['内容'] || '(空)';"
if old_ib in html:
    html = html.replace(old_ib, "txt.textContent = String(r['内容']||'(空)').slice(0,160)+(String(r['内容']||'').length>160?'…':'');", 1)
    # 在 ib-body 后追加展开按钮逻辑：直接替换为 expandableText 更安全
    # 找 txt 创建行前后的上下文
    old_line = [l for l in html.splitlines() if "txt.textContent = String(r['内容']" in l]
    if old_line:
        ln = old_line[0]
        indent = ln[:len(ln)-len(ln.lstrip())]
        html = html.replace(ln, indent + "var fullTxt=String(r['内容']||'(空)'); var txt=expandableText(fullTxt,'ib-text',160); bind(txt,DB_INBOX);", 1)
        # 移除随后重复的 appendChild(txt) 若已存在 bind 行
        html = html.replace(indent + "bind(txt, DB_INBOX); body.appendChild(txt);", indent + "body.appendChild(txt);", 1)

# 复盘三字段
old_rev = "v.textContent = pair[1];   // 全部原文"
if old_rev in html:
    html = html.replace(old_rev, "v.textContent = pair[1];", 1)
# 更稳妥：找到 r-cell 里 v 的赋值（可能有不同缩进）
lines = html.splitlines()
for i, l in enumerate(lines):
    if "v.textContent = pair[1]" in l:
        indent = l[:len(l)-len(l.lstrip())]
        lines[i] = indent + "var vcell=expandableText(pair[1],'v',80); cell.appendChild(vcell);"
        # 原 l 之后通常有 cell.appendChild(v) —— 置空
        for j in range(i+1, min(i+4, len(lines))):
            if 'cell.appendChild(v)' in lines[j]:
                lines[j] = ''
                break
        break
html = '\n'.join(lines)

# ---------- 4. 重复信息合并：任务卡 twoLine 与 subListNode 只留一个 ----------
# 在 taskCard 里，twoLine 已展示子项，subListNode 重复——改为只在编辑态展示 subListNode
html = html.replace("subListNode(t,{editable:true})", "subListNode(t,{editable:true,collapsed:true})", 1)
# gvTaskRow 里同样
html = html.replace("subListNode(t,{editable:false})", "subListNode(t,{editable:false,collapsed:true})", 1)

# 在 subListNode 实现里支持 collapsed：默认收起，点击展开
# 找 subListNode 定义里的容器创建点，加折叠包装
old_sub = "function subListNode(t, opt){"
if old_sub in html and 'opt.collapsed' not in html:
    # 简单做法：collapsed 时给容器加 class，用 CSS 默认收起 + 点击展开
    CSS2 = '''  .sub-list.collapsed{max-height:38px;overflow:hidden;cursor:pointer;position:relative}
  .sub-list.collapsed::after{content:"▾ 展开子项";position:absolute;right:8px;top:8px;font-size:11px;color:var(--muted);background:var(--card);padding:0 4px}
  .sub-list.collapsed.open{max-height:none}
  .sub-list.collapsed.open::after{content:"▴ 收起子项"}
'''
    html = html.replace('</style>', CSS2 + '</style>', 1)
    # 在 subListNode 返回前加 class 与点击
    # 定位 return node 的那一行（在函数体内第一个 return node）
    idx = html.index(old_sub)
    ret = html.index('    return node;', idx)
    insert = '''    if(opt && opt.collapsed){
      node.classList.add('collapsed');
      node.onclick=function(e){ e.stopPropagation(); node.classList.toggle('open'); };
    }
'''
    html = html[:ret] + insert + html[ret:]

# ---------- 5. 修假按钮：仪表盘板块卡片加点击跳转 ----------
old_card = "card.style.cssText = 'flex:1;min-width:140px;padding:12px 14px;border-radius:14px;background:var(--card);border-left:4px solid var(--sage);cursor:pointer';"
if old_card in html:
    new_card = old_card + "\n      card.onclick=function(){ switchView('task'); };"
    html = html.replace(old_card, new_card, 1)

# ---------- 6. 修日历浮层监听残留：解绑收进 calClosePop ----------
old_close = "function calClosePop(){"
if old_close in html and 'calClosePop._cleanup' not in html:
    idx = html.index(old_close)
    body_start = html.index('{', idx) + 1
    body_end = html.index('\n  }', body_start)
    inject = '''
    if(typeof calClosePop._cleanup==='function'){ calClosePop._cleanup(); calClosePop._cleanup=null; }'''
    html = html[:body_end] + inject + html[body_end:]
    # calShowDay 注册处改为存 cleanup
    html = html.replace(
      "document.addEventListener('click', off, true);",
      "document.addEventListener('click', off, true); calClosePop._cleanup=function(){ document.removeEventListener('click',off,true); document.removeEventListener('keydown',onKey,true); };", 1)

SRC.write_text(html, encoding="utf-8")
print("信息密度优化完成")
