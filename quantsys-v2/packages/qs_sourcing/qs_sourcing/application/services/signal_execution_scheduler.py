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

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from qs_kernel.domain.ports import ISignalExecutionLogRepository, ISignalRepository, IStrategyRepository
import structlog

from qs_strategy.application.services.strategy_code_service import StrategyCodeService
from qs_trading.application.services.risk_check_service import RiskCheckService
from application.trading.paper_trading_engine import PaperTradingEngine, Signal as TradeSignal
from infrastructure.services.service_factory import ServiceFactory
from qs_kernel.domain.ports import IPortfolioRepository, IStockRepository, IKlineRepository

logger = structlog.get_logger(__name__)


class SimulationHoldingsProvider:
    """模拟账户持仓口径（供 RiskCheckService 检查指定 simulation 账户）

    2026-10-20 新增：独立量化闭环的风控必须查 rotation_main 自己的持仓/成交，
    而非实盘组合（portfolio_repo）——否则该账户持仓的卖出信号会被「无持仓」
    误拒，买入资金/集中度也按错的账户余额计算。
    """

    def __init__(self, account_name: str):
        self.account_name = account_name

    def _repo(self):
        from adapters.outbound.repositories import SimulationORMRepository
        return SimulationORMRepository()

    def get_holding(self, symbol: str):
        """与 IPortfolioRepository.get_holding 同形：{'quantity': 可卖股数(T+1)}"""
        try:
            p = self._repo().get_position(self.account_name, symbol)
            if p is None or (p.shares_total or 0) <= 0:
                return None
            return {'symbol': symbol, 'quantity': int(p.shares_available or 0)}
        except Exception as e:
            logger.warning(f"sim holdings get_holding 失败: {symbol}: {e}")
            return None

    def get_all_holdings(self):
        try:
            return [
                {'symbol': p.symbol, 'quantity': int(p.shares_available or 0)}
                for p in self._repo().get_all_positions(self.account_name)
                if (p.shares_total or 0) > 0
            ]
        except Exception as e:
            logger.warning(f"sim holdings get_all_holdings 失败: {e}")
            return []

    def get_trades_by_date_and_symbol(self, day: str, symbol: str):
        """供每日交易次数限制检查（同账户当日该标的的成交笔数）"""
        try:
            trades = self._repo().get_trades_by_account(
                account_name=self.account_name, start_date=day, end_date=day)
            return [t for t in trades if getattr(t, 'symbol', None) == symbol]
        except Exception as e:
            logger.warning(f"sim holdings trades 查询失败: {symbol}: {e}")
            return []


def make_sim_account_provider(account_name: str):
    """账户口径 provider：{'cash', 'total_assets'} 取自 simulation_account"""
    def _get():
        try:
            from adapters.outbound.repositories import SimulationORMRepository
            acct = SimulationORMRepository().get_account(account_name)
            if acct is None:
                return None
            return {
                'cash': float(acct.cash_available or 0),
                'total_assets': float(acct.total_value or 0),
            }
        except Exception as e:
            logger.warning(f"sim account provider 失败: {e}")
            return None
    return _get


