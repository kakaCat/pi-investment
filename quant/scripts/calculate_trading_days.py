#!/usr/bin/env python3
"""
计算实际交易日天数（HTTP 客户端版）

通过 Flask API 获取股票数据范围，计算交易日天数。
前置条件: Flask API 服务运行在 127.0.0.1:5002（可通过 QUANT_API_URL 环境变量覆盖）
"""

import sys
from datetime import datetime
import requests
import pandas as pd

API_BASE = os.getenv("QUANT_API_URL", "http://127.0.0.1:5002")


def calculate_trading_days(start_date: str, end_date: str) -> int:
    """计算两个日期之间的交易日天数（排除周末）"""
    try:
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        try:
            import chinese_calendar as cc
            return len([d for d in date_range if not cc.is_holiday(d)])
        except ImportError:
            return len(date_range)
    except Exception:
        return 0


def main():
    print("=" * 80)
    print("计算实际交易日天数 (API 模式)")
    print("=" * 80)
    print()

    base_start_date = '2021-05-19'

    # 检查 API
    try:
        requests.get(f"{API_BASE}/api/health", timeout=5)
    except requests.ConnectionError:
        print(f"❌ 无法连接到 API 服务 ({API_BASE})")
        print("   请先启动: python3 quant/api/server.py")
        return

    # 获取数据状态
    try:
        resp = requests.get(f"{API_BASE}/api/stocks/data-status", timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"❌ 获取数据状态失败: {e}")
        return

    stocks = data.get('stocks', [])
    if not stocks:
        print("❌ 无股票数据")
        return

    print(f"{'代码':<10} {'名称':<12} {'K线天数':<10} {'最早':<12} {'最新':<12} {'交易日':<10}")
    print("-" * 80)

    for s in stocks[:50]:  # 只显示前50只
        symbol = s['symbol']
        name = s.get('name', '')
        kline_days = s.get('kline_days', 0)
        earliest = s.get('earliest_date', '')
        latest = s.get('latest_date', '')

        if earliest and latest:
            calc_start = max(base_start_date, earliest)
            trading_days = calculate_trading_days(calc_start, latest)
        else:
            trading_days = 0

        print(f"{symbol:<10} {name:<12} {kline_days:<10} {earliest:<12} {latest:<12} {trading_days:<10}")

    # 汇总
    if stocks:
        all_latest = [s['latest_date'] for s in stocks if s.get('latest_date')]
        all_earliest = [s['earliest_date'] for s in stocks if s.get('earliest_date')]

        print()
        print("=" * 80)
        print(f"股票总数: {len(stocks)}")
        print(f"数据完整: {data.get('complete_stocks', 0)}")
        if all_earliest:
            print(f"最早数据: {min(all_earliest)}")
        if all_latest:
            print(f"最新数据: {max(all_latest)}")
            calc_start = max(base_start_date, min(all_earliest) if all_earliest else base_start_date)
            td = calculate_trading_days(calc_start, max(all_latest))
            print(f"基准日期: {base_start_date}")
            print(f"交易日数: {td}")

        full_5yr = calculate_trading_days(base_start_date, datetime.now().strftime('%Y-%m-%d'))
        print(f"5年完整交易日: {full_5yr}")


if __name__ == '__main__':
    main()
