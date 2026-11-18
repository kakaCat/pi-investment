"""WatchEngineV2 定时任务装配（REQ-261022235419-2299）

2026-10-23 用户裁定：**V2 改为定时任务驱动，不再起常驻循环**。
本文件是宿主层（adapters/inbound）与 qs_watch 之间的唯一接线点：

    1. `build_engine_v2()`    组装判定引擎（注入规则仓储 / 行情服务 / 名称解析 /
                              飞书直发通道 / 10 次循环计数存储）；
    2. `register_watch_v2_jobs()` 把 5 个 Job 注册进 JobRegistry；
       调度行由迁移播种（20261026 起三个扫描档均按连续竞价时段拆分调度）。

开关：`WATCH_V2_ENABLED` 未设/false → 不注册任何 Job（V1 行为完全不变）。
"""
import os

import structlog

logger = structlog.get_logger(__name__)

#: V2 主流程开关（影子期默认关闭；切主时置 true）
_ENV_V2_ENABLED = 'WATCH_V2_ENABLED'

_V2_ENGINE = None


def v2_enabled() -> bool:
    """V2 是否启用（默认 false = 不注册任务，V1 行为不变）。"""
    return str(os.environ.get(_ENV_V2_ENABLED, '')).strip().lower() in ('1', 'true', 'yes', 'on')


def account_agent_map_from_env() -> dict:
    """账户 → agent 映射（WATCH_ACCOUNT_AGENT_MAP，JSON；坏值按空表处理不阻断启动）。"""
    raw = (os.environ.get('WATCH_ACCOUNT_AGENT_MAP') or '').strip()
    if not raw:
        return {}
    try:
        import json
        parsed = json.loads(raw)
        return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001 - 映射坏掉只影响路由兜底，不该阻断盯盘
        logger.error('WATCH_ACCOUNT_AGENT_MAP 解析失败，按空表处理', raw=raw[:200])
        return {}


def build_feishu_sender(webhook_url: str = ''):
    """优先直发盯盘群 webhook；未配置时复用既有通知门面的盯盘群路由。"""
    from qs_watch.application.services.watch_engine.v2 import notify_feishu

    if webhook_url:
        return lambda title, body: notify_feishu.send_rendered(webhook_url, title, body)

    from qs_notification.application import get_notification_facade
    return notify_feishu.make_facade_sender(get_notification_facade())


def build_engine_v2():
    """组装 V2 判定引擎并恢复两段式伏击观察状态。"""
    from qs_watch.application.services.watch_engine.core.factory import (
        RealtimeQuoteServiceV2,
        get_market_watch_service,
        sim_position_repo,
        watch_rule_repo,
    )
    from qs_watch.application.services.watch_engine.v2.data_providers import (
        make_avg_volume_provider,
        make_fund_flow_provider,
        make_kline_closes_provider,
    )
    from qs_watch.application.services.watch_engine.core.watch_loop_wiring import (
        build_runtime_store,
        watch_runtime_persist_enabled,
    )
    from qs_watch.application.services.watch_engine.v2.engine import create_engine_v2
    from qs_watch.application.services.watch_engine.v2.evaluation_context import (
        EvaluationContextFactory,
    )
    from qs_watch.application.services.watch_engine.v2.rule_evaluator import RuleEvaluator
    from qs_watch.application.services.watch_engine.v2.staged_break_manager import (
        StagedBreakManager,
    )

    # 名称解析（规则表不存名称，渲染标题用）：黑盒复用既有 StockORMRepository
    def _name_resolver(symbols):
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        rows = StockORMRepository().get_by_symbols_batch(list(symbols)) or {}
        return {sym: (info or {}).get('name') for sym, info in rows.items()
                if (info or {}).get('name')}

    _feishu_sender = build_feishu_sender(
        os.environ.get('WATCH_FEISHU_WEBHOOK', '').strip())

    # agent 通道（第 1 次触发唤醒 agent 判断）：qs_agenthub 的既有唤醒服务。
    # 超时用短档（默认 10s）：定时任务线程不能被 agent 侧 300s 超时拖住，否则
    # 30 秒任务的下一拍会被 misfire_grace 跳过（N 拍内丢判定）。
    def _agent_sender(agent, account, prompt, context):
        from qs_agenthub.application.services.agent_notification_service import (
            AgentNotificationService,
        )
        svc = AgentNotificationService(
            timeout=int(os.environ.get('WATCH_AGENT_TIMEOUT', '10')))
        return bool(svc.notify_agent(
            'watch_trigger',
            {'agent': agent, 'account': account, 'prompt': prompt, **context},
            target=agent,
        ))

    def _position_reader(account, symbol):
        if not account or not symbol:
            return None
        return sim_position_repo().get_position(account, symbol)

    runtime_store = None
    if watch_runtime_persist_enabled():
        try:
            runtime_store = build_runtime_store()
        except Exception as exc:  # noqa: BLE001 - 持久化不可用时保留内存状态机
            logger.error('V2 staged 运行态仓储装配失败，降级为内存', error=str(exc))
    avg_volume_evaluator = RuleEvaluator(avg_volume_provider=make_avg_volume_provider())
    evaluation_context = EvaluationContextFactory(
        avg_volume_evaluator=avg_volume_evaluator,
        kline_closes_provider=make_kline_closes_provider(),
        fund_flow_provider=make_fund_flow_provider(),
    )

    return create_engine_v2(
        rule_repo=watch_rule_repo(),
        quote_service=RealtimeQuoteServiceV2(),
        name_resolver=_name_resolver,
        position_reader=_position_reader,
        evaluation_context=evaluation_context,
        staged_manager=StagedBreakManager(store=runtime_store),
        market_watch_service=get_market_watch_service(),
        feishu_sender=_feishu_sender,
        agent_sender=_agent_sender,
        account_agent_map=account_agent_map_from_env(),
        cycle_store=watch_rule_repo(),
    )


