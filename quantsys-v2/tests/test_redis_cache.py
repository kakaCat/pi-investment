"""
Redis缓存测试

测试Redis缓存后端的功能和性能。
"""
import pytest
import time
from unittest.mock import Mock, patch

from infrastructure.cache import CacheService
from infrastructure.cache.cache_service import RedisCacheBackend
from infrastructure.config import create_cache_service, create_redis_client
from infrastructure.config import CACHE_TTL, CACHE_NAMESPACE


class TestRedisCacheBackend:
    """Redis缓存后端测试"""

    @pytest.fixture
    def redis_backend(self):
        """创建Redis后端（需要Redis服务运行）"""
        try:
            import redis
            client = redis.Redis(host='127.0.0.1', port=6379, db=15, decode_responses=True)
            client.ping()
            client.flushdb()  # 清空测试数据库
            return RedisCacheBackend(client)
        except Exception as e:
            pytest.skip(f"Redis不可用: {e}")

    def test_redis_set_and_get(self, redis_backend):
        """测试Redis基本操作"""
        redis_backend.set("test_key", "test_value")
        assert redis_backend.get("test_key") == "test_value"

    def test_redis_complex_data(self, redis_backend):
        """测试Redis存储复杂数据"""
        data = {
            'symbol': 'AAPL',
            'klines': [
                {'date': '2024-01-01', 'close': 100.0},
                {'date': '2024-01-02', 'close': 101.0},
            ],
            'factors': {'ma5': 100.5, 'rsi14': 65.3}
        }

        redis_backend.set("complex_key", data)
        result = redis_backend.get("complex_key")
        assert result == data

    def test_redis_ttl(self, redis_backend):
        """测试Redis TTL"""
        redis_backend.set("ttl_key", "value", ttl=1)
        assert redis_backend.get("ttl_key") == "value"

        time.sleep(1.1)
        assert redis_backend.get("ttl_key") is None

    def test_redis_delete(self, redis_backend):
        """测试Redis删除"""
        redis_backend.set("delete_key", "value")
        assert redis_backend.delete("delete_key") is True
        assert redis_backend.get("delete_key") is None

    def test_redis_keys_pattern(self, redis_backend):
        """测试Redis模式匹配"""
        redis_backend.set("klines:AAPL:2024-01-01", "data1")
        redis_backend.set("klines:AAPL:2024-01-02", "data2")
        redis_backend.set("klines:GOOGL:2024-01-01", "data3")

        keys = redis_backend.keys("klines:AAPL:*")
        assert len(keys) == 2

    def test_redis_stats(self, redis_backend):
        """测试Redis统计"""
        redis_backend.set("key1", "value1")
        redis_backend.get("key1")  # hit
        redis_backend.get("key2")  # miss

        stats = redis_backend.get_stats()
        assert stats['backend'] == 'redis'
        assert stats['hits'] == 1
        assert stats['misses'] == 1


class TestCacheFactory:
    """缓存工厂测试"""

    def test_create_cache_service_with_redis(self):
        """测试创建Redis缓存服务"""
        try:
            cache = create_cache_service(use_redis=True)
            stats = cache.get_stats()
            # 如果Redis可用，应该是redis后端
            assert stats['backend'] in ['redis', 'memory']
        except Exception as e:
            pytest.skip(f"Redis不可用: {e}")

    def test_create_cache_service_memory_fallback(self):
        """测试降级到内存缓存"""
        with patch('redis.Redis') as mock_redis:
            mock_redis.side_effect = Exception("Connection failed")
            cache = create_cache_service(use_redis=True)
            stats = cache.get_stats()
            assert stats['backend'] == 'memory'

    def test_create_redis_client(self):
        """测试创建Redis客户端"""
        client = create_redis_client()
        if client:
            assert client.ping() is True
        else:
            pytest.skip("Redis不可用")


