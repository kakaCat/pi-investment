"""
Stock Pool Repository - CRUD for quant.stock_pools table.

2026-08-04 恢复说明：ORM 重构把本仓储换成缺 dict 契约的残版
（create(dict) 静默吞错返回 None，update/update_symbols/update_validation/
delete/update_scan_enabled 全缺失），导致股票池创建/更新/删除/动态刷新/
扫描开关等生产链路静默退化。按归档 8f06ae1^ 版本恢复旧实现
（symbols 列为 ARRAY、filter_template/members/last_validation/last_signal_scan
为 JSONB，与生产表结构一致），保留 StockPoolORMRepository 别名兼容调用方。
"""
import json
import logging
from typing import Dict, List, Optional

from infrastructure.persistence.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


# ORM 模型保留给 heatmap_repository 等 SQLAlchemy 查询方使用
# （仓储本体走 psycopg2 旧契约，两者共存）
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, ARRAY
from infrastructure.persistence.orm.base import Base


class StockPool(Base):
    __tablename__ = 'stock_pools'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    pool_type = Column(String(10), nullable=False)
    description = Column(Text)
    symbols = Column(ARRAY(Text))
    filter_template = Column(JSON)
    refresh_interval = Column(String(20))
    last_refreshed_at = Column(DateTime)
    last_validation = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    members = Column(JSON)
    scan_enabled = Column(Boolean, default=True)
    last_signal_scan = Column(JSON)


class StockPoolRepository(BaseRepository):
    """Data access for stock_pools table."""

    def create(self, data: Dict) -> Dict:
        """Create a new stock pool. Returns the created pool dict."""
        cursor = self._get_cursor()
        try:
            cursor.execute("""
                INSERT INTO quant.stock_pools
                    (name, pool_type, description, symbols,
                     filter_template, refresh_interval)
                VALUES
                    (%(name)s, %(pool_type)s, %(description)s, %(symbols)s,
                     %(filter_template)s, %(refresh_interval)s)
                RETURNING id
            """, {
                'name': data['name'],
                'pool_type': data['pool_type'],
                'description': data.get('description'),
                'symbols': data.get('symbols', []),
                'filter_template': json.dumps(data['filter_template']) if data.get('filter_template') else None,
                'refresh_interval': data.get('refresh_interval'),
            })
            result = dict(cursor.fetchone())
            self.db.commit()
            return self.get_by_id(result['id'])
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def get_by_id(self, pool_id: int) -> Optional[Dict]:
        """Get a pool by ID. Returns None if not found."""
        cursor = self._get_cursor()
        try:
            cursor.execute(
                "SELECT * FROM quant.stock_pools WHERE id = %(id)s",
                {'id': pool_id}
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._parse_row(row)
        finally:
            cursor.close()

    def get_pool(self, pool_id: int) -> Optional[Dict]:
        """get_by_id 的别名（ORM 时期引入的调用名，16 处生产调用）"""
        return self.get_by_id(pool_id)

    def get_all(self) -> List[Dict]:
        """Get all stock pools."""
        cursor = self._get_cursor()
        try:
            cursor.execute("SELECT * FROM quant.stock_pools ORDER BY created_at DESC")
            return [self._parse_row(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_dynamic_pools(self) -> List[Dict]:
        """Get all dynamic pools (for scheduler recovery)."""
        cursor = self._get_cursor()
        try:
            cursor.execute(
                "SELECT * FROM quant.stock_pools WHERE pool_type = 'dynamic' ORDER BY id"
            )
            return [self._parse_row(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def update(self, pool_id: int, data: Dict) -> Optional[Dict]:
        """Update pool fields. Returns updated pool or None if not found."""
        allowed = {'name', 'description', 'symbols', 'members', 'filter_template', 'refresh_interval'}
        fields = {k: v for k, v in data.items() if k in allowed and v is not None}
        if not fields:
            return self.get_by_id(pool_id)

        set_clauses = []
        params = {'id': pool_id}
        for key, value in fields.items():
            if key in ('filter_template', 'members'):
                params[key] = json.dumps(value)
            else:
                params[key] = value
            set_clauses.append(f"{key} = %({key})s")
        set_clauses.append("updated_at = NOW()")

        cursor = self._get_cursor()
        try:
            cursor.execute(f"""
                UPDATE quant.stock_pools
                SET {', '.join(set_clauses)}
                WHERE id = %(id)s
                RETURNING id
            """, params)
            result = cursor.fetchone()
            self.db.commit()
            if not result:
                return None
            return self.get_by_id(pool_id)
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def update_symbols(self, pool_id: int, symbols: List[str]) -> Optional[Dict]:
        """Update pool symbols and set last_refreshed_at. Used by dynamic pool refresh."""
        cursor = self._get_cursor()
        try:
            cursor.execute("""
                UPDATE quant.stock_pools
                SET symbols = %(symbols)s,
                    last_refreshed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING id
            """, {'id': pool_id, 'symbols': symbols})
            result = cursor.fetchone()
            self.db.commit()
            if not result:
                return None
            return self.get_by_id(pool_id)
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def update_validation(self, pool_id: int, validation: Dict) -> Optional[Dict]:
        """Update last_validation JSON snapshot."""
        cursor = self._get_cursor()
        try:
            cursor.execute("""
                UPDATE quant.stock_pools
                SET last_validation = %(validation)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING id
            """, {'id': pool_id, 'validation': json.dumps(validation)})
            result = cursor.fetchone()
            self.db.commit()
            if not result:
                return None
            return self.get_by_id(pool_id)
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def delete(self, pool_id: int) -> bool:
        """Delete a pool. Returns True if deleted, False if not found."""
        cursor = self._get_cursor()
        try:
            cursor.execute(
                "DELETE FROM quant.stock_pools WHERE id = %(id)s RETURNING id",
                {'id': pool_id}
            )
            result = cursor.fetchone()
            self.db.commit()
            return result is not None
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def update_scan_enabled(self, pool_id: int, enabled: bool) -> bool:
        """开关池的信号扫描（pools_async / pool_scan_switch 路由调用）"""
        cursor = self._get_cursor()
        try:
            cursor.execute("""
                UPDATE quant.stock_pools
                SET scan_enabled = %(enabled)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING id
            """, {'id': pool_id, 'enabled': enabled})
            result = cursor.fetchone()
            self.db.commit()
            return result is not None
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def update_signal_scan(self, pool_id: int, scan_result: Dict) -> Optional[Dict]:
        """
        保存信号扫描结果到last_signal_scan字段

        Args:
            pool_id: 股票池ID
            scan_result: 扫描结果（包含buy_signals, sell_signals等）

        Returns:
            更新后的股票池，或None如果不存在
        """
        cursor = self._get_cursor()
        try:
            cursor.execute("""
                UPDATE quant.stock_pools
                SET last_signal_scan = %(scan_result)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING id
            """, {'id': pool_id, 'scan_result': json.dumps(scan_result)})
            result = cursor.fetchone()
            self.db.commit()
            if not result:
                return None
            return self.get_by_id(pool_id)
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def _parse_row(self, row) -> Dict:
        """Convert a database row to a dict, parsing JSONB fields."""
        d = dict(row)
        for jsonb_field in ('filter_template', 'last_validation', 'members', 'last_signal_scan'):
            if isinstance(d.get(jsonb_field), str):
                d[jsonb_field] = json.loads(d[jsonb_field])
        return d


# 兼容别名：ORM 时期的调用名
StockPoolORMRepository = StockPoolRepository

__all__ = ['StockPoolRepository', 'StockPoolORMRepository']
