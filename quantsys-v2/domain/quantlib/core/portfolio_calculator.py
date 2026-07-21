"""
Portfolio Calculator Engine

Calculates portfolio metrics including total assets, P&L, returns, and position statistics.

DDD Architecture:
- Depends on IPortfolioRepository, IKlineRepository, IRiskRepository interfaces
- Application layer injects concrete implementations
"""
import os
from datetime import date, timedelta
from typing import Dict, Optional
import logging

from domain.ports import IPortfolioRepository, IKlineRepository, IRiskRepository

logger = logging.getLogger(__name__)


class PortfolioCalculator:
    """Investment portfolio calculation engine"""

    def __init__(
        self,
        portfolio_repo: Optional[IPortfolioRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
        risk_repo: Optional[IRiskRepository] = None,
        initial_cash: float = None
    ):
        """
        Initialize calculator

        Args:
            portfolio_repo: Portfolio repository interface (injected by Application layer)
            kline_repo: Kline repository interface (injected by Application layer)
            risk_repo: Risk repository interface (injected by Application layer)
            initial_cash: Initial capital, defaults to INITIAL_CASH env var or 1000000.0

        Note:
            Repositories are optional for backward compatibility, but should be injected
        """
        if initial_cash is None:
            initial_cash = float(os.getenv('INITIAL_CASH', 1000000.0))

        self.initial_cash = initial_cash

        # 临时兼容：如果未注入则自动创建（违反 DDD）
        # TODO: 移除后备逻辑，要求调用方必须注入
        if portfolio_repo is None or kline_repo is None or risk_repo is None:
            from adapters.outbound.repositories import (
                PortfolioORMRepository,
                KlineORMRepository,
                RiskORMRepository,
            )
            portfolio_repo = portfolio_repo or PortfolioORMRepository()
            kline_repo = kline_repo or KlineORMRepository()
            risk_repo = risk_repo or RiskORMRepository()

        self.portfolio_repo = portfolio_repo
        self.kline_repo = kline_repo
        self.risk_repo = risk_repo

    def calculate_cash_balance(self, snapshot_date: date) -> float:
        """
        Calculate cash balance up to snapshot date

        Cash = Initial Cash - Buy Amount + Sell Amount - Fees

        Args:
            snapshot_date: Date to calculate cash balance for

        Returns:
            Cash balance
        """
        # Get all trades up to snapshot_date
        trades = self.portfolio_repo.get_trades_by_date(
            start_date='2020-01-01',  # From very early date
            end_date=snapshot_date.strftime('%Y-%m-%d')
        )

        cash = self.initial_cash

        for trade in trades:
            if trade['action'] == 'buy':
                # Buy: decrease cash
                cash -= trade['amount']
                cash -= trade.get('fee', 0.0)
                cash -= trade.get('stamp_duty', 0.0)
            elif trade['action'] == 'sell':
                # Sell: increase cash
                cash += trade['amount']
                cash -= trade.get('fee', 0.0)
                cash -= trade.get('stamp_duty', 0.0)

        return cash

    def calculate_market_value(self, snapshot_date: date) -> float:
        """
        Calculate total market value of holdings as of snapshot date.

        Reconstructs holdings from trade history (not current positions),
        so historical snapshots reflect the portfolio composition at that time.

        Market Value = Σ(quantity × close_price_on_snapshot_date)

        Args:
            snapshot_date: Date to calculate market value for

        Returns:
            Total market value
        """
        holdings = self.portfolio_repo.get_holdings_as_of(
            snapshot_date.strftime('%Y-%m-%d')
        )

        total_market_value = 0.0

        for holding in holdings:
            price = self.kline_repo.get_close_price(
                symbol=holding['symbol'],
                trade_date=snapshot_date
            )

            if price is None:
                logger.warning(
                    f"Price missing for {holding['symbol']} on {snapshot_date}, skipping"
                )
                continue

            market_value = holding['quantity'] * price
            total_market_value += market_value

        return total_market_value

    def get_position_count(self, snapshot_date: date = None) -> int:
        """
        Get number of positions.

        Args:
            snapshot_date: If provided, count positions as of that date from
                           trade history. Otherwise count current holdings.
        """
        if snapshot_date:
            holdings = self.portfolio_repo.get_holdings_as_of(
                snapshot_date.strftime('%Y-%m-%d')
            )
        else:
            holdings = self.portfolio_repo.get_all_holdings()
        return len(holdings)

    def calculate_snapshot(self, snapshot_date: str) -> Dict:
        """
        Calculate complete account snapshot for given date

        Args:
            snapshot_date: Date string (YYYY-MM-DD) to calculate snapshot for

        Returns:
            Complete snapshot dictionary
        """
        # Convert string to date object for calculations
        from datetime import datetime
        date_obj = datetime.strptime(snapshot_date, '%Y-%m-%d').date()

        # 1. Calculate cash and market value
        cash = self.calculate_cash_balance(date_obj)
        market_value = self.calculate_market_value(date_obj)
        total_assets = cash + market_value

        # 2. Get previous day's assets for daily return calculation
        previous_date = date_obj - timedelta(days=1)
        previous_balance = self.risk_repo.get_balance_by_date(previous_date.strftime('%Y-%m-%d'))

        if previous_balance:
            previous_assets = previous_balance['total_assets']
            daily_pnl = total_assets - previous_assets
            daily_return = (daily_pnl / previous_assets) * 100 if previous_assets > 0 else 0.0
        else:
            daily_pnl = 0.0
            daily_return = 0.0

        # 3. Calculate total P&L
        total_pnl = total_assets - self.initial_cash
        total_return = (total_pnl / self.initial_cash) * 100 if self.initial_cash > 0 else 0.0

        # 4. Get position count (as of snapshot date)
        position_count = self.get_position_count(date_obj)

        # 5. Assemble snapshot
        snapshot = {
            'balance_date': snapshot_date,
            'cash': cash,
            'market_value': market_value,
            'total_assets': total_assets,
            'daily_pnl': daily_pnl,
            'daily_return': daily_return,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'position_count': position_count
        }

        return snapshot
