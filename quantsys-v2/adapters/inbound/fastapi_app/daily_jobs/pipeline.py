"""每日数据管道各作业（拆分自 daily_jobs_bootstrap.py）

2026-10-01（REQ-261001145152-3982 t-686185）：由 daily_jobs_bootstrap.py 机械拆分而来
（原文件 1147 行）。函数体与签名**逐字未改**；原模块保留为转发壳，既有导入路径不受影响。
"""
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

# 失败判定口径唯一来源（含嵌套下钻）：与 APScheduler 路径共用，避免两套标准
from infrastructure.scheduler.job_executor import find_result_failure
from adapters.inbound.fastapi_app.daily_jobs.alerting import _job_failure_watch, _send_feishu  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.defs import logger  # noqa: F401
# 交易日门（REQ-261005203907-2b8c · FR-4）：_job_evening_pipeline 的因子段局部跳过用。
# 模块级导入是有意的——用例按"桩打在被调函数所在模块"的纪律 patch `pipeline.is_non_trading_day`。
from adapters.inbound.fastapi_app.daily_jobs.gate import is_non_trading_day  # noqa: F401

KLINE_COVERAGE_FRESH_THRESHOLD = 0.98

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

    # ── 因子段（REQ-261005203907-2b8c · FR-4）：休市日只在"K 线本次无更新"时跳过 ──
    # 为什么不能只看"K 线段是否 skipped"：**交易日**若 K 线已由别的路径同步过（覆盖度新鲜），
    # kline_sync 同样是 skipped，但当日因子还没算 —— 那样写会在正常交易日漏算因子。
    # 故判据是「非交易日 **且** K 线本次无更新」，交易日一律照跑、行为逐字不变。
    # 反过来，休市日若 K 线段**真的修了数据**（success>0），因子段必须照跑（否则留因子空洞）。
    sync = results.get('kline_sync') or {}
    kline_changed = sync.get('status') != 'skipped' and (sync.get('success') or 0) > 0
    if is_non_trading_day() and not kline_changed and sync.get('status') != 'error':
        logger.info(
            f"evening_pipeline: 非交易日（基准日 {expected}）且 K 线本次无更新 → 跳过因子全市场计算")
        results['factor_compute'] = {
            'status': 'skipped',
            'skipped': True,
            'reason': f'非交易日（{expected} 基准）且 K 线本次无更新',
        }
    else:
        from application.services.scheduler_tasks import handle_factor_compute
        logger.info("evening_pipeline: factor_compute start (full market)")
        results['factor_compute'] = handle_factor_compute({'max_symbols': 6000})

    # K线同步失败必须上抛（2026-09-10，w-23c70356）：update_gem_klines 内部
    # except 后返回 {'status':'error'} 而不抛，本函数把结果塞进 results 照常
    # return → 宿主记 success 并发"✅ 每日任务完成"，2026-09-03~09-09 连续 6 个
    # 交易日全市场同步失败却只有 ✅ 通知。放在因子计算之后 raise，保证因子仍按
    # 现有数据算完，只把任务判 failed 并触发失败告警。
    # ⚠️ 该语义**不受上面那道因子门影响**：status='error' 时因子段照跑（见判据的第三项）。
    if sync.get('status') == 'error':
        raise RuntimeError(f"K线同步失败：{str(sync.get('error'))[:300]}")

    return results


def _job_chip_distribution() -> Dict[str, Any]:
    from infrastructure.jobs.chip_distribution_update_job import execute
    return execute()


def _job_financial_statements() -> Dict[str, Any]:
    from infrastructure.jobs.financial_statement_update_job import execute
    return execute()


def _derive_idle_streak(counts_desc: List[Any]) -> Tuple[int, bool]:
    """自最近一个 window_end 往前数「有效产出为 0」的连续次数（纯函数，便于单测）。

    REQ-261005210015-1603 t-2d12c5（FR-5）：实证 10-02 与 10-05 两次运行的 ok 数都是 0，
    而全表最近一次有效产出停在 2026-09-12——"已经连续几次没算出东西"此前只能靠人翻库。
    返回 (streak, capped)：capped=True 表示取的窗口**全为 0**，真实 streak 可能更长（渲染成「≥N 次」）。
    """
    streak = 0
    for _window_end, ok_count in counts_desc:
        if int(ok_count or 0) != 0:
            break
        streak += 1
    return streak, (bool(counts_desc) and streak == len(counts_desc))


