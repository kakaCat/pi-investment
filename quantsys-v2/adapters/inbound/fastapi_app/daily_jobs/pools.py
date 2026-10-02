"""股票池刷新作业（拆分自 daily_jobs_bootstrap.py）

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

def _refresh_all_dynamic_pools() -> Dict[str, Any]:
    """刷新全部 dynamic 池（refresh 重算换血 + sync-stock-names），供 daily/weekly 复用。

    2026-09-09 下沉自 Agent OS 脚本任务 stock-pool-daily-refresh.sh：
    原脚本 curl -> 5001 API（GET /api/pools + POST /api/pools/{id}/refresh +
    /sync-stock-names），此处改为进程内直调同一 stock_pool_service 单例，
    语义保持一致。幂等由宿主 run_date 记录保证，重复执行 refresh 重算无害。
    单池失败不整体 raise（与旧脚本逐池容错语义一致），由框架完成通知带出明细。
    """
    from adapters.inbound.fastapi_app.shared import stock_pool_service as _pool_svc
    try:
        pools = _pool_svc.list_pools()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f'list_pools failed: {e}') from e

    dynamic = [p for p in pools if p.get('pool_type') == 'dynamic']
    details = []
    ok = fail = 0
    for p in dynamic:
        pid, name = p.get('id'), p.get('name', '')
        try:
            after = _pool_svc.refresh_pool(pid)
        except Exception as e:  # noqa: BLE001
            fail += 1
            details.append({'pool_id': pid, 'name': name, 'error': str(e)[:200]})
            continue
        members = after.get('symbols') if isinstance(after, dict) else None
        count = len(members) if isinstance(members, list) else None
        synced = False
        if count:
            try:
                _pool_svc.sync_stock_names(pid)
                synced = True
            except Exception:  # noqa: BLE001  sync 失败不阻断 refresh 主流程
                synced = False
        ok += 1
        details.append({'pool_id': pid, 'name': name, 'members': count, 'synced': synced})

    status = 'success'
    if fail:
        status = 'partial'
    if not dynamic:
        status = 'no_dynamic_pool'
    return {'status': status, 'updated': ok, 'failed': fail, 'failed_count': fail,
            'dynamic_pools': len(dynamic), 'details': details}


def _job_pool_daily_refresh() -> Dict[str, Any]:
    """股票池每日刷新（基因组 R-012，工作日 19:05）。

    下沉自 Agent OS 任务 stock-pool-daily-routine（2026-09-05 建，w-8366e526）：
    刷新全部 dynamic 池成员（filter_template 规则驱动换血）+ sync 股票名称。
    量化规则池成员换血属正常，不打扰；summary ok/fail 由框架完成通知带出。
    """
    return _refresh_all_dynamic_pools()


def _job_pool_weekly_review() -> Dict[str, Any]:
    """股票池周日盘点（基因组 R-012 weekly，周日 18:00）。

    下沉自 Agent OS 任务 stock-pool-weekly-review：先刷新全部 dynamic 池（同 daily），
    再产出治理事实清单：总池数/static/dynamic/空池/测试临命名线索。
    决策性清理（僵尸/空/测试池剔除或整池删）不自动做——由 agent 依据事实清单决定
    （R-012：delete 须 reason + decision_audit + memory_write 留痕）。
    """
    refreshed = _refresh_all_dynamic_pools()
    from adapters.inbound.fastapi_app.shared import stock_pool_service as _pool_svc
    try:
        pools = _pool_svc.list_pools()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f'list_pools failed: {e}') from e

    total = len(pools)
    static = [p for p in pools if p.get('pool_type') == 'static']
    dynamic = [p for p in pools if p.get('pool_type') == 'dynamic']
    empty = [p for p in pools if (p.get('symbol_count') or 0) == 0]
    _junk_kw = ['测试', 'test', 'tmp', '垃圾', '僵尸', 'demo', 'scratch']
    suspicious = []
    for p in pools:
        nm = (p.get('name') or '').lower()
        if any(k in nm for k in _junk_kw):
            suspicious.append(p)
    return {**refreshed,
            'total_pools': total, 'static': len(static), 'dynamic': len(dynamic),
            'empty_pools': len(empty), 'suspicious_names': len(suspicious),
            'empty_detail': [e.get('name') for e in empty][:20],
            'suspicious_detail': [e.get('name') for e in suspicious][:20]}


