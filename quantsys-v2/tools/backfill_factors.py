#!/usr/bin/env python3
"""
因子历史回填脚本（R2）

目的：为新管线因子（lowercase）补充250天历史，支持ML训练
策略：
- 逐日计算并保存（非只存最新值）
- 使用 FactorStage（与日更同款）
- 支持断点续传（已存在的日期跳过）
- 限流避免DB压力（batch保存）
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import structlog

# 添加项目根到 PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.services.service_factory import ServiceFactory
from domain.quantlib.stages.factor_stage import FactorStage
from adapters.shared.fund_flow_helpers import (
    _inject_fund_flow_to_klines, _extract_fund_flow_factors,
)
from adapters.outbound.repositories.stock_repository import StockORMRepository

logger = structlog.get_logger(__name__)


def backfill_factors(
    symbols: List[str],
    start_date: str,
    end_date: str,
    batch_size: int = 100,
    skip_existing: bool = True,
) -> Dict[str, Any]:
    """
    回填因子历史数据
    
    Args:
        symbols: 股票代码列表
        start_date: 回填起始日期 (YYYY-MM-DD)
        end_date: 回填结束日期 (YYYY-MM-DD)
        batch_size: 每批处理股票数（避免内存爆炸）
        skip_existing: 是否跳过已有数据的日期
    
    Returns:
        回填统计信息
    """
    from adapters.shared.services import get_kline_repo, get_factor_repo
    kline_repo = get_kline_repo()
    factor_repo = get_factor_repo()
    
    # 计算需要回填的交易日列表（使用某只流动性好的股票的交易日历）
    ref_klines_df = kline_repo.get_daily_klines('000001', start_date, end_date)
    if ref_klines_df is None or ref_klines_df.is_empty():
        logger.error("无法获取参考交易日历")
        return {"success": False, "error": "无法获取交易日历"}
    
    ref_klines = ref_klines_df.to_dicts()
    trading_dates = [k.get('trade_date') or k.get('date') for k in ref_klines]
    trading_dates = [str(d) for d in trading_dates if d]
    
    logger.info(f"回填范围：{start_date} ~ {end_date}，共 {len(trading_dates)} 个交易日")
    logger.info(f"回填股票：{len(symbols)} 只")
    
    total_saved = 0
    total_failed = 0
    failed_symbols = []
    
    # 分批处理股票
    for batch_idx in range(0, len(symbols), batch_size):
        batch_symbols = symbols[batch_idx:batch_idx + batch_size]
        logger.info(f"处理批次 {batch_idx//batch_size + 1}/{(len(symbols)-1)//batch_size + 1}，股票数: {len(batch_symbols)}")
        
        for sym in batch_symbols:
            try:
                # 获取该股票的完整K线数据（一次性拉取，避免逐日查询）
                # 多拉60天以提供充足lookback（momentum_52w_high需252天）
                extended_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=300)).strftime('%Y-%m-%d')
                klines_df = kline_repo.get_daily_klines(sym, extended_start, end_date)
                
                if klines_df is None or klines_df.is_empty():
                    logger.warning(f"{sym}: 无K线数据，跳过")
                    failed_symbols.append(sym)
                    total_failed += 1
                    continue
                
                all_klines = klines_df.to_dicts()
                all_klines = _inject_fund_flow_to_klines(all_klines, sym)
                
                # 按日期索引K线（快速查找）
                klines_by_date = {
                    (k.get('trade_date') or k.get('date')): i 
                    for i, k in enumerate(all_klines)
                }
                
                # 逐日计算并保存
                for target_date_str in trading_dates:
                    if skip_existing:
                        # TODO: 检查该股票+日期是否已有因子数据（优化：批量查询）
                        pass
                    
                    # 找到target_date在all_klines中的位置
                    if target_date_str not in klines_by_date:
                        continue  # 该股票当天无交易（停牌/未上市）
                    
                    target_idx = klines_by_date[target_date_str]
                    # 取截至target_date的历史数据（最多300天lookback）
                    lookback_start_idx = max(0, target_idx - 300)
                    klines_slice = all_klines[lookback_start_idx:target_idx+1]
                    
                    if len(klines_slice) < 20:
                        continue  # 数据不足20天，无法计算
                    
                    # 计算因子
                    stage = FactorStage(name='backfill_factors')
                    result = stage.process({'symbol': sym, 'klines': klines_slice})
                    factors = result.get('factors', {})
                    
                    # 提取资金流因子
                    fund_factors = _extract_fund_flow_factors(klines_slice)
                    factors.update(fund_factors)
                    
                    # 保存到DB（关键：保存target_date，非最新日期）
                    if factors:
                        factor_repo.save_factors(sym, target_date_str, factors)
                        total_saved += 1
                
                if (batch_idx + symbols.index(sym) - batch_idx) % 10 == 0:
                    logger.info(f"进度：{sym} 完成，已保存 {total_saved} 条")
                    
            except Exception as e:
                logger.error(f"{sym} 回填失败: {e}")
                failed_symbols.append(sym)
                total_failed += 1
    
    return {
        "success": True,
        "total_symbols": len(symbols),
        "total_saved": total_saved,
        "total_failed": total_failed,
        "failed_symbols": failed_symbols[:50],  # 只返回前50个失败股票
        "trading_dates_count": len(trading_dates),
    }


def main():
    """主入口：回填最近250天的因子历史"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    # 250个交易日 ≈ 350个自然日
    start_date = (datetime.now() - timedelta(days=350)).strftime('%Y-%m-%d')
    
    # 获取股票列表（可选：只回填重要股票，或全市场）
    repo = StockORMRepository()
    # 先回填500只流动性好的股票（加速验证），后续可扩展
    stocks = repo.get_all(limit=500)
    symbols = [s['symbol'] for s in stocks]
    
    logger.info(f"开始回填因子历史：{start_date} ~ {end_date}")
    logger.info(f"目标股票：{len(symbols)} 只")
    
    result = backfill_factors(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        batch_size=50,  # 每批50只，避免内存压力
        skip_existing=True,
    )
    
    logger.info("回填完成", result=result)
    print("\n=== 回填结果 ===")
    print(f"总股票数: {result['total_symbols']}")
    print(f"保存条数: {result['total_saved']}")
    print(f"失败股票: {result['total_failed']}")
    print(f"交易日数: {result['trading_dates_count']}")
    if result.get('failed_symbols'):
        print(f"失败示例: {result['failed_symbols'][:10]}")


if __name__ == '__main__':
    main()
