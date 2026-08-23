"""Strategy execution service - unified strategy execution interface"""
from domain.ports import IKlineRepository, ISignalRepository, IStockRepository, IStrategyRepository
import structlog
import time
import uuid
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

# 已迁移到ORM，不再需要此导入
from domain.backtest.engine.strategy_factory import StrategyFactory
from adapters.outbound.repositories.models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
)

logger = structlog.get_logger(__name__)


class StrategyEngine:
    """Wrapper for strategy execution using real kline data and strategy logic"""

    def __init__(self, strategy_name: str, kline_repo=None, stock_repo=None, strategy_repo=None):
        self.strategy_name = strategy_name
        self._kline_repo = kline_repo
        self._stock_repo = stock_repo
        self._strategy_repo = strategy_repo

        # Track whether this is a DB strategy or Python strategy
        self.is_db_strategy = False
        self.db_strategy_config = None
        self.strategy = None

        # Auto-discover strategies if not already done
        if not StrategyFactory._registry:
            StrategyFactory.auto_discover()

        # Try to find Python strategy first
        available = StrategyFactory.list_all()
        if strategy_name in available:
            self.strategy = StrategyFactory.create(strategy_name)
            self.is_db_strategy = False
        else:
            # Not found in Python strategies, try database
            if self._strategy_repo is None:
                from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
                strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
            else:
                strategy_repo = self._strategy_repo
            db_strategy = strategy_repo.get_by_name(strategy_name)

            # Also try numeric ID lookup (for strategy_execute with numeric IDs)
            if not db_strategy and strategy_name.isdigit():
                db_strategy = strategy_repo.get_by_id(int(strategy_name))

            if db_strategy and db_strategy.get('code_type') == 'indicator':
                # Found DB indicator strategy
                self.is_db_strategy = True
                self.db_strategy_config = db_strategy
                logger.info(f"使用数据库策略: {strategy_name} (indicator)")
            else:
                # Not found anywhere
                raise ValueError(
                    f"策略不存在: {strategy_name}，可用Python策略: {available}"
                )

    @property
    def kline_repo(self):
        """延迟加载 kline_repo"""
        if self._kline_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            self._kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
        return self._kline_repo

    @property
    def stock_repo(self):
        """延迟加载 stock_repo"""
        if self._stock_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            self._stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
        return self._stock_repo

    def execute(self, symbol: str, date: str = None) -> Dict:
        """
        Execute real strategy on kline data.

        Args:
            symbol: Stock symbol (e.g., '600519')
            date: Target date (YYYY-MM-DD), default today

        Returns:
            Signal dict with signal_type, confidence, entry_price, etc.
        """
        # Normalize symbol
        if '.' in symbol:
            symbol = symbol.split('.')[0]

        # Validate stock exists in DB
        stock_info = self.stock_repo.get_by_symbol(symbol)
        if not stock_info:
            raise ValueError(
                f"股票不存在: {symbol}"
            )

        stock_name = stock_info.name

        # Determine date range for klines
        if date:
            end_date = date
        else:
            end_date = datetime.now().strftime('%Y-%m-%d')

        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=400)).strftime('%Y-%m-%d')

        # Fetch klines
        klines = self.kline_repo.get_range(symbol, start_date, end_date)
        # 🔧 兼容 Polars DataFrame（get_range 可能返回 pl.DataFrame）
        try:
            import polars as pl
            is_polars = isinstance(klines, pl.DataFrame)
            is_empty = klines.is_empty() if is_polars else (not klines)
            klines_len = len(klines)
        except ImportError:
            is_polars = False
            is_empty = not klines
            klines_len = len(klines) if klines else 0
        if is_empty or klines_len < 2:
            return {
                'symbol': symbol,
                'name': stock_name,
                'signal_type': 'HOLD',
                'confidence': 0.0,
                'entry_price': None,
                'reason': f'K线数据不足（{klines_len}条）',
                'indicators': {},
                'timestamp': end_date
            }

        # 🔧 统一转换为 List[Dict]（polars DataFrame 转为 dicts，下游代码只支持 list-of-dict 格式）
        if is_polars:
            klines = klines.to_dicts()

        # Execute strategy based on type
        try:
            if self.is_db_strategy:
                # Execute DB indicator strategy
                result = self._execute_db_indicator(klines)
            else:
                # Execute Python strategy
                strategy_meta = StrategyFactory.get_info(self.strategy_name)
                params = strategy_meta.get('default_params', {}) if strategy_meta else {}
                result = self.strategy.generate_signal(klines, params)
        except Exception as e:
            logger.error(f"策略执行失败 [{self.strategy_name}/{symbol}]: {e}")
            return {
                'symbol': symbol,
                'name': stock_name,
                'signal_type': 'HOLD',
                'confidence': 0.0,
                'entry_price': None,
                'reason': f'策略执行异常: {str(e)}',
                'indicators': {},
                'timestamp': end_date
            }

        # Normalize action naming
        action = str(result.get('action', 'hold')).upper()
        if action not in ('BUY', 'SELL', 'HOLD'):
            action = 'HOLD'

        # Get latest price
        latest_close = float(klines[-1].get('close', 0)) if klines else 0

        # Use custom price if available, otherwise use close
        entry_price = result.get('custom_price', latest_close)

        return {
            'symbol': symbol,
            'name': stock_name,
            'signal_type': action,
            'confidence': float(result.get('confidence', 0.0)),
            'entry_price': entry_price,
            'stop_loss': result.get('stop_loss'),
            'target_price': result.get('target_price'),
            'reason': result.get('reason', ''),
            'indicators': result.get('indicators', {}),
            'timestamp': end_date
        }

    def _execute_db_indicator(self, klines: List[Dict]) -> Dict:
        """
        Execute database-stored indicator strategy.

        Args:
            klines: K-line data

        Returns:
            Result dict with action, confidence, etc. (compatible with Python strategy format)
        """
        from domain.backtest.engine.indicator_strategy_executor import IndicatorStrategyExecutor

        executor = IndicatorStrategyExecutor()
        code = self.db_strategy_config['code_content']
        params = self.db_strategy_config.get('parsed_params')

        # Execute indicator code
        exec_result = executor.execute(code=code, klines=klines, params=params)
        signals_df = exec_result.signals

        from infrastructure.utils.dataframe_utils import is_dataframe_empty
        if is_dataframe_empty(signals_df):
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': 'No signal generated'
            }

        # Get last row signal
        last_row = signals_df.iloc[-1]
        has_buy = bool(last_row.get('buy', False))  # Convert pandas bool to Python bool
        has_sell = bool(last_row.get('sell', False))  # Convert pandas bool to Python bool

        # Determine custom price for buy/sell (check tier1 first, fallback to close)
        custom_price = None
        if has_buy and 'buy_tier1_price' in last_row.index and pd.notna(last_row.get('buy_tier1_price')):
            custom_price = float(last_row.get('buy_tier1_price'))
        elif has_sell and 'sell_tier1_price' in last_row.index and pd.notna(last_row.get('sell_tier1_price')):
            custom_price = float(last_row.get('sell_tier1_price'))

        if has_buy:
            action = 'buy'
            confidence = last_row.get('confidence', 0.7)
        elif has_sell:
            action = 'sell'
            confidence = last_row.get('confidence', 0.7)
        else:
            action = 'hold'
            confidence = 0.0

        # Extract indicators from last row (exclude buy/sell/price columns)
        indicators = {}
        exclude_cols = {'buy', 'sell', 'open', 'high', 'low', 'close', 'volume', 'trade_date', 'date'}
        for col in signals_df.columns:
            if col not in exclude_cols:
                val = last_row.get(col)
                if val is not None and not (isinstance(val, float) and str(val) == 'nan'):
                    # Convert pandas/numpy types to Python native types for JSON serialization
                    if isinstance(val, bool) or hasattr(val, 'dtype') and val.dtype == 'bool':
                        indicators[col] = bool(val)
                    elif isinstance(val, (int, float)):
                        indicators[col] = float(val)
                    else:
                        indicators[col] = val

        result = {
            'action': action,
            'confidence': float(confidence),
            'reason': f'Indicator signal from {self.strategy_name}',
            'indicators': indicators
        }

        # Add custom price if available
        if custom_price is not None:
            result['custom_price'] = custom_price

        return result


