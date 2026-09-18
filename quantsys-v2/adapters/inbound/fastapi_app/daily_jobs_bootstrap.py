"""每日数据任务进程内宿主（2026-09-02）

背景：Agent OS 调度器中核心数据任务（kline_update / factor_compute_daily /
data_pipeline_daily / chip_distribution_update / data_quality_check）全部禁用，
数据新鲜度靠 agent 例程自觉——实测（2026-09-02）：601857 K线停在 8-27、
8-31 因子只覆盖 10 只、9-01 因子缺失。与 orchestrator/watch 的静默死亡
事故同根：**无宿主 = 会死**。

设计（与 orchestrator_bootstrap 同模式）：
- 唯一宿主 = FastAPI 5001 进程（lifespan 启动本模块守护线程）
- DB 落库 quant.inprocess_job_runs（job_id + run_date 唯一）：
  每日幂等（重启不重复跑）、漏跑补跑（当天已过点但未成功 → 立即补）、
  失败留痕（status=failed + error）
- 任务失败 → 飞书告警（不再静默死亡）
- freshness_guard 兜底：K线/因子滞后 >1 交易日 → 飞书告警
  （即使 pipeline 本身挂了也能被发现）

任务表（调整请同步文档 docs/guides/quantsys-v2-capability-assessment.md）：
- evening_pipeline   20:30 周一~五：K线分批同步 → 因子全市场计算（串行链式，支持幂等）
- freshness_guard    17:20 周一~五：新鲜度巡检（兜底告警）
- chip_distribution  21:10 周一~五：筹码分布更新
- financial_statements 周六 20:00：季度财报更新
- evolution_fitness 20:35 周一~五：账户行为双侧捕获 fitness 续采（RFC 012 P3，8/14 断点恢复；对象=账户行为，与策略参数进化分域）
- event_calendar_check 16:45 每天：事件日历检查（未来2日 pending imp>=2 飞书提醒→notified）
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

# ── 任务定义 ─────────────────────────────────────────────────


@dataclass
class JobDef:
    job_id: str
    run_at: dtime
    weekdays: tuple          # 0=周一 ... 6=周日
    handler: Callable[[], Dict[str, Any]]
    description: str


def _probe_kline_sources() -> bool:
    """K线源探活（2026-09-02 WAF 封禁教训）：全市场同步前先探测一只权重股。

    源不可用时快速失败——避免 5500 只 × 3 源 fallback 白跑几小时，
    且对已封禁 IP 的反复重试会加重封禁。
    """
    try:
        from adapters.outbound.datasources.manager import DataProviderManager
        m = DataProviderManager()
        r = m.get_klines('601857', 'daily', '2026-08-25', '2026-09-02')
        ok = bool(isinstance(r, dict) and r.get('success') and r.get('data'))
        if not ok:
            logger.warning("kline_source_probe_failed",
                           error=str(r.get('error') if isinstance(r, dict) else r)[:120])
        return ok
    except Exception as e:
        logger.warning("kline_source_probe_failed", error=str(e)[:120])
        return False


KLINE_COVERAGE_FRESH_THRESHOLD = 0.98


def _kline_coverage(engine, expected: str) -> Dict[str, Any]:
    """按标的统计 K 线覆盖度（2026-09-10 修复）。

    原判定用全局 `max(trade_date) FROM daily_klines`：只要有一只票有当日数据
    就认定"全市场新鲜"→ evening_pipeline 直接跳过同步。实际 2026-09-10 时
    5150/5542 只（93%）停在 09-02，缺口被固化近 8 个交易日无人发现。
    改为按标的覆盖度（已覆盖标的数 / 活跃标的数）+ 最陈旧标的日期。
    """
    # 取数收口到仓储（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    # 原先这里是一段 f-string 内联 SQL（universe 子查询被拼了两次 + 一次 LEFT JOIN 聚合），
    # 属 inbound 层裸 SQL。现由 KlineRepository.get_kline_coverage 承担。
    #
    # engine 参数**保留**：签名被 tests/test_freshness_guard.py 直接 patch
    # （monkeypatch _kline_coverage 为 lambda _engine, _expected），改签名会让守卫测试失效。
    # 迁移后本函数不再使用它（仓储自己取 session）。
    from adapters.outbound.repositories.kline_repository import KlineORMRepository
    return KlineORMRepository().get_kline_coverage(expected)


def _job_evening_pipeline() -> Dict[str, Any]:
    """K线分批同步 → 因子全市场计算（链式：因子依赖当日K线）

    2026-09-02 优化：
    - 全市场同步改为分批策略（P0+P1 必同步 + 按陈旧度补充 500 只，约 800 只/天）
    - 支持幂等重复执行：数据已新鲜时跳过同步，避免重复请求
    - 合并了原 morning_topup 功能，可在任何时间安全执行
    """
    results: Dict[str, Any] = {}

    # 新鲜度检查：数据已新鲜则跳过同步（幂等保护）
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text

    expected = _last_trading_day(datetime.now())
    engine = get_engine()
    cov = _kline_coverage(engine, expected)

    if cov['total'] and cov['coverage'] >= KLINE_COVERAGE_FRESH_THRESHOLD:
        logger.info(
            f"K线已新鲜（覆盖 {cov['covered']}/{cov['total']}="
            f"{cov['coverage']:.1%} ≥ {KLINE_COVERAGE_FRESH_THRESHOLD:.0%}，"
            f"基准日 {expected}），跳过同步")
        results['kline_sync'] = {
            'status': 'skipped',
            'reason': (f"K线覆盖 {cov['covered']}/{cov['total']}"
                       f"（{cov['coverage']:.1%}）≥ 基准日 {expected}"),
            'coverage': cov,
        }
    else:
        # 先探活：源挂/被封时快速失败
        if not _probe_kline_sources():
            raise RuntimeError('K线数据源探活失败（疑似故障或 WAF 封禁），本次 pass 放弃，下个窗口重试')

        # 缺口规模决定批大小与回溯天数（2026-09-10）：原固定 batch_size=500/days=2
        # 在大缺口下只能回补约 800 只/天，5150 只缺口要一周以上；按实测缺口动态放大。
        batch_size = min(6000, max(500, cov['stale']))
        gap_days = 2
        if cov['oldest_stale']:
            try:
                gap_days = (datetime.strptime(expected, '%Y-%m-%d').date()
                            - datetime.strptime(cov['oldest_stale'], '%Y-%m-%d').date()).days + 5
            except ValueError:
                gap_days = 2
            gap_days = max(2, min(gap_days, 60))
        logger.info(
            f"K线覆盖不足（{cov['covered']}/{cov['total']}={cov['coverage']:.1%}，"
            f"最陈旧={cov['oldest_stale']}，基准日={expected}）→ "
            f"分批同步 days={gap_days} batch_size={batch_size}")
        from infrastructure.jobs.kline_update_job import update_gem_klines
        results['kline_sync'] = update_gem_klines(
            scope='batch', days=gap_days, batch_size=batch_size)
        results['kline_sync']['coverage_before'] = cov

    # 因子计算
    from application.services.scheduler_tasks import handle_factor_compute
    logger.info("evening_pipeline: factor_compute start (full market)")
    results['factor_compute'] = handle_factor_compute({'max_symbols': 6000})

    # K线同步失败必须上抛（2026-09-10，w-23c70356）：update_gem_klines 内部
    # except 后返回 {'status':'error'} 而不抛，本函数把结果塞进 results 照常
    # return → 宿主记 success 并发"✅ 每日任务完成"，2026-09-03~09-09 连续 6 个
    # 交易日全市场同步失败却只有 ✅ 通知。放在因子计算之后 raise，保证因子仍按
    # 现有数据算完，只把任务判 failed 并触发失败告警。
    sync = results.get('kline_sync') or {}
    if sync.get('status') == 'error':
        raise RuntimeError(f"K线同步失败：{str(sync.get('error'))[:300]}")

    return results


def _job_chip_distribution() -> Dict[str, Any]:
    from infrastructure.jobs.chip_distribution_update_job import execute
    return execute()


def _job_financial_statements() -> Dict[str, Any]:
    from infrastructure.jobs.financial_statement_update_job import execute
    return execute()


def _job_evolution_fitness() -> Dict[str, Any]:
    """B 链账户行为 fitness 盘后续采（RFC 012 P3，2026-09-05，恢复 8/14 断点）

    EvolutionFitnessService.compute_all_accounts 对全部 active 模拟账户计算
    滚动 20 交易日双侧捕获 fitness 并 upsert（幂等：同 (account, window_end,
    window_days) 覆盖，可安全重复）。对象是**账户行为**（agent_virtual 等），
    与策略参数进化（evolution_strategy_runs，RFC 012 P1）分域——数据供
    "行为进化"语义独立持续，绝不冒充策略排名（RFC 012 §0/§10 边界）。
    """
    # fitness_repo 显式注入：service 默认路径从 domain.ports.repository_ports_extended
    # import EvolutionFitnessORMRepository 是 baseline 缺陷（该类已迁 adapters/outbound/
    # repositories/evolution_fitness_repository.py，ports 只留 IEvolutionFitnessRepository
    # 接口，import 必炸）。service 文件属并行会话 in-flight，不改其源码，注入正确 ORM 仓储绕开。
    from adapters.outbound.repositories.evolution_fitness_repository import (
        EvolutionFitnessORMRepository,
    )
    from application.services.evolution.evolution_fitness_service import (
        EvolutionFitnessService,
    )
    svc = EvolutionFitnessService(fitness_repo=EvolutionFitnessORMRepository())
    summary = svc.compute_all_accounts()
    # 异常（bench 源挂/DB 故障）会向上抛 → 宿主记 failed + 飞书告警；
    # data_gap 账户（无快照/样本不足）由算法返回 status 落库留痕，不算失败。
    return {'detail': summary, 'note': '账户行为 fitness（非策略参数进化）'}


def _last_trading_day(ref: datetime) -> str:
    """最近一个应为交易日的日期（周末排除法；节假日由告警人工复核）"""
    d = ref.date()
    # 收盘前（15:30 前）看前一工作日；收盘后看今天
    if ref.time() < dtime(15, 30) or d.weekday() >= 5:
        d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def _job_failure_watch(engine) -> List[Dict[str, Any]]:
    """任务失败巡检：过去 3 个自然日（不含今天——今天失败仍在 2h 自动重试冷却期）仍 failed 的活跃任务

    补 K线/因子巡检的盲区：数据恰好未滞后但 job 本身失败（如 chip_distribution 失败但
    K线新鲜、financial_statements 周六失败周一才发现）。只查 JOBS 内活跃任务，
    已退役 job（如 morning_topup）的历史 failed 残留不告警。
    """
    # 取数收口到仓储（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    # engine 参数保留（签名被 _job_freshness_guard 与既有测试按位置传参）。
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    return JobRunRepository().list_recent_failures([j.job_id for j in JOBS], days=3)


def _job_freshness_guard() -> Dict[str, Any]:
    """新鲜度巡检：K线/因子滞后于最近交易日 + 任务失败残留 → 飞书告警"""
    from infrastructure.persistence.database.engine import get_engine

    # 基准日=前一交易日（2026-09-10，w-23c70356）：本巡检 17:20 跑，而当天 EOD 要到
    # 20:30 的 evening_pipeline 才落库 —— 原用"当天"当基准，结构上每个交易日都必然判
    # stale（09-04~09-09 连续 5 天误报），告警因长期噪声被忽略。观测对象是"上一交易日的
    # EOD 是否到位"，即滞后>1 个交易日，故基准取前一交易日。
    expected = _last_trading_day(datetime.now() - timedelta(days=1))
    engine = get_engine()
    # 因子最新日期收口到仓储（2026-09-14，REQ-24e15d B4-c4）：
    # 原先这里是 conn.execute(text("SELECT max(factor_date) FROM quant.factor_values"))。
    # 注意口径**保持全表 MAX**（不是全市场覆盖度）—— 迁移不顺手改判定。
    from adapters.outbound.repositories.factor_repository import FactorORMRepository
    factor_latest = FactorORMRepository().get_max_factor_date()

    # 按标的覆盖度巡检（2026-09-10 修复）：原用全局 max(trade_date)，一只票新鲜
    # 就判定全市场新鲜 → 93% 标的缺 8 个交易日的缺口 8 天无人告警。
    cov = _kline_coverage(engine, expected)

    stale: List[str] = []
    if cov['total'] and cov['coverage'] < KLINE_COVERAGE_FRESH_THRESHOLD:
        stale.append(
            f"daily_klines 覆盖 {cov['covered']}/{cov['total']}"
            f"（{cov['coverage']:.1%} < {KLINE_COVERAGE_FRESH_THRESHOLD:.0%}，"
            f"基准日 {expected}），缺 {cov['stale']} 只，最陈旧={cov['oldest_stale']}")
    if not factor_latest or str(factor_latest) < expected:
        stale.append(f"factor_values 最新={factor_latest}（期望≥{expected}）")

    # 任务失败巡检（独立于数据滞后——chip/financial_statements 等失败但数据新鲜时仍需告警）
    failed_jobs = _job_failure_watch(engine)

    if stale:
        msg = ("🚨 数据新鲜度告警\n" + "\n".join(f"- {s}" for s in stale) +
               "\n请检查 evening_pipeline 运行状态（/api/jobs/inprocess/status）")
        if failed_jobs:
            msg += ("\n\n⚠️ 任务失败残留（数据滞后或由这些 job 失败引起）：\n"
                    + "\n".join(f"- {f['job_id']} @ {f['run_date']}"
                                 + (f"：{f['error']}" if f['error'] else "") for f in failed_jobs)
                    + "\n框架 2h 自动重试仍失败，请人工排查")
        _send_feishu(msg)
        out = {'status': 'stale', 'stale': stale, 'expected': expected,
               'alert_sent': True}
        if failed_jobs:
            out['failed_jobs'] = failed_jobs
        return out

    if failed_jobs:
        lines = [f"- {f['job_id']} @ {f['run_date']}"
                 + (f"：{f['error']}" if f['error'] else "") for f in failed_jobs]
        _send_feishu("🚨 v2 定时任务失败残留\n" + "\n".join(lines) +
                     "\n框架 2h 自动重试仍失败，请人工排查（/api/jobs/inprocess/status）")
        # 2026-09-11（w-f4aa1f6a）：原写 str(kline_latest) —— 该变量自 2026-09-10 改成
        # 按标的覆盖度巡检后已不存在，导致"数据新鲜"这条分支必抛
        # NameError: name 'kline_latest' is not defined（滞后分支反而正常，故长期未被发现）。
        # 现改报覆盖度事实，信息量更大且与巡检口径一致。
        return {'status': 'fresh_but_job_failed', 'expected': expected,
                'kline_coverage': f"{cov['covered']}/{cov['total']}",
                'kline_stale': cov['stale'], 'kline_oldest_stale': cov['oldest_stale'],
                'factor_latest': str(factor_latest),
                'failed_jobs': failed_jobs, 'alert_sent': True}

    return {'status': 'fresh', 'expected': expected,
            'kline_coverage': f"{cov['covered']}/{cov['total']}",
            'kline_stale': cov['stale'], 'kline_oldest_stale': cov['oldest_stale'],
            'factor_latest': str(factor_latest)}


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


# ── 规则健康检查（RFC 011 Phase 2）───────────────────────────────────────────

def _job_watch_rule_health() -> Dict[str, Any]:
    """规则健康检查：每天收盘后评估所有启用规则的健康度
    
    自动禁用：
    - EXPIRED: 已过有效期
    - STALE: 价格偏差 >20%（位置失效）
    - OUTDATED: 预案日期已过期
    
    标记审查（不自动禁用）：
    - INACTIVE: 30天未触发
    
    飞书通知：健康度报告
    """
    import json
    import re
    
    # 取数收口到仓储（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    # 原先整段跑在一个 with engine.begin() as conn 里，用裸 SQL 读 watch_rules、
    # 逐条查 daily_klines 最新收盘、查 watch_triggers 最近触发，并就地 UPDATE 禁用。
    # 现读走三个仓储，写走 WatchRuleRepository.update_fields。
    #
    # 事务语义差异（已确认对结果无影响）：原实现循环结束后统一提交（中途抛异常则全部回滚），
    # 现在每条禁用即时提交（update_fields 内部 commit）。循环内除禁用外没有任何其它写操作；
    # 对"每天收盘后跑一次"的巡检而言，半途失败不该丢掉已经判定的结论，故按新语义保留。
    from adapters.outbound.repositories.watch_rule_repository import (
        WatchRuleRepository, WatchTriggerRepository,
    )
    from adapters.outbound.repositories.kline_repository import KlineORMRepository

    rule_repo = WatchRuleRepository()
    trigger_repo = WatchTriggerRepository()
    kline_repo = KlineORMRepository()

    reports = []
    auto_disabled = []
    marked_inactive = []

    # 与原来的 FROM quant.watch_rules WHERE enabled = true 等价。
    # 注意：**不能用 list_enabled()** —— 那个方法会把已过期规则过滤掉，
    # 而本函数的 EXPIRED 分支正是要吃这些行并把它们禁用。
    for rule in rule_repo.list_rules(enabled=True):
        rule_id, symbol = rule.id, rule.symbol
        context, conditions = rule.context, rule.conditions
        expires_at, created_at = rule.expires_at, rule.created_at
        status = 'HEALTHY'
        reason = '正常'
            
        # 1. 检查有效期
        if expires_at and expires_at < datetime.now():
            status = 'EXPIRED'
            reason = f'已过有效期（{expires_at.strftime("%Y-%m-%d")}）'
        else:
            # 2. 检查价格偏差
            try:
                # 获取当前价格（仓储口径：无 K 线返回 None，与原 fetchone() 空行为等价）
                current_close = kline_repo.get_latest_close(symbol)
                    
                if current_close is not None and conditions:
                    current_price = float(current_close)
                    conds = json.loads(conditions) if isinstance(conditions, str) else conditions
                        
                    # 提取触发价格
                    trigger_price = None
                    for cond in conds:
                        if isinstance(cond, dict):
                            params = cond.get('params', {})
                            if 'price' in params:
                                trigger_price = float(params['price'])
                                break
                        
                    if trigger_price and trigger_price > 0:
                        deviation = abs(current_price - trigger_price) / trigger_price * 100
                        if deviation > 20:
                            status = 'STALE'
                            reason = f'价格偏差{deviation:.1f}%（当前{current_price} vs 设定{trigger_price}）'
                    
                # 3. 检查预案日期（如果还没被标记为 STALE）
                if status == 'HEALTHY' and context:
                    date_patterns = [
                        r'(\d{1,2})/(\d{1,2})',
                        r'(\d{4})-(\d{2})-(\d{2})',
                    ]
                    for pattern in date_patterns:
                        matches = re.findall(pattern, context)
                        for match in matches:
                            try:
                                if len(match) == 2:
                                    month, day = int(match[0]), int(match[1])
                                    year = datetime.now().year
                                    date_obj = datetime(year, month, day)
                                else:
                                    year, month, day = int(match[0]), int(match[1]), int(match[2])
                                    date_obj = datetime(year, month, day)
                                    
                                days_diff = (datetime.now() - date_obj).days
                                if days_diff > 7:
                                    status = 'OUTDATED'
                                    reason = f'预案日期已过期（{date_obj.strftime("%m/%d")}，已过去{days_diff}天）'
                                    break
                            except (ValueError, IndexError):
                                continue
                        if status == 'OUTDATED':
                            break
                    
                # 4. 检查触发活跃度（如果还没被标记）
                if status == 'HEALTHY':
                    # 无触发行与 MAX 为 NULL 都返回 None，与原 trigger_row[0] if trigger_row else None 一致
                    last_trigger = trigger_repo.get_last_triggered_at(rule_id)
                        
                    if last_trigger:
                        days_since = (datetime.now() - last_trigger).days
                        if days_since > 30:
                            status = 'INACTIVE'
                            reason = f'{days_since}天未触发（上次：{last_trigger.strftime("%Y-%m-%d")}）'
                    elif created_at:
                        days_since = (datetime.now() - created_at).days
                        if days_since > 30:
                            status = 'INACTIVE'
                            reason = f'创建后{days_since}天从未触发'
                
            except Exception as e:
                logger.warning('规则健康检查异常', rule_id=rule_id, error=str(e))
            
        reports.append({
            'rule_id': rule_id,
            'symbol': symbol,
            'status': status,
            'reason': reason,
        })
            
        # 自动处理
        if status in ('EXPIRED', 'STALE', 'OUTDATED'):
            # update_fields 的 updated_at 用 Python datetime.now()（原 SQL 用 NOW()）。
            # 两者都是"当下"，差在进程时钟 vs 库时钟；本巡检不依赖该字段做判定。
            rule_repo.update_fields(rule_id, enabled=False)
            auto_disabled.append({'rule_id': rule_id, 'symbol': symbol, 'reason': reason})
        elif status == 'INACTIVE':
            marked_inactive.append({'rule_id': rule_id, 'symbol': symbol, 'reason': reason})
    
    # 生成飞书通知
    if auto_disabled or marked_inactive:
        lines = [f'🧹 【规则健康检查】{datetime.now().strftime("%Y-%m-%d")}', '']
        
        if auto_disabled:
            lines.append('自动禁用：')
            for d in auto_disabled:
                lines.append(f"- 规则#{d['rule_id']} {d['symbol']}：{d['reason']}")
            lines.append('')
        
        if marked_inactive:
            lines.append('待人工审查：')
            for d in marked_inactive:
                lines.append(f"- 规则#{d['rule_id']} {d['symbol']}：{d['reason']}")
            lines.append('')
        
        # 统计
        healthy_count = len([r for r in reports if r['status'] == 'HEALTHY'])
        lines.append(f'统计：总数 {len(reports)} 条 | 健康 {healthy_count} 条 | 自动禁用 {len(auto_disabled)} 条 | 待审查 {len(marked_inactive)} 条')
        
        _send_feishu('\n'.join(lines))
    
    return {
        'status': 'success',
        'total': len(reports),
        'healthy': len([r for r in reports if r['status'] == 'HEALTHY']),
        'auto_disabled': len(auto_disabled),
        'marked_inactive': len(marked_inactive),
        'details': reports,
    }


# ── 事件日历检查（2026-09-06 下沉自 Agent OS event-calendar-check） ─────────

_EVENT_TYPE_LABELS = {
    'cpi_ppi': '📊 CPI/PPI', 'pmi': '🏭 PMI', 'nbs': '📈 国民经济数据',
    'lpr': '🏦 LPR', 'fomc': '🇺🇸 FOMC 议息', 'us_cpi': '🇺🇸 CPI',
    'nfp': '🇺🇸 非农', 'earnings': '📋 财报披露', 'futures_delivery': '⚙️ 期货交割',
    'policy': '📜 政策事件', 'other': '📌 其他',
}


def _event_md(e) -> str:
    """单条事件的卡片 Markdown"""
    d = e.event_date
    dd = f'{d.month:02d}-{d.day:02d}' if d else '??-??'
    label = _EVENT_TYPE_LABELS.get(e.event_type or 'other', '📌 其他')
    flag = '🚨' if (e.importance or 1) >= 3 else '🔸'
    line = f'{flag} **{dd}** {label}：{e.title}'
    if e.event_time:
        line += f'（{e.event_time.strftime("%H:%M")}）'
    desc = (e.description or '').strip()
    if desc:
        line += f'\n　{desc[:60]}{"…" if len(desc) > 60 else ""}'
    return line


def _job_event_calendar_check() -> Dict[str, Any]:
    """事件日历检查：未来2日 pending 且重要性>=2 的事件 → 飞书提醒 → 标记 notified。

    幂等：只处理 status=='pending'；发送成功即 mark notified（meta 记 notified_by），
    框架失败重试只会补发未成功的——已 notified 的不再命中，事件提醒至多一次。
    无目标事件时返回 no_event（不打扰）。
    """
    from adapters.outbound.repositories.event_calendar_repository import (
        get_event_calendar_repo,
    )
    # 2026-09-11（w-23c70356）：改走 NotificationFacade（原直接 new 旧版
    # FeishuNotificationService，绕过 DDD 通知域）
    from application.notification import get_notification_facade

    events = get_event_calendar_repo().list_upcoming(days_ahead=2)
    target = [e for e in events if e.status == 'pending' and (e.importance or 1) >= 2]
    if not target:
        return {'status': 'no_event', 'pending_in_window': len(events), 'notified': 0}

    high = [e for e in target if e.importance >= 3]
    mid = [e for e in target if e.importance < 3]
    svc = get_notification_facade()
    sent_ids: List[int] = []
    fail: Optional[Exception] = None

    def _send_batch(title: str, urgency: str, items: List[Any]) -> None:
        nonlocal fail
        try:
            ok = svc.send_card(title=title, content='\n'.join(_event_md(e) for e in items),
                               urgency=urgency)
        except Exception as ex:  # noqa: BLE001
            fail = ex
            return
        if not ok:
            fail = RuntimeError('feishu send_card returned False')
            return
        sent_ids.extend(e.id for e in items)

    if high:
        _send_batch('🚨 未来2日高优事件预警', 'high', high)
    if mid and fail is None:
        _send_batch('📌 未来2日事件提醒', 'normal', mid)

    repo = get_event_calendar_repo()
    for eid in sent_ids:
        repo.mark_status(eid, 'notified', meta_patch={
            'notified_at': datetime.now().isoformat(timespec='seconds'),
            'notified_by': 'event_calendar_check',
        })

    if fail is not None:
        raise RuntimeError(f'feishu send failed（重试将只补未 notified 的）: {fail}')
    return {'status': 'notified', 'notified': len(sent_ids),
            'high': len(high), 'mid': len(mid)}


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

# ── 进程外周期任务（REQ-c9f899 t12 §6-项4/5/6/10）────────────────
# 为什么单列一类：JobDef/is_due 的幂等键是 run_date（每天至多一次），1 分钟级的心跳/
# SLA 巡检套不进该模型。新增 IntervalJobDef，由同一宿主线程（daily-jobs）按间隔节流触发
# —— 该线程**独立于 watch-engine 线程**：引擎线程死了，巡检照跑。这正是 architecture §2
# 的要求（WatchSlaJob/WatchHeartbeatJob = 独立定时任务），绝不放回引擎 run_forever
# （否则线程一死巡检也死，等于没有）。
#
# 开关（默认值一律不改）：三个任务统一挂在新闭环总闸 WATCH_TODO_ENABLED（默认 false）下，
# 默认不产生任何新行为；自愈另受 WATCH_SELF_HEAL_ENABLED（默认 false）约束，心跳另受
# WATCH_HEARTBEAT_ENABLED（默认 true）约束。总闸翻转即整体启用。


@dataclass
class IntervalJobDef:
    job_id: str
    handler: Callable[[], Dict[str, Any]]
    interval_sec: float
    description: str
    enabled: Callable[[], bool]


#: 自愈扫描默认周期（秒）。选 10 分钟的理由：R6 要求"反复触发即时抑噪"，
#: 但扫描要聚合窗口触发并可能写规则抑噪态——1 分钟过于频繁（DB 压力无收益），
#: 10 分钟足以把一轮刷屏会话内的重复触发收住，同时把最坏重复量限制在 ~10 分钟。
#: 可用 WATCH_SELF_HEAL_INTERVAL_SEC 覆盖（下限=宿主 tick，避免比循环还密）。
DEFAULT_SELF_HEAL_INTERVAL_SEC = 600


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _self_heal_interval_sec() -> float:
    try:
        value = float(os.getenv('WATCH_SELF_HEAL_INTERVAL_SEC',
                                str(DEFAULT_SELF_HEAL_INTERVAL_SEC)))
    except (TypeError, ValueError):
        value = float(DEFAULT_SELF_HEAL_INTERVAL_SEC)
    return max(float(_TICK_SEC), value)


def _watch_loop_master_enabled() -> bool:
    """新闭环总闸（WATCH_TODO_ENABLED，默认 false）= SLA 巡检 + 心跳巡检的注册条件。"""
    return _env_flag('WATCH_TODO_ENABLED', False)


def _watch_heartbeat_job_enabled() -> bool:
    return _watch_loop_master_enabled() and _env_flag('WATCH_HEARTBEAT_ENABLED', True)


def _watch_self_heal_job_enabled() -> bool:
    return _watch_loop_master_enabled() and _env_flag('WATCH_SELF_HEAL_ENABLED', False)


def _job_watch_heartbeat() -> Dict[str, Any]:
    """引擎心跳 / 影子超期巡检（真实通知通道=NotificationFacade，t12 §6-项10）"""
    from adapters.inbound.fastapi_app.watch_heartbeat_job import run_heartbeat_check
    from adapters.outbound.repositories.watch_runtime_state_repository import (
        WatchRuntimeStateRepository,
    )
    from application.services.watch_engine.watch_channels import send_watch_alert
    return run_heartbeat_check(store=WatchRuntimeStateRepository(), sender=send_watch_alert)


def _job_watch_sla() -> Dict[str, Any]:
    """待办到期巡检（唯一收敛权威，architecture §4）"""
    from application.services.watch_engine.watch_loop_wiring import build_sla_job
    return build_sla_job().run_once()


def _job_watch_self_heal() -> Dict[str, Any]:
    """规则自愈扫描（反复触发 → 抑噪 + 修规则待办，R6）"""
    from application.services.watch_engine.watch_loop_wiring import build_self_heal_service
    return build_self_heal_service().scan()


def _build_interval_jobs() -> List[IntervalJobDef]:
    return [
        IntervalJobDef('watch_heartbeat_patrol', _job_watch_heartbeat, float(_TICK_SEC),
                       '盯盘引擎心跳/影子超期巡检（进程外，1 分钟）',
                       _watch_heartbeat_job_enabled),
        IntervalJobDef('watch_sla_patrol', _job_watch_sla, float(_TICK_SEC),
                       '盯盘待办到期巡检（唯一收敛权威，1 分钟）',
                       _watch_loop_master_enabled),
        IntervalJobDef('watch_self_heal_scan', _job_watch_self_heal, _self_heal_interval_sec(),
                       '盯盘规则自愈扫描（抑噪 + 修规则待办）',
                       _watch_self_heal_job_enabled),
    ]


def interval_due(job: IntervalJobDef, now_monotonic: float,
                 last_run_monotonic: Optional[float], running: bool) -> bool:
    """周期任务到期判定（纯函数，可单测）：开关开 + 不在跑 + 距上次 ≥ interval。"""
    if not job.enabled():
        return False
    if running:
        return False
    if last_run_monotonic is None:
        return True
    return (now_monotonic - last_run_monotonic) >= job.interval_sec


def _run_interval_job(job: IntervalJobDef) -> None:
    try:
        result = job.handler()
        logger.info('interval_job_done', job=job.job_id, summary=_summarize_result(result))
    except Exception as e:  # noqa: BLE001 - 单任务失败不许打挂宿主循环
        logger.error('interval_job_failed', job=job.job_id, error=str(e))


def _dispatch_interval_jobs(now_monotonic: float, last: Dict[str, float],
                            running: set) -> None:
    """派发到期周期任务（每次宿主唤醒调用一次；线程内执行，不阻塞调度循环）"""
    for job in _build_interval_jobs():
        if not interval_due(job, now_monotonic, last.get(job.job_id),
                            job.job_id in running):
            continue
        last[job.job_id] = now_monotonic
        running.add(job.job_id)

        def _runner(_job=job):
            try:
                _run_interval_job(_job)
            finally:
                running.discard(_job.job_id)

        threading.Thread(target=_runner, name=f'interval-{job.job_id}',
                         daemon=True).start()


# ── 运行状态表（幂等核心） ─────────────────────────────────────

# 建表口径已收口到 ORM 模型（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
# 原先这里内联了一份手写 _DDL，而 infrastructure/persistence/orm/models/job_run.py
# 里还有一份 InProcessJobRun 模型 —— 同一张表两处定义，改一处不改另一处就会漂。
# 现只保留模型作为唯一真源（与 application/services/signal_test_log.py 在 B3-b
# 删掉自身 _ensure_table 的做法一致）。
#
# 注：模型里 started_at 显式声明了 server_default=now()，与原 _DDL 的
# DEFAULT now() 对齐 —— 否则 checkfirst 建出来的表会少这个默认值。


def _ensure_table() -> None:
    from infrastructure.persistence.database.engine import get_engine
    from infrastructure.persistence.orm.models import InProcessJobRun

    InProcessJobRun.__table__.create(bind=get_engine(), checkfirst=True)


def _get_run(job_id: str, run_date: str) -> Optional[Dict[str, Any]]:
    """取某任务某日的运行态（仓储化，2026-09-14，REQ-24e15d B4-c4）。"""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    return JobRunRepository().get_run(job_id, run_date)


def _mark_running(job_id: str, run_date: str) -> None:
    """置 running（UPSERT）。仓储化，2026-09-14，REQ-24e15d B4-c4。"""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    JobRunRepository().mark_running(job_id, run_date)


def _mark_done(job_id: str, run_date: str, status: str,
               result: Optional[Dict] = None, error: Optional[str] = None) -> None:
    """写终态（仓储化，2026-09-14，REQ-24e15d B4-c4）。

    json.dumps(..., default=str) 这个兜底已下沉到仓储里（见 JobRunRepository.mark_done），
    调用方不再自己序列化 —— 否则两处序列化口径会漂。
    """
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    JobRunRepository().mark_done(job_id, run_date, status, result=result, error=error)


# ── 调度判定（纯函数，可单测） ──────────────────────────────────

def is_due(job: JobDef, now: datetime, last_run: Optional[Dict[str, Any]]) -> bool:
    """任务当前是否应运行

    规则：今天是对应工作日 且 已过运行点 且 今天没有 success/running（未僵死）记录。
    漏跑补跑：晚间重启进程时，已过点但未跑的任务会立即补跑。
    """
    if now.weekday() not in job.weekdays:
        return False
    if now.time() < job.run_at:
        return False
    if last_run is None:
        return True
    if last_run['status'] == 'success':
        return False
    if last_run['status'] == 'running':
        # 僵死判定：running 超过阈值视为死亡，允许重跑
        started = last_run.get('started_at')
        if started is not None:
            # 用传入的 now（而非真实当前时间）计算年龄——可测试且语义一致
            now_aware = now.replace(tzinfo=started.tzinfo) if started.tzinfo else now
            age_hours = (now_aware - started).total_seconds() / 3600
            return age_hours > _RUNNING_STALE_HOURS
        return False
    if last_run['status'] == 'failed':
        # 失败冷却 2h 后自动重试（探活门控下失败 pass 秒级结束，重试成本低；
        # 跨自然日由新日期的空记录重新计时，不会无限重试）
        started = last_run.get('started_at')
        if started is not None:
            now_aware = now.replace(tzinfo=started.tzinfo) if started.tzinfo else now
            age_hours = (now_aware - started).total_seconds() / 3600
            return age_hours > _FAILED_RETRY_HOURS
        return False
    return False


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


def _run_job(job: JobDef, run_date: str) -> None:
    """在独立线程执行一个任务（异常隔离 + 落库 + 告警 + 生命周期通知）"""
    from infrastructure.persistence.orm import close_session
    from infrastructure.monitoring.business_metrics import (
        scheduler_job_runs_total,
        scheduler_job_duration_seconds,
    )
    
    t0 = time.time()
    try:
        _mark_running(job.job_id, run_date)
        logger.info("inprocess_job_start", job=job.job_id, date=run_date)
        _send_feishu(f"▶️ 每日任务开始：{job.job_id}\n{job.description}\n时间: {datetime.now().strftime('%H:%M')}")
        result = job.handler()

        # 结果契约（2026-09-13，w-32314d00）：**只看有没有抛异常 = 假成功工厂**。
        # 实证（近 30 天 quant.inprocess_job_runs）：evening_pipeline 09-03/04/07/08/09
        # 五天记 success，结果里却是 {'kline_sync': {'status':'error', 'error':
        # 'column "updated_at" does not exist'}}；financial_statements 09-05 记 success
        # 但结果是 {'success': False}。APScheduler 路径早有 classify_job_result 判内层失败，
        # 宿主这一条漏了 → 现在统一走 find_result_failure（含嵌套下钻），失败即记 failed。
        inner_error = find_result_failure(result)
        if inner_error:
            elapsed = time.time() - t0
            logger.error("inprocess_job_inner_failed", job=job.job_id, date=run_date,
                         error=inner_error)
            scheduler_job_runs_total.labels(job=job.job_id, status='failed').inc()
            scheduler_job_duration_seconds.labels(job=job.job_id, phase='execution').observe(elapsed)
            try:
                _mark_done(job.job_id, run_date, 'failed', result=result, error=inner_error)
            except Exception:
                logger.error("inprocess_job_mark_failed_error", job=job.job_id)
            _send_feishu(
                f"🚨 每日任务失败：{job.job_id}\n{job.description}\n"
                f"（handler 未抛异常但返回失败态）错误: {inner_error[:300]}"
            )
            return

        elapsed = time.time() - t0
        
        _mark_done(job.job_id, run_date, 'success', result=result)
        scheduler_job_runs_total.labels(job=job.job_id, status='success').inc()
        scheduler_job_duration_seconds.labels(job=job.job_id, phase='execution').observe(elapsed)
        
        logger.info("inprocess_job_done", job=job.job_id, date=run_date)
        elapsed_min = elapsed / 60
        summary = _summarize_result(result)
        _send_feishu(
            f"✅ 每日任务完成：{job.job_id}\n{job.description}\n"
            f"耗时: {elapsed_min:.1f} 分钟" + (f"\n{summary}" if summary else '')
        )
    except Exception as e:
        elapsed = time.time() - t0
        logger.error("inprocess_job_failed", job=job.job_id, date=run_date,
                     error=str(e), exc_info=True)
        scheduler_job_runs_total.labels(job=job.job_id, status='failed').inc()
        scheduler_job_duration_seconds.labels(job=job.job_id, phase='execution').observe(elapsed)
        try:
            _mark_done(job.job_id, run_date, 'failed', error=str(e))
        except Exception:
            logger.error("inprocess_job_mark_failed_error", job=job.job_id)
        _send_feishu(f"🚨 每日任务失败：{job.job_id}\n{job.description}\n错误: {str(e)[:300]}")
    finally:
        try:
            close_session()
        except Exception:
            pass


# ── 宿主循环 ─────────────────────────────────────────────────

def catchup_due(job: JobDef, now: datetime, has_recent_failure: bool) -> bool:
    """跨日补跑判定（纯函数，便于单测）。

    2026-09-13（w-32314d00）：is_due 只认"今天是不是它的排班日"——周六任务周六失败后
    要等到下周六才重试（一周空窗）。用户要求"需要自动重跑"，故对**失败过**的任务
    在窗口期内允许跨日补跑一次：非排班日 + 已过该任务当天的执行时刻 + 近 3 天内有 failed。
    """
    if now.weekday() in job.weekdays:
        return False           # 排班日交给 is_due（含 2h 失败重试）
    if now.time() < job.run_at:
        return False           # 未到该任务当天的执行时刻
    return bool(has_recent_failure)


def _recent_failed_run(job_id: str, days: int = _CATCHUP_WINDOW_DAYS) -> Optional[Dict[str, Any]]:
    """近 N 天内最近一条 failed 记录（跨日补跑判定用）。仓储化，2026-09-14，REQ-24e15d B4-c4。"""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    return JobRunRepository().get_recent_failed(job_id, days=days)


def _reap_orphan_runs(now: Optional[datetime] = None) -> int:
    """把上一进程遗留的 running 行判死（启动时调用一次）。

    2026-09-13（w-32314d00）：is_due 只查**当天**的 run 行、_job_failure_watch 只看 failed，
    于是"进程被杀/任务僵死在 running"的行既不会被重跑也不会被告警——永久隐形。
    实证：financial_statements 2026-09-12 23:00 起 running 12h+（正是财报数据超期的那个 job）。
    本函数在宿主启动时把早于宽限期的 running 行标 failed，使其进入失败巡检（看门狗可见 +
    次日 freshness_guard 的失败残留告警），并允许 is_due 按失败冷却重跑。
    """
    # 取数/写入收口到仓储（2026-09-14，REQ-24e15d B4-c4）：
    # 原先在同一个 engine.begin() 里先 SELECT 再条件 UPDATE。现在两步各自走仓储。
    # 事务语义差异：原实现是"查到才更新"且两步同事务；现在 list 与 update 分两次提交。
    # 对判死场景无差异 —— 两次之间的新增 running 行会被下一次启动/巡检看到，
    # 且 UPDATE 自身带同样的 status/started_at 条件（不会误伤新行）。
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    now = now or datetime.now()
    cutoff = now - timedelta(minutes=_ORPHAN_GRACE_MINUTES)
    repo = JobRunRepository()
    rows = repo.list_orphan_runs(cutoff)
    if rows:
        repo.mark_orphans_failed(cutoff)
    if rows:
        # 2026-09-13（w-32314d00，事件 c0e69791）：这里**刻意用 warning 而非 error**——
        # 孤儿 running 是"已被本函数发现并收尾"的既成事实，不是当前进程的失败：
        #   · 事故记录已落在 quant.inprocess_job_runs（status=failed + error 原因），
        #     并可被 _job_failure_watch 巡检（次日 freshness_guard 飞书告警）；
        #   · 用 error 级会在每次实例重启时生成一条需要人工闭环的 error_events 卡片，
        #     把"已经处理好的事"变成待办噪声（实测 11:37 重启即产生 c0e69791）。
        # 一条聚合 warning 带明细，日志里照样看得见，但不再制造待闭环事件。
        logger.warning(
            "inprocess_job_orphans_reaped",
            count=len(rows),
            jobs=[f"{job_id}@{run_date}" for job_id, run_date in rows],
        )
    return len(rows)


def _jobs_loop(stop_event: threading.Event) -> None:
    _ensure_table()
    try:
        _reap_orphan_runs()   # 明细 warning 由 _reap_orphan_runs 内部输出（聚合一条）
    except Exception as e:  # 判死失败不能阻断宿主
        logger.error("inprocess_job_orphan_reap_error", error=str(e))
    interval_last: Dict[str, float] = {}
    interval_running: set = set()
    while not stop_event.is_set():
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        for job in JOBS:
            try:
                last = _get_run(job.job_id, today)
                catchup = False
                if not is_due(job, now, last) and last is None:
                    # 跨日补跑（2026-09-13，w-32314d00）：失败过的任务不必等下一个排班日。
                    # 只在"今天还没有任何记录"时判定，跑完即写今天的行 → 天然每天最多一次。
                    try:
                        recent = _recent_failed_run(job.job_id)
                    except Exception as e:
                        recent = None
                        logger.error("inprocess_job_catchup_query_error", job=job.job_id, error=str(e))
                    catchup = catchup_due(job, now, recent is not None)
                    if catchup:
                        logger.warning("inprocess_job_catchup", job=job.job_id,
                                       description=job.description, run_date=today)
                if is_due(job, now, last) or catchup:
                    threading.Thread(
                        target=_run_job, args=(job, today),
                        name=f"job-{job.job_id}", daemon=True,
                    ).start()
            except Exception as e:
                # 单任务调度异常不能杀死循环
                logger.error("inprocess_job_schedule_error", job=job.job_id, error=str(e))
        # 进程外周期任务（REQ-c9f899 t12）：与每日任务共用宿主线程，但独立于 JobDef 幂等模型
        try:
            _dispatch_interval_jobs(time.monotonic(), interval_last, interval_running)
        except Exception as e:  # noqa: BLE001 - 派发异常不许打挂循环
            logger.error("interval_job_dispatch_error", error=str(e))
        stop_event.wait(_TICK_SEC)


def start_daily_jobs(skip: bool = False) -> Optional[threading.Event]:
    """启动每日任务宿主线程。返回 stop_event（测试/关闭用）。"""
    if skip:
        return None
    stop = threading.Event()
    t = threading.Thread(target=_jobs_loop, args=(stop,),
                         name='daily-jobs', daemon=True)
    t.start()
    logger.info("✅ daily-jobs host thread started", jobs=[j.job_id for j in JOBS])
    return stop


def trigger_job(job_id: str, force: bool = False) -> Dict[str, Any]:
    """手动触发（运维/补跑用）。force=True 忽略当日已有记录。"""
    job = next((j for j in JOBS if j.job_id == job_id), None)
    if not job:
        return {'success': False, 'error': f'未知任务: {job_id}',
                'available': [j.job_id for j in JOBS]}
    today = datetime.now().strftime('%Y-%m-%d')
    last = _get_run(job_id, today)
    if not force and last and last['status'] in ('running', 'success'):
        return {'success': False,
                'error': f"今日已有记录（{last['status']}），force=true 可强制重跑"}
    threading.Thread(target=_run_job, args=(job, today),
                     name=f"job-{job_id}-manual", daemon=True).start()
    return {'success': True, 'message': f'{job_id} 已触发（后台运行）'}


def list_today_runs() -> List[Dict[str, Any]]:
    """今日任务运行状态（巡检/排障用）。仓储化，2026-09-14，REQ-24e15d B4-c4。"""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    _ensure_table()
    ran = JobRunRepository().map_by_date()
    return [
        {'job_id': j.job_id, 'description': j.description,
         'scheduled_at': j.run_at.strftime('%H:%M'),
         **ran.get(j.job_id, {'status': 'not_run', 'started_at': None,
                              'finished_at': None, 'error': None})}
        for j in JOBS
    ]
