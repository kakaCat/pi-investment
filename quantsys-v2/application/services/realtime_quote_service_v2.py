"""
实时行情服务 V2 - 增强版

特性：
1. 只返回真实的实时数据（不降级到数据库）
2. 数据源优先级优化（腾讯 → 东方财富 → 新浪 → AkShare → 网易）
3. 熔断机制：失败的数据源1分钟内不再访问
4. 缓存机制：成功的数据缓存5秒（减少API调用）
5. 失败时返回浏览器访问链接
"""
from __future__ import annotations
import structlog
import time
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from application.services.quote_providers import (
    QuoteProvider,
    QuoteData,
    TencentQuoteProvider,
    EastmoneyQuoteProvider,
    SinaQuoteProvider,
    AkshareQuoteProvider,
    NeteaseQuoteProvider,
)

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """熔断器 - 失败的数据源在指定时间内不再访问"""

    def __init__(self, cooldown_seconds: int = 60):
        """
        初始化熔断器

        Args:
            cooldown_seconds: 熔断冷却时间（秒），默认60秒
        """
        self.cooldown_seconds = cooldown_seconds
        self._failures: Dict[str, float] = {}  # provider_name -> failure_timestamp

    def record_failure(self, provider_name: str):
        """记录失败"""
        self._failures[provider_name] = time.time()
        logger.info(f"熔断器：记录 {provider_name} 失败，冷却 {self.cooldown_seconds} 秒")

    def is_available(self, provider_name: str) -> bool:
        """检查数据源是否可用（未被熔断）"""
        if provider_name not in self._failures:
            return True

        elapsed = time.time() - self._failures[provider_name]
        if elapsed >= self.cooldown_seconds:
            # 冷却时间已过，移除记录
            del self._failures[provider_name]
            logger.info(f"熔断器：{provider_name} 冷却完成，恢复可用")
            return True

        remaining = int(self.cooldown_seconds - elapsed)
        logger.debug(f"熔断器：{provider_name} 仍在冷却中，剩余 {remaining} 秒")
        return False

    def get_status(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        now = time.time()
        status = {}
        for provider, failure_time in self._failures.items():
            elapsed = now - failure_time
            remaining = max(0, int(self.cooldown_seconds - elapsed))
            status[provider] = {
                'blocked': elapsed < self.cooldown_seconds,
                'remaining_seconds': remaining
            }
        return status


class QuoteCache:
    """行情数据缓存"""

    def __init__(self, ttl_seconds: int = 5):
        """
        初始化缓存

        Args:
            ttl_seconds: 缓存有效期（秒），默认5秒
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[QuoteData, float]] = {}  # symbol -> (quote, timestamp)

    def get(self, symbol: str) -> Optional[QuoteData]:
        """获取缓存数据"""
        if symbol not in self._cache:
            return None

        quote, timestamp = self._cache[symbol]
        age = time.time() - timestamp

        if age > self.ttl_seconds:
            # 缓存过期
            del self._cache[symbol]
            logger.debug(f"缓存：{symbol} 已过期（{age:.1f}秒）")
            return None

        logger.info(f"缓存命中：{symbol}，数据年龄 {age:.1f}秒")
        return quote

    def set(self, symbol: str, quote: QuoteData):
        """设置缓存"""
        self._cache[symbol] = (quote, time.time())
        logger.debug(f"缓存：保存 {symbol} 数据")

    def clear(self):
        """清空缓存"""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        now = time.time()
        total = len(self._cache)
        fresh = sum(1 for _, (_, ts) in self._cache.items() if (now - ts) <= self.ttl_seconds)
        return {
            'total_entries': total,
            'fresh_entries': fresh,
            'ttl_seconds': self.ttl_seconds
        }


class RealtimeQuoteServiceV2:
    """实时行情服务 V2

    增强特性：
    - 只返回真实实时数据（不降级到数据库）
    - 数据源优先级优化
    - 熔断机制（失败源1分钟内不访问）
    - 缓存机制（5秒缓存）
    - 失败时返回浏览器访问链接
    """

    # 数据源浏览器访问链接模板
    BROWSER_LINKS = {
        'tencent': 'https://gu.qq.com/sh{code}',  # 上交所
        'eastmoney': 'https://quote.eastmoney.com/sh{code}.html',
        'sina': 'https://finance.sina.com.cn/realstock/company/sh{code}/nc.shtml',
        'xueqiu': 'https://xueqiu.com/S/SH{code}',
        'tonghuashun': 'https://stockpage.10jqka.com.cn/{code}/',
    }

    def __init__(
        self,
        cache_ttl: int = 5,
        circuit_breaker_cooldown: int = 60,
        providers: Optional[List[QuoteProvider]] = None
    ):
        """
        初始化服务

        Args:
            cache_ttl: 缓存有效期（秒），默认5秒
            circuit_breaker_cooldown: 熔断冷却时间（秒），默认60秒
            providers: 可选的数据源列表。如果为 None，使用优化后的默认顺序
        """
        if providers is None:
            # 优化后的数据源优先级：腾讯 → 东方财富 → 新浪 → AkShare → 网易
            self.providers = [
                TencentQuoteProvider(),      # 腾讯最稳定，优先级最高
                EastmoneyQuoteProvider(),    # 东方财富第二
                SinaQuoteProvider(),         # 新浪第三
                AkshareQuoteProvider(),      # AkShare 较慢，第四
                NeteaseQuoteProvider(),      # 网易可能已废弃，最后
            ]
        else:
            self.providers = providers

        # 初始化缓存和熔断器
        self.cache = QuoteCache(ttl_seconds=cache_ttl)
        self.circuit_breaker = CircuitBreaker(cooldown_seconds=circuit_breaker_cooldown)

        # 统计信息
        self.total_requests = 0
        self.cache_hits = 0
        self.success_count = 0
        self.failure_count = 0
        self.provider_stats: Dict[str, Dict[str, int]] = {}

        # 初始化各 provider 的统计
        for provider in self.providers:
            self.provider_stats[provider.name] = {
                'success': 0,
                'failure': 0,
                'skipped': 0  # 被熔断器跳过的次数
            }

        logger.info(
            f"RealtimeQuoteServiceV2 初始化完成："
            f"{len(self.providers)} 个数据源，"
            f"缓存 {cache_ttl}秒，"
            f"熔断 {circuit_breaker_cooldown}秒"
        )
        logger.info(f"数据源优先级：{' → '.join([p.name for p in self.providers])}")

    def _is_valid_quote(self, quote: QuoteData) -> bool:
        """验证行情数据完整性"""
        return (
            quote.price > 0 and
            quote.symbol and
            quote.name and
            quote.timestamp and
            quote.source
        )

    def _generate_browser_links(self, symbol: str) -> Dict[str, str]:
        """生成浏览器访问链接

        Args:
            symbol: 股票代码（如 600519.SH）

        Returns:
            链接字典 {平台名: URL}
        """
        # 提取6位代码
        code = symbol.split('.')[0] if '.' in symbol else symbol

        links = {}
        for platform, template in self.BROWSER_LINKS.items():
            links[platform] = template.format(code=code)

        return links

    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情（只返回真实实时数据）

        Args:
            symbol: 股票代码（如 600519.SH）

        Returns:
            QuoteData 或 None（所有数据源都失败时）
        """
        self.total_requests += 1

        # 1. 检查缓存
        cached_quote = self.cache.get(symbol)
        if cached_quote:
            self.cache_hits += 1
            return cached_quote

        # 2. 依次尝试各个数据源
        logger.info(f"获取 {symbol} 实时行情，尝试 {len(self.providers)} 个数据源")

        for i, provider in enumerate(self.providers, 1):
            # 检查熔断器
            if not self.circuit_breaker.is_available(provider.name):
                logger.debug(f"[{i}/{len(self.providers)}] {provider.name} 被熔断，跳过")
                self.provider_stats[provider.name]['skipped'] += 1
                continue

            try:
                logger.debug(f"[{i}/{len(self.providers)}] 尝试 {provider.name}")
                quote = provider.get_quote(symbol)

                # 检查返回值有效性
                if quote is not None and self._is_valid_quote(quote):
                    logger.info(
                        f"✅ 成功从 {provider.name} 获取 {symbol} 实时行情 "
                        f"(价格={quote.price})"
                    )

                    # 更新统计
                    self.success_count += 1
                    self.provider_stats[provider.name]['success'] += 1

                    # 保存到缓存
                    self.cache.set(symbol, quote)

                    return quote
                else:
                    # provider 返回 None 或无效数据
                    logger.warning(f"{provider.name} 返回无效数据：{quote}")
                    self.provider_stats[provider.name]['failure'] += 1
                    self.circuit_breaker.record_failure(provider.name)

            except Exception as e:
                # provider 抛出异常
                logger.warning(
                    f"{provider.name} 查询失败：{type(e).__name__}: {e}"
                )
                self.provider_stats[provider.name]['failure'] += 1
                self.circuit_breaker.record_failure(provider.name)

        # 3. 所有数据源都失败
        logger.error(f"❌ 所有数据源都无法获取 {symbol} 的实时行情")
        self.failure_count += 1
        return None

    def get_browser_links(self, symbol: str) -> Dict[str, str]:
        """
        获取浏览器访问链接（当 API 失败时使用）

        Args:
            symbol: 股票代码

        Returns:
            链接字典
        """
        return self._generate_browser_links(symbol)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        cache_hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
        success_rate = (self.success_count / self.total_requests * 100) if self.total_requests > 0 else 0.0

        return {
            'total_requests': self.total_requests,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': f'{cache_hit_rate:.1f}%',
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': f'{success_rate:.1f}%',
            'provider_stats': self.provider_stats.copy(),
            'circuit_breaker_status': self.circuit_breaker.get_status(),
            'cache_stats': self.cache.get_stats(),
        }

    def reset_stats(self):
        """重置统计信息（保留缓存和熔断器状态）"""
        self.total_requests = 0
        self.cache_hits = 0
        self.success_count = 0
        self.failure_count = 0
        for provider_name in self.provider_stats:
            self.provider_stats[provider_name] = {
                'success': 0,
                'failure': 0,
                'skipped': 0
            }
        logger.info("统计信息已重置")

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("缓存已清空")
