"""
V14完整调仓执行 - 包含止损检查、调仓决策和实际交易
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import json

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

def get_current_price(symbol):
    """获取股票当前价格（使用最新K线收盘价）"""
    from live_trading.multi_source_data_fetcher import MultiSourceDataFetcher
    from datetime import datetime, timedelta

    fetcher = MultiSourceDataFetcher()
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')

    df = fetcher.fetch_klines(symbol, start_date, end_date)
    if df is not None and not df.empty:
        # 检查列名（可能是'close'或'收盘'）
        if 'close' in df.columns:
            return float(df.iloc[-1]['close'])
        elif '收盘' in df.columns:
            return float(df.iloc[-1]['收盘'])
        else:
            print(f'  警告: 未找到收盘价列，可用列: {list(df.columns)}')
    return None

def check_and_execute_stop_loss(trader):
    """检查并执行止损"""
    print('\n' + '='*70)
    print('📉 步骤1: 止损检查')
    print('='*70)

    positions = trader.repo.get_all_positions(trader.account_name)

    if not positions or len(positions) == 0:
        print('✓ 当前无持仓，跳过止损检查')
        return []

    print(f'\n当前持仓: {len(positions)}只')

    stop_loss_threshold = trader.config['risk_control']['single_stock_stop_loss']  # -12%
    to_sell = []

    for pos in positions:
        if pos.shares <= 0:
            continue

        symbol = pos.symbol
        avg_cost = float(pos.avg_price)
        shares = pos.shares

        # 获取当前价格
        print(f'\n检查 {symbol}:')
        print(f'  持仓: {shares}股 @ ¥{avg_cost:.2f}')

        current_price = get_current_price(symbol)
        if current_price is None:
            print(f'  ⚠️  无法获取当前价格，跳过')
            continue

        # 计算盈亏
        pnl_pct = (current_price - avg_cost) / avg_cost
        pnl_amount = (current_price - avg_cost) * shares

        print(f'  当前价: ¥{current_price:.2f}')
        print(f'  盈亏: {pnl_pct*100:+.2f}% (¥{pnl_amount:+,.2f})')

        # 检查是否触发止损
        if pnl_pct <= stop_loss_threshold:
            print(f'  ❌ 触发止损！(阈值: {stop_loss_threshold*100:.1f}%)')
            to_sell.append({
                'symbol': symbol,
                'shares': shares,
                'price': current_price,
                'reason': f'触发止损 (盈亏{pnl_pct*100:.2f}%)'
            })
        else:
            print(f'  ✓ 正常 (距止损线: {(pnl_pct - stop_loss_threshold)*100:.2f}%)')

    # 执行止损卖出
    if to_sell:
        print(f'\n需要止损卖出: {len(to_sell)}只')
        for item in to_sell:
            print(f'\n执行卖出: {item["symbol"]}')
            print(f'  股数: {item["shares"]}')
            print(f'  价格: ¥{item["price"]:.2f}')
            print(f'  原因: {item["reason"]}')

            try:
                # 执行卖出
                trade = trader.broker.sell(item['symbol'], item['shares'], item['price'])

                # 更新账户资金
                trader.cash += trade['total_revenue']

                # 删除持仓
                trader.repo.delete_position(trader.account_name, item['symbol'])

                # 保存交易记录（使用正确的方法：add_trade）
                trader.repo.add_trade(
                    account_name=trader.account_name,
                    symbol=item['symbol'],
                    action='SELL',
                    shares=item['shares'],
                    price=item['price'],
                    filled_price=trade['filled_price'],
                    commission=trade['commission'],
                    trade_date=datetime.now().strftime('%Y-%m-%d'),
                    status='filled'
                )

                print(f'  ✅ 卖出成功')
                print(f'     成交价: ¥{trade["filled_price"]:.2f}')
                print(f'     到账: ¥{trade["total_revenue"]:.2f}')
            except Exception as e:
                print(f'  ❌ 卖出失败: {e}')
    else:
        print('\n✓ 无需止损')

    return to_sell

def execute_v14_full_rebalance():
    """执行V14完整调仓（止损+调仓+实际交易）"""
    from live_trading.simulation_trader import SimulationTrader
    from live_trading.v14_factor_calculator import V14FactorCalculator

    print('='*70)
    print('🚀 V14完整调仓执行')
    print('='*70)
    print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    # 初始化
    trader = SimulationTrader()
    trader.account_name = 'v14_simulation'
    trader.load_model()

    print(f'账户: {trader.account_name}')
    print(f'现金: ¥{trader.cash:,.2f}')

    # 步骤1: 止损检查
    stop_loss_trades = check_and_execute_stop_loss(trader)

    # 步骤2: 调仓决策
    print('\n' + '='*70)
    print('🔄 步骤2: 调仓决策')
    print('='*70)

    calc = V14FactorCalculator()

    print(f'\n获取 {len(GEM_STOCK_POOL)} 只股票数据...')
    factors = calc.calculate_latest_factors(GEM_STOCK_POOL, days=100)

    if factors.empty:
        print('✗ 因子计算失败')
        return {'success': False, 'error': '因子计算失败'}

    print(f'✓ 因子计算完成')

    # 模型预测
    print('\n模型预测 Top 5...')
    factor_cols = [col for col in trader.valid_factors if col in factors.columns]
    X = factors[factor_cols].fillna(0)
    scores = trader.model.predict(X)

    factors['pred_return'] = scores
    latest_factors = factors.groupby('symbol').tail(1)
    top5 = latest_factors.nlargest(5, 'pred_return')

    print('\nTop 5 股票:')
    for idx, row in top5.iterrows():
        symbol = row['symbol']
        score = row['pred_return']
        stock_name = next((s['name'] for s in GEM_STOCK_POOL if s['symbol'] == symbol), '未知')
        print(f'  {symbol} {stock_name:10s} - {score:.4f}')

    # 步骤3: 执行调仓
    print('\n' + '='*70)
    print('💼 步骤3: 执行调仓')
    print('='*70)

    target_symbols = set(top5['symbol'].tolist())
    current_positions = trader.repo.get_all_positions(trader.account_name)
    current_symbols = set([p.symbol for p in current_positions if p.shares > 0])

    to_sell = current_symbols - target_symbols
    to_buy = target_symbols - current_symbols

    print(f'\n目标持仓: {target_symbols}')
    print(f'当前持仓: {current_symbols}')
    print(f'需要卖出: {to_sell}')
    print(f'需要买入: {to_buy}')

    # 执行卖出（调仓）
    if to_sell:
        print(f'\n执行卖出（调仓）:')
        for symbol in to_sell:
            pos = next((p for p in current_positions if p.symbol == symbol), None)
            if pos and pos.shares > 0:
                current_price = get_current_price(symbol)
                if current_price:
                    print(f'\n  卖出 {symbol}: {pos.shares}股 @ ¥{current_price:.2f}')
                    try:
                        trade = trader.broker.sell(symbol, pos.shares, current_price)
                        trader.cash += trade['total_revenue']
                        trader.repo.delete_position(trader.account_name, symbol)

                        # 保存交易记录
                        trader.repo.add_trade(
                            account_name=trader.account_name,
                            symbol=symbol,
                            action='SELL',
                            shares=pos.shares,
                            price=current_price,
                            filled_price=trade['filled_price'],
                            commission=trade['commission'],
                            trade_date=datetime.now().strftime('%Y-%m-%d'),
                            status='filled'
                        )
                        print(f'    ✅ 成功')
                    except Exception as e:
                        print(f'    ❌ 失败: {e}')

    # 执行买入
    if to_buy:
        print(f'\n执行买入:')
        per_stock_pct = 0.18  # 18%仓位

        # 重新获取当前资金（可能因卖出而增加）
        account = trader.repo.get_account(trader.account_name)
        available_cash = float(account.cash)
        per_stock_amount = available_cash * per_stock_pct

        print(f'  可用资金: ¥{available_cash:,.2f}')
        print(f'  单股金额: ¥{per_stock_amount:,.2f} (18%)')

        for symbol in to_buy:
            current_price = get_current_price(symbol)
            if current_price:
                # 计算可买股数（100股整数倍）
                shares = int(per_stock_amount / current_price / 100) * 100

                if shares >= 100:
                    print(f'\n  买入 {symbol}: {shares}股 @ ¥{current_price:.2f}')
                    try:
                        trade = trader.broker.buy(symbol, shares, current_price)

                        # 更新资金
                        trader.cash -= trade['total_cost']

                        # 创建或更新持仓（使用upsert_position）
                        trader.repo.upsert_position(
                            account_name=trader.account_name,
                            symbol=symbol,
                            shares=shares,
                            avg_price=trade['filled_price'],
                            current_price=current_price
                        )

                        # 保存交易记录
                        trader.repo.add_trade(
                            account_name=trader.account_name,
                            symbol=symbol,
                            action='BUY',
                            shares=shares,
                            price=current_price,
                            filled_price=trade['filled_price'],
                            commission=trade['commission'],
                            trade_date=datetime.now().strftime('%Y-%m-%d'),
                            status='filled'
                        )

                        print(f'    ✅ 成功')
                        print(f'       成交价: ¥{trade["filled_price"]:.2f}')
                        print(f'       成本: ¥{trade["total_cost"]:.2f}')
                    except Exception as e:
                        print(f'    ❌ 失败: {e}')
                else:
                    print(f'\n  {symbol}: 资金不足（需要至少100股）')

    # 更新账户信息（使用正确的方法签名）
    account = trader.repo.get_account(trader.account_name)
    trader.repo.update_account(
        account_name=trader.account_name,
        cash=trader.cash,
        total_value=trader.cash,  # 简化计算
        peak_value=max(account.peak_value, trader.cash),
        cumulative_return=0.0,  # 需要计算
        max_drawdown=0.0,  # 需要计算
        last_rebalance_date=datetime.now().strftime('%Y-%m-%d')
    )

    print('\n' + '='*70)
    print('✅ V14调仓完成')
    print('='*70)

    # 最终状态
    final_account = trader.repo.get_account(trader.account_name)
    final_positions = trader.repo.get_all_positions(trader.account_name)

    print(f'\n最终状态:')
    print(f'  账户: {trader.account_name}')
    print(f'  现金: ¥{final_account.cash:,.2f}')
    print(f'  持仓数: {len([p for p in final_positions if p.shares > 0])}只')

    if final_positions:
        print(f'\n  持仓明细:')
        for pos in final_positions:
            if pos.shares > 0:
                print(f'    {pos.symbol} - {pos.shares}股 @ ¥{pos.avg_price:.2f}')

    return {
        'success': True,
        'stop_loss_count': len(stop_loss_trades),
        'sold_count': len(to_sell) if to_sell else 0,
        'bought_count': len(to_buy) if to_buy else 0,
        'final_cash': float(final_account.cash),
        'final_positions': len([p for p in final_positions if p.shares > 0])
    }

if __name__ == '__main__':
    try:
        result = execute_v14_full_rebalance()

        print('\n' + '='*70)
        print('执行结果:')
        print('='*70)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f'\n❌ 执行失败: {e}')
        import traceback
        traceback.print_exc()
