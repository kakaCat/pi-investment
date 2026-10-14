"""任务定义与共享常量（拆分自 daily_jobs_bootstrap.py）

2026-10-01（REQ-261001145152-3982 t-686185）：由 daily_jobs_bootstrap.py 机械拆分而来
（原文件 1147 行）。函数体与签名**逐字未改**；原模块保留为转发壳，既有导入路径不受影响。
"""
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

# 失败判定口径唯一来源（含嵌套下钻）：与 APScheduler 路径共用，避免两套标准
from infrastructure.scheduler.job_executor import find_result_failure

logger = structlog.get_logger(__name__)

_TICK_SEC = 60

_RUNNING_STALE_HOURS = 3  # running 状态超过 3 小时视为死亡，允许重跑

_FAILED_RETRY_HOURS = 2   # failed 超过 2 小时自动重试一次（探活门控下失败 pass 很便宜）

_ORPHAN_GRACE_MINUTES = 5  # 宿主启动时，早于该时长仍在 running 的行 = 上一进程遗留（判死）

_CATCHUP_WINDOW_DAYS = 3   # 跨日补跑窗口：某任务近 N 天内失败且今天不是它的排班日 → 补跑一次

@dataclass
class JobDef:
    job_id: str
    run_at: dtime
    weekdays: tuple          # 0=周一 ... 6=周日
    handler: Callable[[], Dict[str, Any]]
    description: str
    # REQ-261005203907-2b8c（FR-1）：只在交易日执行（休市日整段跳过，见 daily_jobs/gate.py）。
    # 缺省 False = 排班与行为与改造前**逐字一致**。
    # ⚠️ 必须保持"最后一个字段 + 带默认值"：仓内多处按**位置参数**构造 JobDef
    # （tests/test_daily_jobs_bootstrap.py:15、tests/test_false_success_guard.py:162、
    # tests/test_financial_auto_rerun.py:122），插在中间会让这些调用直接炸。
    trading_days_only: bool = False
    # 2026-10-07：任务级自定义通知 webhook（用于结果分类投递）
    webhook_url: Optional[str] = None


@dataclass
class IntervalJobDef:
    job_id: str
    handler: Callable[[], Dict[str, Any]]
    interval_sec: float
    description: str
    enabled: Callable[[], bool]


