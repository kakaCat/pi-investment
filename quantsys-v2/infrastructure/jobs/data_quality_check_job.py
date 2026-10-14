"""
数据质量检查Job - 定时任务执行逻辑

每日检查：
1. 检测数据质量问题（缺失、重复、异常）
2. 补充缺失数据（可选）
3. 生成质量报告
"""
import sys
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Mapping, Optional, Tuple

# 添加项目路径

from application.services.data_quality_service import DataQualityService
from application.services.kline_domain import DomainSnapshot, build_domain_snapshot

logger = logging.getLogger(__name__)

# ── 护栏常量（2026-09-11 w-23c70356）────────────────────────────────────
# 背景：任务 232 配置 {"days": 365, "stock_limit": 100, ...} 与实现读取的键名
# （check_days / symbols_limit）不一致 → 配置静默失效。实测证据：run 3527
# （2026-09-10 22:00）日志 "日期范围: 2026-08-11 ~ 2026-09-10 / 股票限制: 全部"
# —— 配置的 365 天与 100 只限制都没生效，实际跑 30 天 × 5699 只。
DEFAULT_CHECK_DAYS = 30
MAX_CHECK_DAYS = 90            # 日检窗口上限：超出则成本线性膨胀（5699 只 × N 天）
DEFAULT_MAX_RUNTIME_SEC = 1800  # 墙钟预算 30 分钟（run 3391 曾空转 2.8 小时）
BACKFILL_SEC_PER_SYMBOL = 20    # 实测 run 3480 回填 50 只耗时 924.87s ≈ 18.5s/只
MIN_BACKFILL_BUDGET_SEC = 120   # 剩余预算不足 2 分钟则不启动回填
DEFAULT_MAX_BACKFILL_SYMBOLS = 50

# ── 告警口径常量（2026-10-06 · REQ-261006163444-8e4f）────────────────────
# 背景：原阈值 500 / 95.0 / 50% 的**分母是全库 5686 只**（含约 400 只退市/长停标的），
# 且 D 级按"当日行数"计 —— 同一天跑两次即翻倍（实测 806 行 / 真值 404 只）。
# 新口径：三项指标只在**可交易域**内判定（见 application/services/kline_domain.py）。
DEFAULT_D_GRADE_THRESHOLD = 20            # 域内 D 级只数（域内现值 3）
DEFAULT_SCORE_THRESHOLD = 88.0            # 域内平均评分（旧值 95.0 高于该口径上限 95.02 ⇒ 永久红）
DEFAULT_COVERAGE_INFO_THRESHOLD = 97.0    # 域内平均覆盖率：**信息项**，不单独告警
DEFAULT_BACKFILL_FAIL_RATE_THRESHOLD = 50.0
DEFAULT_BACKFILL_MIN_SAMPLE = 10          # 分母 < 10 不判失败率（样本不足不构成结论）
DROPPED_SYMBOLS_DISPLAY_LIMIT = 20        # 正文里掉出名单的展示上限；count 永远是全量真值


