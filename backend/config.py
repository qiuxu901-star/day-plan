from __future__ import annotations
"""应用配置管理——从环境变量读取飞书凭证和多维表 ID。"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # 飞书应用
    FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")

    # 多维表
    BITABLE_APP_TOKEN: str = os.getenv("BITABLE_APP_TOKEN", "")
    TABLE_ID_WEEKLY: str = os.getenv("TABLE_ID_WEEKLY", "")
    TABLE_ID_DAILY: str = os.getenv("TABLE_ID_DAILY", "")
    TABLE_ID_TASKS: str = os.getenv("TABLE_ID_TASKS", "")

    # 服务
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

    def validate(self) -> List[str]:
        """校验必要配置，返回缺失项列表。"""
        required = {
            "FEISHU_APP_ID": self.FEISHU_APP_ID,
            "FEISHU_APP_SECRET": self.FEISHU_APP_SECRET,
            "BITABLE_APP_TOKEN": self.BITABLE_APP_TOKEN,
            "TABLE_ID_WEEKLY": self.TABLE_ID_WEEKLY,
            "TABLE_ID_DAILY": self.TABLE_ID_DAILY,
            "TABLE_ID_TASKS": self.TABLE_ID_TASKS,
        }
        return [k for k, v in required.items() if not v]


settings = Settings()
