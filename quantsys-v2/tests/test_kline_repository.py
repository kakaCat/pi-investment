"""
KlineRepository单元测试

注意：get_daily_klines/get_latest_daily_kline/get_minute_klines 现返回
polars DataFrame（ORM 重构契约），断言用 df.to_dicts()/df.height。
daily_klines 的 symbol 统一无后缀归一化（_normalize_symbol）。
"""
import pytest
import polars as pl
from adapters.outbound.repositories import KlineORMRepository


class TestKlineRepository:
    """KlineRepository测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.repo = KlineORMRepository()

    def teardown_method(self):
        """每个测试方法后执行"""
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== count_klines 别名回归测试 ====================
    # data_service.py:152,161 调用 self.kline.count_klines(symbol)，
    # 但仓库只有 count_daily_klines — 导致 data_manager status 报错。
    # 此测试锁定该接口契约，防止回归。

    def test_count_klines_alias_exists(self):
        """仓库必须提供 count_klines 方法（data_service 调用依赖）"""
        assert hasattr(self.repo, 'count_klines'), \
            "KlineORMRepository 缺少 count_klines 方法（data_service.py 调用依赖）"

    def test_count_klines_matches_count_daily_klines(self):
        """count_klines 行为应与 count_daily_klines 一致"""
        if not hasattr(self.repo, 'count_klines'):
            pytest.fail("count_klines 方法不存在")
        result = self.repo.count_klines("600519.SH")
        assert isinstance(result, int)
        assert result >= 0
        assert result == self.repo.count_daily_klines("600519.SH")

    # ==================== 参数容错测试 ====================
    # 当前 ORM API 不做参数校验（旧 _validate_symbol/_validate_date 已随
    # 8f06ae1 移除，无生产调用方依赖 ValueError），无效输入一律返回空 DataFrame。

    def test_get_daily_klines_invalid_symbol(self):
        """无效股票代码返回空DataFrame（不抛异常）"""
        df = self.repo.get_daily_klines("INVALID", "2024-01-01", "2024-01-31")
        assert isinstance(df, pl.DataFrame)
        assert df.height == 0

    def test_get_daily_klines_invalid_date(self):
        """无效日期格式返回空DataFrame（查询异常被捕获，不抛给调用方）"""
        df = self.repo.get_daily_klines("000001.SZ", "not-a-date", "2024-01-31")
        assert isinstance(df, pl.DataFrame)
        assert df.height == 0
        # PG 报错会使 scoped_session 共享事务进入 aborted 状态，
        # 不回滚会毒化同线程后续测试（如 save_daily_klines upsert）
        self.repo.session.rollback()

    # ==================== 日K线查询测试 ====================

    def test_get_daily_klines_basic(self):
        """测试基本日K线查询"""
        df = self.repo.get_daily_klines("000001.SZ", "2024-01-01", "2024-01-31")

        assert isinstance(df, pl.DataFrame)
        if df.height > 0:
            klines = df.to_dicts()
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

    def test_get_daily_klines_with_fields(self):
        """测试指定字段查询"""
        fields = ['symbol', 'trade_date', 'close', 'volume']
        df = self.repo.get_daily_klines("000001.SZ", "2024-01-01", "2024-01-31", fields=fields)

        if df.height > 0:
            # 验证只返回指定字段
            for field in fields:
                assert field in df.columns

    def test_get_latest_daily_kline(self):
        """测试获取最新日K线"""
        df = self.repo.get_latest_daily_kline("000001.SZ")

        if df is not None and df.height > 0:
            kline = df.to_dicts()[0]
            assert 'symbol' in kline
            assert 'trade_date' in kline
            assert 'close' in kline
            # symbol 统一无后缀归一化
            assert kline['symbol'] == "000001"

    def test_get_daily_klines_batch(self):
        """测试批量查询日K线"""
        symbols = ["000001.SZ", "000002.SZ", "600000.SH"]
        klines_dict = self.repo.get_daily_klines_batch(symbols, "2024-01-01", "2024-01-31")

        assert isinstance(klines_dict, dict)

        # 验证返回的数据结构（dict 键保持入参格式；行内 symbol 为无后缀归一化值）
        for symbol in symbols:
            if symbol in klines_dict:
                assert isinstance(klines_dict[symbol], list)
                if len(klines_dict[symbol]) > 0:
                    assert klines_dict[symbol][0]['symbol'] == symbol.split('.')[0]

    def test_get_daily_klines_batch_empty(self):
        """测试空列表批量查询"""
        klines_dict = self.repo.get_daily_klines_batch([], "2024-01-01", "2024-01-31")
        assert klines_dict == {}

    # ==================== 分钟K线查询测试 ====================

    def test_get_minute_klines_basic(self):
        """测试基本分钟K线查询"""
        df = self.repo.get_minute_klines(
            "000001.SZ",
            "2024-01-02 09:30:00",
            "2024-01-02 15:00:00"
        )

        assert isinstance(df, pl.DataFrame)
        if df.height > 0:
            klines = df.to_dicts()
            assert 'symbol' in klines[0]
            assert 'trade_datetime' in klines[0]
            assert 'close' in klines[0]

            # 验证数据按时间升序排列
            if len(klines) > 1:
                assert klines[0]['trade_datetime'] <= klines[1]['trade_datetime']

    def test_get_latest_minute_kline(self):
        """测试获取最新分钟K线"""
        kline = self.repo.get_latest_minute_kline("000001.SZ")

        if kline:
            assert 'symbol' in kline
            assert 'trade_datetime' in kline
            assert kline['symbol'] == "000001"  # 无后缀归一化

    # ==================== 写入方法测试 ====================

    def test_save_daily_klines_empty(self):
        """测试保存空列表"""
        count = self.repo.save_daily_klines([])
        assert count == 0

    def test_save_daily_klines_basic(self):
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
            count = self.repo.save_daily_klines(klines)
            assert count >= 0  # UPSERT可能返回0（如果数据已存在且未变化）
        except Exception as e:
            # 如果数据库连接失败或权限不足，跳过测试
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    # ==================== 统计方法测试 ====================

    def test_get_date_range(self):
        """get_date_range 返回 (最早, 最晚) 元组
        （stock_code_validator/data_service_orm 生产调用此方法）"""
        date_range = self.repo.get_date_range("000001.SZ")
        if date_range:
            assert len(date_range) == 2
            assert date_range[0] <= date_range[1]

    def test_get_date_range_no_data(self):
        """无数据的股票返回 None"""
        assert self.repo.get_date_range("999999.SZ") is None

    def test_get_trading_days(self):
        """测试获取交易日列表"""
        trading_days = self.repo.get_trading_days("2024-01-01", "2024-01-31")

        assert isinstance(trading_days, list)
        if len(trading_days) > 0:
            # 验证日期格式
            assert len(trading_days[0]) == 10  # YYYY-MM-DD

            # 验证按升序排列
            if len(trading_days) > 1:
                assert trading_days[0] <= trading_days[1]

    def test_get_trading_days_with_symbol(self):
        """测试 symbol 过滤路径（data_gap_detector 生产调用形式）"""
        # 无数据的股票应返回空列表（不抛异常、不返回全市场交易日）
        days = self.repo.get_trading_days(
            "2024-01-01", "2024-01-31", symbol="999999.SZ"
        )
        assert days == []

        all_days = self.repo.get_trading_days("2024-01-01", "2024-01-31")
        if all_days:
            # 有数据股票的交易日必为全市场交易日的子集
            days_with_data = self.repo.get_trading_days(
                "2024-01-01", "2024-01-31", symbol="000001.SZ"
            )
            assert set(days_with_data) <= set(all_days)

    def test_get_kline_stats(self):
        """测试获取K线统计信息"""
        stats = self.repo.get_kline_stats("000001.SZ", "2024-01-01", "2024-01-31")

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

    # ==================== 边界条件测试 ====================

    def test_get_daily_klines_same_date(self):
        """测试开始日期和结束日期相同"""
        df = self.repo.get_daily_klines("000001.SZ", "2024-01-02", "2024-01-02")
        assert isinstance(df, pl.DataFrame)
        # 应该返回0或1条记录
        assert df.height <= 1

    def test_get_daily_klines_future_date(self):
        """测试未来日期"""
        df = self.repo.get_daily_klines("000001.SZ", "2030-01-01", "2030-12-31")
        # 未来日期应该返回空DataFrame
        assert df.height == 0

    def test_get_daily_klines_reverse_date_range(self):
        """测试反向日期范围（开始日期晚于结束日期）"""
        df = self.repo.get_daily_klines("000001.SZ", "2024-01-31", "2024-01-01")
        # 反向日期范围应该返回空DataFrame
        assert df.height == 0

    def test_batch_get_recent_klines(self):
        """测试批量查询最近N天K线数据"""
        from datetime import datetime, timedelta

        # 准备测试数据
        symbols = ['000001.SH', '600036.SH', '601318.SH']
        days = 120

        # 插入测试K线数据
        for symbol in symbols:
            klines_to_insert = []
            for i in range(days):
                date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
                klines_to_insert.append({
                    'symbol': symbol,
                    'trade_date': date,
                    'open': 100.0,
                    'high': 105.0,
                    'low': 95.0,
                    'close': 102.0,
                    'volume': 1000000,
                    'amount': 102000000.0,
                    'turnover_rate': 0.5
                })

            # 批量插入测试数据
            try:
                self.repo.save_daily_klines(klines_to_insert)
            except Exception as e:
                pytest.skip(f"数据库写入测试跳过: {str(e)}")

        # 执行批量查询
        result = self.repo.batch_get_recent_klines(symbols, days)

        # 验证结果（result 键保持入参 symbol 格式；行内 symbol 为无后缀归一化值）
        assert isinstance(result, dict)
        assert len(result) == 3
        for symbol in symbols:
            assert symbol in result
            assert isinstance(result[symbol], list)
            # 验证返回的数据量必须等于days
            assert len(result[symbol]) == days
            if len(result[symbol]) > 0:
                assert result[symbol][0]['symbol'] == symbol.split('.')[0]
                # 验证按日期升序排列
                if len(result[symbol]) > 1:
                    assert result[symbol][0]['trade_date'] <= result[symbol][1]['trade_date']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
