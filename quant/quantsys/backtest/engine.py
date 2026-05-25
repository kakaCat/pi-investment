"""
回测引擎 - 事件驱动架构

这是量化系统的核心模块，负责模拟真实交易环境。

核心特性:
- 事件驱动架构 (逐日遍历)
- 涨跌停限制处理
- 停牌处理
- 滑点模型
- 交易成本计算 (佣金+印花税)
- 权益曲线生成
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd


@dataclass
class Order:
    """订单"""
    symbol: str
    date: str
    action: str  # 'buy' or 'sell'
    price: float
    shares: int
    order_type: str = 'market'  # 'market' or 'limit'


@dataclass
class Trade:
    """成交记录"""
    symbol: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    profit: float
    profit_pct: float
    holding_days: int
    entry_reason: str
    exit_reason: str


@dataclass
class Position:
    """持仓"""
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    cost: float  # 总成本 (包括佣金)
    entry_reason: str
    highest_price: float = 0.0  # 用于移动止损


@dataclass
class DailyEquity:
    """每日权益"""
    date: str
    cash: float
    position_value: float
    total_equity: float
    return_pct: float
    drawdown: float


class BacktestEngine:
    """
    事件驱动回测引擎

    核心流程:
    1. 逐日遍历历史数据
    2. 更新持仓市值
    3. 处理挂单 (检查涨跌停/停牌)
    4. 策略计算信号
    5. 生成新订单
    6. 记录权益曲线
    """

    def __init__(
        self,
        initial_capital: float = 1000000,
        commission_rate: float = 0.0003,  # 佣金 0.03%
        stamp_tax_rate: float = 0.001,    # 印花税 0.1% (仅卖出)
        slippage_rate: float = 0.001,     # 滑点 0.1%
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.slippage_rate = slippage_rate

        # 状态
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.pending_orders: List[Order] = []
        self.trades: List[Trade] = []
        self.equity_curve: List[DailyEquity] = []

        # 数据
        self.data: Optional[pd.DataFrame] = None
        self.suspend_data: Dict[str, List[str]] = {}  # 停牌数据

    def run(
        self,
        strategy,
        data: pd.DataFrame,
        start_date: str,
        end_date: str,
    ) -> Dict:
        """
        运行回测

        Args:
            strategy: 策略对象 (需实现calculate_signals方法)
            data: 历史数据 (包含OHLCV)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            回测结果字典
        """
        self.data = data
        self._reset()

        # 生成交易日列表 (仅使用数据中实际存在的日期)
        trading_dates = sorted(data['date'].unique())
        trading_dates = [d for d in trading_dates if start_date <= d <= end_date]

        print(f"[BacktestEngine] 开始回测: {start_date} -> {end_date}")
        print(f"[BacktestEngine] 初始资金: {self.initial_capital:,.0f}")
        print(f"[BacktestEngine] 交易日数量: {len(trading_dates)}")

        # 逐日遍历
        for date in trading_dates:
            # 1. 更新持仓市值
            self._update_positions(date)

            # 2. 处理挂单
            self._process_orders(date)

            # 3. 策略计算信号
            signals = strategy.calculate_signals(date, self.data)

            # 4. 生成订单
            if signals:
                orders = self._generate_orders(signals, date)
                self.pending_orders.extend(orders)

            # 5. 记录权益
            self._record_equity(date)

        # 生成回测报告
        return self._generate_report(start_date, end_date)

    def _reset(self):
        """重置状态"""
        self.cash = self.initial_capital
        self.positions = {}
        self.pending_orders = []
        self.trades = []
        self.equity_curve = []

    def _update_positions(self, date: str):
        """更新持仓市值和最高价"""
        for symbol, position in self.positions.items():
            current_price = self._get_price(symbol, date)
            if current_price and current_price > position.highest_price:
                position.highest_price = current_price

    def _process_orders(self, date: str):
        """
        处理挂单

        检查:
        1. 涨跌停限制
        2. 停牌
        3. 计算滑点
        4. 成交
        """
        executed_orders = []

        for order in self.pending_orders:
            # 检查停牌
            if self._is_suspended(order.symbol, date):
                continue

            # 检查涨跌停
            if order.action == 'buy' and self._is_limit_up(order.symbol, date):
                continue  # 无法买入涨停股
            if order.action == 'sell' and self._is_limit_down(order.symbol, date):
                continue  # 无法卖出跌停股

            # 计算成交价 (含滑点)
            fill_price = self._calculate_fill_price(order, date)

            # 执行订单
            if order.action == 'buy':
                self._execute_buy(order, fill_price, date)
            else:
                self._execute_sell(order, fill_price, date)

            executed_orders.append(order)

        # 移除已执行订单
        for order in executed_orders:
            self.pending_orders.remove(order)

    def _is_suspended(self, symbol: str, date: str) -> bool:
        """检查是否停牌"""
        if symbol in self.suspend_data:
            return date in self.suspend_data[symbol]
        return False

    def _is_limit_up(self, symbol: str, date: str) -> bool:
        """检查是否涨停"""
        current_price = self._get_price(symbol, date)
        prev_price = self._get_price(symbol, date, offset=-1)

        if current_price and prev_price:
            change_pct = (current_price - prev_price) / prev_price
            return change_pct >= 0.099  # 接近10%涨停
        return False

    def _is_limit_down(self, symbol: str, date: str) -> bool:
        """检查是否跌停"""
        current_price = self._get_price(symbol, date)
        prev_price = self._get_price(symbol, date, offset=-1)

        if current_price and prev_price:
            change_pct = (current_price - prev_price) / prev_price
            return change_pct <= -0.099  # 接近-10%跌停
        return False

    def _calculate_fill_price(self, order: Order, date: str) -> float:
        """
        计算成交价 (含滑点)

        买入: 价格上浮
        卖出: 价格下浮
        """
        base_price = self._get_price(order.symbol, date)

        if order.action == 'buy':
            return base_price * (1 + self.slippage_rate)
        else:
            return base_price * (1 - self.slippage_rate)

    def _execute_buy(self, order: Order, fill_price: float, date: str):
        """执行买入"""
        # 计算成本
        amount = fill_price * order.shares
        commission = max(amount * self.commission_rate, 5)  # 最低5元
        total_cost = amount + commission

        # 检查资金
        if total_cost > self.cash:
            print(f"[BacktestEngine] {date} 资金不足，无法买入 {order.symbol}")
            return

        # 扣除资金
        self.cash -= total_cost

        # 创建持仓
        self.positions[order.symbol] = Position(
            symbol=order.symbol,
            entry_date=date,
            entry_price=fill_price,
            shares=order.shares,
            cost=total_cost,
            entry_reason=getattr(order, 'reason', ''),
            highest_price=fill_price
        )

        print(f"[BacktestEngine] {date} 买入 {order.symbol} "
              f"{order.shares}股 @{fill_price:.2f} 成本:{total_cost:,.0f}")

    def _execute_sell(self, order: Order, fill_price: float, date: str):
        """执行卖出"""
        if order.symbol not in self.positions:
            return

        position = self.positions[order.symbol]

        # 计算收益
        amount = fill_price * position.shares
        commission = max(amount * self.commission_rate, 5)
        stamp_tax = amount * self.stamp_tax_rate
        total_proceeds = amount - commission - stamp_tax

        profit = total_proceeds - position.cost
        profit_pct = profit / position.cost

        # 增加资金
        self.cash += total_proceeds

        # 记录交易
        holding_days = (datetime.strptime(date, '%Y-%m-%d') -
                       datetime.strptime(position.entry_date, '%Y-%m-%d')).days

        trade = Trade(
            symbol=order.symbol,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            exit_date=date,
            exit_price=fill_price,
            shares=position.shares,
            profit=profit,
            profit_pct=profit_pct,
            holding_days=holding_days,
            entry_reason=position.entry_reason,
            exit_reason=getattr(order, 'reason', '')
        )
        self.trades.append(trade)

        # 移除持仓
        del self.positions[order.symbol]

        print(f"[BacktestEngine] {date} 卖出 {order.symbol} "
              f"{position.shares}股 @{fill_price:.2f} "
              f"盈亏:{profit:,.0f} ({profit_pct*100:.2f}%)")

    def _generate_orders(self, signals: List[Dict], date: str) -> List[Order]:
        """根据信号生成订单"""
        orders = []

        for signal in signals:
            if signal['action'] == 'buy':
                # 计算买入股数 (简单等权)
                available_cash = self.cash * 0.95  # 保留5%现金
                price = self._get_price(signal['symbol'], date)
                shares = int(available_cash / price / 100) * 100  # 取整到手

                if shares >= 100:
                    order = Order(
                        symbol=signal['symbol'],
                        date=date,
                        action='buy',
                        price=price,
                        shares=shares
                    )
                    order.reason = signal.get('reason', '')
                    orders.append(order)

            elif signal['action'] == 'sell':
                if signal['symbol'] in self.positions:
                    position = self.positions[signal['symbol']]
                    order = Order(
                        symbol=signal['symbol'],
                        date=date,
                        action='sell',
                        price=self._get_price(signal['symbol'], date),
                        shares=position.shares
                    )
                    order.reason = signal.get('reason', '')
                    orders.append(order)

        return orders

    def _record_equity(self, date: str):
        """记录每日权益"""
        # 计算持仓市值
        position_value = 0
        for symbol, position in self.positions.items():
            current_price = self._get_price(symbol, date)
            if current_price:
                position_value += current_price * position.shares

        total_equity = self.cash + position_value

        # 计算收益率
        return_pct = (total_equity - self.initial_capital) / self.initial_capital

        # 计算回撤
        if self.equity_curve:
            peak = max(e.total_equity for e in self.equity_curve)
            drawdown = (total_equity - peak) / peak if peak > 0 else 0
        else:
            drawdown = 0

        equity = DailyEquity(
            date=date,
            cash=self.cash,
            position_value=position_value,
            total_equity=total_equity,
            return_pct=return_pct,
            drawdown=drawdown
        )
        self.equity_curve.append(equity)

    def _get_price(self, symbol: str, date: str, offset: int = 0) -> Optional[float]:
        """获取价格"""
        if self.data is None:
            return None

        try:
            target_date = datetime.strptime(date, '%Y-%m-%d') + timedelta(days=offset)
            target_date_str = target_date.strftime('%Y-%m-%d')

            mask = (self.data['symbol'] == symbol) & (self.data['date'] == target_date_str)
            rows = self.data[mask]

            if not rows.empty:
                return float(rows.iloc[0]['close'])
        except:
            pass

        return None

    def _generate_report(self, start_date: str, end_date: str) -> Dict:
        """生成回测报告"""
        if not self.equity_curve:
            return {}

        final_equity = self.equity_curve[-1].total_equity
        total_return = (final_equity - self.initial_capital) / self.initial_capital

        # 计算年化收益
        days = (datetime.strptime(end_date, '%Y-%m-%d') -
                datetime.strptime(start_date, '%Y-%m-%d')).days
        years = days / 365
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 计算最大回撤
        max_drawdown = min(e.drawdown for e in self.equity_curve)

        # 计算夏普比率
        returns = [e.return_pct for e in self.equity_curve]
        if len(returns) > 1:
            import numpy as np
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0

        # 计算交易指标
        winning_trades = [t for t in self.trades if t.profit > 0]
        losing_trades = [t for t in self.trades if t.profit <= 0]

        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        avg_win = sum(t.profit for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.profit for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        report = {
            'strategy_id': 'backtest',
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': self.initial_capital,
            'final_capital': final_equity,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_holding_days': sum(t.holding_days for t in self.trades) / len(self.trades) if self.trades else 0,
            'trades': [vars(t) for t in self.trades],
            'daily_equity': [vars(e) for e in self.equity_curve]
        }

        print("\n" + "="*60)
        print("回测报告")
        print("="*60)
        print(f"初始资金: {self.initial_capital:,.0f}")
        print(f"最终资金: {final_equity:,.0f}")
        print(f"总收益率: {total_return*100:.2f}%")
        print(f"年化收益率: {annual_return*100:.2f}%")
        print(f"最大回撤: {max_drawdown*100:.2f}%")
        print(f"夏普比率: {sharpe_ratio:.2f}")
        print(f"总交易次数: {len(self.trades)}")
        print(f"胜率: {win_rate*100:.2f}%")
        print(f"盈亏比: {profit_loss_ratio:.2f}")
        print("="*60)

        return report
