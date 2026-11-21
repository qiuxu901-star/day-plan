#!/usr/bin/env python3
"""写入技能管理页的初始技能（仅在 skills 表为空时执行，不覆盖用户编辑）。"""
import sqlite3, pathlib, hashlib, sys
DB = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'workboard.db'
SEED = [
 ('workboard-today-plan','开工汇总 · TOP3 透出',
  '用户说「开工/今日计划/今天重点」时使用。先跑 fetch_workboard.py 取数（优先自托管 API，登录换 JWT），再跑 analyze_plan.py 打分。输出四段：总表、延期、今日、近期；第一屏必须是「今天最关键的3件事」。打分：P0=100/P1=60/P2=30，逾期每天+4(上限60)，今日到期+50，进行中+20。零臆造。'),
 ('workboard-today-review','收工复盘',
  '用户说「收工/今日完成/复盘今天」时使用。取数同 plan，跑 analyze_review.py。输出：完成汇总、时间线、时间空缺、计划与实际差异、历史逾期。零臆造。'),
 ('workboard-database-write','记录写入',
  '用户口述「计划/记录/已完成」时写入任务/时间/收集箱/复盘表。默认补全：状态=待办、来源=手动、计划日=到期日=次日。写完必回读校验。当前写入走自托管 API（~/.workbuddy/workboard/config.json），不再直接写平台表。'),
 ('workboard-page-publish','页面发布',
  '自托管架构下已停用（原用于发布到 WorkBuddy 资料库 page）。新流程：本地改 web/workboard.fusion.html → python3 scripts/make_h5.py 生成 web/workboard.html → git push → 服务器 bash deploy/deploy.sh。'),
]
def main():
    if not DB.exists():
        print('数据库不存在:',DB); return 1
    c=sqlite3.connect(DB)
    n=c.execute('SELECT count(*) FROM skills').fetchone()[0]
    if n:
        print(f'skills 表已有 {n} 条，跳过初始化'); return 0
    import datetime
    ts=datetime.datetime.now().isoformat(timespec='seconds')+'Z'
    for name,desc,content in SEED:
        c.execute('INSERT INTO skills (id,name,description,content,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                  ('s_'+hashlib.sha1(name.encode()).hexdigest()[:12],name,desc,content,'active',ts,ts))
    c.commit()
    print('已写入',len(SEED),'条初始技能')
    return 0
if __name__=='__main__': sys.exit(main())
