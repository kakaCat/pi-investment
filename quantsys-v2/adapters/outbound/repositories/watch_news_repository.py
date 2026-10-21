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
        # 2026-10-21（w-5d46d252）：真实方法名是 get_news（num 参数），不是 get_stock_news——
        # 旧调用每日刷 'DataProviderManager' object has no attribute 'get_stock_news' 71+ 次。
        result = get_data_provider_manager().get_news(bare, num=limit)
        if not result.get('success'):
            raise RuntimeError('新闻获取失败：%s' % (result.get('error') or '未知'))
        # _try_providers 成功时 data 是**原始 MarketData 对象**（不剥壳，2026-10-20 实测）
        data = result.get('data')
        payload = getattr(data, 'data', None) if data is not None else None
        if payload is None and isinstance(data, dict):
            payload = data
        # akshare stock_news_em 返回 list of dict（中文列名），而非 {'records': [...]}
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = payload.get('records') or []
        else:
            records = []
        out = []
        for r in records:
            if not isinstance(r, dict):
                continue
            title = r.get('title') or r.get('新闻标题')
            if not title:
                continue
            out.append({
                'title': str(title),
                'time': str(r.get('time') or r.get('datetime') or r.get('发布时间') or ''),
                'source': str(r.get('source') or r.get('文章来源') or ''),
                'url': str(r.get('url') or r.get('新闻链接') or ''),
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
