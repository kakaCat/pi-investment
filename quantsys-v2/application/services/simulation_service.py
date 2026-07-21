"""
模拟交易服务

提供策略执行、账户管理等业务逻辑
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from domain.strategies import get_registry, Signal
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository


class SimulationService:
    """模拟交易服务"""
    
    def __init__(self):
        self.registry = get_registry()
        self.repo = SimulationORMRepository()
        self.logger = logging.getLogger(__name__)
    
    def list_strategies(self) -> List[Dict]:
        """
        列出所有可用策略
        
        Returns:
            List[Dict]: 策略列表
        """
        return self.registry.list_all()
    
    def get_strategy_info(self, strategy_id: str) -> Optional[Dict]:
        """
        获取策略详情
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            Dict: 策略详情，不存在则返回None
        """
        strategy = self.registry.get(strategy_id)
        if not strategy:
            return None
        
        metadata = strategy.get_metadata()
        metadata['id'] = strategy_id
        metadata['is_initialized'] = strategy.is_initialized
        return metadata
    
    def run_strategy(
        self,
        strategy_id: str,
        account_name: str,
        force_rebalance: bool = False
    ) -> Dict[str, Any]:
        """
        执行策略
        
        Args:
            strategy_id: 策略ID
            account_name: 账户名称
            force_rebalance: 是否强制调仓
            
        Returns:
            Dict: 执行结果
        """
        strategy = self.registry.get(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found")
        
        # 初始化策略
        if not strategy.is_initialized:
            self.logger.info(f"Initializing strategy: {strategy_id}")
            strategy.initialize()
        
        # 获取账户信息
        account = self.repo.get_account(account_name)
        if not account:
            raise ValueError(f"Account '{account_name}' not found")

        # 判断是否需要调仓
        current_date = datetime.now().strftime('%Y-%m-%d')
        last_rebalance = str(account.last_rebalance_date) if account.last_rebalance_date else None

        # 检查是否有持仓（空仓时每天都可以调仓）
        positions = self.repo.get_all_positions(account_name)
        has_positions = len(positions) > 0

        should_rebalance = force_rebalance or strategy.should_rebalance(last_rebalance, current_date, has_positions)
        
        if not should_rebalance:
            return {
                'success': True,
                'action': 'skip',
                'message': f'No rebalance needed. Last rebalance: {last_rebalance}',
                'last_rebalance_date': last_rebalance,
                'next_rebalance_days': strategy.config.rebalance_days
            }
        
        # 计算交易信号
        self.logger.info(f"Calculating signals for {strategy_id}...")
        signals = strategy.calculate_signals(current_date, account_name)
        
        # 验证信号
        valid_signals = strategy.validate_signals(signals)
        
        self.logger.info(f"Generated {len(valid_signals)} valid signals")
        
        # 执行交易
        trades = self._execute_trades(valid_signals, account_name, current_date)
        
        # 更新账户
        self.repo.update_last_rebalance_date(account_name, current_date)
        
        return {
            'success': True,
            'action': 'rebalance',
            'strategy_id': strategy_id,
            'strategy_name': strategy.config.name,
            'date': current_date,
            'signals_count': len(valid_signals),
            'trades_count': len(trades),
            'trades': [self._trade_to_dict(t) for t in trades]
        }
    
    def get_account_status(self, account_name: str) -> Dict:
        """
        获取账户状态

        Args:
            account_name: 账户名称

        Returns:
            Dict: 账户状态
        """
        account = self.repo.get_account(account_name)
        if not account:
            raise ValueError(f"Account '{account_name}' not found")

        positions = self.repo.get_all_positions(account_name)

        # 更新持仓价格
        if positions:
            self.logger.info(f"Updating prices for {len(positions)} positions")
            try:
                symbols = [p.symbol for p in positions]
                prices = self._fetch_current_prices(symbols)
                if prices:
                    self.repo.update_position_prices(account_name, prices)
                    self.logger.info(f"Updated {len(prices)} position prices")
                    # 重新获取positions以获取更新后的价格
                    positions = self.repo.get_all_positions(account_name)
                    account = self.repo.get_account(account_name)
                else:
                    self.logger.warning("No prices fetched")
            except Exception as e:
                self.logger.error(f"Failed to update position prices: {e}", exc_info=True)

        return {
            'account_name': account_name,
            'display_name': getattr(account, 'display_name', None),
            'strategy_name': getattr(account, 'strategy_name', None),
            'cash_available': float(getattr(account, 'cash_available', 0) or 0),
            'cash_frozen': float(getattr(account, 'cash_frozen', 0) or 0),
            'position_value': float(getattr(account, 'position_value', 0) or 0),
            'total_value': float(getattr(account, 'total_value', 0) or 0),
            'initial_capital': float(getattr(account, 'initial_capital', 0) or 0),
            'cumulative_return': float(getattr(account, 'cumulative_return', 0) or 0),
            'last_rebalance_date': str(getattr(account, 'last_rebalance_date', None)) if getattr(account, 'last_rebalance_date', None) else None,
            'positions_count': len(positions),
            'positions': [self._position_to_dict(p) for p in positions]
        }

    def _fetch_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        获取股票当前价格

        Args:
            symbols: 股票代码列表

        Returns:
            Dict[str, float]: {symbol: price}
        """
        try:
            from application.services.realtime_quote_service import RealtimeQuoteService
            quote_service = RealtimeQuoteService()
            prices = {}
            for symbol in symbols:
                try:
                    quote = quote_service.get_realtime_quote(symbol)
                    if quote and quote.price and quote.price > 0:
                        prices[symbol] = float(quote.price)
                        self.logger.info(f"Updated price for {symbol}: {quote.price}")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch price for {symbol}: {e}")
            return prices
        except Exception as e:
            self.logger.error(f"Error fetching prices: {e}")
            return {}
    
    def get_trades(
        self,
        account_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取交易记录

        Args:
            account_name: 账户名称
            start_date: 开始日期
            end_date: 结束日期
            limit: 最大返回数量

        Returns:
            List[Dict]: 交易记录列表
        """
        try:
            trades = self.repo.get_trades_by_account(account_name, start_date, end_date)
            # 应用limit限制
            if trades and limit:
                trades = trades[:limit]
            return [self._trade_to_dict(t) for t in (trades or [])]
        except Exception as e:
            self.logger.error(f"Error getting trades: {e}")
            return []
    
    def _execute_trades(self, signals: List[Signal], account_name: str, date: str) -> List[Dict]:
        """
        执行交易（简化版，实际需要调用SimulationTrader）
        
        Args:
            signals: 交易信号列表
            account_name: 账户名称
            date: 交易日期
            
        Returns:
            List[Dict]: 交易记录
        """
        # TODO: 这里应该调用实际的SimulationTrader执行交易
        # 目前返回空列表，后续实现
        self.logger.warning("_execute_trades not fully implemented yet")
        return []
    
    def _trade_to_dict(self, trade) -> Dict:
        """将交易记录转换为字典（前端兼容格式）"""
        if isinstance(trade, dict):
            return trade

        # 获取基础字段
        symbol = getattr(trade, 'symbol', None)
        action = getattr(trade, 'action', None)
        shares = getattr(trade, 'shares', None)
        filled_price = getattr(trade, 'filled_price', None)
        trade_date = getattr(trade, 'trade_date', None)
        trade_time = getattr(trade, 'trade_time', None)

        # 查询股票名称
        stock_name = None
        if symbol and self.repo:
            try:
                from infrastructure.persistence.orm.models import Stock
                from sqlalchemy import select
                stmt = select(Stock.name).where(Stock.symbol == symbol)
                result = self.repo.session.execute(stmt).scalar()
                stock_name = result if result else None
            except Exception as e:
                self.logger.warning(f"Failed to fetch stock name for {symbol}: {e}")

        # 构造时间戳（优先使用trade_time，否则用trade_date）
        timestamp = None
        if trade_time:
            timestamp = trade_time.isoformat() if hasattr(trade_time, 'isoformat') else str(trade_time)
        elif trade_date:
            timestamp = trade_date.isoformat() if hasattr(trade_date, 'isoformat') else str(trade_date)

        # 计算金额
        amount = None
        if filled_price and shares:
            amount = float(filled_price) * int(shares)

        return {
            'symbol': symbol,
            'name': stock_name,  # 添加公司名称
            'action': action.upper() if action else None,  # 统一大写
            'shares': shares,
            'price': float(filled_price) if filled_price else None,  # 前端期望price字段
            'filled_price': float(filled_price) if filled_price else None,  # 保留原字段兼容性
            'amount': amount,  # 计算金额
            'timestamp': timestamp,  # 前端期望timestamp字段
            'trade_date': trade_date.isoformat() if hasattr(trade_date, 'isoformat') else str(trade_date) if trade_date else None,
            'commission': float(getattr(trade, 'commission', 0) or 0),
            'stamp_duty': float(getattr(trade, 'stamp_duty', 0) or 0),
            'total_cost': float(getattr(trade, 'total_cost', 0) or 0) if action and action.upper() == 'BUY' else None,
            'total_revenue': float(getattr(trade, 'total_revenue', 0) or 0) if action and action.upper() == 'SELL' else None,
            'realized_pnl': float(trade.realized_pnl) if getattr(trade, 'realized_pnl', None) is not None else None,
            'realized_pnl_rate': float(trade.realized_pnl_rate) if getattr(trade, 'realized_pnl_rate', None) is not None else None,
            'reason': getattr(trade, 'reason', None),
        }
    
    def _position_to_dict(self, position) -> Dict:
        """将持仓记录转换为字典"""
        if isinstance(position, dict):
            return position
        return {
            'symbol': getattr(position, 'symbol', None),
            'shares_total': getattr(position, 'shares_total', None),
            'shares_available': getattr(position, 'shares_available', None),
            'avg_cost': float(position.avg_cost) if getattr(position, 'avg_cost', None) else None,
            'current_price': float(position.current_price) if getattr(position, 'current_price', None) else None,
            'market_value': float(position.market_value) if getattr(position, 'market_value', None) else None,
            'profit_total': float(position.profit_total) if getattr(position, 'profit_total', None) else None,
            'profit_total_rate': float(position.profit_total_rate) if getattr(position, 'profit_total_rate', None) else None,
            'profit_today': float(position.profit_today) if getattr(position, 'profit_today', None) else None,
        }
