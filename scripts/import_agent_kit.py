#!/usr/bin/env python3
"""服务器端：把 agent kit JSON 包写入 workboard.db。幂等，可重复执行。"""
import sqlite3, json, pathlib, datetime, hashlib, sys

DB = pathlib.Path('/home/admin/workboard/data/workboard.db')
PACK = pathlib.Path('/tmp/agent_kit_pack.json')

def now():
    return datetime.datetime.now().isoformat(timespec='seconds') + 'Z'

def main():
    if not PACK.exists():
        print('包不存在:', PACK); return 1
    pack = json.loads(PACK.read_text(encoding='utf-8'))
    c = sqlite3.connect(str(DB))
    ts = now()

    # 1) 建表
    c.execute('CREATE TABLE IF NOT EXISTS prompts (key TEXT PRIMARY KEY, content TEXT, updated_at TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS skill_refs (
        skill_name TEXT, ref_key TEXT, content TEXT, updated_at TEXT,
        PRIMARY KEY (skill_name, ref_key))''')

    # 2) 提示词：00-agent-system → system（主提示词，独立槽位）
    #    01/02/03 → 可选补充；不动现有 intent/qa（结构化分类器不能被散文替换）
    key_map = {
        '00-agent-system': 'system',
        '01-strategic-advisor': 'strategic',
        '02-execution-coach': 'coach',
        '03-skill-generator': 'generator',
    }
    for src, dst in key_map.items():
        if src in pack['prompts']:
            c.execute('INSERT OR REPLACE INTO prompts (key,content,updated_at) VALUES (?,?,?)',
                      (dst, pack['prompts'][src], ts))
            print('提示词:', dst, '<-', src)

    # 3) 技能：替换旧 4 个 workboard-*，导入新 6 个
    old = [r[0] for r in c.execute("SELECT name FROM skills WHERE name LIKE 'workboard-%'")]
    if old:
        c.execute("DELETE FROM skills WHERE name LIKE 'workboard-%'")
        print('移除旧技能:', ', '.join(old))
    for s in pack['skills']:
        sid = 's_' + hashlib.sha1(s['name'].encode()).hexdigest()[:12]
        scripts = '{}'
        related = json.dumps([k for k in pack['references']], ensure_ascii=False)
        sha = hashlib.sha256(s['content'].encode()).hexdigest()
        c.execute('''INSERT OR REPLACE INTO skills
            (id,name,description,content,status,created_at,updated_at,scripts_json,related_json,source_sha,origin)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (sid, s['name'], s['description'], s['content'], 'active', ts, ts,
             scripts, related, sha, 'agent-kit'))
        print('技能:', s['name'])

    # 4) 参考规则：作为技能附带资料存入（每个技能关联全部4份，按需读取）
    for name, content in pack['references'].items():
        for s in pack['skills']:
            c.execute('INSERT OR REPLACE INTO skill_refs (skill_name,ref_key,content,updated_at) VALUES (?,?,?,?)',
                      (s['name'], name, content, ts))
        print('参考:', name)

    # 5) 验收用例与README 也存一份备查
    c.execute('INSERT OR REPLACE INTO prompts (key,content,updated_at) VALUES (?,?,?)',
              ('__tests', pack.get('tests', ''), ts))
    c.execute('INSERT OR REPLACE INTO prompts (key,content,updated_at) VALUES (?,?,?)',
              ('__readme', pack.get('readme', ''), ts))

    c.commit()
    print('完成 | 技能', c.execute('SELECT count(*) FROM skills').fetchone()[0],
          '| 提示词', c.execute('SELECT count(*) FROM prompts').fetchone()[0],
          '| 参考条目', c.execute('SELECT count(*) FROM skill_refs').fetchone()[0])
    return 0

if __name__ == '__main__':
    sys.exit(main())
