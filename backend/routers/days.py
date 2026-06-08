from __future__ import annotations
"""日进度路由——今日进度、周内日列表、日更新、收尾。"""
from datetime import date, datetime
from fastapi import APIRouter, HTTPException

from backend.services.day_service import (
    get_or_create_day,
    get_day,
    get_week_days,
    update_day,
    close_day,
)

router = APIRouter(prefix="/api", tags=["日进度"])


@router.get("/days/today")
async def today_api():
    """获取今日进度（自动创建如不存在）。"""
    try:
        day = await get_or_create_day(date.today())
        return {"code": 0, "data": day}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weeks/{wk}/days")
async def week_days_api(wk: str):
    """获取指定周的所有日进度。"""
    try:
        days = await get_week_days(wk)
        return {"code": 0, "data": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weeks/{wk}/days/{date_str}")
async def get_day_api(wk: str, date_str: str):
    """获取指定日期的日进度。date_str 格式: YYYY-MM-DD"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        day = await get_day(d)
        if not day:
            # 自动创建
            day = await get_or_create_day(d)
        return {"code": 0, "data": day}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"日期格式错误: {date_str}，应为 YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/weeks/{wk}/days/{date_str}")
async def update_day_api(wk: str, date_str: str, fields: dict):
    """更新指定日期的日进度字段。"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        day = await update_day(d, fields)
        return {"code": 0, "data": day}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/weeks/{wk}/days/{date_str}/close")
async def close_day_api(wk: str, date_str: str):
    """一键收尾。"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        day = await close_day(d)
        return {"code": 0, "data": day, "message": "收尾完成"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
