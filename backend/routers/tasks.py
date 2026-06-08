from __future__ import annotations
from typing import Optional
"""周任务路由——任务 CRUD、排序。"""
from fastapi import APIRouter, HTTPException

from backend.services.task_service import (
    list_tasks,
    create_task,
    update_task,
    delete_task,
    reorder_tasks,
)

router = APIRouter(prefix="/api", tags=["周任务"])


@router.get("/weeks/{wk}/tasks")
async def list_tasks_api(wk: str, task_type: Optional[str] = None):
    """获取指定周的任务列表。"""
    try:
        tasks = await list_tasks(wk, task_type=task_type)
        return {"code": 0, "data": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weeks/{wk}/tasks")
async def create_task_api(wk: str, body: dict):
    """新增任务。body: {content, task_type, source}"""
    try:
        task = await create_task(
            wk,
            content=body.get("content", ""),
            task_type=body.get("task_type", "必须完成"),
            source=body.get("source", "本周计划"),
        )
        return {"code": 0, "data": task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/weeks/{wk}/tasks/{task_id}")
async def update_task_api(wk: str, task_id: str, fields: dict):
    """更新任务（含勾选完成）。"""
    try:
        task = await update_task(task_id, fields)
        return {"code": 0, "data": task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/weeks/{wk}/tasks/{task_id}")
async def delete_task_api(wk: str, task_id: str):
    """删除任务。"""
    try:
        await delete_task(task_id)
        return {"code": 0, "message": "已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/weeks/{wk}/tasks/reorder")
async def reorder_tasks_api(wk: str, body: dict):
    """批量更新任务排序。body: {task_ids: [...]}"""
    try:
        task_ids = body.get("task_ids", [])
        await reorder_tasks(task_ids)
        return {"code": 0, "message": "排序已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
