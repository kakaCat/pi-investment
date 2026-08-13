"""
盘中监控服务 (Intraday Monitor)

每30分钟检查持仓，自动触发止损/止盈。
由 APScheduler 在交易时段（09:30-15:00）每30分钟调用。

功能：
1. 止损检查：跌破止损价 → 触发卖出
2. 止盈检查：涨到目标价 → 触发卖出
3. 大盘异动：指数跌超2% → 唤醒 Agent 分析
4. 持仓超时：超过30天无盈利 → 标记复盘
"""
from __future__ import annotations

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, date, time

from application.services.agent_notification_service import agent_service

logger = structlog.get_logger(__name__)


# ============================================================
# 配置
# ============================================================

MONITOR_CONFIG = {
    'stop_loss_pct': -0.08,        # 止损线 -8%
    'take_profit_pct': 0.15,       # 止盈线 +15%
    'index_alert_pct': -0.02,      # 大盘异动阈值 -2%
    'max_holding_days': 30,        # 最大持仓天数
    'check_interval_minutes': 30,  # 检查间隔
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
        }

        try:
            from live_trading.paper_trading_engine import PaperTradingEngine
            engine = PaperTradingEngine(account_name='rotation_main')

            # 获取当前持仓
            positions = engine.get_current_positions()
            if not positions:
                results['status'] = 'no_positions'
                return results

            # 获取实时价格
            symbols = [p['symbol'] for p in positions]
            current_prices = self._get_realtime_prices(symbols)

            if not current_prices:
                results['status'] = 'no_prices'
                return results

            # 1. 止损/止盈检查
            stop_results = engine.check_stop_loss(current_prices)
            for r in stop_results:
                if r.success:
                    if 'stop_loss' in (r.signal.strategy_name or ''):
                        results['stop_loss_triggered'].append(r.to_dict())
                    elif 'take_profit' in (r.signal.strategy_name or ''):
                        results['take_profit_triggered'].append(r.to_dict())

            # 2. 大盘异动检查
            index_alert = self._check_index_alert()
            if index_alert and not self._alert_sent_today:
                results['alerts'].append(index_alert)
                self._alert_sent_today = True
                self._notify_agent_market_alert(index_alert, positions)

            # 3. 持仓超时检查
            timeout_positions = self._check_holding_timeout(positions)
            if timeout_positions:
                results['timeout_positions'] = timeout_positions

            # 4. 更新持仓市值
            engine._update_position_values(current_prices)

            results['status'] = 'completed'
            results['positions_checked'] = len(positions)
            results['prices_fetched'] = len(current_prices)

            logger.info(
                "intraday_check_done",
                positions=len(positions),
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

    def _is_trading_time(self, current_time: time) -> bool:
        """判断是否在交易时段"""
        morning = time(9, 30) <= current_time <= time(11, 30)
        afternoon = time(13, 0) <= current_time <= time(15, 0)
        return morning or afternoon

    def _get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """获取实时价格（使用最新K线收盘价模拟）"""
        prices = {}
        try:
            from application.services.data_service import DataService
            ds = DataService()

            for symbol in symbols:
                try:
                    kline = ds.kline.get_latest_daily_kline(symbol)
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
            from application.services.data_service import DataService
            ds = DataService()

            # 获取上证指数最新K线
            kline = ds.kline.get_latest_daily_kline('000001.SH')
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


def register_intraday_monitor_to_scheduler():
    """将盘中监控注册到 APScheduler

    交易时段每30分钟执行一次。
    """
    from application.services.unified_scheduler import get_unified_scheduler

    scheduler = get_unified_scheduler()
    monitor = get_intraday_monitor()

    # 上午 09:30-11:30 每30分钟
    scheduler.add_cron_job(
        func=monitor.check,
        job_id='intraday_monitor_am',
        name='盘中监控(上午)',
        minute='0,30',
        hour='9-11',
        day_of_week='mon-fri',
    )

    # 下午 13:00-15:00 每30分钟
    scheduler.add_cron_job(
        func=monitor.check,
        job_id='intraday_monitor_pm',
        name='盘中监控(下午)',
        minute='0,30',
        hour='13-14',
        day_of_week='mon-fri',
    )

    logger.info("IntradayMonitor registered (every 30min during trading hours)")
