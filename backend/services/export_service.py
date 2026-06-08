from __future__ import annotations
"""WK.md 格式导出——从飞书多维表读取一周完整数据，渲染为 Markdown。"""
import logging
from datetime import date, datetime
from jinja2 import Template

from backend.services.week_service import get_week, get_week_monday
from backend.services.day_service import get_week_days, WEEKDAY_NAMES
from backend.services.task_service import list_tasks

logger = logging.getLogger(__name__)

# WK.md Jinja2 模板
WK_TEMPLATE = Template("""\
> 本周原则：{{ principle }}

---

## 🎯 本周主线

> [!tip] 本周判断优先级的依据
> 不是任务清单，最多 3 条。

{{ main_line or '1. \n2. \n3. ' }}

---

## ✅ 本周必须完成

> [!important] 硬交付
> 不完成会产生明确损失、影响交付，或阻塞他人。最多 5 件。

{% if must_complete_tasks %}{% for t in must_complete_tasks %}- [{{ 'x' if t.done else ' ' }}] {{ t.content }}
{% endfor %}{% else %}- [ ] {% endif %}

---

## 🌱 本周推进即可

> [!note] 重要但不一定要完成
> 有明确推进就算有效，不要把所有重要事项都变成压力。

{% if push_tasks %}{% for t in push_tasks %}- [{{ 'x' if t.done else ' ' }}] {{ t.content }}
{% endfor %}{% else %}- [ ] {% endif %}

---

## 📥 临时进入

> [!warning] 新任务缓冲区
> 新任务先放这里。只有比今日重点更重要，才进入今天。

{% if temp_tasks %}{% for t in temp_tasks %}- [{{ 'x' if t.done else ' ' }}] {{ t.content }}
{% endfor %}{% else %}- [ ] {% endif %}

---

# 🗓 每日重点

{% for day in days %}
## {{ day.weekday }}

> [!todo] 今日重点
> {{ day.today_focus or '- ' }}

> [!warning] 临时插入
> {{ day.temp_insert or '- ' }}

> [!done] 收尾
> **完成：**
> {{ day.done_list or '- ' }}

> **迁移：**
> {{ day.migrated or '- ' }}

> **搁置 / 放弃：**
> {{ day.abandoned or '- ' }}

> **主要打断：**
> {{ day.interruptions or '- ' }}

> [!tip] {{ '明日优先' if day.weekday != '周日' else '下周优先' }}
> {{ day.next_priority or '- ' }}

---
{% endfor %}
""")


async def export_wk_markdown(wk: str) -> str:
    """导出指定周为 WK.md 格式的 Markdown 字符串。"""
    # 获取周计划
    week = await get_week(wk)
    if not week:
        raise ValueError(f"周记录不存在: {wk}")

    # 获取日进度
    days = await get_week_days(wk)

    # 获取任务
    tasks = await list_tasks(wk)

    # 分类任务
    must_complete_tasks = [
        {"content": t.get("任务内容", ""), "done": t.get("完成状态", False)}
        for t in tasks if t.get("任务类型") == "必须完成"
    ]
    push_tasks = [
        {"content": t.get("任务内容", ""), "done": t.get("完成状态", False)}
        for t in tasks if t.get("任务类型") == "推进即可"
    ]
    temp_tasks = [
        {"content": t.get("任务内容", ""), "done": t.get("完成状态", False)}
        for t in tasks if t.get("任务类型") == "临时进入"
    ]

    # 整理日数据
    days_data = []
    for d in days:
        days_data.append({
            "weekday": d.get("星期", ""),
            "today_focus": d.get("今日重点", ""),
            "temp_insert": d.get("临时插入", ""),
            "done_list": d.get("收尾_完成", ""),
            "migrated": d.get("收尾_迁移", ""),
            "abandoned": d.get("收尾_搁置放弃", ""),
            "interruptions": d.get("主要打断", ""),
            "next_priority": d.get("明日优先", ""),
        })

    return WK_TEMPLATE.render(
        principle=week.get("本周原则", ""),
        main_line=week.get("本周主线", ""),
        must_complete_tasks=must_complete_tasks,
        push_tasks=push_tasks,
        temp_tasks=temp_tasks,
        days=days_data,
    )
