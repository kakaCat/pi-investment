"""Base Data Access Object for quant_agent schema."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from psycopg2.extras import RealDictCursor

from ...data.db import Database


SCHEMA_NAME = 'quant_agent'


class BaseDAO:
    """基础 DAO 类，提供数据库连接和通用查询方法"""

    def __init__(self, db: Optional[Database] = None):
        """初始化 DAO

        Args:
            db: Database 实例，如果为 None 则创建新实例
        """
        self.db = db if db is not None else Database()
        self._conn = None

    @property
    def conn(self):
        """获取数据库连接"""
        if self._conn is None:
            self._conn = self.db.get_connection()
        return self._conn

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果列表

        Args:
            query: SQL 查询语句
            params: 查询参数

        Returns:
            结果列表，每个元素是一个字典
        """
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params or ())
        results = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in results]

    def execute_update(self, query: str, params: tuple = None) -> int:
        """执行更新操作并返回影响的行数

        Args:
            query: SQL 更新语句
            params: 更新参数

        Returns:
            影响的行数
        """
        cursor = self.conn.cursor()
        cursor.execute(query, params or ())
        rowcount = cursor.rowcount
        self.conn.commit()
        cursor.close()
        return rowcount

    def execute_insert(self, query: str, params: tuple = None) -> Optional[str]:
        """执行插入操作并返回新记录的 ID

        Args:
            query: SQL 插入语句（需要包含 RETURNING id）
            params: 插入参数

        Returns:
            新记录的 UUID（字符串格式），如果没有返回则为 None
        """
        cursor = self.conn.cursor()
        cursor.execute(query, params or ())
        result = cursor.fetchone()
        self.conn.commit()
        cursor.close()
        return str(result[0]) if result else None

    def _build_table_name(self, table: str) -> str:
        """构建完整的表名（包含 schema）

        Args:
            table: 表名

        Returns:
            完整表名，格式为 schema.table
        """
        return f"{SCHEMA_NAME}.{table}"
