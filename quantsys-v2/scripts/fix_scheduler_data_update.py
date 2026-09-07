#!/usr/bin/env python3
"""
修复调度器数据更新任务的DataFrame判断问题
"""
import os
import sys
from typing import Tuple

# 设置环境变量
os.environ['PYTHONPATH'] = '.'
os.environ['PGDATABASE'] = 'quant_investment'
os.environ['PGHOST'] = '127.0.0.1'
os.environ['PGPORT'] = '5432'
os.environ['PGUSER'] = 'mac'

print("🔧 执行工具任务: 修复并测试数据更新功能\n")

# 测试修复后的逻辑
from adapters.shared.services import get_kline_repo
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

kline_repo = get_kline_repo()

def update_symbol_fixed(symbol: str) -> Tuple[bool, bool]:
    """Fixed version: Update a single symbol. Returns (success, error)."""
    try:
        latest = kline_repo.get_latest_daily_kline(symbol)
        # Handle DataFrame response correctly (Polars or Pandas)
        if latest is not None:
            if hasattr(latest, 'is_empty'):
                # It's a Polars DataFrame
                has_data = not latest.is_empty()
            elif hasattr(latest, 'empty'):
                # It's a Pandas DataFrame
                has_data = not latest.empty
            elif hasattr(latest, '__len__'):
                # Has length (list, dict, etc.)
                has_data = len(latest) > 0
            else:
                # Other truthy value
                has_data = bool(latest)
            return (has_data, False)
        else:
            # No data available
            return (False, False)
    except Exception as e:
        logger.warning(f"Failed to update {symbol}: {e}")
        return (False, True)

# 测试10个股票
test_symbols = [
    "600519.SH", "000858.SZ", "600036.SH", "000001.SZ", "600276.SH",
    "000002.SZ", "600887.SH", "000333.SZ", "601318.SH", "000651.SZ"
]

print(f"📊 测试 {len(test_symbols)} 个股票...\n")

updated = 0
errors = 0

# 并行测试
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(update_symbol_fixed, sym): sym for sym in test_symbols}
    for future in as_completed(futures):
        sym = futures[future]
        try:
            success, error = future.result()
            if success:
                updated += 1
                print(f"  ✅ {sym}: 有数据")
            elif error:
                errors += 1
                print(f"  ❌ {sym}: 错误")
            else:
                print(f"  ⚠️ {sym}: 无数据")
        except Exception as e:
            errors += 1
            print(f"  ❌ {sym}: 异常 - {e}")

print(f"\n📊 测试结果:")
print(f"  检查股票数: {len(test_symbols)}")
print(f"  更新成功数: {updated}")
print(f"  错误数: {errors}")
print(f"  成功率: {100 * updated / len(test_symbols):.1f}%")

if errors == 0 and updated > 0:
    print(f"\n✅ 修复成功！数据更新功能正常工作")
    print(f"\n💡 下一步: 重启quantsys-v2服务以应用修复")
    sys.exit(0)
elif updated > 0:
    print(f"\n⚠️ 部分成功，还有 {errors} 个错误")
    sys.exit(1)
else:
    print(f"\n❌ 修复验证失败")
    sys.exit(1)
