"""日进度业务逻辑——日记录的读写、收尾操作。"""
from __future__ import annotations
from typing import List
import logging
from datetime import date, datetime

from backend.config import settings
from backend.feishu import bitable
from backend.services.week_service import get_or_create_week

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _wk(d: date) -> str:
    iso = d.isocalendar()
    return f"WK{iso[1]}"


async def _get_week_days_map(wk: str) -> dict:
    """获取指定周的所有日记录，按星期分组返回 {星期: record}。"""
    filter_expr = f'CurrentValue.[所属周次]="{wk}"'
    records = await bitable.list_all_records(settings.TABLE_ID_DAILY, filter_expr=filter_expr)
    result = {}
    for r in records:
        f = r.get("fields", {})
        wd = f.get("星期", "")
        if wd and wd not in result:
            result[wd] = r  # 取第一条，避免重复
    return result


async def get_or_create_day(d: date) -> dict:
    """获取指定日期的日进度记录，不存在则创建。"""
    wk = _wk(d)
    wd_name = WEEKDAY_NAMES[d.weekday()]
    day_map = await _get_week_days_map(wk)

    if wd_name in day_map:
        return bitable.extract_record_fields(day_map[wd_name])

    # 不存在则创建
    await get_or_create_week(wk, today=d)
    date_ms = int(datetime.combine(d, datetime.min.time()).timestamp() * 1000)
    fields = {
        "日期": date_ms,
        "所属周次": wk,
        "星期": wd_name,
        "今日重点": "", "临时插入": "",
        "收尾_完成": "", "收尾_迁移": "", "收尾_搁置放弃": "",
        "主要打断": "", "明日优先": "", "收尾状态": "未填写",
    }
    record = await bitable.create_record(settings.TABLE_ID_DAILY, fields)
    return bitable.extract_record_fields(record)


async def get_day(d: date) -> dict:
    """获取指定日期的日进度（不自动创建）。"""
    wk = _wk(d)
    wd_name = WEEKDAY_NAMES[d.weekday()]
    day_map = await _get_week_days_map(wk)
    if wd_name in day_map:
        return bitable.extract_record_fields(day_map[wd_name])
    return {}


async def get_week_days(wk: str) -> List[dict]:
    """获取指定周的所有日进度记录。"""
    filter_expr = f'CurrentValue.[所属周次]="{wk}"'
    records = await bitable.list_all_records(settings.TABLE_ID_DAILY, filter_expr=filter_expr)
    return [bitable.extract_record_fields(r) for r in records]


async def update_day(d: date, fields: dict) -> dict:
    """更新指定日期的日进度字段。"""
    day_record = await get_or_create_day(d)
    record_id = day_record["record_id"]
    updated = await bitable.update_record(settings.TABLE_ID_DAILY, record_id, fields)
    return bitable.extract_record_fields(updated)


async def close_day(d: date) -> dict:
    """一键收尾——标记已收尾，自动复制今日重点到完成区。"""
    day_record = await get_or_create_day(d)

    update_fields = {"收尾状态": "已收尾"}

    if not day_record.get("收尾_完成"):
        tf = day_record.get("今日重点", "")
        if tf:
            update_fields["收尾_完成"] = tf

    if not day_record.get("收尾_迁移"):
        ti = day_record.get("临时插入", "")
        if ti:
            update_fields["收尾_迁移"] = ti

    record_id = day_record["record_id"]
    updated = await bitable.update_record(settings.TABLE_ID_DAILY, record_id, update_fields)
    return bitable.extract_record_fields(updated)
