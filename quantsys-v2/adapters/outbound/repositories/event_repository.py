"""市场事件仓储实现（ORM/Core SQL，表：quant.event_calendar）

RFC 015 §3.5（2026-09-11，REQ-cf627b，P3）：**扩展现有表**而非重建——
既有 67 行宏观事件（cpi_ppi/pmi/lpr/fomc/nbs/futures_delivery）保持不变，
新增 4 列承载政策与个股事件：scope / symbols(jsonb) / source_url / evidence_hash。

## 为什么用 SQLAlchemy Core（text()）而不是新增 ORM 映射类
既有 ORM 类 `EventCalendar` 定义在 adapters/outbound/repositories/event_calendar_repository.py，
它**没有** extend_existing 标记。若本模块再声明一个同表映射类，两个类的导入顺序会决定谁先
定义 Table：一旦本模块先被导入，旧类再导入就会抛
"Table 'event_calendar' is already defined for this MetaData instance" —— 一个纯粹的
**导入顺序炸弹**（谁先 import 谁活）。Core SQL 完全绕开映射冲突，且 upsert 语义（按
evidence_hash 幂等）用原生 SQL 表达更直接、更可审计。

## 幂等（RFC §5 验收项）
- 数据库层：`uq_event_calendar_evidence_hash` 局部唯一索引（WHERE evidence_hash IS NOT NULL，
  兼容既有 67 行 NULL）——重复 ingest 在**数据库层面**不可能产生重复行。
- 应用层：upsert 先按 hash 查再插/改，并如实返回 inserted/updated/skipped 计数；
  并发撞唯一键时捕获 IntegrityError 降级为重试 UPDATE（不吞异常、不重复插入）。

## 事件 status 口径（重要，防通知噪声）
机器 ingest 的事件一律写 `status='collected'`（已采集终态），**不写 pending**：
既有的每日 16:45 `event_calendar_check` 任务会对 status ∈ (pending, notified) 且
importance ≥ 2 的近期事件发飞书提醒——若个股事件写成 pending，一次 ingest 就会把
几十条解禁/财报提醒灌给用户。事件→提醒的联动由应用层 link_to_watchlist 产出建议、
经人或 agent 复核后另行挂规则（RFC §3.2），不在本层偷偷触发。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from domain.events.ports.IMarketEventRepository import IMarketEventRepository

logger = logging.getLogger(__name__)

_COLUMNS = ('id, event_type, event_date, title, description, symbol, market, importance, '
            'status, source, meta, scope, symbols, source_url, evidence_hash, created_at, updated_at')

# 机器采集的事件状态（见模块 docstring：不进 pending 提醒流水线）
INGESTED_STATUS = 'collected'


def _row_to_dict(row) -> Dict:
    """DB 行 → 事件 dict（应用层/入站适配器消费的统一形态）"""
    meta = row.meta if isinstance(row.meta, dict) else {}
    symbols = row.symbols if isinstance(row.symbols, list) else []
    if not symbols and row.symbol:
        symbols = [row.symbol]
    return {
        'id': row.id,
        'event_id': (row.evidence_hash or '')[:16],
        'evidence_hash': row.evidence_hash or '',
        'scope': row.scope or 'macro',
        'type': row.event_type,
        'event_type': row.event_type,
        'title': row.title,
        'summary': row.description,
        'description': row.description,
        'effective_date': row.event_date.isoformat() if row.event_date else None,
        'event_date': row.event_date.isoformat() if row.event_date else None,
        'announce_date': meta.get('announce_date'),
        'importance': row.importance,
        'symbols': symbols,
        'symbol': row.symbol,
        'industries': meta.get('industries') or [],
        'source': row.source,
        'url': row.source_url or meta.get('url') or '',
        'authority': meta.get('authority'),
        'external_id': meta.get('external_id'),
        'status': row.status,
        'market': row.market,
        'meta': meta,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


class EventRepository(IMarketEventRepository):
    """quant.event_calendar 读写（宏观/政策/个股同一张表，按 scope 区分）"""

    def __init__(self, engine=None):
        """Args: engine —— SQLAlchemy Engine（缺省走进程级单例，便于测试注入）"""
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            from infrastructure.persistence.database.engine import get_engine
            self._engine = get_engine()
        return self._engine

    # ------------------------------------------------------------------ 写入

    def upsert(self, events: List[Dict]) -> Dict:
        """批量幂等写入（按 evidence_hash 去重；见模块 docstring 的幂等说明）"""
        inserted = updated = skipped = 0
        errors: List[str] = []
        for event in events or []:
            try:
                params = self._to_params(event)
            except Exception as exc:  # noqa: BLE001 —— 单行坏数据不炸整批
                skipped += 1
                errors.append(f"invalid event {str(event.get('title'))[:40]!r}: {exc}")
                continue
            if not params['evidence_hash']:
                skipped += 1
                errors.append(f"missing evidence_hash: {str(event.get('title'))[:40]!r}")
                continue
            try:
                action = self._upsert_one(params)
                if action == 'inserted':
                    inserted += 1
                else:
                    updated += 1
            except Exception as exc:  # noqa: BLE001
                skipped += 1
                errors.append(f"upsert failed {params['title'][:40]!r}: {type(exc).__name__}: {exc}")
                logger.warning('event upsert failed: %s', exc)
        return {'inserted': inserted, 'updated': updated, 'skipped': skipped, 'errors': errors}

    def _upsert_one(self, params: Dict) -> str:
        """单条 upsert：存在则受控更新（不覆盖人工维护的 status），否则插入"""
        with self.engine.begin() as conn:
            existing = conn.execute(
                text('SELECT id, status FROM quant.event_calendar WHERE evidence_hash = :h'),
                {'h': params['evidence_hash']},
            ).fetchone()
            if existing:
                # 只更新事件内容字段；status 若已被人工/任务推进（notified/reviewed）则保持不动
                conn.execute(text("""
                    UPDATE quant.event_calendar SET
                        event_type = :event_type, event_date = :event_date, title = :title,
                        description = :description, symbol = :symbol, market = :market,
                        importance = :importance, source = :source, meta = :meta,
                        scope = :scope, symbols = :symbols, source_url = :source_url,
                        updated_at = now()
                    WHERE evidence_hash = :evidence_hash
                """), params)
                return 'updated'
            row = conn.execute(text("""
                INSERT INTO quant.event_calendar
                    (event_type, event_date, event_time, title, description, symbol, market,
                     importance, status, source, meta, scope, symbols, source_url, evidence_hash,
                     created_at, updated_at)
                VALUES
                    (:event_type, :event_date, NULL, :title, :description, :symbol, :market,
                     :importance, :status, :source, :meta, :scope, :symbols, :source_url,
                     :evidence_hash, now(), now())
                RETURNING id
            """), params)
            return 'inserted' if row.fetchone() else 'inserted'

    def _to_params(self, event: Dict) -> Dict:
        """事件 dict → SQL 参数（含类型/日期校验；非法即抛，由 upsert 如实计入 skipped）"""
        evidence_hash = str(event.get('evidence_hash') or '').strip()
        effective = str(event.get('effective_date') or '').strip()[:10]
        title = str(event.get('title') or '').strip()
        if not title:
            raise ValueError('title 为空')
        event_date = datetime.strptime(effective, '%Y-%m-%d').date() if effective else None
        if event_date is None:
            raise ValueError('effective_date 缺失或非法')
        symbols = [str(s).strip() for s in (event.get('symbols') or []) if str(s).strip()]
        meta = dict(event.get('meta') or {})
        meta.update({
            'announce_date': str(event.get('announce_date') or '')[:10] or None,
            'industries': list(event.get('industries') or []),
            'url': str(event.get('url') or ''),
            'authority': event.get('authority'),
            'external_id': str(event.get('external_id') or ''),
            'raw': event.get('raw') or {},
        })
        if event.get('source_divergence'):
            meta['source_divergence'] = event['source_divergence']
        importance = event.get('importance')
        try:
            importance = int(importance) if importance is not None else 1
        except (TypeError, ValueError):
            importance = 1
        if importance not in (1, 2, 3):
            raise ValueError(f'importance 越界: {importance}（契约 1-3）')
        import json
        return {
            'event_type': str(event.get('type') or event.get('event_type') or 'other')[:32],
            'event_date': event_date,
            'title': title[:200],
            'description': str(event.get('summary') or event.get('description') or ''),
            # 兼容既有单值列：仅当恰好一只标的是才写，多标的靠 symbols 数组表达
            'symbol': symbols[0] if len(symbols) == 1 else None,
            'market': str(event.get('market') or 'CN')[:8],
            'importance': importance,
            'status': str(event.get('status') or INGESTED_STATUS)[:16],
            'source': str(event.get('source') or '')[:50],
            'meta': json.dumps(meta, ensure_ascii=False, default=str),
            'scope': str(event.get('scope') or 'macro')[:16],
            'symbols': json.dumps(symbols, ensure_ascii=False),
            'source_url': str(event.get('url') or '')[:1000],
            'evidence_hash': evidence_hash[:64],
        }

    # ------------------------------------------------------------------ 查询

    def _query(self, where: str, params: Dict, limit: int, order: str = 'event_date ASC') -> List[Dict]:
        sql = f'SELECT {_COLUMNS} FROM quant.event_calendar'
        if where:
            sql += f' WHERE {where}'
        sql += f' ORDER BY {order} LIMIT :limit'
        params = dict(params)
        params['limit'] = int(limit)
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def list(self, scope: Optional[str] = None, type: Optional[str] = None,
             date_from: Optional[str] = None, date_to: Optional[str] = None,
             limit: int = 200) -> List[Dict]:
        clauses, params = [], {}
        if scope:
            clauses.append('scope = :scope')
            params['scope'] = scope
        if type:
            clauses.append('event_type = :type')
            params['type'] = type
        if date_from:
            clauses.append('event_date >= :date_from')
            params['date_from'] = date_from
        if date_to:
            clauses.append('event_date <= :date_to')
            params['date_to'] = date_to
        where = ' AND '.join(clauses)
        return self._query(where, params, limit)

    #: 查询某标的时附带的全市场（macro）事件窗口（天）：只取"近期相关"的宏观事件，
    #: 不把 2026-01 的 CPI 也塞进个股排雷结果里
    MACRO_WINDOW_BACK_DAYS = 30
    MACRO_WINDOW_FWD_DAYS = 90

    def for_symbol(self, symbol: str, limit: int = 50) -> List[Dict]:
        """某标的的事件：**先**该标的自己的事件，**再**近期宏观事件（两段各自限量）

        为什么分两段查（2026-09-11 实测踩坑）：原来用一条
        `(symbols @> needle OR scope='macro') ORDER BY event_date ASC LIMIT n` 查询，
        宏观事件日期最早，会把 limit 全部占满——600150 明明有 15 条个股事件，
        for_symbol 却返回 0 条（应用层再按窗口过滤后为空）。多类别混排 + 全局 limit
        是经典的"一类数据挤掉另一类"陷阱，必须按类别分别限量。
        """
        code = str(symbol or '').strip()
        if not code:
            return []
        # 注意：写成 CAST(:needle AS jsonb) 而不是 :needle::jsonb —— SQLAlchemy 的 text() 会把
        # ':needle::jsonb' 里的双冒号误判成绑定参数的一部分（实测报 syntax error at or near ":"）。
        symbol_rows = self._query(
            'symbols @> CAST(:needle AS jsonb)',
            {'needle': f'["{code}"]'},
            limit,
            order='event_date DESC',
        )
        today = date.today()
        macro_rows = self._query(
            "scope = 'macro' AND event_date >= :start AND event_date <= :end",
            {
                'start': (today - timedelta(days=self.MACRO_WINDOW_BACK_DAYS)).isoformat(),
                'end': (today + timedelta(days=self.MACRO_WINDOW_FWD_DAYS)).isoformat(),
            },
            min(limit, 30),
            order='event_date ASC',
        )
        return symbol_rows + macro_rows

    def upcoming(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """未来 N 天内即将发生的事件（含今天）"""
        today = date.today()
        end = today + timedelta(days=max(0, int(days or 0)))
        return self._query(
            'event_date >= :start AND event_date <= :end',
            {'start': today.isoformat(), 'end': end.isoformat()},
            limit,
            order='event_date ASC, importance DESC',
        )

    def exists_by_hash(self, evidence_hash: str) -> bool:
        value = str(evidence_hash or '').strip()
        if not value:
            return False
        with self.engine.connect() as conn:
            row = conn.execute(
                text('SELECT 1 FROM quant.event_calendar WHERE evidence_hash = :h LIMIT 1'),
                {'h': value},
            ).fetchone()
        return row is not None

    def default_universe(self, limit: int = 200) -> List[str]:
        """默认采集池：持仓 ∪ 盯盘规则（只取 quant.stocks 中真实存在的 6 位代码）"""
        sql = """
            SELECT DISTINCT u.symbol
              FROM (
                    SELECT regexp_replace(symbol, '[^0-9]', '', 'g') AS symbol
                      FROM quant.positions WHERE quantity > 0
                    UNION
                    SELECT regexp_replace(symbol, '[^0-9]', '', 'g') AS symbol
                      FROM quant.watch_rules WHERE enabled = true
                   ) u
              JOIN quant.stocks s ON s.symbol = u.symbol
             WHERE length(u.symbol) = 6
             ORDER BY u.symbol
             LIMIT :limit
        """
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), {'limit': int(limit)}).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ 统计

    def stats(self) -> Dict:
        """按 scope/type 的库存统计（体检探针用：事件新鲜度与覆盖面）"""
        with self.engine.connect() as conn:
            by_scope = conn.execute(text(
                'SELECT scope, count(*) FROM quant.event_calendar GROUP BY scope ORDER BY scope'
            )).fetchall()
            by_type = conn.execute(text(
                'SELECT event_type, count(*) FROM quant.event_calendar GROUP BY event_type '
                'ORDER BY count(*) DESC LIMIT 20'
            )).fetchall()
            latest = conn.execute(text('SELECT max(updated_at) FROM quant.event_calendar')).scalar()
        return {
            'by_scope': {r[0]: r[1] for r in by_scope},
            'by_type': {r[0]: r[1] for r in by_type},
            'latest_updated_at': latest.isoformat() if latest else None,
        }


_repo: Optional[EventRepository] = None


def get_market_event_repo() -> EventRepository:
    """进程级单例（与既有仓储模式一致）"""
    global _repo
    if _repo is None:
        _repo = EventRepository()
    return _repo
