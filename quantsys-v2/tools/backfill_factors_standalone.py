#!/usr/bin/env python3
"""
因子历史回填脚本（R2） - Standalone版本

目的：为新管线因子（lowercase）补充250天历史，支持ML训练
策略：逐日计算并保存（非只存最新值）
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import structlog

# 添加项目根到 PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.services.service_factory import ServiceFactory
from domain.quantlib.stages.factor_stage import FactorStage
from adapters.outbound.repositories.stock_repository import StockORMRepository

logger = structlog.get_logger(__name__)


def extract_fund_flow_factors_simple(klines: List[Dict]) -> Dict[str, float]:
    """简化版资金流因子提取（避免复杂依赖）"""
    if not klines:
        return {}
    
    last = klines[-1]
    recent_5 = klines[-5:] if len(klines) >= 5 else klines
    recent_3 = klines[-3:] if len(klines) >= 3 else klines
    
    # 提取最新资金流数据（如果存在）
    factors = {}
    
    # 单日净流入
    if 'main_net_inflow' in last:
        factors['main_net_inflow'] = float(last.get('main_net_inflow', 0))
    if 'large_net' in last:
        factors['large_net'] = float(last.get('large_net', 0))
    if 'super_large_net' in last:
        factors['super_large_net'] = float(last.get('super_large_net', 0))
    
    # 百分比
    if 'main_net_pct' in last:
        factors['main_net_pct'] = float(last.get('main_net_pct', 0))
    if 'large_pct' in last:
        factors['large_pct'] = float(last.get('large_pct', 0))
    if 'super_large_pct' in last:
        factors['super_large_pct'] = float(last.get('super_large_pct', 0))
    
    # 多日累计
    sum_3d = sum(k.get('main_net_inflow', 0) for k in recent_3)
    sum_5d = sum(k.get('main_net_inflow', 0) for k in recent_5)
    factors['fund_inflow_3d_sum'] = float(sum_3d)
    factors['fund_inflow_5d_sum'] = float(sum_5d)
    
    # 正流入天数
    pos_days_3 = sum(1 for k in recent_3 if k.get('main_net_inflow', 0) > 0)
    pos_days_5 = sum(1 for k in recent_5 if k.get('main_net_inflow', 0) > 0)
    factors['fund_inflow_pos_days_3'] = float(pos_days_3)
    factors['fund_inflow_pos_days_5'] = float(pos_days_5)
    
    return factors


def backfill_factors(
    symbols: List[str],
    start_date: str,
    end_date: str,
    batch_size: int = 100,
) -> Dict[str, Any]:
    """
    回填因子历史数据
    
    Args:
        symbols: 股票代码列表
        start_date: 回填起始日期 (YYYY-MM-DD)
        end_date: 回填结束日期 (YYYY-MM-DD)
        batch_size: 每批处理股票数
    
    Returns:
        回填统计信息
    """
    from adapters.shared.services import get_kline_repo, get_factor_repo
    kline_repo = get_kline_repo()
    factor_repo = get_factor_repo()
    
    # 获取交易日历
    ref_klines_df = kline_repo.get_daily_klines('000001', start_date, end_date)
    if ref_klines_df is None or ref_klines_df.is_empty():
        logger.error("无法获取参考交易日历")
        return {"success": False, "error": "无法获取交易日历"}
    
    ref_klines = ref_klines_df.to_dicts()
    trading_dates = [str(k.get('trade_date') or k.get('date')) for k in ref_klines if k.get('trade_date') or k.get('date')]
    
    logger.info(f"回填范围：{start_date} ~ {end_date}，共 {len(trading_dates)} 个交易日")
    logger.info(f"回填股票：{len(symbols)} 只")
    
    total_saved = 0
    total_failed = 0
    failed_symbols = []
    
    for batch_idx in range(0, len(symbols), batch_size):
        batch_symbols = symbols[batch_idx:batch_idx + batch_size]
        logger.info(f"批次 {batch_idx//batch_size + 1}，股票数: {len(batch_symbols)}")
        
        for sym in batch_symbols:
            try:
                # 多拉60天提供lookback
                extended_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=300)).strftime('%Y-%m-%d')
                klines_df = kline_repo.get_daily_klines(sym, extended_start, end_date)
                
                if klines_df is None or klines_df.is_empty():
                    logger.warning(f"{sym}: 无K线数据")
                    failed_symbols.append(sym)
                    total_failed += 1
                    continue
                
                all_klines = klines_df.to_dicts()
                
                # 按日期索引
                klines_by_date = {}
                for i, k in enumerate(all_klines):
                    date_key = str(k.get('trade_date') or k.get('date'))
                    if date_key:
                        klines_by_date[date_key] = i
                
                # 逐日计算
                saved_count = 0
                for target_date_str in trading_dates:
                    if target_date_str not in klines_by_date:
                        continue
                    
                    target_idx = klines_by_date[target_date_str]
                    lookback_start_idx = max(0, target_idx - 300)
                    klines_slice = all_klines[lookback_start_idx:target_idx+1]
                    
                    if len(klines_slice) < 20:
                        continue
                    
                    # 计算技术因子
                    stage = FactorStage(name='backfill')
                    result = stage.process({'symbol': sym, 'klines': klines_slice})
                    factors = result.get('factors', {})
                    
                    # 资金流因子（简化版，不依赖外部helper）
                    fund_factors = extract_fund_flow_factors_simple(klines_slice)
                    factors.update(fund_factors)
                    
                    # 保存（关键：保存target_date）
                    if factors:
                        factor_repo.save_factors(sym, target_date_str, factors)
                        saved_count += 1
                        total_saved += 1
                
                logger.info(f"{sym} 完成，保存 {saved_count} 天")
                    
            except Exception as e:
                logger.error(f"{sym} 失败: {e}")
                failed_symbols.append(sym)
                total_failed += 1
    
    return {
        "success": True,
        "total_symbols": len(symbols),
        "total_saved": total_saved,
        "total_failed": total_failed,
        "failed_symbols": failed_symbols[:20],
        "trading_dates_count": len(trading_dates),
    }


def main():
    """主入口"""
    import argparse
    parser = argparse.ArgumentParser(description='因子历史回填')
    parser.add_argument('--symbols', nargs='+', help='股票代码列表')
    parser.add_argument('--days', type=int, default=350, help='回填天数（自然日）')
    parser.add_argument('--limit', type=int, default=500, help='全市场回填时的股票数上限')
    args = parser.parse_args()
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    
    if args.symbols:
        symbols = args.symbols
    else:
        repo = StockORMRepository()
        stocks = repo.get_all(limit=args.limit)
        symbols = [s['symbol'] for s in stocks]
    
    logger.info(f"开始回填：{start_date} ~ {end_date}，{len(symbols)} 只股票")
    
    result = backfill_factors(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        batch_size=50,
    )
    
    print("\n=== 回填结果 ===")
    print(f"股票数: {result['total_symbols']}")
    print(f"保存: {result['total_saved']} 条")
    print(f"失败: {result['total_failed']}")
    print(f"交易日: {result.get('trading_dates_count', 0)}")


if __name__ == '__main__':
    main()
