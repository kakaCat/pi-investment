"""
季度财报更新 Job - 利润表（毛利率/营收/净利润）落库

数据源：FinancialDataService provider 链（eastmoney_direct → sina_web → akshare → sina）
落库：quant.income_statements（period_type: 12-31=Y，其余=Q）

调度配置（quant.scheduler_tasks，旧表 scheduler_task_configs 已于 2026-09-11 删除/归档）：
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

    # 读完宇宙立即归还会话（2026-09-13，w-32314d00，事件 a6780ec3）：_resolve_universe() 的
    # 读操作会 autobegin 一个事务，若不清，随后数百次网络抓取（或探活失败早退）期间该事务
    # 一直占着连接——session_guard 实测 job-financial-statements 线程因此被判 session_leak_detected。
    try:
        from infrastructure.persistence.orm import close_session
        close_session()
    except Exception:
        pass

    svc = FinancialDataService()
    repo = FinancialORMRepository()

    # 探活门控（见 _probe_financial_sources 注释）：源整体不可用时快速失败，
    # 不做 N 次无效请求（那样只会刷屏 + 加重源侧限流）。
    if not _probe_financial_sources(svc):
        logger.error(
            "财报数据源探活失败（参考标的 %s 全部取不到报表）——本次放弃，"
            "避免对 %d 只标的做无效请求", list(PROBE_SYMBOLS), len(symbols))
        return {
            'success': False,
            'universe': len(symbols),
            'universe_source': universe_source,
            'probe_failed': True,
            'updated': 0, 'balance_rows': 0, 'elapsed_s': int(time.time() - started),
            'error': f"financial sources probe failed ({', '.join(PROBE_SYMBOLS)})",
        }

    updated, no_data, failed, total_rows = [], [], [], 0
    fail_reason = ''
    balance_updated: List[str] = []
    balance_rows = 0
    for i, symbol in enumerate(symbols, 1):
        try:
            data = svc.get_financial_data(symbol, statement_type='income',
                                          periods=periods)
            records = _map_income_rows(symbol, data.income_statement or [])
            if records:
                n = repo.upsert_income_statements(records)
                total_rows += n
                # 映射出记录但落库 0 行 = 落库失败（2026-09-13 实测：多行 INSERT 键不齐时
                # 整批报错、函数只 return 0）——此前仍计入 updated，属"假成功"计数；
                # 现只有真的写进去才算 updated，否则进 failed 清单。
                (updated if n > 0 else failed).append(symbol)
            else:
                no_data.append(symbol)

            # 资产负债表同批落库（2026-09-13，w-32314d00）：provider 一次调用已带回
            # balance_sheet，此前只因"没有写入通道"而丢弃 → 表停在 2026-03-31，
            # 时效性巡检每天判超期却无人能修。
            balance_records = _map_balance_rows(symbol, getattr(data, 'balance_sheet', None) or [])
            if balance_records:
                nb = repo.upsert_balance_sheets(balance_records)
                balance_rows += nb
                if nb > 0:
                    balance_updated.append(symbol)
        except Exception as e:
            # 逐只失败不再单独打一行（2026-09-13，w-32314d00）：源抖动时会有上百行，
            # 被错误采集器聚成"某只标的抓取失败 263 次"这类噪声事件；改在循环后聚合一条汇总。
            failed.append(symbol)
            if not fail_reason:
                fail_reason = f"{type(e).__name__}: {str(e)[:160]}"

        if i % 50 == 0:
            logger.info(f"进度 {i}/{len(symbols)}: 成功{len(updated)} 无数据{len(no_data)} 失败{len(failed)}")
        time.sleep(random.uniform(RATE_MIN, RATE_MAX))

    elapsed = time.time() - started
    try:      # 收尾同样归还会话（与上方同因，避免任务结束后连接滞留在线程本地注册表）
        from infrastructure.persistence.orm import close_session
        close_session()
    except Exception:
        pass
    if failed:
        logger.warning(
            "财报抓取失败 %d/%d 只（样例 %s）%s",
            len(failed), len(symbols), failed[:8],
            f"；首个原因 {fail_reason}" if fail_reason else '')
    result = {
        # success 口径（2026-09-13，w-32314d00）：利润表或资产负债表任一落库即算成功——
        # 原口径只看利润表，导致"只写了资产负债表"的批次被判 failed（实测 5 只全落在
        # quant.balance_sheets 却报 success=False）。
        'success': (len(updated) > 0) or (len(balance_updated) > 0),
        'universe': len(symbols),
        'universe_source': universe_source,
        'updated': len(updated),
        'no_data': len(no_data),
        'failed': len(failed),
        'rows': total_rows,
        'balance_rows': balance_rows,
        'balance_updated': len(balance_updated),
        'elapsed_s': int(elapsed),
        # 显式可见：失败/无数据清单（截断防日志爆炸）
        'failed_symbols': failed[:20],
        'no_data_symbols': no_data[:20],
    }
    logger.info(f"季度财报更新完成: {result}")
    return result


# provider 键口径不一（2026-09-13，w-32314d00 实测）：
#   · eastmoney_direct / tushare 等返回**英文键**：revenue / total_revenue / total_cost / net_profit …
#   · sina_web / akshare-financial 返回**中文键**：营业总收入 / 营业收入 / 营业成本 / 净利润 / 报告日 …
# 原实现只读英文键 → 中文键的行在第一道 row.get('report_date') 就被丢弃，
# 那些标的被记成 no_data（实测 5 只样本全部 no_data，而 provider 明明返回了 100+ 期数据）。
INCOME_KEY_ALIASES: Dict[str, tuple] = {
    'report_date': ('report_date', '报告日', '报告期'),
    'revenue': ('revenue', 'total_revenue', '营业总收入', '营业收入'),
    'operating_revenue': ('operating_revenue', '营业收入'),
    'total_cost': ('operating_cost', 'total_cost', '营业成本', '营业总成本'),
    'gross_margin': ('gross_margin', '销售毛利率', '毛利率'),
    'operating_profit': ('operating_profit', '营业利润'),
    'total_profit': ('total_profit', '利润总额'),
    'net_profit': ('net_profit', '净利润'),
    'net_profit_parent': ('parent_net_profit', 'net_profit_parent',
                          '归属于母公司所有者的净利润', '归属于母公司股东的净利润'),
    'eps': ('basic_eps', 'eps', '基本每股收益'),
    'eps_diluted': ('eps_diluted', '稀释每股收益'),
}


def _pick(row: Dict, field: str) -> Optional[float]:
    """按别名优先级取值（英文键与中文键统一，None 跳过）。"""
    for key in INCOME_KEY_ALIASES.get(field, (field,)):
        v = _f(row.get(key))
        if v is not None:
            return v
    return None


# 财报源探活参考标的（大盘蓝筹，数据源覆盖稳定；与 kline 任务的 _probe_kline_sources 同款门控思路）
PROBE_SYMBOLS = ('600519', '000001')


def _probe_financial_sources(svc) -> bool:
    """财报数据源探活：任一参考标的能取到报表即判"源可用"。

    2026-09-13（w-32314d00，错误事件 d9adc934）：2026-09-12 20:03 ~ 09-13 00:28 数据源全面
    不可用期间，本 job 仍对 367 只标的逐个硬试 —— 最终 186 只失败、263 条失败日志，
    在 error_events 里聚成一条 263 次的"财报抓取失败"事件；既拿不到数据，也会加重源侧限流/WAF。
    kline 同步任务早有同款探活门控（_probe_kline_sources，2026-09-02 WAF 封禁教训），本 job 补齐。
    """
    for sym in PROBE_SYMBOLS:
        try:
            data = svc.get_financial_data(sym, statement_type='income', periods=2)
            if getattr(data, 'income_statement', None) or getattr(data, 'balance_sheet', None):
                return True
        except Exception as e:  # noqa: BLE001 探活失败继续试下一个参考标的
            logger.warning(f"财报源探活失败 {sym}: {type(e).__name__}: {str(e)[:120]}")
    return False


def _map_income_rows(symbol: str, rows: List[Dict]) -> List[Dict[str, Any]]:
    """provider 利润表行 → income_statements 记录（英文键/中文键双兼容）

    period_type: report_date 为 12-31 → Y，其余 → Q
    net_profit 为空时回退 parent_net_profit

    毛利率口径（诚实声明）：provider 直接给 gross_margin 时用它；
    否则**仅在营业收入与营业成本都存在**时按 (营业收入-营业成本)/营业收入×100 推导
    （不与营业总收入混算，避免口径串味）；两者缺一即留 NULL，不猜。
    """
    out = []
    for row in rows:
        rd = row.get('report_date') or row.get('报告日') or row.get('报告期')
        if not rd:
            continue
        rd = str(rd).strip()
        if len(rd) == 8 and rd.isdigit():
            rd = f"{rd[:4]}-{rd[4:6]}-{rd[6:8]}"
        rd = rd[:10]
        revenue = _pick(row, 'revenue')
        gross_margin = _pick(row, 'gross_margin')
        if revenue is None and gross_margin is None:
            continue
        operating_revenue = _pick(row, 'operating_revenue')
        total_cost = _pick(row, 'total_cost')
        # 毛利 = 收入 - 成本，收入口径优先用营业收入，缺失时回退到营收总额
        #（英文键 provider 只给 total_revenue，旧行为即 revenue - total_cost，
        #  不能因为"中文键更讲究口径"就把它改坏——tests/services/scoring/
        #  test_financial_statement_job.py 明确锁了这条契约）。
        gross_basis = operating_revenue if operating_revenue is not None else revenue
        gross_profit = None
        if gross_basis is not None and total_cost is not None:
            gross_profit = gross_basis - total_cost
            if gross_margin is None and gross_basis:
                gross_margin = round(gross_profit / gross_basis * 100, 4)
        period_type = 'Y' if rd[5:7] == '12' else 'Q'
        out.append({
            'symbol': symbol,
            'report_date': rd,
            'period_type': period_type,
            'revenue': revenue,
            'operating_revenue': operating_revenue,
            'operating_cost': total_cost,
            'gross_profit': gross_profit,
            'gross_margin': gross_margin,
            'operating_profit': _pick(row, 'operating_profit'),
            'total_profit': _pick(row, 'total_profit'),
            'net_profit': _pick(row, 'net_profit') or _pick(row, 'net_profit_parent'),
            'net_profit_parent': _pick(row, 'net_profit_parent'),
            'eps': _pick(row, 'eps'),
            'eps_diluted': _pick(row, 'eps_diluted'),
        })
    return out


def _map_balance_rows(symbol: str, rows: List[Dict]) -> List[Dict[str, Any]]:
    """provider 资产负债表行 → balance_sheets 记录（2026-09-13，w-32314d00）

    背景：quant.balance_sheets 此前**没有任何写入通道**（最新停在 2026-03-31），
    而财报时效性巡检/数据契约以它为口径 → 每个交易日 09:00 判"财报超期"却修不了。
    与利润表共用同一次 provider 调用（adapter 一次返回 income+balance+cashflow），
    故在此把资产负债表一并落库。

    口径（诚实声明）：
    - 只落 provider 真实给出的金额；**不计算** debt_ratio / current_ratio
      （单位口径未统一，宁缺勿猜——留 NULL）。
    - 报告日 '20260630' → '2026-06-30'；12 月 → period_type='Y'，其余 'Q'。
    - 关键金额全空的行直接丢弃（不写空壳行）。
    """
    out = []
    for row in rows or []:
        rd = row.get('报告日') or row.get('report_date')
        if not rd:
            continue
        rd = str(rd).strip()
        if len(rd) == 8 and rd.isdigit():
            rd = f"{rd[:4]}-{rd[4:6]}-{rd[6:8]}"
        rd = rd[:10]

        def _num(*keys):
            for k in keys:
                v = _f(row.get(k))
                if v is not None:
                    return v
            return None

        total_assets = _num('资产总计')
        total_liabilities = _num('负债合计')
        total_equity = _num('所有者权益(或股东权益)合计', '所有者权益')
        current_assets = _num('流动资产合计', '流动资产')
        current_liabilities = _num('流动负债合计', '流动负债')
        non_current_assets = _num('非流动资产合计', '非流动资产')
        non_current_liabilities = _num('非流动负债合计', '非流动负债')
        parent_equity = _num('归属于母公司股东权益合计')

        if all(v is None for v in (total_assets, total_liabilities, total_equity,
                                   current_assets, current_liabilities)):
            continue

        out.append({
            'symbol': symbol,
            'report_date': rd,
            'period_type': 'Y' if rd[5:7] == '12' else 'Q',
            'total_assets': total_assets,
            'current_assets': current_assets,
            'non_current_assets': non_current_assets,
            'total_liabilities': total_liabilities,
            'current_liabilities': current_liabilities,
            'non_current_liabilities': non_current_liabilities,
            'total_equity': total_equity,
            'parent_equity': parent_equity,
            'source': 'provider:financial_statements',
        })
    return out


def _normalize_symbol(symbol: str) -> str:
    """去掉交易所后缀（000300.SH → 000300）。

    2026-09-13（w-32314d00）：扫描宇宙里的沪深300成分来自 index_constituents，
    其中 24/367 带后缀（000999.SZ、688981.SH …）——这类代码
    ①provider 取不到数、②落库时撞 FK（income_statements.symbol → stocks.symbol 是裸码）
    必然失败，是"宇宙内 32 只完全没有利润表"的原因之一。
    """
    s = str(symbol or '').strip()
    return s.split('.')[0] if '.' in s else s


def _dedup_universe(symbols: List[str]) -> List[str]:
    """去重保序（并统一为裸 6 位码）"""
    seen, out = set(), []
    for raw in symbols:
        s = _normalize_symbol(raw)
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
    logger.info(result)
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
