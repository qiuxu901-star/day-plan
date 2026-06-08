from __future__ import annotations
from typing import Optional, List
"""周任务业务逻辑——任务 CRUD、排序、统计。"""
import logging
from datetime import date, datetime

from backend.config import settings
from backend.feishu import bitable

logger = logging.getLogger(__name__)


async def list_tasks(wk: str, task_type: Optional[str] = None) -> List[dict]:
    """获取指定周的所有任务，可按类型筛选。"""
    filter_expr = f'CurrentValue.[所属周次]="{wk}"'
    if task_type:
        filter_expr += f' && CurrentValue.[任务类型]="{task_type}"'

    records = await bitable.list_all_records(
        settings.TABLE_ID_TASKS,
        filter_expr=filter_expr,
    )
    return [bitable.extract_record_fields(r) for r in records]


async def create_task(wk: str, content: str, task_type: str = "必须完成",
                      source: str = "本周计划") -> dict:
    """新增一条周任务。"""
    fields = {
        "任务内容": content,
        "所属周次": wk,
        "任务类型": task_type,
        "完成状态": False,
        "完成日期": None,
        "来源": source,
        "排序": 0,  # TODO: 自动计算末位排序
    }
    record = await bitable.create_record(settings.TABLE_ID_TASKS, fields)
    return bitable.extract_record_fields(record)


async def update_task(task_id: str, fields: dict) -> dict:
    """更新任务（含勾选完成状态、自动填写完成日期）。"""
    # 如果标记为完成且未提供完成日期，自动设置为今天
    if fields.get("完成状态") is True and "完成日期" not in fields:
        today_ms = int(datetime.combine(date.today(), datetime.min.time()).timestamp() * 1000)
        fields["完成日期"] = today_ms

    record = await bitable.update_record(settings.TABLE_ID_TASKS, task_id, fields)
    return bitable.extract_record_fields(record)


async def delete_task(task_id: str) -> bool:
    """删除一条任务。"""
    return await bitable.delete_record(settings.TABLE_ID_TASKS, task_id)


async def reorder_tasks(task_ids: List[str]) -> bool:
    """批量更新任务排序（按数组顺序 = 新排序）。"""
    for idx, task_id in enumerate(task_ids):
        await bitable.update_record(settings.TABLE_ID_TASKS, task_id, {"排序": idx})
    return True
