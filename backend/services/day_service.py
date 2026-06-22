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


def _has_content(fields: dict) -> bool:
    """判断日记录是否有实际内容（非空字段）。"""
    return bool(
        fields.get("今日重点") or fields.get("临时插入")
        or fields.get("收尾_完成") or fields.get("收尾_迁移")
        or fields.get("收尾_搁置放弃") or fields.get("主要打断")
        or fields.get("明日优先")
    )


async def _get_week_days_map(wk: str) -> dict:
    """获取指定周的所有日记录，按星期分组返回 {星期: record}。

    有内容的记录优先于空记录；如果多条都有内容，保留最先返回的。
    """
    filter_expr = f'CurrentValue.[所属周次]="{wk}"'
    records = await bitable.list_all_records(settings.TABLE_ID_DAILY, filter_expr=filter_expr)
    result = {}
    for r in records:
        f = r.get("fields", {})
        wd = f.get("星期", "")
        if not wd:
            continue
        existing = result.get(wd)
        if existing is None:
            result[wd] = r
        else:
            # 新记录有内容、旧记录无内容时替换
            if _has_content(f) and not _has_content(existing.get("fields", {})):
                result[wd] = r
    return result


async def _dedup_weekday(wk: str, wd_name: str) -> int:
    """删除指定周+星期的重复记录，保留确定性选择的一条（并发安全）。

    选择策略（确定性，所有并发调用收敛到同一结果）：
    1. 优先保留有内容的记录（取 record_id 最小的）
    2. 都无内容时保留 record_id 最小的
    """
    filter_expr = f'CurrentValue.[所属周次]="{wk}"'
    records = await bitable.list_all_records(settings.TABLE_ID_DAILY, filter_expr=filter_expr)

    same_wd = [r for r in records if r.get("fields", {}).get("星期") == wd_name]
    if len(same_wd) <= 1:
        return 0

    # 确定性选择：有内容优先，同类型按 record_id 升序
    with_content = [r for r in same_wd if _has_content(r.get("fields", {}))]
    without_content = [r for r in same_wd if not _has_content(r.get("fields", {}))]

    if with_content:
        with_content.sort(key=lambda r: r["record_id"])
        keep = with_content[0]
    else:
        without_content.sort(key=lambda r: r["record_id"])
        keep = without_content[0]

    deleted = 0
    for r in same_wd:
        if r["record_id"] != keep["record_id"]:
            try:
                await bitable.delete_record(settings.TABLE_ID_DAILY, r["record_id"])
                deleted += 1
            except Exception as e:
                # 可能已被其他并发调用删除，忽略
                logger.debug(f"删除重复记录失败（可能已删除） {r['record_id']}: {e}")

    if deleted:
        logger.warning(f"去重: {wk} {wd_name} 删除了 {deleted} 条重复记录，保留了 {keep['record_id']}")
    return deleted


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

    # 去重：防止并发创建导致的重复记录（确定性选择，并发安全）
    await _dedup_weekday(wk, wd_name)

    # 重新获取（可能被去重替换为有内容的记录）
    day_map = await _get_week_days_map(wk)
    if wd_name in day_map:
        return bitable.extract_record_fields(day_map[wd_name])

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
