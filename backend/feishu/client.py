from __future__ import annotations
from typing import Optional
"""飞书 HTTP 客户端封装——统一处理认证头和错误。"""
import httpx
from backend.feishu.auth import get_tenant_access_token


class FeishuClient:
    """飞书 API 的轻量 HTTP 客户端。"""

    def __init__(self):
        self._base = "https://open.feishu.cn/open-apis"

    async def _headers(self) -> dict:
        token = await get_tenant_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}{path}",
                headers=await self._headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    async def post(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}{path}",
                headers=await self._headers(),
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    async def put(self, path: str, body: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self._base}{path}",
                headers=await self._headers(),
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    async def delete(self, path: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self._base}{path}",
                headers=await self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()


# 全局单例
client = FeishuClient()
