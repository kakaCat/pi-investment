"""
筹码分布增量更新 Job — 全市场每日增量

调度配置（quant.scheduler_task_configs，见 011_seed_chip_distribution_job.sql）：
    task_name: chip_distribution_update
    command:   infrastructure.jobs.chip_distribution_update_job.execute
    cron:      30 18 * * 0-4（kline_update 17:40 之后）

手动执行：
    python -m infrastructure.jobs.chip_distribution_update_job [--limit 100]
    python -m infrastructure.jobs.chip_distribution_update_job --symbol 600519.SH
"""
import structlog
logger = structlog.get_logger(__name__)
import os
import logging
import sys
from pathlib import Path


logger = logging.getLogger(__name__)


def execute(**params):
    """
    Args:
        **params:
            - limit: 最多处理多少只（调试用）
            - symbol: 只更新单只股票（调试用）

    Returns:
        dict: {pending, updated, failed, days_applied}
    """
    from adapters.outbound.repositories.chip_repository import ChipRepository
    from domain.chip_distribution.service import ChipDistributionService

    svc = ChipDistributionService(ChipRepository())

    symbol = params.get('symbol')
    if symbol:
        result = svc.update_symbol(symbol)
        logger.info(f"单票更新: {result}")
        return result

    return svc.daily_update(limit=params.get('limit'))


if __name__ == '__main__':
    import argparse
    import json
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--symbol', type=str, default=None)
    args = parser.parse_args()
    params = {k: v for k, v in vars(args).items() if v is not None}
    logger.info(json.dumps(execute(**params), ensure_ascii=False, default=str))
