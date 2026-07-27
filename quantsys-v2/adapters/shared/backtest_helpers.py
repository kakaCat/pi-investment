"""回测执行助手（框架无关）— 从 adapters/inbound/api/routes/backtest.py 解耦而来

save_simple_backtest / run_pe_mean_reversion_backtest / run_pb_mean_reversion_backtest。
纯回测数学计算（只依赖 datetime/math），Flask 与 FastAPI 两个 API 层共享。
"""
from datetime import datetime
import math

def save_simple_backtest(params, klines, initial_capital):
    """执行简单的移动平均交叉回测"""
    from datetime import datetime
    import math

    short_window = int(params.get('ma_short', 5))
    long_window = int(params.get('ma_long', 20))
    commission_rate = float(params.get('commission_rate', 0.0003))  # 默认万三

    capital = initial_capital
    position = 0
    position_cost = 0
    trades = []
    equity_curve = []
    daily_returns = []

    for i in range(long_window, len(klines)):
        short_ma = sum(k['close'] for k in klines[i-short_window:i]) / short_window
        long_ma = sum(k['close'] for k in klines[i-long_window:i]) / long_window
        price = klines[i]['close']
        date = klines[i]['trade_date']

        current_equity = capital + (position * price if position > 0 else 0)
        equity_curve.append({
            'date': date,
            'value': round(current_equity, 2)
        })

        if i > long_window:
            prev_equity = equity_curve[-2]['value']
            daily_return = (current_equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_returns.append(daily_return)

        if short_ma > long_ma and position == 0:
            shares = capital / price
            commission = capital * commission_rate
            position = shares
            position_cost = price
            capital = 0
            trades.append({
                'date': date,
                'type': 'BUY',
                'action': 'buy',
                'price': round(price, 2),
                'quantity': round(shares, 2),
                'shares': round(shares, 2),
                'amount': round(shares * price, 2),
                'commission': round(commission, 2),
                'profit': 0,
                'balance': round(current_equity, 2)
            })
        elif short_ma < long_ma and position > 0:
            sell_value = position * price
            commission = sell_value * commission_rate
            capital = sell_value - commission
            profit = (price - position_cost) * position - commission
            trades.append({
                'date': date,
                'type': 'SELL',
                'action': 'sell',
                'price': round(price, 2),
                'quantity': round(position, 2),
                'shares': round(position, 2),
                'amount': round(sell_value, 2),
                'commission': round(commission, 2),
                'profit': round(profit, 2),
                'balance': round(capital, 2),
                'value': round(capital, 2)
            })
            position = 0
            position_cost = 0

    if position > 0:
        final_price = klines[-1]['close']
        sell_value = position * final_price
        commission = sell_value * commission_rate
        capital = sell_value - commission
        profit = (final_price - position_cost) * position - commission
        trades.append({
            'date': klines[-1]['trade_date'],
            'type': 'SELL',
            'action': 'sell',
            'price': round(final_price, 2),
            'quantity': round(position, 2),
            'shares': round(position, 2),
            'amount': round(sell_value, 2),
            'commission': round(commission, 2),
            'profit': round(profit, 2),
            'balance': round(capital, 2),
            'value': round(capital, 2)
        })
        position = 0

    final_capital = capital
    total_return = (final_capital - initial_capital) / initial_capital

    start_date_str = params['start_date']
    end_date_str = params['end_date']
    date_format = '%Y-%m-%d' if '-' in start_date_str else '%Y%m%d'
    start_date = datetime.strptime(start_date_str, date_format)
    end_date = datetime.strptime(end_date_str, date_format)
    trading_days = len(equity_curve)
    total_days = (end_date - start_date).days

    years = total_days / 365.0
    annual_return = (pow(final_capital / initial_capital, 1 / years) - 1) if years > 0 else 0

    max_drawdown = 0
    peak = initial_capital
    drawdown_start = None
    drawdown_end = None
    recovery_days = 0

    for point in equity_curve:
        value = point['value']
        if value > peak:
            peak = value
            if drawdown_start and not drawdown_end:
                drawdown_end = point['date']
        else:
            dd = (peak - value) / peak
            if dd > max_drawdown:
                max_drawdown = dd
                drawdown_start = point['date']
                drawdown_end = None

    if drawdown_start and drawdown_end:
        try:
            start_dt = datetime.strptime(str(drawdown_start), '%Y%m%d')
            end_dt = datetime.strptime(str(drawdown_end), '%Y%m%d')
            recovery_days = (end_dt - start_dt).days
        except:
            recovery_days = 0

    if len(daily_returns) > 1:
        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = math.sqrt(variance)
        sharpe_ratio = (avg_return * math.sqrt(252)) / std_dev if std_dev > 0 else 0
    else:
        sharpe_ratio = 0

    win_trades = 0
    loss_trades = 0
    total_profit = 0
    total_loss = 0
    max_profit = 0
    max_loss = 0

    for trade in trades:
        if trade.get('profit', 0) > 0:
            win_trades += 1
            total_profit += trade['profit']
            max_profit = max(max_profit, trade['profit'])
        elif trade.get('profit', 0) < 0:
            loss_trades += 1
            total_loss += abs(trade['profit'])
            max_loss = min(max_loss, trade['profit'])

    win_rate = win_trades / len(trades) if len(trades) > 0 else 0
    avg_profit = total_profit / win_trades if win_trades > 0 else 0
    avg_loss = total_loss / loss_trades if loss_trades > 0 else 0
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

    monthly_returns = {}
    for i in range(1, len(equity_curve)):
        date_str = str(equity_curve[i]['date'])
        try:
            dt = datetime.strptime(date_str, '%Y%m%d')
            year = dt.year
            month = dt.month

            if year not in monthly_returns:
                monthly_returns[year] = {}

            prev_value = equity_curve[i-1]['value']
            curr_value = equity_curve[i]['value']
            monthly_return = (curr_value - prev_value) / prev_value if prev_value > 0 else 0

            if month not in monthly_returns[year]:
                monthly_returns[year][month] = []
            monthly_returns[year][month].append(monthly_return)
        except:
            continue

    monthly_returns_list = []
    for year in sorted(monthly_returns.keys()):
        months = [0] * 12
        for month, returns in monthly_returns[year].items():
            avg_return = sum(returns) / len(returns) if returns else 0
            months[month - 1] = round(avg_return * 100, 2)
        monthly_returns_list.append({
            'year': year,
            'months': months
        })

    return {
        'strategy_name': params['strategy_name'],
        'symbol': params['symbol'],
        'start_date': params['start_date'],
        'end_date': params['end_date'],
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 2),
        'total_return': round(total_return, 4),
        'annualReturn': round(annual_return, 4),
        'maxDrawdown': round(max_drawdown, 4),
        'sharpeRatio': round(sharpe_ratio, 4),
        'winRate': round(win_rate, 4),
        'profitLossRatio': round(profit_loss_ratio, 4),
        'winTrades': win_trades,
        'lossTrades': loss_trades,
        'avgProfit': round(avg_profit, 2),
        'avgLoss': round(avg_loss, 2),
        'maxProfit': round(max_profit, 2),
        'maxLoss': round(max_loss, 2),
        'recoveryDays': recovery_days,
        'total_trades': len(trades),
        'trades': trades,
        'equityCurve': equity_curve,
        'monthlyReturns': monthly_returns_list
    }


