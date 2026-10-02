"""因子计算任务处理器

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_common import logger  # noqa: F401

MIN_BARS_FOR_FACTORS = 26  # MACD 最长窗口（26 根）→ 全量技术因子可算的最低门槛

_NON_EQUITY_NAME_KEYWORDS = (
    '退', '定转', '指数', '沪深300', '上证50', '中证500', '中证1000',
    '深证成指', '创业板指', '科创50',
)

def _filter_factor_universe(symbols, start_date: str, end_date: str):
    """因子计算前预筛标的池（2026-09-10 修复 C，w-8f2c4cc5）。

    背景：因子池直接取 stocks 全表，未剔除①退市/ST ②定转凭证（810xxx）③指数伪标的
    ④K 线不足的标的（新上市/长期停牌）。实测 8 只标的在同一个 pass 里各抛 8 次
    InsufficientDataError（ATR14 / RSI14 / BOLL×3 / MACD×3），既污染 Agent OS 错误
    事件流（8 条事件 28 次），又让整轮全市场计算的失败面被误读为"系统异常"。

    返回 (kept, dropped)；dropped 为统计 dict，供调用方日志留痕。
    """
    # 2026-09-14（REQ-24e15d B4-c5）：原为裸 SQL（stocks LEFT JOIN daily_klines 统计 bars，
    # 日期条件在 ON 子句、symbol = ANY(:syms) 绑定列表），收进
    # KlineORMRepository.count_bars_by_symbol()，口径逐字保留（见该方法 docstring）。
    from adapters.outbound.repositories.kline_repository import KlineORMRepository

    dropped = {
        'delisted': 0, 'st': 0, 'non_equity': 0, 'insufficient_bars': 0,
        'unknown': [], 'examples': [],
    }
    if not symbols:
        return [], dropped

    rows = KlineORMRepository().count_bars_by_symbol(symbols, start_date, end_date)
    known = {r['symbol']: r for r in rows}

    kept = []
    for sym in symbols:
        r = known.get(sym)
        if r is None:
            dropped['unknown'].append(sym)      # 不在股票主表（指数伪代码等）
            continue
        name = r['name'] or ''
        if r['is_delisted']:
            dropped['delisted'] += 1
            continue
        # ST 判定用 is_st 布尔位 + 名称前缀（A 股 ST 一律以 ST/*ST 开头；
        # 不做全文子串匹配——"Test" 这类名称含 "ST"，会被误判成 ST 股）
        upper = name.upper()
        if r['is_st'] or upper.startswith('ST') or upper.startswith('*ST'):
            dropped['st'] += 1
            continue
        # 非股票标的：定转挂牌凭证（810xxx）、带后缀的伪代码（600000.SH~600009.SH
        # 「Test」测试污染行，实测 stocks 表内 10 行）、指数伪标的（名称关键词）
        if sym.startswith('810') or '.' in sym or 'TEST' in upper \
                or any(k in name for k in _NON_EQUITY_NAME_KEYWORDS):
            dropped['non_equity'] += 1
            if len(dropped['examples']) < 10:
                dropped['examples'].append(f"{sym} {name}")
            continue
        bars = int(r['bars'] or 0)
        if bars < MIN_BARS_FOR_FACTORS:
            dropped['insufficient_bars'] += 1
            if len(dropped['examples']) < 10:
                dropped['examples'].append(f"{sym} {bars}bar")
            continue
        kept.append(sym)
    return kept, dropped


def handle_factor_compute(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """因子计算任务（盘后批量重算并落库，为次日信号做准备）

    注意：不要调用 FactorAnalysisService —— 它是 IC/收益分析服务，
    没有 compute_factors 入口。批量计算走 FactorStage（与
    adapters/inbound/api/routes/jobs.py 的 compute_factors 同一条路径）。
    """
    params = params or {}

    logger.info("Starting factor_compute task")

    try:
        from domain.backtest.stages.factor_stage import FactorStage
        from adapters.shared.fund_flow_helpers import (
            _inject_fund_flow_to_klines, _extract_fund_flow_factors,
        )
        from adapters.outbound.repositories import KlineORMRepository, FactorORMRepository

        # 获取股票列表（如果没有指定）
        symbols = params.get('symbols')
        if not symbols:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStockRepository
            repo = EnhancedServiceFactory.resolve(IStockRepository)
            stocks = repo.get_all(limit=params.get('max_symbols', 500))
            # 过滤指数代码（399开头、000300、000852、000016等）
            symbols = [
                s['symbol'] for s in stocks 
                if not s['symbol'].startswith('399')  # 深证指数
                and s['symbol'] not in ('000300', '000852', '000016', '000905', '000906')  # 常见指数
            ]

        requested = params.get('factors') or None
        if requested == ['all']:
            requested = None  # None = FactorStage 默认全量技术因子

        # R1修复v2（2026-09-03）：lookback 300→420。v1 混淆了自然日与交易日——
        # momentum_52w_high 需要 250 根日K（交易日），300 自然日实际只有 ~201 根，
        # 导致该因子全市场静默丢弃（8/18 后零落库）。420 自然日 ≈ 280 交易日，留 30 天缓冲。
        lookback_days = params.get('lookback_days', 420)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        # C 修复（2026-09-10）：进入 FactorStage 之前预筛标的池——退市/ST/定转/指数
        # 伪标的/K 线不足标的直接剔除，避免"预期内数据不足"被当成系统异常刷错误事件。
        symbols, dropped = _filter_factor_universe(symbols, start_date, end_date)
        universe_dropped = dropped
        logger.info(
            f"factor universe 预筛：{len(symbols)} 只入选，剔除 "
            f"{dropped['delisted']} 退市 / {dropped['st']} ST / "
            f"{dropped['non_equity']} 非股票标的 / "
            f"{dropped['insufficient_bars']} K线<{MIN_BARS_FOR_FACTORS}根 / "
            f"{len(dropped['unknown'])} 不在主表；样例={dropped['examples']}")

        computed = 0
        failed = []
        for sym in symbols:
            try:
                kline_repo = KlineORMRepository()
                klines_df = kline_repo.get_daily_klines(sym, start_date, end_date)
                if klines_df is None or klines_df.is_empty():
                    failed.append(sym)
                    continue

                klines = klines_df.to_dicts()
                klines = _inject_fund_flow_to_klines(klines, sym)
                
                stage = FactorStage(name='factors', factor_names=requested)
                stage_input = {'symbol': sym, 'klines': klines}
                if requested:
                    stage_input['requested_factors'] = requested

                result = stage.process(stage_input)
                factors = result.get('factors', {})
                
                all_requested = requested or stage.DEFAULT_TECHNICAL_FACTORS
                computed_names = set(factors.keys())
                missing = set(all_requested) - computed_names
                if missing and len(klines) < 250:
                    logger.warning(f"{sym}: {len(missing)} factors dropped (insufficient data {len(klines)}<250): {sorted(missing)}")
                
                fund_factors = _extract_fund_flow_factors(klines)
                factors.update(fund_factors)

                last_row = klines[-1]
                latest_date = last_row.get('trade_date') or last_row.get('date') or ''
                FactorORMRepository().save_factors(sym, str(latest_date), factors)
                computed += 1
            except Exception as sym_err:
                logger.warning(f"factor compute failed for {sym}: {sym_err}")
                failed.append(sym)

        return {
            "action": "factor_compute",
            "status": "success",
            "symbols_count": len(symbols),
            "factors_computed": computed,
            "failed": failed[:20],
            "universe_dropped": {k: v for k, v in universe_dropped.items() if k != 'examples'},
            "universe_dropped_examples": universe_dropped['examples'],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Factor compute failed: {e}")
        return {
            "action": "factor_compute",
            "status": "failed",
            "error": str(e)
        }


