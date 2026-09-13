"""板块快照仓储（quant.sector_snapshot）。

2026-09-14（w-32314d00，REQ-24e15d B2）：读写原先都在
adapters/outbound/datasources/sector_snapshot.py 里以内联 text(f"...{_TABLE}...") 实现，
现收口到这里 —— 数据源层只做"抓取 + 组装"，持久化归仓储。
"""
from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime
from typing import Dict, List, Optional

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import SectorSnapshot

logger = logging.getLogger(__name__)

__all__ = ['SectorSnapshotRepository']


class SectorSnapshotRepository(BaseORMRepository[SectorSnapshot]):
    """板块快照读写。"""

    model = SectorSnapshot

    def upsert_snapshot(
        self,
        industries: List,
        concepts: List,
        total: int,
        source: str = 'eastmoney',
        snapshot_date: Optional[_date] = None,
    ) -> bool:
        """写入/覆盖某日快照（主键 snapshot_date，同日 UPSERT）。

        与原 SQL 的 ON CONFLICT (snapshot_date) DO UPDATE 等价。
        industries/concepts 以 **jsonb 原生列表**写入（原实现先 json.dumps 再交给
        psycopg2，等于让字符串进 jsonb 列——能work但多一层隐式转换）。
        """
        day = snapshot_date or _date.today()
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(SectorSnapshot).values(
                snapshot_date=day,
                industries=industries,
                concepts=concepts,
                total=int(total),
                source=source or 'eastmoney',
                updated_at=datetime.now(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['snapshot_date'],
                set_={
                    'industries': stmt.excluded.industries,
                    'concepts': stmt.excluded.concepts,
                    'total': stmt.excluded.total,
                    'source': stmt.excluded.source,
                    'updated_at': datetime.now(),
                },
            )
            self.session.execute(stmt)
            self.session.commit()
            return True
        except Exception as e:  # noqa: BLE001 —— 缓存写入失败不影响主链路
            self._safe_rollback()
            logger.warning(f"板块快照写入失败: {e}")
            return False

    def get_latest(self) -> Optional[Dict]:
        """最近一次快照；无数据返回 None。"""
        try:
            row = (
                self.session.query(SectorSnapshot)
                .order_by(SectorSnapshot.snapshot_date.desc(),
                          SectorSnapshot.updated_at.desc())
                .first()
            )
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            logger.warning(f"板块快照读取失败: {e}")
            return None
        if not row:
            return None
        return {
            'snapshot_date': str(row.snapshot_date),
            'industries': row.industries or [],
            'concepts': row.concepts or [],
            'total': row.total or (len(row.industries or []) + len(row.concepts or [])),
            'source': row.source,
        }

    def list_recent(self, limit: int = 5) -> List[Dict]:
        """最近 N 天快照（日期倒序，最新在前）。"""
        try:
            rows = (
                self.session.query(SectorSnapshot)
                .order_by(SectorSnapshot.snapshot_date.desc(),
                          SectorSnapshot.updated_at.desc())
                .limit(int(limit))
                .all()
            )
        except Exception as e:  # noqa: BLE001
            self._safe_rollback()
            logger.warning(f"板块快照历史读取失败: {e}")
            return []
        return [
            {
                'snapshot_date': str(r.snapshot_date),
                'industries': r.industries or [],
                'concepts': r.concepts or [],
            }
            for r in rows
        ]
