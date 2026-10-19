"""
盘中监控服务 (Intraday Monitor)

每30分钟检查持仓，自动触发止损/止盈。
由 APScheduler 在交易时段（09:30-15:00）每30分钟调用。

功能：
1. 止损检查：跌破止损价 → 触发卖出（agent 自治账户自动执行；
   user_main 等 alert-only 账户只告警请用户裁定，绝不下单）
2. 止盈检查：涨到目标价 → 触发卖出（同上分级）
3. 大盘异动：指数跌超2% → 唤醒 Agent 分析
4. 持仓超时：超过30天无盈利 → 标记复盘
"""
from __future__ import annotations

import structlog
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, time

from application.services.agent_notification_service import agent_service
from qs_trading.domain.trading.services.market_session_policy import MarketSessionPolicy
from qs_trading.application.services.intraday_risk_policy import stop_loss_pct

logger = structlog.get_logger(__name__)


# ============================================================
# 配置
# ============================================================

# 账户清单的单一事实源 = quant.simulation_account.account_type 列
# （strategy=策略自动 / agent=Agent驱动 / user=用户主仓 / legacy=历史冻结）：
#   agent + status='active' → 自动执行止损/止盈（check_stop_loss）；
#   user  + status='active' → 只告警不执行（evaluate_stop_loss + 告警请用户裁定——
#                             user_main 处置权在用户，自动卖单 = 越权，2026-10-19 用户裁定）；
#   strategy / legacy / status!='active'（frozen/archived，如已退役冻结的 v14）→ 不监控。
#   account_type 为 NULL/空串/未识别值的 active 账户 → 一律 alert_only（2026-10-19 用户裁定：
#   类型缺失是数据质量问题，静默不监控会让真实持仓账户盘中完全失明；安全方向 = 盯着但不动钱）。
# 口径变更改表不改码。v13/v14 正是靠 account_type=strategy（+ v14 frozen）被排除——
# 它们自有 v13/v14_daily_check 日频止损闭环，纳入盘中监控会重复触发卖单。
#
# 表查询失败时的兜底清单：一律按 alert-only 处理（fail-closed——
# 宁可不自动执行也绝不动用户的钱；alert-only 只告警不下单）。
DEFAULT_FALLBACK_ACCOUNTS = ('agent_virtual', 'agent_brain', 'user_main_simulation')

MONITOR_CONFIG = {
    'stop_loss_pct': -0.08,        # 止损线（标量兜底；分级口径见 intraday_risk_policy.stop_loss_pct）
    'take_profit_pct': 0.15,       # 止盈线 +15%
    'index_alert_pct': -0.02,      # 大盘异动阈值 -2%
    'max_holding_days': 30,        # 最大持仓天数
    'check_interval_minutes': 30,  # 检查间隔
    # 缺省（None）= 从 quant.simulation_account 读账户清单（单一事实源）；
    # 显式给清单 = 调试覆盖（不读表）。同名账户同时在两清单时 alert-only 优先（安全方向）。
    'accounts': None,
    'alert_only_accounts': None,
}


# ============================================================
# 盘中监控
# ============================================================

