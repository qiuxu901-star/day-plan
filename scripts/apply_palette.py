#!/usr/bin/env python3
"""全站换色 → C 青碧潮汐配色。幂等（标记守卫）。"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "web" / "workboard.fusion.html"
html = SRC.read_text(encoding="utf-8")

if 'data-palette: teal' in html:
    print("已换色，跳过")
    raise SystemExit(0)

# 1) :root 变量整体替换（青碧潮汐）
old_root = ''':root{
  --paper:#f5f0e8;--card:#fffdfa;--ink:#29251f;--muted:#746d63;--line:#ded5c8;
  --plum:#4d3045;--plum-soft:#e8dfe5;--terra:#b65f42;--terra-soft:#f3dfd6;
  --sage:#627a67;--sage-soft:#dfe8df;--sand:#a57c45;--sand-soft:#eee2ce;
  --red:#b44d43;--green:#477358;--shadow:0 16px 40px rgba(63,48,36,.07);--radius:22px;--sidebar:248px
}'''
new_root = ''':root{ /* data-palette: teal */
  --paper:#eef5f4;--card:#fbfdfc;--ink:#123b3b;--muted:#4e7b78;--line:#cfe3df;
  --plum:#0e7c7b;--plum-soft:#d6eeea;--terra:#e07a5f;--terra-soft:#fbe4dc;
  --sage:#0e7c7b;--sage-soft:#d6eeea;--sand:#c98a3c;--sand-soft:#f7e9d2;
  --red:#c04a3a;--green:#1d8a6a;--shadow:0 16px 40px rgba(14,124,123,.10);--radius:22px;--sidebar:248px
}'''
assert old_root in html
html = html.replace(old_root, new_root, 1)

# 2) 主题色 meta
html = html.replace('content="#f5f0e8"', 'content="#eef5f4"')

# 3) 品牌修饰的 !important 硬编码 → 变量
html = html.replace('background:linear-gradient(140deg,#2c8b86,#14515d)!important',
                    'background:linear-gradient(140deg,var(--sage),#0a5b5a)!important')
html = html.replace('box-shadow:0 7px 18px rgba(20,81,93,.24)!important',
                    'box-shadow:0 7px 18px rgba(14,124,123,.24)!important')
html = html.replace('color:#1c4a52', 'color:var(--ink)')
html = html.replace('color:#6b8a88!important', 'color:var(--muted)!important')
html = html.replace('background:linear-gradient(180deg,#eef2ec 0%,#ede6dc 42%)!important',
                    'background:linear-gradient(180deg,#e3f1ee 0%,var(--paper) 42%)!important')

# 4) 侧栏底色与文字硬编码灰 → 变量/新灰阶
html = html.replace('background:#ede6dc;', 'background:var(--paper);')
html = html.replace('border-right:1px solid rgba(104,87,68,.12)', 'border-right:1px solid var(--line)')
html = html.replace('color:#5e574e;', 'color:var(--muted);')
html = html.replace('color:#9a9186', 'color:var(--muted)')

# 5) 仪表盘独立色板 → 变量体系
html = html.replace("background:#f0f0f0;border-left:4px solid #888",
                    "background:var(--card);border-left:4px solid var(--sage)")
html = html.replace("{'客服':'#dc2626','AI文档':'#f43f5e','迪波运力':'#f59e0b','产品看板':'#22c55e','城际':'#6b7280'}",
                    "{'客服':'var(--terra)','AI文档':'#d9577e','迪波运力':'var(--sand)','产品看板':'var(--green)','城际':'var(--muted)'}")
html = html.replace('color:#666;margin-top:4px', 'color:var(--muted);margin-top:4px')
html = html.replace('color:#999">完成率', 'color:var(--muted)">完成率')
html = html.replace('background:#fff5f5', 'background:var(--terra-soft)')
html = html.replace("'#dc2626'", "'var(--terra)'")

# 6) Keys/Skills 棕色系 → 变量
for old, new in [
    ('#ddd3c6', 'var(--line)'), ('#8a6f52', 'var(--sage)'),
    ('#b9a184', 'var(--line)'), ('#f0ebe3', 'var(--sage-soft)'),
    ('#faf7f2', 'var(--card)'), ('#c0392b', 'var(--red)'),
    ('#5a8a5a', 'var(--green)'), ('#9a9086', 'var(--muted)'),
    ('#b0a69b', 'var(--muted)'),
]:
    html = html.replace(old, new)

# 7) 通用表单硬编码 → 变量
html = html.replace('border:1px solid #ddd4c8', 'border:1px solid var(--line)')
html = html.replace('background:#fbf8f3', 'background:var(--card)')
html = html.replace('border:#92748a', 'border:var(--sage)')
html = html.replace('box-shadow:0 0 0 3px rgba(77,48,69,.07)', 'box-shadow:0 0 0 3px rgba(14,124,123,.09)')

# 8) 鲸鱼 SVG 渐变 → 新色系（更鲜活的青碧）
html = html.replace('stop-color="#7fd3c4"', 'stop-color="#8ee0d4"')
html = html.replace('stop-color="#2c8b86"', 'stop-color="#0e7c7b"')
html = html.replace('stop-color="#123c4a"', 'stop-color="#0a4d52"')
html = html.replace('stop-color="#14515d"', 'stop-color="#0a5b5a"')
html = html.replace('stop-color="#eaf6f2"', 'stop-color="#e8f5f1"')
html = html.replace('stop-color="#0b2330"', 'stop-color="#0f2a3a"')

SRC.write_text(html, encoding="utf-8")
print("全站换色完成：C 青碧潮汐")