def _normalize_params(params: Dict[str, Any]) -> Tuple[Dict[str, Any], list]:
    """键名归一 + 防呆钳制，返回 (生效参数, 说明列表)。

    兼容历史键名（days / stock_limit），并把生效值显式记录下来，
    避免"配置了但没生效"再次静默发生（R-013 可核验原则）。
    """
    p = dict(params or {})
    notes: list = []

    check_days = p.get('check_days')
    if check_days is None and p.get('days') is not None:
        check_days = p.get('days')
        notes.append(f"参数别名 days={p.get('days')} → check_days")
    try:
        check_days = int(check_days) if check_days is not None else DEFAULT_CHECK_DAYS
    except (TypeError, ValueError):
        notes.append(f"check_days 非法值 {check_days!r}，回退默认 {DEFAULT_CHECK_DAYS}")
        check_days = DEFAULT_CHECK_DAYS
    if check_days > MAX_CHECK_DAYS:
        notes.append(f"check_days={check_days} 超上限，钳制为 {MAX_CHECK_DAYS}")
        check_days = MAX_CHECK_DAYS
    if check_days < 1:
        notes.append(f"check_days={check_days} 非法，回退默认 {DEFAULT_CHECK_DAYS}")
        check_days = DEFAULT_CHECK_DAYS

    symbols_limit = p.get('symbols_limit')
    if symbols_limit is None and p.get('stock_limit'):
        symbols_limit = p.get('stock_limit')
        notes.append(f"参数别名 stock_limit={p.get('stock_limit')} → symbols_limit")
    if p.get('check_all_stocks'):
        if symbols_limit:
            notes.append(
                f"check_all_stocks=true 覆盖 symbols_limit={symbols_limit}（全市场检查）"
            )
        symbols_limit = None

    max_runtime_sec = p.get('max_runtime_sec')
    try:
        max_runtime_sec = int(max_runtime_sec) if max_runtime_sec else DEFAULT_MAX_RUNTIME_SEC
    except (TypeError, ValueError):
        notes.append(f"max_runtime_sec 非法值 {max_runtime_sec!r}，回退默认 {DEFAULT_MAX_RUNTIME_SEC}")
        max_runtime_sec = DEFAULT_MAX_RUNTIME_SEC

    max_backfill_symbols = p.get('max_backfill_symbols') or DEFAULT_MAX_BACKFILL_SYMBOLS
    try:
        max_backfill_symbols = int(max_backfill_symbols)
    except (TypeError, ValueError):
        max_backfill_symbols = DEFAULT_MAX_BACKFILL_SYMBOLS

    def _pick(key, default, cast):
        """取值 + 防呆：非法值回落默认并写 notes（禁静默）。"""
        raw = p.get(key)
        if raw is None or raw == '':
            return default
        try:
            return cast(raw)
        except (TypeError, ValueError):
            notes.append(f"参数 {key}={raw!r} 非法，回退默认 {default}")
            return default

    # 告警阈值（REQ-261006163444-8e4f FR-4）：四个键都可配、都要落 effective_params
    quality_threshold = _pick('quality_threshold', DEFAULT_SCORE_THRESHOLD, float)
    d_grade_threshold = _pick('d_grade_threshold', DEFAULT_D_GRADE_THRESHOLD, int)
    coverage_info_threshold = _pick('coverage_info_threshold', DEFAULT_COVERAGE_INFO_THRESHOLD, float)
    backfill_fail_rate_threshold = _pick(
        'backfill_fail_rate_threshold', DEFAULT_BACKFILL_FAIL_RATE_THRESHOLD, float)
    backfill_min_sample = max(1, _pick('backfill_min_sample', DEFAULT_BACKFILL_MIN_SAMPLE, int))

    effective = {
        'check_days': check_days,
        'symbols_limit': symbols_limit,
        'auto_backfill': bool(p.get('auto_backfill', False)),
        'include_report': bool(p.get('include_report', False)),
        'max_runtime_sec': max_runtime_sec,
        'max_backfill_symbols': max_backfill_symbols,
        'quality_threshold': quality_threshold,
        'd_grade_threshold': d_grade_threshold,
        'coverage_info_threshold': coverage_info_threshold,
        'backfill_fail_rate_threshold': backfill_fail_rate_threshold,
        'backfill_min_sample': backfill_min_sample,
    }
    return effective, notes