def run_pe_mean_reversion_backtest(params, klines, initial_capital):
    """
    PE均值回归策略回测引擎。

    核心逻辑：
    - 从K线价格估算每日PE（EPS线性插值）
    - PE ≤ pe_heavy_buy → 重仓买入60%
    - PE ≤ pe_batch_buy → 分批买入40%
    - PE ≥ pe_reduce → 减仓到10%
    - PE ≥ pe_liquidate → 清仓
    - 止损 -8% / 止盈 +25%
    """
    from datetime import datetime
    import math

    # ── 策略参数 ──
    eps_start = float(params.get('eps_start', 1.20))
    eps_end = float(params.get('eps_end', 1.48))
    pe_heavy_buy = float(params.get('pe_heavy_buy', 16.0))
    pe_batch_buy = float(params.get('pe_batch_buy', 17.0))
    pe_reduce = float(params.get('pe_reduce', 19.5))
    pe_liquidate = float(params.get('pe_liquidate', 20.5))
    stop_loss_pct = float(params.get('stop_loss_pct', 0.08))
    take_profit_pct = float(params.get('take_profit_pct', 0.25))
    max_position_pct = float(params.get('max_position_pct', 0.60))
    commission_rate = float(params.get('commission_rate', 0.0003))
    dividend_yield = float(params.get('dividend_yield', 0.0))

    if not klines:
        return {'error': 'no_kline_data'}

    # ── 估算每日PE ──
    n = len(klines)
    for i, k in enumerate(klines):
        # 线性插值EPS
        if n > 1:
            eps = eps_start + (eps_end - eps_start) * i / (n - 1)
        else:
            eps = eps_start
        k['pe_est'] = k['close'] / eps if eps > 0 else 20.0

    # ── 确定PE区间 ──
    def get_zone(pe):
        if pe <= pe_heavy_buy:
            return 'heavy_buy'
        elif pe <= pe_batch_buy:
            return 'batch_buy'
        elif pe >= pe_liquidate:
            return 'liquidate'
        elif pe >= pe_reduce:
            return 'reduce'
        return 'hold'

    def zone_to_target_pct(zone):
        mapping = {'heavy_buy': 0.60, 'batch_buy': 0.40, 'hold': 0.30,
                   'reduce': 0.10, 'liquidate': 0.00}
        return mapping.get(zone, 0.30)

    # ── 模拟交易 ──
    capital = initial_capital
    position = 0.0       # 持仓股数
    position_cost = 0.0  # 持仓均价
    trades = []
    equity_curve = []
    daily_returns = []
    prev_zone = None

    for i, k in enumerate(klines):
        pe = k.get('pe_est', 20.0)
        price = k['close']
        date = k['trade_date']
        zone = get_zone(pe)

        # ── 股息每日积累 ──
        dividend_cash = 0.0
        if dividend_yield > 0 and position > 0:
            daily_div_rate = dividend_yield / 252  # 年化 → 每交易日
            dividend_cash = position * price * daily_div_rate
            capital += dividend_cash

        current_equity = capital + (position * price if position > 0 else 0)
        equity_curve.append({'date': date, 'value': round(current_equity, 2)})

        if i > 0:
            prev_equity = equity_curve[-2]['value']
            daily_return = (current_equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_returns.append(daily_return)

        # --- 止损止盈检查 ---
        if position > 0:
            # 止损
            if price <= position_cost * (1 - stop_loss_pct):
                sell_value = position * price
                commission = sell_value * commission_rate
                capital = sell_value - commission
                profit = (price - position_cost) * position - commission
                trades.append({
                    'date': date, 'type': 'SELL', 'action': 'sell',
                    'price': round(price, 2), 'quantity': round(position, 2),
                    'shares': round(position, 2), 'amount': round(sell_value, 2),
                    'commission': round(commission, 2),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2),
                })
                position = 0
                position_cost = 0
                prev_zone = zone
                continue

            # 止盈
            if price >= position_cost * (1 + take_profit_pct):
                sell_value = position * price
                commission = sell_value * commission_rate
                capital = sell_value - commission
                profit = (price - position_cost) * position - commission
                trades.append({
                    'date': date, 'type': 'SELL', 'action': 'sell',
                    'price': round(price, 2), 'quantity': round(position, 2),
                    'shares': round(position, 2), 'amount': round(sell_value, 2),
                    'commission': round(commission, 2),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2),
                })
                position = 0
                position_cost = 0
                prev_zone = zone
                continue

        # --- 区间切换交易 ---
        target_pct = zone_to_target_pct(zone)
        current_pct = (position * price) / current_equity if current_equity > 0 else 0

        # 买入信号：PE从合理/偏高进入低估区
        if zone in ('heavy_buy', 'batch_buy') and position == 0:
            # 全仓买入（按目标仓位）
            buy_capital = capital * min(target_pct * 1.5, max_position_pct)  # 首次买入可稍多
            if buy_capital > 0:
                shares = buy_capital / price
                commission = buy_capital * commission_rate
                position = shares
                position_cost = price
                capital -= buy_capital
                trades.append({
                    'date': date, 'type': 'BUY', 'action': 'buy',
                    'price': round(price, 2), 'quantity': round(shares, 2),
                    'shares': round(shares, 2), 'amount': round(buy_capital, 2),
                    'commission': round(commission, 2), 'profit': 0,
                    'balance': round(capital + position * price, 2),
                })

        # 卖出信号：PE从合理/低估进入高估区
        elif zone in ('reduce', 'liquidate') and position > 0:
            sell_pct = 1.0 if zone == 'liquidate' else 2 / 3  # 清仓 or 减仓2/3
            sell_shares = position * sell_pct
            sell_value = sell_shares * price
            commission = sell_value * commission_rate
            capital += sell_value - commission
            profit = (price - position_cost) * sell_shares - commission
            position -= sell_shares
            trades.append({
                'date': date, 'type': 'SELL', 'action': 'sell',
                'price': round(price, 2), 'quantity': round(sell_shares, 2),
                'shares': round(sell_shares, 2), 'amount': round(sell_value, 2),
                'commission': round(commission, 2),
                'profit': round(profit, 2),
                'balance': round(capital, 2),
            })
            if position < 0.01:
                position = 0
                position_cost = 0

        prev_zone = zone

    # ── 期末清仓 ──
    if position > 0:
        final_price = klines[-1]['close']
        sell_value = position * final_price
        commission = sell_value * commission_rate
        capital += sell_value - commission
        profit = (final_price - position_cost) * position - commission
        trades.append({
            'date': klines[-1]['trade_date'], 'type': 'SELL', 'action': 'sell',
            'price': round(final_price, 2), 'quantity': round(position, 2),
            'shares': round(position, 2), 'amount': round(sell_value, 2),
            'commission': round(commission, 2),
            'profit': round(profit, 2),
            'balance': round(capital, 2),
        })
        position = 0

    # ── 计算指标（与 save_simple_backtest 保持一致）──
    final_capital = capital
    total_return = (final_capital - initial_capital) / initial_capital

    start_date_str = params['start_date']
    end_date_str = params['end_date']
    date_format = '%Y-%m-%d' if '-' in start_date_str else '%Y%m%d'
    start_date = datetime.strptime(start_date_str, date_format)
    end_date = datetime.strptime(end_date_str, date_format)
    total_days = (end_date - start_date).days
    years = total_days / 365.0
    annual_return = (pow(final_capital / initial_capital, 1 / years) - 1) if years > 0 else 0

    max_drawdown = 0
    peak = initial_capital
    drawdown_start = None
    drawdown_end = None
    recovery_days = 0

    for point in equity_curve:
        value = point['value']
        if value > peak:
            peak = value
            if drawdown_start and not drawdown_end:
                drawdown_end = point['date']
        else:
            dd = (peak - value) / peak
            if dd > max_drawdown:
                max_drawdown = dd
                drawdown_start = point['date']
                drawdown_end = None

    if drawdown_start and drawdown_end:
        try:
            start_dt = datetime.strptime(str(drawdown_start), '%Y%m%d')
            end_dt = datetime.strptime(str(drawdown_end), '%Y%m%d')
            recovery_days = (end_dt - start_dt).days
        except:
            recovery_days = 0

    if len(daily_returns) > 1:
        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = math.sqrt(variance)
        sharpe_ratio = (avg_return * math.sqrt(252)) / std_dev if std_dev > 0 else 0
    else:
        sharpe_ratio = 0

    win_trades = 0
    loss_trades = 0
    total_profit = 0
    total_loss = 0
    max_profit = 0
    max_loss = 0

    for trade in trades:
        if trade.get('profit', 0) > 0:
            win_trades += 1
            total_profit += trade['profit']
            max_profit = max(max_profit, trade['profit'])
        elif trade.get('profit', 0) < 0:
            loss_trades += 1
            total_loss += abs(trade['profit'])
            max_loss = min(max_loss, trade['profit'])

    win_rate = win_trades / len(trades) if len(trades) > 0 else 0
    avg_profit = total_profit / win_trades if win_trades > 0 else 0
    avg_loss = total_loss / loss_trades if loss_trades > 0 else 0
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

    monthly_returns = {}
    for i in range(1, len(equity_curve)):
        date_str = str(equity_curve[i]['date'])
        try:
            dt = datetime.strptime(date_str, '%Y%m%d')
            year = dt.year
            month = dt.month
            if year not in monthly_returns:
                monthly_returns[year] = {}
            prev_value = equity_curve[i-1]['value']
            curr_value = equity_curve[i]['value']
            monthly_return = (curr_value - prev_value) / prev_value if prev_value > 0 else 0
            if month not in monthly_returns[year]:
                monthly_returns[year][month] = []
            monthly_returns[year][month].append(monthly_return)
        except:
            continue

    monthly_returns_list = []
    for year in sorted(monthly_returns.keys()):
        months = [0] * 12
        for month, returns in monthly_returns[year].items():
            avg_return = sum(returns) / len(returns) if returns else 0
            months[month - 1] = round(avg_return * 100, 2)
        monthly_returns_list.append({'year': year, 'months': months})

    return {
        'strategy_name': params['strategy_name'],
        'symbol': params['symbol'],
        'start_date': params['start_date'],
        'end_date': params['end_date'],
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 2),
        'total_return': round(total_return, 4),
        'annualReturn': round(annual_return, 4),
        'maxDrawdown': round(max_drawdown, 4),
        'sharpeRatio': round(sharpe_ratio, 4),
        'winRate': round(win_rate, 4),
        'profitLossRatio': round(profit_loss_ratio, 4),
        'winTrades': win_trades,
        'lossTrades': loss_trades,
        'avgProfit': round(avg_profit, 2),
        'avgLoss': round(avg_loss, 2),
        'maxProfit': round(max_profit, 2),
        'maxLoss': round(max_loss, 2),
        'recoveryDays': recovery_days,
        'total_trades': len(trades),
        'trades': trades,
        'equityCurve': equity_curve,
        'monthlyReturns': monthly_returns_list
    }


