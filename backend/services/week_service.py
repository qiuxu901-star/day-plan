"""周计划业务逻辑——当前周计算、周计划 CRUD、统计。"""
from __future__ import annotations
from typing import Optional
import logging
from datetime import date, datetime, timedelta

from backend.config import settings
from backend.feishu import bitable

logger = logging.getLogger(__name__)


def get_current_week_key(today: Optional[date] = None) -> str:
    """根据日期计算 ISO 周次标识，如 'WK24'。"""
    today = today or date.today()
    iso = today.isocalendar()
    return f"WK{iso[1]}"


def get_week_monday(year: int, week: int) -> date:
    """根据 ISO 年份和周号，返回该周周一日期。"""
    # ISO 第 1 周 = 包含 1 月 4 日的那周
    jan4 = date(year, 1, 4)
    monday_of_week1 = jan4 - timedelta(days=jan4.weekday())
    return monday_of_week1 + timedelta(weeks=week - 1)


async def get_or_create_week(wk: str, today: Optional[date] = None) -> dict:
    """获取指定周记录，如不存在则自动创建。"""
    filter_expr = f'CurrentValue.[周次]="{wk}"'
    records = await bitable.list_all_records(settings.TABLE_ID_WEEKLY, filter_expr=filter_expr)

    if records:
        return bitable.extract_record_fields(records[0])

    # 自动创建
    today = today or date.today()
    year = today.year
    week_num = int(wk.replace("WK", ""))
    monday = get_week_monday(year, week_num)

    fields = {
        "周次": wk,
        "周起始日期": int(datetime.combine(monday, datetime.min.time()).timestamp() * 1000),
        "本周原则": "少承诺、重推进、每天只抓最重要的 1-3 件事。",
        "本周主线": "",
        "本周必须完成": "",
        "本周推进即可": "",
        "临时进入": "",
        "本周总结": "",
        "状态": "进行中",
    }
    record = await bitable.create_record(settings.TABLE_ID_WEEKLY, fields)
    return bitable.extract_record_fields(record)


async def list_weeks(page_size: int = 20, page_token: Optional[str] = None) -> dict:
    """列出所有周（按周起始日期倒序）。"""
    data = await bitable.list_records(
        settings.TABLE_ID_WEEKLY,
        page_size=page_size,
        page_token=page_token,
    )
    return {
        "items": [bitable.extract_record_fields(r) for r in data.get("items", [])],
        "has_more": data.get("has_more", False),
        "page_token": data.get("page_token", ""),
    }


async def get_week(wk: str) -> Optional[dict]:
    """获取指定周详情。"""
    filter_expr = f'CurrentValue.[周次]="{wk}"'
    records = await bitable.list_all_records(settings.TABLE_ID_WEEKLY, filter_expr=filter_expr)
    if not records:
        return None
    return bitable.extract_record_fields(records[0])


async def update_week(wk: str, fields: dict) -> dict:
    """更新周计划字段（部分更新）。先查找 record_id，再更新。"""
    filter_expr = f'CurrentValue.[周次]="{wk}"'
    records = await bitable.list_all_records(settings.TABLE_ID_WEEKLY, filter_expr=filter_expr)
    if not records:
        raise ValueError(f"周记录不存在: {wk}")

    record_id = records[0]["record_id"]
    updated = await bitable.update_record(settings.TABLE_ID_WEEKLY, record_id, fields)
    return bitable.extract_record_fields(updated)


async def get_week_stats(wk: str) -> dict:
    """获取本周统计：各类任务完成率、收尾天数。"""
    # 任务统计
    tasks = await bitable.list_all_records(
        settings.TABLE_ID_TASKS,
        filter_expr=f'CurrentValue.[所属周次]="{wk}"',
    )

    must_total, must_done = 0, 0
    push_total, push_done = 0, 0
    temp_total, temp_done = 0, 0

    for t in tasks:
        fields = t.get("fields", {})
        task_type = fields.get("任务类型", "")
        done = fields.get("完成状态", False)

        if task_type == "必须完成":
            must_total += 1
            if done:
                must_done += 1
        elif task_type == "推进即可":
            push_total += 1
            if done:
                push_done += 1
        elif task_type == "临时进入":
            temp_total += 1
            if done:
                temp_done += 1

    # 收尾统计
    days = await bitable.list_all_records(
        settings.TABLE_ID_DAILY,
        filter_expr=f'CurrentValue.[所属周次]="{wk}"',
    )
    days_closed = sum(
        1 for d in days if d.get("fields", {}).get("收尾状态") == "已收尾"
    )

    return {
        "must_complete": {"total": must_total, "done": must_done,
                          "rate": must_done / must_total if must_total else 0},
        "push_forward": {"total": push_total, "done": push_done,
                         "rate": push_done / push_total if push_total else 0},
        "temp_in": {"total": temp_total, "done": temp_done,
                    "rate": temp_done / temp_total if temp_total else 0},
        "days_closed": days_closed,
        "days_total": len(days),
    }