class DataQualityCheckJob:
    """数据质量检查Job类 - 供调度器使用"""

    def __init__(self):
        """初始化Job"""
        self.service = None

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行数据质量检查

        Args:
            params: 任务参数
                - check_days: 检查最近N天的数据（默认30天）
                - auto_backfill: 是否自动补充缺失数据（默认False）
                - symbols_limit: 检查的股票数量限制（None=全部）
                - include_report: 是否生成详细报告（默认False）

        Returns:
            执行结果字典
        """
        return daily_data_quality_check(**params)


def daily_data_quality_check(**params):
    """
    每日数据质量检查

    Args:
        **params: 任务参数
            - check_days: 检查最近N天的数据（默认30天）
            - auto_backfill: 是否自动补充缺失数据（默认False）
            - symbols_limit: 检查的股票数量限制（None=全部）
            - include_report: 是否生成详细报告（默认False）

    Returns:
        dict: 执行结果
    """
    logger.info("="*70)
    logger.info("每日数据质量检查开始")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)

    started_monotonic = time.monotonic()
    effective, param_notes = _normalize_params(params)
    check_days = effective['check_days']
    auto_backfill = effective['auto_backfill']
    symbols_limit = effective['symbols_limit']
    include_report = effective['include_report']
    deadline = started_monotonic + effective['max_runtime_sec']

    try:
        for note in param_notes:
            logger.warning(f"参数处理: {note}")

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=check_days)).strftime('%Y-%m-%d')

        # 生效参数显式落日志：配置键与实现键漂移曾导致 stock_limit/days 静默失效
        logger.info(f"检查参数（生效值）:")
        logger.info(f"  日期范围: {start_date} ~ {end_date} ({check_days} 天)")
        logger.info(f"  股票限制: {symbols_limit or '全部'}")
        logger.info(f"  自动补充: {auto_backfill}")
        logger.info(f"  墙钟预算: {effective['max_runtime_sec']}s / 单次回填上限: {effective['max_backfill_symbols']} 只")

        # 初始化服务
        logger.info("\n初始化数据质量服务...")
        service = DataQualityService()

        # 获取股票池
        if symbols_limit:
            symbols = service._get_hot_stocks(limit=symbols_limit)
        else:
            symbols = service._get_hot_stocks(limit=None)

        logger.info(f"股票池: {len(symbols)} 只股票")

        # 检查域快照（REQ-261006163444-8e4f FR-1）：判据是**数据事实**（最后交易日有无 K 线），
        # 不依赖 is_delisted/is_suspended 标记（实测仅覆盖死标的 46%）。
        # 零新增状态、零 DDL：由 quant.daily_klines 的 trade_date 现算。
        domain = build_domain_snapshot(service.kline_repo)
        if domain.degraded:
            logger.error(f"⚠️ 分域快照不可用: {domain.degrade_reason}（本次不做域内判定）")
        else:
            logger.info(
                f"检查域: 可交易 {len(domain.tradable)} / 观察中 {len(domain.observing)} / "
                f"存量 {len(domain.stock)}（最后交易日 {domain.last_trade_date}，"
                f"上期 {domain.prev_trade_date or '无'}）"
            )

        thresholds = {
            'd_grade': effective['d_grade_threshold'],
            'score': effective['quality_threshold'],
            'coverage_info': effective['coverage_info_threshold'],
            'backfill_fail_rate': effective['backfill_fail_rate_threshold'],
            'backfill_min_sample': effective['backfill_min_sample'],
        }

        # 1. 检查数据质量
        logger.info("\n1. 检查数据质量...")
        # 检查阶段也受墙钟约束：给回填预留最小预算，避免"检查跑 100 分钟 + 回填再跑"
        check_deadline = deadline - MIN_BACKFILL_BUDGET_SEC
        quality_result = service.check_data_quality(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            include_report=include_report,
            deadline=check_deadline
        )

        if not quality_result['success']:
            raise Exception(f"质量检查失败: {quality_result.get('error')}")

        summary = quality_result['summary']
        logger.info(f"\n质量检查结果:")
        logger.info(f"  总股票数: {summary['total_stocks']}")
        logger.info(f"  有问题股票: {summary['stocks_with_issues']}")
        logger.info(f"  缺失天数: {summary['total_missing_days']}")
        logger.info(f"  平均覆盖率: {summary['avg_coverage_rate']:.2f}%")
        logger.info(f"  质量评分: {summary['data_quality_score']:.2f}")
        check_truncated = bool(summary.get('check_truncated'))
        if check_truncated:
            logger.warning(
                f"  ⚠️ 检查阶段触达预算: 已扫描 {summary.get('checked_stocks')}/"
                f"{summary.get('total_stocks')} 只（剩余未做重复/异常扫描）"
            )
        # 明细只返回前 50 只（服务层上限），与检出数不一致时如实说明，
        # 否则"只回填了 50 只"会被误读为"只有 50 只有问题"
        if summary['stocks_with_issues'] > len(quality_result['stocks_with_issues']):
            logger.warning(
                f"  注: 检出 {summary['stocks_with_issues']} 只，明细仅返回前 "
                f"{len(quality_result['stocks_with_issues'])} 只（服务层上限），回填范围以此为界"
            )

        # 长耗时的回填阶段前先释放共享事务，避免连接被 PG 因
        # idle-in-transaction 超时杀掉后拖累后续告警查询与 run 记账
        _release_db_session("回填前")

        # 2. 自动补充（如果启用）—— 受墙钟预算与单次标的额度约束
        # 2026-09-11 w-23c70356：原实现把"检测到有问题的全部标的"直接丢给回填，
        # 回填内部还会对失败标的 retry 5 轮 ⇒ 夜间数据源不可用时空转数小时
        # （run 3391 = 2.8 小时；run 3480 回填 50 只耗时 924.87s，失败 49 只）。
        backfill_result = None
        backfill_skip_reason = None
        budget_limited = False
        timed_out = False

        if auto_backfill and summary['stocks_with_issues'] > 0:
            logger.info("\n2. 自动补充缺失数据...")

            # 提取有问题的股票（REQ-261006163444-8e4f FR-4）：
            # ① 用**全量** per_symbol，不再用被 [:50] 截断的展示明细
            #    （旧样本既小又偏：今日 7 只目标里 5 只已退市）；
            # ② 只在**可交易域**内选——对退市/长停标的回填是必败动作（数据源永远取不到），
            #    既烧墙钟预算，又把"标的已死"污染成"数据源不可用"的失败率。
            per_symbol_map = quality_result.get('per_symbol') or {}
            symbols_with_issues = _select_backfill_targets(per_symbol_map, domain.tradable)

            check_elapsed = time.monotonic() - started_monotonic
            remaining = deadline - time.monotonic()
            budget_symbols = max(1, int(remaining // BACKFILL_SEC_PER_SYMBOL))
            limit = min(effective['max_backfill_symbols'], budget_symbols)

            if domain.degraded:
                backfill_skip_reason = (
                    f"分域快照不可用（{domain.degrade_reason}）→ 不在不可信的分母上开火"
                )
                logger.warning(f"  {backfill_skip_reason}")
            elif remaining < MIN_BACKFILL_BUDGET_SEC:
                backfill_skip_reason = (
                    f"剩余预算 {remaining:.0f}s < {MIN_BACKFILL_BUDGET_SEC}s"
                    f"（检查阶段耗时 {check_elapsed:.0f}s），跳过回填避免超预算"
                )
                timed_out = True
                logger.warning(f"  {backfill_skip_reason}")
            elif symbols_with_issues:
                if len(symbols_with_issues) > limit:
                    budget_limited = True
                    backfill_skip_reason = (
                        f"检出 {len(symbols_with_issues)} 只超本次额度 {limit} 只"
                        f"（剩余预算 {remaining:.0f}s ≈ {budget_symbols} 只，单次上限 "
                        f"{effective['max_backfill_symbols']} 只），本轮只补缺失最多的 Top{limit}"
                    )
                    logger.warning(f"  {backfill_skip_reason}")
                targets = symbols_with_issues[:limit]
                logger.info(f"  补充股票: {len(targets)} 只（检出 {len(symbols_with_issues)} 只）")
                backfill_result = service.backfill_missing_data(
                    symbols=targets,
                    start_date=start_date,
                    end_date=end_date,
                    mode='auto',
                    max_workers=8
                )

                if backfill_result.get('retry_skipped_reason'):
                    logger.warning(f"  回填重试熔断: {backfill_result['retry_skipped_reason']}")

                if backfill_result['success']:
                    logger.info(f"  补充成功: {backfill_result['summary']['success_count']} 只")
                    logger.info(f"  补充天数: {backfill_result['summary']['total_days_filled']}")
                else:
                    # 回填"部分失败"时 error 为空，原写法会打印 "补充失败: None"
                    _bs2 = backfill_result.get('summary') or {}
                    _err = backfill_result.get('error')
                    logger.warning(
                        f"  补充未全部成功: {_err if _err else ''}"
                        f"成功 {_bs2.get('success_count', 0)}/{_bs2.get('total_stocks', 0)} 只, "
                        f"失败 {_bs2.get('failed_count', 0)} 只, 补充 {_bs2.get('total_days_filled', 0)} 条"
                    )
            else:
                logger.info("  无需补充（无缺失数据）")

        # 构建结果（符合调度器期望的格式）
        result = {
            'success': True,  # 调度器期望的键名
            'timestamp': datetime.now().isoformat(),
            'check_period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': check_days
            },
            'check_summary': summary,  # 调度器期望的键名
            'stocks_with_issues_count': summary['stocks_with_issues'],
            'data_quality_score': summary['data_quality_score'],
            'message': '数据质量检查完成',
            'backfill_executed': False,  # 默认值
            # 生效参数与预算执行情况（可核验，避免"配置了但没生效"再次静默发生）
            'effective_params': effective,
            'param_notes': param_notes,
            'runtime_sec': round(time.monotonic() - started_monotonic, 2),
            'timed_out': timed_out,
            'check_truncated': check_truncated,
            'checked_stocks': summary.get('checked_stocks'),
            'skipped_stocks': summary.get('skipped_stocks'),
            'budget_limited': budget_limited,
            'backfill_skip_reason': backfill_skip_reason,
            'backfill_degraded': False,
            # 检查域口径（REQ-261006163444-8e4f）：domain / domain_dropped / alert_thresholds
            # 由 _check_quality_alerts 回填；alert_scope 先落默认值，便于异常时也能看出口径。
            'alert_scope': 'degraded' if domain.degraded else 'tradable',
        }

        if backfill_result:
            result['backfill_summary'] = backfill_result.get('summary')
            result['backfill_executed'] = True
            _bs = backfill_result.get('summary') or {}
            _bt = _bs.get('total_stocks') or 0
            # 回填全灭（数据源不可用）时如实标注，避免看板上"成功"掩盖数据缺口扩大
            if _bt and (_bs.get('success_count') or 0) == 0:
                result['backfill_degraded'] = True
                logger.warning(
                    f"  ⚠️ 回填无任何成功（{_bt} 只全部失败）→ 数据缺口未收敛，标记 backfill_degraded"
                )

        if include_report and 'report_url' in quality_result:
            result['report_url'] = quality_result['report_url']

        logger.info("\n执行结果:")
        logger.info(f"  状态: 成功")
        logger.info(f"  质量评分: {summary['data_quality_score']:.2f}")
        logger.info(f"  问题股票: {summary['stocks_with_issues']}/{summary['total_stocks']}")

        logger.info("="*70)
        logger.info("✅ 每日数据质量检查完成")
        logger.info("="*70)

        # 质量告警检查（REQ-261006163444-8e4f）：口径 = 可交易域；
        # 统计 = 本次 run 的全量 per_symbol（不受展示层 [:50] 截断影响）
        _check_quality_alerts(result, domain, quality_result.get('per_symbol') or {}, thresholds)

        return result

    except Exception as e:
        logger.error(f"❌ 每日数据质量检查失败: {e}")
        import traceback
        traceback.print_exc()

        return {
            'success': False,  # 调度器期望的键名
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'message': '数据质量检查失败'
        }


def _release_db_session(stage: str) -> None:
    """释放线程内共享 Session 的挂起事务。

    背景（2026-09-11 00:31 全市场实跑）：get_session() 返回**线程内共享** Session，
    检查阶段写入审计后事务一直挂着；随后回填阶段耗时 822.86s（50 只 × 16.5s，
    夜间数据源超时），该连接长期 idle-in-transaction，被 PG 侧
    "terminating connection due to idle-in-transaction timeout" 杀掉，
    导致紧随其后的告警查询直接失败（告警内容丢失）。此处显式回滚，代价近乎为零。
    """
    try:
        from infrastructure.persistence.orm.config import get_session
        get_session().rollback()
    except Exception as e:  # 回滚失败不阻断主流程，仅记录
        logger.warning(f"释放 DB 会话失败（{stage}）: {e}")


# 2026-09-14（w-32314d00，REQ-24e15d B2）：原 _get_alert_session() 已删除。
# 它存在的唯一理由是"告警查询前先回滚挂起事务、失败则丢弃重建会话"，
# 而这正是 KlineQualityRepository.count_by_grade_on 内部 _safe_rollback 的职责；
# 收口后它变成无人调用的死代码，留着只会诱导后来者再写一套会话修补。


def _select_backfill_targets(
    per_symbol: Mapping[str, Mapping[str, Any]],
    tradable,
    limit: Optional[int] = None,
) -> list:
    """回填目标选取（REQ-261006163444-8e4f FR-4）——**只在可交易域内**。

    两条都是缺陷修复：
    · 候选集改用**全量 per_symbol**，不再用被 [:50] 截断的展示明细（旧样本既小又偏：
      今日 7 只目标里 5 只已退市）；
    · 只在**可交易域**内选：对退市/长停标的回填是必败动作（数据源永远取不到），
      既烧墙钟预算，又把"标的已死"污染成"数据源不可用"的失败率。

    排序仍是"缺失天数降序"（额度有限时花在最有价值的标的上）。
    """
    rank = {
        s: rec.get('missing_days_count', 0)
        for s, rec in (per_symbol or {}).items()
        if rec.get('missing_days_count', 0) > 0 and s in tradable
    }
    ordered = sorted(rank, key=rank.get, reverse=True)
    return ordered[:limit] if limit is not None else ordered


@dataclass(frozen=True)
class DomainStats:
    """告警用的域内事实（一次算好，判据与正文共用，避免两处各算一遍）。"""

    last_trade_date: Optional[str]
    tradable: int
    observing: int
    stock: int
    stats_symbols: int
    partial: bool
    d_grade: int
    mean_score: float
    mean_coverage: float
    dropped_count: int
    dropped_symbols: Tuple[str, ...]
    dropped_truncated: bool
    dropped_known: bool
    degraded: bool
    degrade_reason: Optional[str]
    backfill_total: int
    backfill_failed: int

    @property
    def backfill_fail_rate(self) -> float:
        return (self.backfill_failed / self.backfill_total * 100.0) if self.backfill_total else 0.0


def _build_domain_stats(
    domain: DomainSnapshot,
    per_symbol: Mapping[str, Mapping[str, Any]],
    backfill_summary: Optional[Mapping[str, Any]],
) -> DomainStats:
    """把「域快照 + 本次 run 的全量 per_symbol + 回填汇总」折成一份域内事实。"""
    in_domain = [(s, rec) for s, rec in (per_symbol or {}).items() if s in domain.tradable]
    scores = [float(rec.get('quality_score') or 0.0) for _, rec in in_domain]
    coverages = [float(rec.get('coverage_rate') or 0.0) for _, rec in in_domain]
    dropped = tuple(sorted(domain.dropped_new))
    bs = backfill_summary or {}
    return DomainStats(
        last_trade_date=domain.last_trade_date,
        tradable=len(domain.tradable),
        observing=len(domain.observing),
        stock=len(domain.stock),
        stats_symbols=len(in_domain),
        partial=len(in_domain) < len(domain.tradable),
        d_grade=sum(1 for _, rec in in_domain if rec.get('grade') == 'D'),
        mean_score=(sum(scores) / len(scores)) if scores else float('nan'),
        mean_coverage=(sum(coverages) / len(coverages)) if coverages else float('nan'),
        dropped_count=len(dropped),
        dropped_symbols=dropped[:DROPPED_SYMBOLS_DISPLAY_LIMIT],
        dropped_truncated=len(dropped) > DROPPED_SYMBOLS_DISPLAY_LIMIT,
        dropped_known=bool(domain.dropped_known),
        degraded=bool(domain.degraded),
        degrade_reason=domain.degrade_reason,
        backfill_total=int(bs.get('total_stocks') or 0),
        backfill_failed=int(bs.get('failed_count') or 0),
    )


def _check_quality_alerts(
    result: Dict[str, Any],
    domain: DomainSnapshot,
    per_symbol: Mapping[str, Mapping[str, Any]],
    thresholds: Mapping[str, float],
) -> Optional[Dict[str, Any]]:
    """域内数据质量告警（REQ-261006163444-8e4f）。

    与旧版的差别（每一条都有实测证据）：
    · 三项指标只在**可交易域**内统计 —— 旧版把约 400 只退市/长停标的算进分母，
      平均覆盖率被从 98.54% 拉到 91.70%、评分从 90.84 拉到 86.28；
    · D 级按**本次 run 的 distinct 标的**计 —— 旧版按「当日行数」计，同一天跑两次即翻倍
      （实测 806 行 / 真值 404 只），触发过一条纯属虚构的告警；
    · 阈值随口径重定（域内 D级 > 20 / 评分 < 88.0 / 覆盖率仅信息项 / 回填失败率需分母 >= 10）；
    · 新增「本期掉出可交易域」哨兵 —— 新掉出必须亮相，否则新口径会把采集漏批静默豁免。

    降级一律**响亮**：分域不可用或 per_symbol 缺失 ⇒ error 项 qa_scope_unavailable，
    **不回退**到 count_by_grade_on（避免出现第二个真相源）。

    Returns:
        外发回执（与 result['alert_dispatch'] 同义）；无告警或异常时为 None。
    """
    try:
        stats = _build_domain_stats(domain, per_symbol, result.get('backfill_summary'))
        result['domain'] = {
            'last_trade_date': stats.last_trade_date,
            'prev_trade_date': domain.prev_trade_date,
            'tradable_count': stats.tradable,
            'observing_count': stats.observing,
            'stock_count': stats.stock,
            'stats_symbols': stats.stats_symbols,
            'partial': stats.partial,
            'degraded': stats.degraded,
            'degrade_reason': stats.degrade_reason,
        }
        result['domain_dropped'] = {
            'count': stats.dropped_count,
            'symbols': list(stats.dropped_symbols),
            'truncated': stats.dropped_truncated,
            'known': stats.dropped_known,
            'reason': None if stats.dropped_known else 'no_prev_trade_date',
        }
        result['alert_thresholds'] = {
            'd_grade': thresholds.get('d_grade', DEFAULT_D_GRADE_THRESHOLD),
            'score': thresholds.get('score', DEFAULT_SCORE_THRESHOLD),
            'coverage_info': thresholds.get('coverage_info', DEFAULT_COVERAGE_INFO_THRESHOLD),
            'backfill_fail_rate': thresholds.get('backfill_fail_rate',
                                                 DEFAULT_BACKFILL_FAIL_RATE_THRESHOLD),
            'backfill_min_sample': thresholds.get('backfill_min_sample',
                                                  DEFAULT_BACKFILL_MIN_SAMPLE),
        }

        alerts: list = []
        d_threshold = result['alert_thresholds']['d_grade']
        score_threshold = result['alert_thresholds']['score']
        fail_threshold = result['alert_thresholds']['backfill_fail_rate']
        min_sample = result['alert_thresholds']['backfill_min_sample']

        if stats.degraded or stats.stats_symbols == 0:
            # 分域不可用：不发域内阈值告警，但**必须**响亮（不许静默跳过判定）
            reason = stats.degrade_reason or (
                'per_symbol 缺失或为空' if not per_symbol else '域内无可统计标的'
            )
            result['alert_scope'] = 'degraded'
            alerts.append({
                'level': 'error',
                'type': 'qa_scope_unavailable',
                'message': f'❌ 分域不可用，本次未做域内判定（原因: {reason}）',
            })
        else:
            result['alert_scope'] = 'tradable'
            if stats.d_grade > d_threshold:
                alerts.append({
                    'level': 'warning',
                    'type': 'quality_grade',
                    'message': f'⚠️ D级股票数量过多: {stats.d_grade}只 (阈值: {d_threshold}, 域内)',
                })
            if stats.mean_score < score_threshold:
                alerts.append({
                    'level': 'warning',
                    'type': 'quality_score',
                    'message': (f'⚠️ 数据质量评分偏低: {stats.mean_score:.2f} '
                                f'(阈值: {score_threshold:.1f}, 域内)'),
                })
            if stats.dropped_known and stats.dropped_count > 0:
                _more = (f'（只显示前 {DROPPED_SYMBOLS_DISPLAY_LIMIT} 只）'
                         if stats.dropped_truncated else '')
                alerts.append({
                    'level': 'warning',
                    'type': 'domain_dropped',
                    'message': f'⚠️ 本期掉出可交易域: {stats.dropped_count} 只{_more}',
                })
            if stats.backfill_total >= min_sample and stats.backfill_fail_rate > fail_threshold:
                alerts.append({
                    'level': 'error',
                    'type': 'backfill_failure',
                    'message': (f'❌ 回填失败率过高: {stats.backfill_fail_rate:.1f}% '
                                f'(阈值: {fail_threshold}%, 分母 {stats.backfill_total} 只)'),
                })
            if result.get('backfill_degraded'):
                alerts.append({
                    'level': 'error',
                    'type': 'backfill_degraded',
                    'message': '❌ 回填无任何成功（数据源不可用）→ 数据缺口未收敛',
                })

        if alerts:
            dispatch = _send_quality_alerts(alerts, stats, result['alert_thresholds'])
            if dispatch:
                result['alert_dispatch'] = dispatch
            logger.warning(f"数据质量告警触发: {len(alerts)} 项问题")
        else:
            logger.info("数据质量告警检查通过，无异常")

        return result.get('alert_dispatch')

    except Exception as e:
        # 告警检查本身出错也要响亮（不得让"没有告警"冒充"一切正常"）
        logger.error(f"质量告警检查失败: {e}")
        return None


def _get_notification_facade():
    """获取通知门面（单独抽出，便于测试注入假门面）

    架构铁律（CLAUDE.md 通知架构）：所有外发通知必须走
    application.notification.NotificationFacade，禁止直接调用飞书 SDK/webhook。
    """
    from application.notification import get_notification_facade
    return get_notification_facade()


def _dispatch_alert_to_feishu(title: str, message: str, urgency: str = 'normal') -> bool:
    """把质量告警外发到飞书（经 NotificationFacade）

    2026-09-11 w-23c70356：用户要求质量告警不能只落日志，需真实外发。
    失败只记录、绝不影响任务结果（通知是旁路，不是主线）。
    """
    try:
        facade = _get_notification_facade()
        ok = facade.send_card(title=title, content=message, urgency=urgency)
        if ok:
            logger.info(f"✅ 质量告警已外发飞书（urgency={urgency}）")
        else:
            logger.error("❌ 质量告警外发失败：门面返回 False（渠道未配置或投递被策略拦截）")
        return bool(ok)
    except Exception as e:
        logger.error(f"❌ 质量告警外发异常: {e}")
        return False


def _send_quality_alerts(alerts: list, stats: DomainStats, thresholds: Mapping[str, float]) -> dict:
    """发送质量告警通知（日志 + 飞书外发）。

    正文固定三段：**检查域**（三层计数 + 最后交易日）、**本期掉出可交易域**（名单）、
    **域内指标**（评分 / 覆盖率 / D级，各带阈值）。口径写在正文里，让读数可核验。

    Returns:
        dict: {'alert_count', 'urgency', 'delivered', 'title'}，供调用方写入运行结果，
              让「告警是否真的发出去」在 run 记录里可核验。
    """
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _partial = '（检查被墙钟截断）' if stats.partial else ''
        lines = [
            "📊 数据质量告警",
            f"时间: {timestamp}",
            f"口径: 可交易域（最后交易日 {stats.last_trade_date or '未知'}）"
            f"｜统计 {stats.stats_symbols}/{stats.tradable} 只{_partial}",
            "",
            "检查域:",
            f"  可交易 {stats.tradable} ｜ 观察中 {stats.observing} ｜ 存量 {stats.stock}",
            "",
        ]

        if stats.dropped_known:
            _names = "、".join(stats.dropped_symbols) if stats.dropped_symbols else "（无）"
            _trunc = "…（只显示前 %d）" % DROPPED_SYMBOLS_DISPLAY_LIMIT if stats.dropped_truncated else ""
            lines.extend([
                f"本期掉出可交易域: {stats.dropped_count} 只",
                f"  {_names}{_trunc}",
                "",
            ])
        else:
            lines.extend(["本期掉出可交易域: 不可判（无上期交易日）", ""])

        lines.extend([
            "域内指标:",
            f"  评分 {stats.mean_score:.2f}（阈值 {thresholds.get('score', DEFAULT_SCORE_THRESHOLD)}）",
            f"  平均覆盖率 {stats.mean_coverage:.2f}%"
            f"（信息项，阈值 {thresholds.get('coverage_info', DEFAULT_COVERAGE_INFO_THRESHOLD)}）",
            f"  D级 {stats.d_grade} 只（阈值 {thresholds.get('d_grade', DEFAULT_D_GRADE_THRESHOLD)}）",
            "",
            "问题清单:",
        ])
        for alert in alerts:
            lines.append(f"{alert['message']}")

        if stats.backfill_total:
            _min = thresholds.get('backfill_min_sample', DEFAULT_BACKFILL_MIN_SAMPLE)
            if stats.backfill_total >= _min:
                lines.extend([
                    "",
                    f"回填: 目标 {stats.backfill_total} 只（域内）｜失败 {stats.backfill_failed} 只"
                    f" → 失败率 {stats.backfill_fail_rate:.1f}%",
                ])
            else:
                lines.extend([
                    "",
                    f"回填: 目标 {stats.backfill_total} 只（域内）｜失败 {stats.backfill_failed} 只"
                    f" → 样本 n={stats.backfill_total} < {_min}，不判失败率",
                ])

        message = "\n".join(lines)

        # 2026-09-11 w-23c70356：此处曾以 structlog 风格关键字参数调用 stdlib logger，
        # 实测抛 TypeError 并被外层 except 吞掉 ⇒ 告警内容从未落日志。改标准写法。
        logger.warning(
            "data_quality_alert alert_count=%d score=%.2f\n%s",
            len(alerts),
            stats.mean_score if stats.mean_score == stats.mean_score else 0.0,
            message,
        )

        # 外发飞书：error 级（失败率过高 / 分域不可用 / 缺口未收敛）用 high，其余 normal
        urgency = 'high' if any(a.get('level') in ('error', 'critical') for a in alerts) else 'normal'
        title = f"数据质量告警（{len(alerts)} 项）"
        delivered = _dispatch_alert_to_feishu(title=title, message=message, urgency=urgency)

        return {
            'alert_count': len(alerts),
            'urgency': urgency,
            'delivered': delivered,
            'title': title,
        }

    except Exception as e:
        logger.error(f"发送质量告警失败: {e}")
        return None


# Job注册点 - scheduler会调用这个函数
def execute(**params):
    """Scheduler调用的入口函数"""
    return daily_data_quality_check(**params)


if __name__ == '__main__':
    # 测试执行
    result = daily_data_quality_check(
        check_days=7,
        auto_backfill=False,
        symbols_limit=10
    )
    print(f"\n执行结果: {result}")
