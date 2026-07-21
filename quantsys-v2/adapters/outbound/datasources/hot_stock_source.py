"""Hot Stock Data Source - 热搜股票数据源

支持多个数据源获取热搜股票排行，自动 failover：
1. 雪球关注排行 (primary, 数据最全)
2. 雪球交易排行 (fallback)
3. 东方财富热搜 (fallback, 支持 A股/港股/美股，但当前不稳定)
"""

import logging
import time
import threading
from typing import Dict, Any, List
from datetime import datetime
from adapters.outbound.datasources.base import DataSourceResponse

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """超时异常"""
    pass


def with_timeout(seconds):
    """线程安全的超时装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = [TimeoutError(f"{func.__name__} 超时")]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    result[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                logger.warning(f"{func.__name__} 超时 ({seconds}秒)")
                raise TimeoutError(f"{func.__name__} 超时")

            if isinstance(result[0], Exception):
                raise result[0]

            return result[0]
        return wrapper
    return decorator


class HotStockSource:
    """热搜股票数据源（多源支持 + 缓存）"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 初始化缓存
        from infrastructure.utils.simple_cache import SimpleCache
        self.cache = SimpleCache()

    @with_timeout(10)  # 10秒超时
    def get_hot_stocks_xueqiu_follow(self) -> DataSourceResponse:
        """
        从雪球获取关注排行（最佳数据源）

        Returns:
            DataSourceResponse
        """
        try:
            import akshare as ak

            self.logger.info(f"[雪球关注] 获取热搜股票...")

            # 雪球关注排行
            df = ak.stock_hot_follow_xq()

            if df is None or df.empty:
                return DataSourceResponse.error_response(
                    '暂无热搜股票数据',
                    metadata={'source': 'xueqiu_follow'}
                )

            self.logger.info(f"[雪球关注] 获取成功: {len(df)} 条")

            # 标准化数据格式
            df_renamed = df.rename(columns={
                '股票代码': '代码',
                '股票简称': '股票名称',
                '关注': '热度',
                '最新价': '最新价'
            })

            return DataSourceResponse.success_response(
                data={
                    'market': 'A股',
                    'stocks': df_renamed.head(100).to_dict('records'),
                    'total': len(df_renamed),
                    'update_time': datetime.now().isoformat(),
                    'ranking_type': '关注排行'
                },
                metadata={'source': 'xueqiu_follow'}
            )

        except Exception as e:
            self.logger.warning(f"[雪球关注] 获取失败: {e}")
            return DataSourceResponse.error_response(
                f'雪球关注排行失败: {str(e)}',
                metadata={'source': 'xueqiu_follow'}
            )

    @with_timeout(10)  # 10秒超时
    def get_hot_stocks_xueqiu_deal(self) -> DataSourceResponse:
        """
        从雪球获取交易排行（备用数据源）

        Returns:
            DataSourceResponse
        """
        try:
            import akshare as ak

            self.logger.info(f"[雪球交易] 获取热搜股票...")

            # 雪球交易排行
            df = ak.stock_hot_deal_xq()

            if df is None or df.empty:
                return DataSourceResponse.error_response(
                    '暂无热搜股票数据',
                    metadata={'source': 'xueqiu_deal'}
                )

            self.logger.info(f"[雪球交易] 获取成功: {len(df)} 条")

            # 标准化数据格式
            df_renamed = df.rename(columns={
                '股票代码': '代码',
                '股票简称': '股票名称',
                '关注': '热度',
                '最新价': '最新价'
            })

            return DataSourceResponse.success_response(
                data={
                    'market': 'A股',
                    'stocks': df_renamed.head(100).to_dict('records'),
                    'total': len(df_renamed),
                    'update_time': datetime.now().isoformat(),
                    'ranking_type': '交易排行'
                },
                metadata={'source': 'xueqiu_deal'}
            )

        except Exception as e:
            self.logger.warning(f"[雪球交易] 获取失败: {e}")
            return DataSourceResponse.error_response(
                f'雪球交易排行失败: {str(e)}',
                metadata={'source': 'xueqiu_deal'}
            )
        """
        从东方财富获取热搜股票（主要数据源，带重试）

        Args:
            market: 市场类型（A股/港股/美股）

        Returns:
            DataSourceResponse
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                import akshare as ak

                self.logger.info(f"[东方财富] 尝试 {attempt}/{self.max_retries}: market={market}")

                # 根据市场类型选择不同的 API
                if market == "A股":
                    df = ak.stock_hot_rank_em()
                elif market == "港股":
                    df = ak.stock_hot_rank_em(symbol="港股")
                elif market == "美股":
                    df = ak.stock_hot_rank_em(symbol="美股")
                else:
                    return DataSourceResponse.error_response(
                        f'不支持的市场类型: {market}',
                        metadata={'source': 'eastmoney'}
                    )

                if df is None or df.empty:
                    if attempt < self.max_retries:
                        self.logger.warning(f"[东方财富] 数据为空，{self.retry_delay}秒后重试...")
                        time.sleep(self.retry_delay)
                        continue

                    return DataSourceResponse.error_response(
                        '暂无热搜股票数据',
                        metadata={'source': 'eastmoney'}
                    )

                self.logger.info(f"[东方财富] 获取成功: {len(df)} 条")

                return DataSourceResponse.success_response(
                    data={
                        'market': market,
                        'stocks': df.head(50).to_dict('records'),
                        'total': len(df),
                        'update_time': datetime.now().isoformat()
                    },
                    metadata={'source': 'eastmoney', 'attempts': attempt}
                )

            except Exception as e:
                self.logger.warning(f"[东方财富] 尝试 {attempt} 失败: {e}")

                if attempt < self.max_retries:
                    self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    return DataSourceResponse.error_response(
                        f'东方财富数据源失败（已重试{self.max_retries}次）: {str(e)}',
                        metadata={'source': 'eastmoney', 'attempts': attempt}
                    )

        return DataSourceResponse.error_response(
            f'东方财富数据源失败（已重试{self.max_retries}次）',
            metadata={'source': 'eastmoney'}
        )

    def get_hot_stocks_eastmoney(self, market: str = "A股") -> DataSourceResponse:
        """
        从东方财富获取热搜股票（备用数据源，当前不稳定）

        Args:
            market: 市场类型（A股/港股/美股）

        Returns:
            DataSourceResponse
        """
        try:
            import akshare as ak

            self.logger.info(f"[东方财富] 获取热搜股票: market={market}")

            # 根据市场类型选择不同的 API
            if market == "A股":
                df = ak.stock_hot_rank_em()
            elif market == "港股":
                df = ak.stock_hot_rank_em(symbol="港股")
            elif market == "美股":
                df = ak.stock_hot_rank_em(symbol="美股")
            else:
                return DataSourceResponse.error_response(
                    f'不支持的市场类型: {market}',
                    metadata={'source': 'eastmoney'}
                )

            if df is None or df.empty:
                return DataSourceResponse.error_response(
                    '暂无热搜股票数据',
                    metadata={'source': 'eastmoney'}
                )

            self.logger.info(f"[东方财富] 获取成功: {len(df)} 条")

            return DataSourceResponse.success_response(
                data={
                    'market': market,
                    'stocks': df.head(50).to_dict('records'),
                    'total': len(df),
                    'update_time': datetime.now().isoformat(),
                    'ranking_type': '热搜排行'
                },
                metadata={'source': 'eastmoney'}
            )

        except Exception as e:
            self.logger.warning(f"[东方财富] 获取失败: {e}")
            return DataSourceResponse.error_response(
                f'东方财富数据源失败: {str(e)}',
                metadata={'source': 'eastmoney'}
            )

    def get_hot_stocks_with_fallback(self, market: str = "A股", mode: str = "first") -> Dict[str, Any]:
        """
        使用多数据源获取热搜股票（缓存优先）

        支持两种模式：
        - first: 返回第一个成功的数据源（failover）
        - all: 返回所有成功的数据源（聚合）

        Args:
            market: 市场类型（A股/港股/美股）
            mode: 返回模式（first/all）

        Returns:
            标准响应格式字典
        """
        cache_key = f"hot_stocks_{market}_{mode}"

        # 1. 优先返回缓存（30分钟有效期）
        cached_data = self.cache.get(cache_key, max_age_seconds=1800)
        if cached_data:
            self.logger.info(f"热搜股票使用缓存: {market}")
            return cached_data

        # 2. 缓存未命中，尝试从数据源获取
        # 定义数据源优先级
        sources = [
            ('雪球关注排行', self.get_hot_stocks_xueqiu_follow, ['A股']),
            ('雪球交易排行', self.get_hot_stocks_xueqiu_deal, ['A股']),
            ('东方财富', lambda: self.get_hot_stocks_eastmoney(market), ['A股', '港股', '美股']),
        ]

        successful_results = []
        errors = []

        for source_name, source_func, supported_markets in sources:
            # 检查数据源是否支持当前市场
            if market not in supported_markets:
                self.logger.debug(f"[{source_name}] 不支持 {market} 市场，跳过")
                continue

            try:
                self.logger.info(f"尝试数据源: {source_name}")
                response = source_func()

                if response.success:
                    self.logger.info(f"✓ 数据源 [{source_name}] 获取成功")

                    result = {
                        'source': response.metadata.get('source', source_name),
                        'source_name': source_name,
                        'data': response.data
                    }
                    successful_results.append(result)

                    # first 模式：返回第一个成功的
                    if mode == "first":
                        result_data = {
                            'success': True,
                            'data': response.data,
                            'source': response.metadata.get('source', source_name),
                            'mode': 'first'
                        }
                        # 保存到缓存
                        self.cache.set(cache_key, result_data)
                        return result_data
                else:
                    error_msg = f"[{source_name}] {response.error}"
                    errors.append(error_msg)
                    self.logger.warning(error_msg)

            except Exception as e:
                error_msg = f"[{source_name}] 异常: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg, exc_info=True)

        # all 模式：返回所有成功的数据源
        if mode == "all" and successful_results:
            result_data = {
                'success': True,
                'data': {
                    'sources': successful_results,
                    'total_sources': len(successful_results),
                    'market': market
                },
                'mode': 'all',
                'source_count': len(successful_results)
            }
            # 保存到缓存
            self.cache.set(cache_key, result_data)
            return result_data

        # 3. 所有数据源都失败，尝试返回旧缓存（降级策略）
        self.logger.error("所有热搜股票数据源均失败，尝试使用旧缓存")
        stale_cache = self.cache.get_stale(cache_key)
        if stale_cache:
            self.logger.warning(f"使用旧缓存数据: {cache_key}")
            return stale_cache

        # 4. 完全失败 - 提示 LLM 稍后重试
        return {
            'success': False,
            'error': '数据正在加载中，请稍等片刻后重试。提示：可以等待10-20秒后再次调用此接口获取最新数据。',
            'data': None,
            'tried_sources': [s[0] for s in sources if market in s[2]],
            'retry_suggested': True
        }


# 全局单例
_hot_stock_source = None


def get_hot_stock_source() -> HotStockSource:
    """获取热搜股票数据源单例"""
    global _hot_stock_source
    if _hot_stock_source is None:
        _hot_stock_source = HotStockSource()
    return _hot_stock_source