def run_pb_mean_reversion_backtest(params, klines, initial_capital):
    """
    PB均值回归策略回测引擎。

    核心逻辑：
    - 从 PE × ROE 反推每日PB（EPS线性插值 + ROE均值）
    - PB ≤ pb_heavy_buy → 重仓买入60%
    - PB ≤ pb_batch_buy → 分批买入40%
    - PB ≥ pb_reduce → 减仓到10%
    - PB ≥ pb_liquidate → 清仓
    - 止损 -8% / 止盈 +30%
    """
    from datetime import datetime
    import math

    # ── 策略参数 ──
    eps_start = float(params.get('eps_start', 0.60))
    eps_end = float(params.get('eps_end', 2.40))
    roe_mean = float(params.get('roe_mean', 0.35))
    pb_heavy_buy = float(params.get('pb_heavy_buy', 2.0))
    pb_batch_buy = float(params.get('pb_batch_buy', 2.5))
    pb_reduce = float(params.get('pb_reduce', 4.5))
    pb_liquidate = float(params.get('pb_liquidate', 5.5))
    stop_loss_pct = float(params.get('stop_loss_pct', 0.08))
    take_profit_pct = float(params.get('take_profit_pct', 0.30))
    max_position_pct = float(params.get('max_position_pct', 0.60))
    commission_rate = float(params.get('commission_rate', 0.0003))

    if not klines:
        return {'error': 'no_kline_data'}

    # ── 估算每日PE → PB ──
    n = len(klines)
    for i, k in enumerate(klines):
        if n > 1:
            eps = eps_start + (eps_end - eps_start) * i / (n - 1)
        else:
            eps = eps_start
        pe_est = k['close'] / eps if eps > 0 else 20.0
        k['pb_est'] = pe_est * roe_mean

    # ── 确定PB区间 ──
    def get_zone(pb):
        if pb <= pb_heavy_buy:
            return 'heavy_buy'
        elif pb <= pb_batch_buy:
            return 'batch_buy'
        elif pb >= pb_liquidate:
            return 'liquidate'
        elif pb >= pb_reduce:
            return 'reduce'
        return 'hold'

    def zone_to_target_pct(zone):
        mapping = {'heavy_buy': 0.60, 'batch_buy': 0.40, 'hold': 0.30,
                   'reduce': 0.10, 'liquidate': 0.00}
        return mapping.get(zone, 0.30)

    # ── 模拟交易 ──
    capital = initial_capital
    position = 0.0
    position_cost = 0.0
    trades = []
    equity_curve = []
    daily_returns = []

    for i, k in enumerate(klines):
        pb = k.get('pb_est', 4.0)
        price = k['close']
        date = k['trade_date']
        zone = get_zone(pb)

        current_equity = capital + (position * price if position > 0 else 0)
        equity_curve.append({'date': date, 'value': round(current_equity, 2)})

        if i > 0:
            prev_equity = equity_curve[-2]['value']
            daily_return = (current_equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_returns.append(daily_return)

        # --- 止损止盈检查 ---
        if position > 0:
            if price <= position_cost * (1 - stop_loss_pct):
                sell_value = position * price
                commission = sell_value * commission_rate
                capital = sell_value - commission
                profit = (price - position_cost) * position - commission
                trades.append({
                    'date': date, 'type': 'SELL', 'action': 'sell',
                    'price': round(price, 2), 'quantity': round(position, 2),
                    'shares': round(position, 2), 'amount': round(sell_value, 2),
                    'commission': round(commission, 2),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2),
                })
                position = 0
                position_cost = 0
                continue

            if price >= position_cost * (1 + take_profit_pct):
                sell_value = position * price
                commission = sell_value * commission_rate
                capital = sell_value - commission
                profit = (price - position_cost) * position - commission
                trades.append({
                    'date': date, 'type': 'SELL', 'action': 'sell',
                    'price': round(price, 2), 'quantity': round(position, 2),
                    'shares': round(position, 2), 'amount': round(sell_value, 2),
                    'commission': round(commission, 2),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2),
                })
                position = 0
                position_cost = 0
                continue

        # --- 区间切换交易 ---
        if zone in ('heavy_buy', 'batch_buy') and position == 0:
            buy_capital = capital * min(zone_to_target_pct(zone) * 1.5, max_position_pct)
            if buy_capital > 0:
                shares = buy_capital / price
                commission = buy_capital * commission_rate
                position = shares
                position_cost = price
                capital -= buy_capital
                trades.append({
                    'date': date, 'type': 'BUY', 'action': 'buy',
                    'price': round(price, 2), 'quantity': round(shares, 2),
                    'shares': round(shares, 2), 'amount': round(buy_capital, 2),
                    'commission': round(commission, 2), 'profit': 0,
                    'balance': round(capital + position * price, 2),
                })

        elif zone in ('reduce', 'liquidate') and position > 0:
            sell_pct = 1.0 if zone == 'liquidate' else 2 / 3
            sell_shares = position * sell_pct
            sell_value = sell_shares * price
            commission = sell_value * commission_rate
            capital += sell_value - commission
            profit = (price - position_cost) * sell_shares - commission
            position -= sell_shares
            trades.append({
                'date': date, 'type': 'SELL', 'action': 'sell',
                'price': round(price, 2), 'quantity': round(sell_shares, 2),
                'shares': round(sell_shares, 2), 'amount': round(sell_value, 2),
                'commission': round(commission, 2),
                'profit': round(profit, 2),
                'balance': round(capital, 2),
            })
            if position < 0.01:
                position = 0
                position_cost = 0

    # ── 期末清仓 ──
    if position > 0:
        final_price = klines[-1]['close']
        sell_value = position * final_price
        commission = sell_value * commission_rate
        capital += sell_value - commission
        profit = (final_price - position_cost) * position - commission
        trades.append({
            'date': klines[-1]['trade_date'], 'type': 'SELL', 'action': 'sell',
            'price': round(final_price, 2), 'quantity': round(position, 2),
            'shares': round(position, 2), 'amount': round(sell_value, 2),
            'commission': round(commission, 2),
            'profit': round(profit, 2),
            'balance': round(capital, 2),
        })
        position = 0

    # ── 计算指标 ──
    final_capital = capital
    total_return = (final_capital - initial_capital) / initial_capital

    start_date_str = params['start_date']
    end_date_str = params['end_date']
    date_format = '%Y-%m-%d' if '-' in start_date_str else '%Y%m%d'
    start_date = datetime.strptime(start_date_str, date_format)
    end_date = datetime.strptime(end_date_str, date_format)
    total_days = (end_date - start_date).days
    years = total_days / 365.0
    annual_return = (pow(final_capital / initial_capital, 1 / years) - 1) if years > 0 else 0

    max_drawdown = 0
    peak = initial_capital
    drawdown_start = None
    drawdown_end = None
    recovery_days = 0

    for point in equity_curve:
        value = point['value']
        if value > peak:
            peak = value
            if drawdown_start and not drawdown_end:
                drawdown_end = point['date']
        else:
            dd = (peak - value) / peak
            if dd > max_drawdown:
                max_drawdown = dd
                drawdown_start = point['date']
                drawdown_end = None

    if drawdown_start and drawdown_end:
        try:
            start_dt = datetime.strptime(str(drawdown_start), '%Y%m%d')
            end_dt = datetime.strptime(str(drawdown_end), '%Y%m%d')
            recovery_days = (end_dt - start_dt).days
        except:
            recovery_days = 0

    if len(daily_returns) > 1:
        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = math.sqrt(variance)
        sharpe_ratio = (avg_return * math.sqrt(252)) / std_dev if std_dev > 0 else 0
    else:
        sharpe_ratio = 0

    win_trades = 0
    loss_trades = 0
    total_profit = 0
    total_loss = 0
    max_profit = 0
    max_loss = 0

    for trade in trades:
        if trade.get('profit', 0) > 0:
            win_trades += 1
            total_profit += trade['profit']
            max_profit = max(max_profit, trade['profit'])
        elif trade.get('profit', 0) < 0:
            loss_trades += 1
            total_loss += abs(trade['profit'])
            max_loss = min(max_loss, trade['profit'])

    win_rate = win_trades / len(trades) if len(trades) > 0 else 0
    avg_profit = total_profit / win_trades if win_trades > 0 else 0
    avg_loss = total_loss / loss_trades if loss_trades > 0 else 0
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

    monthly_returns = {}
    for i in range(1, len(equity_curve)):
        date_str = str(equity_curve[i]['date'])
        try:
            dt = datetime.strptime(date_str, '%Y%m%d')
            year = dt.year
            month = dt.month
            if year not in monthly_returns:
                monthly_returns[year] = {}
            prev_value = equity_curve[i-1]['value']
            curr_value = equity_curve[i]['value']
            monthly_return = (curr_value - prev_value) / prev_value if prev_value > 0 else 0
            if month not in monthly_returns[year]:
                monthly_returns[year][month] = []
            monthly_returns[year][month].append(monthly_return)
        except:
            continue

    monthly_returns_list = []
    for year in sorted(monthly_returns.keys()):
        months = [0] * 12
        for month, returns in monthly_returns[year].items():
            avg_return = sum(returns) / len(returns) if returns else 0
            months[month - 1] = round(avg_return * 100, 2)
        monthly_returns_list.append({'year': year, 'months': months})

    return {
        'strategy_name': params['strategy_name'],
        'symbol': params['symbol'],
        'start_date': params['start_date'],
        'end_date': params['end_date'],
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 2),
        'total_return': round(total_return, 4),
        'annualReturn': round(annual_return, 4),
        'maxDrawdown': round(max_drawdown, 4),
        'sharpeRatio': round(sharpe_ratio, 4),
        'winRate': round(win_rate, 4),
        'profitLossRatio': round(profit_loss_ratio, 4),
        'winTrades': win_trades,
        'lossTrades': loss_trades,
        'avgProfit': round(avg_profit, 2),
        'avgLoss': round(avg_loss, 2),
        'maxProfit': round(max_profit, 2),
        'maxLoss': round(max_loss, 2),
        'recoveryDays': recovery_days,
        'total_trades': len(trades),
        'trades': trades,
        'equityCurve': equity_curve,
        'monthlyReturns': monthly_returns_list
    }


