"""FastAPI 应用入口——注册路由、CORS、启动事件。"""
from __future__ import annotations
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.config import settings
from backend.routers import weeks, days, tasks, export as export_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="周计划 Web 看板", version="1.0.0", docs_url="/api/docs", redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# API 路由（先注册，优先匹配）
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

app.include_router(weeks.router)
app.include_router(days.router)
app.include_router(tasks.router)
app.include_router(export_router.router)

# 前端静态文件（兜底，API 路由优先）
frontend_dir = (Path(__file__).parent.parent / "frontend").resolve()


@app.get("/{filename:path}")
async def serve_frontend(filename: str):
    """SPA：匹配文件就返回文件，否则返回 index.html"""
    file_path = frontend_dir / filename
    if filename and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(frontend_dir / "index.html")


@app.on_event("startup")
async def startup():
    missing = settings.validate()
    if missing:
        logger.error("❌ 缺少必要配置: %s", ", ".join(missing))
    else:
        logger.info(f"✅ 配置校验通过 | 🚀 http://127.0.0.1:8000")
