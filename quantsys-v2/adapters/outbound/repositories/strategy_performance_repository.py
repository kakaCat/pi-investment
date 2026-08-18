"""
Strategy Performance Repository - 策略表现记录

2026-08-04 恢复说明：ORM 重构（8f06ae1 系）曾把本仓储换成指向
quant.strategy_performances（复数，仅 id+created_at）的空壳 stub，
create/get_statistics 等全部丢失，导致 StrategyWeightAdjuster 动态权重、
ExperienceAccumulator 经验积累、StrategyRotationEngine 轮换评估静默退化。
现按归档仓库 6281332 的旧实现恢复，指向真实表 quant.strategy_performance（单数）。
对外保留 StrategyPerformanceORMRepository 别名（调用方均用此名）。
"""
from typing import List, Dict, Optional
import json
from datetime import date
from infrastructure.persistence.database.base_repository import BaseRepository


class StrategyPerformanceRepository(BaseRepository):
    """策略表现 Repository（quant.strategy_performance 表）"""

    def __init__(self, db_connection=None):
        # 兼容 BaseRepository 形参，调用父类初始化以设置连接管理属性
        super().__init__(db_connection)

    # ==================== 创建方法 ====================

    def create(
        self,
        strategy_name: str,
        symbol: str,
        signal_date: date,
        entry_price: float,
        exit_price: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        holding_days: int = 0,
        scenario_tags: Optional[List[str]] = None,
        params_snapshot: Optional[Dict] = None,
        source: str = 'paper'
    ) -> Dict:
        """
        创建策略表现记录

        Args:
            strategy_name: 策略名称
            symbol: 标的代码
            signal_date: 信号日期
            entry_price: 入场价格
            exit_price: 出场价格（可选）
            pnl_pct: 盈亏百分比（可选）
            holding_days: 持仓天数
            scenario_tags: 场景标签列表
            params_snapshot: 参数快照
            source: 来源 ('paper' 或 'live')

        Returns:
            创建的记录
        """
        query = """
            INSERT INTO quant.strategy_performance (
                strategy_name, symbol, signal_date, entry_price, exit_price,
                pnl_pct, holding_days, scenario_tags, params_snapshot, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """

        cursor = self._get_cursor()
        try:
            cursor.execute(query, (
                strategy_name,
                symbol,
                signal_date,
                entry_price,
                exit_price,
                pnl_pct,
                holding_days,
                json.dumps(scenario_tags) if scenario_tags else None,
                json.dumps(params_snapshot) if params_snapshot else None,
                source
            ))
            result = cursor.fetchone()
            self.db.commit()

            record = dict(result)
            # PostgreSQL JSONB 字段已经是 Python 对象，无需 json.loads
            return record
        finally:
            cursor.close()

    # ==================== 更新方法 ====================

    def update_exit(
        self,
        record_id: int,
        exit_price: float,
        holding_days: int
    ) -> Optional[Dict]:
        """
        更新出场价格和盈亏

        Args:
            record_id: 记录ID
            exit_price: 出场价格
            holding_days: 持仓天数

        Returns:
            更新后的记录
        """
        # 先获取入场价格
        cursor = self._get_cursor()
        try:
            cursor.execute(
                "SELECT entry_price FROM quant.strategy_performance WHERE id = %s",
                (record_id,)
            )
            result = cursor.fetchone()
            if not result:
                return None

            entry_price = float(result['entry_price'])
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100

            # 更新记录
            query = """
                UPDATE quant.strategy_performance
                SET exit_price = %s,
                    pnl_pct = %s,
                    holding_days = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
            """

            cursor.execute(query, (exit_price, pnl_pct, holding_days, record_id))
            result = cursor.fetchone()
            self.db.commit()

            if result:
                record = dict(result)
                # PostgreSQL JSONB 字段已经是 Python 对象，无需 json.loads
                return record

            return None
        finally:
            cursor.close()

    # ==================== 查询方法 ====================

    def get_by_strategy_and_symbol(
        self,
        strategy_name: str,
        symbol: str,
        source: Optional[str] = None
    ) -> List[Dict]:
        """
        按策略和标的查询

        Args:
            strategy_name: 策略名称
            symbol: 标的代码
            source: 来源筛选（可选）

        Returns:
            记录列表
        """
        if source:
            query = """
                SELECT *
                FROM quant.strategy_performance
                WHERE strategy_name = %s
                  AND symbol = %s
                  AND source = %s
                ORDER BY signal_date DESC
            """
            params = (strategy_name, symbol, source)
        else:
            query = """
                SELECT *
                FROM quant.strategy_performance
                WHERE strategy_name = %s
                  AND symbol = %s
                ORDER BY signal_date DESC
            """
            params = (strategy_name, symbol)

        cursor = self._get_cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()

            records = []
            for row in results:
                record = dict(row)
                # PostgreSQL JSONB 字段已经是 Python 对象，无需 json.loads
                records.append(record)

            return records
        finally:
            cursor.close()

    def get_recent(
        self,
        strategy_name: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        获取最近N条记录

        Args:
            strategy_name: 策略名称筛选（可选）
            symbol: 标的筛选（可选）
            limit: 返回数量

        Returns:
            记录列表
        """
        conditions = []
        params = []

        if strategy_name:
            conditions.append("strategy_name = %s")
            params.append(strategy_name)

        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT *
            FROM quant.strategy_performance
            WHERE {where_clause}
            ORDER BY signal_date DESC
            LIMIT %s
        """
        params.append(limit)

        cursor = self._get_cursor()
        try:
            cursor.execute(query, tuple(params))
            results = cursor.fetchall()

            records = []
            for row in results:
                record = dict(row)
                # PostgreSQL JSONB 字段已经是 Python 对象，无需 json.loads
                records.append(record)

            return records
        finally:
            cursor.close()

    def get_by_scenario_tag(self, tag: str) -> List[Dict]:
        """
        按场景标签查询

        Args:
            tag: 场景标签

        Returns:
            包含该标签的记录列表
        """
        query = """
            SELECT *
            FROM quant.strategy_performance
            WHERE scenario_tags::text LIKE %s
            ORDER BY signal_date DESC
        """

        cursor = self._get_cursor()
        try:
            cursor.execute(query, (f'%{tag}%',))
            results = cursor.fetchall()

            records = []
            for row in results:
                record = dict(row)
                # PostgreSQL JSONB 字段已经是 Python 对象，无需 json.loads
                records.append(record)

            return records
        finally:
            cursor.close()

    # ==================== 统计方法 ====================

    def get_statistics(
        self,
        strategy_name: str,
        symbol: Optional[str] = None,
        source: Optional[str] = None
    ) -> Optional[Dict]:
        """
        获取策略统计数据

        Args:
            strategy_name: 策略名称
            symbol: 标的筛选（可选）
            source: 来源筛选（可选）

        Returns:
            统计数据（含 total_trades/win_trades/avg_pnl_pct/win_rate 等）；
            无已平仓记录时返回 None
        """
        conditions = ["strategy_name = %s", "exit_price IS NOT NULL"]
        params = [strategy_name]

        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)

        if source:
            conditions.append("source = %s")
            params.append(source)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as win_trades,
                SUM(CASE WHEN pnl_pct <= 0 THEN 1 ELSE 0 END) as loss_trades,
                AVG(pnl_pct) as avg_pnl_pct,
                AVG(holding_days) as avg_holding_days,
                MAX(pnl_pct) as max_pnl_pct,
                MIN(pnl_pct) as min_pnl_pct
            FROM quant.strategy_performance
            WHERE {where_clause}
        """

        cursor = self._get_cursor()
        try:
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()

            if not result or result['total_trades'] == 0:
                return None

            stats = dict(result)
            # 转换 Decimal 为 float
            for key in ['avg_pnl_pct', 'avg_holding_days', 'max_pnl_pct', 'min_pnl_pct']:
                if stats.get(key) is not None:
                    stats[key] = float(stats[key])

            stats['win_rate'] = (stats['win_trades'] / stats['total_trades']) * 100 if stats['total_trades'] > 0 else 0

            return stats
        finally:
            cursor.close()


# 兼容别名：调用方（order_service / strategy_weight_adjuster /
# experience_accumulator / strategy_rotation_engine）均使用 ORM 命名
StrategyPerformanceORMRepository = StrategyPerformanceRepository

__all__ = ['StrategyPerformanceRepository', 'StrategyPerformanceORMRepository']
