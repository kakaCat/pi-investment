"""Account Data Access Object."""

from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime

from .base_dao import BaseDAO


class AccountDAO(BaseDAO):
    """账户数据访问对象"""

    def get_account(self, name: str = 'Default Account') -> Optional[Dict]:
        """获取账户信息

        Args:
            name: 账户名称

        Returns:
            账户信息，不存在返回 None
        """
        query = f"""
            SELECT * FROM {self._build_table_name('accounts')}
            WHERE name = %s
        """
        results = self.execute_query(query, (name,))
        return results[0] if results else None

    def update_account(self, name: str, data: Dict) -> int:
        """更新账户信息

        Args:
            name: 账户名称
            data: 更新数据，允许的字段：current_capital, currency, notes

        Returns:
            影响的行数
        """
        # 允许更新的字段
        allowed_fields = {'current_capital', 'currency', 'notes'}

        # 过滤出允许的字段
        update_fields = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_fields:
            return 0

        # 自动设置 updated_at
        update_fields['updated_at'] = datetime.now()

        # 构建 SET 子句
        set_clause = ', '.join([f"{field} = %s" for field in update_fields.keys()])
        params = list(update_fields.values())
        params.append(name)

        query = f"""
            UPDATE {self._build_table_name('accounts')}
            SET {set_clause}
            WHERE name = %s
        """

        return self.execute_update(query, tuple(params))
