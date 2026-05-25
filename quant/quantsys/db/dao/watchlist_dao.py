"""Watchlist Data Access Object."""

from __future__ import annotations

from typing import Dict, List, Optional

from .base_dao import BaseDAO


class WatchlistDAO(BaseDAO):
    """关注列表数据访问对象"""

    def list_watchlist(
        self,
        pool: Optional[str] = None,
        priority: Optional[int] = None,
        status: str = 'watching'
    ) -> List[Dict]:
        """获取关注列表

        Args:
            pool: 池子（A/B/C）
            priority: 优先级（1-5）
            status: 状态（watching/paused/removed）

        Returns:
            关注列表

        Raises:
            Exception: 数据库查询错误
        """
        conditions = ["status = %s"]
        params = [status]

        if pool is not None:
            conditions.append("pool = %s")
            params.append(pool)

        if priority is not None:
            conditions.append("priority = %s")
            params.append(priority)

        query = f"""
            SELECT * FROM {self._build_table_name('watchlist')}
            WHERE {' AND '.join(conditions)}
            ORDER BY priority ASC, symbol ASC
        """
        return self.execute_query(query, tuple(params))

    def get_watchlist_item(self, symbol: str) -> Optional[Dict]:
        """获取单个关注项详情

        Args:
            symbol: 股票代码

        Returns:
            关注项字典，如果不存在则返回 None

        Raises:
            Exception: 数据库查询错误
        """
        query = f"""
            SELECT * FROM {self._build_table_name('watchlist')}
            WHERE symbol = %s
        """
        results = self.execute_query(query, (symbol,))
        return results[0] if results else None

    def add_to_watchlist(self, data: Dict) -> str:
        """添加新的关注项

        Args:
            data: 关注项数据
                - symbol (必需): 股票代码
                - name (必需): 股票名称
                - market (必需): 市场（A/HK/US）
                - priority (可选): 优先级（1-5），默认 3
                - pool (可选): 池子（A/B/C）
                - status (可选): 状态，默认 'watching'
                - buy_range_low (可选): 买入区间下限
                - buy_range_high (可选): 买入区间上限
                - target_price (可选): 目标价
                - stop_loss (可选): 止损价
                - reason (可选): 关注原因
                - notes (可选): 备注

        Returns:
            新记录的 UUID

        Raises:
            ValueError: 缺少必需字段或股票代码已存在
            Exception: 数据库插入错误
        """
        # Validate required fields
        required_fields = ['symbol', 'name', 'market']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Required fields
        fields = ['symbol', 'name', 'market']
        values = [data['symbol'], data['name'], data['market']]

        # Optional fields with defaults
        if 'priority' in data:
            fields.append('priority')
            values.append(data['priority'])
        else:
            fields.append('priority')
            values.append(3)

        if 'status' in data:
            fields.append('status')
            values.append(data['status'])
        else:
            fields.append('status')
            values.append('watching')

        # Optional fields without defaults
        optional_fields = [
            'pool', 'buy_range_low', 'buy_range_high',
            'target_price', 'stop_loss', 'reason', 'notes'
        ]
        for field in optional_fields:
            if field in data:
                fields.append(field)
                values.append(data[field])

        placeholders = ', '.join(['%s'] * len(values))
        field_names = ', '.join(fields)

        query = f"""
            INSERT INTO {self._build_table_name('watchlist')} ({field_names})
            VALUES ({placeholders})
            RETURNING id
        """
        try:
            return self.execute_insert(query, tuple(values))
        except Exception as e:
            if 'unique constraint' in str(e).lower() or 'duplicate key' in str(e).lower():
                raise ValueError(f"Watchlist item already exists for symbol: {data['symbol']}")
            raise

    def remove_from_watchlist(self, symbol: str) -> int:
        """从关注列表中删除

        Args:
            symbol: 股票代码

        Returns:
            删除的行数

        Raises:
            Exception: 数据库删除错误
        """
        query = f"""
            DELETE FROM {self._build_table_name('watchlist')}
            WHERE symbol = %s
        """
        return self.execute_update(query, (symbol,))

    def update_watchlist_item(self, symbol: str, data: Dict) -> int:
        """更新关注项

        Args:
            symbol: 股票代码
            data: 要更新的字段
                - priority: 优先级（1-5）
                - pool: 池子（A/B/C）
                - status: 状态（watching/paused/removed）
                - buy_range_low: 买入区间下限
                - buy_range_high: 买入区间上限
                - target_price: 目标价
                - stop_loss: 止损价
                - reason: 关注原因
                - notes: 备注

        Returns:
            更新的行数

        Raises:
            Exception: 数据库更新错误
        """
        allowed_fields = [
            'priority', 'pool', 'status', 'buy_range_low', 'buy_range_high',
            'target_price', 'stop_loss', 'reason', 'notes'
        ]

        updates = []
        values = []

        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(data[field])

        if not updates:
            return 0

        # Always update updated_at
        updates.append("updated_at = NOW()")

        # Add symbol for WHERE clause
        values.append(symbol)

        query = f"""
            UPDATE {self._build_table_name('watchlist')}
            SET {', '.join(updates)}
            WHERE symbol = %s
        """
        return self.execute_update(query, tuple(values))
