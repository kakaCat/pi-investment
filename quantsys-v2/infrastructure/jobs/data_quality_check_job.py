"""
数据质量检查Job - 定时任务执行逻辑

每日检查：
1. 检测数据质量问题（缺失、重复、异常）
2. 补充缺失数据（可选）
3. 生成质量报告
"""
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

# 添加项目路径

from application.services.data_quality_service import DataQualityService

logger = logging.getLogger(__name__)


class DataQualityCheckJob:
    """数据质量检查Job类 - 供调度器使用"""

    def __init__(self):
        """初始化Job"""
        self.service = None

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行数据质量检查

        Args:
            params: 任务参数
                - check_days: 检查最近N天的数据（默认30天）
                - auto_backfill: 是否自动补充缺失数据（默认False）
                - symbols_limit: 检查的股票数量限制（None=全部）
                - include_report: 是否生成详细报告（默认False）

        Returns:
            执行结果字典
        """
        return daily_data_quality_check(**params)


def daily_data_quality_check(**params):
    """
    每日数据质量检查

    Args:
        **params: 任务参数
            - check_days: 检查最近N天的数据（默认30天）
            - auto_backfill: 是否自动补充缺失数据（默认False）
            - symbols_limit: 检查的股票数量限制（None=全部）
            - include_report: 是否生成详细报告（默认False）

    Returns:
        dict: 执行结果
    """
    logger.info("="*70)
    logger.info("每日数据质量检查开始")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)

    try:
        # 参数解析
        check_days = params.get('check_days', 30)
        auto_backfill = params.get('auto_backfill', False)
        symbols_limit = params.get('symbols_limit', None)
        include_report = params.get('include_report', False)

        # 计算日期范围
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=check_days)).strftime('%Y-%m-%d')

        logger.info(f"检查参数:")
        logger.info(f"  日期范围: {start_date} ~ {end_date}")
        logger.info(f"  股票限制: {symbols_limit or '全部'}")
        logger.info(f"  自动补充: {auto_backfill}")

        # 初始化服务
        logger.info("\n初始化数据质量服务...")
        service = DataQualityService()

        # 获取股票池
        if symbols_limit:
            symbols = service._get_hot_stocks(limit=symbols_limit)
        else:
            symbols = service._get_hot_stocks(limit=None)

        logger.info(f"股票池: {len(symbols)} 只股票")

        # 1. 检查数据质量
        logger.info("\n1. 检查数据质量...")
        quality_result = service.check_data_quality(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            include_report=include_report
        )

        if not quality_result['success']:
            raise Exception(f"质量检查失败: {quality_result.get('error')}")

        summary = quality_result['summary']
        logger.info(f"\n质量检查结果:")
        logger.info(f"  总股票数: {summary['total_stocks']}")
        logger.info(f"  有问题股票: {summary['stocks_with_issues']}")
        logger.info(f"  缺失天数: {summary['total_missing_days']}")
        logger.info(f"  平均覆盖率: {summary['avg_coverage_rate']:.2f}%")
        logger.info(f"  质量评分: {summary['data_quality_score']:.2f}")

        # 2. 自动补充（如果启用）
        backfill_result = None
        if auto_backfill and summary['stocks_with_issues'] > 0:
            logger.info("\n2. 自动补充缺失数据...")

            # 提取有问题的股票
            symbols_with_issues = [
                item['symbol']
                for item in quality_result['stocks_with_issues']
                if item['missing_days_count'] > 0
            ]

            if symbols_with_issues:
                logger.info(f"  补充股票: {len(symbols_with_issues)} 只")
                backfill_result = service.backfill_missing_data(
                    symbols=symbols_with_issues,
                    start_date=start_date,
                    end_date=end_date,
                    mode='auto',
                    max_workers=8
                )

                if backfill_result['success']:
                    logger.info(f"  补充成功: {backfill_result['summary']['success_count']} 只")
                    logger.info(f"  补充天数: {backfill_result['summary']['total_days_filled']}")
                else:
                    logger.warning(f"  补充失败: {backfill_result.get('error')}")
            else:
                logger.info("  无需补充（无缺失数据）")

        # 构建结果（符合调度器期望的格式）
        result = {
            'success': True,  # 调度器期望的键名
            'timestamp': datetime.now().isoformat(),
            'check_period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': check_days
            },
            'check_summary': summary,  # 调度器期望的键名
            'stocks_with_issues_count': summary['stocks_with_issues'],
            'data_quality_score': summary['data_quality_score'],
            'message': '数据质量检查完成',
            'backfill_executed': False  # 默认值
        }

        if backfill_result:
            result['backfill_summary'] = backfill_result.get('summary')
            result['backfill_executed'] = True

        if include_report and 'report_url' in quality_result:
            result['report_url'] = quality_result['report_url']

        logger.info("\n执行结果:")
        logger.info(f"  状态: 成功")
        logger.info(f"  质量评分: {summary['data_quality_score']:.2f}")
        logger.info(f"  问题股票: {summary['stocks_with_issues']}/{summary['total_stocks']}")

        logger.info("="*70)
        logger.info("✅ 每日数据质量检查完成")
        logger.info("="*70)

        return result

    except Exception as e:
        logger.error(f"❌ 每日数据质量检查失败: {e}")
        import traceback
        traceback.print_exc()

        return {
            'success': False,  # 调度器期望的键名
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'message': '数据质量检查失败'
        }


# Job注册点 - scheduler会调用这个函数
def execute(**params):
    """Scheduler调用的入口函数"""
    return daily_data_quality_check(**params)


if __name__ == '__main__':
    # 测试执行
    result = daily_data_quality_check(
        check_days=7,
        auto_backfill=False,
        symbols_limit=10
    )
    print(f"\n执行结果: {result}")
