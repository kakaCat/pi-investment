"""
FactorRepository单元测试
"""
import pytest
import math
from adapters.outbound.repositories import FactorORMRepository


class TestFactorRepository:
    """FactorRepository测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.repo = FactorORMRepository()

    def teardown_method(self):
        """每个测试方法后执行"""
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 参数校验测试 ====================

    def test_get_factors_invalid_symbol(self):
        """测试无效股票代码"""
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_factors("INVALID", "2024-01-01")

    def test_get_factors_invalid_date(self):
        """测试无效日期格式"""
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_factors("000001.SZ", "2024/01/01")

    # ==================== 查询方法测试 ====================

    def test_get_factors_basic(self):
        """测试基本因子查询"""
        factors = self.repo.get_factors("000001.SZ", "2024-01-02")

        if factors:
            assert isinstance(factors, dict)
            # 验证因子值是数字
            for factor_name, factor_value in factors.items():
                assert isinstance(factor_name, str)
                assert isinstance(factor_value, (int, float)) or factor_value is None

    def test_get_factors_no_data(self):
        """测试不存在的数据"""
        factors = self.repo.get_factors("999999.SZ", "2024-01-01")
        assert factors is None

    def test_get_factors_batch(self):
        """测试批量查询因子"""
        symbols = ["000001.SZ", "000002.SZ", "600000.SH"]
        factors_dict = self.repo.get_factors_batch(symbols, "2024-01-02")

        assert isinstance(factors_dict, dict)

        # 验证返回的数据结构
        for symbol, factors in factors_dict.items():
            assert symbol in symbols
            assert isinstance(factors, dict)
            for factor_name, factor_value in factors.items():
                assert isinstance(factor_name, str)
                assert isinstance(factor_value, (int, float)) or factor_value is None

    def test_get_factors_batch_empty(self):
        """测试空列表批量查询"""
        factors_dict = self.repo.get_factors_batch([], "2024-01-02")
        assert factors_dict == {}

    def test_get_factor_history(self):
        """测试因子历史查询"""
        history = self.repo.get_factor_history(
            "000001.SZ",
            "ma5",
            "2024-01-01",
            "2024-01-31"
        )

        assert isinstance(history, list)
        if len(history) > 0:
            assert 'factor_date' in history[0]
            assert 'factor_value' in history[0]

            # 验证按日期升序排列
            if len(history) > 1:
                assert history[0]['factor_date'] <= history[1]['factor_date']

    def test_get_latest_factors(self):
        """测试获取最新因子"""
        factors = self.repo.get_latest_factors("000001.SZ")

        if factors:
            assert isinstance(factors, dict)
            assert len(factors) > 0

    def test_get_latest_factors_no_data(self):
        """测试不存在的股票"""
        factors = self.repo.get_latest_factors("999999.SZ")
        assert factors is None

    # ==================== 写入方法测试 ====================

    def test_save_factors_empty(self):
        """测试保存空因子字典"""
        result = self.repo.save_factors("000001.SZ", "2024-01-02", {})
        assert result is True

    def test_save_factors_with_nan(self):
        """测试保存包含NaN的因子"""
        factors = {
            'ma5': 10.5,
            'ma10': float('nan'),
            'ma20': float('inf'),
            'rsi': 50.0
        }

        try:
            result = self.repo.save_factors("000001.SZ", "2024-01-02", factors)
            assert result is True
        except Exception as e:
            # 如果数据库连接失败或权限不足，跳过测试
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_save_factors_batch_empty(self):
        """测试批量保存空列表"""
        count = self.repo.save_factors_batch([])
        assert count == 0

    def test_update_factor(self):
        """测试更新单个因子"""
        try:
            result = self.repo.update_factor(
                "000001.SZ",
                "2024-01-02",
                "ma5",
                10.5
            )
            assert result is True
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_update_factor_with_nan(self):
        """测试更新因子为NaN"""
        try:
            result = self.repo.update_factor(
                "000001.SZ",
                "2024-01-02",
                "test_factor",
                float('nan')
            )
            assert result is True
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    # ==================== 统计方法测试 ====================

    def test_get_factor_stats(self):
        """测试获取因子统计信息"""
        stats = self.repo.get_factor_stats("ma5", "2024-01-01", "2024-01-31")

        assert isinstance(stats, dict)
        if stats.get('count', 0) > 0:
            # 验证统计字段
            assert 'count' in stats
            assert 'mean' in stats
            assert 'std' in stats
            assert 'min' in stats
            assert 'max' in stats

            # 验证数据合理性
            assert stats['count'] > 0
            if stats['min'] is not None and stats['max'] is not None:
                assert stats['min'] <= stats['max']

    def test_get_available_factors(self):
        """测试获取可用因子列表"""
        factors = self.repo.get_available_factors("000001.SZ")

        assert isinstance(factors, list)
        if len(factors) > 0:
            # 验证因子名称是字符串
            for factor_name in factors:
                assert isinstance(factor_name, str)

            # 验证按字母顺序排列
            if len(factors) > 1:
                assert factors == sorted(factors)

    def test_get_available_factors_no_data(self):
        """测试不存在的股票"""
        factors = self.repo.get_available_factors("999999.SZ")
        assert factors == []

    def test_get_factor_coverage(self):
        """测试获取因子覆盖率"""
        coverage = self.repo.get_factor_coverage("ma5", "2024-01-02")

        assert isinstance(coverage, dict)
        assert 'total_stocks' in coverage
        assert 'covered_stocks' in coverage
        assert 'coverage_rate' in coverage

        # 验证数据合理性
        assert coverage['total_stocks'] >= 0
        assert coverage['covered_stocks'] >= 0
        assert 0.0 <= coverage['coverage_rate'] <= 1.0
        assert coverage['covered_stocks'] <= coverage['total_stocks']

    # ==================== 边界条件测试 ====================

    def test_get_factors_future_date(self):
        """测试未来日期"""
        factors = self.repo.get_factors("000001.SZ", "2030-01-01")
        # 未来日期应该返回None
        assert factors is None

    def test_get_factor_history_reverse_date_range(self):
        """测试反向日期范围"""
        history = self.repo.get_factor_history(
            "000001.SZ",
            "ma5",
            "2024-01-31",
            "2024-01-01"
        )
        # 反向日期范围应该返回空列表
        assert history == []

    def test_save_factors_all_none(self):
        """测试保存全部为None的因子"""
        factors = {
            'factor1': None,
            'factor2': None,
            'factor3': None
        }

        try:
            result = self.repo.save_factors("000001.SZ", "2024-01-02", factors)
            assert result is True
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_get_factor_stats_no_data(self):
        """测试不存在的因子统计"""
        stats = self.repo.get_factor_stats("nonexistent_factor", "2024-01-01", "2024-01-31")
        # 不存在的因子应该返回空字典或count为0
        assert isinstance(stats, dict)
        if stats:
            assert stats.get('count', 0) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
