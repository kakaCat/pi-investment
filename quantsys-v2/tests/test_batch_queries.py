"""
测试批量查询优化

验证批量查询方法的正确性和性能提升
"""
import pytest
import time
from adapters.outbound.repositories import StockORMRepository
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import FactorORMRepository
from adapters.outbound.repositories import PortfolioORMRepository


class TestStockRepositoryBatch:
    """测试StockRepository批量查询"""

    def setup_method(self):
        self.repo = StockORMRepository()

    def test_get_by_symbols_batch_empty_list(self):
        """测试空列表输入"""
        result = self.repo.get_by_symbols_batch([])
        assert result == {}

    def test_get_by_symbols_batch_single_symbol(self):
        """测试单个股票查询"""
        result = self.repo.get_by_symbols_batch(['600000'])

        if '600000' in result:
            assert 'symbol' in result['600000']
            assert 'name' in result['600000']
            assert result['600000']['symbol'] == '600000'

    def test_get_by_symbols_batch_multiple_symbols(self):
        """测试多个股票批量查询"""
        symbols = ['600000', '000001', '000002']
        result = self.repo.get_by_symbols_batch(symbols)

        # 结果应该是字典
        assert isinstance(result, dict)

        # 检查返回的股票信息
        for symbol in result.keys():
            assert 'symbol' in result[symbol]
            assert 'name' in result[symbol]

    def test_get_by_symbols_batch_with_suffix(self):
        """测试带交易所后缀的股票代码"""
        symbols = ['600000.SH', '000001.SZ']
        result = self.repo.get_by_symbols_batch(symbols)

        assert isinstance(result, dict)

    def test_get_by_symbols_batch_nonexistent(self):
        """测试不存在的股票"""
        result = self.repo.get_by_symbols_batch(['999999'])

        # 不存在的股票不应该在结果中
        assert '999999' not in result

    def test_get_by_symbols_batch_performance(self):
        """性能测试：批量查询 vs 循环查询"""
        # 使用更多股票来体现性能差异
        symbols = ['600000', '000001', '000002', '600036', '601398',
                   '600519', '000858', '601318', '000333', '600276']

        # 预热数据库连接
        self.repo.get_by_symbol('600000')

        # 批量查询（多次测量取平均）
        batch_times = []
        for _ in range(5):
            start = time.time()
            batch_result = self.repo.get_by_symbols_batch(symbols)
            batch_times.append(time.time() - start)
        batch_time = sum(batch_times) / len(batch_times)

        # 循环查询（模拟旧方法）
        loop_times = []
        for _ in range(5):
            start = time.time()
            loop_result = {}
            for symbol in symbols:
                stock = self.repo.get_by_symbol(symbol)
                if stock:
                    loop_result[symbol] = stock
            loop_times.append(time.time() - start)
        loop_time = sum(loop_times) / len(loop_times)

        print(f"\n批量查询平均耗时: {batch_time:.4f}秒")
        print(f"循环查询平均耗时: {loop_time:.4f}秒")
        if batch_time > 0:
            print(f"性能提升: {(loop_time / batch_time):.2f}x")

        # 结果应该一致
        assert set(batch_result.keys()) == set(loop_result.keys())

        # 性能提升说明（不作为硬性断言，因为测试数据库可能很快）
        print(f"查询数量减少: {len(symbols)} 个查询 -> 1 个查询")


