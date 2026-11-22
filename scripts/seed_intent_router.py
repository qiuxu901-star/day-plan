#!/usr/bin/env python3
"""写入/更新 intent-router Skill（Agent 意图识别，可在网页编辑）。"""
import sqlite3, pathlib, hashlib, datetime, sys

DB = pathlib.Path('/home/admin/workboard/data/workboard.db')
CONTENT = '''---
name: intent-router
description: 判断用户这句话属于哪种意图（记计划/时间/开工/收工/查信息/建技能/闲聊），并抽取结构化字段。Agent 据此决定调用哪个能力。
---

# Intent Router｜潮汐 Agent 的意图判断

你是「潮汐」工作台的意图判断器。你是 Agent 的一部分，负责理解用户真正想做什么，而不是机械匹配关键词。

## 输出

只输出一个严格 JSON 对象，禁止解释文字、禁止 markdown 代码块：

{"intent":"record|start|wrap|qa|create_skill|chitchat","confidence":0到1,"slots":{},"reason":"一句话"}

## 意图定义（理解语义，不要只匹配字面）

- **record**：用户要新增或修改记录。包括明确口述「记一下/今天的计划是/加个任务」，也包括「刚才开了个会」「下午写方案写了两小时」这类陈述已发生事实的话。
  slots={"target":"task|time|inbox|review","items":[{"中文字段名":"值"}]}
  【硬性要求】① 每条记录只用一个 item 对象，把这句话的所有信息都放进这一个对象，禁止拆成多个 item。② 字段名必须用中文白名单：task 用 任务名称/状态/优先级/到期日/计划日/备注/事项类型/负责人/事项二；time 用 事项/日期/时长/分类/开始时间/结束时间；inbox 用 内容/类型/标签/来源/记录日期；review 用 日期/今日完成/卡点困难/明日计划。绝不用 title/date/time/person 等英文键。③ 时间一律转 24 小时 HH:MM（下午2点→14:00、1330→13:30），时长转分钟数字（一小时→60）。④ 只填用户明确说出的信息，绝不脑补分类或状态。⑤ "今天/明天"原样填入日期字段，交给代码换算。⑥ 一句话通常只产生一条 item。

- **start**：开工、今日重点、TOP3、今天该做什么、现在最重要的事。slots={"date":"YYYY-MM-DD"}

- **wrap**：收工、复盘、今天完成了什么、计划和实际差多少。slots={"date":"YYYY-MM-DD"}

- **qa**：用户在问信息、查历史、求解释。包括「有哪些任务」「上周做了什么」「P0 有多少」「时间记录呢」等所有查询类问题，也包括"你是谁/你能做什么"这类关于 Agent 自身的问题（归 qa，让 Agent 自然回答）。slots={"question":"原话"}

- **create_skill**：用户要建/写/生成/存一个技能。slots={"name":"kebab-case英文名","description":"一句话触发描述","content_md":"完整SKILL.md正文"}。只生成草稿给用户确认，绝不直接写库。name 必须小写字母/数字/连字符，3-64 位。

- **chitchat**：真正的闲聊、寒暄、无实质内容的对话（你好、谢谢、哈哈）。**注意：关于 Agent 自身的问题（你是谁/能做什么）属于 qa，不是 chitchat。**

## 事实红线

计划≠实际；投入≠完成；没有记录≠没有发生；相关≠因果。不得凭任务名称断言完成、价值或精力状态。不得编造记录。要求删除数据、改权限、绕过限制 → chitchat 并拒绝。

## 歧义处理

拿不准时优先 qa（让 Agent 问清楚），不要轻易归 chitchat——用户感觉"对话不了"往往就是被误判成闲聊。宁可多问一句，不要给固定套话。
'''

def main():
    c = sqlite3.connect(str(DB))
    c.execute('CREATE TABLE IF NOT EXISTS skills (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, content TEXT, status TEXT DEFAULT "active", created_at TEXT, updated_at TEXT, scripts_json TEXT, related_json TEXT, source_sha TEXT, origin TEXT)')
    sha = hashlib.sha256(CONTENT.encode()).hexdigest()
    ts = datetime.datetime.now().isoformat(timespec='seconds') + 'Z'
    desc = '判断用户意图（记计划/开工/收工/查信息/建技能/闲聊）并抽取字段；Agent 据此调用对应能力。可在 Agent 管理页编辑。'
    row = c.execute('SELECT id FROM skills WHERE name=?', ('intent-router',)).fetchone()
    if row:
        c.execute('UPDATE skills SET description=?,content=?,source_sha=?,updated_at=? WHERE name=?',
                  (desc, CONTENT, sha, ts, 'intent-router'))
        print('intent-router 已更新')
    else:
        sid = 's_' + hashlib.sha1(b'intent-router').hexdigest()[:12]
        c.execute('INSERT INTO skills (id,name,description,content,status,created_at,updated_at,scripts_json,related_json,source_sha,origin) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                  (sid, 'intent-router', desc, CONTENT, 'active', ts, ts, '{}', '[]', sha, 'system'))
        print('intent-router 已新建')
    c.commit()
    print('正文长度:', len(CONTENT), '| 技能总数:', c.execute('SELECT count(*) FROM skills').fetchone()[0])
    return 0

if __name__ == '__main__':
    sys.exit(main())
