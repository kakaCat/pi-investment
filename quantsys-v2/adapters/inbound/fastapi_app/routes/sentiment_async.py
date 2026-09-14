"""情绪/资金 API - FastAPI 版（从 Flask sentiment.py 迁移，响应契约保持一致）

覆盖端点：
- /api/stock/{symbol}/fund-flow     个股资金流向
- /api/stock/{symbol}/margin        个股融资融券
- /api/stock/{symbol}/lhb           龙虎榜（个股）
- /api/stock/{symbol}/fund-holdings 基金持仓
- /api/stock/{symbol}/top-holders   十大股东
- /api/stock/{symbol}/holder-changes 股东变化趋势
- /api/sentiment/top-fund-stocks    基金重仓股

复用同一 LhbService / SentimentService / 数据源实现，保证 parity。
（/api/stock/{symbol}/insider-trades 不在本批迁移范围。）
"""
from typing import Optional

from fastapi import APIRouter, Query
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error, provider_payload,
)
from adapters.shared.services import lhb_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Sentiment - 情绪/资金"])

# 与 Flask 一致：模块级服务单例（通过 ServiceFactory 统一获取）
# lhb_service = LhbService()  # 已迁移到 adapters.shared.services


@router.get('/api/stock/{symbol}/fund-flow')
@handle_api_error
def get_stock_fund_flow_v2(symbol: str, days: int = Query(5)):
    """个股资金流向 - v2 原生实现"""
    from adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
    from application.services.sentiment_service import SentimentService

    # 初始化服务
    fund_flow_source = FundFlowDataSource()
    sentiment_service = SentimentService(fund_flow_source)

    # 获取资金流向数据
    result = sentiment_service.get_stock_fund_flow(symbol, days)

    if 'error' in result:
        # 数据源全部失败=上游不可用（502），而非请求参数错误（400）
        return error_response({'success': False, 'error': result['error']}, 502)

    return api_response(result)


@router.get('/api/stock/{symbol}/margin')
@handle_api_error
def get_stock_margin(symbol: str, days: int = Query(5)):
    """个股融资融券 - v2 原生实现"""
    from adapters.outbound.datasources.margin_data_source import MarginDataSource

    # 初始化数据源
    margin_source = MarginDataSource()

    # 获取融资融券数据
    result = margin_source.get_margin_data(symbol, days)

    return api_response(result)


@router.get('/api/stock/{symbol}/lhb')
@handle_api_error
def get_stock_lhb(symbol: str, days: int = Query(30)):
    """
    龙虎榜 - 个股查询

    Query Params:
        days: 查询最近N天（默认 30）

    Example:
        GET /api/stock/600737/lhb?days=30
    """
    result = lhb_service.get_stock_lhb(symbol, days)
    return api_response(result)


# ===========================================================================
# 股东 / 基金类端点（2026-09-14，w-2129d492，REQ-48d896）
#
# 改造前：这 4 个端点全部走 `SentimentDataSource` —— 该类的 5 个 public 方法
# 都是 `random` 生成的**伪造数据**（已删除），响应还没有任何来源标记。
# 改造后：统一走 provider 多源框架 `get_data_provider_manager()`，
# 每个响应都带 source / attemptedSources / empty / degraded 诚实标记；
# 失败时返回 502（不再用 success:true 掩盖）。
#
# ⚠️ 字段口径变更：旧实现的记录键是伪造的英文名（holderName/shares/...），
#    新实现返回**数据源原生列**（中文列名，如「股东名称」「持股数」）。
#    仓内消费方为零，故按真实口径输出而非迁就伪字段。
# ===========================================================================


def _provider_or_502(result):
    """manager 返回 → 200 数据 或 502 显式失败（不假成功）。"""
    if not result.get('success'):
        return error_response({
            'success': False,
            'error': result.get('error') or '数据源不可用',
            'attempted_sources': list(result.get('attempted_sources') or []),
            'provider_errors': result.get('provider_errors') or {},
        }, 502)
    return api_response(provider_payload(result))


@router.get('/api/stock/{symbol}/fund-holdings')
@handle_api_error
def get_fund_holdings(symbol: str, quarter: Optional[str] = Query(None)):
    """基金持股明细（东财 stock_fund_stock_holder）：哪些基金持有该股。

    原生列：基金名称/基金代码/持仓数量/占流通股比例/持股市值/占净值比例/截止日期
    """
    from adapters.outbound.datasources import get_data_provider_manager

    return _provider_or_502(get_data_provider_manager().get_fund_holdings(symbol, quarter))


@router.get('/api/stock/{symbol}/top-holders')
@handle_api_error
def get_top_holders(symbol: str, holder_type: str = Query('all')):
    """十大股东 / 十大流通股东（东财）。

    holder_type: 'free' / 'circulating' → 十大流通股东；其余（含 'all'）→ 十大股东
    原生列：名次/股东名称/股份类型/持股数/占总股本持股比例/增减/变动比率
    """
    from adapters.outbound.datasources import get_data_provider_manager

    return _provider_or_502(get_data_provider_manager().get_top_holders(symbol, holder_type))


@router.get('/api/stock/{symbol}/holder-changes')
@handle_api_error
def get_holder_changes(symbol: str, periods: int = Query(4)):
    """股东户数变化（东财 stock_zh_a_gdhs_detail_em），最新在前。

    原生列：股东户数统计截止日/股东户数-本次/上次/增减/增减比例/户均持股市值...
    """
    from adapters.outbound.datasources import get_data_provider_manager

    return _provider_or_502(get_data_provider_manager().get_holder_changes(symbol, periods))


@router.get('/api/sentiment/top-fund-stocks')
@handle_api_error
def get_top_fund_stocks(fund_type: str = Query('all'), limit: int = Query(50)):
    """机构重仓股排行（基金/QFII/社保/券商/保险/信托 持仓）。

    ⚠️ 当前**上游数据源不可用**：ak.stock_report_fund_hold 返回的表存在列错位
    （「股票代码」列是浮点、「股票简称」列装的才是 6 位代码），已试换报告期与换函数
    均无可信替代。provider 侧有完整性校验，检测到错位即拒绝返回，
    故本端点目前会**诚实返回 502**（而不是回造数据）；上游修复后自动恢复。
    详见 docs/work-logs/2026-09/ 的 REQ-48d896 记录。
    """
    from adapters.outbound.datasources import get_data_provider_manager

    return _provider_or_502(get_data_provider_manager().get_top_fund_stocks(fund_type, limit))
