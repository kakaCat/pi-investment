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
            self.db = self._connect()
            self._owns_connection = True
        else:
            self._owns_connection = False
    
    def _connect(self):
        """新建连接 —— 走**连接池**（2026-09-13，w-32314d00，REQ-24e15d t2）。

        原先 `psycopg2.connect(...)` 直连且长期持有：既绕开连接池/session_guard，
        也会被 PostgreSQL 的 idle_in_transaction_session_timeout 强杀（事件 9c8ebd29 / 21ee9ab6）。
        PooledConnection 保持 `cursor()/commit()/rollback()/close()/closed` 同一套用法，
        且 close() 是归还连接池 —— 上面的 _ensure_connection 自愈逻辑照常工作。
        """
        from infrastructure.persistence.database.engine import PooledConnection
        return PooledConnection()

    def _ensure_connection(self):
        """连接可用性检查 + 自愈重建（幂等）。

        2026-09-13（w-32314d00，事件 21ee9ab6）：本 Repository 持有**长寿命裸连接**，
        一旦被 PostgreSQL 的 idle_in_transaction_session_timeout 杀掉，旧代码在 except 里
        又对死连接调 rollback() → 抛 InterfaceError: connection already closed，**把真因
        （terminating connection due to idle-in-transaction timeout）完全掩盖**，且连接永不重建，
        之后每次调用都继续失败。这里补上检查与重建。
        """
        conn = self.db
        if conn is None or getattr(conn, 'closed', 0):
            self.db = self._connect()
            self._owns_connection = True
            logger.warning("signal_tracking: 连接不可用，已重建（自愈）")
        return self.db

    def _safe_rollback(self, context: str) -> None:
        """回滚但**不掩盖原始异常**；连接已死则丢弃，交由下次调用重建。"""
        try:
            if getattr(self.db, 'closed', 0):
                raise psycopg2.InterfaceError('connection already closed')
            self.db.rollback()
        except Exception as rb_err:  # noqa: BLE001 回滚失败不能顶替原始异常
            logger.error(
                f"signal_tracking 回滚失败（{context}）: {rb_err}；丢弃该连接，下次调用重建"
            )
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None

    def _end_read(self) -> None:
        """读操作后结束事务。

        2026-09-13（同事件）：psycopg2 在第一条语句处隐式开启事务，读方法原本不 commit/rollback，
        长寿命连接于两次调用之间**空闲在事务中**；超过 PG 的 idle_in_transaction_session_timeout
        即被服务端杀连接 → 下一次写操作 bomb（本事件的真实起点）。读后显式结束事务即可根治。
        """
        try:
            if self.db is not None and not getattr(self.db, 'closed', 0):
                self.db.rollback()
        except Exception as e:  # noqa: BLE001 结束事务失败不影响本次读结果，交由下次调用自愈
            logger.warning(f"signal_tracking 读后结束事务失败: {e}")
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
        cursor = self._ensure_connection().cursor()
        
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
            logger.error(f"Failed to insert signal: {e}")
            self._safe_rollback('insert_signal')
            raise
        finally:
            # 统一收尾：无论读写，退出前结束事务——长寿命连接空闲在事务中会被 PG
            # idle_in_transaction_session_timeout 杀掉（本事件 21ee9ab6 的真实起点）。
            self._end_read()
            cursor.close()
    
    def update_signal_performance(self, signal_id: int, updates: Dict[str, Any]) -> None:
        """更新信号表现数据
        
        Args:
            signal_id: 信号ID
            updates: 更新字段字典，如 {"price_5d": 10.5, "return_5d": 0.05, "hit_5d": True}
        """
        if not updates:
            return
        
        cursor = self._ensure_connection().cursor()
        
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
            # 先记**原始**异常（本次事故里真因是 idle-in-transaction 超时，
            # 被 rollback 的 InterfaceError 顶替后彻底看不见），再安全回滚。
            logger.error(f"Failed to update signal {signal_id}: {e}")
            self._safe_rollback('update_signal_performance')
            raise
        finally:
            # 统一收尾：无论读写，退出前结束事务——长寿命连接空闲在事务中会被 PG
            # idle_in_transaction_session_timeout 杀掉（本事件 21ee9ab6 的真实起点）。
            self._end_read()
            cursor.close()
    
    def get_signals_by_date(self, signal_date: str) -> List[Dict]:
        """获取指定日期的所有信号"""
        cursor = self._ensure_connection().cursor()
        
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
            # 统一收尾：无论读写，退出前结束事务——长寿命连接空闲在事务中会被 PG
            # idle_in_transaction_session_timeout 杀掉（本事件 21ee9ab6 的真实起点）。
            self._end_read()
            cursor.close()
    
    def get_signals_after_date(self, start_date: str) -> List[Dict]:
        """获取指定日期之后的所有信号"""
        cursor = self._ensure_connection().cursor()
        
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
            # 统一收尾：无论读写，退出前结束事务——长寿命连接空闲在事务中会被 PG
            # idle_in_transaction_session_timeout 杀掉（本事件 21ee9ab6 的真实起点）。
            self._end_read()
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
        cursor = self._ensure_connection().cursor()
        
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
            # 统一收尾：无论读写，退出前结束事务——长寿命连接空闲在事务中会被 PG
            # idle_in_transaction_session_timeout 杀掉（本事件 21ee9ab6 的真实起点）。
            self._end_read()
            cursor.close()
    
    def get_signal_by_id(self, signal_id: int) -> Optional[Dict]:
        """根据ID获取单个信号"""
        cursor = self._ensure_connection().cursor()
        
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
            # 统一收尾：无论读写，退出前结束事务——长寿命连接空闲在事务中会被 PG
            # idle_in_transaction_session_timeout 杀掉（本事件 21ee9ab6 的真实起点）。
            self._end_read()
            cursor.close()
