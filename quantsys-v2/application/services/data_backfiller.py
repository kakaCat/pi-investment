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
    - 指数K线支持（使用 get_index_daily）
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

    def _is_index_symbol(self, symbol: str) -> bool:
        """判断是否为指数代码（使用白名单，避免与股票代码混淆）"""
        # 常见指数白名单（000001既是上证指数也是平安银行，需显式区分）
        index_whitelist = {
            '000001',  # 上证指数
            '000300',  # 沪深300
            '399001',  # 深证成指
            '399300',  # 沪深300(深)
            '399006',  # 创业板指
            '399005',  # 中小板指
            '000016',  # 上证50
            '000905',  # 中证500
            '000852',  # 中证1000
        }
        return symbol in index_whitelist

    def backfill_symbol(
        self,
        symbol: str,
        missing_segments: List[Dict],
        max_retries: int = 3
    ) -> Dict:
        """补充单个股票/指数的缺失数据

        Args:
            symbol: 股票/指数代码
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

        logger.info(f"开始补充{'指数' if self._is_index_symbol(symbol) else '股票'} {symbol}: {len(missing_segments)} 个缺失段")
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
                    # 根据符号类型选择不同的API
                    if self._is_index_symbol(symbol_clean):
                        # 指数使用 get_index_daily（多数据源支持）
                        response = self._fetch_index_klines(
                            symbol_clean, start_date, end_date
                        )
                    else:
                        # 股票使用 get_klines（原有逻辑）
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
                    klines = self._convert_klines(symbol, data, start_date, end_date)
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

    def _fetch_index_klines(self, symbol: str, start_date: str, end_date: str) -> dict:
        """获取指数K线数据（带多数据源 failover）
        
        Args:
            symbol: 裸指数代码（000300）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            
        Returns:
            {'success': bool, 'data': [...], 'source': str}
        """
        # 尝试 market_providers 的 get_index_daily
        # 指数代码需要加前缀：000300 -> sh000300, 399xxx -> szxxxxxx
        if symbol.startswith('000') or symbol.startswith('600'):
            prefixed_symbol = f'sh{symbol}'
        else:
            prefixed_symbol = f'sz{symbol}'
        
        result = self.data_source_manager.get_index_daily(prefixed_symbol)
        
        if result.get('success'):
            # MarketData 对象的 data 属性是 {'records': [...], 'total': n}
            market_data = result.get('data')
            if hasattr(market_data, 'data') and isinstance(market_data.data, dict):
                all_records = market_data.data.get('records', [])
            else:
                all_records = []
            
            # 过滤日期范围
            filtered = self._filter_by_date_range(all_records, start_date, end_date)
            return {
                'success': True,
                'data': filtered,
                'source': result.get('source', 'market_provider')
            }
        
        return result

    def _filter_by_date_range(self, klines: List, start_date: str, end_date: str) -> List:
        """过滤K线数据到指定日期范围"""
        filtered = []
        for kline in klines:
            # 支持 KlineData 对象或字典
            if hasattr(kline, 'date'):
                date_str = kline.date
            else:
                date_str = kline.get('date') or kline.get('trade_date') or kline.get('日期', '')
            
            # 日期可能是 datetime 对象
            if isinstance(date_str, datetime):
                date_str = date_str.strftime('%Y-%m-%d')
            else:
                date_str = str(date_str).split()[0]  # 去掉可能的时间部分
            
            if start_date <= date_str <= end_date:
                filtered.append(kline)
        
        return filtered

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

    def _convert_klines(self, symbol: str, raw_data: List, start_date: str, end_date: str) -> List[Dict]:
        """转换原始K线数据为标准格式

        Args:
            symbol: 股票代码（带后缀）
            raw_data: 原始K线数据（可能是 KlineData 对象列表或字典列表）
            start_date: 开始日期（用于过滤）
            end_date: 结束日期（用于过滤）

        Returns:
            标准格式K线列表
        """
        klines = []

        for item in raw_data:
            try:
                # 支持 KlineData 对象（有属性）或字典（有键）
                if hasattr(item, 'date'):
                    # KlineData 对象
                    trade_date = item.date
                    open_val = item.open
                    high_val = item.high
                    low_val = item.low
                    close_val = item.close
                    volume_val = item.volume
                    amount_val = getattr(item, 'amount', 0)
                    turnover_val = getattr(item, 'turnover_rate', 0)
                else:
                    # 字典格式（兼容旧数据源）
                    trade_date = item.get('date') or item.get('trade_date') or item.get('日期')
                    open_val = item.get('open') or item.get('开盘') or 0
                    high_val = item.get('high') or item.get('最高') or 0
                    low_val = item.get('low') or item.get('最低') or 0
                    close_val = item.get('close') or item.get('收盘') or 0
                    volume_val = item.get('volume') or item.get('成交量') or 0
                    amount_val = item.get('amount') or item.get('成交额') or 0
                    turnover_val = item.get('turnover_rate') or item.get('换手率') or 0

                # 日期格式归一化
                if isinstance(trade_date, datetime):
                    trade_date = trade_date.strftime('%Y-%m-%d')
                else:
                    trade_date = str(trade_date).split()[0]  # 去掉可能的时间部分

                # 日期过滤
                if trade_date < start_date or trade_date > end_date:
                    continue

                kline = {
                    'symbol': symbol,
                    'trade_date': trade_date,
                    'open': float(open_val),
                    'high': float(high_val),
                    'low': float(low_val),
                    'close': float(close_val),
                    'volume': float(volume_val),
                    'amount': float(amount_val),
                    'turnover_rate': float(turnover_val),
                }

                # 基本验证
                if kline['close'] > 0:
                    klines.append(kline)

            except (KeyError, ValueError, TypeError, AttributeError) as e:
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
