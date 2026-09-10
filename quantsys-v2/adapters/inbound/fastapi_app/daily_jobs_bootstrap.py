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
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

_TICK_SEC = 60
_RUNNING_STALE_HOURS = 3  # running 状态超过 3 小时视为死亡，允许重跑
_FAILED_RETRY_HOURS = 2   # failed 超过 2 小时自动重试一次（探活门控下失败 pass 很便宜）

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
    from sqlalchemy import text

    universe = """
        SELECT s.symbol FROM quant.stocks s
         WHERE NOT s.is_delisted
           AND s.name NOT LIKE '%退%'
           AND s.name NOT LIKE '%ST%'
    """
    with engine.connect() as conn:
        row = conn.execute(
            text(f"""
                SELECT
                  (SELECT count(*) FROM ({universe}) u) AS total,
                  (SELECT count(*) FROM ({universe}) u
                    WHERE EXISTS (SELECT 1 FROM quant.daily_klines k
                                   WHERE k.symbol = u.symbol
                                     AND k.trade_date >= :expected)) AS covered,
                  (SELECT min(mx) FROM (
                      SELECT s.symbol, max(k.trade_date) AS mx
                        FROM quant.stocks s
                        LEFT JOIN quant.daily_klines k ON k.symbol = s.symbol
                       WHERE NOT s.is_delisted
                         AND s.name NOT LIKE '%退%'
                         AND s.name NOT LIKE '%ST%'
                       GROUP BY s.symbol) t
                    WHERE t.mx IS NULL OR t.mx < :expected) AS oldest_stale
            """),
            {'expected': expected},
        ).mappings().first()

    total = int(row['total'] or 0)
    covered = int(row['covered'] or 0)
    oldest = row['oldest_stale']
    return {
        'total': total,
        'covered': covered,
        'stale': total - covered,
        'coverage': (covered / total) if total else 1.0,
        'oldest_stale': str(oldest) if oldest else None,
    }


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
        d = d - __import__('datetime').timedelta(days=1)
    while d.weekday() >= 5:
        d = d - __import__('datetime').timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def _job_failure_watch(engine) -> List[Dict[str, Any]]:
    """任务失败巡检：过去 3 个自然日（不含今天——今天失败仍在 2h 自动重试冷却期）仍 failed 的活跃任务

    补 K线/因子巡检的盲区：数据恰好未滞后但 job 本身失败（如 chip_distribution 失败但
    K线新鲜、financial_statements 周六失败周一才发现）。只查 JOBS 内活跃任务，
    已退役 job（如 morning_topup）的历史 failed 残留不告警。
    """
    from sqlalchemy import text as _text, bindparam
    active = [j.job_id for j in JOBS]
    if not active:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            _text(
                "SELECT job_id, run_date, error FROM quant.inprocess_job_runs "
                "WHERE status='failed' AND run_date < CURRENT_DATE "
                "AND run_date >= CURRENT_DATE - 3 "
                "AND job_id IN :jobs ORDER BY run_date DESC, job_id"
            ).bindparams(bindparam('jobs', expanding=True)),
            {'jobs': active},
        ).fetchall()
    return [{'job_id': r[0], 'run_date': str(r[1]), 'error': (r[2] or '')[:200]}
            for r in rows]


def _job_freshness_guard() -> Dict[str, Any]:
    """新鲜度巡检：K线/因子滞后于最近交易日 + 任务失败残留 → 飞书告警"""
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text

    expected = _last_trading_day(datetime.now())
    engine = get_engine()
    with engine.connect() as conn:
        factor_latest = conn.execute(
            text("SELECT max(factor_date) FROM quant.factor_values")).scalar()

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
        return {'status': 'fresh_but_job_failed', 'expected': expected,
                'kline_latest': str(kline_latest), 'factor_latest': str(factor_latest),
                'failed_jobs': failed_jobs, 'alert_sent': True}

    return {'status': 'fresh', 'expected': expected,
            'kline_latest': str(kline_latest), 'factor_latest': str(factor_latest)}


