"""
W1 K线历史回填脚本
目标：
1. 个股日K回填 ≥250 自然日（≥160 交易日）
2. 指数K线回填（000300/000001/399300）
3. 回填常态化任务配置

执行方式：
    python scripts/w1_backfill_klines.py --mode stocks
    python scripts/w1_backfill_klines.py --mode index
    python scripts/w1_backfill_klines.py --mode all
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import structlog
from datetime import datetime, timedelta
from typing import List, Dict, Set
from application.services.data_backfiller import DataBackfiller
from adapters.outbound.repositories.kline_repository import KlineORMRepository
from adapters.outbound.repositories.stock_pool_repository import StockPoolRepository
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from infrastructure.persistence.orm import get_session

logger = structlog.get_logger(__name__)


class W1KlineBackfiller:
    """W1工单：K线历史回填"""
    
    def __init__(self):
        self.kline_repo = KlineORMRepository()
        self.pool_repo = StockPoolRepository()
        self.sim_repo = SimulationORMRepository()
        self.backfiller = DataBackfiller(kline_repo=self.kline_repo)
        
        # 回填起始日期：保证 ≥250 自然日（约 160+ 交易日）
        self.target_start_date = '2025-06-01'  # 2026-08-25 往前 250+ 天
        self.today = datetime.now().strftime('%Y-%m-%d')
        
    def get_target_symbols(self) -> Set[str]:
        """获取需要回填的股票列表：持仓股 + 池子成员 + 指数成分龙头"""
        symbols = set()
        
        # 1. 持仓股
        try:
            positions = self.sim_repo.list_positions(account_name='agent_virtual')
            for pos in positions:
                symbols.add(pos['symbol'])
            logger.info(f"持仓股: {len(positions)} 只")
        except Exception as e:
            logger.warning(f"获取持仓失败: {e}")
        
        # 2. 各股票池成员
        try:
            pools = self.pool_repo.list_pools()
            for pool in pools:
                pool_id = pool.get('id')
                members = self.pool_repo.get_pool_members(pool_id)
                for member in members:
                    symbols.add(member['symbol'])
            logger.info(f"股票池成员: {len(symbols)} 只（累计）")
        except Exception as e:
            logger.warning(f"获取股票池失败: {e}")
        
        # 3. 如果上述都失败，至少回填几个常见股票
        if not symbols:
            symbols = {
                '600519', '000001', '000002', '600036', '601318',  # 主板
                '300750', '300059', '002594',  # 创业板
            }
            logger.warning(f"使用默认股票列表: {symbols}")
        
        return symbols
    
    def check_data_gap(self, symbol: str) -> List[Dict]:
        """检查单只股票的数据缺失段"""
        try:
            # 查询当前数据的日期范围
            session = self.kline_repo.session
            from infrastructure.persistence.orm.models import DailyKline
            from sqlalchemy import func
            
            result = session.query(
                func.min(DailyKline.trade_date),
                func.max(DailyKline.trade_date),
                func.count()
            ).filter(DailyKline.symbol == symbol).one()
            
            min_date, max_date, count = result
            
            # 如果没有数据或最小日期晚于目标日期，需要回填
            if not min_date or min_date > datetime.strptime(self.target_start_date, '%Y-%m-%d').date():
                return [{
                    'start': self.target_start_date,
                    'end': self.today,
                    'days': (datetime.now() - datetime.strptime(self.target_start_date, '%Y-%m-%d')).days
                }]
            
            # 检查最早日期到目标日期的gap
            if min_date > datetime.strptime(self.target_start_date, '%Y-%m-%d').date():
                return [{
                    'start': self.target_start_date,
                    'end': min_date.strftime('%Y-%m-%d'),
                    'days': (min_date - datetime.strptime(self.target_start_date, '%Y-%m-%d').date()).days
                }]
            
            return []
            
        except Exception as e:
            logger.error(f"检查数据gap失败 {symbol}: {e}")
            # 出错时返回全段回填
            return [{
                'start': self.target_start_date,
                'end': self.today,
                'days': (datetime.now() - datetime.strptime(self.target_start_date, '%Y-%m-%d')).days
            }]
    
    def backfill_stocks(self, symbols: Set[str] = None):
        """回填个股K线"""
        if symbols is None:
            symbols = self.get_target_symbols()
        
        logger.info(f"=" * 60)
        logger.info(f"W1-1 个股K线回填")
        logger.info(f"目标日期: {self.target_start_date} ~ {self.today}")
        logger.info(f"股票数量: {len(symbols)}")
        logger.info(f"=" * 60)
        
        # 构建回填任务
        backfill_tasks = {}
        for symbol in symbols:
            gaps = self.check_data_gap(symbol)
            if gaps:
                backfill_tasks[symbol] = gaps
        
        logger.info(f"需要回填的股票: {len(backfill_tasks)} 只")
        
        if not backfill_tasks:
            logger.info("所有股票数据已完整，无需回填")
            return
        
        # 执行批量回填
        result = self.backfiller.backfill_batch(
            backfill_tasks=backfill_tasks,
            max_workers=8,
            max_retries=3
        )
        
        logger.info(f"=" * 60)
        logger.info(f"回填完成:")
        logger.info(f"  成功: {result['success_count']}/{result['total_stocks']}")
        logger.info(f"  失败: {result['failed_count']}")
        logger.info(f"  回填数据: {result['total_days_filled']} 条")
        logger.info(f"  耗时: {result['elapsed_time']}s")
        
        if result['failed_symbols']:
            logger.warning(f"  失败股票: {result['failed_symbols'][:10]}")
        
        logger.info(f"=" * 60)
    
    def backfill_index(self):
        """回填指数K线"""
        index_symbols = ['000300', '000001', '399300']  # 沪深300、上证指数、深证成指
        
        logger.info(f"=" * 60)
        logger.info(f"W1-2 指数K线回填")
        logger.info(f"目标日期: {self.target_start_date} ~ {self.today}")
        logger.info(f"指数: {index_symbols}")
        logger.info(f"=" * 60)
        
        # 构建回填任务（指数通常需要全量回填）
        backfill_tasks = {}
        for symbol in index_symbols:
            backfill_tasks[symbol] = [{
                'start': self.target_start_date,
                'end': self.today,
                'days': (datetime.now() - datetime.strptime(self.target_start_date, '%Y-%m-%d')).days
            }]
        
        # 执行批量回填
        result = self.backfiller.backfill_batch(
            backfill_tasks=backfill_tasks,
            max_workers=3,  # 指数数据源可能更慢，降低并发
            max_retries=3
        )
        
        logger.info(f"=" * 60)
        logger.info(f"回填完成:")
        logger.info(f"  成功: {result['success_count']}/{result['total_stocks']}")
        logger.info(f"  失败: {result['failed_count']}")
        logger.info(f"  回填数据: {result['total_days_filled']} 条")
        logger.info(f"  耗时: {result['elapsed_time']}s")
        
        if result['failed_symbols']:
            logger.error(f"  失败指数: {result['failed_symbols']}")
        
        logger.info(f"=" * 60)
    
    def verify_backfill(self):
        """验证回填结果（W1验收命令）"""
        logger.info(f"=" * 60)
        logger.info(f"W1 验收：检查回填结果")
        logger.info(f"=" * 60)
        
        # 验收1: 600519 K线数量 ≥ 200
        try:
            df = self.kline_repo.get_range(
                symbol='600519',
                start_date=self.target_start_date,
                end_date=self.today
            )
            count_600519 = len(df)
            logger.info(f"✓ 600519 K线数量: {count_600519} {'✅ PASS' if count_600519 >= 200 else '❌ FAIL'}")
        except Exception as e:
            logger.error(f"✗ 600519 检查失败: {e}")
        
        # 验收2: 指数K线
        for symbol in ['000300', '000001']:
            try:
                df = self.kline_repo.get_range(
                    symbol=symbol,
                    start_date=self.target_start_date,
                    end_date=self.today
                )
                count = len(df)
                logger.info(f"✓ {symbol} K线数量: {count} {'✅ PASS' if count >= 200 else '❌ FAIL'}")
            except Exception as e:
                logger.error(f"✗ {symbol} 检查失败: {e}")
        
        logger.info(f"=" * 60)


def main():
    parser = argparse.ArgumentParser(description='W1 K线历史回填')
    parser.add_argument(
        '--mode',
        choices=['stocks', 'index', 'all', 'verify'],
        default='all',
        help='回填模式: stocks=个股, index=指数, all=全部, verify=验收'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='指定股票代码（可选，不指定则自动获取）'
    )
    
    args = parser.parse_args()
    
    backfiller = W1KlineBackfiller()
    
    if args.mode == 'verify':
        backfiller.verify_backfill()
    elif args.mode == 'stocks':
        symbols = set(args.symbols) if args.symbols else None
        backfiller.backfill_stocks(symbols)
    elif args.mode == 'index':
        backfiller.backfill_index()
    elif args.mode == 'all':
        symbols = set(args.symbols) if args.symbols else None
        backfiller.backfill_stocks(symbols)
        backfiller.backfill_index()
        backfiller.verify_backfill()


if __name__ == '__main__':
    main()