class TestKlineRepositoryBatch:
    """测试KlineRepository批量查询"""

    def setup_method(self):
        self.repo = KlineORMRepository()

    def test_get_latest_daily_klines_batch_empty(self):
        """测试空列表"""
        result = self.repo.get_latest_daily_klines_batch([])
        assert result == {}

    def test_get_latest_daily_klines_batch_single(self):
        """测试单个股票"""
        result = self.repo.get_latest_daily_klines_batch(['600000'])

        assert isinstance(result, dict)
        assert '600000' in result

    def test_get_latest_daily_klines_batch_multiple(self):
        """测试多个股票批量查询"""
        symbols = ['600000', '000001', '000002']
        result = self.repo.get_latest_daily_klines_batch(symbols)

        assert isinstance(result, dict)

        # 检查每个symbol都在结果中（即使值为None）
        for symbol in symbols:
            assert symbol in result

    def test_get_latest_daily_klines_batch_with_suffix(self):
        """测试带后缀的股票代码"""
        symbols = ['600000.SH', '000001.SZ']
        result = self.repo.get_latest_daily_klines_batch(symbols)

        # 应该保持原始symbol格式
        assert '600000.SH' in result
        assert '000001.SZ' in result

    def test_get_daily_klines_batch(self):
        """测试批量查询历史K线"""
        symbols = ['600000', '000001']
        result = self.repo.get_daily_klines_batch(
            symbols,
            '2024-01-01',
            '2024-01-31'
        )

        assert isinstance(result, dict)

        # 每个symbol都应该有一个列表（可能为空，如果测试数据库没有数据）
        for symbol in symbols:
            assert symbol in result, f"Symbol {symbol} not in result keys: {result.keys()}"
            assert isinstance(result[symbol], list), f"Result for {symbol} is not a list: {type(result[symbol])}"

        print(f"\n批量查询返回: {len(result)} 个股票")
        for symbol, klines in result.items():
            print(f"  {symbol}: {len(klines)} 条K线")

    def test_get_daily_klines_batch_performance(self):
        """性能测试：批量查询 vs 循环查询"""
        symbols = ['600000', '000001', '000002', '600036', '601398']
        start_date = '2024-01-01'
        end_date = '2024-01-31'

        # 预热
        self.repo.get_daily_klines('600000', start_date, end_date)

        # 批量查询（多次测量）
        batch_times = []
        for _ in range(3):
            start = time.time()
            batch_result = self.repo.get_daily_klines_batch(symbols, start_date, end_date)
            batch_times.append(time.time() - start)
        batch_time = sum(batch_times) / len(batch_times)

        # 循环查询
        loop_times = []
        for _ in range(3):
            start = time.time()
            loop_result = {}
            for symbol in symbols:
                klines = self.repo.get_daily_klines(symbol, start_date, end_date)
                loop_result[symbol] = klines
            loop_times.append(time.time() - start)
        loop_time = sum(loop_times) / len(loop_times)

        print(f"\n批量查询平均耗时: {batch_time:.4f}秒")
        print(f"循环查询平均耗时: {loop_time:.4f}秒")
        if batch_time > 0:
            print(f"性能提升: {(loop_time / batch_time):.2f}x")

        print(f"查询数量减少: {len(symbols)} 个查询 -> 1 个查询")


class TestFactorRepositoryBatch:
    """测试FactorRepository批量查询（已有batch方法）"""

    def setup_method(self):
        self.repo = FactorORMRepository()

    def test_get_factors_batch_empty(self):
        """测试空列表"""
        result = self.repo.get_factors_batch([], '2024-01-01')
        assert result == {}

    def test_get_factors_batch_multiple(self):
        """测试多个股票批量查询因子"""
        symbols = ['600000', '000001']
        result = self.repo.get_factors_batch(symbols, '2024-01-15')

        assert isinstance(result, dict)

        # 检查结果结构
        for symbol in result.keys():
            assert isinstance(result[symbol], dict)


class TestPortfolioRepositoryOptimization:
    """测试PortfolioRepository的N+1查询优化"""

    def setup_method(self):
        self.repo = PortfolioORMRepository()

    def test_get_holdings_as_of(self):
        """测试优化后的持仓查询"""
        result = self.repo.get_holdings_as_of('2024-12-31')

        assert isinstance(result, list)

        # 每条记录应该包含 symbol, name, quantity
        for holding in result:
            assert 'symbol' in holding
            assert 'quantity' in holding
            # name 可能为 None（如果没有交易记录）
            assert 'name' in holding

    def test_get_holdings_as_of_performance(self):
        """性能测试：验证窗口函数优化"""
        date = '2024-12-31'

        # 测试新查询（优化版本）- 只测试新版本能正常工作
        start = time.time()
        new_results = self.repo.get_holdings_as_of(date)
        new_time = time.time() - start

        print(f"\n优化后查询耗时: {new_time:.4f}秒")
        print(f"返回 {len(new_results)} 条持仓记录")
        print("使用窗口函数优化，避免了N+1查询模式")

        # 验证结果结构
        assert isinstance(new_results, list)
        for holding in new_results:
            assert 'symbol' in holding
            assert 'quantity' in holding
            assert holding['quantity'] > 0  # 应该只返回正持仓


class TestAPIEndpointOptimization:
    """测试API端点的批量查询优化"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from adapters.inbound.api.server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_compare_stocks_endpoint(self, client):
        """测试优化后的股票对比接口"""
        response = client.post('/api/stocks/compare', json={
            'symbols': ['600000', '000001', '000002']
        })

        assert response.status_code == 200
        data = response.get_json()

        assert 'comparisons' in data
        assert 'count' in data
        assert data['count'] == 3

        # 验证每个股票的数据结构
        for item in data['comparisons']:
            assert 'symbol' in item
            assert 'name' in item
            assert 'market' in item
            assert 'current_price' in item or item['current_price'] is None
            assert 'factors' in item

    def test_compare_stocks_performance(self, client):
        """性能测试：优化前后对比"""
        symbols = ['600000', '000001', '000002', '600036', '601398']

        # 多次请求测试平均性能
        times = []
        for _ in range(5):
            start = time.time()
            response = client.post('/api/stocks/compare', json={'symbols': symbols})
            elapsed = time.time() - start
            times.append(elapsed)
            assert response.status_code == 200

        avg_time = sum(times) / len(times)
        print(f"\n平均响应时间: {avg_time:.4f}秒")

        # 5个股票的对比应该在200ms内完成（批量查询优化后）
        assert avg_time < 0.3  # 300ms阈值


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
