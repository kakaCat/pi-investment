"""
Backtest Report Generator

Generates comprehensive backtest reports with performance metrics,
risk analysis, and trade statistics.

DDD Architecture:
- Depends on IRiskMetricsService interface (optional)
- Application layer injects concrete implementation if needed

Updated 2026-06-03: 使用 RiskMetricsService 替换手工计算
Updated 2026-06-26: 添加依赖注入支持
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import json
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics container"""
    # Returns
    total_return: float
    annual_return: float
    monthly_returns: List[float]

    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int

    # Volatility
    volatility: float
    downside_deviation: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_loss_ratio: float
    avg_win: float
    avg_loss: float
    avg_holding_days: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Capital metrics
    initial_capital: float
    final_capital: float
    peak_capital: float

    # Time metrics
    start_date: str
    end_date: str
    trading_days: int


class BacktestReportGenerator:
    """
    Generates comprehensive backtest reports.

    Calculates performance metrics, risk metrics, and trade statistics
    from equity curve and trade history.
    """

    def __init__(self, risk_service: Optional[Any] = None, risk_free_rate: float = 0.03):
        """
        Initialize report generator.

        Args:
            risk_service: Risk metrics service interface (injected by Application layer)
                         If None, uses fallback manual calculations
            risk_free_rate: Annual risk-free rate for Sharpe calculation (default 3%)
        """
        self.risk_free_rate = risk_free_rate
        self.risk_service = risk_service

        if risk_service is not None:
            logger.info(f"BacktestReportGenerator initialized with injected risk_service, rf_rate={risk_free_rate:.2%}")
        else:
            logger.info(f"BacktestReportGenerator initialized with fallback calculations, rf_rate={risk_free_rate:.2%}")

    def generate_report(
        self,
        equity_curve: List[Dict],
        trades: List[Dict],
        initial_capital: float,
        start_date: str,
        end_date: str,
        strategy_name: str = "Strategy",
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive backtest report.

        Args:
            equity_curve: Daily equity data
            trades: Trade history
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date
            strategy_name: Strategy name
            parameters: Strategy parameters

        Returns:
            Complete report dictionary
        """
        logger.info(f"Generating report for {strategy_name}: {start_date} to {end_date}")

        # Calculate metrics
        metrics = self._calculate_metrics(
            equity_curve, trades, initial_capital, start_date, end_date
        )

        # Generate report structure
        report = {
            'strategy_name': strategy_name,
            'parameters': parameters or {},
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'trading_days': metrics.trading_days
            },
            'metrics': asdict(metrics),
            'equity_curve': equity_curve,
            'trades': trades,
            'summary': self._generate_summary(metrics),
            'generated_at': datetime.now().isoformat()
        }

        logger.info(
            f"Report generated: return={metrics.total_return:.2%}, "
            f"sharpe={metrics.sharpe_ratio:.2f}, trades={metrics.total_trades}"
        )

        return report

    def _calculate_metrics(
        self,
        equity_curve: List[Dict],
        trades: List[Dict],
        initial_capital: float,
        start_date: str,
        end_date: str
    ) -> PerformanceMetrics:
        """Calculate all performance metrics"""

        if not equity_curve:
            return self._empty_metrics(initial_capital, start_date, end_date)

        # Extract equity values
        equity_values = [e['total_equity'] for e in equity_curve]
        dates = [e['date'] for e in equity_curve]

        # Calculate returns
        total_return = (equity_values[-1] - initial_capital) / initial_capital

        # Calculate annual return
        days = (datetime.strptime(end_date, "%Y-%m-%d") -
                datetime.strptime(start_date, "%Y-%m-%d")).days
        years = max(days / 365.25, 1 / 365.25)
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0.0

        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(equity_values)):
            ret = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
            daily_returns.append(ret)

        # Calculate monthly returns
        monthly_returns = self._calculate_monthly_returns(equity_curve)

        # Volatility (annualized)
        volatility = np.std(daily_returns) * np.sqrt(252) if daily_returns else 0.0

        # Downside deviation (for Sortino)
        negative_returns = [r for r in daily_returns if r < 0]
        downside_deviation = (
            np.std(negative_returns) * np.sqrt(252) if negative_returns else 0.0
        )

        # 使用 RiskMetricsService 计算风险指标（2026-06-03 更新）
        if self.risk_service is not None and daily_returns:
            try:
                risk_metrics = self.risk_service.calculate_all_metrics(daily_returns)
                sharpe_ratio = risk_metrics['sharpe_ratio']
                sortino_ratio = risk_metrics['sortino_ratio']
                calmar_ratio = risk_metrics['calmar_ratio']
                max_dd = risk_metrics['max_drawdown']
                logger.debug("Using RiskMetricsService for risk calculations")
            except Exception as e:
                logger.warning(f"RiskMetricsService failed: {e}, using fallback")
                # Fallback to manual calculation
                sharpe_ratio, sortino_ratio, calmar_ratio, max_dd = self._calculate_risk_metrics_fallback(
                    annual_return, volatility, downside_deviation, equity_values
                )
        else:
            # Fallback to manual calculation
            sharpe_ratio, sortino_ratio, calmar_ratio, max_dd = self._calculate_risk_metrics_fallback(
                annual_return, volatility, downside_deviation, equity_values
            )

        # Drawdown duration
        _, max_dd_duration = self._calculate_drawdown_metrics(equity_values)

        # Trade statistics
        trade_stats = self._calculate_trade_statistics(trades)

        # Peak capital
        peak_capital = max(equity_values)

        return PerformanceMetrics(
            # Returns
            total_return=round(total_return, 6),
            annual_return=round(annual_return, 6),
            monthly_returns=[round(r, 6) for r in monthly_returns],

            # Risk metrics
            sharpe_ratio=round(sharpe_ratio, 4),
            sortino_ratio=round(sortino_ratio, 4),
            calmar_ratio=round(calmar_ratio, 4),
            max_drawdown=round(max_dd, 6),
            max_drawdown_duration=max_dd_duration,

            # Volatility
            volatility=round(volatility, 6),
            downside_deviation=round(downside_deviation, 6),

            # Trade statistics
            total_trades=trade_stats['total_trades'],
            winning_trades=trade_stats['winning_trades'],
            losing_trades=trade_stats['losing_trades'],
            win_rate=round(trade_stats['win_rate'], 4),
            profit_loss_ratio=round(trade_stats['profit_loss_ratio'], 4),
            avg_win=round(trade_stats['avg_win'], 2),
            avg_loss=round(trade_stats['avg_loss'], 2),
            avg_holding_days=round(trade_stats['avg_holding_days'], 1),
            max_consecutive_wins=trade_stats['max_consecutive_wins'],
            max_consecutive_losses=trade_stats['max_consecutive_losses'],

            # Capital metrics
            initial_capital=round(initial_capital, 2),
            final_capital=round(equity_values[-1], 2),
            peak_capital=round(peak_capital, 2),

            # Time metrics
            start_date=start_date,
            end_date=end_date,
            trading_days=len(equity_curve)
        )

    def _calculate_risk_metrics_fallback(
        self,
        annual_return: float,
        volatility: float,
        downside_deviation: float,
        equity_values: List[float]
    ) -> Tuple[float, float, float, float]:
        """
        Fallback risk metrics calculation (manual)

        Used when RiskMetricsService is not available.

        Returns:
            (sharpe_ratio, sortino_ratio, calmar_ratio, max_drawdown)
        """
        # Sharpe ratio
        if volatility > 0:
            excess_return = annual_return - self.risk_free_rate
            sharpe_ratio = excess_return / volatility
        else:
            sharpe_ratio = 0.0

        # Sortino ratio
        if downside_deviation > 0:
            excess_return = annual_return - self.risk_free_rate
            sortino_ratio = excess_return / downside_deviation
        else:
            sortino_ratio = 0.0

        # Drawdown
        max_dd, _ = self._calculate_drawdown_metrics(equity_values)

        # Calmar ratio
        calmar_ratio = (
            annual_return / abs(max_dd) if max_dd < 0 else 0.0
        )

        return sharpe_ratio, sortino_ratio, calmar_ratio, max_dd

    def _calculate_monthly_returns(self, equity_curve: List[Dict]) -> List[float]:
        """Calculate monthly returns from equity curve"""
        if not equity_curve:
            return []

        # Group by month
        monthly_equity = {}
        for entry in equity_curve:
            date = entry['date']
            month_key = date[:7]  # YYYY-MM
            if month_key not in monthly_equity:
                monthly_equity[month_key] = []
            monthly_equity[month_key].append(entry['total_equity'])

        # Calculate monthly returns
        monthly_returns = []
        sorted_months = sorted(monthly_equity.keys())

        for i in range(1, len(sorted_months)):
            prev_month = sorted_months[i-1]
            curr_month = sorted_months[i]

            prev_equity = monthly_equity[prev_month][-1]
            curr_equity = monthly_equity[curr_month][-1]

            if prev_equity > 0:
                monthly_return = (curr_equity - prev_equity) / prev_equity
                monthly_returns.append(monthly_return)

        return monthly_returns

    def _calculate_drawdown_metrics(self, equity_values: List[float]) -> tuple:
        """Calculate maximum drawdown and duration"""
        if not equity_values:
            return 0.0, 0

        max_dd = 0.0
        max_dd_duration = 0

        peak = equity_values[0]
        peak_idx = 0

        for i, equity in enumerate(equity_values):
            if equity > peak:
                peak = equity
                peak_idx = i

            drawdown = (equity - peak) / peak if peak > 0 else 0.0

            if drawdown < max_dd:
                max_dd = drawdown
                max_dd_duration = i - peak_idx

        return max_dd, max_dd_duration

    def _calculate_trade_statistics(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate trade statistics"""
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_loss_ratio': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'avg_holding_days': 0.0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0
            }

        winning_trades = [t for t in trades if t['profit'] > 0]
        losing_trades = [t for t in trades if t['profit'] <= 0]

        total_trades = len(trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)

        win_rate = win_count / total_trades if total_trades > 0 else 0.0

        avg_win = (
            sum(t['profit'] for t in winning_trades) / win_count
            if win_count > 0 else 0.0
        )

        avg_loss = (
            sum(t['profit'] for t in losing_trades) / loss_count
            if loss_count > 0 else 0.0
        )

        profit_loss_ratio = (
            abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
        )

        avg_holding_days = (
            sum(t['holding_days'] for t in trades) / total_trades
            if total_trades > 0 else 0.0
        )

        # Calculate consecutive wins/losses
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            if trade['profit'] > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)

        return {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_holding_days': avg_holding_days,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses
        }

    def _empty_metrics(
        self,
        initial_capital: float,
        start_date: str,
        end_date: str
    ) -> PerformanceMetrics:
        """Return empty metrics for no-data case"""
        return PerformanceMetrics(
            total_return=0.0,
            annual_return=0.0,
            monthly_returns=[],
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            volatility=0.0,
            downside_deviation=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_loss_ratio=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            avg_holding_days=0.0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            initial_capital=initial_capital,
            final_capital=initial_capital,
            peak_capital=initial_capital,
            start_date=start_date,
            end_date=end_date,
            trading_days=0
        )

    def _generate_summary(self, metrics: PerformanceMetrics) -> str:
        """Generate human-readable summary"""
        summary_lines = [
            f"Backtest Summary ({metrics.start_date} to {metrics.end_date})",
            "=" * 60,
            "",
            "Performance:",
            f"  Total Return: {metrics.total_return:>12.2%}",
            f"  Annual Return: {metrics.annual_return:>11.2%}",
            f"  Sharpe Ratio: {metrics.sharpe_ratio:>12.2f}",
            f"  Sortino Ratio: {metrics.sortino_ratio:>11.2f}",
            f"  Calmar Ratio: {metrics.calmar_ratio:>12.2f}",
            "",
            "Risk:",
            f"  Max Drawdown: {metrics.max_drawdown:>12.2%}",
            f"  Volatility: {metrics.volatility:>14.2%}",
            f"  Downside Dev: {metrics.downside_deviation:>12.2%}",
            "",
            "Trading:",
            f"  Total Trades: {metrics.total_trades:>12}",
            f"  Win Rate: {metrics.win_rate:>16.2%}",
            f"  Profit/Loss Ratio: {metrics.profit_loss_ratio:>6.2f}",
            f"  Avg Holding Days: {metrics.avg_holding_days:>8.1f}",
            "",
            "Capital:",
            f"  Initial: {metrics.initial_capital:>17,.2f}",
            f"  Final: {metrics.final_capital:>19,.2f}",
            f"  Peak: {metrics.peak_capital:>20,.2f}",
        ]

        return "\n".join(summary_lines)

    def export_to_json(self, report: Dict[str, Any], filepath: str):
        """
        Export report to JSON file.

        Args:
            report: Report dictionary
            filepath: Output file path
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Report exported to JSON: {filepath}")

    def export_to_markdown(self, report: Dict[str, Any], filepath: str):
        """
        Export report to Markdown file.

        Args:
            report: Report dictionary
            filepath: Output file path
        """
        metrics = report['metrics']

        md_lines = [
            f"# Backtest Report: {report['strategy_name']}",
            "",
            f"**Period:** {report['period']['start_date']} to {report['period']['end_date']}",
            f"**Trading Days:** {report['period']['trading_days']}",
            "",
            "## Performance Metrics",
            "",
            "### Returns",
            f"- **Total Return:** {metrics['total_return']:.2%}",
            f"- **Annual Return:** {metrics['annual_return']:.2%}",
            "",
            "### Risk-Adjusted Returns",
            f"- **Sharpe Ratio:** {metrics['sharpe_ratio']:.2f}",
            f"- **Sortino Ratio:** {metrics['sortino_ratio']:.2f}",
            f"- **Calmar Ratio:** {metrics['calmar_ratio']:.2f}",
            "",
            "### Risk Metrics",
            f"- **Max Drawdown:** {metrics['max_drawdown']:.2%}",
            f"- **Max DD Duration:** {metrics['max_drawdown_duration']} days",
            f"- **Volatility:** {metrics['volatility']:.2%}",
            f"- **Downside Deviation:** {metrics['downside_deviation']:.2%}",
            "",
            "## Trade Statistics",
            "",
            f"- **Total Trades:** {metrics['total_trades']}",
            f"- **Winning Trades:** {metrics['winning_trades']}",
            f"- **Losing Trades:** {metrics['losing_trades']}",
            f"- **Win Rate:** {metrics['win_rate']:.2%}",
            f"- **Profit/Loss Ratio:** {metrics['profit_loss_ratio']:.2f}",
            f"- **Average Win:** {metrics['avg_win']:.2f}",
            f"- **Average Loss:** {metrics['avg_loss']:.2f}",
            f"- **Average Holding Days:** {metrics['avg_holding_days']:.1f}",
            f"- **Max Consecutive Wins:** {metrics['max_consecutive_wins']}",
            f"- **Max Consecutive Losses:** {metrics['max_consecutive_losses']}",
            "",
            "## Capital",
            "",
            f"- **Initial Capital:** {metrics['initial_capital']:,.2f}",
            f"- **Final Capital:** {metrics['final_capital']:,.2f}",
            f"- **Peak Capital:** {metrics['peak_capital']:,.2f}",
            "",
            "## Strategy Parameters",
            "",
            "```json",
            json.dumps(report['parameters'], indent=2),
            "```",
            "",
            f"*Report generated at: {report['generated_at']}*"
        ]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(md_lines))

        logger.info(f"Report exported to Markdown: {filepath}")