class TestDataServiceWithRedis:
    """DataService集成Redis测试"""

    @pytest.fixture
    def data_service_with_cache(self):
        """创建带缓存的DataService"""
        from application.services.data_service import DataService

        cache = create_cache_service(use_redis=False)  # 使用内存缓存测试
        return DataService(cache_manager=cache)

    def test_kline_caching(self, data_service_with_cache):
        """测试K线缓存"""
        ds = data_service_with_cache

        # 模拟数据库查询
        with patch.object(ds.kline, 'get_latest_daily_kline') as mock_get:
            mock_get.return_value = {'date': '2024-01-01', 'close': 100.0}

            # 首次查询（缓存未命中）
            result1 = ds._get_latest_kline_cached('AAPL')
            assert mock_get.call_count == 1

            # 再次查询（缓存命中）
            result2 = ds._get_latest_kline_cached('AAPL')
            assert mock_get.call_count == 1  # 没有再次调用数据库
            assert result1 == result2

    def test_factor_caching(self, data_service_with_cache):
        """测试因子缓存"""
        ds = data_service_with_cache

        with patch.object(ds.factor, 'get_latest_factors') as mock_get:
            mock_get.return_value = {'ma5': 100.5, 'rsi14': 65.3}

            # 首次查询
            result1 = ds._get_latest_factors_cached('AAPL')
            assert mock_get.call_count == 1

            # 缓存命中
            result2 = ds._get_latest_factors_cached('AAPL')
            assert mock_get.call_count == 1
            assert result1 == result2

    def test_cache_invalidation(self, data_service_with_cache):
        """测试缓存失效"""
        ds = data_service_with_cache

        # 设置缓存
        ds._cache.set(CACHE_NAMESPACE['klines'], 'latest:AAPL', {'close': 100.0})
        ds._cache.set(CACHE_NAMESPACE['factors'], 'latest:AAPL', {'ma5': 100.5})

        # 清除缓存
        ds.invalidate_stock_cache('AAPL')

        # 验证缓存已清除
        assert ds._cache.get(CACHE_NAMESPACE['klines'], 'latest:AAPL') is None
        assert ds._cache.get(CACHE_NAMESPACE['factors'], 'latest:AAPL') is None

    def test_cache_stats(self, data_service_with_cache):
        """测试缓存统计"""
        ds = data_service_with_cache

        stats = ds.get_cache_stats()
        assert 'backend' in stats
        assert stats['backend'] in ['memory', 'redis']


class TestCachePerformance:
    """缓存性能测试"""

    @pytest.fixture
    def redis_cache(self):
        """创建Redis缓存（如果可用）"""
        try:
            cache = create_cache_service(use_redis=True)
            if cache.get_stats()['backend'] == 'redis':
                return cache
            pytest.skip("Redis不可用")
        except Exception as e:
            pytest.skip(f"Redis不可用: {e}")

    def test_redis_write_performance(self, redis_cache):
        """测试Redis写入性能"""
        start = time.perf_counter()
        for i in range(1000):
            redis_cache.set("perf", f"key{i}", f"value{i}", ttl=60)
        write_time = time.perf_counter() - start

        print(f"\nRedis写入1000条: {write_time*1000:.2f}ms")
        assert write_time < 2.0  # 应该在2秒内完成

    def test_redis_read_performance(self, redis_cache):
        """测试Redis读取性能"""
        # 预先写入数据
        for i in range(1000):
            redis_cache.set("perf", f"key{i}", f"value{i}", ttl=60)

        start = time.perf_counter()
        for i in range(1000):
            redis_cache.get("perf", f"key{i}")
        read_time = time.perf_counter() - start

        print(f"\nRedis读取1000条: {read_time*1000:.2f}ms")
        assert read_time < 2.0

    def test_cache_hit_rate(self, redis_cache):
        """测试缓存命中率"""
        # 写入数据
        for i in range(100):
            redis_cache.set("test", f"key{i}", f"value{i}")

        # 命中
        for i in range(100):
            redis_cache.get("test", f"key{i}")

        # 未命中
        for i in range(100, 150):
            redis_cache.get("test", f"key{i}")

        stats = redis_cache.get_stats()
        print(f"\n缓存命中率: {stats['hit_rate']*100:.1f}%")
        assert stats['hit_rate'] > 0.6


class TestCacheTTLConfig:
    """缓存TTL配置测试"""

    def test_ttl_config_exists(self):
        """测试TTL配置存在"""
        assert 'kline_latest' in CACHE_TTL
        assert 'factor_latest' in CACHE_TTL
        assert 'stock_info' in CACHE_TTL

    def test_ttl_values_reasonable(self):
        """测试TTL值合理"""
        assert CACHE_TTL['kline_latest'] == 60  # 1分钟
        assert CACHE_TTL['factor_latest'] == 300  # 5分钟
        assert CACHE_TTL['stock_info'] == 3600  # 1小时

    def test_namespace_config(self):
        """测试命名空间配置"""
        assert 'klines' in CACHE_NAMESPACE
        assert 'factors' in CACHE_NAMESPACE
        assert 'stocks' in CACHE_NAMESPACE


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
