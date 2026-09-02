"""
交易护栏服务 (Trade Guard Service)

职责：集中管理所有交易前校验规则（业务规则层）

设计原则：
1. 所有业务规则集中在领域层
2. 校验失败抛出明确的异常
3. 可独立单元测试
4. 支持规则配置化

重构说明：
    从 AccountTradingService 提取的业务规则，
    符合 DDD 原则（业务规则属于领域层）。

    参考: docs/work-logs/2026-09/quantsys-v2-p2-issues-analysis.md
"""

import structlog
from datetime import date, datetime, time as dt_time
from typing import List, Tuple, Optional

from domain.ports import ISimulationRepository

logger = structlog.get_logger(__name__)

# 导入应用层的 TradingError（领域层可以依赖应用层的异常类型）
from application.services.account_trading_service import TradingError


class TradeGuardService:
    """
    交易护栏服务

    集中管理所有交易前校验：
    - 交易时段校验
    - 每日限额校验
    - 资金/持仓充足性校验
    - 仓位比例校验
    """

    # ========== 交易规则常量 ==========

    # 费率配置
    COMMISSION_RATE = 0.00025      # 佣金万2.5
    COMMISSION_MIN = 5.0           # 最低5元
    STAMP_DUTY_RATE = 0.0005       # 印花税(卖出)
    TRANSFER_FEE_RATE = 0.00001    # 过户费

    # 仓位控制
    MAX_SINGLE_POSITION_RATIO = 0.30   # 单票仓位上限 30%
    MAX_TOTAL_POSITION_RATIO = 0.80    # 总仓位上限 80%

    # 日内限额
    MAX_DAILY_BUY_COUNT = 5              # 单日买入笔数上限
    MAX_DAILY_BUY_AMOUNT_RATIO = 0.50    # 单日买入金额占总资产上限

    # A股交易时段
    TRADING_SESSIONS = (
        (dt_time(9, 30), dt_time(11, 30)),   # 上午盘
        (dt_time(13, 0), dt_time(15, 0)),    # 下午盘
    )

    def __init__(
        self,
        repo: ISimulationRepository,
        calendar=None,
        now_fn=None
    ):
        """
        初始化交易护栏

        Args:
            repo: 仓储接口（查询账户、持仓、历史交易）
            calendar: 交易日历服务（判断交易日）
            now_fn: 时间函数（可注入用于测试）
        """
        self.repo = repo

        if calendar is None:
            from application.services.trading_calendar_service import TradingCalendarService
            calendar = TradingCalendarService()
        self.calendar = calendar

        self.now_fn = now_fn or datetime.now

    # ========== 交易时段校验 ==========

    def validate_trading_window(self, now: Optional[datetime] = None) -> None:
        """
        校验当前是否在交易时段

        规则：
        1. 必须是交易日
        2. 必须在交易时段（9:30-11:30 或 13:00-15:00）

        Args:
            now: 当前时间（None 则使用注入的 now_fn）

        Raises:
            TradingError: 非交易日或非交易时段
        """
        if now is None:
            now = self.now_fn()

        day_str = now.date().isoformat()

        # 校验交易日
        if not self.calendar.is_trading_day(day_str):
            raise TradingError(
                f'非交易日（{day_str}），A股不开市，委托拒绝',
                status_code=422
            )

        # 校验交易时段
        t = now.time()
        if not any(start <= t <= end for start, end in self.TRADING_SESSIONS):
            raise TradingError(
                f'非交易时段（{t.strftime("%H:%M")}），'
                f'A股交易时段为 9:30-11:30 / 13:00-15:00，委托拒绝',
                status_code=422
            )

    def is_in_trading_window(self, now: Optional[datetime] = None) -> bool:
        """
        判断是否在交易时段（不抛异常）

        Args:
            now: 当前时间

        Returns:
            bool: True=在交易时段，False=不在
        """
        try:
            self.validate_trading_window(now)
            return True
        except TradingError:
            return False

    # ========== 每日限额校验 ==========

    def validate_daily_buy_limits(
        self,
        account_name: str,
        trade_amount: float,
        total_value: float
    ) -> None:
        """
        校验账户级日买入限额

        规则：
        1. 单日买入笔数 ≤ MAX_DAILY_BUY_COUNT
        2. 单日买入总金额 ≤ 总资产 × MAX_DAILY_BUY_AMOUNT_RATIO

        Args:
            account_name: 账户名
            trade_amount: 本次交易金额
            total_value: 账户总资产

        Raises:
            TradingError: 超过每日限额
        """
        today = date.today().isoformat()

        # 查询今日已完成的买入交易
        trades = self.repo.get_trades_by_account(
            account_name,
            start_date=today,
            end_date=today
        )
        buys = [t for t in trades if t.action == 'BUY']

        # 校验笔数
        if len(buys) >= self.MAX_DAILY_BUY_COUNT:
            raise TradingError(
                f'单日买入笔数超限: 今日已买 {len(buys)} 笔，'
                f'上限 {self.MAX_DAILY_BUY_COUNT} 笔',
                status_code=422
            )

        # 校验金额
        bought_amount = sum(float(t.amount or 0) for t in buys)
        total_buy_amount = bought_amount + trade_amount

        if total_buy_amount / total_value > self.MAX_DAILY_BUY_AMOUNT_RATIO:
            raise TradingError(
                f'单日买入金额超限: 今日已买 ¥{bought_amount:,.0f}，'
                f'本次 ¥{trade_amount:,.0f}，'
                f'超过总资产 {self.MAX_DAILY_BUY_AMOUNT_RATIO:.0%}',
                status_code=422
            )

    # ========== 资金充足性校验 ==========

    def validate_sufficient_funds(
        self,
        account_name: str,
        symbol: str,
        shares: int,
        price: float
    ) -> dict:
        """
        校验资金充足性（买入）

        Args:
            account_name: 账户名
            symbol: 股票代码
            shares: 买入股数
            price: 买入价格

        Returns:
            dict: 费用明细 {trade_amount, commission, stamp_duty, transfer_fee, total_cost}

        Raises:
            TradingError: 资金不足
        """
        account = self.repo.get_account(account_name)
        if not account:
            raise TradingError(f'账户不存在: {account_name}', status_code=404)

        # 计算费用
        trade_amount = round(price * shares, 2)
        commission = max(round(trade_amount * self.COMMISSION_RATE, 2), self.COMMISSION_MIN)
        stamp_duty = 0.0  # 买入无印花税
        transfer_fee = round(trade_amount * self.TRANSFER_FEE_RATE, 2)
        total_cost = trade_amount + commission + transfer_fee

        # 校验资金
        cash_available = float(account.cash_available)
        if total_cost > cash_available:
            raise TradingError(
                f'可用资金不足: 需要 ¥{total_cost:,.2f}，可用 ¥{cash_available:,.2f}',
                status_code=422
            )

        return {
            'trade_amount': trade_amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'total_cost': total_cost
        }

    # ========== 持仓充足性校验 ==========

    def validate_sufficient_position(
        self,
        account_name: str,
        symbol: str,
        shares: int,
        price: float
    ) -> dict:
        """
        校验持仓充足性（卖出）

        Args:
            account_name: 账户名
            symbol: 股票代码
            shares: 卖出股数
            price: 卖出价格

        Returns:
            dict: 费用明细 + 盈亏信息

        Raises:
            TradingError: 持仓不足
        """
        positions = self.repo.get_all_positions(account_name)
        pos = next((p for p in positions if p.symbol == symbol), None)

        # 校验持仓存在
        if pos is None or pos.shares_total <= 0:
            raise TradingError(
                f'无 {symbol} 持仓，无法卖出',
                status_code=422
            )

        # 校验 T+1 可卖数量
        if shares > pos.shares_available:
            raise TradingError(
                f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股',
                status_code=422,
                details={'sellable_shares': pos.shares_available, 'symbol': symbol}
            )

        # 计算费用和盈亏
        trade_amount = round(price * shares, 2)
        commission = max(round(trade_amount * self.COMMISSION_RATE, 2), self.COMMISSION_MIN)
        stamp_duty = round(trade_amount * self.STAMP_DUTY_RATE, 2)  # 卖出有印花税
        transfer_fee = round(trade_amount * self.TRANSFER_FEE_RATE, 2)

        cost_basis = shares * float(pos.avg_cost)
        realized_pnl = round(
            trade_amount - cost_basis - commission - stamp_duty - transfer_fee,
            2
        )
        realized_pnl_rate = round(realized_pnl / cost_basis, 4) if cost_basis else 0.0

        return {
            'trade_amount': trade_amount,
            'commission': commission,
            'stamp_duty': stamp_duty,
            'transfer_fee': transfer_fee,
            'total_proceeds': trade_amount - commission - stamp_duty - transfer_fee,
            'cost_basis': cost_basis,
            'realized_pnl': realized_pnl,
            'realized_pnl_rate': realized_pnl_rate
        }

    # ========== 仓位比例校验 ==========

    def validate_position_limits(
        self,
        account_name: str,
        symbol: str,
        shares: int,
        price: float,
        max_positions: int = 10
    ) -> None:
        """
        校验仓位比例限制（买入）

        规则：
        1. 单票仓位 ≤ 总资产 × MAX_SINGLE_POSITION_RATIO
        2. 总仓位 ≤ 总资产 × MAX_TOTAL_POSITION_RATIO
        3. 持仓数量 ≤ max_positions

        Args:
            account_name: 账户名
            symbol: 股票代码
            shares: 买入股数
            price: 买入价格
            max_positions: 持仓数量上限

        Raises:
            TradingError: 超过仓位限制
        """
        account = self.repo.get_account(account_name)
        positions = self.repo.get_all_positions(account_name)
        pos = next((p for p in positions if p.symbol == symbol), None)

        # 计算总资产
        position_value = sum(
            float(p.market_value or 0) or float(p.shares_total) * float(p.current_price or p.avg_cost)
            for p in positions
        )
        total_value = float(account.cash_available) + float(account.cash_frozen) + position_value
        if total_value <= 0:
            total_value = float(account.total_value or account.initial_capital or 1)

        trade_amount = shares * price

        # 校验单票仓位
        current_position_value = (
            float(pos.market_value or 0) or float(pos.shares_total) * price
        ) if pos else 0
        new_position_value = current_position_value + trade_amount

        if new_position_value / total_value > self.MAX_SINGLE_POSITION_RATIO:
            raise TradingError(
                f'单票仓位超限: 买入后 {symbol} 市值占比 '
                f'{new_position_value / total_value:.1%} > '
                f'{self.MAX_SINGLE_POSITION_RATIO:.0%}',
                status_code=422
            )

        # 校验持仓数量
        if pos is None and len(positions) >= max_positions:
            raise TradingError(
                f'持仓数量超限: 已持有 {len(positions)} 只，上限 {max_positions}',
                status_code=422
            )

        # 校验总仓位
        new_total_position_value = position_value + trade_amount
        if new_total_position_value / total_value > self.MAX_TOTAL_POSITION_RATIO:
            raise TradingError(
                f'总仓位超限: 买入后持仓占比 '
                f'{new_total_position_value / total_value:.1%} > '
                f'{self.MAX_TOTAL_POSITION_RATIO:.0%}',
                status_code=422
            )

    # ========== 完整交易校验 ==========

    def validate_trade_request(
        self,
        account_name: str,
        action: str,
        symbol: str,
        shares: int,
        price: float,
        max_positions: int = 10,
        allow_off_hours: bool = False
    ) -> dict:
        """
        完整的交易前校验（所有护栏）

        Args:
            account_name: 账户名
            action: 交易方向 ('BUY' | 'SELL')
            symbol: 股票代码
            shares: 股数
            price: 价格
            max_positions: 持仓数量上限
            allow_off_hours: 是否允许盘后交易

        Returns:
            dict: 费用明细和盈亏信息

        Raises:
            TradingError: 任何校验失败
        """
        # 1. 交易时段校验
        if not allow_off_hours:
            self.validate_trading_window()

        # 2. 账户存在性和状态校验
        account = self.repo.get_account(account_name)
        if not account:
            raise TradingError(f'账户不存在: {account_name}', status_code=404)
        if account.status != 'active':
            raise TradingError(
                f'账户已归档，拒绝写操作: {account_name}',
                status_code=409
            )

        # 3. 根据交易方向执行不同校验
        if action == 'BUY':
            # 买入护栏
            trade_amount = shares * price

            # 计算总资产（用于限额校验）
            positions = self.repo.get_all_positions(account_name)
            position_value = sum(
                float(p.market_value or 0) or float(p.shares_total) * float(p.current_price or p.avg_cost)
                for p in positions
            )
            total_value = float(account.cash_available) + float(account.cash_frozen) + position_value
            if total_value <= 0:
                total_value = float(account.total_value or account.initial_capital or 1)

            # 每日限额校验
            self.validate_daily_buy_limits(account_name, trade_amount, total_value)

            # 仓位限制校验
            self.validate_position_limits(account_name, symbol, shares, price, max_positions)

            # 资金充足性校验
            fees = self.validate_sufficient_funds(account_name, symbol, shares, price)

            return fees

        else:  # SELL
            # 卖出护栏
            fees_and_pnl = self.validate_sufficient_position(account_name, symbol, shares, price)

            return fees_and_pnl
