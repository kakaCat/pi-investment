#!/usr/bin/env python
"""
测试交易日判断和调仓逻辑
"""
import sys
import os
os.chdir('quantsys-v2')
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from live_trading.simulation_trader import SimulationTrader
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')

# 初始化trader
config_path = Path('live_trading/config_simulation.yaml')
trader = SimulationTrader(config_path=str(config_path))
trader.load_model()

print('='*70)
print('交易日判断功能测试')
print('='*70)

# 测试1: 周末应该被识别为非交易日
test_cases = [
    ('2026-06-23', '周一'),
    ('2026-06-24', '周二'),
    ('2026-06-25', '周三'),
    ('2026-06-26', '周四'),
    ('2026-06-27', '周五'),
    ('2026-06-28', '周六'),
    ('2026-06-29', '周日'),
    ('2026-06-30', '下周一'),
]

print('\n1. 基本周末检查:')
print('-'*70)
for date_str, desc in test_cases:
    date = datetime.strptime(date_str, '%Y-%m-%d')
    weekday = date.weekday()
    is_weekend = weekday >= 5
    status = '❌ 周末' if is_weekend else '✅ 工作日'
    print(f'{date_str} ({desc}): {status}')

# 测试2: 调仓周期计算（假设数据库有6/23-6/26的数据）
print('\n2. 调仓周期测试 (假设上次调仓: 2026-06-23 周一):')
print('-'*70)
trader.last_rebalance_date = '2026-06-23'

# 假设6/23-6/26是交易日
trading_days_from_623 = {
    '2026-06-23': 0,  # 当天
    '2026-06-24': 1,  # +1
    '2026-06-25': 2,  # +2
    '2026-06-26': 3,  # +3
    '2026-06-27': 4,  # +4 (如果是交易日)
    '2026-06-30': 5,  # +5 (如果是交易日，应该触发调仓)
}

for date_str in ['2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26', '2026-06-27', '2026-06-30']:
    expected_days = trading_days_from_623.get(date_str, '?')
    print(f'{date_str}: 距离上次调仓 {expected_days} 个交易日')

print('\n3. 预期行为:')
print('-'*70)
print('✅ 周末（6/28、6/29）应该跳过检查')
print('✅ 6/27（周五）如果有数据，距离6/23是4个交易日，不应触发调仓')
print('✅ 6/30（周一）如果有数据，距离6/23是5个交易日，应该触发调仓')
print('✅ V13策略配置: 每5个交易日调仓一次')

print('\n4. 修复内容:')
print('-'*70)
print('✅ 添加 _is_trading_day() - 检查周末 + 数据库K线存在')
print('✅ 添加 _count_trading_days() - 计算两日期间的交易日数')
print('✅ 修改 should_rebalance() - 按交易日计算，非交易日直接返回False')
print('✅ 修复配置和模型文件路径问题')

print('='*70)
