"""
季度财报更新 Job - 利润表（毛利率/营收/净利润）落库

数据源：FinancialDataService provider 链（eastmoney_direct → sina_web → akshare → sina）
落库：quant.income_statements（period_type: 12-31=Y，其余=Q）

调度配置（quant.scheduler_task_configs）：
    task_name: financial_statement_update
    command:   infrastructure.jobs.financial_statement_update_job.execute
    cron:      0 20 * * 6（每周六 20:00）

手动执行：
    python -m infrastructure.jobs.financial_statement_update_job
    python -m infrastructure.jobs.financial_statement_update_job --symbols 600519 601899

背景：2026-07-30 动态评分系统上线后发现 income_statements 仅剩历史遗产
（沪深300×3季度，写入方 UpdateFinancialDataJob 已被删除），profile 分类全部
退化 balanced。本 job 重建财报数据链路。
"""
import os
import sys
import time
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

project_root = Path(__file__).parent.parent.parent

logger = logging.getLogger(__name__)

# 限速：uniform(0.3, 0.8)s（与 kline 反封禁策略一致，见 kline-anti-ban-architecture）
RATE_MIN, RATE_MAX = 0.3, 0.8
DEFAULT_PERIODS = 8
INDEX_CSI300 = '000300.SH'


def execute(**params) -> Dict[str, Any]:
    """
    抓取扫描宇宙的季度利润表并落库

    Args:
        **params:
            - symbols: 指定股票列表（默认：池成员+watchlist+沪深300）
            - periods: 每只股票抓取期数（默认 8）

    Returns:
        dict: {success, universe, updated, no_data, failed, rows, elapsed_s}
    """
    from application.services.financial_data_service_adapter import FinancialDataServiceAdapter as FinancialDataService
    from adapters.outbound.repositories.financial_repository import FinancialORMRepository

    started = time.time()
    periods = int(params.get('periods', DEFAULT_PERIODS))
    symbols = params.get('symbols')
    if symbols:
        symbols = _dedup_universe(list(symbols))
        universe_source = 'explicit'
    else:
        symbols = _resolve_universe()
        universe_source = 'pools+watchlist+csi300'

    logger.info("=" * 70)
    logger.info(f"季度财报更新任务开始 (universe={len(symbols)}, source={universe_source}, periods={periods})")
    logger.info("=" * 70)

    if not symbols:
        logger.error("扫描宇宙为空，任务失败（不静默成功）")
        return {'success': False, 'universe': 0, 'updated': 0,
                'error': 'empty universe'}

    svc = FinancialDataService()
    repo = FinancialORMRepository()

    updated, no_data, failed, total_rows = [], [], [], 0
    for i, symbol in enumerate(symbols, 1):
        try:
            data = svc.get_financial_data(symbol, statement_type='income',
                                          periods=periods)
            records = _map_income_rows(symbol, data.income_statement or [])
            if records:
                n = repo.upsert_income_statements(records)
                total_rows += n
                updated.append(symbol)
            else:
                no_data.append(symbol)
        except Exception as e:
            logger.warning(f"{symbol}: 财报抓取失败 - {type(e).__name__}: {e}")
            failed.append(symbol)

        if i % 50 == 0:
            logger.info(f"进度 {i}/{len(symbols)}: 成功{len(updated)} 无数据{len(no_data)} 失败{len(failed)}")
        time.sleep(random.uniform(RATE_MIN, RATE_MAX))

    elapsed = time.time() - started
    result = {
        'success': len(updated) > 0,
        'universe': len(symbols),
        'universe_source': universe_source,
        'updated': len(updated),
        'no_data': len(no_data),
        'failed': len(failed),
        'rows': total_rows,
        'elapsed_s': int(elapsed),
        # 显式可见：失败/无数据清单（截断防日志爆炸）
        'failed_symbols': failed[:20],
        'no_data_symbols': no_data[:20],
    }
    logger.info(f"季度财报更新完成: {result}")
    return result


def _map_income_rows(symbol: str, rows: List[Dict]) -> List[Dict[str, Any]]:
    """provider 利润表行 → income_statements 记录

    period_type: report_date 为 12-31 → 'Y'，其余 → 'Q'
    net_profit 为空时回退 parent_net_profit
    """
    out = []
    for row in rows:
        rd = row.get('report_date')
        if not rd:
            continue
        rd = str(rd)[:10]
        revenue = _f(row.get('revenue')) or _f(row.get('total_revenue'))
        gross_margin = _f(row.get('gross_margin'))
        if revenue is None and gross_margin is None:
            continue
        total_cost = _f(row.get('total_cost'))
        period_type = 'Y' if rd[5:7] == '12' else 'Q'
        out.append({
            'symbol': symbol,
            'report_date': rd,
            'period_type': period_type,
            'revenue': revenue,
            'operating_cost': total_cost,
            'gross_profit': (revenue - total_cost
                             if revenue is not None and total_cost is not None
                             else None),
            'gross_margin': gross_margin,
            'operating_profit': _f(row.get('operating_profit')),
            'total_profit': _f(row.get('total_profit')),
            'net_profit': _f(row.get('net_profit')) or _f(row.get('parent_net_profit')),
            'net_profit_parent': _f(row.get('parent_net_profit')),
            'eps': _f(row.get('basic_eps')),
        })
    return out


def _dedup_universe(symbols: List[str]) -> List[str]:
    """去重保序"""
    seen, out = set(), []
    for s in symbols:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _resolve_universe() -> List[str]:
    """扫描宇宙：股票池成员 + watchlist + 沪深300 成分"""
    symbols: List[str] = []

    # 1. 股票池成员
    try:
        from adapters.outbound.repositories import StockPoolORMRepository
        pool_repo = StockPoolORMRepository()
        for pool in pool_repo.get_all():
            symbols.extend(pool.get('symbols') or [])
    except Exception as e:
        logger.warning(f"股票池成员获取失败: {e}")

    # 2. watchlist（直接读文件，避免 import Flask shared）
    try:
        import json
        watchlist_file = project_root / '.pi-invest' / 'watchlist.json'
        if watchlist_file.exists():
            data = json.loads(watchlist_file.read_text(encoding='utf-8'))
            items = data if isinstance(data, list) else data.get('items', [])
            symbols.extend(item.get('symbol') for item in items if item.get('symbol'))
    except Exception as e:
        logger.warning(f"watchlist 读取失败: {e}")

    # 3. 沪深300 成分
    try:
        from adapters.outbound.repositories import StockORMRepository
        stock_repo = StockORMRepository()
        symbols.extend(stock_repo.get_index_constituents([INDEX_CSI300]) or [])
    except Exception as e:
        logger.warning(f"沪深300 成分获取失败: {e}")

    return _dedup_universe(symbols)


def _f(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(description='季度财报更新')
    parser.add_argument('--symbols', nargs='*', default=None,
                        help='指定股票列表（默认：池成员+watchlist+沪深300）')
    parser.add_argument('--periods', type=int, default=DEFAULT_PERIODS)
    args = parser.parse_args()

    result = execute(symbols=args.symbols, periods=args.periods)
    print(result)
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
