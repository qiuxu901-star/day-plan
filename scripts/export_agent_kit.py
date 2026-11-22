#!/usr/bin/env python3
"""把 time-energy-agent-kit 文件夹打包成 JSON，供服务器导入。"""
import pathlib, json, re, sys

KIT = pathlib.Path('/Users/qiuxu/Downloads/time-energy-agent-kit')
OUT = pathlib.Path('/tmp/agent_kit_pack.json')

def parse_skill(p):
    text = p.read_text(encoding='utf-8')
    name, desc = p.parent.name, ''
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if m:
        fm = m.group(1)
        nm = re.search(r'^name:\s*(.+)$', fm, re.M)
        dm = re.search(r'^description:\s*(.*?)(?=\n\w+:|\Z)', fm, re.M | re.S)
        if nm: name = nm.group(1).strip()
        if dm: desc = ' '.join(dm.group(1).split())
    return {'name': name, 'description': desc, 'content': text,
            'origin': 'agent-kit', 'source': str(p.relative_to(KIT))}

def main():
    if not KIT.exists():
        print('套件目录不存在:', KIT); return 1
    pack = {'prompts': {}, 'skills': [], 'references': {}}
    for p in sorted((KIT/'prompts').glob('*.md')):
        pack['prompts'][p.stem] = p.read_text(encoding='utf-8')
    for p in sorted((KIT/'skills').glob('*/SKILL.md')):
        pack['skills'].append(parse_skill(p))
    for p in sorted((KIT/'reference').glob('*.md')):
        pack['references'][p.stem] = p.read_text(encoding='utf-8')
    pack['tests'] = (KIT/'tests'/'acceptance-cases.md').read_text(encoding='utf-8')
    pack['readme'] = (KIT/'README.md').read_text(encoding='utf-8')
    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding='utf-8')
    print('导出:', OUT)
    print('  提示词', len(pack['prompts']), '| 技能', len(pack['skills']), '| 参考', len(pack['references']))
    for s in pack['skills']:
        print('   -', s['name'], '| 描述', len(s['description']), '字 | 正文', len(s['content']), '字')
    return 0

if __name__ == '__main__':
    sys.exit(main())
