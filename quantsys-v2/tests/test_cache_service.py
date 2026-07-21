"""
缓存服务测试
"""
import pytest
import time
from infrastructure.cache import (
    CacheService,
    MemoryCacheBackend,
)
from infrastructure.cache.cache_service import get_cache_service, init_cache_service


class TestMemoryCacheBackend:
    """内存缓存后端测试"""

    @pytest.fixture
    def backend(self):
        return MemoryCacheBackend()

    def test_set_and_get(self, backend):
        """测试基本的设置和获取"""
        backend.set("key1", "value1")
        assert backend.get("key1") == "value1"

    def test_get_nonexistent(self, backend):
        """测试获取不存在的键"""
        assert backend.get("nonexistent") is None

    def test_ttl_expiration(self, backend):
        """测试TTL过期"""
        backend.set("key1", "value1", ttl=1)
        assert backend.get("key1") == "value1"

        time.sleep(1.1)
        assert backend.get("key1") is None

    def test_delete(self, backend):
        """测试删除"""
        backend.set("key1", "value1")
        assert backend.delete("key1") is True
        assert backend.get("key1") is None
        assert backend.delete("key1") is False

    def test_clear(self, backend):
        """测试清空"""
        backend.set("key1", "value1")
        backend.set("key2", "value2")
        backend.clear()
        assert backend.get("key1") is None
        assert backend.get("key2") is None

    def test_keys_pattern(self, backend):
        """测试模式匹配"""
        backend.set("user:1", "data1")
        backend.set("user:2", "data2")
        backend.set("product:1", "data3")

        user_keys = backend.keys("user:*")
        assert len(user_keys) == 2
        assert "user:1" in user_keys
        assert "user:2" in user_keys

    def test_stats(self, backend):
        """测试统计信息"""
        backend.set("key1", "value1")
        backend.get("key1")  # hit
        backend.get("key2")  # miss

        stats = backend.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['sets'] == 1
        assert stats['hit_rate'] == 0.5


class TestCacheService:
    """缓存服务测试"""

    @pytest.fixture
    def cache(self):
        return CacheService()

    def test_namespace_isolation(self, cache):
        """测试命名空间隔离"""
        cache.set("ns1", "key1", "value1")
        cache.set("ns2", "key1", "value2")

        assert cache.get("ns1", "key1") == "value1"
        assert cache.get("ns2", "key1") == "value2"

    def test_set_and_get(self, cache):
        """测试基本操作"""
        cache.set("test", "key1", {"data": "value"})
        result = cache.get("test", "key1")
        assert result == {"data": "value"}

    def test_ttl(self, cache):
        """测试TTL"""
        cache.set("test", "key1", "value1", ttl=1)
        assert cache.get("test", "key1") == "value1"

        time.sleep(1.1)
        assert cache.get("test", "key1") is None

    def test_delete(self, cache):
        """测试删除"""
        cache.set("test", "key1", "value1")
        assert cache.delete("test", "key1") is True
        assert cache.get("test", "key1") is None

    def test_invalidate_by_pattern(self, cache):
        """测试模式清除"""
        cache.set("klines", "AAPL:2024-01-01", "data1")
        cache.set("klines", "AAPL:2024-01-02", "data2")
        cache.set("klines", "GOOGL:2024-01-01", "data3")

        count = cache.invalidate_by_pattern("klines", "AAPL:*")
        assert count == 2

        assert cache.get("klines", "AAPL:2024-01-01") is None
        assert cache.get("klines", "AAPL:2024-01-02") is None
        assert cache.get("klines", "GOOGL:2024-01-01") == "data3"

    def test_clear_namespace(self, cache):
        """测试清空命名空间"""
        cache.set("ns1", "key1", "value1")
        cache.set("ns1", "key2", "value2")
        cache.set("ns2", "key1", "value3")

        count = cache.clear_namespace("ns1")
        assert count == 2

        assert cache.get("ns1", "key1") is None
        assert cache.get("ns1", "key2") is None
        assert cache.get("ns2", "key1") == "value3"

    def test_hash_key(self, cache):
        """测试键哈希"""
        hash1 = cache.hash_key("symbol", "2024-01-01", "2024-12-31")
        hash2 = cache.hash_key("symbol", "2024-01-01", "2024-12-31")
        hash3 = cache.hash_key("symbol", "2024-01-01", "2024-12-30")

        assert hash1 == hash2
        assert hash1 != hash3

    def test_complex_data_types(self, cache):
        """测试复杂数据类型"""
        data = {
            'list': [1, 2, 3],
            'dict': {'a': 1, 'b': 2},
            'nested': {'x': [1, 2], 'y': {'z': 3}},
        }

        cache.set("test", "complex", data)
        result = cache.get("test", "complex")
        assert result == data

    def test_cache_hit_rate(self, cache):
        """测试缓存命中率"""
        # 设置一些数据
        for i in range(10):
            cache.set("test", f"key{i}", f"value{i}")

        # 命中
        for i in range(10):
            cache.get("test", f"key{i}")

        # 未命中
        for i in range(10, 15):
            cache.get("test", f"key{i}")

        stats = cache.get_stats()
        assert stats['hits'] == 10
        assert stats['misses'] == 5
        assert abs(stats['hit_rate'] - 0.6667) < 0.01


