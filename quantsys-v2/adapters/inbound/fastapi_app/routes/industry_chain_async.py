"""产业链图谱 API（RFC 015 §2.4，2026-09-11 REQ-cf627b P2）

数据流：
    agent-dh 工具 / web → 本路由（入站适配器）
        → application/services/industry_chain_service（编排，零 adapters 依赖）
            → domain/industry_chain/service（拓扑自校验/去重/证据冲突裁决）
            → 端口 ← adapters.outbound（provider 多源矩阵 / repository）

组合根说明：具体实现的装配放在**本文件**（入站适配器），应用层因此可以完全不出现 adapters
导入（ADR-001 依赖倒置红线；2026-09-11 的历史审计共 157 处违规，P1 起沿用"组合根前移"）。

端点：
    GET  /api/industry-chains                 产业链清单（策展 → DB 兜底）
    GET  /api/industry-chains/{name}          单链全貌（按环节分组的成员 + evidence，只读不打上游）
    GET  /api/stocks/{symbol}/chain           个股 → 所属链/环节/主营占比
    POST /api/industry-chains/{name}/scan     链式扫描（按环节分组 + 实时行情 + 低置信候选）
                                              ?rebuild=true 时先跑一遍 build_chain（策展拓扑 +
                                              主营构成归位 → 落库），供定时任务与人工刷新使用
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
import structlog

from adapters.inbound.fastapi_app.shared import error_response
from application.services.industry_chain_service import (
    IndustryChainService,
    get_industry_chain_service,
    set_industry_chain_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Industry Chain - 产业链图谱"])


def get_service() -> IndustryChainService:
    """组合根：装配 IDataProviderManager + IIndustryChainRepository（进程级复用）"""
    svc = get_industry_chain_service()
    if svc is None:
        from adapters.outbound.datasources.manager import get_data_provider_manager
        from adapters.outbound.repositories.industry_chain_repository import (
            get_industry_chain_repo,
        )
        svc = IndustryChainService(
            manager=get_data_provider_manager(),
            repository=get_industry_chain_repo(),
        )
        set_industry_chain_service(svc)
    return svc


@router.get('/api/industry-chains')
def list_industry_chains():
    """产业链清单（含节点数、成员数、最近构建时间、来源）"""
    try:
        return get_service().list_chains()
    except Exception as e:
        logger.error('list_industry_chains failed', error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.get('/api/industry-chains/{name}')
def get_industry_chain(name: str):
    """单链全貌：按环节分组（上游/中游/下游/终端）+ 每个成员的 evidence/confidence

    只读（不打上游）：成员优先取上次 build 落库结果，未 build 时退回策展 seed 成员。
    刷新证据请用 POST /api/industry-chains/{name}/scan?rebuild=true。
    """
    try:
        result = get_service().get_chain(name)
        if not result.get('success'):
            # 404=这条链不存在；502=策展源取数失败（拓扑不可降级，不能静默返回空链）
            return error_response(result, 404 if result.get('not_found') else 502)
        return result
    except Exception as e:
        logger.error('get_industry_chain failed', name=name, error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.get('/api/stocks/{symbol}/chain')
def get_symbol_chain(symbol: str):
    """个股 → 所属链/环节/主营占比（链式扫描的关键查询）

    同时给出**实时主营构成**（东财 F10 → 同花顺 F10 → DB 兜底），即便该标的尚未入链，
    也能回答"它靠什么赚钱"，供人工判断应归哪个环节。
    """
    try:
        return get_service().map_symbol(symbol)
    except Exception as e:
        logger.error('get_symbol_chain failed', symbol=symbol, error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)


@router.post('/api/industry-chains/{name}/scan')
def scan_industry_chain(
    name: str,
    payload: Optional[Dict[str, Any]] = Body(None),
    rebuild: bool = Query(default=False, description='true=先执行 build_chain（策展拓扑+主营构成归位→落库）'),
):
    """链式扫描：按环节分组的标的 + 实时行情 + 低置信候选（行业板块）

    Body（可选）：{"include_quotes": true, "include_candidates": true}
    """
    params = payload or {}
    try:
        svc = get_service()
        rebuilt = None
        if rebuild:
            rebuilt = svc.build_chain(name)
            if not rebuilt.get('success'):
                return error_response(rebuilt, 502)
        result = svc.chain_scan(
            name,
            include_quotes=bool(params.get('include_quotes', True)),
            include_candidates=bool(params.get('include_candidates', True)),
        )
        if not result.get('success'):
            return error_response(result, 404 if result.get('not_found') else 502)
        if rebuilt is not None:
            result['rebuild'] = {
                'success': rebuilt.get('success'),
                'attribution_summary': rebuilt.get('attribution_summary'),
                'persist_result': rebuilt.get('persist_result'),
                'evidence_conflicts': rebuilt.get('evidence_conflicts'),
            }
        return result
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 400)
    except Exception as e:
        logger.error('scan_industry_chain failed', name=name, error=str(e))
        return error_response({'success': False, 'error': f'{type(e).__name__}: {e}'}, 500)
