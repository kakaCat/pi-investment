"""Stock Pool Repository - CRUD for quant.stock_pools table.

2026-08-04 恢复说明：ORM 重构把本仓储换成缺 dict 契约的残版
（create(dict) 静默吞错返回 None，update/update_symbols/update_validation/
delete/update_scan_enabled 全缺失），导致股票池创建/更新/删除/动态刷新/
扫描开关等生产链路静默退化。按归档 8f06ae1^ 版本恢复旧实现
（symbols 列为 ARRAY、filter_template/members/last_validation/last_signal_scan
为 JSONB，与生产表结构一致），保留 StockPoolORMRepository 别名兼容调用方。

2026-09-14（w-32314d00，REQ-24e15d B4）：**上一段说的"旧实现"本身是 db_cursor + 裸 SQL**
（10 处），本批把它真正落到 ORM —— 类改为继承 BaseORMRepository[StockPool]，
SQL 全部消失，JSONB 直接传 Python 对象（不再手工 json.dumps）。
对外契约（方法名、返回 dict、None 语义、bool 语义、字段白名单）**逐条保持不变**。
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


from sqlalchemy import ARRAY, Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from infrastructure.persistence.orm import BaseORMRepository
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


# update() 允许修改的字段（与旧实现的 allowed 集合一致）
_UPDATABLE_FIELDS = frozenset({
    'name', 'description', 'symbols', 'members', 'filter_template', 'refresh_interval',
})


class StockPoolRepository(BaseORMRepository[StockPool]):
    """Data access for stock_pools table.

    db_connection 参数仅为向后兼容保留（忽略）：连接由 scoped_session 按线程现取。
    """

    model = StockPool

    def __init__(self, db_connection=None):
        if self.model is None:
            raise ValueError('StockPoolRepository must set model')
        self._session = None

    def close(self):
        """兼容旧调用方的 no-op（连接不再由实例持有）。"""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    # ---------------- 内部 ----------------

    def _parse_row(self, row) -> Dict:
        """ORM 对象 → dict。

        旧实现要 JSONB 字段是 str 时再 json.loads（psycopg2 裸游标 + json.dumps 写入的遗留）；
        ORM 的 JSON 列读出来已是 Python 对象，这段兼容分支保留但正常情况下不会触发。
        """
        d = {c.name: getattr(row, c.name) for c in row.__table__.columns} if not isinstance(row, dict) else dict(row)
        for jsonb_field in ('filter_template', 'last_validation', 'members', 'last_signal_scan'):
            if isinstance(d.get(jsonb_field), str):
                try:
                    d[jsonb_field] = json.loads(d[jsonb_field])
                except (ValueError, TypeError):
                    pass
        return d

    def _get_model(self, pool_id: int) -> Optional[StockPool]:
        return (
            self.session.query(StockPool)
            .filter(StockPool.id == pool_id)
            .first()
        )

    # ---------------- 读 ----------------

    def get_by_id(self, pool_id: int) -> Optional[Dict]:
        """Get a pool by ID. Returns None if not found."""
        try:
            obj = self._get_model(pool_id)
            return self._parse_row(obj) if obj else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_by_id({pool_id}): {e}")
            return None

    def get_pool(self, pool_id: int) -> Optional[Dict]:
        """get_by_id 的别名（ORM 时期引入的调用名，16 处生产调用）"""
        return self.get_by_id(pool_id)

    def get_all(self) -> List[Dict]:
        """Get all stock pools."""
        try:
            rows = (
                self.session.query(StockPool)
                .order_by(StockPool.created_at.desc())
                .all()
            )
            return [self._parse_row(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_all: {e}")
            return []

    def get_dynamic_pools(self) -> List[Dict]:
        """Get all dynamic pools (for scheduler recovery)."""
        try:
            rows = (
                self.session.query(StockPool)
                .filter(StockPool.pool_type == 'dynamic')
                .order_by(StockPool.id.asc())
                .all()
            )
            return [self._parse_row(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_dynamic_pools: {e}")
            return []

    # ---------------- 写 ----------------

    def create(self, data: Dict) -> Dict:
        """Create a new stock pool. Returns the created pool dict."""
        obj = StockPool(
            name=data['name'],
            pool_type=data['pool_type'],
            description=data.get('description'),
            symbols=data.get('symbols', []),
            # 旧实现 json.dumps 后交给 psycopg2；ORM 下直接传 Python 对象
            filter_template=data.get('filter_template') or None,
            refresh_interval=data.get('refresh_interval'),
        )
        self.session.add(obj)
        self.session.commit()
        return self.get_by_id(obj.id)

    def update(self, pool_id: int, data: Dict) -> Optional[Dict]:
        """Update pool fields. Returns updated pool or None if not found."""
        fields = {k: v for k, v in data.items()
                  if k in _UPDATABLE_FIELDS and v is not None}
        if not fields:
            return self.get_by_id(pool_id)

        obj = self._get_model(pool_id)
        if not obj:
            return None
        for key, value in fields.items():
            setattr(obj, key, value)
        obj.updated_at = func.now()
        self.session.commit()
        return self.get_by_id(pool_id)

    def update_symbols(self, pool_id: int, symbols: List[str]) -> Optional[Dict]:
        """Update pool symbols and set last_refreshed_at. Used by dynamic pool refresh."""
        obj = self._get_model(pool_id)
        if not obj:
            return None
        obj.symbols = list(symbols)
        obj.last_refreshed_at = func.now()
        obj.updated_at = func.now()
        self.session.commit()
        return self.get_by_id(pool_id)

    def update_validation(self, pool_id: int, validation: Dict) -> Optional[Dict]:
        """Update last_validation JSON snapshot."""
        obj = self._get_model(pool_id)
        if not obj:
            return None
        obj.last_validation = validation
        obj.updated_at = func.now()
        self.session.commit()
        return self.get_by_id(pool_id)

    def delete(self, pool_id: int) -> bool:
        """Delete a pool. Returns True if deleted, False if not found."""
        obj = self._get_model(pool_id)
        if not obj:
            return False
        self.session.delete(obj)
        self.session.commit()
        return True

    def update_scan_enabled(self, pool_id: int, enabled: bool) -> bool:
        """开关池的信号扫描（pools_async / pool_scan_switch 路由调用）"""
        obj = self._get_model(pool_id)
        if not obj:
            return False
        obj.scan_enabled = bool(enabled)
        obj.updated_at = func.now()
        self.session.commit()
        return True

    def update_signal_scan(self, pool_id: int, scan_result: Dict) -> Optional[Dict]:
        """
        保存信号扫描结果到last_signal_scan字段

        Args:
            pool_id: 股票池ID
            scan_result: 扫描结果（包含buy_signals, sell_signals等）

        Returns:
            更新后的股票池，或None如果不存在
        """
        obj = self._get_model(pool_id)
        if not obj:
            return None
        obj.last_signal_scan = scan_result
        obj.updated_at = func.now()
        self.session.commit()
        return self.get_by_id(pool_id)


# 兼容别名：ORM 时期的调用名
StockPoolORMRepository = StockPoolRepository

__all__ = ['StockPoolRepository', 'StockPoolORMRepository', 'StockPool']
