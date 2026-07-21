"""
快速修复：执行V14调仓 - 使用硬编码股票池
"""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# 优质创业板股票池
GEM_STOCK_POOL = [
    {'symbol': '300750', 'name': '宁德时代'},
    {'symbol': '300760', 'name': '迈瑞医疗'},
    {'symbol': '300059', 'name': '东方财富'},
    {'symbol': '300015', 'name': '爱尔眼科'},
    {'symbol': '300142', 'name': '沃森生物'},
    {'symbol': '300014', 'name': '亿纬锂能'},
    {'symbol': '300274', 'name': '阳光电源'},
    {'symbol': '300122', 'name': '智飞生物'},
    {'symbol': '300124', 'name': '汇川技术'},
    {'symbol': '300454', 'name': '深信服'},
    {'symbol': '300751', 'name': '迈为股份'},
    {'symbol': '300408', 'name': '三环集团'},
    {'symbol': '300896', 'name': '爱美客'},
    {'symbol': '300999', 'name': '金龙鱼'},
    {'symbol': '300919', 'name': '中伟股份'},
    {'symbol': '300762', 'name': '上海瀚讯'},
    {'symbol': '300763', 'name': '锦浪科技'},
    {'symbol': '300450', 'name': '先导智能'},
    {'symbol': '300316', 'name': '晶盛机电'},
    {'symbol': '300957', 'name': '贝泰妮'},
]

def execute_v14_rebalance_with_stock_pool():
    """执行V14调仓（使用指定股票池）"""
    from live_trading.simulation_trader import SimulationTrader
    from live_trading.v14_factor_calculator import V14FactorCalculator
    import json

    print('='*70)
    print('🚀 执行V14完整调仓流程')
    print('='*70)
    print()

    # 1. 初始化交易器
    print('[1/5] 初始化SimulationTrader...')
    trader = SimulationTrader()
    trader.account_name = 'v14_simulation'
    trader.load_model()

    print(f'  账户: {trader.account_name}')
    print(f'  现金: ¥{trader.cash:,.2f}')
    print(f'  持仓: {len(trader.portfolio)}只')

    # 显示当前持仓
    if trader.portfolio:
        print('\n  当前持仓:')
        for symbol, pos in trader.portfolio.items():
            pnl_pct = ((pos['current_price'] - pos['avg_cost']) / pos['avg_cost'] * 100) if pos['avg_cost'] > 0 else 0
            print(f'    {symbol} - {pos["shares"]}股 @ ¥{pos["avg_cost"]:.2f} (盈亏: {pnl_pct:+.2f}%)')

    # 2. 初始化V14因子计算器
    print('\n[2/5] 初始化V14FactorCalculator（多数据源）...')
    calc = V14FactorCalculator()

    # 3. 获取数据并计算因子
    print(f'\n[3/5] 获取 {len(GEM_STOCK_POOL)} 只股票数据并计算因子...')
    factors = calc.calculate_latest_factors(GEM_STOCK_POOL, days=100)

    if factors.empty:
        print('✗ 因子计算失败')
        return {'success': False, 'error': '因子计算失败'}

    print(f'✓ 因子计算完成: {len(factors)} 条记录')

    # 4. 模型预测
    print('\n[4/5] 使用V14 P0模型预测...')

    # 准备预测数据
    factor_cols = [col for col in trader.valid_factors if col in factors.columns]
    X = factors[factor_cols].fillna(0)

    # 预测（trader.model是XGBRegressor，直接传DataFrame）
    scores = trader.model.predict(X)

    # 获取最新记录的预测分数（按symbol分组，取最后一条）
    factors['pred_return'] = scores
    latest_factors = factors.groupby('symbol').tail(1)

    # 排序并选择Top 5
    top5 = latest_factors.nlargest(5, 'pred_return')

    print(f'\n✓ 预测完成，Top 5 股票:')
    for idx, row in top5.iterrows():
        symbol = row['symbol']
        score = row['pred_return']
        stock_name = next((s['name'] for s in GEM_STOCK_POOL if s['symbol'] == symbol), '未知')
        print(f'  {symbol} {stock_name:10s} - 预测得分: {score:.4f}')

    # 5. 执行调仓
    print('\n[5/5] 执行调仓操作...')

    target_symbols = set(top5['symbol'].tolist())
    current_symbols = set(trader.portfolio.keys())

    # 计算需要卖出和买入的股票
    to_sell = current_symbols - target_symbols
    to_buy = target_symbols - current_symbols

    print(f'\n  目标持仓: {target_symbols}')
    print(f'  当前持仓: {current_symbols}')
    print(f'  需要卖出: {to_sell}')
    print(f'  需要买入: {to_buy}')

    # 执行卖出
    if to_sell:
        print('\n  执行卖出操作...')
        for symbol in to_sell:
            pos = trader.portfolio.get(symbol)
            if pos and pos['shares'] > 0:
                print(f'    卖出 {symbol} {pos["shares"]}股')
                # TODO: 调用trader.sell()方法
                # trader.sell(symbol, pos['shares'], current_date=datetime.now().strftime('%Y-%m-%d'))

    # 执行买入
    if to_buy:
        print('\n  执行买入操作...')
        per_stock_amount = trader.cash * 0.18
        print(f'    单股金额: ¥{per_stock_amount:,.2f} (18%仓位)')

        for symbol in to_buy:
            print(f'    计划买入 {symbol}')
            # TODO: 调用trader.buy()方法
            # trader.buy(symbol, amount=per_stock_amount, current_date=datetime.now().strftime('%Y-%m-%d'))

    print('\n' + '='*70)
    print('V14调仓流程完成')
    print('='*70)

    print('\n注意: 实际买卖操作需要实现trader.buy()和trader.sell()方法')
    print('当前仅显示调仓计划，未执行实际交易')

    # 数据源健康报告
    print('\n数据源健康报告:')
    report = calc.get_health_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))

    return {
        'success': True,
        'top5_symbols': list(target_symbols),
        'to_sell': list(to_sell),
        'to_buy': list(to_buy),
        'account': trader.account_name
    }


if __name__ == '__main__':
    result = execute_v14_rebalance_with_stock_pool()

    print('\n执行结果:')
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
