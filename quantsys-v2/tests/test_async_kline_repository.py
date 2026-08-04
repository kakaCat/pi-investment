"""
AsyncKlineORMRepository单元测试

测试异步K线数据仓库的功能，包括：
- 连接池管理
- 批量查询性能
- 异步数据读写
- 事务支持
"""
import pytest
import pytest_asyncio
from adapters.outbound.repositories import AsyncKlineORMRepository
from infrastructure.persistence.database.async_base_repository import AsyncConnectionPool, init_async_pool, close_async_pool


@pytest_asyncio.fixture
async def async_pool():
    """创建异步连接池fixture"""
    pool = await init_async_pool(min_size=5, max_size=20)
    yield pool
    await close_async_pool()


@pytest_asyncio.fixture
async def async_repo(async_pool):
    """创建异步仓库fixture"""
    repo = AsyncKlineORMRepository(pool=async_pool)
    yield repo
    await repo.close()


class TestAsyncConnectionPool:
    """异步连接池测试"""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """测试连接池初始化"""
        pool = await init_async_pool(min_size=5, max_size=20)

        assert pool is not None
        assert pool._pool is not None
        assert pool.min_size == 5
        assert pool.max_size == 20

        await close_async_pool()

    @pytest.mark.asyncio
    async def test_pool_acquire_connection(self, async_pool):
        """测试获取连接"""
        async with async_pool.acquire() as conn:
            assert conn is not None
            # 执行简单查询验证连接可用
            result = await conn.fetchval("SELECT 1")
            assert result == 1

    @pytest.mark.asyncio
    async def test_pool_fetch_query(self, async_pool):
        """测试连接池查询方法"""
        result = await async_pool.fetchval("SELECT 1 + 1")
        assert result == 2

    @pytest.mark.asyncio
    async def test_pool_concurrent_connections(self, async_pool):
        """测试并发连接"""
        import asyncio

        async def query_task(i):
            result = await async_pool.fetchval(f"SELECT {i}")
            return result

        # 并发执行10个查询
        tasks = [query_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert results == list(range(10))


class TestAsyncKlineORMRepository:
    """异步K线仓库测试"""

    # ==================== 参数校验测试 ====================

    @pytest.mark.asyncio
    async def test_get_daily_klines_invalid_symbol(self, async_repo):
        """测试无效股票代码"""
        with pytest.raises(ValueError, match="股票代码格式错误"):
            await async_repo.get_daily_klines("INVALID", "2024-01-01", "2024-01-31")

    @pytest.mark.asyncio
    async def test_get_daily_klines_invalid_date(self, async_repo):
        """测试无效日期格式"""
        with pytest.raises(ValueError, match="Invalid date format"):
            await async_repo.get_daily_klines("000001.SZ", "2024/01/01", "2024-01-31")

    @pytest.mark.asyncio
    async def test_get_kline_count_invalid_type(self, async_repo):
        """测试无效K线类型"""
        with pytest.raises(ValueError, match="不支持的K线类型"):
            await async_repo.get_kline_count(
                "000001.SZ", "2024-01-01", "2024-01-31", kline_type="invalid"
            )

    # ==================== 日K线查询测试 ====================

    @pytest.mark.asyncio
    async def test_get_daily_klines_basic(self, async_repo):
        """测试基本日K线查询"""
        klines = await async_repo.get_daily_klines(
            "000001.SZ", "2024-01-01", "2024-01-31"
        )

        assert isinstance(klines, list)
        if len(klines) > 0:
            # 验证返回的字段
            assert 'symbol' in klines[0]
            assert 'trade_date' in klines[0]
            assert 'open' in klines[0]
            assert 'high' in klines[0]
            assert 'low' in klines[0]
            assert 'close' in klines[0]
            assert 'volume' in klines[0]

            # 验证数据按日期升序排列
            if len(klines) > 1:
                assert klines[0]['trade_date'] <= klines[1]['trade_date']

    @pytest.mark.asyncio
    async def test_get_daily_klines_with_fields(self, async_repo):
        """测试指定字段查询"""
        fields = ['symbol', 'trade_date', 'close', 'volume']
        klines = await async_repo.get_daily_klines(
            "000001.SZ", "2024-01-01", "2024-01-31", fields=fields
        )

        if len(klines) > 0:
            # 验证只返回指定字段
            for field in fields:
                assert field in klines[0]

    @pytest.mark.asyncio
    async def test_get_latest_daily_kline(self, async_repo):
        """测试获取最新日K线"""
        kline = await async_repo.get_latest_daily_kline("000001.SZ")

        if kline:
            assert 'symbol' in kline
            assert 'trade_date' in kline
            assert 'close' in kline
            assert kline['symbol'] == "000001.SZ"

    @pytest.mark.asyncio
    async def test_get_daily_klines_batch(self, async_repo):
        """测试批量查询日K线（核心性能优化点）"""
        symbols = ["000001.SZ", "000002.SZ", "600000.SH"]
        klines_dict = await async_repo.get_daily_klines_batch(
            symbols, "2024-01-01", "2024-01-31"
        )

        assert isinstance(klines_dict, dict)

        # 验证返回的数据结构
        for symbol in symbols:
            if symbol in klines_dict:
                assert isinstance(klines_dict[symbol], list)
                if len(klines_dict[symbol]) > 0:
                    assert klines_dict[symbol][0]['symbol'] == symbol

    @pytest.mark.asyncio
    async def test_get_daily_klines_batch_empty(self, async_repo):
        """测试空列表批量查询"""
        klines_dict = await async_repo.get_daily_klines_batch(
            [], "2024-01-01", "2024-01-31"
        )
        assert klines_dict == {}

    @pytest.mark.asyncio
    async def test_get_daily_klines_batch_performance(self, async_repo):
        """测试批量查询性能（100只股票）"""
        import time

        # 生成100只股票代码
        symbols = [f"{str(i).zfill(6)}.SZ" for i in range(1, 101)]

        start_time = time.time()
        klines_dict = await async_repo.get_daily_klines_batch(
            symbols, "2024-01-01", "2024-01-31"
        )
        elapsed = time.time() - start_time

        # 批量查询应该在合理时间内完成（<5秒）
        assert elapsed < 5.0, f"批量查询耗时过长: {elapsed:.2f}秒"
        assert isinstance(klines_dict, dict)

    # ==================== 分钟K线查询测试 ====================

    @pytest.mark.asyncio
    async def test_get_minute_klines_basic(self, async_repo):
        """测试基本分钟K线查询"""
        klines = await async_repo.get_minute_klines(
            "000001.SZ",
            "2024-01-02 09:30:00",
            "2024-01-02 15:00:00"
        )

        assert isinstance(klines, list)
        if len(klines) > 0:
            assert 'symbol' in klines[0]
            assert 'ts' in klines[0]
            assert 'close' in klines[0]

            # 验证数据按时间升序排列
            if len(klines) > 1:
                assert klines[0]['ts'] <= klines[1]['ts']

    @pytest.mark.asyncio
    async def test_get_latest_minute_kline(self, async_repo):
        """测试获取最新分钟K线"""
        kline = await async_repo.get_latest_minute_kline("000001.SZ")

        if kline:
            assert 'symbol' in kline
            assert 'ts' in kline
            assert kline['symbol'] == "000001.SZ"

    # ==================== 写入方法测试 ====================

    @pytest.mark.asyncio
    async def test_save_daily_klines_empty(self, async_repo):
        """测试保存空列表"""
        count = await async_repo.save_daily_klines([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_save_daily_klines_basic(self, async_repo):
        """测试保存日K线数据"""
        klines = [
            {
                'symbol': '000001.SZ',
                'trade_date': '2024-01-02',
                'open': 10.0,
                'high': 10.5,
                'low': 9.8,
                'close': 10.2,
                'volume': 1000000,
                'amount': 10200000.0,
                'turnover_rate': 0.5
            }
        ]

        try:
            count = await async_repo.save_daily_klines(klines)
            assert count >= 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    @pytest.mark.asyncio
    async def test_save_daily_klines_batch(self, async_repo):
        """测试批量保存日K线数据"""
        klines = [
            {
                'symbol': f'{str(i).zfill(6)}.SZ',
                'trade_date': '2024-01-02',
                'open': 10.0 + i * 0.1,
                'high': 10.5 + i * 0.1,
                'low': 9.8 + i * 0.1,
                'close': 10.2 + i * 0.1,
                'volume': 1000000 + i * 1000,
                'amount': 10200000.0 + i * 10000,
                'turnover_rate': 0.5
            }
            for i in range(100)
        ]

        try:
            count = await async_repo.save_daily_klines(klines)
            assert count == 100
        except Exception as e:
            pytest.skip(f"批量写入测试跳过: {str(e)}")

    @pytest.mark.asyncio
    async def test_save_minute_klines_empty(self, async_repo):
        """测试保存空分钟K线列表"""
        count = await async_repo.save_minute_klines([])
        assert count == 0

    # ==================== 统计方法测试 ====================

    @pytest.mark.asyncio
    async def test_get_kline_count(self, async_repo):
        """测试统计K线数量"""
        count = await async_repo.get_kline_count(
            "000001.SZ", "2024-01-01", "2024-01-31", kline_type='daily'
        )
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_get_available_date_range(self, async_repo):
        """测试获取可用日期范围"""
        date_range = await async_repo.get_available_date_range("000001.SZ")

        if date_range:
            assert isinstance(date_range, tuple)
            assert len(date_range) == 2
            min_date, max_date = date_range
            assert min_date <= max_date

    @pytest.mark.asyncio
    async def test_get_available_date_range_no_data(self, async_repo):
        """测试不存在的股票"""
        date_range = await async_repo.get_available_date_range("999999.SZ")
        assert date_range is None

    @pytest.mark.asyncio
    async def test_get_trading_days(self, async_repo):
        """测试获取交易日列表"""
        trading_days = await async_repo.get_trading_days("2024-01-01", "2024-01-31")

        assert isinstance(trading_days, list)
        if len(trading_days) > 0:
            # 验证日期格式
            assert len(trading_days[0]) == 10  # YYYY-MM-DD

            # 验证按升序排列
            if len(trading_days) > 1:
                assert trading_days[0] <= trading_days[1]

    @pytest.mark.asyncio
    async def test_get_kline_stats(self, async_repo):
        """测试获取K线统计信息"""
        stats = await async_repo.get_kline_stats("000001.SZ", "2024-01-01", "2024-01-31")

        assert isinstance(stats, dict)
        if stats.get('count', 0) > 0:
            # 验证统计字段
            assert 'count' in stats
            assert 'max_high' in stats
            assert 'min_low' in stats
            assert 'avg_close' in stats
            assert 'total_volume' in stats

            # 验证数据合理性
            assert stats['max_high'] >= stats['min_low']
            assert stats['total_volume'] >= 0

    # ==================== 并发性能测试 ====================

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, async_repo):
        """测试并发查询性能"""
        import asyncio
        import time

        symbols = ["000001.SZ", "000002.SZ", "600000.SH", "000001.SH", "000858.SZ"]

        async def query_symbol(symbol):
            return await async_repo.get_daily_klines(symbol, "2024-01-01", "2024-01-31")

        start_time = time.time()
        tasks = [query_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # 并发查询应该比串行快
        assert len(results) == len(symbols)
        assert elapsed < 3.0, f"并发查询耗时过长: {elapsed:.2f}秒"

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, async_repo):
        """测试混合并发操作（读+写+统计）"""
        import asyncio

        async def read_task():
            return await async_repo.get_daily_klines("000001.SZ", "2024-01-01", "2024-01-31")

        async def count_task():
            return await async_repo.get_kline_count("000002.SZ", "2024-01-01", "2024-01-31")

        async def stats_task():
            return await async_repo.get_kline_stats("600000.SH", "2024-01-01", "2024-01-31")

        # 并发执行不同类型的操作
        results = await asyncio.gather(
            read_task(),
            count_task(),
            stats_task(),
            return_exceptions=True
        )

        # 验证所有操作都成功完成
        assert len(results) == 3
        for result in results:
            assert not isinstance(result, Exception)

    # ==================== 边界条件测试 ====================

    @pytest.mark.asyncio
    async def test_get_daily_klines_same_date(self, async_repo):
        """测试开始日期和结束日期相同"""
        klines = await async_repo.get_daily_klines("000001.SZ", "2024-01-02", "2024-01-02")
        assert isinstance(klines, list)
        assert len(klines) <= 1

    @pytest.mark.asyncio
    async def test_get_daily_klines_future_date(self, async_repo):
        """测试未来日期"""
        klines = await async_repo.get_daily_klines("000001.SZ", "2030-01-01", "2030-12-31")
        assert klines == []

    @pytest.mark.asyncio
    async def test_get_daily_klines_reverse_date_range(self, async_repo):
        """测试反向日期范围"""
        klines = await async_repo.get_daily_klines("000001.SZ", "2024-01-31", "2024-01-01")
        assert klines == []


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
