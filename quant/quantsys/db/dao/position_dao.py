"""Position Data Access Object."""

from __future__ import annotations

from typing import Dict, List, Optional

from .base_dao import BaseDAO


class PositionDAO(BaseDAO):
    """持仓数据访问对象"""

    def list_positions(
        self,
        account_id: str = 'default',
        status: str = 'open'
    ) -> List[Dict]:
        """获取持仓列表

        Args:
            account_id: 账户 ID
            status: 持仓状态（open/closed）

        Returns:
            持仓列表
        """
        query = f"""
            SELECT * FROM {self._build_table_name('positions')}
            WHERE account_id = %s AND status = %s
            ORDER BY entry_date DESC
        """
        return self.execute_query(query, (account_id, status))

    def get_position(
        self,
        symbol: str,
        account_id: str = 'default'
    ) -> Optional[Dict]:
        """获取单个持仓详情

        Args:
            symbol: 股票代码
            account_id: 账户 ID

        Returns:
            持仓详情字典，如果不存在则返回 None
        """
        query = f"""
            SELECT * FROM {self._build_table_name('positions')}
            WHERE symbol = %s AND account_id = %s AND status = 'open'
            LIMIT 1
        """
        results = self.execute_query(query, (symbol, account_id))
        return results[0] if results else None

    def update_position(
        self,
        symbol: str,
        data: Dict,
        account_id: str = 'default'
    ) -> int:
        """更新持仓字段

        Args:
            symbol: 股票代码
            data: 要更新的字段字典
            account_id: 账户 ID

        Returns:
            更新的行数
        """
        # 允许更新的字段
        allowed_fields = {'quantity', 'current_price', 'stop_loss', 'take_profit', 'notes'}

        # 过滤出允许的字段
        update_fields = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_fields:
            return 0

        # 构建 SET 子句
        set_clause = ', '.join([f"{field} = %s" for field in update_fields.keys()])
        set_clause += ', updated_at = NOW()'

        # 构建参数元组
        params = tuple(update_fields.values()) + (symbol, account_id)

        query = f"""
            UPDATE {self._build_table_name('positions')}
            SET {set_clause}
            WHERE symbol = %s AND account_id = %s AND status = 'open'
        """

        return self.execute_update(query, params)

    def close_position(
        self,
        symbol: str,
        reason: Optional[str] = None,
        account_id: str = 'default'
    ) -> int:
        """关闭持仓

        Args:
            symbol: 股票代码
            reason: 关闭原因
            account_id: 账户 ID

        Returns:
            更新的行数
        """
        if reason:
            query = f"""
                UPDATE {self._build_table_name('positions')}
                SET status = 'closed',
                    notes = COALESCE(notes || ' | ', '') || %s,
                    updated_at = NOW()
                WHERE symbol = %s AND account_id = %s AND status = 'open'
            """
            params = (f"关闭原因: {reason}", symbol, account_id)
        else:
            query = f"""
                UPDATE {self._build_table_name('positions')}
                SET status = 'closed',
                    updated_at = NOW()
                WHERE symbol = %s AND account_id = %s AND status = 'open'
            """
            params = (symbol, account_id)

        return self.execute_update(query, params)

    def get_position_summary(
        self,
        account_id: str = 'default'
    ) -> Dict:
        """获取持仓统计信息

        Args:
            account_id: 账户 ID

        Returns:
            统计信息字典
        """
        query = f"""
            SELECT
                COUNT(*) as total_positions,
                COALESCE(SUM(quantity), 0) as total_quantity,
                COALESCE(SUM(entry_price * quantity), 0) as total_cost,
                COALESCE(SUM(current_price * quantity), 0) as total_market_value,
                COALESCE(SUM((current_price - entry_price) * quantity), 0) as total_pnl,
                CASE
                    WHEN SUM(entry_price * quantity) > 0
                    THEN (SUM((current_price - entry_price) * quantity) / SUM(entry_price * quantity)) * 100
                    ELSE 0
                END as total_pnl_pct
            FROM {self._build_table_name('positions')}
            WHERE account_id = %s AND status = 'open'
        """
        results = self.execute_query(query, (account_id,))
        return results[0] if results else {
            'total_positions': 0,
            'total_quantity': 0,
            'total_cost': 0,
            'total_market_value': 0,
            'total_pnl': 0,
            'total_pnl_pct': 0
        }
