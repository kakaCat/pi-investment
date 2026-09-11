"""
资金流数据更新Job - 全市场资金流向每日采集

数据源：东方财富 push2 clist 全市场分页扫描（约 60 页请求覆盖全部 A 股）
落库：quant.stock_fund_flow（单位：万元）

调度配置（quant.scheduler_tasks，旧表 scheduler_task_configs 已于 2026-09-11 删除/归档）：
    task_name: fund_flow_update
    command:   infrastructure.jobs.fund_flow_update_job.execute
    cron:      30 15 * * 1-5（交易日收盘后）

也可手动执行：
    python -m infrastructure.jobs.fund_flow_update_job [--date 2026-07-28]
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# 添加项目路径

logger = logging.getLogger(__name__)

# ── 快照一致性闸门的参数 ──────────────────────────────────────────────
_SANITY_SAMPLE_SIZE = 40        # 抽样只数（全市场 ~5000 只，抽样足够发现整批错位）
_SANITY_MAX_MISMATCH = 0.30     # 抽样中收盘价不一致的比例上限
_SANITY_TOLERANCE_PCT = 0.5     # 单只收盘价允许偏差（%）——给复权/四舍五入留余量


def _load_reference_closes(symbols: List[str], trade_date: str) -> Dict[str, float]:
    """权威 K 线该交易日收盘价（quant.daily_klines）。取不到返回空 dict。"""
    if not symbols:
        return {}
    try:
        from sqlalchemy import text

        from infrastructure.persistence.database.engine import get_engine
        with get_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT symbol, close FROM quant.daily_klines
                WHERE trade_date = :d AND symbol = ANY(:syms) AND close IS NOT NULL
            """), {'d': trade_date, 'syms': list(symbols)}).fetchall()
        return {str(r[0]): float(r[1]) for r in rows}
    except Exception as exc:      # 参照系取不到不阻断主流程，由 detail 如实暴露
        logger.warning(f"取 K 线参照价失败（本次跳过一致性校验）: {exc}")
        return {}


def _snapshot_matches_reference(
    records: List[Dict],
    trade_date: str,
    close_lookup: Optional[Callable[[List[str], str], Dict[str, float]]] = None,
) -> Tuple[bool, str, Dict]:
    """批次级一致性闸门：抽样比对「快照收盘价」与「权威 K 线该交易日收盘」。

    为什么必须做（2026-09-11 实测事故，w-f436d4ea）：本 job 的 trade_date 来自**墙钟**
    （params['date'] 或 datetime.now()），而快照来自「发起请求那一刻」，两者可能不是
    同一天。历史上已发生两种污染，都写进了 quant.stock_fund_flow：
      · 手动回补 --date 2026-09-10 在 09-11 **盘中**运行（updated_at 12:52:33）→
        抓到盘中价 41.82 / −3.77% 记成 09-10 收盘，而 09-10 真值 43.46 / +1.85%
        （差 3.9%）——下游做「资金流 vs 涨跌」对齐会得出错误结论；
      · **非交易日**运行 → 上游返回上一交易日陈旧快照并被记成当天（实测 09-05 周六
        整行复制 09-04）。
    非交易日由 TradingDayGuard 先拦掉；本函数拦「是交易日，但快照不属于该日」。

    取不到参照 K 线时**不拦**（无法证伪 ≠ 有问题），但把情况写进 detail 供排查——
    与「空结果 ≠ 故障」同一口径。

    Returns:
        (ok, reason, detail)
    """
    sampled = [r for r in records if r.get('close_price') not in (None, '')][:_SANITY_SAMPLE_SIZE]
    if not sampled:
        return True, '', {'checked': 0, 'note': '无可用收盘价，跳过校验'}
    lookup = close_lookup or _load_reference_closes
    refs = lookup([str(r['symbol']) for r in sampled], trade_date)
    if not refs:
        return True, '', {'checked': 0,
                          'note': f'{trade_date} 取不到权威 K 线（该日 K 线未落库？）——未做一致性校验'}
    mismatch, examples = 0, []
    for r in sampled:
        ref = refs.get(str(r['symbol']))
        if ref in (None, 0):
            continue
        actual = float(r['close_price'])
        if abs(actual - ref) / abs(ref) * 100 > _SANITY_TOLERANCE_PCT:
            mismatch += 1
            if len(examples) < 3:
                examples.append({'symbol': str(r['symbol']), 'snapshot': actual, 'kline': ref})
    checked = sum(1 for r in sampled if refs.get(str(r['symbol'])) not in (None, 0))
    if checked == 0:
        return True, '', {'checked': 0, 'note': '抽样标的均无参照 K 线，跳过校验'}
    ratio = mismatch / checked
    detail = {'checked': checked, 'mismatch': mismatch, 'ratio': round(ratio, 4),
              'examples': examples, 'trade_date': trade_date}
    if ratio > _SANITY_MAX_MISMATCH:
        return False, (
            f'快照与 {trade_date} 权威 K 线不一致（{mismatch}/{checked} 只超 {_SANITY_TOLERANCE_PCT}% 容差，'
            f'例: {examples}）——该快照不属于 {trade_date}（疑似盘中运行或上游未更新），拒绝落库'
        ), detail
    return True, '', detail


