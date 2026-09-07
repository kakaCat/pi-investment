"""
Job 协议 - 所有定时任务的统一接口

每个任务必须实现 Job 接口，返回 JobResult。
调度层通过 JobRegistry 按 name 查找并执行任务。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class JobResult:
    """所有任务的统一输出契约"""
    success: bool
    action: str                              # 任务名
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def ok(cls, action: str, message: str = "", **details) -> "JobResult":
        """成功结果"""
        return cls(success=True, action=action, message=message, details=details)

    @classmethod
    def fail(cls, action: str, error: str) -> "JobResult":
        """失败结果"""
        return cls(success=False, action=action, error=error)


class Job(ABC):
    """所有定时任务必须实现的接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """任务唯一标识，如 'kline_update'"""

    @property
    def description(self) -> str:
        """任务描述（可选）"""
        return ""

    @property
    def timeout_seconds(self) -> int:
        """任务超时时间（秒），默认 1 小时"""
        return 3600

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> JobResult:
        """执行任务

        Args:
            params: 任务参数（从 webhook metadata 传入）

        Returns:
            JobResult: 统一结果格式
        """
