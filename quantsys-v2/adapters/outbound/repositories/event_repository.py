"""市场事件仓储实现（ORM，表：quant.event_calendar）

RFC 015 §3.5（2026-09-11，REQ-cf627b，P3）：**扩展现有表**而非重建——
既有宏观事件（cpi_ppi/pmi/lpr/fomc/nbs/futures_delivery）保持不变，
2026-09-12 迁移新增 4 列承载政策与个股事件：scope / symbols(jsonb) / source_url / evidence_hash。

## 为什么以前用 SQLAlchemy Core（text()），以及为什么现在改成 ORM
（2026-09-14，w-32314d00，REQ-24e15d B4-c5）

原模块 docstring 记的理由是**导入顺序炸弹**：同一个 Base 上若声明**两个**映射同一张表的类，
谁先被导入谁定义 Table，后导入的那个会抛
"Table 'event_calendar' is already defined for this MetaData instance"。

该理由只对「**再声明一个同表映射类**」成立。本次收口改为**复用本仓已有的唯一映射类**
EventCalendar（定义在 adapters/outbound/repositories/event_calendar_repository.py）——
全仓只有一个类，炸弹前提消失，Core SQL 不再必要。

同时修掉一个真实缺陷：EventCalendar 原先只有 14 列，而线上表有 18 列，
**scope / symbols / source_url / evidence_hash 四列没进模型**。任何走该模型的全列读写
都会静默丢掉这 4 列（与 B4-c4 的 StrategyConfig 缺 3 列同一类陷阱）。已补齐并逐列核对。

## 幂等（RFC §5 验收项）
- 数据库层：uq_event_calendar_evidence_hash 局部唯一索引（WHERE evidence_hash IS NOT NULL，
  兼容既有 NULL 行）——重复 ingest 在**数据库层面**不可能产生重复行。
- 应用层：upsert 先按 hash 查再插/改，并如实返回 inserted/updated/skipped 计数。
  单行坏数据/单行异常如实计入 errors，不炸整批、不静默丢。

## 事件 status 口径（重要，防通知噪声）
机器 ingest 的事件一律写 status='collected'（已采集终态），**不写 pending**：
每日 16:45 的 event_calendar_check 任务会对 status ∈ (pending, notified) 且 importance >= 2
的近期事件发飞书提醒——若个股事件写成 pending，一次 ingest 就会把几十条解禁/财报提醒灌给用户。

## upsert 的受控更新（行为契约，勿改）
已存在（同 evidence_hash）时只更新**事件内容字段**，**不动 status**：status 可能已被
人工/任务推进到 notified/reviewed，覆盖它等于把提醒流水线打回去。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.exc import IntegrityError

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import DailyKline, Stock
from domain.events.ports.IMarketEventRepository import IMarketEventRepository
from adapters.outbound.repositories.event_calendar_repository import EventCalendar
from adapters.outbound.repositories.position_repository import Position
from adapters.outbound.repositories.watch_rule_repository import WatchRule

logger = logging.getLogger(__name__)

# 机器采集的事件状态（见模块 docstring：不进 pending 提醒流水线）
INGESTED_STATUS = 'collected'

#: 数字化的标的代码表达式（去除非数字字符）。原 Core SQL 用
#: regexp_replace(symbol, '[^0-9]', '', 'g')，这里用同一个函数，口径不变。
def _digits(column):
    return func.regexp_replace(column, '[^0-9]', '', 'g')


def _row_to_dict(row) -> Dict:
    """DB 行/ORM 对象 → 事件 dict（应用层/入站适配器消费的统一形态）

    属性访问对 Core Row 与 ORM 实例都成立（Row 有 _mapping/属性同名），
    故本函数在迁移前后逐字未改。
    """
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


class EventRepository(BaseORMRepository[EventCalendar], IMarketEventRepository):
    """quant.event_calendar 读写（宏观/政策/个股同一张表，按 scope 区分）"""

    model = EventCalendar

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
                self._safe_rollback()
        return {'inserted': inserted, 'updated': updated, 'skipped': skipped, 'errors': errors}

    def _upsert_one(self, params: Dict) -> str:
        """单条 upsert：存在则受控更新（不覆盖人工维护的 status），否则插入。

        并发撞唯一键（uq_event_calendar_evidence_hash）时降级为重试 UPDATE ——
        不吞异常、不重复插入，返回 'updated' 而不是 'inserted'（如实反映实际发生的事）。
        """
        session = self.session
        hash_value = params['evidence_hash']
        existing = (
            session.query(EventCalendar.id)
            .filter(EventCalendar.evidence_hash == hash_value)
            .first()
        )
        if existing:
            self._update_content(params)
            session.commit()
            return 'updated'
        try:
            row = EventCalendar(
                event_type=params['event_type'],
                event_date=params['event_date'],
                event_time=None,
                title=params['title'],
                description=params['description'],
                symbol=params['symbol'],
                market=params['market'],
                importance=params['importance'],
                status=params['status'],
                source=params['source'],
                meta=params['meta'],
                scope=params['scope'],
                symbols=params['symbols'],
                source_url=params['source_url'],
                evidence_hash=hash_value,
                created_at=func.now(),
                updated_at=func.now(),
            )
            session.add(row)
            session.commit()
            return 'inserted'
        except IntegrityError:
            # 并发下另一个写入者刚插了同一 hash：回滚后按"已存在"处理（受控更新）
            self._safe_rollback()
            self._update_content(params)
            session.commit()
            return 'updated'

    def _update_content(self, params: Dict) -> None:
        """只更新事件内容字段；**不碰 status**（见模块 docstring 的受控更新契约）。"""
        (self.session.query(EventCalendar)
         .filter(EventCalendar.evidence_hash == params['evidence_hash'])
         .update({
             EventCalendar.event_type: params['event_type'],
             EventCalendar.event_date: params['event_date'],
             EventCalendar.title: params['title'],
             EventCalendar.description: params['description'],
             EventCalendar.symbol: params['symbol'],
             EventCalendar.market: params['market'],
             EventCalendar.importance: params['importance'],
             EventCalendar.source: params['source'],
             EventCalendar.meta: params['meta'],
             EventCalendar.scope: params['scope'],
             EventCalendar.symbols: params['symbols'],
             EventCalendar.source_url: params['source_url'],
             EventCalendar.updated_at: func.now(),
         }, synchronize_session=False))

    def _to_params(self, event: Dict) -> Dict:
        """事件 dict → 列值（含类型/日期校验；非法即抛，由 upsert 如实计入 skipped）

        2026-09-14：meta / symbols 由"json.dumps 字符串"改为**直接给 Python 对象**
        （JSONB 列由 SQLAlchemy 序列化）。原实现靠 json.dumps(..., default=str) 兜底
        不可序列化对象，这里保留同一兜底（见 _jsonable）。
        """
        import json
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
            'meta': _jsonable(meta),
            'scope': str(event.get('scope') or 'macro')[:16],
            'symbols': _jsonable(symbols),
            'source_url': str(event.get('url') or '')[:1000],
            'evidence_hash': evidence_hash[:64],
        }

    # ------------------------------------------------------------------ 查询

    def _select(self, filters=None, order_by=None, limit: int = 200) -> List[Any]:
        """统一取数：过滤 + 排序 + 限量。返回 ORM 实例列表。"""
        q = self.session.query(EventCalendar)
        for f in (filters or []):
            q = q.filter(f)
        for o in (order_by or []):
            q = q.order_by(o)
        return q.limit(int(limit)).all()

    def list(self, scope: Optional[str] = None, type: Optional[str] = None,
             date_from: Optional[str] = None, date_to: Optional[str] = None,
             limit: int = 200) -> List[Dict]:
        filters = []
        if scope:
            filters.append(EventCalendar.scope == scope)
        if type:
            filters.append(EventCalendar.event_type == type)
        if date_from:
            filters.append(EventCalendar.event_date >= date_from)
        if date_to:
            filters.append(EventCalendar.event_date <= date_to)
        rows = self._select(filters, [EventCalendar.event_date.asc()], limit)
        return [_row_to_dict(r) for r in rows]

    #: 查询某标的时附带的全市场（macro）事件窗口（天）：只取"近期相关"的宏观事件，
    #: 不把 2026-01 的 CPI 也塞进个股排雷结果里
    MACRO_WINDOW_BACK_DAYS = 30
    MACRO_WINDOW_FWD_DAYS = 90

    def for_symbol(self, symbol: str, limit: int = 50) -> List[Dict]:
        """某标的的事件：**先**该标的自己的事件，**再**近期宏观事件（两段各自限量）

        为什么分两段查（2026-09-11 实测踩坑）：原来用一条
        (symbols @> needle OR scope='macro') ORDER BY event_date ASC LIMIT n 查询，
        宏观事件日期最早，会把 limit 全部占满——600150 明明有 15 条个股事件，
        for_symbol 却返回 0 条（应用层再按窗口过滤后为空）。多类别混排 + 全局 limit
        是经典的"一类数据挤掉另一类"陷阱，必须按类别分别限量。
        """
        code = str(symbol or '').strip()
        if not code:
            return []
        # symbols @> '["600176"]' —— JSONB 的 contains 语义，SQLAlchemy 的 JSONB 比较器
        # 会生成 @>。原实现写 CAST(:needle AS jsonb) 是为了绕开 text() 把 ::jsonb 误判成
        # 绑定参数；改用 ORM 表达式后该问题不复存在。
        symbol_rows = self._select(
            [EventCalendar.symbols.contains([code])],
            [EventCalendar.event_date.desc()],
            limit,
        )
        today = date.today()
        macro_rows = self._select(
            [
                EventCalendar.scope == 'macro',
                EventCalendar.event_date >= (today - timedelta(days=self.MACRO_WINDOW_BACK_DAYS)),
                EventCalendar.event_date <= (today + timedelta(days=self.MACRO_WINDOW_FWD_DAYS)),
            ],
            [EventCalendar.event_date.asc()],
            min(limit, 30),
        )
        return [_row_to_dict(r) for r in symbol_rows] + [_row_to_dict(r) for r in macro_rows]

    def upcoming(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """未来 N 天内即将发生的事件（含今天）"""
        today = date.today()
        end = today + timedelta(days=max(0, int(days or 0)))
        rows = self._select(
            [EventCalendar.event_date >= today, EventCalendar.event_date <= end],
            [EventCalendar.event_date.asc(), EventCalendar.importance.desc()],
            limit,
        )
        return [_row_to_dict(r) for r in rows]

    def exists_by_hash(self, evidence_hash: str) -> bool:
        value = str(evidence_hash or '').strip()
        if not value:
            return False
        return (self.session.query(EventCalendar.id)
                .filter(EventCalendar.evidence_hash == value)
                .first()) is not None

    def is_in_default_universe(self, symbol: str) -> bool:
        """该标的是否在默认采集池内（持仓 ∪ 启用中的盯盘规则）

        为什么需要（2026-09-11，w-f436d4ea）：个股事件通道**只采集 default_universe**，
        池外标的的 for_symbol 只能返回宏观事件。调用方（买入前排雷）必须能区分两种截然不同的结论：
          · 在池内且无个股事件 → 确实没有（可放心）
          · 不在池内           → **未知**（不是"没有"，是"没抓过"）
        混合成同一个空结果，就是拿"没查"冒充"没问题"。

        判据与 default_universe 同源，避免两处各写一套范围定义。
        """
        universe = self._universe_subquery()
        code = _digits(literal_column('u.symbol'))
        row = (self.session.query(literal_column('1'))
               .select_from(universe)
               .filter(code == _digits(str(symbol or '')), func.length(universe.c.symbol) == 6)
               .limit(1)
               .first())
        return row is not None

    @staticmethod
    def _universe_subquery():
        """持仓(quantity>0) ∪ 启用中盯盘规则 —— 代码数字化后的去重子查询。"""
        pos = (select(_digits(Position.symbol).label('symbol'))
               .where(Position.quantity > 0))
        rules = (select(_digits(WatchRule.symbol).label('symbol'))
                 .where(WatchRule.enabled.is_(True)))
        return pos.union(rules).subquery('u')

    def research_universe(self, limit: int = 800) -> List[str]:
        """研究宇宙：按流动性取标的（**与 default_universe 的「监控宇宙」是两回事**）。

        2026-09-13（w-a9ec14d7，RFC 015 §4）：此前只有 default_universe = 持仓 ∪ 盯盘规则，
        实测导致 individual 事件只覆盖 34 只——事件研究需要「同一事件日的横截面」，
        34 只根本不成立。两个概念必须分开命名，否则永远会被混用。
        """
        try:
            latest = (select(func.max(DailyKline.trade_date)).scalar_subquery())
            rows = (self.session.query(Stock.symbol)
                    .join(DailyKline, DailyKline.symbol == Stock.symbol)
                    .filter(DailyKline.trade_date == latest)
                    .filter(Stock.is_st.isnot(True), Stock.is_suspended.isnot(True))
                    .filter(DailyKline.amount.isnot(None))
                    .order_by(DailyKline.amount.desc())
                    .limit(int(limit))
                    .all())
            return [str(r[0]).zfill(6) for r in rows]
        except Exception as exc:  # noqa: BLE001
            self._safe_rollback()
            logger.error("research_universe failed: %s", exc)
            return []

    def default_universe(self, limit: int = 200) -> List[str]:
        """监控宇宙（默认采集池）：持仓 ∪ 盯盘规则（只取 quant.stocks 中真实存在的 6 位代码）。

        ⚠️ 2026-09-13：这只是「监控」宇宙，**不要**拿它做事件研究——实测它只有 34 只，
        研究要用 research_universe()（按流动性取 800 只）。两者混用正是事件覆盖过窄的根因。
        """
        universe = self._universe_subquery()
        rows = (self.session.query(universe.c.symbol)
                .select_from(universe)
                .join(Stock, Stock.symbol == universe.c.symbol)
                .filter(func.length(universe.c.symbol) == 6)
                .order_by(universe.c.symbol.asc())
                .limit(int(limit))
                .all())
        return [r[0] for r in rows]

    # ------------------------------------------------------------------ 统计

    def stats(self) -> Dict:
        """按 scope/type 的库存统计（体检探针用：事件新鲜度与覆盖面）"""
        by_scope = (self.session.query(EventCalendar.scope, func.count())
                    .group_by(EventCalendar.scope)
                    .order_by(EventCalendar.scope)
                    .all())
        by_type = (self.session.query(EventCalendar.event_type, func.count())
                   .group_by(EventCalendar.event_type)
                   .order_by(func.count().desc())
                   .limit(20)
                   .all())
        latest = self.session.query(func.max(EventCalendar.updated_at)).scalar()
        return {
            'by_scope': {r[0]: r[1] for r in by_scope},
            'by_type': {r[0]: r[1] for r in by_type},
            'latest_updated_at': latest.isoformat() if latest else None,
        }


def _jsonable(value):
    """把值过一遍 json 序列化（保留原实现 json.dumps(..., default=str) 的兜底）。

    原实现把 meta/symbols 以 json 字符串写库；改用 JSONB 列后必须给 Python 对象。
    但直接给对象会丢掉 default=str 这个兜底（datetime 等不可序列化对象原本会被
    转成字符串，现在会抛 TypeError）—— 故先 dumps 再 loads，语义完全一致。
    """
    import json
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


_repo: Optional[EventRepository] = None


def get_market_event_repo() -> EventRepository:
    """进程级单例（与既有仓储模式一致）"""
    global _repo
    if _repo is None:
        _repo = EventRepository()
    return _repo
