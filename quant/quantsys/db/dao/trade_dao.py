"""Trade Data Access Object."""

from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .base_dao import BaseDAO


class TradeDAO(BaseDAO):
    """交易历史数据访问对象"""

    def list_trades(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取交易历史

        Args:
            symbol: 股票代码
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
            limit: 返回记录数限制

        Returns:
            交易历史列表
        """
        conditions = []
        params = []

        if symbol is not None:
            conditions.append("symbol = %s")
            params.append(symbol)

        if start_date is not None:
            conditions.append("timestamp >= %s")
            params.append(start_date)

        if end_date is not None:
            conditions.append("timestamp <= %s")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT * FROM {self._build_table_name('position_history')}
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s
        """
        params.append(limit)
        return self.execute_query(query, tuple(params))

    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """获取单笔交易详情

        Args:
            trade_id: 交易 ID

        Returns:
            交易详情，不存在返回 None
        """
        query = f"""
            SELECT * FROM {self._build_table_name('position_history')}
            WHERE notes LIKE %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        results = self.execute_query(query, (f"%{trade_id}%",))
        return results[0] if results else None

    def get_trade_stats(
        self,
        symbol: Optional[str] = None,
        period: str = 'all'
    ) -> Dict:
        """获取交易统计

        Args:
            symbol: 股票代码，None 表示所有股票
            period: 统计周期，可选值：'all', 'year', 'month', 'week'

        Returns:
            交易统计信息，包含：
            - total_trades: 总交易次数
            - buy_count: 买入次数
            - sell_count: 卖出次数
            - total_pnl: 总盈亏
            - avg_pnl: 平均盈亏
            - win_count: 盈利次数
            - loss_count: 亏损次数
            - win_rate: 胜率
        """
        conditions = []
        params = []

        # 添加股票代码过滤
        if symbol is not None:
            conditions.append("symbol = %s")
            params.append(symbol)

        # 添加时间周期过滤
        if period != 'all':
            now = datetime.now()
            if period == 'year':
                start_date = now - timedelta(days=365)
            elif period == 'month':
                start_date = now - timedelta(days=30)
            elif period == 'week':
                start_date = now - timedelta(days=7)
            else:
                raise ValueError(f"Invalid period: {period}. Must be 'all', 'year', 'month', or 'week'")

            conditions.append("timestamp >= %s")
            params.append(start_date.strftime('%Y-%m-%d'))

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN action = 'buy' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN action = 'sell' THEN 1 ELSE 0 END) as sell_count,
                COALESCE(SUM(pnl), 0) as total_pnl,
                COALESCE(AVG(pnl), 0) as avg_pnl,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as win_count,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as loss_count
            FROM {self._build_table_name('position_history')}
            {where_clause}
        """

        results = self.execute_query(query, tuple(params))

        if not results or results[0]['total_trades'] == 0:
            return {
                'total_trades': 0,
                'buy_count': 0,
                'sell_count': 0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'win_count': 0,
                'loss_count': 0,
                'win_rate': 0.0
            }

        stats = results[0]
        total_trades = stats['total_trades']
        win_count = stats['win_count'] or 0

        # 计算胜率
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0

        return {
            'total_trades': total_trades,
            'buy_count': stats['buy_count'] or 0,
            'sell_count': stats['sell_count'] or 0,
            'total_pnl': float(stats['total_pnl'] or 0),
            'avg_pnl': float(stats['avg_pnl'] or 0),
            'win_count': win_count,
            'loss_count': stats['loss_count'] or 0,
            'win_rate': round(win_rate, 2)
        }
