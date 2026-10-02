"""失败判定与飞书告警（拆分自 daily_jobs_bootstrap.py）

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
from adapters.inbound.fastapi_app.daily_jobs.defs import logger  # noqa: F401

def _send_feishu(text: str) -> bool:
    """飞书告警（失败只记日志，不阻断任务流）

    2026-09-11（w-23c70356）：改为经 NotificationFacade 投递，并与其余系统通知统一为
    卡片样式（首行作标题、其余作正文）。此前直接调旧版 FeishuNotificationService
    .send_text 走裸 webhook：既绕过 DDD 通知域（违反 CLAUDE.md 通知架构铁律），
    也拿不到「Agent OS 优先、飞书降级」策略路由，所以在同一飞书群里与本 Agent 的
    卡片消息观感不一致。urgency：🚨/❌ 开头按 high，其余 normal。
    """
    try:
        from application.notification import get_notification_facade

        title, _, body = text.partition('\n')
        title = title.strip() or '每日任务通知'
        urgency = 'high' if title.startswith(('🚨', '❌')) else 'normal'
        return bool(get_notification_facade().send_card(
            title=title,
            content=(body.strip() or title),
            urgency=urgency
        ))
    except Exception as e:
        logger.error("freshness/job alert feishu send failed", error=str(e))
        return False


def _job_failure_watch(engine) -> List[Dict[str, Any]]:
    """任务失败巡检：过去 3 个自然日（不含今天——今天失败仍在 2h 自动重试冷却期）仍 failed 的活跃任务

    补 K线/因子巡检的盲区：数据恰好未滞后但 job 本身失败（如 chip_distribution 失败但
    K线新鲜、financial_statements 周六失败周一才发现）。只查 JOBS 内活跃任务，
    已退役 job（如 morning_topup）的历史 failed 残留不告警。
    """
    # 惰性导入：registry 依赖各作业模块，模块级导入会成环
    from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
    # 取数收口到仓储（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    # engine 参数保留（签名被 _job_freshness_guard 与既有测试按位置传参）。
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    return JobRunRepository().list_recent_failures([j.job_id for j in JOBS], days=3)


def _summarize_result(result: Any, max_len: int = 300) -> str:
    """任务结果摘要（完成通知用）：提取关键计数，截断防爆消息"""
    if not isinstance(result, dict):
        return ''
    keys = ['symbols_updated', 'updated', 'computed', 'failed_count',
            'symbols_checked', 'status', 'expected', 'kline_coverage', 'kline_stale',
            'kline_oldest_stale', 'factor_latest']
    parts = [f"{k}={result[k]}" for k in keys if k in result]
    # evening_pipeline 等链式任务：深入一层提取子任务摘要
    for sub_key, sub_val in result.items():
        if isinstance(sub_val, dict):
            sub_parts = [f"{k}={sub_val[k]}" for k in ('updated', 'computed', 'status', 'stale')
                         if k in sub_val]
            if sub_parts:
                parts.append(f"{sub_key}[{', '.join(map(str, sub_parts[:4]))}]")
    text = '; '.join(parts)
    return text[:max_len]


