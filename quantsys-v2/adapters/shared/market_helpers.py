"""行情解析与股票数据助手（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来"""
from typing import Optional

from adapters.shared.stores import _safe_float


def _parse_sina_a_quote(data):
    """解析新浪 A 股行情数据"""
    return {
        'symbol': data.get('symbol', ''),
        'name': data.get('name', ''),
        'price': _safe_float(data.get('price')),
        'change': _safe_float(data.get('change')),
        'change_pct': _safe_float(data.get('change_pct')),
        'volume': _safe_float(data.get('volume')),
        'amount': _safe_float(data.get('amount')),
    }


def _parse_sina_hk_quote(data):
    """解析新浪港股行情数据"""
    return {
        'symbol': data.get('symbol', ''),
        'name': data.get('name', ''),
        'price': _safe_float(data.get('price')),
        'change': _safe_float(data.get('change')),
        'change_pct': _safe_float(data.get('change_pct')),
        'volume': _safe_float(data.get('volume')),
        'amount': _safe_float(data.get('amount')),
    }


def infer_market(symbol) -> Optional[str]:
    """从代码推断 stocks.market 取值（DB 约束 chk_stocks_market 仅允许 'A' / 'HK'）。

    背景（2026-09-11，w-8f2c4cc5｜看板事件 98d2a20f / 60911dd8）：
    K 线回填路径在股票元数据缺失时用 market='unknown' 占位建 stocks 行，
    而 chk_stocks_market 只允许 'A'/'HK' → CheckViolation → 整批 K 线回填静默失败
    （接口仍返回 200，DB 永不落数据，每次请求重复打外网源）。

    规则：6 位纯数字 = A 股（含 688 科创板，仍是 A 股市场）；
          5 位纯数字 / 以 HK 开头 / 以 .HK 结尾 = 港股。
    无法判定时返回 None —— 调用方必须显式处理，禁止回退成 'unknown'
    （'unknown' 必然违反约束，等于把"不知道"写成"必失败"）。
    """
    if not isinstance(symbol, str):
        return None
    raw = symbol.strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper.startswith('HK'):
        body = upper[2:]
        return 'HK' if body.isascii() and body.isdigit() else None
    body = upper.split('.')[0]
    if not (body.isascii() and body.isdigit()):
        return None
    if len(body) == 6:
        return 'A'
    if len(body) == 5:
        return 'HK'
    return None


def enrich_stock_data(stock_data):
    """丰富股票数据（向后兼容）"""
    return stock_data


def signal_to_opportunity(signal):
    """将信号转换为机会（向后兼容）"""
    return signal


def _aggregate_weekly(klines):
    """将日K线聚合为周K线"""
    import pandas as pd
    if not klines:
        return []
    df = pd.DataFrame(klines)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
    weekly = df.resample('W').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum', 'amount': 'sum',
    }).dropna()
    weekly.reset_index(inplace=True)
    return weekly.to_dict('records')


def _aggregate_monthly(klines):
    """将日K线聚合为月K线"""
    import pandas as pd
    if not klines:
        return []
    df = pd.DataFrame(klines)
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
    monthly = df.resample('M').agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum', 'amount': 'sum',
    }).dropna()
    monthly.reset_index(inplace=True)
    return monthly.to_dict('records')