def _send_feishu(text: str) -> bool:
    """飞书告警（失败只记日志，不阻断任务流）"""
    try:
        from application.services.feishu_service import FeishuNotificationService
        return FeishuNotificationService().send_text(text)
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
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    
    engine = get_engine()
    reports = []
    auto_disabled = []
    marked_inactive = []
    
    with engine.begin() as conn:  # 使用 begin() 自动提交
        # 获取所有启用规则
        rules = conn.execute(text(
            "SELECT id, symbol, context, conditions, expires_at, created_at, action_hint "
            "FROM quant.watch_rules WHERE enabled = true"
        )).fetchall()
        
        for rule in rules:
            rule_id, symbol, context, conditions, expires_at, created_at, action_hint = rule
            status = 'HEALTHY'
            reason = '正常'
            
            # 1. 检查有效期
            if expires_at and expires_at < datetime.now():
                status = 'EXPIRED'
                reason = f'已过有效期（{expires_at.strftime("%Y-%m-%d")}）'
            else:
                # 2. 检查价格偏差
                try:
                    # 获取当前价格
                    price_row = conn.execute(text(
                        "SELECT close FROM quant.daily_klines WHERE symbol = :s "
                        "ORDER BY trade_date DESC LIMIT 1"
                    ), {'s': symbol}).fetchone()
                    
                    if price_row and conditions:
                        current_price = float(price_row[0])
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
                        trigger_row = conn.execute(text(
                            "SELECT MAX(triggered_at) FROM quant.watch_triggers WHERE rule_id = :rid"
                        ), {'rid': rule_id}).fetchone()
                        
                        last_trigger = trigger_row[0] if trigger_row else None
                        
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
                conn.execute(text(
                    "UPDATE quant.watch_rules SET enabled = false, updated_at = NOW() WHERE id = :rid"
                ), {'rid': rule_id})
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
    from application.services.feishu_service import FeishuNotificationService

    events = get_event_calendar_repo().list_upcoming(days_ahead=2)
    target = [e for e in events if e.status == 'pending' and (e.importance or 1) >= 2]
    if not target:
        return {'status': 'no_event', 'pending_in_window': len(events), 'notified': 0}

    high = [e for e in target if e.importance >= 3]
    mid = [e for e in target if e.importance < 3]
    svc = FeishuNotificationService()
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

# ── 运行状态表（幂等核心） ─────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS quant.inprocess_job_runs (
    job_id      text        NOT NULL,
    run_date    date        NOT NULL,
    status      text        NOT NULL,   -- running/success/failed
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    result      jsonb,
    error       text,
    PRIMARY KEY (job_id, run_date)
)
"""


def _ensure_table() -> None:
    from infrastructure.persistence.database.engine import get_engine
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(_DDL)


def _get_run(job_id: str, run_date: str) -> Optional[Dict[str, Any]]:
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT status, started_at FROM quant.inprocess_job_runs "
            "WHERE job_id=:j AND run_date=:d"
        ), {'j': job_id, 'd': run_date}).fetchone()
    if not row:
        return None
    return {'status': row[0], 'started_at': row[1]}


def _mark_running(job_id: str, run_date: str) -> None:
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO quant.inprocess_job_runs (job_id, run_date, status, started_at) "
            "VALUES (:j, :d, 'running', now()) "
            "ON CONFLICT (job_id, run_date) DO UPDATE "
            "SET status='running', started_at=now(), finished_at=NULL, error=NULL"
        ), {'j': job_id, 'd': run_date})


def _mark_done(job_id: str, run_date: str, status: str,
               result: Optional[Dict] = None, error: Optional[str] = None) -> None:
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE quant.inprocess_job_runs "
            "SET status=:s, finished_at=now(), result=:r, error=:e "
            "WHERE job_id=:j AND run_date=:d"
        ), {'s': status, 'r': json.dumps(result, ensure_ascii=False, default=str) if result else None,
            'e': (error or '')[:1000] or None, 'j': job_id, 'd': run_date})


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
            'symbols_checked', 'status', 'expected', 'kline_latest', 'factor_latest']
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

def _jobs_loop(stop_event: threading.Event) -> None:
    _ensure_table()
    while not stop_event.is_set():
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        for job in JOBS:
            try:
                last = _get_run(job.job_id, today)
                if is_due(job, now, last):
                    threading.Thread(
                        target=_run_job, args=(job, today),
                        name=f"job-{job.job_id}", daemon=True,
                    ).start()
            except Exception as e:
                # 单任务调度异常不能杀死循环
                logger.error("inprocess_job_schedule_error", job=job.job_id, error=str(e))
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
    """今日任务运行状态（巡检/排障用）"""
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    _ensure_table()
    engine = get_engine()
    today = datetime.now().strftime('%Y-%m-%d')
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT job_id, status, started_at, finished_at, error "
            "FROM quant.inprocess_job_runs WHERE run_date=:d ORDER BY started_at"
        ), {'d': today}).fetchall()
    ran = {r[0]: {'status': r[1], 'started_at': str(r[2]),
                  'finished_at': str(r[3]) if r[3] else None,
                  'error': r[4]} for r in rows}
    return [
        {'job_id': j.job_id, 'description': j.description,
         'scheduled_at': j.run_at.strftime('%H:%M'),
         **ran.get(j.job_id, {'status': 'not_run', 'started_at': None,
                              'finished_at': None, 'error': None})}
        for j in JOBS
    ]
