#!/usr/bin/env python3
"""
测试 KlineRepository 查询
"""
import sys

from adapters.outbound.repositories import KlineORMRepository
from datetime import datetime, timedelta

# 初始化
repo = KlineORMRepository()

# 测试查询
symbols = ['920896', '000001', '600737']
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

print(f"测试日期范围: {start_date} 到 {end_date}\n")

for symbol in symbols:
    print(f"=" * 50)
    print(f"测试股票: {symbol}")
    print(f"=" * 50)

    try:
        klines = repo.get_daily_klines(
            symbol,
            start_date,
            end_date,
            fields=['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        )

        print(f"返回类型: {type(klines)}")

        if klines is None:
            print("结果: None")
        elif hasattr(klines, 'is_empty'):
            print(f"是 Polars DataFrame")
            print(f"Is empty: {klines.is_empty()}")
            if not klines.is_empty():
                print(f"Shape: {klines.shape}")
                print(f"前3行:")
                print(klines.head(3))
        else:
            print(f"是其他类型: {type(klines)}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    print()
