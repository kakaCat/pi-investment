"""
策略回测服务

负责策略回测执行和性能指标计算
"""

import structlog
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

from domain.ports import IStrategyRepository
from domain.backtest.engine.indicator_strategy_executor import IndicatorStrategyExecutor
from domain.backtest.engine.script_strategy_executor import ScriptStrategyExecutor

logger = structlog.get_logger(__name__)


@dataclass
class PositionTier:
    """持仓批次"""
    shares: int           # 该批次股数
    entry_price: float    # 该批次买入价
    tier: int             # 层级 (1/2/3)
    entry_date: str       # 买入日期


class StrategyBacktestService:
    """策略回测服务

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        strategy_repo: Optional[IStrategyRepository] = None,
        indicator_executor: Optional[IndicatorStrategyExecutor] = None,
        script_executor: Optional[ScriptStrategyExecutor] = None,
    ):
        """初始化服务

        Args:
            strategy_repo: 策略仓库（可选）
            indicator_executor: 指标策略执行器（可选）
            script_executor: 脚本策略执行器（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.strategy_repo = strategy_repo
        self.indicator_executor = indicator_executor or IndicatorStrategyExecutor()
        self.script_executor = script_executor or ScriptStrategyExecutor()

    def backtest_indicator_strategy(
        self,
        strategy: Dict,
        klines: List[Dict],
        initial_cash: float = 1000000,
        params_override: Optional[Dict] = None,
        period: Optional[str] = None
    ) -> Dict:
        """
        回测 Indicator 类型策略

        Args:
            strategy: 策略配置字典
            klines: K线数据（已注入因子和财务数据）
            initial_cash: 初始资金
            params_override: 参数覆盖
            period: K线周期（None=日线, '5min'=5分钟线）

        Returns:
            回测结果字典
        """
        try:
            # 1. 执行策略生成信号
            code = strategy['code_content']
            params = params_override if params_override else strategy.get('parsed_params')

            exec_result = self.indicator_executor.execute(
                code=code,
                klines=klines,
                params=params
            )

            signals_df = exec_result.signals
            # 检查 signals_df 是否为空（兼容 pandas 和 polars）
            is_empty = False
            if signals_df is None:
                is_empty = True
            else:
                try:
                    # Pandas DataFrame
                    is_empty = signals_df.empty
                except AttributeError:
                    try:
                        # Polars DataFrame
                        import polars as pl
                        if isinstance(signals_df, pl.DataFrame):
                            is_empty = signals_df.is_empty()
                        else:
                            is_empty = len(signals_df) == 0
                    except (ImportError, AttributeError):
                        is_empty = len(signals_df) == 0

            if is_empty:
                raise ValueError("策略未生成任何信号")

            # 兼容新旧列名（tier列 vs 原buy/sell列）
            buy_sum = 0
            sell_sum = 0
            if 'buy' in signals_df.columns:
                buy_sum = signals_df['buy'].sum()
                sell_sum = signals_df['sell'].sum()
            else:
                for tier in [1, 2, 3]:
                    if f'buy_tier{tier}' in signals_df.columns:
                        buy_sum += signals_df[f'buy_tier{tier}'].sum()
                    if f'sell_tier{tier}' in signals_df.columns:
                        sell_sum += signals_df[f'sell_tier{tier}'].sum()
            logger.info(f"生成信号: {len(signals_df)} 条, buy信号: {buy_sum}, sell信号: {sell_sum}")

            # 1.5. 价格校验（新增）
            price_validation = self._validate_custom_prices(signals_df)

            # 如果有错误（规则3：未来信息），拒绝回测
            if price_validation['errors']:
                error_msg = '价格校验失败: ' + '; '.join(price_validation['errors'])
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'validation_errors': price_validation['errors'],
                    'validation_warnings': price_validation['warnings'],
                    'total_return': 0,
                    'annual_return': 0,
                    'max_drawdown': 0,
                    'sharpe_ratio': 0,
                    'win_rate': 0,
                    'total_trades': 0,
                    'trades': [],
                    'equity_curve': []
                }

            # 如果有警告，记录日志但继续回测
            if price_validation['warnings']:
                logger.warning(f"价格校验警告: {'; '.join(price_validation['warnings'])}")

            # 2. 从信号运行回测
            result = self.run_backtest_from_signals(
                signals_df=signals_df,
                initial_cash=initial_cash,
                period=period
            )

            # 在结果中包含价格校验信息
            result['price_validation'] = price_validation

            return result

        except Exception as e:
            logger.error(f"Indicator策略回测失败: {e}", exc_info=True)
            raise

    def backtest_script_strategy(
        self,
        strategy: Dict,
        klines: List[Dict],
        initial_cash: float = 1000000,
        params_override: Optional[Dict] = None
    ) -> Dict:
        """
        回测 Script 类型策略

        Args:
            strategy: 策略配置字典
            klines: K线数据（已注入因子和财务数据）
            initial_cash: 初始资金
            params_override: 参数覆盖

        Returns:
            回测结果字典
        """
        try:
            code = strategy['code_content']
            params = params_override if params_override else strategy.get('parsed_params')

            exec_result = self.script_executor.execute(
                code=code,
                klines=klines,
                params=params,
                initial_cash=initial_cash
            )

            # Script executor 返回的是完整的回测结果
            return exec_result

        except Exception as e:
            logger.error(f"Script策略回测失败: {e}", exc_info=True)
            raise

    def _normalize_signals(self, signals_df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化信号列，支持向后兼容

        - 如果只有 buy/sell 列，自动转为 buy_tier1/sell_tier1
        - 如果已有 tier 列，补充缺失的 _pct 列

        Args:
            signals_df: 原始信号 DataFrame

        Returns:
            标准化后的信号 DataFrame
        """
        df = signals_df.copy()

        # 检查是否是分批信号
        has_tiered = any(f'buy_tier{i}' in df.columns for i in [1, 2, 3])

        if not has_tiered:
            # 旧格式：转换为 tier1 全仓
            if 'buy' in df.columns:
                df['buy_tier1'] = df['buy']
                df['buy_tier1_pct'] = 1.0

            if 'sell' in df.columns:
                df['sell_tier1'] = df['sell']
                df['sell_tier1_pct'] = 1.0
        else:
            # 新格式：补充缺失的 _pct 列
            for tier in [1, 2, 3]:
                if f'buy_tier{tier}' in df.columns and f'buy_tier{tier}_pct' not in df.columns:
                    # 默认值：tier1=1.0, tier2/3=0.3
                    default_pct = 1.0 if tier == 1 else 0.3
                    df[f'buy_tier{tier}_pct'] = default_pct

                if f'sell_tier{tier}' in df.columns and f'sell_tier{tier}_pct' not in df.columns:
                    # 默认值：tier1=0.5, tier2=0.3, tier3=1.0
                    default_pct = 0.5 if tier == 1 else (0.3 if tier == 2 else 1.0)
                    df[f'sell_tier{tier}_pct'] = default_pct

        return df

    def run_backtest_from_signals(
        self,
        signals_df: pd.DataFrame,
        initial_cash: float = 1000000,
        period: Optional[str] = None
    ) -> Dict:
        """
        从信号 DataFrame 运行回测（支持分批买入/卖出）

        Args:
            signals_df: 包含 buy/sell 信号的 DataFrame
            initial_cash: 初始资金
            period: K线周期（None=日线, '5min'等=分钟线，分钟线启用T+1约束）

        Returns:
            回测结果字典
        """
        # 价格校验（新增）
        price_validation = self._validate_custom_prices(signals_df)

        # 标准化信号列（向后兼容）
        signals_df = self._normalize_signals(signals_df)

        # 初始化
        cash = initial_cash
        position_tiers = []  # List[PositionTier]
        trades = []  # 交易记录
        trade_records = []  # 买卖执行流水
        equity_curve = []  # 权益曲线

        # T+1 约束（仅分钟线启用）
        enable_t1_constraint = period is not None
        bought_today = False
        last_trade_date = None

        for idx, row in signals_df.iterrows():
            date_str = str(row.get('trade_date') or row.get('date', ''))
            close_price = float(row['close'])

            # T+1 约束检查（每个新交易日重置）
            current_date = date_str.split(' ')[0] if ' ' in date_str else date_str
            if enable_t1_constraint and current_date != last_trade_date:
                bought_today = False
                last_trade_date = current_date

            # ========== 卖出逻辑（遍历 tier1/2/3） ==========
            for tier in [1, 2, 3]:
                sig_col = f'sell_tier{tier}'
                pct_col = f'sell_tier{tier}_pct'

                if sig_col in row.index and row.get(sig_col) and position_tiers:
                    # T+1检查
                    if enable_t1_constraint and bought_today:
                        logger.debug(f"T+1约束: {date_str} 今日买入，不能卖出 tier{tier}")
                        continue

                    sell_pct = float(row.get(pct_col, 1.0))

                    if sell_pct >= 0.99:  # 全清
                        total_shares = sum(t.shares for t in position_tiers)
                        total_cost = sum(t.shares * t.entry_price for t in position_tiers)
                        avg_entry = total_cost / total_shares if total_shares > 0 else 0

                        # 读取自定义卖出价格
                        price_col = f'sell_tier{tier}_price'
                        if price_col in row.index and pd.notna(row.get(price_col)):
                            exit_price = float(row.get(price_col))
                        else:
                            exit_price = close_price

                        sell_value = total_shares * exit_price
                        cash += sell_value
                        pnl = sell_value - total_cost
                        pnl_pct = pnl / total_cost if total_cost > 0 else 0
                        trade_records.append({
                            'date': date_str,
                            'action': 'sell',
                            'type': 'SELL',
                            'tier': tier,
                            'price': exit_price,
                            'shares': total_shares,
                            'quantity': total_shares,
                            'amount': sell_value,
                            'cash': cash,
                            'position_shares': 0,
                            'pnl': pnl
                        })

                        # 记录交易（包含tier明细）
                        trades.append({
                            'entry_date': position_tiers[0].entry_date,
                            'exit_date': date_str,
                            'entry_price': avg_entry,
                            'exit_price': exit_price,
                            'shares': total_shares,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'tiers': [
                                {
                                    'tier': t.tier,
                                    'entry_date': t.entry_date,
                                    'entry_price': t.entry_price,
                                    'shares': t.shares,
                                    'exit_date': date_str,
                                    'exit_price': exit_price,
                                    'pnl': t.shares * (exit_price - t.entry_price)
                                }
                                for t in position_tiers
                            ]
                        })

                        logger.debug(f"全清 tier{tier}: {date_str}, 盈亏={pnl:.2f} ({pnl_pct*100:.2f}%)")
                        position_tiers = []

                    else:  # 按比例减仓
                        # 读取自定义卖出价格
                        price_col = f'sell_tier{tier}_price'
                        if price_col in row.index and pd.notna(row.get(price_col)):
                            exit_price = float(row.get(price_col))
                        else:
                            exit_price = close_price

                        sold_tiers = []
                        remaining_tiers = []

                        for pt in position_tiers:
                            # 计算该tier卖出股数
                            sell_shares = int(pt.shares * sell_pct)

                            if sell_shares > 0:
                                sell_value = sell_shares * exit_price
                                cost = sell_shares * pt.entry_price
                                cash += sell_value

                                sold_tiers.append({
                                    'tier': pt.tier,
                                    'entry_date': pt.entry_date,
                                    'entry_price': pt.entry_price,
                                    'shares': sell_shares,
                                    'exit_date': date_str,
                                    'exit_price': exit_price,
                                    'pnl': sell_value - cost
                                })

                                # 更新该tier剩余股数
                                remaining_shares = pt.shares - sell_shares
                                if remaining_shares > 0:
                                    remaining_tiers.append(PositionTier(
                                        shares=remaining_shares,
                                        entry_price=pt.entry_price,
                                        tier=pt.tier,
                                        entry_date=pt.entry_date
                                    ))
                            else:
                                # 不卖出，保留
                                remaining_tiers.append(pt)

                        position_tiers = remaining_tiers

                        # 记录部分卖出交易
                        if sold_tiers:
                            total_sold_shares = sum(t['shares'] for t in sold_tiers)
                            total_sold_cost = sum(t['shares'] * t['entry_price'] for t in sold_tiers)
                            avg_sold_entry = total_sold_cost / total_sold_shares if total_sold_shares > 0 else 0
                            total_pnl = sum(t['pnl'] for t in sold_tiers)
                            pnl_pct = total_pnl / total_sold_cost if total_sold_cost > 0 else 0
                            trade_records.append({
                                'date': date_str,
                                'action': 'sell',
                                'type': 'SELL',
                                'tier': tier,
                                'price': exit_price,
                                'shares': total_sold_shares,
                                'quantity': total_sold_shares,
                                'amount': total_sold_shares * exit_price,
                                'cash': cash,
                                'position_shares': sum(t.shares for t in position_tiers),
                                'pnl': total_pnl
                            })

                            trades.append({
                                'entry_date': sold_tiers[0]['entry_date'],
                                'exit_date': date_str,
                                'entry_price': avg_sold_entry,
                                'exit_price': exit_price,
                                'shares': total_sold_shares,
                                'pnl': total_pnl,
                                'pnl_pct': pnl_pct,
                                'tiers': sold_tiers
                            })

                            logger.debug(f"减仓 tier{tier}: {date_str}, 比例={sell_pct*100:.1f}%, 盈亏={total_pnl:.2f}")

                    # 只执行第一个触发的卖出信号
                    break

            # ========== 买入逻辑（遍历 tier1/2/3） ==========
            for tier in [1, 2, 3]:
                sig_col = f'buy_tier{tier}'
                pct_col = f'buy_tier{tier}_pct'

                if sig_col in row.index and row.get(sig_col):
                    target_pct = float(row.get(pct_col, 0.0))

                    if target_pct > 0 and cash > 0:
                        # 读取自定义买入价格
                        price_col = f'buy_tier{tier}_price'
                        if price_col in row.index and pd.notna(row.get(price_col)):
                            entry_price = float(row.get(price_col))
                        else:
                            entry_price = close_price

                        # 计算该批次分配资金
                        allocated_cash = initial_cash * target_pct
                        shares = int(min(allocated_cash, cash) / entry_price / 100) * 100  # 整百股

                        if shares > 0:
                            cost = shares * entry_price
                            if cash >= cost:
                                cash -= cost

                                position_tiers.append(PositionTier(
                                    shares=shares,
                                    entry_price=entry_price,
                                    tier=tier,
                                    entry_date=date_str
                                ))
                                trade_records.append({
                                    'date': date_str,
                                    'action': 'buy',
                                    'type': 'BUY',
                                    'tier': tier,
                                    'price': entry_price,
                                    'shares': shares,
                                    'quantity': shares,
                                    'amount': cost,
                                    'cash': cash,
                                    'position_shares': sum(t.shares for t in position_tiers)
                                })

                                if enable_t1_constraint:
                                    bought_today = True

                                logger.debug(f"买入 tier{tier}: {date_str}, 价格={entry_price}, "
                                           f"股数={shares}, 比例={target_pct*100:.1f}%")

            # 更新权益曲线
            total_shares = sum(t.shares for t in position_tiers)
            current_equity = cash + (total_shares * close_price)
            equity_curve.append({
                'date': date_str,
                'equity': current_equity,
                'cash': cash,
                'position_value': total_shares * close_price
            })

        # 计算指标
        metrics = self.calculate_metrics_from_trades(
            trades=trades,
            equity_curve=equity_curve,
            initial_cash=initial_cash
        )
        metrics['trade_records'] = trade_records

        # 添加价格校验结果
        metrics['price_validation'] = price_validation

        return metrics

    def calculate_metrics_from_trades(
        self,
        trades: List[Dict],
        equity_curve: List[Dict],
        initial_cash: float
    ) -> Dict:
        """
        从交易记录计算回测指标

        Returns:
            包含所有性能指标的字典
        """
        if not equity_curve:
            return self._empty_metrics()

        # 提取权益序列
        equities = [e['equity'] for e in equity_curve]
        dates = [e['date'] for e in equity_curve]

        # 计算日收益率
        returns = np.diff(equities) / equities[:-1]

        # ==================== 基础指标 ====================
        final_equity = equity_curve[-1]['equity']
        total_return = (final_equity - initial_cash) / initial_cash

        # 年化收益率（假设252个交易日）
        n_days = len(equity_curve)
        n_years = n_days / 252
        annual_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0

        # 最大回撤
        max_drawdown = self.calculate_max_drawdown(equities)

        # ==================== 风险指标 ====================
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0

        # 下行波动率（只考虑负收益）
        negative_returns = returns[returns < 0]
        downside_volatility = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0

        # 夏普比率（假设无风险利率为0）
        sharpe_ratio = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 0 and np.std(returns) > 0 else 0

        # Sortino比率
        sortino_ratio = (np.mean(returns) / np.std(negative_returns) * np.sqrt(252)) if len(negative_returns) > 0 and np.std(negative_returns) > 0 else 0

        # Calmar比率
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # ==================== 交易指标 ====================
        win_rate = self.calculate_win_rate(trades)
        profit_loss_ratio = self.calculate_profit_loss_ratio(trades)
        avg_holding_days = self.calculate_avg_holding_days(trades)
        trade_frequency = len(trades) / n_years if n_years > 0 else 0

        # 最大连续盈利/亏损
        max_consecutive_wins, max_consecutive_losses = self.calculate_consecutive_wins_losses(trades)

        # 盈利因子（总盈利 / 总亏损）
        profit_factor = self.calculate_profit_factor(trades)

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'downside_volatility': downside_volatility,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_holding_days': avg_holding_days,
            'trade_frequency': trade_frequency,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'profit_factor': profit_factor,
            'total_trades': len(trades),
            'trades': trades,
            'equity_curve': equity_curve
        }

    def calculate_max_drawdown(self, equities: List[float]) -> float:
        """计算最大回撤"""
        if not equities or len(equities) < 2:
            return 0.0

        max_equity = equities[0]
        max_dd = 0.0

        for equity in equities:
            if equity > max_equity:
                max_equity = equity
            dd = (equity - max_equity) / max_equity
            if dd < max_dd:
                max_dd = dd

        return max_dd

    def calculate_win_rate(self, trades: List[Dict]) -> float:
        """计算胜率"""
        if not trades:
            return 0.0

        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        return winning_trades / len(trades)

    def calculate_profit_loss_ratio(self, trades: List[Dict]) -> float:
        """计算盈亏比（平均盈利 / 平均亏损）"""
        if not trades:
            return 0.0

        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]

        if not winning_trades or not losing_trades:
            return 0.0

        avg_win = np.mean([t['pnl'] for t in winning_trades])
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades]))

        return avg_win / avg_loss if avg_loss > 0 else 0.0

    def calculate_avg_holding_days(self, trades: List[Dict]) -> float:
        """计算平均持仓天数"""
        if not trades:
            return 0.0

        holding_days = []
        for trade in trades:
            try:
                entry = datetime.strptime(trade['entry_date'].split(' ')[0], '%Y-%m-%d')
                exit = datetime.strptime(trade['exit_date'].split(' ')[0], '%Y-%m-%d')
                days = (exit - entry).days
                holding_days.append(days)
            except Exception:
                logger.debug("unexpected exception in module", exc_info=True)
                continue

        return np.mean(holding_days) if holding_days else 0.0

    def calculate_consecutive_wins_losses(self, trades: List[Dict]) -> tuple:
        """计算最大连续盈利/亏损次数"""
        if not trades:
            return 0, 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            if trade['pnl'] > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade['pnl'] < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def calculate_profit_factor(self, trades: List[Dict]) -> float:
        """计算盈利因子（总盈利 / 总亏损）"""
        if not trades:
            return 0.0

        total_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        total_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))

        return total_profit / total_loss if total_loss > 0 else 0.0

    def _empty_metrics(self) -> Dict:
        """返回空指标"""
        return {
            'total_return': 0,
            'annual_return': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0,
            'max_drawdown': 0,
            'volatility': 0,
            'downside_volatility': 0,
            'win_rate': 0,
            'profit_loss_ratio': 0,
            'avg_holding_days': 0,
            'trade_frequency': 0,
            'max_consecutive_wins': 0,
            'max_consecutive_losses': 0,
            'profit_factor': 0,
            'total_trades': 0,
            'trades': [],
            'equity_curve': []
        }

    def _validate_custom_prices(self, signals_df: pd.DataFrame) -> Dict:
        """
        验证自定义价格列的合理性

        Args:
            signals_df: 包含信号和价格列的DataFrame

        Returns:
            {
                'warnings': [...],  # 警告列表
                'errors': [...]     # 错误列表
            }
        """
        from application.services.strategy_code_validator import StrategyCodeValidator

        validator = StrategyCodeValidator()
        return validator.validate_custom_prices(signals_df)