class TestCacheIntegration:
    """缓存集成测试"""

    def test_kline_caching_pattern(self):
        """测试K线数据缓存模式"""
        cache = CacheService()

        symbol = "AAPL"
        start_date = "2024-01-01"
        end_date = "2024-12-31"

        # 模拟K线数据
        klines = [
            {'date': '2024-01-01', 'close': 100.0},
            {'date': '2024-01-02', 'close': 101.0},
        ]

        # 缓存键
        cache_key = f"{symbol}:{start_date}:{end_date}"

        # 首次查询（未命中）
        cached = cache.get("klines", cache_key)
        assert cached is None

        # 写入缓存
        cache.set("klines", cache_key, klines, ttl=300)

        # 再次查询（命中）
        cached = cache.get("klines", cache_key)
        assert cached == klines

    def test_factor_caching_pattern(self):
        """测试因子缓存模式"""
        cache = CacheService()

        symbol = "AAPL"
        date = "2024-01-01"

        factors = {
            'ma5': 100.5,
            'ma10': 99.8,
            'rsi14': 65.3,
        }

        cache_key = f"{symbol}:{date}"

        # 写入缓存
        cache.set("factors", cache_key, factors, ttl=600)

        # 读取缓存
        cached = cache.get("factors", cache_key)
        assert cached == factors

    def test_cache_invalidation_on_update(self):
        """测试数据更新时的缓存失效"""
        cache = CacheService()

        symbol = "AAPL"

        # 缓存旧数据
        cache.set("stock_info", symbol, {"price": 100.0})

        # 模拟数据更新
        # 清除相关缓存
        cache.delete("stock_info", symbol)

        # 验证缓存已失效
        assert cache.get("stock_info", symbol) is None

    def test_batch_cache_warming(self):
        """测试批量缓存预热"""
        cache = CacheService()

        symbols = ["AAPL", "GOOGL", "MSFT"]
        date = "2024-01-01"

        # 批量预热
        for symbol in symbols:
            factors = {
                'ma5': 100.0,
                'rsi14': 50.0,
            }
            cache.set("factors", f"{symbol}:{date}", factors, ttl=300)

        # 验证所有数据都已缓存
        for symbol in symbols:
            cached = cache.get("factors", f"{symbol}:{date}")
            assert cached is not None


class TestCachePerformance:
    """缓存性能测试"""

    def test_memory_cache_performance(self):
        """测试内存缓存性能"""
        cache = CacheService()

        # 写入性能
        start = time.perf_counter()
        for i in range(1000):
            cache.set("perf", f"key{i}", f"value{i}")
        write_time = time.perf_counter() - start

        # 读取性能
        start = time.perf_counter()
        for i in range(1000):
            cache.get("perf", f"key{i}")
        read_time = time.perf_counter() - start

        print(f"\nMemory Cache Performance:")
        print(f"  Write 1000 entries: {write_time*1000:.2f}ms")
        print(f"  Read 1000 entries: {read_time*1000:.2f}ms")

        # 性能断言（应该非常快）
        assert write_time < 0.1  # 100ms
        assert read_time < 0.1

    def test_cache_overhead(self):
        """测试缓存开销"""
        cache = CacheService()

        data = {"large": "x" * 10000}  # 10KB数据

        # 无缓存
        start = time.perf_counter()
        for _ in range(100):
            _ = data.copy()
        no_cache_time = time.perf_counter() - start

        # 有缓存
        cache.set("test", "data", data)
        start = time.perf_counter()
        for _ in range(100):
            _ = cache.get("test", "data")
        cache_time = time.perf_counter() - start

        print(f"\nCache Overhead:")
        print(f"  No cache: {no_cache_time*1000:.2f}ms")
        print(f"  With cache: {cache_time*1000:.2f}ms")
        print(f"  Speedup: {no_cache_time/cache_time:.2f}x")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
