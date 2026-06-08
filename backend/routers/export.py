from __future__ import annotations
"""WK.md 导出路由。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from backend.services.export_service import export_wk_markdown

router = APIRouter(prefix="/api", tags=["导出"])


@router.get("/weeks/{wk}/export")
async def export_week_api(wk: str):
    """导出指定周为 WK.md 格式文件。"""
    try:
        md = await export_wk_markdown(wk)
        return PlainTextResponse(
            content=md,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={wk}.md"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
