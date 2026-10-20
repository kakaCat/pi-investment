"""消息监控适配器（2026-10-20）：新闻来源 + 已报留痕

  · WatchNewsSource：qs_watch 端口 INewsSource 的实现——经 qs_market_data
    的 DataProviderManager.get_stock_news（新闻+公告统一通道，ADR-001 不直连 akshare）。
  · NewsAlertRepository：已报留痕（幂等键 symbol+title_hash，重复命中返回已存在行）。
"""
import hashlib
from typing import Any, Dict, List, Optional

import structlog

from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models import WatchNewsAlert

logger = structlog.get_logger(__name__)


class WatchNewsSource:
    """个股新闻+公告来源（盯盘消息监控用）。"""

    def fetch_news(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        from qs_market_data.adapters.outbound.datasources.manager import (
            get_data_provider_manager,
        )
        bare = str(symbol).split('.')[0]
        result = get_data_provider_manager().get_stock_news(bare, limit=limit)
        if not result.get('success'):
            raise RuntimeError('新闻获取失败：%s' % (result.get('error') or '未知'))
        # _try_providers 成功时 data 是**原始 MarketData 对象**（不剥壳，2026-10-20 实测）
        data = result.get('data')
        payload = getattr(data, 'data', None) if data is not None else None
        if payload is None and isinstance(data, dict):
            payload = data
        records = (payload or {}).get('records') or []
        out = []
        for r in records:
            if isinstance(r, dict) and r.get('title'):
                out.append({
                    'title': str(r.get('title')),
                    'time': str(r.get('time') or r.get('datetime') or ''),
                    'source': str(r.get('source') or ''),
                    'url': str(r.get('url') or ''),
                })
        return out


class NewsAlertRepository:
    """已报留痕：同一条新闻只报一次（幂等键 symbol+title_hash）。"""

    @staticmethod
    def _hash(title: str) -> str:
        return hashlib.sha256(title.strip().encode('utf-8')).hexdigest()[:32]

    def exists(self, symbol: str, title: str) -> bool:
        session = get_session()
        try:
            return session.query(WatchNewsAlert.id).filter(
                WatchNewsAlert.symbol == str(symbol).split('.')[0],
                WatchNewsAlert.title_hash == self._hash(title),
            ).first() is not None
        finally:
            pass

    def record(self, symbol: str, title: str, matched_words: List[str],
               tier: str) -> Optional[Dict[str, Any]]:
        bare = str(symbol).split('.')[0]
        session = get_session()
        try:
            row = session.query(WatchNewsAlert).filter(
                WatchNewsAlert.symbol == bare,
                WatchNewsAlert.title_hash == self._hash(title)).first()
            if row is not None:
                return None   # 已报过（幂等）
            row = WatchNewsAlert(symbol=bare, title_hash=self._hash(title),
                                 title=title[:290], matched_words=list(matched_words),
                                 tier=tier)
            session.add(row)
            session.commit()
            return {'id': row.id, 'symbol': bare, 'title': row.title,
                    'matched_words': matched_words, 'tier': tier}
        except Exception:
            session.rollback()
            raise

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = (get_session().query(WatchNewsAlert)
                .order_by(WatchNewsAlert.id.desc()).limit(int(limit)).all())
        return [{'id': r.id, 'symbol': r.symbol, 'title': r.title,
                 'matched_words': r.matched_words, 'tier': r.tier,
                 'created_at': r.created_at.isoformat() if r.created_at else None}
                for r in rows]