def execute(**params):
    """
    采集全市场资金流向并落库

    Args:
        **params:
            - date: 交易日期 YYYY-MM-DD（默认今天）

    Returns:
        dict: 执行结果
    """
    from adapters.outbound.datasources.fund_flow_source import (
        EastMoneyFundFlowSource, SinaFundFlowSource,
    )
    from adapters.outbound.repositories import FundFlowORMRepository

    trade_date = params.get('date') or datetime.now().strftime('%Y-%m-%d')

    # 闸门①：非交易日一律不落库。
    # 快照来自「发请求那一刻」，非交易日运行时上游返回的是上一交易日的陈旧快照，
    # 若按当天记就是**凭空造出一行交易数据**（实测 2026-09-05 周六整行复制 09-04）。
    from application.services.trading_day_guard import TradingDayGuard
    if not TradingDayGuard.is_trading_day(trade_date):
        logger.warning(f"跳过：{trade_date} 非交易日，不落库")
        return {'success': False, 'skipped': True, 'reason': 'non_trading_day',
                'trade_date': trade_date, 'records': 0,
                'error': f'{trade_date} 非交易日——跳过落库（避免把上一交易日的陈旧快照记成该日）'}

    logger.info("=" * 70)
    logger.info(f"资金流数据更新任务开始 (trade_date={trade_date})")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    # 主源东财（4 档细分），被封时降级新浪（仅主力/小单两档）。
    # 东财 WAF 自 2026-07-22 起对本机房 IP 有长时间封锁记录。
    records = []
    used_source = None
    errors = []
    for source in (EastMoneyFundFlowSource(), SinaFundFlowSource()):
        try:
            logger.info(f"尝试数据源: {source.name}")
            records = source.fetch_market_wide_flow()
            if records:
                used_source = source.name
                break
            errors.append(f"{source.name}: 返回 0 条")
        except Exception as e:
            errors.append(f"{source.name}: {type(e).__name__} {str(e)[:100]}")
            logger.warning(f"数据源 {source.name} 失败: {e}")

    if not records:
        # 显式失败：非交易日/数据源全挂时不写库、不静默成功
        logger.error(f"全市场资金流采集失败: {'; '.join(errors)}")
        return {'success': False, 'trade_date': trade_date, 'records': 0,
                'error': '; '.join(errors)}

    # 闸门②：快照必须真的属于 trade_date（抽样比对权威 K 线收盘）。
    # 拦的是「是交易日，但这份快照不是这天的」——例如手动回补历史日期却在实际
    # 盘中/次日运行，抓到的是当时的实时价。
    ok, reason, sanity = _snapshot_matches_reference(records, trade_date)
    if not ok:
        logger.error(f"拒绝落库: {reason}")
        return {'success': False, 'skipped': True, 'reason': 'snapshot_mismatch',
                'trade_date': trade_date, 'records': 0, 'error': reason, 'sanity': sanity}
    logger.info(f"一致性闸门通过: {sanity}")

    for r in records:
        r['trade_date'] = trade_date

    repo = FundFlowORMRepository()
    count = repo.batch_upsert(records)

    logger.info(f"✅ 资金流数据落库完成: {count}/{len(records)} 条 "
                f"(trade_date={trade_date}, source={used_source})")
    return {'success': count > 0, 'trade_date': trade_date,
            'records': count, 'source': used_source, 'sanity': sanity}


if __name__ == '__main__':
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    parser = argparse.ArgumentParser(description='全市场资金流向采集')
    parser.add_argument('--date', help='交易日期 YYYY-MM-DD（默认今天）')
    args = parser.parse_args()

    result = execute(**({'date': args.date} if args.date else {}))
    sys.exit(0 if result.get('success') else 1)