class SignalExecutionScheduler:
    """信号执行调度器

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        strategy_service: Optional[StrategyCodeService] = None,
        risk_service: Optional[RiskCheckService] = None,
        signal_repo: Optional[ISignalRepository] = None,
        log_repo: Optional[ISignalExecutionLogRepository] = None,
        strategy_repo: Optional[IStrategyRepository] = None,
        paper_engine: Optional[PaperTradingEngine] = None,
        portfolio_repo: Optional[IPortfolioRepository] = None,
        stock_repo: Optional[IStockRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
    ):
        """初始化信号执行调度器

        Args:
            strategy_service: 策略服务（可选）
            risk_service: 风控服务（可选）
            signal_repo: 信号仓库（可选）
            log_repo: 执行日志仓库（可选）
            strategy_repo: 策略仓库（可选）
            paper_engine: 纸面交易引擎（可选）
            portfolio_repo: PortfolioRepository（可选）
            stock_repo: StockRepository（可选）
            kline_repo: KlineRepository（可选）
        """
        # P2-1: 依赖注入 - 优先使用传入的实例，否则回退到 ServiceFactory
        # 注意：signal/log/strategy repo 也必须走 ServiceFactory 兜底——无参构造
        # （orchestrator 主推路径、242 signal_execution_daily 兜底路径）依赖此行为。
        # 曾只有 portfolio/stock/kline 兜底，导致无参构造时 signal_repo=None，
        # _collect_signals 直接 AttributeError（2026-09-02 修复）。
        self.portfolio_repo = portfolio_repo or ServiceFactory.get_portfolio_repository()
        self.stock_repo = stock_repo or ServiceFactory.get_stock_repository()
        self.kline_repo = kline_repo or ServiceFactory.get_kline_repository()
        self.signal_repo = signal_repo or ServiceFactory.get_signal_repository()
        self.log_repo = log_repo or ServiceFactory.get_signal_execution_log_repository()
        self.strategy_repo = strategy_repo or ServiceFactory.get_strategy_repository()
        self.strategy_service = strategy_service or StrategyCodeService()

        # risk_service 依赖 repo，需要特殊处理
        # 2026-10-20：缺省按 rotation_main 自己的账本做风控（独立量化闭环），
        # 不再误用实盘组合/实盘账户余额——否则本账户持仓的卖单被「无持仓」误拒。
        if risk_service:
            self.risk_service = risk_service
        else:
            self.risk_service = RiskCheckService(
                account_provider=make_sim_account_provider('rotation_main'),
                holdings_provider=SimulationHoldingsProvider('rotation_main'),
            )

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

            # Step 5: 更新信号状态（实际成交的标 executed，其余通过的标 approved）
            self._update_signal_status(approved_signals, rejected_signals, executed_ids=orders_created)

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
                        'executed_signal_ids': orders_created
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
                # 2026-10-20：信号生成侧（handle_signal_generate）不带
                # risk_management.stop_loss，而风控缺省 require_stop_loss=True →
                # 所有 BUY 必被「缺少止损设置」误拒。缺省时注入与引擎缺省一致的
                # -8% 止损（引擎成交后另有日频 check_stop_loss 兜底，口径一致）。
                if str(signal.get('action', '')).upper() == 'BUY':
                    rm = signal.get('risk_management') or {}
                    if not rm.get('stop_loss'):
                        signal['risk_management'] = {**rm, 'stop_loss': {'percent': 8}}

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
        为通过的信号执行下单（模拟交易引擎）

        2026-09-14（REQ-24e15d B4-c2）：本方法原先**先**调 legacy
        application.services.order_service.create_order()（写 quant.orders）
        **再**喂给 PaperTradingEngine。但 quant.orders 已于 2026-08-25 归档不存在，
        该调用必抛 UndefinedTable、被下方 except 吞掉后 continue ——
        trade_signals 永远为空，**模拟引擎一单都不会执行**，整条信号执行链
        静默失效（日志只留下"订单创建失败"）。删除该 legacy 调用后，
        本方法回归单一职责：只走模拟引擎（落 simulation_* 表）。

        Args:
            approved_signals: 通过风控的信号列表

        Returns:
            实际成交的信号 ID 列表（调用方取其长度写 signal_executions.orders_created）
        """
        logger.info("Step 4: 批量执行信号（模拟交易引擎）")

        trade_signals = []  # 收集转换为引擎信号

        for signal in approved_signals:
            try:
                # 获取最新价格
                # 2026-10-21 修复：get_latest_daily_kline 返回 polars DataFrame，
                # `if not latest_kline` 必抛 "truth value of a DataFrame is ambiguous"
                # → 每条信号都在转换处炸掉、被 except 吞掉 → 引擎永远 0 单
                # （昨日/今日 3 条 approved SELL 未成交的真因，T+1 只是表象）
                latest_kline = self.kline_repo.get_latest_daily_kline(signal['symbol'])
                if latest_kline is None or latest_kline.is_empty():
                    logger.warning(f"无法获取股票价格: {signal['symbol']}")
                    continue

                close_price = float(latest_kline['close'][0])

                # 转换为 PaperTradingEngine 信号格式
                # 2026-10-20 修复：confidence 在 DB 是 NULL 时
                # signal.get('confidence', 0.8) 返回 None → float(None) 必抛，
                # 全量信号转换失败 → 引擎一单不收 → orders_created 静默为 0
                trade_signal = TradeSignal(
                    symbol=signal['symbol'],
                    action=signal['action'],
                    strategy_id=int(signal.get('strategy_id', 0)) if signal.get('strategy_id') else None,
                    strategy_name=signal.get('reason', 'strategy'),
                    strength=float(signal.get('confidence') or 0.8),
                    price=close_price,
                    signal_id=str(signal.get('id', '')),
                    reason=signal.get('reason', ''),
                )
                trade_signals.append(trade_signal)

            except Exception as e:
                logger.error(f"信号转换失败: {signal.get('symbol')} - {str(e)}")
                continue

        executed_signal_ids: List[int] = []

        # 全部转换失败是链路事故（典型：字段契约漂移），必须显式报错而非静默 0 单
        if approved_signals and not trade_signals:
            logger.error(
                f"信号转换全部失败: approved={len(approved_signals)} 但 0 条进入引擎，"
                "检查信号字段契约（confidence/action/price）"
            )

        # 通过模拟交易引擎执行（唯一的落库路径：simulation_* 表）
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
                executed_signal_ids = [
                    int(r.signal.signal_id)
                    for r in trade_results
                    if r.success and str(r.signal.signal_id or '').strip().isdigit()
                ]
                logger.info(
                    f"模拟交易执行完成: 总数={len(trade_signals)}, "
                    f"成功={executed}, 失败={len(trade_signals)-executed}"
                )

            except Exception as e:
                logger.error(f"模拟交易执行失败: {str(e)}")

        logger.info(f"信号执行完成: 成交={len(executed_signal_ids)}")

        return executed_signal_ids

    def _get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """获取股票当前价格"""
        prices = {}
        for symbol in symbols:
            try:
                kline = self.kline_repo.get_latest_daily_kline(symbol)
                # 2026-10-21 修复：polars DataFrame 不可判真（必抛 TypeError 被
                # 下方 except 吞掉 → 价格表静默全空，引擎只能靠 signal.price 兜底）
                if kline is not None and not kline.is_empty():
                    prices[symbol] = float(kline['close'][0])
            except Exception:
                pass
        return prices

    def execute_pending_signals(self, execution_date: Optional[str] = None) -> Dict[str, Any]:
        """独立量化虚拟交易闭环（不跑策略、不依赖 Agent）：

        收集当日 pending 信号 → 批量风控 → PaperTradingEngine（rotation_main）执行
        → 状态回写（成交=executed / 通过未成交=approved / 拒绝=rejected）→ 执行日志。

        信号生成由 orchestrator 盘前 phase（handle_signal_generate）负责；
        本方法只做"信号 → 成交"段，供收盘后调度（15:40）调用。

        2026-10-20 新增：此前生产唯一接线是 handle_signal_execution_daily 的
        "兜底推送 Agent"（07:30 跑、当日信号尚未生成完，实测天天 signals_pending=0），
        真实执行器只被测试调用 → 962 条信号全部停在 pending、rotation_main 从未成交。
        """
        execution_date = execution_date or date.today().strftime('%Y-%m-%d')
        start_time = datetime.now()

        log_id = self.log_repo.create_execution_log({
            'execution_date': execution_date,
            'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'running'
        })

        try:
            # Step 0: 日频止损/止盈（收盘口径）。rotation_main 是 strategy 账户，
            # 盘中监控（intraday_monitor）按口径不管 strategy/legacy 账户，
            # 本闭环必须自我保护：先止损再执行新信号（释放现金、腾出仓位预算）
            stop_loss_results = []
            try:
                held = self.paper_engine.get_current_positions()
                if held:
                    held_prices = self._get_current_prices([p['symbol'] for p in held])
                    if held_prices:
                        stop_loss_results = self.paper_engine.check_stop_loss(held_prices)
                        triggered = sum(1 for r in stop_loss_results if r.success)
                        if triggered:
                            logger.info(f"日频止损/止盈触发 {triggered} 笔")
            except Exception as e:
                logger.error(f"日频止损检查失败（不阻断信号执行）: {e}")

            pending_signals = self._collect_signals(execution_date)
            approved_signals, rejected_signals = self._batch_risk_check(pending_signals)
            executed_ids = self._batch_create_orders(approved_signals)
            self._update_signal_status(approved_signals, rejected_signals, executed_ids=executed_ids)

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            self.log_repo.update_execution_log(log_id, {
                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'duration_ms': duration_ms,
                'strategies_run': 0,
                'signals_generated': 0,
                'signals_approved': len(approved_signals),
                'signals_rejected': len(rejected_signals),
                'orders_created': len(executed_ids),
                'errors_count': 0,
                'status': 'completed',
                'execution_details': {
                    'mode': 'execute_pending_only',
                    'stop_loss_triggered': sum(1 for r in stop_loss_results if r.success),
                    'risk_check_summary': {
                        'total_checked': len(pending_signals),
                        'approved': len(approved_signals),
                        'rejected': len(rejected_signals),
                        'rejection_reasons': self._summarize_rejections(rejected_signals)
                    },
                    'orders_summary': {
                        'total_created': len(executed_ids),
                        'executed_signal_ids': executed_ids
                    }
                }
            })

            result = {
                'success': True,
                'execution_date': execution_date,
                'duration_ms': duration_ms,
                'signals_pending': len(pending_signals),
                'signals_approved': len(approved_signals),
                'signals_rejected': len(rejected_signals),
                'orders_created': len(executed_ids),
                'stop_loss_triggered': sum(1 for r in stop_loss_results if r.success),
                'log_id': log_id
            }
            logger.info(f"待执行信号闭环完成: {result}")
            return result

        except Exception as e:
            logger.error(f"待执行信号闭环失败: {str(e)}", exc_info=True)
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

    def _update_signal_status(
        self,
        approved_signals: List[Dict],
        rejected_signals: List[Dict],
        executed_ids: Optional[List[int]] = None,
    ):
        """
        更新信号状态

        Args:
            approved_signals: 通过风控的信号列表
            rejected_signals: 拒绝的信号列表
            executed_ids: 实际成交的信号 ID（2026-10-20 新增）：命中 → 'executed'，
                其余通过的 → 'approved'（通过但未成交，如余额不足/引擎拒单）
        """
        logger.info("Step 5: 更新信号状态")

        executed_set = {int(i) for i in (executed_ids or [])}

        for signal in approved_signals:
            sid = signal['id']
            new_status = 'executed' if int(sid) in executed_set else 'approved'
            try:
                # 2026-10-20 修复：改用 SignalORMRepository.update_signal_status
                # （专门方法，带 commit）；原调用 update_signal(id, dict) 与真实
                # 签名 update_signal(id, **kwargs) 不匹配，必然 TypeError——
                # 状态回写从未生效（本闭环此前零生产接线的又一实证）
                self.signal_repo.update_signal_status(sid, new_status)
            except Exception as e:
                logger.error(f"更新信号状态失败: {sid} - {str(e)}")

        # 更新拒绝的信号为 rejected
        for signal in rejected_signals:
            try:
                self.signal_repo.update_signal_status(
                    signal['id'], 'rejected',
                    reject_reason=signal.get('reject_reason', '未知原因'),
                )
            except Exception as e:
                logger.error(f"更新信号状态失败: {signal['id']} - {str(e)}")

        logger.info(
            f"信号状态更新完成: 成交={len(executed_set)}, "
            f"通过={len(approved_signals)}, 拒绝={len(rejected_signals)}"
        )

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
            from qs_sourcing.application.services.stock_pool_service import StockPoolService
            pool_service = StockPoolService()
            stock_pool = pool_service.get_hot_stocks()

            if stock_pool and len(stock_pool) > 0:
                logger.info(f"从股票池服务获取 {len(stock_pool)} 只股票")
                return stock_pool
        except Exception as e:
            logger.warning(f"从股票池服务获取股票失败: {e}")

        # Fallback: 从数据库直接查询所有股票
        try:
            stocks = self.stock_repo.get_all()
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
            stock = self.stock_repo.get_by_symbol(symbol)
            # 2026-09-13（w-c8cae280）：get_by_symbol 返回 Stock ORM 实体（属性访问），
            # 原写法按 dict 调 .get('name') → AttributeError → 被下面 except 吞掉 → **永远回落到代码号**，
            # 股票名静默解析不出来（与 exit-plan 500 同一类，只是这里不崩、只失真）。
            if isinstance(stock, dict):
                return stock.get('name') or symbol
            return getattr(stock, 'name', None) or symbol
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
