"""业务任务目录（不再直接驱动调度）

2026-10-01（REQ-261001145152-3982 t-686185）：由 daily_jobs_bootstrap.py 机械拆分而来
（原文件 1147 行）。函数体与签名**逐字未改**；原模块保留为转发壳，既有导入路径不受影响。

2026-10-27：11 个 JobDef 的 cron 已迁到 quant.scheduler_tasks，由 APScheduler +
JobRegistry 驱动。这里的 run_at/weekdays 只作为迁移与兼容展示的目录信息；
应用启动不再调用 DailyJobs 宿主线程。
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
from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.pipeline import _job_chip_distribution, _job_evening_pipeline, _job_evolution_fitness, _job_financial_statements, _job_freshness_guard  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.pools import _job_pool_daily_refresh, _job_pool_weekly_review  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.health import (  # noqa: F401
    _job_event_calendar_check, _job_invalid_escalation, _job_watch_rule_health)
from adapters.inbound.fastapi_app.daily_jobs.v2_jobs import _job_v2_daily_cycle_reset  # noqa: F401

JOBS: List[JobDef] = [
    # 错峰（2026-09-02）：20:30 是 EOD 低峰期，避开全国量化高峰
    # freshness_guard 17:20 早发现滞后，evening_pipeline 20:30 补齐
    # event_calendar_check 16:45 每日（含周末，原 Agent OS cron 语义）
    # watch_rule_health 16:30 周一~五：规则健康检查（RFC 011 Phase 2）
    JobDef('watch_rule_health', dtime(16, 30), (0, 1, 2, 3, 4),
           _job_watch_rule_health, '规则健康检查：过期/预案过期标 invalid 进裁决，价格偏离移交实时失效判定（agent 阈值），标记长期未触发（RFC 011）'),
    # invalid_rule_escalation 17:00 周一~五：失效规则滞留升级（2026-10-22 用户裁定）——
    # invalid 该 agent 裁决却超 24h 未处理 → 发盯盘群请用户推进，标记 invalid_escalated_at 只提醒一次
    # v2_daily_cycle_reset 16:35 周一~五（REQ-261022235419-2299 t9 / D-18）：
    # V2 触发路由的跨天重置 —— **仅活跃规则** cycle_count=0、process_state='pending'
    # （活跃 = rule_state='active' 且启用且未过期，与引擎判定集合同源；非活跃规则
    # 不参与判定、不需要重置——2026-10-23 用户裁定），次日从「循环第 1 次（agent 先处理）」
    # 重新开始。与 watch_rule_health 分离（只管计数/状态）。
    JobDef('v2_daily_cycle_reset', dtime(16, 35), (0, 1, 2, 3, 4),
           _job_v2_daily_cycle_reset, 'V2 每日循环重置：活跃规则循环计数与处理状态清零（次日首发 agent）'),
    JobDef('invalid_rule_escalation', dtime(17, 0), (0, 1, 2, 3, 4),
           _job_invalid_escalation, '失效规则滞留升级：agent 未裁决超24h → 发用户推进'),
    JobDef('event_calendar_check', dtime(16, 45), (0, 1, 2, 3, 4, 5, 6),
           _job_event_calendar_check, '事件日历检查：未来2日 pending 高优事件（imp>=2）飞书提醒→标记notified'),
    JobDef('freshness_guard', dtime(17, 20), (0, 1, 2, 3, 4),
           _job_freshness_guard, 'K线/因子新鲜度巡检（滞后>1交易日飞书告警）'),
    JobDef('evening_pipeline', dtime(20, 30), (0, 1, 2, 3, 4),
           _job_evening_pipeline, 'K线分批同步 → 因子全市场计算（支持幂等重复执行）'),
    JobDef('chip_distribution', dtime(21, 10), (0, 1, 2, 3, 4),
           _job_chip_distribution, '筹码分布更新（排在 pipeline 后，用当日新K线）'),
    JobDef('evolution_fitness', dtime(20, 35), (0, 1, 2, 3, 4),
           _job_evolution_fitness, 'B链账户行为双侧捕获 fitness 续采（RFC 012 P3，8/14 断点恢复；账户行为域，非策略参数进化）'),
    JobDef('financial_statements', dtime(20, 0), (5,),
           _job_financial_statements, '季度财报更新'),
    # pool_* 2026-09-09 下沉自 Agent OS command 脚本（Agent OS 侧删除前须见 v2 宿主
    # 跑出 success；原 cron：daily 19:05 一~五 / weekly 周日 18:00）
    JobDef('pool_daily_refresh', dtime(19, 5), (0, 1, 2, 3, 4),
           _job_pool_daily_refresh, '股票池每日刷新：全部 dynamic 池 refresh 换血 + sync 股票名称（R-012）'),
    JobDef('pool_weekly_review', dtime(18, 0), (6,),
           _job_pool_weekly_review, '股票池周日盘点：dynamic 刷新 + 空池/测试临命名线索清单（R-012）'),
]

