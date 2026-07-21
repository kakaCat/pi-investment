#!/usr/bin/env python3
"""调试脚本：直接调用 backtest_strategy 来查看完整错误堆栈"""

import sys
import traceback
import logging

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导入必要的模块
from application.services.strategy_code_service import StrategyCodeService

def main():
    """直接调用 backtest_strategy"""
    try:
        service = StrategyCodeService()

        print("开始回测...")
        result = service.backtest_strategy(
            strategy_id=415,
            symbol='002714',
            start_date='2025-06-22',
            end_date='2026-06-22',
            initial_cash=1000000,
            period='daily'
        )

        print("回测成功!")
        print(f"结果: {result}")

    except Exception as e:
        print(f"\n错误: {e}")
        print("\n完整堆栈:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
