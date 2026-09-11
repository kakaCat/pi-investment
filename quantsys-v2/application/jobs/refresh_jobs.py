"""自维护回路任务（RFC 015 §2.5 / §4.5，2026-09-11，w-f436d4ea）

补上 P1/P2 的两条**自维护回路**——此前两个能力都只能手动触发或按需取数，
本地兜底侧的数据不更新，能力会随时间衰减：

  · minute_kline_sync      ：盘中增量采分钟线落库（P1 的本地兜底链路；此前
                            quant.minute_klines 断更至 2026-05-29）
  · industry_chain_refresh ：重建产业链成员归位（P2 的成员证据刷新；此前无任何任务调用 build_chain）

设计要点：
1. **复用既有组合根**（manager / minute repo / chain service / universe repo），不新增基础设施。
2. **范围受控**：默认 = 持仓 ∪ 启用盯盘规则（复用仓储 default_universe），
   不做全市场分钟线入库（量级不可控）；pool 也支持 params.symbols 显式指定。
3. **幂等前提**：落库走 save_minute_klines，而它已于 2026-09-11 改为
   PostgreSQL ON CONFLICT DO UPDATE —— 这是"每 5 分钟反复跑"能成立的前提
   （原实现 add_all 直插，第二次必然因重叠 K 线冲突整批失败）。
4. **失败显式**：逐标的失败计入 failures 并如实返回；整体 success=False 时
   调度器据此标红（不得把部分失败包装成成功）。
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _RefreshJobBase:
    """自维护任务的公共骨架（与 event ingest job 同款契约）"""

    def __init__(self, name: str, description: str, timeout_seconds: int = 900):
        self._job_name = name
        self._description = description
        self._timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return self._job_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_seconds

    async def execute(self, params: Dict[str, Any]):
        from application.jobs.job_protocol import JobResult, result_from_dict
        try:
            result = self._run(params or {})
        except Exception as exc:  # noqa: BLE001 失败必须显式，调度器据此标红
            logger.exception('refresh job failed: %s', self._job_name)
            return JobResult.fail(self._job_name, f'{type(exc).__name__}: {exc}')
        if isinstance(result, dict) and not result.get('success', True):
            return JobResult.fail(self._job_name, result.get('error') or 'refresh returned success=False')
        return result_from_dict(self._job_name, f'{self._job_name} done', result)

    def _run(self, params: Dict[str, Any]) -> Dict:
        raise NotImplementedError


def _resolve_symbols(params: Dict[str, Any], universe_repo, default_period_limit: int = 60) -> (List[str], str):
    """解析标的范围：params.symbols 优先，否则用 default_universe（持仓∪盯盘规则）"""
    symbols = params.get('symbols')
    if isinstance(symbols, str):
        symbols = [s for s in symbols.replace(',', ' ').split() if s]
    if symbols:
        return [str(s).split('.')[0] for s in symbols], 'params.symbols'
    if universe_repo is None:
        return [], 'none(未注入 universe 仓储)'
    try:
        return [str(s).split('.')[0] for s in universe_repo.default_universe(limit=int(params.get('universe_limit') or default_period_limit))], 'default_universe(持仓∪盯盘规则)'
    except Exception as exc:  # noqa: BLE001
        logger.warning('default_universe 取数失败: %s', exc)
        return [], f'default_universe 失败: {exc}'


class MinuteKlineSyncJob(_RefreshJobBase):
    """盘中分钟线增量同步（RFC 015 §4.5：仅自选池+持仓，控制数据量）

    范围受控是刻意的：全市场分钟线入库量级不可控。默认只同步
    持仓 ∪ 启用盯盘规则，让 Network→DB 的兜底链路真正有数据。
    """

    def __init__(self, manager, minute_repo, universe_repo=None):
        super().__init__('minute_kline_sync',
                         '盘中分钟线增量同步：持仓∪盯盘标的（多源取数 → 幂等 upsert 落库，RFC 015 §4.5）',
                         timeout_seconds=600)
        self._manager = manager
        self._minute_repo = minute_repo
        self._universe_repo = universe_repo

    def _run(self, params: Dict[str, Any]) -> Dict:
        symbols, universe_source = _resolve_symbols(params, self._universe_repo)
        if not symbols:
            # 空池不伪造标的（与 event ingest 同款契约）
            return {'success': True, 'synced_symbols': 0, 'saved_bars': 0,
                    'note': f'采集池为空（{universe_source}）：未采集，不伪造标的',
                    'universe_source': universe_source}

        period = str(params.get('period') or '5m')
        limit = int(params.get('limit') or 240)
        saved_bars = 0
        synced: List[str] = []
        failures: Dict[str, str] = {}

        for sym in symbols:
            try:
                resp = self._manager.get_minute_klines(sym, period=period, limit=limit)
                if not resp or not resp.get('success'):
                    failures[sym] = str(resp.get('error') if isinstance(resp, dict) else 'no response')[:120]
                    continue
                payload = resp.get('data') or {}
                bars = payload.get('data') if isinstance(payload, dict) else payload
                bars = bars or []
                if not bars:
                    failures[sym] = '取数为空'
                    continue
                # 行可能是 dict，也可能是已被 provider 转好的领域模型 MinuteKline
                # （2026-09-11 实测：manager 返回的就是 MinuteKline 对象，早期按 dict
                #  处理导致 AttributeError: 'MinuteKline' object has no attribute 'get'）。
                from domain.models.market_data import MinuteKline as MinuteKlineModel

                def _to_model(b):
                    if isinstance(b, dict):
                        dt = b.get('trade_datetime') or b.get('date')
                        if not dt:
                            return None
                        return MinuteKlineModel(
                            symbol=b.get('symbol') or sym,
                            trade_datetime=str(dt),
                            open=float(b.get('open') or 0.0),
                            high=float(b.get('high') or 0.0),
                            low=float(b.get('low') or 0.0),
                            close=float(b.get('close') or 0.0),
                            volume=float(b.get('volume') or 0.0),
                            amount=float(b.get('amount') or 0.0),
                            period=period,
                            source=str(resp.get('source') or ''),
                        )
                    # 已是领域模型：补齐 period/source 后直接透传
                    try:
                        if not getattr(b, 'trade_datetime', None):
                            return None
                        b.period = period
                        if not getattr(b, 'source', ''):
                            b.source = str(resp.get('source') or '')
                        return b
                    except Exception:  # noqa: BLE001
                        return None

                models = [m for m in (_to_model(b) for b in bars) if m is not None]
                if not models:
                    failures[sym] = '取数行缺少时间字段'
                    continue
                if not self._minute_repo.save_minute_klines(models):
                    failures[sym] = '落库失败（幂等 upsert 返回 False）'
                    continue
                saved_bars += len(models)
                synced.append(sym)
            except Exception as exc:  # noqa: BLE001 逐标的隔离，不让单只拖垮整批
                failures[sym] = f'{type(exc).__name__}: {exc}'[:120]

        result: Dict[str, Any] = {
            'success': len(synced) > 0 or not symbols,
            'universe_source': universe_source,
            'period': period,
            'requested_symbols': len(symbols),
            'synced_symbols': len(synced),
            'saved_bars': saved_bars,
            'failures': failures,
        }
        if not synced and symbols:
            result['error'] = f'全部 {len(symbols)} 只取数/落库失败（样例: {list(failures.items())[:2]}）'
        return result


class IndustryChainRefreshJob(_RefreshJobBase):
    """产业链成员刷新（RFC 015 §2.5：周更重建成员归位）

    逐链重建：策展拓扑 → 主营构成/产品归位 → 领域裁决 → 幂等整链替换落库。
    证据源（东财/同花顺）的弱化不会污染结果——归位裁决在领域层，
    弱证据只在 weak_evidence 里点名。
    """

    def __init__(self, chain_service):
        super().__init__('industry_chain_refresh',
                         '产业链成员刷新：逐链重建归位并落库（RFC 015 §2.5）',
                         timeout_seconds=900)
        self._service = chain_service

    def _run(self, params: Dict[str, Any]) -> Dict:
        names = params.get('chains')
        if isinstance(names, str):
            names = [n for n in names.replace(',', ' ').split() if n]
        if not names:
            listing = self._service.list_chains()
            if not listing.get('success'):
                return {'success': False, 'error': f"产业链清单取数失败: {listing.get('error')}"}
            payload = listing.get('data') or {}
            chains = payload.get('chains') if isinstance(payload, dict) else payload
            names = [c.get('name') for c in (chains or []) if c.get('name')]
        if not names:
            return {'success': False, 'error': '无可用产业链（策展库为空或清单解析失败）'}

        refreshed: List[Dict[str, Any]] = []
        failures: Dict[str, str] = {}
        for name in names:
            try:
                resp = self._service.build_chain(name, persist=True)
                if not resp.get('success'):
                    failures[name] = str(resp.get('error') or 'build_chain 返回失败')[:140]
                    continue
                data = resp.get('data') or {}
                attr = (data.get('rebuild') or {}).get('attribution_summary') if isinstance(data, dict) else None
                refreshed.append({
                    'chain': name,
                    'members': (data.get('member_count') if isinstance(data, dict) else None),
                    'attribution': attr or {},
                })
            except Exception as exc:  # noqa: BLE001 逐链隔离
                failures[name] = f'{type(exc).__name__}: {exc}'[:140]

        return {
            'success': len(refreshed) > 0,
            'refreshed_count': len(refreshed),
            'refreshed': refreshed,
            'failures': failures,
            'error': None if refreshed else f'全部 {len(names)} 条链刷新失败',
        }


def build_refresh_jobs(manager, minute_repo, chain_service, universe_repo=None) -> List[Any]:
    """构造两个自维护任务（组合根在 main.py 注册进 JobRegistry）

    返回 Job 协议实例：name 即 scheduler_tasks.command
    （minute_kline_sync / industry_chain_refresh）。
    """
    return [
        MinuteKlineSyncJob(manager, minute_repo, universe_repo),
        IndustryChainRefreshJob(chain_service),
    ]
