"""资金流助手（框架无关）— 从 adapters/inbound/api/routes/jobs.py 解耦而来

2026-09-11（REQ-cf627b，w-f436d4ea）根治三个 latent bug（Flask 时代 parity 保留）：
① _inject_fund_flow_to_klines 调用的 get_stock_fund_flow 从未定义（NameError 被
   try/except 吞掉 → 资金流列静默全 0 → 因子表 10 个资金因子恒 0）
② _fetch_financial_data 用的 ds 从未定义（NameError → 财务因子静默 None）
③ 本模块缺 logger（异常处理路径里的 logger.warning 会二次崩溃）
现改为：资金流走 FundFlowDataSource（DB 缓存优先，每日批量 job 以万元写入）；
财务数据走 adapters.shared.services.get_data_service()；补 structlog logger。
"""
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


# -- 资金流注入辅助函数 --
_FUND_FLOW_COLUMN_MAP = {
    '主力净流入-净额': 'main_net_inflow',
    '主力净流入-净占比': 'main_net_pct',
    '超大单净流入-净额': 'super_large_net',
    '大单净流入-净额': 'large_net',
    '超大单净流入-净占比': 'super_large_pct',
    '大单净流入-净占比': 'large_pct',
}


def _inject_fund_flow_to_klines(klines: List[dict], symbol: str) -> List[dict]:
    """
    将主力资金流向数据合并到 klines 列表中。
    如果获取失败，所有资金流列填充 0。
    """
    # 初始化所有资金流列为 0
    for k in klines:
        for alias in _FUND_FLOW_COLUMN_MAP.values():
            k[alias] = 0.0

    try:
        from adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
        days = len(klines)
        fund_data = FundFlowDataSource().get_stock_fund_flow(symbol, days=days)

        if not fund_data or not isinstance(fund_data, dict):
            return klines

        fund_rows = fund_data.get('data', [])
        if not fund_rows:
            return klines

        # 行键兼容：FundFlowDataSource 为 snake_case（单位=万元），akshare 原始为中文列名
        def _g(row: dict, *names):
            for n in names:
                v = row.get(n)
                if v is not None:
                    return v
            return None

        # 建立 日期→资金流 映射
        fund_by_date: Dict[str, dict] = {}
        for row in fund_rows:
            d = _g(row, 'date', 'trade_date', '日期')
            if d:
                fund_by_date[str(d).replace('-', '')] = row

        # FundFlowDataSource 字段口径（万元）：
        #   large_net_inflow = 超大单净流入；big_net_inflow = 大单净流入
        _KEY_MAP = {
            'main_net_inflow': ('main_net_inflow', '主力净流入-净额'),
            'main_net_pct': ('main_net_inflow_rate', '主力净流入-净占比'),
            'super_large_net': ('large_net_inflow', '超大单净流入-净额'),
            'super_large_pct': ('large_net_inflow_rate', '超大单净流入-净占比'),
            'large_net': ('big_net_inflow', '大单净流入-净额'),
            'large_pct': ('big_net_inflow_rate', '大单净流入-净占比'),
        }

        # 按日期合并
        merged = 0
        for k in klines:
            kdate = str(k.get('trade_date', k.get('date', ''))).replace('-', '')
            frow = fund_by_date.get(kdate)
            if not frow:
                continue
            merged += 1
            for alias, names in _KEY_MAP.items():
                val = _g(frow, *names)
                if val is not None:
                    try:
                        k[alias] = float(val)
                    except (ValueError, TypeError):
                        pass
        if merged == 0:
            logger.warning(f'{symbol} 资金流注入 0 条命中（日期对不上），资金流列保持 0')
    except Exception as e:
        # 数据源不可用时降级，但不再静默吞掉——至少留日志可追
        logger.warning(f'{symbol} 资金流注入失败（资金流列保持 0）: {e}')

    return klines


