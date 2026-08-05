"""进化适应度排行榜 API（行为进化 Phase 1）

响应契约与 Flask parity 一致：api_response 包装（success/data，camelCase 序列化）。
"""
from typing import Optional

from fastapi import APIRouter, Query
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Evolution - 行为进化"])


@router.get('/api/evolution/leaderboard')
@handle_api_error
def get_leaderboard(
    window: int = Query(20, ge=5, le=60),
    window_end: Optional[str] = Query(None, description='YYYY-MM-DD，默认最新已计算日'),
    include_non_ok: bool = Query(False),
):
    """全账户双侧捕获适应度排行（fitness 降序，rank 从 1 起）"""
    from datetime import date as _date
    from adapters.outbound.repositories.evolution_fitness_repository import (
        EvolutionFitnessORMRepository,
    )
    repo = EvolutionFitnessORMRepository()
    end = _date.fromisoformat(window_end) if window_end else repo.get_latest_window_end(window)
    if end is None:
        return api_response({'windowEnd': None, 'ranking': [], 'message': '尚无适应度数据'})
    rows = repo.get_leaderboard(end, window_days=window, include_non_ok=include_non_ok)
    for i, row in enumerate(rows, 1):
        row['rank'] = i
    return api_response({'windowEnd': end.isoformat(), 'windowDays': window, 'ranking': rows})
