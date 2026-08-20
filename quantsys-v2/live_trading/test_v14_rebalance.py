"""
快速测试V14调仓 - 使用硬编码的优质创业板股票池
"""
import os
import sys
import logging
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# 硬编码优质创业板股票池（用于测试）
TEST_GEM_STOCKS = [
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

def test_v14_rebalance():
    """测试V14调仓流程"""
    from live_trading.v14_factor_calculator import V14FactorCalculator
    from live_trading.simulation_trader import SimulationTrader
    import json

    print('='*70)
    print('V14调仓测试 - 使用优质创业板股票池')
    print('='*70)

    # 1. 初始化因子计算器
    print('\n[1/4] 初始化V14因子计算器（多数据源）...')
    calc = V14FactorCalculator()

    # 2. 获取数据并计算因子
    print(f'\n[2/4] 获取 {len(TEST_GEM_STOCKS)} 只股票的数据并计算因子...')
    factors = calc.calculate_latest_factors(TEST_GEM_STOCKS, days=100)

    if factors.empty:
        print('✗ 因子计算失败，无法继续')
        return

    print(f'✓ 成功计算因子: {len(factors)} 只股票')

    # 3. 使用XGBoost模型预测
    print('\n[3/4] 加载V14 P0模型并预测...')

    import xgboost as xgb
    import pandas as pd

    # 加载模型
    model_path = 'live_trading/models/v14_p0_model.json'
    model = xgb.Booster()
    model.load_model(model_path)

    # 加载有效因子列表
    import json
    with open('live_trading/models/v14_p0_valid_factors.json', 'r') as f:
        valid_factors = json.load(f)

    print(f'✓ 模型已加载: {len(valid_factors)} 个因子')

    # 准备预测数据
    factor_cols = [col for col in valid_factors if col in factors.columns]
    X = factors[factor_cols].fillna(0)

    # 预测
    dmatrix = xgb.DMatrix(X)
    scores = model.predict(dmatrix)

    # 添加预测分数
    factors['pred_return'] = scores
    factors['symbol'] = factors.index

    # 排序并选择Top 5
    top5 = factors.nlargest(5, 'pred_return')

    print(f'\n✓ 预测完成，Top 5 股票:')
    for idx, row in top5.iterrows():
        symbol = row['symbol']
        score = row['pred_return']
        stock_name = next((s['name'] for s in TEST_GEM_STOCKS if s['symbol'] == symbol), '未知')
        print(f'  {symbol} {stock_name:10s} - 预测得分: {score:.4f}')

    # 4. 执行模拟交易
    print('\n[4/4] 执行模拟交易（买入Top 5）...')

    trader = SimulationTrader()
    trader.account_name = 'v14_simulation'
    trader.load_model()

    # 获取当前资金
    print(f'  当前资金: ¥{trader.cash:,.2f}')

    # 计算每只股票的买入金额（18%仓位）
    per_stock_amount = trader.cash * 0.18

    print(f'  单股仓位: 18% = ¥{per_stock_amount:,.2f}')
    print(f'  总计划仓位: 90% = ¥{trader.cash * 0.90:,.2f}')

    # TODO: 这里需要调用trader的buy方法执行买入
    # 但trader可能需要实时价格，暂时只显示计划

    print('\n' + '='*70)
    print('V14调仓测试完成')
    print('='*70)

    # 数据源健康报告
    print('\n数据源健康报告:')
    report = calc.get_health_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    test_v14_rebalance()
