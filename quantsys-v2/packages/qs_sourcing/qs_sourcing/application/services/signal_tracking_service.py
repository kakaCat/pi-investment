"""M3-1 信号质量追踪服务

功能：
- 记录买入信号（symbol/grade/source/price/reason）
- 盘后回填表现（5/10/20日收益率和命中率）
- 统计各级别信号的胜率

设计文档: docs/architecture/signal-grading.md
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)


class SignalTrackingService:
    """信号质量追踪服务"""
    
    def __init__(self, db_connection=None):
        """
        Args:
            db_connection: PostgreSQL 连接（可选，用于测试注入）
        """
        self.db = db_connection
    
    def record_signal(
        self,
        signal_date: str,
        symbol: str,
        grade: str,
        source: str,
        price: float,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """记录买入信号
        
        Args:
            signal_date: 信号日期 YYYY-MM-DD
            symbol: 股票代码
            grade: A/B/C
            source: 信号来源（strategy_execute/opportunity_scan/mainline_stocks/watch_rule）
            price: 买入价格
            reason: 信号理由（可选）
        
        Returns:
            {"success": True, "signal_id": 123}
        """
        if grade not in ('A', 'B', 'C'):
            raise ValueError(f"Invalid grade: {grade}, must be A/B/C")
        
        if source not in ('strategy_execute', 'opportunity_scan', 'mainline_stocks', 'watch_rule'):
            logger.warning(f"Unusual signal source: {source}")
        
        # 插入数据库
        from qs_sourcing.adapters.outbound.repositories.signal_tracking_repository import SignalTrackingRepository
        repo = SignalTrackingRepository(self.db)
        
        signal_id = repo.insert_signal(
            signal_date=signal_date,
            symbol=symbol,
            grade=grade,
            source=source,
            price=price,
            reason=reason
        )
        
        logger.info(
            "signal_recorded",
            signal_id=signal_id,
            symbol=symbol,
            grade=grade,
            source=source,
            price=price
        )
        
        return {
            "success": True,
            "signal_id": signal_id,
            "message": f"Signal recorded: {symbol} grade {grade}"
        }
    
    def update_performance(
        self,
        signal_date: str = None,
        lookback_days: Optional[int] = None,
        symbol: Optional[str] = None,
        refresh: bool = False,
    ) -> Dict[str, Any]:
        """批量回填 5/10/20 交易日表现，并显式报告无法回填的原因。

        - 默认扫描全部历史 NULL 欠账；显式 lookback_days 是自然日下界过滤。
        - 整次调用共享一份交易日历，所有目标日 K 线只做一次批量查询。
        - refresh=True 用于 K 线修复后的受控重算，必须限定 signal_date 或 symbol。
        - 未到期与目标日缺 K 线分开计数；缺数据绝不取邻日价格代替。
        """
        from qs_sourcing.adapters.outbound.repositories.signal_tracking_repository import SignalTrackingRepository
        from infrastructure.services.service_factory import ServiceFactory
        from qs_market_data.application.services.trading_calendar_service import TradingCalendarService

        if lookback_days is not None and lookback_days < 0:
            raise ValueError("lookback_days 必须 >= 0")
        if refresh and not (signal_date or symbol):
            raise ValueError("refresh=true 必须同时限定 signal_date 或 symbol")

        repo = SignalTrackingRepository(self.db)
        kline_repo = ServiceFactory.get_kline_repository()
        cutoff = (
            (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            if lookback_days is not None else None
        )
        if signal_date:
            signals = repo.get_signals_by_date(signal_date)
            if symbol:
                signals = [s for s in signals if s.get('symbol') == symbol]
            if not refresh:
                signals = [s for s in signals if any(
                    s.get(f'price_{h}d') is None for h in (5, 10, 20)
                )]
        else:
            signals = repo.get_signals_pending_backfill(
                symbol=symbol,
                include_filled=refresh,
                start_date=cutoff,
            )

        details = {"5d": 0, "10d": 0, "20d": 0}
        diagnostics = {
            "scanned_signals": len(signals),
            "candidate_horizons": 0,
            "not_due": 0,
            "missing_kline": 0,
            "invalid_signal": 0,
            "blocked": [],
            "refresh": refresh,
            "scope": {
                "signal_date": signal_date,
                "symbol": symbol,
                "lookback_days": lookback_days,
            },
        }
        if not signals:
            return {
                "success": True,
                "updated": 0,
                "details": details,
                "diagnostics": diagnostics,
                "complete": True,
            }

        today = datetime.now().strftime('%Y-%m-%d')
        normalized_signal_dates = [self._date_text(s.get('signal_date')) for s in signals]
        calendar = TradingCalendarService()
        raw_days = calendar.get_trading_days(
            start_date=min(d for d in normalized_signal_dates if d),
            end_date=today,
        )
        trading_days = sorted({self._date_text(d) for d in (raw_days or []) if self._date_text(d)})
        if not trading_days:
            raise RuntimeError("交易日历不可用：拒绝按自然日估算信号表现")
        day_index = {day: idx for idx, day in enumerate(trading_days)}

        work = []
        for signal, sig_date in zip(signals, normalized_signal_dates):
            symbol_value = str(signal.get('symbol') or '').split('.')[0]
            try:
                entry_price = float(signal['price'])
                if entry_price <= 0:
                    raise ValueError("entry price must be positive")
            except (TypeError, ValueError, KeyError) as exc:
                diagnostics['invalid_signal'] += 1
                diagnostics['blocked'].append({
                    "signal_id": signal.get('id'), "symbol": symbol_value,
                    "reason": "invalid_entry_price", "detail": str(exc),
                })
                continue
            if sig_date not in day_index:
                diagnostics['invalid_signal'] += 1
                diagnostics['blocked'].append({
                    "signal_id": signal.get('id'), "symbol": symbol_value,
                    "signal_date": sig_date, "reason": "signal_date_not_trading_day",
                })
                continue

            for horizon in (5, 10, 20):
                if not refresh and signal.get(f'price_{horizon}d') is not None:
                    continue
                target_idx = day_index[sig_date] + horizon
                if target_idx >= len(trading_days):
                    diagnostics['not_due'] += 1
                    continue
                work.append({
                    "signal": signal,
                    "symbol": symbol_value,
                    "entry_price": entry_price,
                    "horizon": horizon,
                    "target_date": trading_days[target_idx],
                })

        diagnostics['candidate_horizons'] = len(work)
        close_map = {}
        if work:
            # 查询异常必须响亮失败，不能被仓储的空 dict 伪装成"全市场缺 K"。
            batch = kline_repo.get_daily_klines_batch(
                symbols=sorted({item['symbol'] for item in work}),
                start_date=min(item['target_date'] for item in work),
                end_date=max(item['target_date'] for item in work),
                raise_on_error=True,
            )
            for symbol_value, rows in (batch or {}).items():
                bare_symbol = str(symbol_value).split('.')[0]
                for row in rows or []:
                    day = self._date_text(row.get('trade_date') or row.get('date'))
                    try:
                        close = float(row.get('close'))
                        if close > 0:
                            close_map[(bare_symbol, day)] = close
                    except (TypeError, ValueError):
                        continue

        updates_by_signal = {}
        for item in work:
            signal = item['signal']
            horizon = item['horizon']
            close = close_map.get((item['symbol'], item['target_date']))
            if close is None:
                diagnostics['missing_kline'] += 1
                diagnostics['blocked'].append({
                    "signal_id": signal.get('id'),
                    "symbol": item['symbol'],
                    "horizon": f"{horizon}d",
                    "target_date": item['target_date'],
                    "reason": "missing_kline",
                })
                continue
            updates = updates_by_signal.setdefault(signal['id'], {})
            updates[f'price_{horizon}d'] = close
            updates[f'return_{horizon}d'] = close / item['entry_price'] - 1
            updates[f'hit_{horizon}d'] = close > item['entry_price']
            details[f'{horizon}d'] += 1

        for signal_id, updates in updates_by_signal.items():
            repo.update_signal_performance(signal_id, updates)

        logger.info(
            "signal_performance_updated",
            updated_count=len(updates_by_signal),
            details=details,
            missing_kline=diagnostics['missing_kline'],
            not_due=diagnostics['not_due'],
        )
        return {
            "success": True,
            "updated": len(updates_by_signal),
            "details": details,
            "diagnostics": diagnostics,
            "complete": not diagnostics['blocked'],
        }

    @staticmethod
    def _date_text(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d')
        if hasattr(value, 'isoformat'):
            return value.isoformat()[:10]
        return str(value)[:10]
    
    def get_statistics(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        grade: Optional[str] = None,
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取信号统计报告
        
        Returns:
            {
                "total": 100,
                "by_grade": {
                    "A": {"count": 30, "hit_rate_5d": 0.75, "avg_return_5d": 0.08, ...},
                    "B": {...},
                    "C": {...}
                },
                "by_source": {...},
                "recent_signals": [...]
            }
        """
        from qs_sourcing.adapters.outbound.repositories.signal_tracking_repository import SignalTrackingRepository
        
        repo = SignalTrackingRepository(self.db)
        
        # 默认时间范围：最近30天
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 获取符合条件的信号
        signals = repo.get_signals(
            start_date=start_date,
            end_date=end_date,
            grade=grade,
            source=source
        )
        
        # 统计
        stats = {
            "total": len(signals),
            "date_range": {"start": start_date, "end": end_date},
            "by_grade": self._calculate_grade_stats(signals),
            "by_source": self._calculate_source_stats(signals),
            "recent_signals": signals[:10]  # 最近10条
        }
        
        return stats
    
    def _calculate_grade_stats(self, signals: List[Dict]) -> Dict[str, Dict]:
        """按级别统计"""
        stats = {}
        
        for grade in ['A', 'B', 'C']:
            grade_signals = [s for s in signals if s['grade'] == grade]
            
            if not grade_signals:
                stats[grade] = {"count": 0, "mature_count": 0}
                continue
            
            # count 是原始信号数；mature_count 只包含有 5 日表现的样本。
            stats[grade] = {
                "count": len(grade_signals),
                "mature_count": sum(1 for s in grade_signals if s.get('return_5d') is not None),
                "hit_rate_5d": self._calc_hit_rate(grade_signals, 'hit_5d'),
                "avg_return_5d": self._calc_avg_return(grade_signals, 'return_5d'),
                "hit_rate_10d": self._calc_hit_rate(grade_signals, 'hit_10d'),
                "avg_return_10d": self._calc_avg_return(grade_signals, 'return_10d'),
                "hit_rate_20d": self._calc_hit_rate(grade_signals, 'hit_20d'),
                "avg_return_20d": self._calc_avg_return(grade_signals, 'return_20d'),
            }
        
        return stats
    
    def _calculate_source_stats(self, signals: List[Dict]) -> Dict[str, Dict]:
        """按来源统计"""
        sources = set(s['source'] for s in signals)
        stats = {}
        
        for source in sources:
            source_signals = [s for s in signals if s['source'] == source]
            stats[source] = {
                "count": len(source_signals),
                "mature_count": sum(1 for s in source_signals if s.get('return_5d') is not None),
                "hit_rate_5d": self._calc_hit_rate(source_signals, 'hit_5d'),
                "avg_return_5d": self._calc_avg_return(source_signals, 'return_5d'),
            }
        
        return stats
    
    def _calc_hit_rate(self, signals: List[Dict], field: str) -> Optional[float]:
        """计算命中率"""
        valid = [s for s in signals if s.get(field) is not None]
        if not valid:
            return None
        hits = sum(1 for s in valid if s[field])
        return hits / len(valid)
    
    def _calc_avg_return(self, signals: List[Dict], field: str) -> Optional[float]:
        """计算平均收益率"""
        valid = [s for s in signals if s.get(field) is not None]
        if not valid:
            return None
        return sum(s[field] for s in valid) / len(valid)
    
    def _get_trading_date_after(self, date_str: str, trading_days: int) -> Optional[str]:
        """获取N个交易日后的日期

        2026-09-01 修复（investor w-8366e526）：原实现按 交易日*1.4 自然日估算，
        会落在周末/节假日 → 取收盘价恒空 → 回填静默失败。改用 TradingCalendarService
        真实交易日历推进。
        """
        try:
            from qs_market_data.application.services.trading_calendar_service import TradingCalendarService
            from datetime import datetime, timedelta

            base = datetime.strptime(date_str, '%Y-%m-%d').date()
            calendar = TradingCalendarService()
            # 3 倍自然日窗口兜底，从真实交易日历取信号日之后的第 N 个交易日
            end_hint = base + timedelta(days=int(trading_days * 3) + 7)
            days = calendar.get_trading_days(
                start_date=base.strftime('%Y-%m-%d'),
                end_date=end_hint.strftime('%Y-%m-%d'),
            )
            if days:
                dates = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in days]
                dates = [d for d in dates if d > date_str]
                if len(dates) >= trading_days:
                    return dates[trading_days - 1]
        except Exception as e:
            logger.warning(f"trading_date_calc_failed date={date_str} n={trading_days}: {e}")
        # 回退到原估算（至少不抛错）
        from datetime import datetime, timedelta
        return (datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=int(trading_days * 1.4))).strftime('%Y-%m-%d')

    def _get_close_price(self, kline_repo, symbol: str, date: str) -> Optional[float]:
        """获取指定日期的收盘价

        2026-09-01 修复（investor w-8366e526）：get_daily_klines 返回 polars
        DataFrame，原实现按 list 处理（`if klines and len(klines)>0` 触发
        DataFrame.__bool__ → TypeError → 回填恒失败）。
        """
        try:
            klines = kline_repo.get_daily_klines(
                symbol=symbol,
                start_date=date,
                end_date=date
            )
            if klines is None:
                return None
            # polars DataFrame
            if hasattr(klines, 'is_empty'):
                if klines.is_empty():
                    return None
                return float(klines['close'][0])
            # list[dict] / list[Row]
            if isinstance(klines, (list, tuple)) and len(klines) > 0:
                row = klines[0]
                if isinstance(row, dict):
                    return float(row.get('close'))
                return float(getattr(row, 'close'))
        except Exception as e:
            logger.warning(f"Failed to get close price for {symbol} on {date}: {e}")

        return None
