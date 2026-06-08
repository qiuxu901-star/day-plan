from __future__ import annotations
from typing import Optional, List, Union
"""飞书多维表操作的通用封装——列表、读取、新增、更新、删除记录。"""
import logging
from backend.config import settings
from backend.feishu.client import client

logger = logging.getLogger(__name__)

# 每页读取记录数
PAGE_SIZE = 100


def _bitable_path(table_id: str) -> str:
    return f"/bitable/v1/apps/{settings.BITABLE_APP_TOKEN}/tables/{table_id}/records"


def _unwrap(result: dict) -> dict:
    """检查飞书 API 返回 code，失败抛异常。"""
    code = result.get("code", -1)
    if code != 0:
        msg = result.get("msg", "未知错误")
        raise RuntimeError(f"飞书多维表 API 错误 (code={code}): {msg}")
    return result.get("data", {})


# ── 通用 CRUD ──────────────────────────────────────────

async def list_records(
    table_id: str,
    filter_expr: Optional[str] = None,
    page_size: int = PAGE_SIZE,
    page_token: Optional[str] = None,
    sort: Optional[list] = None,
) -> dict:
    """列出记录（支持筛选、分页、排序）。"""
    params: dict = {"page_size": page_size}
    if filter_expr:
        params["filter"] = filter_expr
    if page_token:
        params["page_token"] = page_token
    if sort:
        params["sort"] = sort

    result = await client.get(_bitable_path(table_id), params=params)
    return _unwrap(result)


async def list_all_records(
    table_id: str,
    filter_expr: Optional[str] = None,
    sort: Optional[list] = None,
) -> List[dict]:
    """获取全部记录（自动翻页）。"""
    all_items = []
    page_token = None
    while True:
        data = await list_records(table_id, filter_expr=filter_expr, page_token=page_token, sort=sort)
        all_items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return all_items


async def get_record(table_id: str, record_id: str) -> dict:
    """获取单条记录。"""
    path = f"{_bitable_path(table_id)}/{record_id}"
    result = await client.get(path)
    return _unwrap(result).get("record", {})


async def create_record(table_id: str, fields: dict) -> dict:
    """新增一条记录，返回创建的记录。"""
    result = await client.post(_bitable_path(table_id), {"fields": fields})
    return _unwrap(result).get("record", {})


async def update_record(table_id: str, record_id: str, fields: dict) -> dict:
    """更新一条记录（部分更新）。"""
    path = f"{_bitable_path(table_id)}/{record_id}"
    result = await client.put(path, {"fields": fields})
    return _unwrap(result).get("record", {})


async def delete_record(table_id: str, record_id: str) -> bool:
    """删除一条记录。"""
    path = f"{_bitable_path(table_id)}/{record_id}"
    result = await client.delete(path)
    _unwrap(result)
    return True


# ── 多行文本 ↔ 纯文本转换 ──────────────────────────────

def multiline_to_text(field_value: Union[list, Optional][str]) -> str:
    """飞书多行文本 → 换行分隔的纯文本。"""
    if field_value is None:
        return ""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, list):
        return "\n".join(
            item.get("text", "") for item in field_value
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return str(field_value)


def text_to_multiline(text: str) -> List[dict]:
    """换行分隔的纯文本 → 飞书多行文本格式。"""
    if not text:
        return [{"type": "text", "text": ""}]
    return [{"type": "text", "text": line} for line in text.split("\n")]


# ── 记录字段提取辅助 ───────────────────────────────────

def extract_record_fields(record: dict) -> dict:
    """从飞书记录中提取纯字段数据（去掉类型包裹）。"""
    fields = record.get("fields", {})
    result = {}
    for key, value in fields.items():
        # 多行文本字段 → 纯文本
        if isinstance(value, list):
            # 检查是否是富文本格式
            if value and isinstance(value[0], dict) and value[0].get("type") == "text":
                result[key] = multiline_to_text(value)
            else:
                result[key] = value
        else:
            result[key] = value
    result["record_id"] = record.get("record_id")
    return result
