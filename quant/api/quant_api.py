#!/usr/bin/env python3
"""
Quant API - TypeScript 调用 Python 量化系统的桥接层

提供统一的 API 接口，让 TypeScript 工具通过 JSON-RPC 方式调用量化功能。

Usage:
    python3 quant_api.py <function_name> <json_args>

Example:
    python3 quant_api.py get_stock_factors '{"symbol": "600036", "date": "2026-05-18"}'
    python3 quant_api.py get_signals '{"date": "2026-05-18", "min_confidence": 0.7}'
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import math

# 添加 quantsys 到路径
QUANT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(QUANT_ROOT))

from quantsys.data.db import Database


def _json_number(value: Any) -> Any:
    """Return JSON-safe scalar values for API output."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


class QuantAPI:
    """量化系统 API"""

    def __init__(self):
        """初始化数据库连接"""
        _project_root = QUANT_ROOT.parent  # quant/ → project_root/
        _project_db = _project_root / '.pi-invest' / 'stock-db' / 'stocks.db'
        _home_db = Path.home() / '.pi-invest' / 'stock-db' / 'stocks.db'
        db_path = _project_db if _project_db.exists() else _home_db
        self.db = Database(str(db_path))

    def get_stock_factors(self, symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        获取股票因子数据

        Args:
            symbol: 股票代码
            date: 日期 (YYYY-MM-DD)，默认最新

        Returns:
            {
                "symbol": "600036",
                "date": "2026-05-18",
                "factors": {
                    "RSI": 10.37,
                    "MA5": 37.74,
                    "MA20": 38.72,
                    ...
                }
            }
        """
        # 如果没有指定日期，获取最新日期
        if not date:
            date = self.db.get_latest_factor_date_for_symbol(symbol)

        if not date:
            return {"error": f"No factor data found for {symbol}"}

        # 获取因子数据
        factors = self.db.get_factor_values(symbol, date)

        if not factors:
            return {"error": f"No factors found for {symbol} on {date}"}

        return {
            "symbol": symbol,
            "date": date,
            "factors": factors
        }

    def get_klines(self, symbol: str, start_date: Optional[str] = None,
                   end_date: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        获取K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 最大返回条数

        Returns:
            {
                "symbol": "600036",
                "count": 100,
                "klines": [
                    {"date": "2026-05-18", "open": 37.5, "close": 37.47, ...},
                    ...
                ]
            }
        """
        frame = self.db.get_backtest_klines(
            symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        if frame.empty:
            rows = []
        else:
            date_column = "date" if "date" in frame.columns else "timestamp"
            frame = frame.sort_values(date_column, ascending=False)
            rows = frame.to_dict("records")
        klines = []
        for row in rows:
            klines.append({
                "date": row.get("date") or row.get("timestamp"),
                "open": _json_number(row.get("open")),
                "high": _json_number(row.get("high")),
                "low": _json_number(row.get("low")),
                "close": _json_number(row.get("close")),
                "volume": _json_number(row.get("volume")),
                "amount": _json_number(row.get("amount"))
            })

        return {
            "symbol": symbol,
            "count": len(klines),
            "klines": klines
        }

    def get_signals(self, date: Optional[str] = None,
                    signal_type: Optional[str] = None,
                    min_confidence: float = 0.0) -> Dict[str, Any]:
        """
        获取交易信号

        Args:
            date: 日期，默认最新
            signal_type: 信号类型 (BUY/SELL)
            min_confidence: 最小置信度

        Returns:
            {
                "date": "2026-05-18",
                "count": 20,
                "signals": [
                    {
                        "symbol": "600036",
                        "signal": "BUY",
                        "strategy": "RSI反转",
                        "confidence": 1.0,
                        "reason": "RSI超卖",
                        "price": 37.47
                    },
                    ...
                ]
            }
        """
        # 读取信号文件
        signals_file = QUANT_ROOT / '.pi-invest' / 'signals.json'

        if not signals_file.exists():
            return {"error": "Signals file not found. Run generate_signals.py first."}

        with open(signals_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        signals = data.get('signals', [])

        # 过滤信号
        filtered = []
        for sig in signals:
            # 日期过滤
            if date and sig.get('date') != date:
                continue

            # 类型过滤
            if signal_type and sig.get('signal') != signal_type:
                continue

            # 置信度过滤
            if sig.get('confidence', 0) < min_confidence:
                continue

            filtered.append(sig)

        return {
            "date": data.get('date'),
            "count": len(filtered),
            "signals": filtered
        }

    def get_stock_list(self, market: Optional[str] = None,
                       has_data: bool = False) -> Dict[str, Any]:
        """
        获取股票列表

        Args:
            market: 市场 (A/HK)
            has_data: 是否只返回有K线数据的股票

        Returns:
            {
                "count": 41,
                "stocks": [
                    {"symbol": "600036", "name": "招商银行", "market": "A"},
                    ...
                ]
            }
        """
        stocks = self.db.get_stock_rows(market=market, has_data=has_data)

        return {
            "count": len(stocks),
            "stocks": stocks
        }

    def get_daily_report(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        获取每日报告

        Args:
            date: 日期，默认最新

        Returns:
            每日报告的完整内容
        """
        # 读取报告文件
        if date:
            report_file = QUANT_ROOT / '.pi-invest' / f'daily_report_{date}.json'
        else:
            report_file = QUANT_ROOT / '.pi-invest' / 'daily_report.json'

        if not report_file.exists():
            return {"error": "Daily report not found. Run daily_report.py first."}

        with open(report_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def calculate_technical_indicators(self, symbol: str,
                                       indicators: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        计算技术指标

        Args:
            symbol: 股票代码
            indicators: 指标列表，如 ["RSI", "MACD", "MA5"]，默认全部

        Returns:
            {
                "symbol": "600036",
                "date": "2026-05-18",
                "indicators": {
                    "RSI": 10.37,
                    "MACD_DIF": -0.5,
                    "MA5": 37.74,
                    ...
                }
            }
        """
        # 获取最新K线数据
        klines_result = self.get_klines(symbol, limit=100)

        if 'error' in klines_result or klines_result['count'] < 20:
            return {"error": f"Insufficient data for {symbol}"}

        klines = klines_result['klines']

        # 转换为 pandas DataFrame
        import pandas as pd
        df = pd.DataFrame(klines)
        # 兼容多种日期格式: ISO8601 (2026-05-15) 和紧凑格式 (20260515)
        df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')
        df = df.sort_values('date')

        # 计算指标
        result_indicators = {}

        # RSI
        if not indicators or 'RSI' in indicators:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            result_indicators['RSI'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

        # MA5, MA10, MA20
        for period in [5, 10, 20, 60]:
            key = f'MA{period}'
            if not indicators or key in indicators:
                ma = df['close'].rolling(window=period).mean()
                result_indicators[key] = float(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else None

        # MACD
        if not indicators or 'MACD' in indicators or 'MACD_DIF' in indicators:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd_dif = exp1 - exp2
            macd_dea = macd_dif.ewm(span=9, adjust=False).mean()
            macd_histogram = macd_dif - macd_dea

            result_indicators['MACD_DIF'] = float(macd_dif.iloc[-1]) if not pd.isna(macd_dif.iloc[-1]) else None
            result_indicators['MACD_DEA'] = float(macd_dea.iloc[-1]) if not pd.isna(macd_dea.iloc[-1]) else None
            result_indicators['MACD'] = float(macd_histogram.iloc[-1]) if not pd.isna(macd_histogram.iloc[-1]) else None

        return {
            "symbol": symbol,
            "date": klines[0]['date'],
            "indicators": result_indicators
        }


def main():
    """主函数：处理命令行调用"""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python3 quant_api.py <function_name> [json_args]"}))
        sys.exit(1)

    function_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    try:
        api = QuantAPI()

        # 调用对应的方法
        if hasattr(api, function_name):
            method = getattr(api, function_name)
            result = method(**args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"error": f"Unknown function: {function_name}"}))
            sys.exit(1)

    except Exception as e:
        import traceback
        print(json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc()
        }, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
