"""行情解析与股票数据助手（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来"""
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
