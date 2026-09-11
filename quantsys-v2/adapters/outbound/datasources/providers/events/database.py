"""本地库兜底 provider（RFC 015 §1.5 硬约束 4：**最后一级**，stale-while-error）

读 `quant.event_calendar`（含 P3 新增 scope/symbols/source_url/evidence_hash 列）：
上游（东财/巨潮/akshare）全挂时链路不中断，但**必须显式标记 stale**——
调用方（应用层）据此把响应的 stale=True 透出，禁止把库里的旧事件当实时事件用
（2026-09-11 分钟线 DB 兜底只到 2026-05-29 的同类教训）。

本 provider 只读不写（写入走 adapters/outbound/repositories/event_repository.py）。

失败语义：读库失败 → 返回 None + last_error（fail-loud）；
库内确实没有该标的/该类型的事件 → 返回 []（空结果，不计健康分）。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from domain.events.model import AUTHORITY_DB
from domain.events.ports.IMarketEventProvider import IMarketEventProvider

logger = logging.getLogger(__name__)


class DatabaseEventProvider(IMarketEventProvider):
    """本地事件表兜底（权威度 20；stale 标记如实透出）"""

    #: 兜底源标记：manager 的聚合方法据此在 **ingest** 路径排除本 provider
    #: （ingest 读库再写库 = 自己喂自己；既有 67 行 evidence_hash 为空，
    #:  重算 hash 后会作为"新事件"插入，把宏观事件翻倍）
    is_fallback = True

    def __init__(self, repository=None):
        """Args: repository —— IMarketEventRepository（缺省走进程级单例）"""
        self._repository = repository
        self.last_error: Optional[str] = None
        self.stale = True          # 兜底源天然陈旧：本 provider 的所有输出都标 stale
        self.as_of: Optional[str] = None

    @property
    def name(self) -> str:
        return 'database_event'

    @property
    def repository(self):
        if self._repository is None:
            from adapters.outbound.repositories.event_repository import get_market_event_repo
            self._repository = get_market_event_repo()
        return self._repository

    # ------------------------------------------------------------------ 政策

    def fetch_policy(self) -> Optional[List[Dict]]:
        """库内已有的政策/行业事件（stale）"""
        self.last_error = None
        try:
            rows: List[Dict] = []
            rows.extend(self.repository.list(scope='macro', type='policy', limit=100))
            rows.extend(self.repository.list(scope='industry', type='policy', limit=100))
            self.as_of = datetime.now().isoformat(timespec='seconds')
            return [self._to_row(r) for r in rows]
        except Exception as exc:  # noqa: BLE001
            self.last_error = f'{type(exc).__name__}: {exc}'
            logger.warning('database_event fetch_policy failed: %s', self.last_error)
            return None

    # -------------------------------------------------------------- 个股事件

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """库内已有的个股事件（stale）"""
        self.last_error = None
        targets = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        try:
            rows: List[Dict] = []
            if targets:
                for symbol in targets[:50]:
                    rows.extend(self.repository.for_symbol(symbol, limit=50))
            else:
                today = date.today()
                rows.extend(self.repository.list(
                    date_from=(today - timedelta(days=30)).strftime('%Y-%m-%d'),
                    date_to=(today + timedelta(days=90)).strftime('%Y-%m-%d'),
                    limit=200))
            # 同一事件可能被两只标的查询各取一次 → 按 evidence_hash 去重
            seen = set()
            out: List[Dict] = []
            for row in rows:
                key = row.get('evidence_hash') or row.get('event_id')
                if key in seen:
                    continue
                seen.add(key)
                out.append(self._to_row(row))
            self.as_of = datetime.now().isoformat(timespec='seconds')
            return out
        except Exception as exc:  # noqa: BLE001
            self.last_error = f'{type(exc).__name__}: {exc}'
            logger.warning('database_event fetch_symbol_events failed: %s', self.last_error)
            return None

    # ------------------------------------------------------------------ 内部

    def _to_row(self, record: Dict) -> Dict:
        """库行 → provider 行契约（保留原 evidence_hash，保证幂等 upsert 命中同一行）"""
        return {
            'scope': record.get('scope') or 'macro',
            'type': record.get('type') or record.get('event_type'),
            'title': record.get('title') or '',
            'effective_date': str(record.get('effective_date') or '')[:10],
            'announce_date': str(record.get('announce_date') or '')[:10],
            'importance': record.get('importance'),
            'symbols': record.get('symbols') or ([record['symbol']] if record.get('symbol') else []),
            'industries': record.get('industries') or [],
            'source': self.name,
            'url': record.get('url') or record.get('source_url') or '',
            'summary': record.get('summary') or record.get('description') or '',
            'external_id': record.get('external_id') or record.get('evidence_hash') or '',
            'authority': AUTHORITY_DB,
            'evidence_hash': record.get('evidence_hash') or '',
            'stale': True,
            'raw': {'db_row_id': record.get('id'), 'db_source': record.get('source'),
                    'db_updated_at': record.get('updated_at')},
        }
