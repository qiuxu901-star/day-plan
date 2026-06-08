from __future__ import annotations
from typing import Optional
"""周计划路由——当前周、周列表、周详情、周更新、周统计。"""
from datetime import date
from fastapi import APIRouter, HTTPException

from backend.services.week_service import (
    get_current_week_key,
    get_or_create_week,
    list_weeks,
    get_week,
    update_week,
    get_week_stats,
)

router = APIRouter(prefix="/api", tags=["周计划"])


@router.get("/weeks/current")
async def current_week():
    """获取当前周（自动创建如不存在）。"""
    wk = get_current_week_key()
    try:
        week = await get_or_create_week(wk)
        return {"code": 0, "data": week}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weeks")
async def list_weeks_api(page_size: int = 20, page_token: str = ""):
    """获取周列表。"""
    try:
        data = await list_weeks(page_size=page_size, page_token=page_token or None)
        return {"code": 0, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weeks/{wk}")
async def get_week_api(wk: str):
    """获取指定周详情（不存在则自动创建）。"""
    try:
        week = await get_or_create_week(wk)
        return {"code": 0, "data": week}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weeks")
async def create_week_api(wk: Optional[str] = None):
    """创建新周（如不指定 wk，则创建当前周）。"""
    try:
        wk = wk or get_current_week_key()
        week = await get_or_create_week(wk)
        return {"code": 0, "data": week}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/weeks/{wk}")
async def update_week_api(wk: str, fields: dict):
    """更新周计划字段。"""
    try:
        week = await update_week(wk, fields)
        return {"code": 0, "data": week}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weeks/{wk}/stats")
async def week_stats_api(wk: str):
    """获取本周统计。"""
    try:
        stats = await get_week_stats(wk)
        return {"code": 0, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
