# tests/repositories/test_strategy_weight_repository.py
# 2026-08-04 重写：对齐 StrategyWeightORMRepository 当前 API
# （无参构造；get_static_weight 为生产唯一调用——strategy_weight_adjuster）。
# 旧 get_all_for_style/get_all_for_strategy/update_weight 无生产调用方，删除。
import pytest
from adapters.outbound.repositories import StrategyWeightORMRepository
from adapters.outbound.repositories.strategy_weight_repository import StrategyWeightConfig


@pytest.fixture
def repo():
    return StrategyWeightORMRepository()


@pytest.fixture
def weight_row(repo):
    """插入一条测试权重配置，测试后清理"""
    row = StrategyWeightConfig(
        strategy_type='test_tf_unit',
        market_style='test_momentum_unit',
        static_weight=0.6,
        is_active=True,
    )
    repo.session.add(row)
    repo.session.commit()
    yield row
    repo.session.query(StrategyWeightConfig).filter_by(id=row.id).delete()
    repo.session.commit()


class TestGetStaticWeight:
    """get_static_weight（生产调用：strategy_weight_adjuster）"""

    def test_returns_weight_when_active(self, repo, weight_row):
        w = repo.get_static_weight('test_tf_unit', 'test_momentum_unit')
        assert w == pytest.approx(0.6)

    def test_returns_none_when_not_found(self, repo):
        assert repo.get_static_weight('nonexistent_type', 'nonexistent_style') is None

    def test_returns_none_when_inactive(self, repo, weight_row):
        """停用配置视为不存在（is_active 过滤）"""
        weight_row.is_active = False
        repo.session.commit()
        assert repo.get_static_weight('test_tf_unit', 'test_momentum_unit') is None


class TestGetWeights:
    def test_returns_only_active(self, repo, weight_row):
        rows = repo.get_weights('default')
        assert isinstance(rows, list)
        assert all(r['is_active'] for r in rows)
        assert any(r['strategy_type'] == 'test_tf_unit' for r in rows)
