"""
数据质量管理服务

统一的数据质量管理入口，整合检测、补充、验证功能。
"""
import structlog
from typing import List, Dict, Optional

logger = structlog.get_logger(__name__)


class DataQualityService:
    """数据质量管理服务

    提供完整的数据质量管理功能：
    - 检查数据质量
    - 检测缺失数据
    - 补充缺失数据
    - 验证数据质量
    - 生成质量报告

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        kline_repo=None,
        calendar=None,
        gap_detector=None,
        backfiller=None,
        validator=None,
    ):
        """初始化数据质量服务

        Args:
            kline_repo: K线仓库（可选）
            calendar: 交易日历服务（可选）
            gap_detector: 数据缺口检测器（可选）
            backfiller: 数据回填器（可选）
            validator: 数据验证器（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        from domain.ports import IKlineRepository
        from application.services.trading_calendar_service import TradingCalendarService
        from application.services.data_gap_detector import DataGapDetector
        from application.services.data_backfiller import DataBackfiller
        from application.services.data_validator import DataValidator

        self.kline_repo = kline_repo
        self.calendar = calendar or TradingCalendarService(self.kline_repo)
        self.gap_detector = gap_detector or DataGapDetector(self.kline_repo, self.calendar)
        self.backfiller = backfiller or DataBackfiller(self.kline_repo)
        self.validator = validator or DataValidator(self.kline_repo)

    def check_data_quality(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_report: bool = False
    ) -> Dict:
        """检查数据质量

        Args:
            symbols: 股票代码列表（可选，默认热门股票池）
            start_date: 开始日期（可选，默认最近30天）
            end_date: 结束日期（可选，默认今天）
            include_report: 是否生成详细报告

        Returns:
            质量检查结果:
            {
                'success': True,
                'summary': {
                    'total_stocks': 100,
                    'stocks_with_issues': 15,
                    'total_missing_days': 450,
                    'avg_coverage_rate': 98.5,
                    'data_quality_score': 95.5
                },
                'stocks_with_issues': [
                    {
                        'symbol': '600000.SH',
                        'missing_days_count': 30,
                        'coverage_rate': 88.0,
                        'quality_score': 85.5,
                        'has_duplicates': False,
                        'has_anomalies': True
                    }
                ],
                'report_url': '/api/data-quality/reports/20260604_143022'  # if include_report
            }
        """
        try:
            # 1. 参数处理
            symbols = symbols or self._get_hot_stocks()
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (
                datetime.now() - timedelta(days=30)
            ).strftime('%Y-%m-%d')

            logger.info(f"检查数据质量: {len(symbols)} 只股票, {start_date} ~ {end_date}")

            # 2. 检测数据缺失
            gaps = self.gap_detector.detect_gaps_batch(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                only_with_gaps=False  # 获取所有股票信息
            )

            # 3. 检测其他问题（重复、异常）
            stocks_with_issues = []
            total_issues = 0

            for symbol, gap_info in gaps.items():
                # 检测重复数据
                dup_info = self.validator.detect_duplicates(symbol, start_date, end_date)

                # 检测异常值
                anomaly_info = self.validator.detect_anomalies(symbol, start_date, end_date)

                # 计算质量评分
                quality_score = self.validator.get_data_quality_score(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    coverage_rate=gap_info['coverage_rate']
                )

                # 判断是否有问题
                has_issues = (
                    gap_info['missing_days_count'] > 0 or
                    dup_info['has_duplicates'] or
                    anomaly_info['has_anomalies']
                )

                if has_issues:
                    total_issues += 1
                    stocks_with_issues.append({
                        'symbol': symbol,
                        'missing_days_count': gap_info['missing_days_count'],
                        'coverage_rate': gap_info['coverage_rate'],
                        'quality_score': quality_score,
                        'has_duplicates': dup_info['has_duplicates'],
                        'duplicate_count': dup_info['duplicate_count'],
                        'has_anomalies': anomaly_info['has_anomalies'],
                        'anomaly_count': anomaly_info['total_anomalies']
                    })

            # 4. 计算汇总统计
            gap_summary = self.gap_detector.get_gap_summary(gaps)
            avg_quality_score = sum(
                self.validator.get_data_quality_score(
                    s, start_date, end_date, gaps[s]['coverage_rate']
                ) for s in symbols
            ) / len(symbols) if symbols else 100.0

            summary = {
                'total_stocks': len(symbols),
                'stocks_with_issues': total_issues,
                'total_missing_days': gap_summary['total_missing_days'],
                'avg_coverage_rate': gap_summary['avg_coverage_rate'],
                'data_quality_score': round(avg_quality_score, 2)
            }

            # 5. 生成报告（可选）
            report_url = None
            if include_report:
                report_id = datetime.now().strftime('%Y%m%d_%H%M%S')
                report_data = {
                    'report_id': report_id,
                    'period': {'start_date': start_date, 'end_date': end_date},
                    'summary': summary,
                    'stocks_with_issues': stocks_with_issues,
                    'gaps': gaps
                }
                # TODO: 保存报告到数据库
                report_url = f'/api/data-quality/reports/{report_id}'

            result = {
                'success': True,
                'summary': summary,
                'stocks_with_issues': stocks_with_issues[:50],  # 最多返回50个
                'timestamp': datetime.now().isoformat()
            }

            if report_url:
                result['report_url'] = report_url

            logger.info(f"质量检查完成: {total_issues}/{len(symbols)} 只股票有问题, "
                       f"质量评分 {avg_quality_score:.2f}")

            return result

        except Exception as e:
            logger.error(f"检查数据质量失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def detect_missing_data(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """检测缺失数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            缺失检测结果
        """
        try:
            symbols = symbols or self._get_hot_stocks()
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (
                datetime.now() - timedelta(days=30)
            ).strftime('%Y-%m-%d')

            logger.info(f"检测缺失数据: {len(symbols)} 只股票")

            gaps = self.gap_detector.detect_gaps_batch(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                only_with_gaps=True
            )

            summary = self.gap_detector.get_gap_summary(gaps)

            return {
                'success': True,
                'summary': summary,
                'gaps': gaps,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"检测缺失数据失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def backfill_missing_data(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mode: str = 'auto',
        max_workers: int = 8
    ) -> Dict:
        """补充缺失数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            mode: 补充模式 ('auto' = 仅补充缺失, 'force' = 强制重新获取)
            max_workers: 并行线程数

        Returns:
            补充结果
        """
        try:
            symbols = symbols or self._get_hot_stocks()
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (
                datetime.now() - timedelta(days=30)
            ).strftime('%Y-%m-%d')

            logger.info(f"补充缺失数据: {len(symbols)} 只股票, mode={mode}")

            # 1. 检测缺失数据
            if mode == 'auto':
                gaps = self.gap_detector.detect_gaps_batch(
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    only_with_gaps=True
                )

                if not gaps:
                    return {
                        'success': True,
                        'message': 'No missing data found',
                        'summary': {
                            'total_stocks': len(symbols),
                            'success_count': 0,
                            'failed_count': 0,
                            'total_days_filled': 0
                        }
                    }

                # 构建补充任务
                backfill_tasks = {
                    symbol: gap['missing_segments']
                    for symbol, gap in gaps.items()
                }

            else:  # mode == 'force'
                # 强制模式：补充整个日期范围
                backfill_tasks = {
                    symbol: [{'start': start_date, 'end': end_date, 'days': 0}]
                    for symbol in symbols
                }

            # 2. 执行补充
            logger.info(f"开始补充: {len(backfill_tasks)} 只股票")
            result = self.backfiller.backfill_batch(
                backfill_tasks=backfill_tasks,
                max_workers=max_workers
            )

            # 3. 重试失败的任务（最多1次）
            if result['failed_count'] > 0 and result['failed_symbols']:
                logger.info(f"重试失败任务: {result['failed_count']} 只股票")
                failed_tasks = {
                    symbol: backfill_tasks[symbol]
                    for symbol in result['failed_symbols']
                    if symbol in backfill_tasks
                }

                retry_result = self.backfiller.retry_failed(failed_tasks, max_retries=5)

                # 合并结果
                result['success_count'] += retry_result['success_count']
                result['failed_count'] = retry_result['failed_count']
                result['total_days_filled'] += retry_result['total_days_filled']
                result['failed_symbols'] = retry_result['failed_symbols']

            return {
                'success': result['failed_count'] == 0,
                'summary': {
                    'total_stocks': result['total_stocks'],
                    'success_count': result['success_count'],
                    'failed_count': result['failed_count'],
                    'total_days_filled': result['total_days_filled'],
                    'elapsed_time': result['elapsed_time']
                },
                'failed_symbols': result['failed_symbols'],
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"补充缺失数据失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def validate_data(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """验证数据质量

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            验证结果
        """
        try:
            symbols = symbols or self._get_hot_stocks()
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (
                datetime.now() - timedelta(days=30)
            ).strftime('%Y-%m-%d')

            logger.info(f"验证数据质量: {len(symbols)} 只股票")

            validation_results = []

            for symbol in symbols:
                # 获取K线数据
                klines = self.kline_repo.get_daily_klines(symbol, start_date, end_date)

                # 验证K线数据
                validation = self.validator.validate_klines(klines)

                # 检测重复和异常
                duplicates = self.validator.detect_duplicates(symbol, start_date, end_date)
                anomalies = self.validator.detect_anomalies(symbol, start_date, end_date)

                if not validation['valid'] or duplicates['has_duplicates'] or anomalies['has_anomalies']:
                    validation_results.append({
                        'symbol': symbol,
                        'valid': validation['valid'],
                        'total_records': validation['total_records'],
                        'invalid_records': validation['invalid_records'],
                        'validation_errors': validation['errors'][:5],  # 最多5个
                        'has_duplicates': duplicates['has_duplicates'],
                        'duplicate_count': duplicates['duplicate_count'],
                        'has_anomalies': anomalies['has_anomalies'],
                        'anomaly_count': anomalies['total_anomalies']
                    })

            return {
                'success': True,
                'summary': {
                    'total_stocks': len(symbols),
                    'stocks_with_issues': len(validation_results)
                },
                'validation_results': validation_results,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"验证数据质量失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_hot_stocks(self, limit: int = None) -> List[str]:
        """获取股票池（默认：所有有数据的股票）

        Args:
            limit: 返回数量限制（None=全部，默认None）

        Returns:
            股票代码列表
        """
        try:
            from sqlalchemy import func, desc
            from infrastructure.persistence.orm.models import DailyKline

            # 使用 ORM session 而不是 cursor
            session = self.kline_repo.session

            if limit is None:
                # 获取所有股票
                query = session.query(DailyKline.symbol)\
                    .distinct()\
                    .order_by(DailyKline.symbol)
            else:
                # 获取指定数量的热门股票（按最近30天数据量排序）
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=30)

                query = session.query(
                    DailyKline.symbol,
                    func.count(DailyKline.symbol).label('cnt')
                )\
                .filter(DailyKline.trade_date >= cutoff_date)\
                .group_by(DailyKline.symbol)\
                .order_by(desc('cnt'))\
                .limit(limit)

            results = query.all()

            # 提取 symbol
            if results:
                if hasattr(results[0], 'symbol'):
                    symbols = [row.symbol for row in results]
                else:
                    symbols = [row[0] for row in results]
            else:
                symbols = []

            # 如果数据库为空，返回示例股票
            if not symbols:
                symbols = [
                    '600519', '000858', '600036', '601318', '600900',
                    '600276', '601888', '600887', '000333', '002475'
                ]
                logger.warning("数据库中无K线数据，使用默认股票池")

            logger.info(f"获取股票池: {len(symbols)} 只股票" +
                       (f" (限制: {limit})" if limit else " (全部)"))
            return symbols

        except Exception as e:
            logger.error(f"获取股票池失败: {e}", exc_info=True)
            # 返回默认股票池而不是空列表
            return [
                '600519', '000858', '600036', '601318', '600900',
                '600276', '601888', '600887', '000333', '002475'
            ]
