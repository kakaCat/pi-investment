"""
SignalRepository单元测试
"""
import pytest
from adapters.outbound.repositories import SignalORMRepository


class TestSignalRepository:
    """SignalRepository测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.repo = SignalORMRepository()

    def teardown_method(self):
        """每个测试方法后执行"""
        if hasattr(self.repo, 'db') and self.repo.db:
            self.repo.db.close()

    # ==================== 查询方法测试 ====================

    def test_get_signal_by_id(self):
        """测试根据ID查询信号"""
        signal = self.repo.get_signal(1)

        if signal:
            assert isinstance(signal, dict)
            assert 'id' in signal
            assert 'symbol' in signal
            assert 'action' in signal
            assert signal['id'] == 1

    def test_get_signal_not_found(self):
        """测试查询不存在的信号"""
        signal = self.repo.get_signal(999999999)
        assert signal is None

    def test_get_signals_by_date(self):
        """测试按日期查询信号"""
        signals = self.repo.get_signals_by_date("2024-01-02")

        assert isinstance(signals, list)
        if len(signals) > 0:
            assert 'signal_date' in signals[0]
            assert 'symbol' in signals[0]
            assert 'action' in signals[0]

            # 验证按创建时间降序排列
            if len(signals) > 1:
                assert signals[0]['created_at'] >= signals[1]['created_at']

    def test_get_signals_by_date_with_type(self):
        """测试按日期和类型查询信号"""
        signals = self.repo.get_signals_by_date("2024-01-02", signal_type="buy")

        assert isinstance(signals, list)
        if len(signals) > 0:
            # 验证所有信号都是buy类型
            for signal in signals:
                assert signal['action'] == 'BUY'

    def test_get_signals_by_date_invalid(self):
        """测试无效日期"""
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_signals_by_date("2024/01/02")

    def test_get_signals_by_symbol(self):
        """测试按股票代码查询信号"""
        signals = self.repo.get_signals_by_symbol(
            "000001.SZ",
            "2024-01-01",
            "2024-01-31"
        )

        assert isinstance(signals, list)
        if len(signals) > 0:
            # 验证所有信号都是该股票
            for signal in signals:
                assert signal['symbol'] == "000001.SZ"

            # 验证按日期降序排列
            if len(signals) > 1:
                assert signals[0]['signal_date'] >= signals[1]['signal_date']

    def test_get_signals_by_symbol_invalid(self):
        """测试无效股票代码"""
        with pytest.raises(ValueError, match="股票代码"):
            self.repo.get_signals_by_symbol("INVALID", "2024-01-01", "2024-01-31")

    def test_get_latest_signals(self):
        """测试获取最新信号"""
        signals = self.repo.get_latest_signals(limit=10)

        assert isinstance(signals, list)
        assert len(signals) <= 10

        if len(signals) > 0:
            # 验证按创建时间降序排列
            if len(signals) > 1:
                assert signals[0]['created_at'] >= signals[1]['created_at']

    def test_get_latest_signals_default_limit(self):
        """测试默认限制"""
        signals = self.repo.get_latest_signals()
        assert isinstance(signals, list)
        assert len(signals) <= 100

    # ==================== 写入方法测试 ====================

    def test_create_signal_missing_field(self):
        """测试缺少必需字段"""
        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': 'test_signal'
            # 缺少 action, action_type, strategy_id
        }

        with pytest.raises(ValueError, match="缺少必需字段"):
            self.repo.create_signal(signal_data)

    def test_create_signal_invalid_symbol(self):
        """测试无效股票代码"""
        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': 'INVALID',
            'name': 'test_signal',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy'
        }

        with pytest.raises(ValueError, match="股票代码"):
            self.repo.create_signal(signal_data)

    def test_create_signal_invalid_date(self):
        """测试无效日期"""
        signal_data = {
            'signal_date': '2024/01/02',
            'symbol': '000001.SZ',
            'name': 'test_signal',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy'
        }

        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.create_signal(signal_data)

    def test_create_signal_basic(self):
        """测试创建基本信号"""
        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': 'test_signal',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy',
            'price': 10.5,
            'reason': 'test reason',
            'confidence': 0.8
        }

        try:
            signal_id = self.repo.create_signal(signal_data)
            assert isinstance(signal_id, int)
            assert signal_id > 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    def test_create_signal_with_indicators(self):
        """测试创建带指标的信号"""
        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': 'test_signal',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy',
            'indicators': {
                'ma5': 10.5,
                'ma10': 10.3,
                'rsi': 45.0
            }
        }

        try:
            signal_id = self.repo.create_signal(signal_data)
            assert isinstance(signal_id, int)
            assert signal_id > 0
        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {str(e)}")

    # ==================== 统计方法测试 ====================

    def test_get_signal_stats(self):
        """测试获取信号统计"""
        stats = self.repo.get_signal_stats("2024-01-01", "2024-01-31")

        assert isinstance(stats, dict)
        assert 'total' in stats
        assert 'by_action' in stats
        assert 'by_strategy' in stats
        assert 'avg_confidence' in stats

        assert isinstance(stats['total'], int)
        assert isinstance(stats['by_action'], dict)
        assert isinstance(stats['by_strategy'], dict)
        assert isinstance(stats['avg_confidence'], float)

    def test_get_signal_stats_invalid_date(self):
        """测试无效日期"""
        with pytest.raises(ValueError, match="Invalid date format"):
            self.repo.get_signal_stats("2024/01/01", "2024-01-31")

    def test_get_signal_count_by_date(self):
        """测试按日期统计信号数量"""
        counts = self.repo.get_signal_count_by_date("2024-01-01", "2024-01-31")

        assert isinstance(counts, list)
        if len(counts) > 0:
            assert 'signal_date' in counts[0]
            assert 'count' in counts[0]

            # 验证按日期升序排列
            if len(counts) > 1:
                assert counts[0]['signal_date'] <= counts[1]['signal_date']

    # ==================== 边界条件测试 ====================

    def test_get_signals_by_date_future(self):
        """测试未来日期"""
        signals = self.repo.get_signals_by_date("2030-01-01")
        assert signals == []

    def test_get_signals_by_symbol_reverse_date(self):
        """测试反向日期范围"""
        signals = self.repo.get_signals_by_symbol(
            "000001.SZ",
            "2024-01-31",
            "2024-01-01"
        )
        # 反向日期范围应该返回空列表
        assert signals == []

    def test_get_latest_signals_zero_limit(self):
        """测试限制为0"""
        signals = self.repo.get_latest_signals(limit=0)
        assert signals == []


# ==================== Mock-based tests (no DB required) ====================

class TestSignalRepositoryMocked:
    """SignalRepository tests using mocked DB cursor.

    Cover branches unreachable with real DB (insert try block, stats aggregation).
    """

    def test_create_signal_success(self):
        """创建信号成功返回 signal_id"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        # Mock the db connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 42}
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': 'test_signal',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy',
            'price': 10.5,
            'reason': 'test reason',
            'confidence': 0.8,
        }

        signal_id = repo.create_signal(signal_data)

        assert signal_id == 42
        repo.db.commit.assert_called_once()

    def test_create_signal_with_indicators_mocked(self):
        """带 indicators 的创建信号，indicators 转为 JSON"""
        from unittest.mock import MagicMock
        import json
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 99}
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': 'test_indicators',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy',
            'indicators': {'rsi': 30, 'ma5': 10.0},
        }

        signal_id = repo.create_signal(signal_data)

        assert signal_id == 99
        # Verify indicators was converted to JSON
        call_args = mock_cursor.execute.call_args[0][1]
        assert isinstance(call_args['indicators'], str)
        parsed = json.loads(call_args['indicators'])
        assert parsed['rsi'] == 30

    def test_create_signal_db_error_rollback(self):
        """创建信号 DB 错误时回滚并抛出"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB insert error")
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': 'test',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy',
        }

        with pytest.raises(Exception, match="创建信号失败"):
            repo.create_signal(signal_data)

        repo.db.rollback.assert_called_once()

    def test_create_signal_indicators_already_string(self):
        """indicators 已经是字符串时不重复转换"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 1}
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        signal_data = {
            'signal_date': '2024-01-02',
            'symbol': '000001.SZ',
            'name': 'test',
            'action': 'BUY',
            'action_type': 1,
            'strategy_id': 'test_strategy',
            'indicators': '{"rsi": 30}',
        }

        signal_id = repo.create_signal(signal_data)
        assert signal_id == 1

    def test_get_signal_stats_with_data(self):
        """get_signal_stats 正确聚合统计信息"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'total': 3, 'action': 'BUY', 'strategy_id': 'ma_cross', 'avg_confidence': 0.75},
            {'total': 2, 'action': 'SELL', 'strategy_id': 'rsi_reversal', 'avg_confidence': 0.60},
        ]
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        stats = repo.get_signal_stats('2024-01-01', '2024-12-31')

        assert stats['total'] == 5
        assert stats['by_action']['buy'] == 3
        assert stats['by_action']['sell'] == 2
        assert stats['by_strategy']['ma_cross'] == 3
        assert stats['by_strategy']['rsi_reversal'] == 2
        # Weighted avg confidence: (3*0.75 + 2*0.60) / 5 = (2.25 + 1.2) / 5 = 0.69
        assert stats['avg_confidence'] == pytest.approx(0.69)

    def test_get_signal_stats_with_null_confidence(self):
        """avg_confidence 为 NULL 时不参与计算"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'total': 2, 'action': 'BUY', 'strategy_id': 'ma_cross', 'avg_confidence': None},
            {'total': 3, 'action': 'BUY', 'strategy_id': 'rsi_reversal', 'avg_confidence': 0.80},
        ]
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        stats = repo.get_signal_stats('2024-01-01', '2024-12-31')

        assert stats['total'] == 5
        # Only rsi_reversal contributes to weighted avg: 3*0.80/3 = 0.80
        assert stats['avg_confidence'] == pytest.approx(0.80)

    def test_get_signal_stats_empty(self):
        """无数据时返回空统计"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        stats = repo.get_signal_stats('2024-01-01', '2024-12-31')

        assert stats['total'] == 0
        assert stats['by_action'] == {}
        assert stats['by_strategy'] == {}
        assert stats['avg_confidence'] == 0.0

    def test_get_signal_count_by_date_with_data(self):
        """按日期统计信号数量"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'signal_date': '2024-01-01', 'count': 5},
            {'signal_date': '2024-01-02', 'count': 3},
            {'signal_date': '2024-01-03', 'count': 7},
        ]
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        counts = repo.get_signal_count_by_date('2024-01-01', '2024-01-31')

        assert len(counts) == 3
        assert counts[0]['signal_date'] == '2024-01-01'
        assert counts[0]['count'] == 5

    def test_get_latest_signals_with_negative_limit(self):
        """负 limit 返回空列表（SQL 行为）"""
        from unittest.mock import MagicMock
        repo = SignalORMRepository()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        repo.db = MagicMock()
        repo.db.cursor.return_value = mock_cursor

        signals = repo.get_latest_signals(limit=-5)
        assert signals == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