def _job_evolution_fitness() -> Dict[str, Any]:
    """B 链账户行为 fitness 盘后续采（RFC 012 P3，2026-09-05，恢复 8/14 断点）

    EvolutionFitnessService.compute_all_accounts 对全部 active 模拟账户计算
    滚动 20 交易日双侧捕获 fitness 并 upsert（幂等：同 (account, window_end,
    window_days) 覆盖，可安全重复）。对象是**账户行为**（agent_virtual 等），
    与策略参数进化（evolution_strategy_runs，RFC 012 P1）分域——数据供
    "行为进化"语义独立持续，绝不冒充策略排名（RFC 012 §0/§10 边界）。

    2026-10-05（REQ-261005210015-1603 t-2d12c5，FR-2/FR-3/FR-5）：本 handler 额外
    把"有没有产出"说清楚——组装人读 `summary`（有效/样本不足/无成交/数据缺口 + 空转连续次数）、
    声明 `no_output`（零有效产出时宿主改 ⚠️ 语气），两次读数均**只读**；
    读数失败只降级文案 + error 日志，**绝不**把一次成功的采集判失败。
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
    repo = EvolutionFitnessORMRepository()
    svc = EvolutionFitnessService(fitness_repo=repo)
    detail = svc.compute_all_accounts()

    # 空转统计（只读）：查询失败 → 文案降级为「空转统计不可用」+ error 日志，任务仍记 success。
    counts: List[Any] = []
    last_ok: Optional[str] = None
    stats_ok = True
    try:
        counts = repo.list_recent_window_ok_counts(limit=20)
        _last_ok_date = repo.get_last_ok_window_end()
        last_ok = _last_ok_date.isoformat() if _last_ok_date else None
    except Exception as e:  # noqa: BLE001 - 报告写不出来不许拖垮采集（设计「失败隔离」）
        stats_ok = False
        logger.error("evolution_fitness_idle_stats_failed", error=str(e)[:200])

    computed_ok = int(detail.get('computed_ok') or 0)
    text = (f"有效 {computed_ok}（样本不足 {detail.get('insufficient_sample', 0)}"
            f" / 无成交 {detail.get('no_trades', 0)}"
            f" / 数据缺口 {detail.get('data_gap', 0)}）")
    if computed_ok == 0:
        if not stats_ok:
            text += "｜空转统计不可用"
        else:
            streak, capped = _derive_idle_streak(counts)
            recent = last_ok or '从未'
            if streak >= 2:
                shown = f"≥{streak}" if capped else str(streak)
                text += f"｜已连续 {shown} 次无有效产出（最近有效：{recent}）"
            else:
                text += f"｜本次无有效产出（最近有效：{recent}）"

    # 异常（bench 源挂/DB 故障）仍会向上抛 → 宿主记 failed + 飞书告警（本卡不改这条）；
    # data_gap 账户（无快照/样本不足）由算法返回 status 落库留痕，不算失败。
    # 注意：detail 里**不得**出现 success / status 标记键，否则会触发失败判定的下钻（见设计陷阱 1）。
    return {'detail': detail, 'summary': text,
            'no_output': computed_ok == 0,
            'note': '账户行为 fitness（非策略参数进化）'}


def _job_freshness_guard() -> Dict[str, Any]:
    """新鲜度巡检：K线/因子滞后于最近交易日 + 任务失败残留 → 飞书告警"""
    from infrastructure.persistence.database.engine import get_engine

    # 基准日=前一交易日（2026-09-10，w-23c70356）：本巡检 17:20 跑，而当天 EOD 要到
    # 20:30 的 evening_pipeline 才落库 —— 原用"当天"当基准，结构上每个交易日都必然判
    # stale（09-04~09-09 连续 5 天误报），告警因长期噪声被忽略。观测对象是"上一交易日的
    # EOD 是否到位"，即滞后>1 个交易日，故基准取前一交易日。
    # 2026-10-04（REQ-261004102115-d3de）：基准日改由唯一口径给出（节假日感知），
    # 并把**判定来源**带进 result —— 日历不可用时按工作日口径判，读告警的人要看得出。
    from application.services.trading_day_resolver import last_closed_trading_day

    _resolved = last_closed_trading_day(datetime.now() - timedelta(days=1))
    expected = _resolved.date.isoformat()
    expected_source = 'weekday_fallback' if _resolved.degraded else 'calendar'
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
               'expected_source': expected_source, 'alert_sent': True}
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
                'expected_source': expected_source,
                'kline_coverage': f"{cov['covered']}/{cov['total']}",
                'kline_stale': cov['stale'], 'kline_oldest_stale': cov['oldest_stale'],
                'factor_latest': str(factor_latest),
                'failed_jobs': failed_jobs, 'alert_sent': True}

    return {'status': 'fresh', 'expected': expected,
            'expected_source': expected_source,
            'kline_coverage': f"{cov['covered']}/{cov['total']}",
            'kline_stale': cov['stale'], 'kline_oldest_stale': cov['oldest_stale'],
            'factor_latest': str(factor_latest)}


def _last_trading_day(ref: datetime) -> str:
    """最近一个**已收盘**的交易日（`YYYY-MM-DD`）。

    2026-10-04（REQ-261004102115-d3de）：原实现是「周末排除法；节假日由告警人工复核」，
    于是国庆休市期间把 2026-10-02 当成应有交易日，让探针与 freshness_guard 一起对着一份
    完好的数据报"K 线滞后"。现改为复用**唯一口径**
    `application.services.trading_day_resolver.last_closed_trading_day`（日历表 → AKShare → 工作日回退）。

    **签名与返回类型保持不变**——本仓有 40+ 处按原样导入它（含 `daily_jobs_bootstrap` 转发壳）。
    """
    from application.services.trading_day_resolver import last_closed_trading_day

    return last_closed_trading_day(ref).date.isoformat()


