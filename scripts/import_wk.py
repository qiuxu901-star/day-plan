#!/usr/bin/env python3
"""从 Obsidian WKxx.md 文件导入历史数据到飞书多维表。

用法: python scripts/import_wk.py WK22 WK23 WK25
"""

import sys, os, re, json, asyncio, httpx
from datetime import date, datetime, timedelta

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

# Read .env
env = {}
with open(os.path.join(PROJECT_DIR, '.env')) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

APP_ID = env['FEISHU_APP_ID']
APP_SECRET = env['FEISHU_APP_SECRET']
APP_TOKEN = env['BITABLE_APP_TOKEN']
TABLE_W = env['TABLE_ID_WEEKLY']
TABLE_D = env['TABLE_ID_DAILY']
TABLE_T = env['TABLE_ID_TASKS']

OBSIDIAN_DIR = os.path.expanduser('~/Documents/工作obsidian/04_任务池')
WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

API = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}'

# ── HTTP ──
async def get_token():
    async with httpx.AsyncClient() as c:
        r = await c.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
                         json={'app_id': APP_ID, 'app_secret': APP_SECRET}, timeout=15)
        r.raise_for_status()
        return r.json()['tenant_access_token']

async def api_get(path, params=None):
    token = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.get(f'{API}{path}', headers={'Authorization': f'Bearer {token}'}, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

async def api_post(path, body):
    token = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.post(f'{API}{path}', headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, json=body, timeout=30)
        r.raise_for_status()
        return r.json()

async def api_put(path, body):
    token = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.put(f'{API}{path}', headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, json=body, timeout=30)
        r.raise_for_status()
        return r.json()

async def api_del(path):
    token = await get_token()
    async with httpx.AsyncClient() as c:
        r = await c.delete(f'{API}{path}', headers={'Authorization': f'Bearer {token}'}, timeout=30)
        r.raise_for_status()
        return r.json()

# ── Parser ──
def parse_wk(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    result = {'principle': '', 'main_line': '', 'must_complete': '', 'push_forward': '', 'temp_in': '', 'days': {}, 'weekly_review': ''}

    m = re.search(r'> 本周原则[：:]\s*(.+?)(?:\n|$)', text)
    if m: result['principle'] = m.group(1).strip()

    for key, icon in [('main_line', '🎯 本周主线'), ('must_complete', '✅ 本周必须完成'), ('push_forward', '🌱 本周推进即可'), ('temp_in', '📥 临时进入')]:
        m = re.search(rf'## {icon}\s*\n(.*?)(?=\n---|\n## |\Z)', text, re.DOTALL)
        if m:
            items = []
            for line in m.group(1).strip().split('\n'):
                s = line.strip()
                if s.startswith('- [x]') or s.startswith('- [ ]'): items.append(s[5:].strip())
                elif s.startswith('- ') and '>' not in s: items.append(s[2:].strip())
                elif s and not s.startswith('>') and not s.startswith('#'): items.append(s)
            result[key] = '\n'.join(items)

    # Daily sections
    dm = re.search(r'# 🗓 每日重点\s*\n(.*?)(?=\n# |\Z)', text, re.DOTALL)
    if dm:
        blocks = re.split(r'\n## (周[一二三四五六日])[^\n]*\n', dm.group(1))
        for i in range(1, len(blocks), 2):
            dn, dc = blocks[i], blocks[i+1]
            dd = {'focus': '', 'temp': '', 'done': '', 'migrated': '', 'dropped': '', 'interrupt': '', 'next': '', 'closed': False}

            m = re.search(r'> \[!todo\] 今日重点\s*\n(.*?)(?=> \[!|\Z)', dc, re.DOTALL)
            if m: dd['focus'] = _items(m.group(1))

            m = re.search(r'> \[!warning\] 临时插入\s*\n(.*?)(?=> \[!|\Z)', dc, re.DOTALL)
            if m: dd['temp'] = _items(m.group(1))

            m = re.search(r'\*\*完成[：:]\*\*\s*\n(.*?)(?=\n> \*\*|\Z)', dc, re.DOTALL)
            if m: dd['done'] = _items(m.group(1))

            m = re.search(r'\*\*迁移[：:]\*\*\s*\n(.*?)(?=\n> \*\*|\Z)', dc, re.DOTALL)
            if m: dd['migrated'] = _items(m.group(1))

            m = re.search(r'\*\*搁置 / 放弃[：:]\*\*\s*\n(.*?)(?=\n> \*\*|\Z)', dc, re.DOTALL)
            if m: dd['dropped'] = _items(m.group(1))

            m = re.search(r'\*\*主要打断[：:]\*\*\s*\n(.*?)(?=\n> \[!tip\]|\Z)', dc, re.DOTALL)
            if m: dd['interrupt'] = _items(m.group(1))

            m = re.search(r'> \[!tip\] (?:明日优先|下周优先)\s*\n(.*?)(?=\n---|\Z)', dc, re.DOTALL)
            if m: dd['next'] = _items(m.group(1))

            if dd['done'] or dd['migrated'] or dd['dropped']: dd['closed'] = True
            result['days'][dn] = dd

    rm = re.search(r'# 🔁 周复盘\s*\n(.*?)$', text, re.DOTALL)
    if rm: result['weekly_review'] = rm.group(1).strip()

    return result

def _items(text):
    items = []
    for line in text.strip().split('\n'):
        s = line.strip()
        if not s: continue
        if s.startswith('- [x]') or s.startswith('- [ ]'): items.append(s[5:].strip())
        elif s.startswith('- '): items.append(s[2:].strip())
        else: items.append(s)
    return '\n'.join(items)

def get_monday(year, week):
    j4 = date(year, 1, 4)
    return j4 - timedelta(days=j4.weekday()) + timedelta(weeks=week-1)

# ── Import ──
async def import_week(wk_name, data):
    week_num = int(wk_name.replace('WK', ''))
    monday = get_monday(2026, week_num)
    print(f'\n{"="*50}\n📅 {wk_name} ({monday})\n{"="*50}')

    # Week record
    existing = await api_get(f'/tables/{TABLE_W}/records', {'filter': f'CurrentValue.[周次]="{wk_name}"'})
    if existing['data']['items']:
        rid = existing['data']['items'][0]['record_id']
        print(f'  Week: exists ({rid})')
    else:
        r = await api_post(f'/tables/{TABLE_W}/records', {'fields': {
            '周次': wk_name,
            '周起始日期': int(datetime.combine(monday, datetime.min.time()).timestamp() * 1000),
            '本周原则': data['principle'], '本周主线': data['main_line'],
            '本周必须完成': data['must_complete'], '本周推进即可': data['push_forward'],
            '临时进入': data['temp_in'], '本周总结': data['weekly_review'],
            '状态': '已完成' if data['weekly_review'] else '进行中',
        }})
        rid = r['data']['record']['record_id']
        print(f'  Week: created ({rid})')

    await api_put(f'/tables/{TABLE_W}/records/{rid}', {'fields': {
        '本周主线': data['main_line'], '本周必须完成': data['must_complete'],
        '本周推进即可': data['push_forward'], '临时进入': data['temp_in'],
        '本周总结': data['weekly_review'],
    }})

    # Delete existing tasks
    tr = await api_get(f'/tables/{TABLE_T}/records', {'filter': f'CurrentValue.[所属周次]="{wk_name}"', 'page_size': 200})
    items = tr.get('data', {}).get('items', [])
    for item in items:
        await api_del(f'/tables/{TABLE_T}/records/{item["record_id"]}')
    print(f'  Tasks: deleted {len(items)}, creating...')

    # Create tasks
    tc = 0
    for tt, content in [('必须完成', data['must_complete']), ('推进即可', data['push_forward']), ('临时进入', data['temp_in'])]:
        if content:
            for line in content.split('\n'):
                line = line.strip()
                if line:
                    await api_post(f'/tables/{TABLE_T}/records', {'fields': {'任务内容': line, '所属周次': wk_name, '任务类型': tt, '来源': '本周计划'}})
                    tc += 1
    print(f'  Tasks: {tc} created')

    # Day records
    dc = 0
    for i, dn in enumerate(WEEKDAY_NAMES):
        if dn not in data['days']: continue
        dd = data['days'][dn]
        d = monday + timedelta(days=i)
        dms = int(datetime.combine(d, datetime.min.time()).timestamp() * 1000)
        ex = await api_get(f'/tables/{TABLE_D}/records', {'filter': f'CurrentValue.[所属周次]="{wk_name}"&&CurrentValue.[星期]="{dn}"'})
        ex_items = ex.get('data', {}).get('items', [])
        fields = {
            '今日重点': dd['focus'], '临时插入': dd['temp'], '收尾_完成': dd['done'],
            '收尾_迁移': dd['migrated'], '收尾_搁置放弃': dd['dropped'],
            '主要打断': dd['interrupt'], '明日优先': dd['next'],
            '收尾状态': '已收尾' if dd['closed'] else '未填写',
        }
        if ex_items:
            await api_put(f'/tables/{TABLE_D}/records/{ex_items[0]["record_id"]}', {'fields': fields})
        else:
            fields['日期'] = dms; fields['所属周次'] = wk_name; fields['星期'] = dn
            await api_post(f'/tables/{TABLE_D}/records', {'fields': fields})
        dc += 1
    print(f'  ✅ {dc} days imported')

async def main():
    weeks = sys.argv[1:] if len(sys.argv) > 1 else ['WK22', 'WK23', 'WK24', 'WK25']
    for wk in weeks:
        fp = os.path.join(OBSIDIAN_DIR, f'{wk}.md')
        if not os.path.exists(fp):
            print(f'⚠️  Not found: {fp}'); continue
        data = parse_wk(fp)
        await import_week(wk, data)
    print(f'\n🎉 Done!')

if __name__ == '__main__':
    asyncio.run(main())
