"""
信号执行调度器

核心编排器，协调完整的信号到订单流程：
1. 运行所有启用的策略
2. 收集今日待处理信号
3. 批量风控检查
4. 为通过的信号创建订单
5. 更新信号状态并记录日志

每日 15:30 由定时任务调用
"""

from domain.ports import ISignalExecutionLogRepository, ISignalRepository, IStrategyRepository
from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime, date
import structlog

from application.services.data_service import DataService
from application.services.strategy_code_service import StrategyCodeService
from application.services.risk_check_service import RiskCheckService
from application.services.order_service import create_order
from live_trading.paper_trading_engine import PaperTradingEngine, Signal as TradeSignal

logger = structlog.get_logger(__name__)


class SignalExecutionScheduler:
    """信号执行调度器

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        data_service: Optional[DataService] = None,
        strategy_service: Optional[StrategyCodeService] = None,
        risk_service: Optional[RiskCheckService] = None,
        signal_repo: Optional[ISignalRepository] = None,
        log_repo: Optional[ISignalExecutionLogRepository] = None,
        strategy_repo: Optional[IStrategyRepository] = None,
        paper_engine: Optional[PaperTradingEngine] = None,
    ):
        """初始化信号执行调度器

        Args:
            data_service: 数据服务（可选，用于依赖注入）
            strategy_service: 策略服务（可选）
            risk_service: 风控服务（可选）
            signal_repo: 信号仓库（可选）
            log_repo: 执行日志仓库（可选）
            strategy_repo: 策略仓库（可选）
            paper_engine: 纸面交易引擎（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例而非直接构造
        """
        # P2-1: 依赖注入 - 优先使用传入的实例，否则回退到直接实例化
        self.ds = data_service or DataService()
        self.strategy_service = strategy_service or StrategyCodeService()

        # risk_service 依赖 data_service，需要特殊处理
        if risk_service:
            self.risk_service = risk_service
        else:
            self.risk_service = RiskCheckService(self.ds)

        self.signal_repo = signal_repo or ISignalRepository()
        self.log_repo = log_repo or ISignalExecutionLogRepository()
        self.strategy_repo = strategy_repo or IStrategyRepository()

        # 懒加载：只有真正下单的路径（_batch_create_orders）才创建引擎。
        # 2026-07-24 盈利闭环改造：orchestrator 只收集信号不下单，
        # 不应因构造 scheduler 就绑定 rotation_main 账户。
        # P2-1: 支持注入已配置的 paper_engine
        self._paper_engine = paper_engine

    @property
    def paper_engine(self):
        if self._paper_engine is None:
            self._paper_engine = PaperTradingEngine(
                account_name='rotation_main',
                initial_capital=1_000_000,
            )
        return self._paper_engine

    def execute_daily_signals(self) -> Dict[str, Any]:
        """
        执行每日信号处理流程（15:30定时调用）

        Returns:
            执行结果摘要
        """
        execution_date = date.today().strftime('%Y-%m-%d')
        start_time = datetime.now()

        logger.info(f"开始执行每日信号流程: {execution_date}")

        # 创建执行日志
        log_id = self.log_repo.create_execution_log({
            'execution_date': execution_date,
            'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'running'
        })

        try:
            # Step 1: 运行所有启用的策略
            strategies_result = self._run_strategies(execution_date)

            # Step 2: 收集今日待处理信号
            pending_signals = self._collect_signals(execution_date)

            # Step 3: 批量风控检查
            approved_signals, rejected_signals = self._batch_risk_check(pending_signals)

            # Step 4: 为通过的信号创建订单
            orders_created = self._batch_create_orders(approved_signals)

            # Step 5: 更新信号状态
            self._update_signal_status(approved_signals, rejected_signals)

            # 计算执行时长
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # 更新执行日志
            self.log_repo.update_execution_log(log_id, {
                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'duration_ms': duration_ms,
                'strategies_run': strategies_result['total'],
                'signals_generated': strategies_result['signals_generated'],
                'signals_approved': len(approved_signals),
                'signals_rejected': len(rejected_signals),
                'orders_created': len(orders_created),
                'errors_count': strategies_result['errors'],
                'status': 'completed',
                'execution_details': {
                    'strategies': strategies_result['details'],
                    'risk_check_summary': {
                        'total_checked': len(pending_signals),
                        'approved': len(approved_signals),
                        'rejected': len(rejected_signals),
                        'rejection_reasons': self._summarize_rejections(rejected_signals)
                    },
                    'orders_summary': {
                        'total_created': len(orders_created),
                        'order_ids': orders_created
                    }
                }
            })

            result = {
                'success': True,
                'execution_date': execution_date,
                'duration_ms': duration_ms,
                'strategies_run': strategies_result['total'],
                'signals_generated': strategies_result['signals_generated'],
                'signals_approved': len(approved_signals),
                'signals_rejected': len(rejected_signals),
                'orders_created': len(orders_created),
                'log_id': log_id
            }

            logger.info(
                f"每日信号流程完成: 策略={strategies_result['total']}, "
                f"信号生成={strategies_result['signals_generated']}, "
                f"通过={len(approved_signals)}, "
                f"拒绝={len(rejected_signals)}, "
                f"订单={len(orders_created)}, "
                f"耗时={duration_ms}ms"
            )

            return result

        except Exception as e:
            logger.error(f"每日信号流程失败: {str(e)}", exc_info=True)

            # 更新执行日志为失败状态
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            self.log_repo.update_execution_log(log_id, {
                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'duration_ms': duration_ms,
                'status': 'failed',
                'error_message': str(e),
                'errors_count': 1
            })

            return {
                'success': False,
                'execution_date': execution_date,
                'error': str(e),
                'log_id': log_id
            }

    def _run_strategies(self, execution_date: str) -> Dict[str, Any]:
        """
        运行所有启用的策略

        Args:
            execution_date: 执行日期

        Returns:
            {
                'total': 运行的策略数量,
                'signals_generated': 生成的信号数量,
                'errors': 错误数量,
                'details': [策略执行详情]
            }
        """
        logger.info("Step 1: 运行所有启用的策略")

        # 获取所有启用的策略
        strategies = self.strategy_repo.get_all(active_only=True)

        total = 0
        signals_generated = 0
        errors = 0
        details = []

        for strategy in strategies:
            strategy_id = strategy['id']
            strategy_name = strategy.get('strategy_name', f'strategy_{strategy_id}')

            try:
                # 获取策略关联的股票池（这里简化处理，实际应该从配置中读取）
                # 暂时使用沪深300成分股作为默认股票池
                stock_pool = self._get_stock_pool()

                strategy_signals = 0

                for symbol in stock_pool:
                    try:
                        # 生成信号
                        signal = self.strategy_service.generate_signal(
                            strategy_id=strategy_id,
                            symbol=symbol,
                            date=execution_date
                        )

                        if signal:
                            # 保存信号到数据库
                            signal_data = {
                                'signal_date': execution_date,
                                'symbol': signal['symbol'],
                                'name': self._get_stock_name(signal['symbol']),
                                'action': signal['signal_type'],
                                # signal_type 内存契约大小写混存（strategy_executor 大写/
                                # strategy_code_service 小写），推导必须大小写容忍
                                'action_type': 1 if str(signal['signal_type']).lower() == 'buy' else 2,
                                'strategy_id': str(strategy_id),
                                'price': signal['price'],
                                'reason': f"Strategy: {strategy_name}",
                                'confidence': signal['confidence'],
                                'indicators': {}
                            }

                            self.signal_repo.create_signal(signal_data)
                            strategy_signals += 1

                    except Exception as e:
                        logger.warning(f"策略 {strategy_name} 处理股票 {symbol} 失败: {str(e)}")
                        continue

                total += 1
                signals_generated += strategy_signals

                details.append({
                    'strategy_id': strategy_id,
                    'strategy_name': strategy_name,
                    'signals_generated': strategy_signals,
                    'status': 'success'
                })

                logger.info(f"策略 {strategy_name} 完成: 生成 {strategy_signals} 个信号")

            except Exception as e:
                logger.error(f"策略 {strategy_name} 执行失败: {str(e)}")
                errors += 1

                details.append({
                    'strategy_id': strategy_id,
                    'strategy_name': strategy_name,
                    'signals_generated': 0,
                    'status': 'failed',
                    'error': str(e)
                })

        logger.info(f"策略运行完成: 总数={total}, 信号={signals_generated}, 错误={errors}")

        return {
            'total': total,
            'signals_generated': signals_generated,
            'errors': errors,
            'details': details
        }

    def _collect_signals(self, execution_date: str) -> List[Dict]:
        """
        收集今日待处理信号

        Args:
            execution_date: 执行日期

        Returns:
            待处理信号列表
        """
        logger.info("Step 2: 收集今日待处理信号")

        # 查询今日状态为 pending 的信号
        all_signals = self.signal_repo.get_signals_by_date(execution_date)
        # get_signals_by_date 返回 ORM Signal 对象（ORM 重构后），下游全链路
        # （风控/下单/orchestrator 推送）按 dict 消费——统一在此转 dict。
        # 曾按 dict 假设直接 s.get('status') → AttributeError 致 MARKET_OPEN
        # phase 崩溃、signals_ready 推送静默丢失（2026-08-13 修复）
        all_signals = [
            s if isinstance(s, dict) else s.to_dict() for s in all_signals
        ]
        pending_signals = [s for s in all_signals if s.get('status') == 'pending']

        logger.info(f"收集到 {len(pending_signals)} 个待处理信号")

        return pending_signals

    def _batch_risk_check(self, signals: List[Dict]) -> tuple[List[Dict], List[Dict]]:
        """
        批量风控检查

        Args:
            signals: 待检查的信号列表

        Returns:
            (approved_signals, rejected_signals)
        """
        logger.info("Step 3: 批量风控检查")

        approved = []
        rejected = []

        for signal in signals:
            try:
                # 执行风控检查
                check_result = self.risk_service.check_signal(signal)

                if check_result['passed']:
                    # 将计算的数量添加到信号中
                    signal['quantity'] = check_result['quantity']
                    approved.append(signal)
                else:
                    signal['reject_reason'] = check_result['reason']
                    rejected.append(signal)

            except Exception as e:
                logger.error(f"风控检查失败: {signal.get('symbol')} - {str(e)}")
                signal['reject_reason'] = f'检查异常: {str(e)}'
                rejected.append(signal)

        logger.info(f"风控检查完成: 通过={len(approved)}, 拒绝={len(rejected)}")

        return approved, rejected

    def _batch_create_orders(self, approved_signals: List[Dict]) -> List[int]:
        """
        为通过的信号批量创建订单并通过模拟引擎执行

        Args:
            approved_signals: 通过风控的信号列表

        Returns:
            创建的订单ID列表
        """
        logger.info("Step 4: 批量创建订单 + 模拟执行")

        order_ids = []
        trade_signals = []  # 收集转换为引擎信号

        for signal in approved_signals:
            try:
                # 获取最新价格
                latest_kline = self.ds.kline.get_latest_daily_kline(signal['symbol'])
                if not latest_kline:
                    logger.warning(f"无法获取股票价格: {signal['symbol']}")
                    continue

                close_price = float(latest_kline['close'])

                # 计算限价单价格
                if signal['action'] == 'BUY':  # signals 大写契约（08-13 统一）
                    limit_price = round(close_price * 1.01, 2)
                else:
                    limit_price = round(close_price * 0.99, 2)

                # 创建订单（保留原有订单系统记录）
                order_id = create_order(
                    ds=self.ds,
                    symbol=signal['symbol'],
                    action=signal['action'],
                    order_type='limit',
                    quantity=signal['quantity'],
                    price=limit_price,
                    reason=signal.get('reason', 'Signal execution'),
                    signal_id=signal['id']
                )
                order_ids.append(order_id)

                # 转换为 PaperTradingEngine 信号格式
                trade_signal = TradeSignal(
                    symbol=signal['symbol'],
                    action=signal['action'],
                    strategy_id=int(signal.get('strategy_id', 0)) if signal.get('strategy_id') else None,
                    strategy_name=signal.get('reason', 'strategy'),
                    strength=float(signal.get('confidence', 0.8)),
                    price=close_price,
                    signal_id=str(signal.get('id', '')),
                    reason=signal.get('reason', ''),
                )
                trade_signals.append(trade_signal)

                logger.info(
                    f"订单创建成功: {signal['symbol']} {signal['action']} "
                    f"qty={signal['quantity']} price={limit_price} order_id={order_id}"
                )

            except Exception as e:
                logger.error(f"订单创建失败: {signal.get('symbol')} - {str(e)}")
                continue

        # 通过模拟交易引擎执行
        if trade_signals:
            try:
                # 获取当前价格
                symbols = [s.symbol for s in trade_signals]
                current_prices = self._get_current_prices(symbols)

                trade_results = self.paper_engine.execute_signals(
                    signals=trade_signals,
                    current_prices=current_prices,
                )

                executed = sum(1 for r in trade_results if r.success)
                logger.info(
                    f"模拟交易执行完成: 总数={len(trade_signals)}, "
                    f"成功={executed}, 失败={len(trade_signals)-executed}"
                )

            except Exception as e:
                logger.error(f"模拟交易执行失败: {str(e)}")

        logger.info(f"订单创建完成: 总数={len(order_ids)}")

        return order_ids

    def _get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """获取股票当前价格"""
        prices = {}
        for symbol in symbols:
            try:
                kline = self.ds.kline.get_latest_daily_kline(symbol)
                if kline:
                    prices[symbol] = float(kline['close'])
            except Exception:
                pass
        return prices

    def _update_signal_status(
        self,
        approved_signals: List[Dict],
        rejected_signals: List[Dict]
    ):
        """
        更新信号状态

        Args:
            approved_signals: 通过的信号列表
            rejected_signals: 拒绝的信号列表
        """
        logger.info("Step 5: 更新信号状态")

        # 更新通过的信号为 approved
        for signal in approved_signals:
            try:
                self.signal_repo.update_signal(signal['id'], {
                    'status': 'approved',
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception as e:
                logger.error(f"更新信号状态失败: {signal['id']} - {str(e)}")

        # 更新拒绝的信号为 rejected
        for signal in rejected_signals:
            try:
                self.signal_repo.update_signal(signal['id'], {
                    'status': 'rejected',
                    'reject_reason': signal.get('reject_reason', '未知原因'),
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception as e:
                logger.error(f"更新信号状态失败: {signal['id']} - {str(e)}")

        logger.info(f"信号状态更新完成: 通过={len(approved_signals)}, 拒绝={len(rejected_signals)}")

    def _get_stock_pool(self, symbols: List[str] = None) -> List[str]:
        """
        获取股票池

        Args:
            symbols: 可选的股票代码列表，如果提供则直接使用

        Returns:
            股票代码列表
        """
        # 如果提供了 symbols 参数，直接使用
        if symbols:
            return symbols

        # 从数据库读取沪深300成分股
        try:
            from application.services.stock_pool_service import StockPoolService
            pool_service = StockPoolService()
            stock_pool = pool_service.get_hot_stocks()

            if stock_pool and len(stock_pool) > 0:
                logger.info(f"从股票池服务获取 {len(stock_pool)} 只股票")
                return stock_pool
        except Exception as e:
            logger.warning(f"从股票池服务获取股票失败: {e}")

        # Fallback: 从数据库直接查询所有股票
        try:
            stocks = self.ds.stock.get_all()
            if stocks and len(stocks) > 0:
                stock_symbols = [s['symbol'] for s in stocks if s.get('symbol')]
                logger.info(f"从数据库获取 {len(stock_symbols)} 只股票")
                return stock_symbols
        except Exception as e:
            logger.warning(f"从数据库获取股票失败: {e}")

        # 最后的 fallback: 返回沪深300前10只作为示例
        logger.warning("无法从数据库获取股票池，使用默认示例股票")
        return [
            '600000.SH',  # 浦发银行
            '600036.SH',  # 招商银行
            '601318.SH',  # 中国平安
            '000858.SZ',  # 五粮液
            '600276.SH',  # 恒瑞医药
            '000333.SZ',  # 美的集团
            '601166.SH',  # 兴业银行
            '600030.SH',  # 中信证券
            '000002.SZ',  # 万科A
            '600887.SH',  # 伊利股份
        ]

    def _get_stock_name(self, symbol: str) -> str:
        """
        获取股票名称

        Args:
            symbol: 股票代码

        Returns:
            股票名称
        """
        try:
            stock = self.ds.stock.get_by_symbol(symbol)
            return stock.get('name', symbol) if stock else symbol
        except Exception:
            return symbol

    def _summarize_rejections(self, rejected_signals: List[Dict]) -> Dict[str, int]:
        """
        汇总拒绝原因统计

        Args:
            rejected_signals: 拒绝的信号列表

        Returns:
            拒绝原因统计字典
        """
        summary = {}

        for signal in rejected_signals:
            reason = signal.get('reject_reason', '未知原因')
            summary[reason] = summary.get(reason, 0) + 1

        return summary
