"""
资金流数据更新Job - 全市场资金流向每日采集

数据源：东方财富 push2 clist 全市场分页扫描（约 60 页请求覆盖全部 A 股）
落库：quant.stock_fund_flow（单位：万元）

调度配置（quant.scheduler_task_configs）：
    task_name: fund_flow_update
    command:   infrastructure.jobs.fund_flow_update_job.execute
    cron:      30 15 * * 1-5（交易日收盘后）

也可手动执行：
    python -m infrastructure.jobs.fund_flow_update_job [--date 2026-07-28]
"""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


def execute(**params):
    """
    采集全市场资金流向并落库

    Args:
        **params:
            - date: 交易日期 YYYY-MM-DD（默认今天）

    Returns:
        dict: 执行结果
    """
    from adapters.outbound.datasources.fund_flow_source import (
        EastMoneyFundFlowSource, SinaFundFlowSource,
    )
    from adapters.outbound.repositories import FundFlowORMRepository

    trade_date = params.get('date') or datetime.now().strftime('%Y-%m-%d')

    logger.info("=" * 70)
    logger.info(f"资金流数据更新任务开始 (trade_date={trade_date})")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    # 主源东财（4 档细分），被封时降级新浪（仅主力/小单两档）。
    # 东财 WAF 自 2026-07-22 起对本机房 IP 有长时间封锁记录。
    records = []
    used_source = None
    errors = []
    for source in (EastMoneyFundFlowSource(), SinaFundFlowSource()):
        try:
            logger.info(f"尝试数据源: {source.name}")
            records = source.fetch_market_wide_flow()
            if records:
                used_source = source.name
                break
            errors.append(f"{source.name}: 返回 0 条")
        except Exception as e:
            errors.append(f"{source.name}: {type(e).__name__} {str(e)[:100]}")
            logger.warning(f"数据源 {source.name} 失败: {e}")

    if not records:
        # 显式失败：非交易日/数据源全挂时不写库、不静默成功
        logger.error(f"全市场资金流采集失败: {'; '.join(errors)}")
        return {'success': False, 'trade_date': trade_date, 'records': 0,
                'error': '; '.join(errors)}

    for r in records:
        r['trade_date'] = trade_date

    repo = FundFlowORMRepository()
    count = repo.batch_upsert(records)

    logger.info(f"✅ 资金流数据落库完成: {count}/{len(records)} 条 "
                f"(trade_date={trade_date}, source={used_source})")
    return {'success': count > 0, 'trade_date': trade_date,
            'records': count, 'source': used_source}


if __name__ == '__main__':
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    parser = argparse.ArgumentParser(description='全市场资金流向采集')
    parser.add_argument('--date', help='交易日期 YYYY-MM-DD（默认今天）')
    args = parser.parse_args()

    result = execute(**({'date': args.date} if args.date else {}))
    sys.exit(0 if result.get('success') else 1)
