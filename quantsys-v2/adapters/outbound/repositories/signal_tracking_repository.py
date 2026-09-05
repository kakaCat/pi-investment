"""M3-1 信号追踪 Repository

数据库操作层：signal_tracking 表的 CRUD
"""
from typing import Dict, List, Optional, Any
import structlog
import psycopg2

logger = structlog.get_logger(__name__)


class SignalTrackingRepository:
    """信号追踪数据访问对象"""
    
    def __init__(self, db_connection=None):
        """
        Args:
            db_connection: PostgreSQL 连接（可选，用于测试注入）
        """
        self.db = db_connection
        if not self.db:
            # 使用 psycopg2 直接连接
            self.db = psycopg2.connect(
                dbname="quant_investment",
                user="yunpeng",
                host="localhost"
            )
            self._owns_connection = True
        else:
            self._owns_connection = False
    
    def insert_signal(
        self,
        signal_date: str,
        symbol: str,
        grade: str,
        source: str,
        price: float,
        reason: Optional[str] = None
    ) -> int:
        """插入信号记录
        
        Returns:
            signal_id (int)
        """
        cursor = self.db.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO quant.signal_tracking (
                    signal_date, symbol, grade, source, price, reason
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (signal_date, symbol, source) 
                DO UPDATE SET
                    grade = EXCLUDED.grade,
                    price = EXCLUDED.price,
                    reason = EXCLUDED.reason,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (signal_date, symbol, grade, source, price, reason))
            
            result = cursor.fetchone()
            self.db.commit()
            
            return result[0]
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to insert signal: {e}")
            raise
        finally:
            cursor.close()
    
    def update_signal_performance(self, signal_id: int, updates: Dict[str, Any]) -> None:
        """更新信号表现数据
        
        Args:
            signal_id: 信号ID
            updates: 更新字段字典，如 {"price_5d": 10.5, "return_5d": 0.05, "hit_5d": True}
        """
        if not updates:
            return
        
        cursor = self.db.cursor()
        
        try:
            # 动态构建 SET 子句
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                set_clauses.append(f"{field} = %s")
                values.append(value)
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(signal_id)
            
            sql = f"""
                UPDATE quant.signal_tracking
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """
            
            cursor.execute(sql, values)
            self.db.commit()
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update signal {signal_id}: {e}")
            raise
        finally:
            cursor.close()
    
    def get_signals_by_date(self, signal_date: str) -> List[Dict]:
        """获取指定日期的所有信号"""
        cursor = self.db.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, signal_date, symbol, grade, source, price, reason,
                    price_5d, price_10d, price_20d,
                    return_5d, return_10d, return_20d,
                    hit_5d, hit_10d, hit_20d,
                    created_at, updated_at
                FROM quant.signal_tracking
                WHERE signal_date = %s
                ORDER BY created_at DESC
            """, (signal_date,))
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
        
        finally:
            cursor.close()
    
    def get_signals_after_date(self, start_date: str) -> List[Dict]:
        """获取指定日期之后的所有信号"""
        cursor = self.db.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, signal_date, symbol, grade, source, price, reason,
                    price_5d, price_10d, price_20d,
                    return_5d, return_10d, return_20d,
                    hit_5d, hit_10d, hit_20d,
                    created_at, updated_at
                FROM quant.signal_tracking
                WHERE signal_date >= %s
                ORDER BY signal_date DESC, created_at DESC
            """, (start_date,))
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
        
        finally:
            cursor.close()
    
    def get_signals(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        grade: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """查询信号（支持多条件过滤）"""
        cursor = self.db.cursor()
        
        try:
            conditions = []
            params = []
            
            if start_date:
                conditions.append("signal_date >= %s")
                params.append(start_date)
            
            if end_date:
                conditions.append("signal_date <= %s")
                params.append(end_date)
            
            if grade:
                conditions.append("grade = %s")
                params.append(grade)
            
            if source:
                conditions.append("source = %s")
                params.append(source)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)
            
            cursor.execute(f"""
                SELECT 
                    id, signal_date, symbol, grade, source, price, reason,
                    price_5d, price_10d, price_20d,
                    return_5d, return_10d, return_20d,
                    hit_5d, hit_10d, hit_20d,
                    created_at, updated_at
                FROM quant.signal_tracking
                {where_clause}
                ORDER BY signal_date DESC, created_at DESC
                LIMIT %s
            """, params)
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
        
        finally:
            cursor.close()
    
    def get_signal_by_id(self, signal_id: int) -> Optional[Dict]:
        """根据ID获取单个信号"""
        cursor = self.db.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, signal_date, symbol, grade, source, price, reason,
                    price_5d, price_10d, price_20d,
                    return_5d, return_10d, return_20d,
                    hit_5d, hit_10d, hit_20d,
                    created_at, updated_at
                FROM quant.signal_tracking
                WHERE id = %s
            """, (signal_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        
        finally:
            cursor.close()