class IntradayMonitor:
    """盘中持仓监控

    交易时段每30分钟运行一次，检查止损/止盈/异动。
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**MONITOR_CONFIG, **(config or {})}
        self._alert_sent_today = False  # 每日只发一次大盘异动告警

    def check(self) -> Dict[str, Any]:
        """执行一次盘中检查

        Returns:
            检查结果摘要
        """
        # 只在交易时段运行
        now = datetime.now()
        if not self._is_trading_time(now.time()):
            return {'status': 'skipped', 'reason': 'not trading time'}

        # 重置每日告警标记
        if not hasattr(self, '_last_check_date') or self._last_check_date != now.date():
            self._last_check_date = now.date()
            self._alert_sent_today = False

        results = {
            'timestamp': now.isoformat(),
            'stop_loss_triggered': [],
            'take_profit_triggered': [],
            'alerts': [],
            'accounts': {},  # 按账户分组汇报
        }

        # 逐账户独立跑止损/止盈：单账户失败不影响其他账户。
        # alert_only 账户同样逐账户检查，但只评估告警、绝不下卖单。
        # 账户清单缺省读 quant.simulation_account（account_type 列 = 单一事实源）；
        # 显式 config 覆盖仅调试用；表查询失败一律降级 alert-only（fail-closed）。
        auto_accounts, alert_accounts, account_source = self._resolve_accounts()
        results['account_source'] = account_source
        alert_only = set(alert_accounts)
        # 同名账户同时在两清单时 alert-only 优先（安全方向：不动用户的钱）
        auto_accounts = [a for a in auto_accounts if a not in alert_only]
        all_accounts = auto_accounts + list(alert_accounts)

        if not all_accounts:
            results['status'] = 'no_accounts'
            logger.warning("intraday_no_accounts", source=account_source)
            return results

        all_positions: List[Dict] = []
        total_checked = 0
        total_prices = 0

        for account in all_accounts:
            is_alert_only = account in alert_only
            acct_result: Dict[str, Any] = {
                'status': 'pending',
                'mode': 'alert_only' if is_alert_only else 'auto_execute',
                'stop_loss_triggered': [],
                'take_profit_triggered': [],
                'alerts': [],
            }
            try:
                from application.trading.paper_trading_engine import PaperTradingEngine
                engine = PaperTradingEngine(
                    account_name=account,
                    risk_config={
                        # 分级止损口径（宪法：创业板/科创板 -10%，其余 -8%）
                        'stop_loss_pct_fn': stop_loss_pct,
                        # 标量兜底（fn 缺失时生效）
                        'stop_loss_pct': self.config['stop_loss_pct'],
                        'take_profit_pct': self.config['take_profit_pct'],
                    },
                )

                # 获取当前持仓
                positions = engine.get_current_positions()
                if not positions:
                    acct_result['status'] = 'no_positions'
                    results['accounts'][account] = acct_result
                    continue

                # 获取实时价格
                symbols = [p['symbol'] for p in positions]
                current_prices = self._get_realtime_prices(symbols)

                if not current_prices:
                    acct_result['status'] = 'no_prices'
                    results['accounts'][account] = acct_result
                    continue

                if is_alert_only:
                    # 只告警不执行（user_main：处置权在用户，自动卖单 = 越权）。
                    # 只调用纯评估方法，**绝不调用 engine.check_stop_loss**。
                    triggers = engine.evaluate_stop_loss(current_prices)
                    for t in triggers:
                        t['account'] = account
                        acct_result['alerts'].append(t)
                        results['alerts'].append(t)
                    if triggers:
                        self._notify_user_stop_alert(account, triggers)
                else:
                    # 1. 止损/止盈检查（止盈在同一函数内）
                    stop_results = engine.check_stop_loss(current_prices)
                    for r in stop_results:
                        if r.success:
                            entry = r.to_dict()
                            entry['account'] = account
                            if 'stop_loss' in (r.signal.strategy_name or ''):
                                acct_result['stop_loss_triggered'].append(entry)
                                results['stop_loss_triggered'].append(entry)
                            elif 'take_profit' in (r.signal.strategy_name or ''):
                                acct_result['take_profit_triggered'].append(entry)
                                results['take_profit_triggered'].append(entry)

                # 4. 更新持仓市值
                engine._update_position_values(current_prices)

                acct_result['status'] = 'completed'
                acct_result['positions_checked'] = len(positions)
                acct_result['prices_fetched'] = len(current_prices)
                all_positions.extend(positions)
                total_checked += len(positions)
                total_prices += len(current_prices)

            except Exception as e:
                acct_result['status'] = 'error'
                acct_result['error'] = str(e)
                logger.error("intraday_account_check_failed", account=account, error=str(e))

            results['accounts'][account] = acct_result

        if not all_positions:
            # 沿用旧行为：无持仓时不做大盘异动/持仓超时检查
            any_error = any(a['status'] == 'error' for a in results['accounts'].values())
            results['status'] = 'error' if any_error else 'no_positions'
            return results

        try:
            # 2. 大盘异动检查
            index_alert = self._check_index_alert()
            if index_alert and not self._alert_sent_today:
                results['alerts'].append(index_alert)
                self._alert_sent_today = True
                self._notify_agent_market_alert(index_alert, all_positions)

            # 3. 持仓超时检查
            timeout_positions = self._check_holding_timeout(all_positions)
            if timeout_positions:
                results['timeout_positions'] = timeout_positions

            results['status'] = 'completed'
            results['positions_checked'] = total_checked
            results['prices_fetched'] = total_prices

            logger.info(
                "intraday_check_done",
                accounts=len(results['accounts']),
                positions=total_checked,
                stop_loss=len(results['stop_loss_triggered']),
                take_profit=len(results['take_profit_triggered']),
                alerts=len(results['alerts']),
            )

        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
            logger.error(f"Intraday check failed: {e}")

        return results

    # ==================== 内部方法 ====================

    def _resolve_accounts(self) -> Tuple[List[str], List[str], str]:
        """解析盘中监控账户清单 → (自动执行清单, 只告警清单, 来源)。

        单一事实源 = quant.simulation_account.account_type 列（口径变更改表不改码）：
          account_type='agent' + status='active' → auto_execute；
          account_type='user'  + status='active' → alert_only；
          strategy/legacy → 不监控；status!='active'（frozen/archived）由
          list_accounts(status='active') 在 SQL 层滤除。
          account_type 为 NULL/空串/未识别值 → 一律 alert_only
          （2026-10-19 用户裁定：类型缺失是数据质量问题，静默不监控会让真实持仓账户
          盘中完全失明，比"多告警一条"更危险；安全方向永远是"盯着但不动钱"）。

        数据访问走既有仓储端口 SimulationORMRepository.list_accounts
        （与 PaperTradingEngine 同一个仓储类，不新建第三份实现）。

        fail-closed：查询异常 → 自动执行清单为空 + 兜底清单按 alert-only 监控
        （宁可不自动执行也绝不动用户的钱），异常记日志。
        config 显式给了 accounts / alert_only_accounts 时不读表（调试覆盖）。
        """
        cfg_auto = self.config.get('accounts')
        cfg_alert = self.config.get('alert_only_accounts')
        if cfg_auto is not None or cfg_alert is not None:
            return list(cfg_auto or ()), list(cfg_alert or ()), 'config_override'

        try:
            from adapters.outbound.repositories import SimulationORMRepository
            repo = SimulationORMRepository()
            rows = repo.list_accounts(status='active')  # frozen/archived 在此被滤除
        except Exception as e:
            logger.error("intraday_account_resolve_failed", error=str(e))
            logger.warning(
                "intraday_account_fallback_alert_only",
                accounts=list(DEFAULT_FALLBACK_ACCOUNTS),
            )
            return [], list(DEFAULT_FALLBACK_ACCOUNTS), 'fallback_fail_closed'

        auto, alert = [], []
        for a in rows:
            name = getattr(a, 'account_name', None)
            if not name:
                continue
            account_type = (getattr(a, 'account_type', None) or '').strip()
            if account_type == 'agent':
                auto.append(name)
            elif account_type in ('strategy', 'legacy'):
                continue  # 策略自有日频闭环 / 历史冻结：不监控
            else:
                # 'user' 及 NULL/空串/未识别值：一律 alert-only（2026-10-19 裁定：
                # 类型缺失 = 数据质量问题，盯着但不动钱，绝不静默失明）
                alert.append(name)
                if account_type != 'user':
                    logger.warning(
                        "intraday_account_type_unknown_alert_only",
                        account=name, account_type=account_type or None,
                    )
        return auto, alert, 'table'

    def _is_trading_time(self, current_time: time) -> bool:
        """判断是否在交易时段（RFC 016 §8.1：时段判定收敛到 MarketSessionPolicy）

        回归背景（2026-09-12 代码审查）：旧实现按精确 `time` 比较，而调用方传的是
        `datetime.now().time()`（秒/微秒非零）→ `time(15,0,30) <= time(15,0)` 为假，
        使 11:30 与 15:00 两次巡检被静默跳过（外层节拍闸门判 True、内层却 False，
        收盘那次止损/止盈不执行）。策略内部先**截到整分钟**，端点按整分钟语义闭合。

        日级仍由调用方（外层节拍闸门）把关，待 RFC 016 D9 统一。
        """
        return MarketSessionPolicy.is_market_open(
            MarketSessionPolicy.phase_for(current_time, is_trading_day=True)
        )

    def _get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """获取实时价格（使用最新K线收盘价模拟）"""
        prices = {}
        try:
            from infrastructure.services.service_factory import ServiceFactory
            kline_repo = ServiceFactory.get_kline_repository()

            for symbol in symbols:
                try:
                    kline = kline_repo.get_latest_daily_kline(symbol)
                    if kline:
                        prices[symbol] = float(kline['close'])
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to get prices: {e}")

        return prices

    def _check_index_alert(self) -> Optional[Dict[str, Any]]:
        """检查大盘异动（上证指数跌幅超阈值）"""
        try:
            from infrastructure.services.service_factory import ServiceFactory
            kline_repo = ServiceFactory.get_kline_repository()

            # 获取上证指数最新K线
            kline = kline_repo.get_latest_daily_kline('000001.SH')
            if not kline:
                return None

            close = float(kline.get('close', 0))
            prev_close = float(kline.get('pre_close', 0)) or close

            if prev_close <= 0:
                return None

            change_pct = (close - prev_close) / prev_close

            if change_pct <= self.config['index_alert_pct']:
                return {
                    'type': 'index_drop',
                    'index': '上证指数',
                    'change_pct': round(change_pct, 4),
                    'close': close,
                    'threshold': self.config['index_alert_pct'],
                    'timestamp': datetime.now().isoformat(),
                }

        except Exception as e:
            logger.warning(f"Index alert check failed: {e}")

        return None

    def _check_holding_timeout(self, positions: List[Dict]) -> List[Dict]:
        """检查持仓超时（超过N天无盈利）"""
        timeout = []
        today = date.today()

        for pos in positions:
            # 计算持仓天数（从 created_at 或首次买入日期）
            created = pos.get('created_at') or pos.get('first_buy_date')
            if not created:
                continue

            try:
                if isinstance(created, str):
                    buy_date = datetime.fromisoformat(created).date()
                else:
                    buy_date = created.date() if hasattr(created, 'date') else created

                holding_days = (today - buy_date).days
                profit_rate = pos.get('profit_total_rate', 0) or 0

                if holding_days > self.config['max_holding_days'] and profit_rate <= 0:
                    timeout.append({
                        'symbol': pos['symbol'],
                        'holding_days': holding_days,
                        'profit_rate': profit_rate,
                        'suggestion': '建议复盘，考虑是否止损',
                    })

            except Exception:
                pass

        return timeout

    def _notify_user_stop_alert(self, account: str, triggers: List[Dict]):
        """alert-only 账户（user_main）止损/止盈触发：只告警请用户裁定，绝不下单。

        走既有 agent 通知通道；处置权在用户本人（2026-10-19 用户裁定）。
        """
        try:
            lines = [
                f"- {t['symbol']} {t['type']}: 盈亏 {t['pnl_pct']:.2%}，"
                f"阈值 {t['threshold']:.2%}，现价 {t['current_price']}，成本 {t['avg_cost']}"
                for t in triggers
            ]
            agent_service.notify_agent('user_stop_alert', {
                'account': account,
                'triggers': triggers,
                'instructions': (
                    f"用户账户 {account} 盘中风控触发（只告警，系统未执行任何卖出）：\n"
                    + '\n'.join(lines)
                    + '\n该账户处置权在用户本人，请转达用户裁定是否卖出；'
                      '在用户明确指示前不得代为下单。'
                ),
            })
        except Exception as e:
            logger.warning(f"Failed to notify user stop alert: {e}")

    def _notify_agent_market_alert(self, alert: Dict, positions: List[Dict]):
        """大盘异动时唤醒 Agent"""
        try:
            agent_service.notify_agent('market_alert', {
                'alert': alert,
                'current_positions': len(positions),
                'position_symbols': [p['symbol'] for p in positions[:10]],
                'instructions': (
                    '大盘异动告警：\n'
                    f"上证指数跌幅 {alert['change_pct']:.2%}，超过阈值 {alert['threshold']:.2%}。\n"
                    '请分析：\n'
                    '1. 是否需要减仓？\n'
                    '2. 当前持仓是否受影响？\n'
                    '3. 是否需要暂停今日买入？\n'
                    '通过 API 反馈决策给 V2。'
                ),
            })
        except Exception as e:
            logger.warning(f"Failed to notify agent for market alert: {e}")


# ============================================================
# 全局单例 + 调度注册
# ============================================================

_monitor: Optional[IntradayMonitor] = None


def get_intraday_monitor() -> IntradayMonitor:
    """获取全局盘中监控实例"""
    global _monitor
    if _monitor is None:
        _monitor = IntradayMonitor()
    return _monitor

# 盘中监控的调度宿主 = FastAPI lifespan（orchestrator_bootstrap.py，2026-08-13 起）。
# 原 register_intraday_monitor_to_scheduler（APScheduler/unified_scheduler 路线）
# 已随 scheduler_daemon 一并删除。
