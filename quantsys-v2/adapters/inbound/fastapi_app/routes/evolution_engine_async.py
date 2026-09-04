"""策略进化引擎 API（RFC 012 P1，2026-09-03 w-8366e526）

替代 Agent OS legacy evolution（0.05×i 占位）：qv2 真实回测参数进化。

POST /api/evolution/engine/run    跑一轮真实进化（策略 → 参数网格 → 逐变体回测 →
                                  同批 fitness 归一 → 落库 evolution_strategy_runs）
GET  /api/evolution/engine/runs   策略最近进化结果（leaderboard 数据源，P2 工具消费）
GET  /api/evolution/engine/runs/{run_id}  整批变体明细（含 base 对照组与 degraded 行）

请求/响应契约与 qv2 惯例一致：camelCase 进出，api_response 包装（success/data）。
数据诚实性：进化失败返回 data_source=degraded + degraded_reason，绝不产出占位 fitness。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Evolution - 策略进化引擎（RFC 012）"])


def _to_camel_run(result: Dict[str, Any]) -> Dict[str, Any]:
    """服务 snake_case 结果 → qv2 camelCase 契约（proposals/metrics 内部键保留）。"""
    out: Dict[str, Any] = {}
    for k, v in result.items():
        if k == 'proposals':
            out['proposals'] = [
                {
                    'variant': p.get('variant'),
                    'params': p.get('params'),
                    'estimatedFitness': p.get('estimated_fitness'),
                    'metrics': p.get('metrics'),
                    'rationale': p.get('rationale'),
                }
                for p in (v or [])
            ]
        elif k == 'best_metrics':
            out['bestMetrics'] = v
        elif k == 'best_params':
            out['bestParams'] = v
        elif k == 'fitness_improvement':
            out['fitnessImprovement'] = v
        elif k == 'data_source':
            out['dataSource'] = v
        elif k == 'degraded_reason':
            out['degradedReason'] = v
        elif k == 'kline_window':
            out['klineWindow'] = v
        elif k == 'run_id':
            out['runId'] = v
        elif k == 'strategy_id':
            out['strategyId'] = v
        elif k == 'run_at':
            out['runAt'] = v
        elif k in ('total_variants',):
            out['totalVariants'] = v
        elif k in ('success_variants',):
            out['successVariants'] = v
        elif k in ('degraded_variants',):
            out['degradedVariants'] = v
        else:
            out[k] = v
    return out


def _to_camel_row(r: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in r.items():
        if k == 'run_id':
            out['runId'] = v
        elif k == 'strategy_id':
            out['strategyId'] = v
        elif k == 'variant_key':
            out['variantKey'] = v
        elif k == 'kline_window':
            out['klineWindow'] = v
        elif k == 'computed_at':
            out['computedAt'] = v
        elif k == 'degraded_reason':
            out['degradedReason'] = v
        else:
            out[k] = v
    return out


@router.post('/api/evolution/engine/run')
@handle_api_error
def run_evolution(payload: Optional[Dict[str, Any]] = Body(None)):
    """对策略跑一轮真实回测进化（参数网格 → 回测 → 同批 fitness → 落库）。"""
    data = payload or {}
    strategy_id = data.get('strategyId')
    symbol = data.get('symbol')
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    mode = data.get('mode', 'full')
    generations = data.get('generations', 3)
    initial_cash = data.get('initialCash', 1000000)

    if not all([strategy_id, symbol, start_date, end_date]):
        return error_response(
            {'success': False,
             'error': "strategyId, symbol, startDate, endDate are required"}, 400)
    if mode not in ('full', 'propose'):
        return error_response(
            {'success': False, 'error': "mode must be 'full' or 'propose'"}, 400)

    # 服务经共享惰性代理获取（ServiceFactory 单例；路由不自行构造，遵循
    # adapters/shared/services.py 的 PEP 562 __getattr__ 转发惯例）
    from adapters.shared.services import strategy_evolution_service
    service = strategy_evolution_service
    result = service.run(
        strategy_id=strategy_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        generations=int(generations),
        initial_cash=float(initial_cash),
    )
    return api_response(_to_camel_run(result))


@router.get('/api/evolution/engine/runs')
@handle_api_error
def get_runs(
    strategy_id: int = Query(..., description='策略 ID'),
    limit: int = Query(50, ge=1, le=200),
):
    """策略最近进化结果行（真实 fitness，供 leaderboard 数据源）。"""
    from adapters.outbound.repositories.strategy_evolution_run_repository import (
        StrategyEvolutionRunORMRepository,
    )
    repo = StrategyEvolutionRunORMRepository()
    rows = repo.get_runs(strategy_id=strategy_id, limit=limit)
    return api_response({'runs': [_to_camel_row(r) for r in rows]})


@router.get('/api/evolution/engine/runs/{run_id}')
@handle_api_error
def get_run_detail(run_id: str):
    """整批变体明细（含 base 对照组与 degraded 行，按 variant 升序）。"""
    from adapters.outbound.repositories.strategy_evolution_run_repository import (
        StrategyEvolutionRunORMRepository,
    )
    repo = StrategyEvolutionRunORMRepository()
    rows = repo.get_run(run_id=run_id)
    if not rows:
        return error_response({'success': False, 'error': f"run not found: {run_id}"}, 404)
    return api_response({'runId': run_id, 'variants': [_to_camel_row(r) for r in rows]})
