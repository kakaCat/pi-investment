#!/usr/bin/env python3
"""测试回填脚本（3只股票，最近30天）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from scripts.backfill_factors import backfill_factors

end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=45)).strftime('%Y-%m-%d')

print(f"=== 测试回填 ===")
print(f"范围: {start_date} ~ {end_date}")
print(f"股票: 600519, 000001, 600737")

result = backfill_factors(
    symbols=['600519', '000001', '600737'],
    start_date=start_date,
    end_date=end_date,
    batch_size=10,
    skip_existing=False,  # 测试时强制重算
)

print("\n=== 结果 ===")
print(f"保存: {result['total_saved']} 条")
print(f"失败: {result['total_failed']}")
print(f"交易日: {result['trading_dates_count']}")
