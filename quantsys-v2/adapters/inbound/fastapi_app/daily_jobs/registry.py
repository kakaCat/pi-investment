"""JOBS 注册表（顺序即调度顺序，改动需同步文档）

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
from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.pipeline import _job_chip_distribution, _job_evening_pipeline, _job_evolution_fitness, _job_financial_statements, _job_freshness_guard  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.pools import _job_pool_daily_refresh, _job_pool_weekly_review  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.health import _job_event_calendar_check, _job_watch_rule_health  # noqa: F401

JOBS: List[JobDef] = [
    # 错峰（2026-09-02）：20:30 是 EOD 低峰期，避开全国量化高峰
    # freshness_guard 17:20 早发现滞后，evening_pipeline 20:30 补齐
    # event_calendar_check 16:45 每日（含周末，原 Agent OS cron 语义）
    # watch_rule_health 16:30 周一~五：规则健康检查（RFC 011 Phase 2）
    JobDef('watch_rule_health', dtime(16, 30), (0, 1, 2, 3, 4),
           _job_watch_rule_health, '规则健康检查：自动禁用过期/失效规则，标记长期未触发规则（RFC 011）'),
    JobDef('event_calendar_check', dtime(16, 45), (0, 1, 2, 3, 4, 5, 6),
           _job_event_calendar_check, '事件日历检查：未来2日 pending 高优事件（imp>=2）飞书提醒→标记notified'),
    JobDef('freshness_guard', dtime(17, 20), (0, 1, 2, 3, 4),
           _job_freshness_guard, 'K线/因子新鲜度巡检（滞后>1交易日飞书告警）'),
    JobDef('evening_pipeline', dtime(20, 30), (0, 1, 2, 3, 4),
           _job_evening_pipeline, 'K线分批同步 → 因子全市场计算（支持幂等重复执行）'),
    JobDef('chip_distribution', dtime(21, 10), (0, 1, 2, 3, 4),
           _job_chip_distribution, '筹码分布更新（排在 pipeline 后，用当日新K线）',
           trading_days_only=True,
           webhook_url='https://open.feishu.cn/open-apis/bot/v2/hook/7aa7ebdd-be9e-47f9-be45-ba9c772499c9'),
    JobDef('evolution_fitness', dtime(20, 35), (0, 1, 2, 3, 4),
           _job_evolution_fitness, 'B链账户行为双侧捕获 fitness 续采（RFC 012 P3，8/14 断点恢复；账户行为域，非策略参数进化）',
           trading_days_only=True),
    JobDef('financial_statements', dtime(20, 0), (5,),
           _job_financial_statements, '季度财报更新'),
    # pool_* 2026-09-09 下沉自 Agent OS command 脚本（Agent OS 侧删除前须见 v2 宿主
    # 跑出 success；原 cron：daily 19:05 一~五 / weekly 周日 18:00）
    #
    # ── 交易日门（REQ-261005203907-2b8c · FR-4）：本表共 3 个任务声明 trading_days_only=True ──
    # （chip_distribution / evolution_fitness 见上方错峰段，pool_daily_refresh 见下一行）
    # 它们吃的都是"当日行情数据"，休市日重算的是同一份冻结快照（2026-10-05 实测：
    # pool_daily_refresh 空跑 22.1 秒、pool_change_log 全天 0 行）。
    # · chip_distribution / evolution_fitness / pool_daily_refresh → 休市日整段跳过；
    # · evening_pipeline **不加**：它的 K 线段是休市日唯一的缺口修复路径，只在其 handler 内
    #   跳过因子段（见 pipeline._job_evening_pipeline）；
    # · watch_rule_health / event_calendar_check / freshness_guard / financial_statements /
    #   pool_weekly_review 一律不加（与当日行情无关或本就排在非交易日）。
    JobDef('pool_daily_refresh', dtime(19, 5), (0, 1, 2, 3, 4),
           _job_pool_daily_refresh, '股票池每日刷新：全部 dynamic 池 refresh 换血 + sync 股票名称（R-012）',
           trading_days_only=True),
    JobDef('pool_weekly_review', dtime(18, 0), (6,),
           _job_pool_weekly_review, '股票池周日盘点：dynamic 刷新 + 空池/测试临命名线索清单（R-012）'),
]