def _extract_fund_flow_factors(klines: List[dict]) -> dict:
    """
    从合并后的 klines 最后一条提取主力资金流因子。
    返回可合并到 factors 字典的键值对。
    """
    if not klines:
        return {}

    last = klines[-1]

    # 最近 3/5 日主力净流入累计
    inflow_sum_3d = 0.0
    inflow_sum_5d = 0.0
    for k in klines[-3:]:
        inflow_sum_3d += float(k.get('main_net_inflow', 0) or 0)
    for k in klines[-5:]:
        inflow_sum_5d += float(k.get('main_net_inflow', 0) or 0)

    # 最近 N 日主力净流入为正的天数
    pos_days_3 = sum(1 for k in klines[-3:] if float(k.get('main_net_inflow', 0) or 0) > 0)
    pos_days_5 = sum(1 for k in klines[-5:] if float(k.get('main_net_inflow', 0) or 0) > 0)

    return {
        # 最新一日
        'main_net_inflow': float(last.get('main_net_inflow', 0) or 0),
        'main_net_pct': float(last.get('main_net_pct', 0) or 0),
        'super_large_net': float(last.get('super_large_net', 0) or 0),
        'large_net': float(last.get('large_net', 0) or 0),
        'super_large_pct': float(last.get('super_large_pct', 0) or 0),
        'large_pct': float(last.get('large_pct', 0) or 0),
        # 趋势因子
        'fund_inflow_3d_sum': inflow_sum_3d,
        'fund_inflow_5d_sum': inflow_sum_5d,
        'fund_inflow_pos_days_3': pos_days_3,
        'fund_inflow_pos_days_5': pos_days_5,
    }