class StrategyExecutionService:
    """Strategy execution service - handles single, batch, and pipeline execution"""

    def __init__(self, signal_repo=None):
        self._signal_repo = signal_repo

    @property
    def signal_repo(self):
        """延迟加载 signal_repo"""
        if self._signal_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            self._signal_repo = EnhancedServiceFactory.resolve(ISignalRepository)
        return self._signal_repo

    def execute_single(self, request: Dict) -> Dict:
        """Execute single stock strategy"""
        # Initialize strategy engine
        engine = StrategyEngine(request.strategy_name)

        # Execute strategy
        signal = engine.execute(
            symbol=request.symbol,
            date=request.date
        )

        # Persist if requested
        if request.persist:
            signal_date = request.date or datetime.now().strftime('%Y-%m-%d')

            # Look up strategy_id from strategy_configs table
            strategy_id = self._get_strategy_id(request.strategy_name)

            # Store signal in database
            signal_id = self.signal_repo.create_signal({
                'signal_date': signal_date,
                'symbol': request.symbol,
                'name': request.strategy_name,
                'action': signal['signal_type'],
                'action_type': 1,
                'strategy_id': strategy_id,
                'price': signal.get('entry_price'),
                'reason': signal.get('reason', ''),
                'confidence': signal.get('confidence', 0.0),
                'indicators': signal.get('indicators')
            })

            signal['signal_id'] = signal_id

        return signal

    def execute_batch(self, request: Dict) -> Generator[Dict, None, None]:
        """Batch execute strategies (streaming response)"""
        start_time = time.time()

        # Deduplicate symbols
        symbols = list(set(request.symbols))

        # Concurrent execution
        max_workers = min(10, len(symbols))
        success_count = 0
        failed_count = 0
        signal_distribution = {'BUY': 0, 'SELL': 0, 'HOLD': 0}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_symbol = {
                executor.submit(
                    self._execute_single_for_batch,
                    symbol,
                    request.strategy_name,
                    request.date,
                    request.persist
                ): symbol
                for symbol in symbols
            }

            # Yield results as they complete
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    signal = future.result()

                    # Filter by confidence
                    if request.min_confidence and signal['confidence'] < request.min_confidence:
                        continue

                    success_count += 1
                    signal_distribution[signal['signal_type']] += 1

                    yield {
                        'type': 'signal',
                        'data': signal
                    }

                except Exception as e:
                    failed_count += 1
                    yield {
                        'type': 'error',
                        'data': {
                            'symbol': symbol,
                            'error': str(e)
                        }
                    }

        # Return summary
        duration_ms = int((time.time() - start_time) * 1000)
        yield {
            'type': 'summary',
            'data': {
                'total': len(symbols),
                'success': success_count,
                'failed': failed_count,
                'buy': signal_distribution['BUY'],
                'sell': signal_distribution['SELL'],
                'hold': signal_distribution['HOLD'],
                'duration_ms': duration_ms
            }
        }

    def execute_pipeline(self, request: Dict) -> Dict:
        """Execute complete pipeline: strategy → signal → risk → orders"""
        start_time = time.time()
        execution_date = datetime.now().strftime('%Y-%m-%d')

        # Statistics
        signals_generated = 0
        signals_approved = 0
        signals_rejected = 0
        orders_created = 0
        rejection_reasons = {}
        orders = []

        # Batch execute strategies
        batch_request = StrategyBatchExecuteRequest(
            symbols=request.symbols,
            strategy_name=request.strategy_name,
            persist=True  # Pipeline mode forces persistence
        )

        for item in self.execute_batch(batch_request):
            if item['type'] == 'signal':
                signal = item['data']
                signals_generated += 1

                # Risk check (placeholder - will implement in Task 4)
                if request.risk_check:
                    # For now, approve all signals
                    risk_approved = True
                    risk_reason = None
                else:
                    risk_approved = True
                    risk_reason = None

                if risk_approved:
                    signals_approved += 1

                    # Create orders if requested
                    if request.create_orders and signal['signal_type'] in ['BUY', 'SELL']:
                        order = self._create_order_from_signal(signal)
                        orders.append(order)
                        orders_created += 1
                else:
                    signals_rejected += 1
                    reason = risk_reason or 'unknown'
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            'execution_date': execution_date,
            'duration_ms': duration_ms,
            'signals_generated': signals_generated,
            'signals_approved': signals_approved,
            'signals_rejected': signals_rejected,
            'orders_created': orders_created,
            'rejection_reasons': rejection_reasons,
            'orders': orders
        }

    def _execute_single_for_batch(self, symbol: str, strategy_name: str,
                                   date: str, persist: bool) -> Dict:
        """Execute single stock for batch mode (internal method)"""
        request = StrategyExecuteRequest(
            symbol=symbol,
            strategy_name=strategy_name,
            date=date,
            persist=persist,
            return_details=False  # Batch mode doesn't return detailed indicators
        )
        return self.execute_single(request)

    def _create_order_from_signal(self, signal: Dict) -> Dict:
        """Create order from signal (placeholder)"""
        # TODO: Implement actual order creation via OrderRepository
        return {
            'order_id': f"ORD{uuid.uuid4().hex[:8].upper()}",
            'symbol': signal['symbol'],
            'side': signal['signal_type'],
            'price': signal.get('entry_price'),
            'signal_id': signal.get('signal_id')
        }

    def _get_strategy_id(self, strategy_name: str) -> str:
        """Get strategy_id - uses strategy_name directly as TEXT identifier."""
        return strategy_name

    def _generate_signal_id(self, symbol: str, strategy: str, date: str) -> str:
        """Generate unique signal ID"""
        short_uuid = str(uuid.uuid4())[:8]
        clean_symbol = symbol.replace('.', '_')
        clean_date = date.replace('-', '')
        return f"sig_{clean_date}_{clean_symbol}_{strategy.lower()}_{short_uuid}"
