"""事件日历 / 政策·个股事件源 API - FastAPI 版

特殊日子（宏观发布/央行议息/财报/交割）的日历查询与维护，
以及 P3 新增的**政策·个股事件源**（RFC 015 §3.4，2026-09-11 REQ-cf627b）读写入口。

数据流：
  宏观（既有，未改动）：初始化脚本/手动 → quant.event_calendar →
      本 API（/api/events、/api/events/upcoming…）→ 每日检查任务/Agent 工具
  政策/个股（P3 新增）：provider 多源（东财公告流 / 巨潮法定披露 / akshare 解禁 /
      gov.cn+发改委 / 证监会 + DB 兜底）→ domain.events 归并去重 →
      quant.event_calendar（同表，scope 区分）→ /api/events/feed、/api/events/symbol/{symbol}

组合根说明：具体实现的装配放在**本文件**（入站适配器），应用层因此可以完全不出现
adapters 导入（ADR-001 依赖倒置红线；与 industry_chain_async.py 同模式）。

既有端点全部保留原语义与响应形状（6 个），P3 只**新增** 4 个（feed / symbol /
ingest / watch-suggestions）。注意：新增的字面量路径必须声明在 /api/events/{event_id}
之前，否则 FastAPI 会先匹配到 {event_id} 并把 'feed' 当 int 解析而报 422。

设计文档：docs/work-logs/2026-09/event-calendar-system-design.md；RFC 015 §3
"""
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import error_response
from adapters.outbound.repositories.event_calendar_repository import (
    get_event_calendar_repo, event_to_dict,
)
from application.services.event_feed_service import (
    EventFeedService, get_event_feed_service, set_event_feed_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Events - 事件日历"])

VALID_STATUSES = {'pending', 'notified', 'collected', 'reviewed', 'skipped'}


def get_feed_service() -> EventFeedService:
    """组合根：装配 IDataProviderManager + IMarketEventRepository（进程级复用）

    ⚠️ 命名纪律（两次踩坑，务必保留）：本工厂**不能**叫 get_event_feed（= 下面 /api/events/feed
    的端点函数名），也**不能**叫 get_event_feed_service（= 从 application.services 导入的
    单例 getter 同名）。两次同名都导致端点/工厂内部递归调用自己，实测分别报
    "TypeError: 'Query' object is not callable" 与 "RecursionError"。工厂名必须与二者都不同。
    """
    svc = get_event_feed_service()
    if svc is None:
        from adapters.outbound.datasources.manager import get_data_provider_manager
        from adapters.outbound.repositories.event_repository import get_market_event_repo
        svc = EventFeedService(
            manager=get_data_provider_manager(),
            repository=get_market_event_repo(),
        )
        set_event_feed_service(svc)
    return svc


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


@router.get('/api/events/upcoming')
def get_upcoming_events(days: int = Query(default=2, ge=0, le=30)):
    """查未来 N 天待处理事件（含今天）。每日检查任务核心调用。"""
    try:
        repo = get_event_calendar_repo()
        events = repo.list_upcoming(days_ahead=days)
        return {
            'success': True,
            'days': days,
            'count': len(events),
            'events': [event_to_dict(e) for e in events],
        }
    except Exception as e:
        logger.error("get_upcoming_events failed", error=str(e))
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/events')
def list_events(
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """范围查询事件日历：按日期区间/类型/状态/标的过滤。默认查近30天。"""
    try:
        repo = get_event_calendar_repo()
        start_d = _parse_date(start)
        end_d = _parse_date(end)
        # 默认窗口：近 30 天（不含参数时）
        if start_d is None and end_d is None:
            today = date.today()
            start_d = date.fromordinal(today.toordinal() - 7)
            end_d = date.fromordinal(today.toordinal() + 30)
        events = repo.list_range(
            start=start_d, end=end_d,
            event_type=event_type, status=status, symbol=symbol, limit=limit,
        )
        return {
            'success': True,
            'count': len(events),
            'events': [event_to_dict(e) for e in events],
        }
    except Exception as e:
        logger.error("list_events failed", error=str(e))
        return error_response({'success': False, 'error': str(e)}, 500)


# ── P3 新增：政策·个股事件源（RFC 015 §3.4）──────────────────────────────
# ⚠️ 顺序纪律：本段全部声明在 /api/events/{event_id} **之前**——
# FastAPI 按声明顺序匹配，若 {event_id} 在前，'/api/events/feed' 会被当成
# event_id='feed' 去解析 int 而返回 422（静默把新端点废掉）。

@router.get('/api/events/feed')
def get_event_feed(
    scope: Optional[str] = Query(default=None, description='macro/industry/individual'),
    type: Optional[str] = Query(default=None, description='policy/earnings/unlock/placement/...（宏观类型如 pmi 亦可）'),
    date_from: Optional[str] = Query(default=None, description='YYYY-MM-DD'),
    date_to: Optional[str] = Query(default=None, description='YYYY-MM-DD'),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """事件流查询（宏观 + 政策 + 个股），响应遵循 RFC §1.5.3 统一契约。

    与既有 /api/events 的分工：后者是**宏观日历**视图（status 状态机 + 手维护），
    本端点是**事件源**视图（scope/type/日期区间，含 P3 采集的政策与个股事件）。
    """
    try:
        result = get_feed_service().list_events(
            scope=scope, type=type, date_from=date_from, date_to=date_to, limit=limit)
        return result
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error('get_event_feed failed', error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.get('/api/events/symbol/{symbol}')
def get_events_for_symbol(
    symbol: str,
    limit: int = Query(default=50, ge=1, le=500),
    window_days: Optional[int] = Query(default=None, ge=1, le=365,
                                       description='只保留 今天±N 天内的事件（排雷用）'),
    days: Optional[int] = Query(default=None, ge=1, le=365,
                                description='window_days 的别名（agent-dh 客户端 getSymbolEvents 传的是 days）'),
):
    """个股事件（含影响该标的的宏观事件）；买入前排雷入口（RFC §3.6）

    ⚠️ 同时接受 window_days 与 days：并行窗口的 quantsys-v2-client.getSymbolEvents(symbol,{days})
    传的是 days，而本端点参数名是 window_days——不接别名的话 FastAPI 会**静默忽略** days
    （未知查询参数不报错），工具层以为过滤生效而实际返回全量，属于最难查的一类假成功。
    """
    try:
        span = window_days if window_days is not None else days
        return get_feed_service().events_for_symbol(symbol, limit=limit, window_days=span)
    except Exception as e:
        logger.error('get_events_for_symbol failed', symbol=symbol, error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.post('/api/events/ingest')
def ingest_events(payload: Optional[Dict[str, Any]] = Body(None)):
    """手动触发采集（幂等：同一批重复 ingest 不产生重复行，evidence_hash 唯一索引兜底）

    Body（可选）：
      {"scope": "policy"}                  → 只采政策（gov/发改委 + 证监会 + 人工兜底）
      {"scope": "symbol", "symbols": [...]} → 只采个股（缺 symbols 用默认池：持仓∪盯盘）
      {"scope": "all"}                      → 两者都采（默认）
    """
    params = payload or {}
    scope = str(params.get('scope') or 'all').lower()
    if scope not in ('policy', 'symbol', 'all'):
        return error_response({'success': False,
                               'error': f"非法 scope={scope!r}（支持 policy/symbol/all）"}, 400)
    try:
        service = get_feed_service()
        out: Dict[str, Any] = {'success': True, 'scope': scope}
        if scope in ('policy', 'all'):
            out['policy'] = service.ingest_policy()
        if scope in ('symbol', 'all'):
            symbols = params.get('symbols')
            if isinstance(symbols, str):
                symbols = [s for s in symbols.replace(',', ' ').split() if s]
            out['symbol'] = service.ingest_symbol_events(
                symbols=symbols or None,
                universe_limit=int(params.get('universe_limit') or 200),
            )
        out['success'] = all(v.get('success') for k, v in out.items()
                             if k in ('policy', 'symbol') and isinstance(v, dict))
        return out
    except Exception as e:
        logger.error('ingest_events failed', error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.get('/api/events/watch-suggestions')
def get_watch_suggestions(
    symbols: Optional[str] = Query(default=None, description='逗号分隔的标的；不传则看未来 days 天的全部事件'),
    days: int = Query(default=30, ge=1, le=180),
):
    """事件 → 盯盘规则**建议**（只产建议不建规则，RFC §3.2/§3.6）"""
    try:
        targets = [s for s in (symbols or '').replace(',', ' ').split() if s] or None
        return get_feed_service().link_to_watchlist(symbols=targets, days=days)
    except Exception as e:
        logger.error('get_watch_suggestions failed', error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.get('/api/events/{event_id}')
def get_event(event_id: int):
    """按 ID 查单个事件。"""
    try:
        repo = get_event_calendar_repo()
        obj = repo.get_by_id(event_id)
        if not obj:
            return error_response({'success': False, 'error': f'事件不存在 id={event_id}'}, 404)
        return {'success': True, 'event': event_to_dict(obj)}
    except Exception as e:
        logger.error("get_event failed", error=str(e), event_id=event_id)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/events')
def create_event(payload: Dict[str, Any] = Body(default_factory=dict)):
    """创建事件（手动/初始化脚本）。"""
    event_type = (payload.get('event_type') or '').strip()
    event_date_s = payload.get('event_date')
    title = (payload.get('title') or '').strip()
    if not event_type or not event_date_s or not title:
        return error_response({'success': False, 'error': 'event_type/event_date/title 必填'}, 400)
    event_date = _parse_date(event_date_s)
    if not event_date:
        return error_response({'success': False, 'error': 'event_date 格式应为 YYYY-MM-DD'}, 400)
    try:
        repo = get_event_calendar_repo()
        obj = repo.upsert(
            event_type=event_type,
            event_date=event_date,
            title=title,
            event_time=payload.get('event_time'),
            description=payload.get('description'),
            symbol=payload.get('symbol'),
            market=payload.get('market', 'CN'),
            importance=payload.get('importance', 1),
            status=payload.get('status', 'pending'),
            source=payload.get('source', 'manual'),
            meta=payload.get('meta'),
        )
        if not obj:
            return error_response({'success': False, 'error': '创建失败'}, 500)
        return {'success': True, 'event': event_to_dict(obj)}
    except Exception as e:
        logger.error("create_event failed", error=str(e), title=title)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.patch('/api/events/{event_id}')
def update_event(event_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    """更新事件状态/结果/影响评估。status 变更走状态机。"""
    try:
        repo = get_event_calendar_repo()
        obj = repo.get_by_id(event_id)
        if not obj:
            return error_response({'success': False, 'error': f'事件不存在 id={event_id}'}, 404)

        status = payload.get('status')
        meta_patch = payload.get('meta') if isinstance(payload.get('meta'), dict) else None
        if status is not None:
            if status not in VALID_STATUSES:
                return error_response({'success': False, 'error': f'非法 status：{status}'}, 400)
            obj = repo.mark_status(event_id, status, meta_patch)
        elif meta_patch:
            obj = repo.mark_status(event_id, obj.status, meta_patch)
        else:
            # 其他字段直接更新
            for k in ('title', 'description', 'symbol', 'market', 'importance', 'source', 'event_time'):
                if k in payload and payload[k] is not None and hasattr(obj, k):
                    v = payload[k]
                    if k == 'event_time':
                        from adapters.outbound.repositories.event_calendar_repository import _parse_time
                        v = _parse_time(v)
                    setattr(obj, k, v)
            if 'event_date' in payload and payload['event_date']:
                d = _parse_date(payload['event_date'])
                if d:
                    obj.event_date = d
            obj.updated_at = datetime.now()
            obj = repo.update(obj)

        return {'success': True, 'event': event_to_dict(obj)}
    except Exception as e:
        logger.error("update_event failed", error=str(e), event_id=event_id)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.delete('/api/events/{event_id}')
def delete_event(event_id: int):
    """删除事件。"""
    try:
        repo = get_event_calendar_repo()
        ok = repo.delete_by_id(event_id)
        if not ok:
            return error_response({'success': False, 'error': f'事件不存在 id={event_id}'}, 404)
        return {'success': True, 'deleted': event_id}
    except Exception as e:
        logger.error("delete_event failed", error=str(e), event_id=event_id)
        return error_response({'success': False, 'error': str(e)}, 500)