def tier_column_ready(rule_repo) -> bool:
    """迁移预检：watch_tier 列是否已落库。

    判据：有 active 规则时，至少一条能读到非 None 的 watch_tier。迁移给存量规则
    NOT NULL DEFAULT 30，所以"全部为 None"只能是列不存在（仓储缺列 fail-open 时
    该字段被 load_only 排除、读取返回 None）——此时拒绝注册 V2 任务，
    避免任务按默认档盲跑、档位永远写不进去。
    """
    try:
        rules = list(rule_repo.list_by_state('active') or [])
    except Exception as exc:  # noqa: BLE001 - 读不到就按未就绪处理（宁可不跑）
        logger.error('WatchEngineV2 启动预检失败（读规则异常）', error=str(exc))
        return False
    if not rules:
        return True
    return any(getattr(rule, 'watch_tier', None) is not None for rule in rules)


def register_watch_v2_jobs(rule_repo=None) -> int:
    """注册 5 个 V2 定时任务；返回注册数量（0 = 开关关闭/预付检未过/未注册）。"""
    global _V2_ENGINE
    if not v2_enabled():
        logger.info('WatchEngineV2 未启用（WATCH_V2_ENABLED=false，V1 行为不变）')
        return 0

    from qs_ops.application.jobs.job_registry import job_registry
    from qs_watch.application.services.watch_engine.v2.scheduled import build_watch_v2_jobs

    if rule_repo is None:
        from qs_watch.application.services.watch_engine.core.factory import watch_rule_repo
        rule_repo = watch_rule_repo()

    if not tier_column_ready(rule_repo):
        logger.error(
            'watch_tier 列未就绪（迁移 20261023_watch_rules_tier 未落库），'
            '拒绝注册 WatchEngineV2 任务：V1 若同时停用将无人盯盘，'
            '请先跑迁移再启用 V2')
        return 0

    engine = build_engine_v2()
    jobs = build_watch_v2_jobs(engine)
    for job in jobs:
        job_registry.register(job)
    _V2_ENGINE = engine
    logger.info('✅ WatchEngineV2 定时任务已注册', count=len(jobs),
                jobs=[job.name for job in jobs])
    return len(jobs)


def start_watch_engine_v2(skip: bool = False):
    """已废弃：V2 不再起常驻线程（保留函数名只为旧调用方不炸）。"""
    if skip:
        return None
    logger.warning('start_watch_engine_v2 已废弃：V2 已改为定时任务（register_watch_v2_jobs）')
    register_watch_v2_jobs()
    return None


def stop_watch_engine_v2(handle=None) -> None:
    """保存观察状态并回收取数线程池。"""
    global _V2_ENGINE
    engine = handle if handle not in (None, True) else _V2_ENGINE
    if engine is not None:
        engine.stop()
    _V2_ENGINE = None
