"""政策·个股事件源应用服务（RFC 015 §3.2，2026-09-11 REQ-cf627b P3）

应用层只做**编排**：
- 多源取数与故障转移/聚合 → 注入的 IDataProviderManager（出站适配器侧，
  get_event_policy_events / get_event_symbol_events，内部复用 _try_providers 的
  独立超时 + 熔断 + 动态降权 + attempted_sources）
- 归并去重/影响判定/重要度推断/多源合并裁决 → domain.events.service（纯计算零 I/O）
- 落库与查询 → 注入的 IMarketEventRepository

依赖方向（ADR-001 红线）：本文件**不得出现任何 adapters 导入**（含函数内局部导入）。
具体实现的装配（组合根）在入站适配器 adapters/inbound/fastapi_app/routes/events_async.py；
定时任务用 build_event_ingest_jobs() 由 main.py 注入服务实例。

响应契约（RFC §1.5.3 统一）：{success, data, source, attempted_sources, degraded, stale,
cross_source_conflict, as_of}；全源失败 → success=False（**显式失败**，绝不返回空清单冒充成功）。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from domain.events.model import EventScope, EventType, MarketEvent
from domain.events.service import MarketEventService

logger = logging.getLogger(__name__)

_service_instance: Optional['EventFeedService'] = None


class EventFeedService:
    """事件源用例编排：ingest / list / for_symbol / upcoming / link_to_watchlist"""

    def __init__(self, manager=None, repository=None, domain: Optional[MarketEventService] = None):
        """
        Args:
            manager: IDataProviderManager（事件 provider 子链路）——组合根注入
            repository: IMarketEventRepository（落库与查询）——组合根注入
            domain: 领域规则服务（纯计算，缺省新建）
        """
        self._manager = manager
        self._repository = repository
        self._domain = domain or MarketEventService()

    # ------------------------------------------------------------------ 依赖

    def _require_manager(self):
        if self._manager is None:
            raise RuntimeError(
                'EventFeedService 需要注入 IDataProviderManager（组合根见 '
                'adapters/inbound/fastapi_app/routes/events_async.py）'
            )
        return self._manager

    def _require_repository(self):
        if self._repository is None:
            raise RuntimeError(
                'EventFeedService 需要注入 IMarketEventRepository（组合根见 '
                'adapters/inbound/fastapi_app/routes/events_async.py）'
            )
        return self._repository

    @staticmethod
    def _truncation_notes(manager) -> List[str]:
        """收集各 provider 自报的截断说明（静默失败清单 §2：截断必须出现在响应里）

        为什么在这里读：provider 按标的数有单次上限（东财 30 / 巨潮 20 / DB 50），
        超限时**只采集前 N 只**；manager 的聚合返回值只带 data/source/attempted_sources，
        没有透出 provider 级说明的通道。若不在应用层透出，调用方拿到的是"覆盖完整的假象"。
        组合根换实现时（manager 支持 provider_notes 合并）本方法可删除。
        """
        notes: List[str] = []
        for provider in (getattr(manager, 'event_symbol_providers', None) or []):
            note = str(getattr(provider, 'truncation_note', '') or '').strip()
            if note:
                notes.append(note)
        return notes

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _envelope(data: Any, *, source: Optional[str] = None, attempted: Optional[List[str]] = None,
                  degraded: bool = False, stale: bool = False, error: Optional[str] = None,
                  conflicts: Optional[List[Dict]] = None, **extra) -> Dict:
        payload = {
            'success': error is None,
            'data': data,
            'source': source,
            'attempted_sources': attempted or [],
            'degraded': bool(degraded),
            'stale': bool(stale),
            'cross_source_conflict': conflicts or None,
            'as_of': datetime.now().isoformat(timespec='seconds'),
        }
        if error:
            payload['error'] = error
        payload.update(extra)
        return payload

    # ------------------------------------------------------------------ ingest

    def ingest_policy(self) -> Dict:
        """采集政策事件并幂等落库

        语义护栏（RFC §3.3 硬要求）：自动通道（gov/发改委 + 证监会）全失败或全空时，
        manager 会落到人工策展 seed；响应里用 `manual_fallback_used` 显式标注，
        使"抓到真政策"与"人工补位"可区分——绝不允许两条通道都挂了却返回"没有政策"。
        """
        manager = self._require_manager()
        repository = self._require_repository()
        fetched = manager.get_event_policy_events()
        if not fetched.get('success'):
            return self._envelope(
                None, attempted=fetched.get('attempted_sources'),
                degraded=True, error=fetched.get('error') or 'policy providers failed',
                provider_errors=fetched.get('provider_errors') or {},
            )
        prepared = self._domain.prepare(fetched.get('data') or [])
        events: List[MarketEvent] = prepared['events']
        written = repository.upsert([self._to_record(e) for e in events])
        provider_notes = self._truncation_notes(manager)
        return self._envelope(
            [e.to_dict() for e in events],
            source=fetched.get('source'),
            attempted=fetched.get('attempted_sources'),
            degraded=bool(fetched.get('degraded')) or bool(provider_notes),
            conflicts=[d.to_dict() for d in prepared['divergences']],
            manual_fallback_used=bool(fetched.get('manual_fallback_used')),
            truncated=bool(provider_notes),
            provider_notes=provider_notes,
            counts={
                'fetched': len(fetched.get('data') or []),
                'parsed': prepared['parsed'],
                'deduped': prepared['deduped'],
                'merged': len(events),
                'rejected': len(prepared['rejected']),
                **written,
            },
            rejected_rows=prepared['rejected'][:20],
            provider_errors=fetched.get('provider_errors') or {},
        )

    def ingest_symbol_events(self, symbols: Optional[List[str]] = None,
                             universe_limit: int = 200) -> Dict:
        """采集个股事件（公告/财报/解禁/定增…）并幂等落库

        Args:
            symbols: 目标标的；None 时取仓储的 default_universe（持仓 ∪ 盯盘规则）
            universe_limit: 默认采集池上限

        Returns:
            统一响应契约；`universe` 字段如实回报本次使用的标的范围
            （空池时只做政策 ingest 不伪造标的，见 default_universe 契约）
            全部通道**健康但无数据** → success=True + data=[] + empty=True + note 说明
            （2026-09-11『空结果≠故障』契约对齐）：这是**成功且 0 条**，不是失败——
            "当天确实没有公告"与"抓取挂了"必须可区分，否则无人值守的每日 17:00
            ingest 在无公告日误报红。只有存在**硬失败**（源异常/超时/熔断）时才 success=False。
        """
        manager = self._require_manager()
        repository = self._require_repository()
        targets = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        universe_source = 'explicit'
        notes: List[str] = []
        if not targets:
            targets = repository.default_universe(limit=universe_limit)
            universe_source = 'default_universe(持仓∪盯盘规则)'
            if len(targets) >= int(universe_limit):
                # 池子命中上限 = 可能被截断（仓储用 LIMIT，无法区分"正好这么多"与"被截"）
                notes.append(
                    'default_universe 命中上限 %d 只，采集范围可能被截断（提高 universe_limit 可扩展）'
                    % int(universe_limit)
                )
        if not targets:
            # 不伪造标的：如实返回"无可采集标的"，由调用方决定是否视为异常
            return self._envelope(
                [], source=None, attempted=[], degraded=False,
                universe=[], universe_source=universe_source,
                counts={'fetched': 0, 'parsed': 0, 'deduped': 0, 'merged': 0,
                        'rejected': 0, 'inserted': 0, 'updated': 0, 'skipped': 0},
                note='默认采集池为空（无持仓且无启用盯盘规则）：未采集个股事件，不伪造标的',
            )

        fetched = manager.get_event_symbol_events(targets, include_fallback=False)
        if not fetched.get('success'):
            # 走到这里 = 存在**硬失败**（源异常/超时/熔断）；"全源健康无数据"已由 manager
            # 归入 success=True+empty=True（下面的 empty 分支处理），不在此路径。
            return self._envelope(
                None, attempted=fetched.get('attempted_sources'),
                degraded=True, error=fetched.get('error') or 'event providers failed',
                provider_errors=fetched.get('provider_errors') or {},
                empty=False, empty_sources=list(fetched.get('empty_sources') or []),
                universe=targets, universe_source=universe_source,
            )
        empty = bool(fetched.get('empty'))
        empty_sources = list(fetched.get('empty_sources') or [])
        if empty:
            # 全源健康但无数据（2026-09-11『空结果≠故障』对齐）：**成功且 0 条**。
            # 这里不落库（没有事件可写），但必须返回 success=True —— 任务层据此判绿；
            # 之前 manager 把这种情形报成 success=False，导致无公告日任务误报红。
            return self._envelope(
                [], source=None,
                attempted=fetched.get('attempted_sources'),
                degraded=False,
                universe=targets, universe_source=universe_source,
                empty=True, empty_sources=empty_sources,
                counts={'fetched': 0, 'parsed': 0, 'deduped': 0, 'merged': 0,
                        'rejected': 0, 'inserted': 0, 'updated': 0, 'skipped': 0},
                provider_errors=fetched.get('provider_errors') or {},
                note=('全部事件源健康但对本批标的无事件（0 条）：'
                      '源=%s；这不是故障，未落库、也不计任务失败'
                      % (','.join(empty_sources) or '未记录')),
            )

        prepared = self._domain.prepare(fetched.get('data') or [])
        events: List[MarketEvent] = prepared['events']
        # 多源同一事件的分歧挂回被保留的那条（RFC §3.3：差异不静默丢弃）
        records = []
        for event in events:
            record = self._to_record(event)
            divergence = self._divergence_for(event, prepared['divergences'])
            if divergence:
                record['source_divergence'] = divergence
            records.append(record)
        written = repository.upsert(records)
        notes.extend(self._truncation_notes(manager))
        return self._envelope(
            [e.to_dict() for e in events],
            source=fetched.get('source'),
            attempted=fetched.get('attempted_sources'),
            degraded=bool(fetched.get('degraded')) or bool(notes),
            conflicts=[d.to_dict() for d in prepared['divergences']],
            universe=targets, universe_source=universe_source,
            empty=empty,
            empty_sources=empty_sources,
            truncated=bool(notes),
            provider_notes=notes,
            counts={
                'fetched': len(fetched.get('data') or []),
                'parsed': prepared['parsed'],
                'deduped': prepared['deduped'],
                'merged': len(events),
                'rejected': len(prepared['rejected']),
                **written,
            },
            rejected_rows=prepared['rejected'][:20],
            provider_errors=fetched.get('provider_errors') or {},
        )

    # ------------------------------------------------------------------ 查询

    def list_events(self, scope: Optional[str] = None, type: Optional[str] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None,
                   limit: int = 200) -> Dict:
        """按范围/类型/日期区间查询（含宏观+政策+个股）"""
        repository = self._require_repository()
        if scope:
            EventScope.parse(scope)      # 非法 scope fail-loud（不静默忽略过滤条件）
        if type and type not in {t.value for t in EventType}:
            # 既有宏观类型（cpi_ppi/pmi/…）不在 EventType 里，故只做"非空字符串"宽松校验 + 提示
            pass
        rows = repository.list(scope=scope, type=type, date_from=date_from,
                               date_to=date_to, limit=limit)
        return self._envelope(rows, source='database' if rows else None, stale=False,
                              count=len(rows), filters={'scope': scope, 'type': type,
                                                        'date_from': date_from, 'date_to': date_to})

    def events_for_symbol(self, symbol: str, limit: int = 50,
                          window_days: Optional[int] = None) -> Dict:
        """某标的的事件（含影响它的宏观事件）

        window_days 非空时只保留"今天 ± window_days"范围内的事件（排雷只关心近期）。
        """
        repository = self._require_repository()
        code = str(symbol or '').strip()
        if not code:
            return self._envelope(None, error='symbol 不能为空')
        rows = repository.for_symbol(code, limit=limit)
        # 在**窗口过滤前**记录是否真有个股事件：过滤会把窗口外的事件裁掉，
        # 若在过滤后判断，一次窄窗口查询会把"有数据但不在窗口内"误报成"未采集"。
        has_individual_rows = any(str(r.get('scope') or '') == 'individual' for r in rows)
        dropped = 0
        if window_days:
            # 窗口 = [今天 - window_days, 今天 + window_days]（排雷既要看即将发生、
            # 也要看刚发生的）；用日期字符串比较，避免把"未来"与"过去"混为一谈。
            span = abs(int(window_days))
            low = _shift_date(-span)
            high = _shift_date(span)
            kept = []
            for row in rows:
                effective = str(row.get('effective_date') or '')[:10]
                if low <= effective <= high:
                    kept.append(row)
            dropped = len(rows) - len(kept)
            rows = kept
        # 覆盖状态如实回报（2026-09-11，w-f436d4ea）：个股事件通道的采集范围 =
        # default_universe（持仓 ∪ 启用中的盯盘规则），实测仅 24 只标的被采过。
        # 池外标的只能拿到宏观事件，而"没抓过"与"确实没有"必须可分——买入前排雷时
        # 前者是未知（要去补采），后者才可放心。混合成同一个空结果是拿"没查"冒充"没问题"。
        try:
            covered: Optional[bool] = repository.is_in_default_universe(code)
        except Exception as exc:
            covered = None
            # 本模块用 stdlib logging（非 structlog）：必须 printf 风格，
            # 传 key=value 会抛 TypeError——而且是在异常分支里抛，等于降级逻辑自己崩。
            logger.warning('default_universe 覆盖检查失败: symbol=%s error=%s', code, exc)
        # 语义校准（2026-09-11 第二轮）：本字段回答的是「**有没有**个股事件数据」，
        # 不是「在不在周期采集池里」。初版只看池内成员，导致显式补采过的标的
        # （实测 600176/002080 补采后有 31 条个股事件）仍被标成 not_covered——
        # 反向误导。现在：有数据 → covered；无数据且不在池 → not_covered（未知）；
        # 无数据但检查失败 → unknown（无法断言）。
        if has_individual_rows or covered is True:
            coverage = 'covered'
        elif covered is False:
            coverage = 'not_covered'
        else:
            coverage = 'unknown'
        coverage_note = None
        if coverage == 'not_covered':
            coverage_note = (
                '该标的**不在**个股事件采集池内（持仓 ∪ 启用中的盯盘规则）——返回中不含个股事件，'
                '但这是"未采集"而非"确实没有"：解禁/减持/定增等供给冲击无从判断。'
                '需要排雷请先为该标的建立盯盘规则（watch_manage），或显式触发一次个股 ingest。'
            )
        return self._envelope(rows, source='database' if rows else None,
                              count=len(rows), symbol=code,
                              window_days=window_days, filtered_out=dropped,
                              individual_coverage=coverage, note=coverage_note)

    def upcoming(self, days: int = 7, limit: int = 100) -> Dict:
        """未来 N 天内即将发生的事件（含今天；覆盖宏观+政策+个股）"""
        repository = self._require_repository()
        rows = repository.upcoming(days=days, limit=limit)
        return self._envelope(rows, source='database' if rows else None,
                              count=len(rows), days=days)

    def link_to_watchlist(self, symbols: Optional[List[str]] = None, days: int = 30) -> Dict:
        """事件 → 盯盘规则**建议**（本批只产建议，不自动建规则，RFC §3.2）

        为什么不由服务直接建规则：挂规则会真实触发飞书提醒与资金动作（R-015 分档纪律），
        阈值必须结合价格与仓位由人或 agent 复核。本方法只把"值得盯的时点"列出来。
        """
        repository = self._require_repository()
        targets = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        if targets:
            rows: List[Dict] = []
            seen = set()
            for symbol in targets:
                for row in repository.for_symbol(symbol, limit=200):
                    key = row.get('evidence_hash') or row.get('id')
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(row)
        else:
            rows = repository.upcoming(days=days, limit=300)
        events, rejected = self._domain.parse_rows(rows)
        suggestions = self._domain.watch_suggestions(events, days=days)
        return self._envelope(suggestions, source='database',
                              count=len(suggestions),
                              evaluated=len(events),
                              rejected=len(rejected),
                              symbols=targets or None, days=days,
                              note='本接口只返回建议（auto_created=False），建规则请经人/agent 复核后调用 watch_manage')

    def stats(self) -> Dict:
        """库存统计（体检探针：事件覆盖面与新鲜度）"""
        repository = self._require_repository()
        repo_stats = repository.stats() if hasattr(repository, 'stats') else {}
        return self._envelope(repo_stats, source='database')

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _to_record(event: MarketEvent) -> Dict:
        return event.to_dict()

    @staticmethod
    def _divergence_for(event: MarketEvent, divergences: List) -> Optional[Dict]:
        """把与某事件同源的分歧记录挂回该事件（按 kept_source + kept_title 匹配）"""
        for divergence in divergences:
            if divergence.kept_source == event.source and divergence.kept_title == event.title:
                return divergence.to_dict()
        return None


def _shift_date(delta_days: int) -> str:
    """今天 + delta_days（YYYY-MM-DD；仅用于查询窗口过滤，不做业务判断）"""
    return (date.today() + timedelta(days=delta_days)).strftime('%Y-%m-%d')


# ── 进程级单例（组合根装配；与 industry_chain_service 同模式）────────────

def get_event_feed_service() -> Optional[EventFeedService]:
    return _service_instance


def set_event_feed_service(service: EventFeedService) -> None:
    global _service_instance
    _service_instance = service


# ── 定时任务适配（RFC §3.5：ingest_events_daily / ingest_events_policy）────
#
# 为什么 Job 类定义在本文件：这批只允许改列出的文件（README 纪律），而定时任务的
# JobRegistry 需要"可被 job_executor 按 command 名解析到的 Job 实例"。
# 本类是**薄适配层**（只调用上面两个用例），不含业务逻辑；服务实例由组合根注入
# （main.py 里用入站适配器装配，本文件因此仍然零 adapters 导入）。

class _EventIngestJobBase:
    """事件 ingest 定时任务基类（Job 协议实现，见 application/jobs/job_protocol.py）"""

    def __init__(self, service: EventFeedService, job_name: str, description: str):
        self._service = service
        self._job_name = job_name
        self._description = description

    @property
    def name(self) -> str:
        return self._job_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def timeout_seconds(self) -> int:
        return 900

    async def execute(self, params: Dict[str, Any]):
        from application.jobs.job_protocol import JobResult, result_from_dict
        try:
            result = self._run(params or {})
        except Exception as exc:  # noqa: BLE001 —— 失败必须显式（调度器据此标红并告警）
            logger.exception('event ingest job failed: %s', self._job_name)
            return JobResult.fail(self._job_name, f'{type(exc).__name__}: {exc}')
        # 内部失败（success=False）不允许被包装成"任务成功"（2026-09-11 静默失败教训）
        if isinstance(result, dict) and not result.get('success', True):
            return JobResult.fail(self._job_name, result.get('error') or 'ingest returned success=False')
        counts = result.get('counts') if isinstance(result, dict) else None
        return result_from_dict(self._job_name, f'{self._job_name} done: {counts}', result)

    def _run(self, params: Dict[str, Any]) -> Dict:
        raise NotImplementedError


class IngestEventsDailyJob(_EventIngestJobBase):
    """每日个股事件采集（RFC §3.5：每日 17:00）

    范围 = 持仓 ∪ 启用中的盯盘规则（default_universe），并对该范围跑
    东财公告流 + 巨潮法定披露 + akshare 解禁三条通道（ingest 路径排除 DB 兜底）。
    """

    def __init__(self, service: EventFeedService):
        super().__init__(service, 'ingest_events_daily',
                         '每日个股事件采集：持仓∪盯盘标的的公告/财报/解禁/定增（RFC 015 §3.5）')

    def _run(self, params: Dict[str, Any]) -> Dict:
        symbols = params.get('symbols')
        if isinstance(symbols, str):
            symbols = [s for s in symbols.replace(',', ' ').split() if s]
        return self._service.ingest_symbol_events(symbols=symbols or None,
                                                  universe_limit=int(params.get('universe_limit') or 200))


class IngestEventsPolicyJob(_EventIngestJobBase):
    """政策事件采集（RFC §3.5：每 4 小时）

    通道 = 国务院/发改委（gov.cn JSON + 发改委列表）+ 证监会政策解读，
    全挂/全空时落到人工策展 seed 并在响应里标注 manual_fallback_used。
    """

    def __init__(self, service: EventFeedService):
        super().__init__(service, 'ingest_events_policy',
                         '政策事件采集：国务院/发改委/证监会发布页 + 人工策展兜底（RFC 015 §3.5）')

    def _run(self, params: Dict[str, Any]) -> Dict:
        return self._service.ingest_policy()


def build_event_ingest_jobs(service: EventFeedService) -> List[Any]:
    """构造两个定时任务（组合根在 main.py 里注册进 JobRegistry）

    返回的是 Job 协议实例：name 即 scheduler_tasks.command
    （ingest_events_daily / ingest_events_policy）。
    """
    return [IngestEventsDailyJob(service), IngestEventsPolicyJob(service)]
