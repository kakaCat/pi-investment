#!/bin/bash
# V13模拟交易每日检查脚本

cd "$(dirname "$0")/.."

echo "============================================================"
echo "V13模拟交易系统 - 每日检查"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

python -c "
from live_trading.simulation_trader import SimulationTrader
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

try:
    trader = SimulationTrader()
    trader.load_model()
    
    print(f'\n当前账户:')
    total = trader._calculate_total_value_from_portfolio()
    print(f'  总资产: ¥{total:,.2f}')
    print(f'  持仓: {len(trader.portfolio)}只')
    
    trader.run_daily_check()
    
    print('\n✅ 每日检查完成')
except Exception as e:
    print(f'\n❌ 每日检查失败: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"

echo "============================================================"
