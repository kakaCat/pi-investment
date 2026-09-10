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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Tuple

# 添加项目路径

from application.services.data_quality_service import DataQualityService

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

    quality_threshold = p.get('quality_threshold')
    try:
        quality_threshold = float(quality_threshold) if quality_threshold else 90.0
    except (TypeError, ValueError):
        quality_threshold = 90.0

    effective = {
        'check_days': check_days,
        'symbols_limit': symbols_limit,
        'auto_backfill': bool(p.get('auto_backfill', False)),
        'include_report': bool(p.get('include_report', False)),
        'max_runtime_sec': max_runtime_sec,
        'max_backfill_symbols': max_backfill_symbols,
        'quality_threshold': quality_threshold,
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

            # 提取有问题的股票
            symbols_with_issues = [
                item['symbol']
                for item in quality_result['stocks_with_issues']
                if item['missing_days_count'] > 0
            ]
            # 缺失天数多的优先补：额度有限时花在最有价值的标的上
            issue_rank = {
                item['symbol']: item.get('missing_days_count', 0)
                for item in quality_result['stocks_with_issues']
            }
            symbols_with_issues.sort(key=lambda s: issue_rank.get(s, 0), reverse=True)

            check_elapsed = time.monotonic() - started_monotonic
            remaining = deadline - time.monotonic()
            budget_symbols = max(1, int(remaining // BACKFILL_SEC_PER_SYMBOL))
            limit = min(effective['max_backfill_symbols'], budget_symbols)

            if remaining < MIN_BACKFILL_BUDGET_SEC:
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
            'backfill_degraded': False
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

        # 质量告警检查（阈值来自 params.quality_threshold，配置不再是摆设）
        _check_quality_alerts(result, effective['quality_threshold'])

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


def _get_alert_session():
    """取可用于告警查询的 Session：先回滚挂起事务，异常则丢弃重建"""
    from infrastructure.persistence.orm.config import get_session
    session = get_session()
    try:
        session.rollback()
    except Exception as e:
        logger.warning(f"告警查询前回滚失败，重建会话: {e}")
        try:
            session.close()
        except Exception:
            pass
        session = get_session()
    return session


def _check_quality_alerts(result: Dict[str, Any], quality_threshold: float = 90.0) -> None:
    """检查数据质量并触发告警

    告警条件：
    1. D级股票数量 > 500
    2. 平均质量评分 < quality_threshold（默认 90；可由 task params.quality_threshold 覆盖）
    3. 回填失败率 > 50%
    4. 回填全部失败（backfill_degraded，数据缺口未收敛）
    """
    session = None
    try:
        summary = result.get('check_summary', {})
        quality_score = summary.get('data_quality_score', 100)

        # 计算 D 级股票数量
        from infrastructure.persistence.orm.config import get_session
        from sqlalchemy import text

        session = _get_alert_session()
        _d_grade_sql = text("""
            SELECT COUNT(*)
            FROM kline_data_quality
            WHERE DATE(created_at) = CURRENT_DATE
              AND grade = 'D'
        """)
        try:
            d_grade_count = session.execute(_d_grade_sql).scalar() or 0
        except Exception as q_err:
            # 连接可能已被服务端回收（实测 idle-in-transaction timeout）→ 丢弃重建重试一次
            logger.warning(f"告警查询失败，重建会话重试一次: {q_err}")
            try:
                session.close()
            except Exception:
                pass
            session = get_session()
            d_grade_count = session.execute(_d_grade_sql).scalar() or 0

        # 回填失败率
        backfill_summary = result.get('backfill_summary')
        backfill_fail_rate = 0
        if backfill_summary:
            total = backfill_summary.get('total_stocks', 0)
            failed = backfill_summary.get('failed_count', 0)
            if total > 0:
                backfill_fail_rate = (failed / total) * 100

        # 判断是否需要告警
        alerts = []

        if d_grade_count > 500:
            alerts.append({
                'level': 'warning',
                'type': 'quality_grade',
                'message': f'⚠️ D级股票数量过多: {d_grade_count}只 (阈值: 500)',
            })

        if quality_score < quality_threshold:
            alerts.append({
                'level': 'warning',
                'type': 'quality_score',
                'message': f'⚠️ 数据质量评分偏低: {quality_score:.2f} (阈值: {quality_threshold:.1f})',
            })

        if backfill_fail_rate > 50:
            alerts.append({
                'level': 'error',
                'type': 'backfill_failure',
                'message': f'❌ 回填失败率过高: {backfill_fail_rate:.1f}% (阈值: 50%)',
            })

        if result.get('backfill_degraded'):
            alerts.append({
                'level': 'error',
                'type': 'backfill_degraded',
                'message': '❌ 回填无任何成功（数据源不可用）→ 数据缺口未收敛',
            })

        # 发送告警
        if alerts:
            _send_quality_alerts(alerts, summary, d_grade_count, backfill_fail_rate)
            logger.warning(f"数据质量告警触发: {len(alerts)} 项问题")
        else:
            logger.info("数据质量告警检查通过，无异常")

    except Exception as e:
        # 2026-09-11 w-23c70356：告警检查用共享 session 做 SELECT，一旦 SQL 报错
        # 事务进入 aborted 状态，会连带把调度器的 run 记账（同 session）打成
        # InFailedSqlTransaction —— 这正是 run 3391 最终"失败"的直接原因
        # （launchd-stdout.log 2026-09-04 00:47）。此处显式回滚，切断级联。
        logger.error(f"质量告警检查失败: {e}")
        try:
            if session is not None:
                session.rollback()
        except Exception as rb_err:
            logger.error(f"质量告警检查回滚失败: {rb_err}")


def _send_quality_alerts(alerts: list, summary: dict, d_grade_count: int, backfill_fail_rate: float) -> None:
    """发送质量告警通知"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message_lines = [
            "📊 数据质量告警",
            f"时间: {timestamp}",
            "",
            "问题清单:",
        ]

        for alert in alerts:
            message_lines.append(f"{alert['message']}")

        message_lines.extend([
            "",
            "质量概况:",
            f"总股票数: {summary.get('total_stocks', 0)}",
            f"有问题股票: {summary.get('stocks_with_issues', 0)}",
            f"质量评分: {summary.get('data_quality_score', 0):.2f}",
            f"平均覆盖率: {summary.get('avg_coverage_rate', 0):.2f}%",
            f"D级股票: {d_grade_count}只",
            f"回填失败率: {backfill_fail_rate:.1f}%" if backfill_fail_rate > 0 else "",
        ])

        message = "\n".join([line for line in message_lines if line])

        # 2026-09-11 w-23c70356：此处原以 structlog 风格关键字参数调用 stdlib logger
        # （本模块用 logging.getLogger），实测抛
        # "Logger._log() got an unexpected keyword argument 'alert_count'"
        # 并被外层 except 吞掉 ⇒ 告警内容从未落日志（实证：2026-09-11 00:13 小范围实跑）。
        # 改标准 logging 写法，告警全文进日志。
        # 注：本仓库 infrastructure/ 层无 NotificationFacade 投递先例，告警目前仅落日志，
        # 真正外发渠道待统一设计（已在工作日志记录为后续项）。
        logger.warning(
            "data_quality_alert alert_count=%d score=%.2f\n%s",
            len(alerts),
            summary.get('data_quality_score', 0) or 0,
            message,
        )

    except Exception as e:
        logger.error(f"发送质量告警失败: {e}")


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
