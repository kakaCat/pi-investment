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
        from adapters.outbound.repositories.signal_tracking_repository import SignalTrackingRepository
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
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """批量更新信号表现（盘后例程调用）
        
        回填逻辑：
        - 5日后：计算 price_5d, return_5d, hit_5d
        - 10日后：计算 price_10d, return_10d, hit_10d
        - 20日后：计算 price_20d, return_20d, hit_20d
        
        Args:
            signal_date: 指定更新日期（None=更新最近lookback_days内的所有信号）
            lookback_days: 回溯天数
        
        Returns:
            {"success": True, "updated": 15, "details": {...}}
        """
        from adapters.outbound.repositories.signal_tracking_repository import SignalTrackingRepository
        from adapters.outbound.repositories.kline_repository import KlineORMRepository
        
        repo = SignalTrackingRepository(self.db)
        kline_repo = KlineORMRepository()
        
        # 获取待更新的信号
        if signal_date:
            signals = repo.get_signals_by_date(signal_date)
        else:
            cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            signals = repo.get_signals_after_date(cutoff)
        
        updated_count = 0
        details = {"5d": 0, "10d": 0, "20d": 0}
        
        for signal in signals:
            sig_date = signal['signal_date']
            # 确保是字符串格式
            if isinstance(sig_date, datetime):
                sig_date = sig_date.strftime('%Y-%m-%d')
            elif hasattr(sig_date, 'isoformat'):
                sig_date = sig_date.isoformat()
            
            symbol = signal['symbol']
            entry_price = signal['price']
            
            updates = {}
            
            # 5日表现
            if signal['price_5d'] is None:
                date_5d = self._get_trading_date_after(sig_date, 5)
                if date_5d and date_5d <= datetime.now().strftime('%Y-%m-%d'):
                    price_5d = self._get_close_price(kline_repo, symbol, date_5d)
                    if price_5d:
                        updates['price_5d'] = price_5d
                        updates['return_5d'] = (price_5d / entry_price - 1)
                        updates['hit_5d'] = (price_5d > entry_price)
                        details["5d"] += 1
            
            # 10日表现
            if signal['price_10d'] is None:
                date_10d = self._get_trading_date_after(sig_date, 10)
                if date_10d and date_10d <= datetime.now().strftime('%Y-%m-%d'):
                    price_10d = self._get_close_price(kline_repo, symbol, date_10d)
                    if price_10d:
                        updates['price_10d'] = price_10d
                        updates['return_10d'] = (price_10d / entry_price - 1)
                        updates['hit_10d'] = (price_10d > entry_price)
                        details["10d"] += 1
            
            # 20日表现
            if signal['price_20d'] is None:
                date_20d = self._get_trading_date_after(sig_date, 20)
                if date_20d and date_20d <= datetime.now().strftime('%Y-%m-%d'):
                    price_20d = self._get_close_price(kline_repo, symbol, date_20d)
                    if price_20d:
                        updates['price_20d'] = price_20d
                        updates['return_20d'] = (price_20d / entry_price - 1)
                        updates['hit_20d'] = (price_20d > entry_price)
                        details["20d"] += 1
            
            if updates:
                repo.update_signal_performance(signal['id'], updates)
                updated_count += 1
        
        logger.info(
            "signal_performance_updated",
            updated_count=updated_count,
            details=details
        )
        
        return {
            "success": True,
            "updated": updated_count,
            "details": details
        }
    
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
        from adapters.outbound.repositories.signal_tracking_repository import SignalTrackingRepository
        
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
                stats[grade] = {"count": 0}
                continue
            
            # 计算各周期胜率和平均收益
            stats[grade] = {
                "count": len(grade_signals),
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
        
        简化实现：假设每周5个交易日，实际应查交易日历
        """
        from datetime import datetime, timedelta
        
        base_date = datetime.strptime(date_str, '%Y-%m-%d')
        # 简单估算：N个交易日 ≈ N * 1.4 自然日（考虑周末）
        estimated_days = int(trading_days * 1.4)
        target_date = base_date + timedelta(days=estimated_days)
        
        return target_date.strftime('%Y-%m-%d')
    
    def _get_close_price(self, kline_repo, symbol: str, date: str) -> Optional[float]:
        """获取指定日期的收盘价"""
        try:
            # 使用 KLineRepository 获取K线
            klines = kline_repo.get_daily_klines(
                symbol=symbol,
                start_date=date,
                end_date=date
            )
            if klines and len(klines) > 0:
                return float(klines[0]['close'])
        except Exception as e:
            logger.warning(f"Failed to get close price for {symbol} on {date}: {e}")
        
        return None
