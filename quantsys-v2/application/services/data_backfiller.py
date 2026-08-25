"""
数据补充器

从多数据源补充缺失的K线数据，支持重试和并行处理。
"""
import structlog
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from domain.ports.datasource_ports import IDataProviderManager

logger = structlog.get_logger(__name__)


class DataBackfiller:
    """数据补充器

    使用 DataSourceManager 从多数据源获取并补充缺失的K线数据。
    支持：
    - 多数据源自动 failover
    - 指数退避重试
    - 批量并行处理
    - 进度追踪
    """

    def __init__(self, kline_repo=None, data_source_manager=None):
        """初始化数据补充器

        Args:
            kline_repo: K线数据仓库实例
            data_source_manager: 数据源管理器实例
        """
        from domain.ports import IKlineRepository

        self.kline_repo = kline_repo
        # 延迟导入避免顶层依赖
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.data_source_manager = data_source_manager or get_data_provider_manager()

    def backfill_symbol(
        self,
        symbol: str,
        missing_segments: List[Dict],
        max_retries: int = 3
    ) -> Dict:
        """补充单个股票的缺失数据

        Args:
            symbol: 股票代码
            missing_segments: 缺失日期段列表，格式 [{'start': '2026-01-01', 'end': '2026-01-10', 'days': 10}]
            max_retries: 最大重试次数

        Returns:
            补充结果:
            {
                'symbol': '600000.SH',
                'success': True,
                'segments_filled': 2,
                'total_days_filled': 15,
                'failed_segments': [],
                'data_source': 'akshare',
                'elapsed_time': 1.23
            }
        """
        if not missing_segments:
            return {
                'symbol': symbol,
                'success': True,
                'segments_filled': 0,
                'total_days_filled': 0,
                'failed_segments': [],
                'message': 'No missing data'
            }

        logger.info(f"开始补充股票 {symbol}: {len(missing_segments)} 个缺失段")
        start_time = time.time()

        # 去除股票代码后缀（DataSourceManager 使用不带后缀的代码）
        symbol_clean = symbol.split('.')[0] if '.' in symbol else symbol

        segments_filled = 0
        total_days_filled = 0
        failed_segments = []
        data_source_used = None

        for segment in missing_segments:
            start_date = segment['start']
            end_date = segment['end']
            expected_days = segment['days']

            logger.debug(f"补充段 {symbol}: {start_date} ~ {end_date} ({expected_days} 天)")

            # 重试机制
            success = False
            for attempt in range(max_retries):
                try:
                    # 使用 DataSourceManager 获取数据（自动多源 failover）
                    response = self.data_source_manager.get_klines(
                        symbol=symbol_clean,
                        period='daily',
                        start_date=start_date.replace('-', ''),  # YYYYMMDD
                        end_date=end_date.replace('-', '')
                    )

                    if not response.get('success'):
                        logger.warning(f"获取数据失败 (尝试 {attempt+1}/{max_retries}): {response.get('error', 'Unknown')}")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s
                        continue

                    data = response.get('data', [])
                    if not data or len(data) == 0:
                        logger.warning(f"无数据返回: {symbol} {start_date}~{end_date}")
                        break

                    # 转换并保存数据
                    klines = self._convert_klines(symbol, data)
                    if klines:
                        saved_count = self.kline_repo.save_daily_klines(klines)
                        logger.info(f"✓ {symbol}: 保存 {saved_count} 条数据 ({start_date}~{end_date})")

                        segments_filled += 1
                        total_days_filled += saved_count
                        data_source_used = response.get('source', 'unknown')
                        success = True
                        break

                except Exception as e:
                    logger.error(f"补充数据异常 (尝试 {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)

            if not success:
                failed_segments.append({
                    'start': start_date,
                    'end': end_date,
                    'days': expected_days
                })

        elapsed_time = time.time() - start_time
        all_success = len(failed_segments) == 0

        result = {
            'symbol': symbol,
            'success': all_success,
            'segments_filled': segments_filled,
            'total_days_filled': total_days_filled,
            'failed_segments': failed_segments,
            'data_source': data_source_used,
            'elapsed_time': round(elapsed_time, 2)
        }

        if all_success:
            logger.info(f"✓ {symbol}: 补充完成，共 {total_days_filled} 条数据")
        else:
            logger.warning(f"⚠ {symbol}: 部分失败，成功 {segments_filled}/{len(missing_segments)} 段")

        return result

    def backfill_batch(
        self,
        backfill_tasks: Dict[str, List[Dict]],
        max_workers: int = 8,
        max_retries: int = 3
    ) -> Dict:
        """批量补充多个股票的缺失数据

        Args:
            backfill_tasks: 补充任务字典，格式 {symbol: missing_segments}
            max_workers: 并行工作线程数
            max_retries: 最大重试次数

        Returns:
            补充汇总结果:
            {
                'total_stocks': 100,
                'success_count': 95,
                'failed_count': 5,
                'total_days_filled': 2850,
                'elapsed_time': 45.67,
                'failed_symbols': ['600599.SH', '000638.SZ'],
                'results': {symbol: result_dict, ...}
            }
        """
        total_stocks = len(backfill_tasks)
        logger.info(f"开始批量补充: {total_stocks} 只股票")
        start_time = time.time()

        results = {}
        success_count = 0
        failed_count = 0
        total_days_filled = 0
        failed_symbols = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(
                    self.backfill_symbol,
                    symbol,
                    segments,
                    max_retries
                ): symbol
                for symbol, segments in backfill_tasks.items()
            }

            # 处理完成的任务
            completed = 0
            for future in as_completed(futures):
                symbol = futures[future]
                completed += 1

                try:
                    result = future.result()
                    results[symbol] = result

                    if result['success']:
                        success_count += 1
                        total_days_filled += result['total_days_filled']
                    else:
                        failed_count += 1
                        failed_symbols.append(symbol)

                    # 每处理 10% 打印进度
                    if completed % max(1, total_stocks // 10) == 0:
                        progress = completed / total_stocks * 100
                        logger.info(f"进度: {completed}/{total_stocks} ({progress:.1f}%) - "
                                  f"成功: {success_count}, 失败: {failed_count}")

                except Exception as e:
                    logger.error(f"处理股票 {symbol} 失败: {e}")
                    failed_count += 1
                    failed_symbols.append(symbol)
                    results[symbol] = {
                        'symbol': symbol,
                        'success': False,
                        'error': str(e)
                    }

        elapsed_time = time.time() - start_time

        summary = {
            'total_stocks': total_stocks,
            'success_count': success_count,
            'failed_count': failed_count,
            'total_days_filled': total_days_filled,
            'elapsed_time': round(elapsed_time, 2),
            'failed_symbols': failed_symbols,
            'results': results
        }

        logger.info(f"批量补充完成: {success_count}/{total_stocks} 成功, "
                   f"共补充 {total_days_filled} 条数据, 耗时 {elapsed_time:.2f}s")

        return summary

    def retry_failed(
        self,
        failed_tasks: Dict[str, List[Dict]],
        max_retries: int = 5
    ) -> Dict:
        """重试失败的补充任务

        Args:
            failed_tasks: 失败任务字典，格式与 backfill_batch 相同
            max_retries: 最大重试次数（更多次数）

        Returns:
            重试结果汇总
        """
        logger.info(f"重试失败任务: {len(failed_tasks)} 只股票")

        # 单线程重试，降低并发压力
        return self.backfill_batch(
            backfill_tasks=failed_tasks,
            max_workers=2,
            max_retries=max_retries
        )

    def _convert_klines(self, symbol: str, raw_data: List[Dict]) -> List[Dict]:
        """转换原始K线数据为标准格式

        Args:
            symbol: 股票代码（带后缀）
            raw_data: 原始K线数据

        Returns:
            标准格式K线列表
        """
        klines = []

        for item in raw_data:
            try:
                # 统一字段名（兼容不同数据源）
                trade_date = item.get('date') or item.get('trade_date') or item.get('日期')

                kline = {
                    'symbol': symbol,
                    'trade_date': trade_date,
                    'open': float(item.get('open') or item.get('开盘') or 0),
                    'high': float(item.get('high') or item.get('最高') or 0),
                    'low': float(item.get('low') or item.get('最低') or 0),
                    'close': float(item.get('close') or item.get('收盘') or 0),
                    'volume': float(item.get('volume') or item.get('成交量') or 0),
                    'amount': float(item.get('amount') or item.get('成交额') or 0),
                    'turnover_rate': float(item.get('turnover_rate') or item.get('换手率') or 0),
                }

                # 基本验证
                if kline['close'] > 0:
                    klines.append(kline)

            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"跳过无效数据: {e}")
                continue

        return klines

    def estimate_time(
        self,
        total_stocks: int,
        avg_segments_per_stock: int = 2,
        max_workers: int = 8
    ) -> float:
        """估算补充时间

        Args:
            total_stocks: 股票数量
            avg_segments_per_stock: 每只股票平均缺失段数
            max_workers: 并行线程数

        Returns:
            估算时间（秒）
        """
        # 假设每个段的平均获取时间为 2 秒
        avg_time_per_segment = 2.0
        total_segments = total_stocks * avg_segments_per_stock
        estimated_time = (total_segments * avg_time_per_segment) / max_workers

        return estimated_time