def _fetch_financial_data(symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取财务数据用于基本面因子计算。

    使用 ds.get_financial_statements 获取原始财报数据（Sina 格式），
    解析出 FSCORE 和盈利质量计算所需的指标。

    返回 current 和 previous 两期数据，用于同比比较。
    至少需要 2 期数据；不足则返回 None。
    """
    try:
        from adapters.shared.services import get_data_service
        raw = get_data_service().get_financial_statements(symbol, statement_type='all', periods=8)
    except Exception as e:
        logger.warning(f"Failed to fetch financial statements for {symbol}: {e}")
        return None

    if not raw or 'error' in raw:
        logger.warning(f"No financial data for {symbol}: {raw.get('error', 'unknown') if isinstance(raw, dict) else 'empty'}")
        return None

    income_records = raw.get('income_statement', [])
    balance_records = raw.get('balance_sheet', [])
    cashflow_records = raw.get('cash_flow', [])

    if not income_records or not balance_records:
        logger.warning(f"Incomplete financial data for {symbol}: income={bool(income_records)}, balance={bool(balance_records)}")
        return None

    # Parse records into simplified metric dicts
    try:
        periods_data = _parse_financial_periods(income_records, balance_records, cashflow_records)
    except Exception as e:
        logger.warning(f"Failed to parse financial periods for {symbol}: {e}")
        return None
    if len(periods_data) < 2:
        logger.warning(f"Insufficient financial periods for {symbol}: {len(periods_data)}")
        return None

    current = periods_data[0]
    previous = periods_data[1]

    def _v(d: dict, key: str) -> Optional[float]:
        return d.get(key)

    return {
        'current': {
            'roa':             _v(current, 'roa'),
            'operating_cf':    _v(current, 'operating_cf'),
            'net_income':      _v(current, 'net_income'),
            'long_term_debt':  _v(current, 'long_term_debt'),
            'total_assets':    _v(current, 'total_assets'),
            'current_ratio':   _v(current, 'current_ratio'),
            'total_shares':    _v(current, 'total_shares'),
            'gross_margin':    _v(current, 'gross_margin'),
            'revenue':         _v(current, 'revenue'),
            'total_liabilities': _v(current, 'total_liabilities'),
            'roe':             _v(current, 'roe'),
        },
        'previous': {
            'roa':             _v(previous, 'roa'),
            'long_term_debt':  _v(previous, 'long_term_debt'),
            'total_assets':    _v(previous, 'total_assets'),
            'current_ratio':   _v(previous, 'current_ratio'),
            'total_shares':    _v(previous, 'total_shares'),
            'gross_margin':    _v(previous, 'gross_margin'),
            'revenue':         _v(previous, 'revenue'),
        }
    }


def _parse_financial_periods(
    income_records: List[dict],
    balance_records: List[dict],
    cashflow_records: List[dict],
) -> List[dict]:
    """
    Parse raw Sina financial report records into simplified metric dicts.
    Returns list of period dicts sorted by report date (most recent first).

    Each period dict contains:
        roa, operating_cf, net_income, long_term_debt, total_assets,
        current_ratio, total_shares, gross_margin, revenue,
        total_liabilities, roe
    """
    # Merge income + balance + cashflow by report date
    periods: Dict[str, dict] = {}  # report_date -> merged dict

    for rec in income_records:
        if isinstance(rec, dict) and 'error' not in rec:
            date = _report_date(rec)
            if date:
                periods.setdefault(date, {})['report_date'] = date

                # Income statement fields
                revenue = _pick_num(rec, ['营业总收入', '营业收入'])
                cost   = _pick_num(rec, ['营业成本'])  # COGS for gross margin, NOT 营业总成本 (total costs)
                net_income = _pick_num(rec, ['净利润'])

                if date in periods:
                    p = periods[date]
                    p['revenue']    = revenue
                    p['net_income'] = net_income
                    if revenue and cost and revenue != 0:
                        p['gross_margin'] = (revenue - cost) / revenue

    for rec in balance_records:
        if isinstance(rec, dict) and 'error' not in rec:
            date = _report_date(rec)
            if date:
                periods.setdefault(date, {})['report_date'] = date

                total_assets      = _pick_num(rec, ['资产总计', '总资产'])
                total_liabilities  = _pick_num(rec, ['负债合计', '总负债'])
                current_assets    = _pick_num(rec, ['流动资产合计'])
                current_liab      = _pick_num(rec, ['流动负债合计'])
                noncurrent_liab   = _pick_num(rec, ['非流动负债合计'])
                total_equity      = _pick_num(rec, ['所有者权益(或股东权益)合计', '所有者权益合计', '股东权益合计', '归属于母公司股东权益合计'])

                p = periods[date]
                p['total_assets']      = total_assets
                p['total_liabilities']  = total_liabilities
                p['long_term_debt']    = noncurrent_liab  # proxy
                if current_assets and current_liab and current_liab != 0:
                    p['current_ratio'] = current_assets / current_liab
                if net_income := p.get('net_income'):
                    if total_assets and total_assets != 0:
                        p['roa'] = net_income / total_assets
                    if total_equity and total_equity != 0:
                        p['roe'] = net_income / total_equity

    for rec in cashflow_records:
        if isinstance(rec, dict) and 'error' not in rec:
            date = _report_date(rec)
            if date and date in periods:
                op_cf = _pick_num(rec, ['经营活动产生的现金流量净额', '经营活动现金流量净额'])
                periods[date]['operating_cf'] = op_cf

    # Sort by date descending, filter incomplete periods, return as list
    result = []
    for date in sorted(periods.keys(), reverse=True):
        p = periods[date]
        # Need at minimum: roa, operating_cf, net_income, long_term_debt, total_assets,
        #   current_ratio, gross_margin, revenue, total_liabilities, roe
        required = ['roa', 'operating_cf', 'net_income', 'long_term_debt',
                     'total_assets', 'current_ratio', 'gross_margin', 'revenue',
                     'total_liabilities', 'roe']
        if all(p.get(k) is not None for k in required):
            # total_shares: use a placeholder (we can't easily get from Sina)
            # The FSCORE criterion will default to 0 if shares == 0
            if 'total_shares' not in p:
                p['total_shares'] = 0  # placeholder
            result.append(p)

    return result


def _report_date(rec: dict) -> Optional[str]:
    """Extract report date from a Sina financial record."""
    for col in ('报告日', '报表日', '截止日期', 'date', '报告期'):
        val = rec.get(col)
        if val is not None:
            s = str(val)[:10]
            return s
    return None


def _pick_num(rec: dict, candidates: List[str]) -> Optional[float]:
    """Pick the first non-None numeric value from a list of candidate column names."""
    for col in candidates:
        val = rec.get(col)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None
