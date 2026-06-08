"""飞书 Tenant Access Token 管理与自动刷新。"""
from __future__ import annotations
from typing import Optional
import time
import logging
import httpx
from backend.config import settings

logger = logging.getLogger(__name__)

# 模块级缓存
_cached_token: Optional[str] = None
_expires_at: float = 0.0

# 提前 5 分钟刷新，避免边界情况
REFRESH_BEFORE_SECONDS = 300


async def get_tenant_access_token() -> str:
    """获取 tenant_access_token，自动缓存和刷新。"""
    global _cached_token, _expires_at

    if _cached_token and time.time() < _expires_at - REFRESH_BEFORE_SECONDS:
        return _cached_token

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": settings.FEISHU_APP_ID,
        "app_secret": settings.FEISHU_APP_SECRET,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 Token 失败: {data}")

    _cached_token = data["tenant_access_token"]
    _expires_at = time.time() + data.get("expire", 7200)
    logger.info("飞书 Token 已刷新，有效期至 %s", time.ctime(_expires_at))
    return _cached_token
