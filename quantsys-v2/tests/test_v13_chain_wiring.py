"""V13 链路接线体检（REQ-261004154902-a7cd · FR-6 · 卡 t-373c05）

背景（已取证，本文件是它的回归锁）：`application/strategies/**` + `StrategyExecutor`
这条「更正式」的链路此前**看起来有、其实不能跑**——

1. `v13_config.py` / `v14_config.py` 的 `model_path` / `factors_path` 指向磁盘上
   **不存在**的文件 → 实测加载结果 `model=None, factors=[]`；
2. `xgboost_strategy.py` 的 `reference_capital` 硬编码 `1_000_000`，而账户本金是 10 万
   → 0.17 权重 × 10 元 = 17,000 股（10 倍超买）；
3. `strategy_trading_job.strategy_execute_all` 用 `entry.get('success', True)` 判成功，
   而 use case 返回体没有 `success` 键 → 恒判成功。

本文件把这三条钉死。**不接线、不写库、不发通知**——只断言「不再骗人 + 参数不再离谱」。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from application.strategies.v13_config import V13_CONFIG
from application.strategies.v14_config import V14_CONFIG
from domain.strategies.value_objects import Signal, SignalAction, StrategyConfig
from domain.strategies.xgboost_strategy import (
    DEFAULT_MIN_FACTOR_COVERAGE,
    FALLBACK_REFERENCE_CAPITAL,
    XGBoostStrategy,
)

JOB_LOGGER = "infrastructure.jobs.strategy_trading_job"


# ---------------------------------------------------------------------------
# ① 两个路径都存在（改前：都不存在 → 加载恒为空）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "config",
    [V13_CONFIG, V14_CONFIG],
    ids=lambda c: c.version,
)
def test_model_and_factors_paths_exist(config):
    assert Path(config.model_path).exists(), f"{config.version} model_path 不存在: {config.model_path}"
    assert Path(config.factors_path).exists(), (
        f"{config.version} factors_path 不存在: {config.factors_path}"
    )
    # 改前的两个具体坏路径，必须不再被引用
    assert "xgboost_multi_factor_model.json" not in config.model_path
    assert config.factors_path != "config/v13_factors.json"
    assert config.factors_path != "config/v14_factors.json"


# ---------------------------------------------------------------------------
# ② 模型特征数与因子清单一致（否则 reindex 后列对不上）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "config",
    [V13_CONFIG, V14_CONFIG],
    ids=lambda c: c.version,
)
def test_model_num_feature_matches_factor_list(config):
    model_json = json.loads(Path(config.model_path).read_text(encoding="utf-8"))
    num_feature = int(model_json["learner"]["learner_model_param"]["num_feature"])

    factors = json.loads(Path(config.factors_path).read_text(encoding="utf-8"))
    assert isinstance(factors, list) and factors, "因子清单必须是非空 JSON 列表"
    assert len(factors) == len(set(factors)), "因子清单存在重复项"

    assert num_feature == len(factors), (
        f"{config.version}: 模型 num_feature={num_feature} 但因子清单 {len(factors)} 项"
    )


# ---------------------------------------------------------------------------
# ③ reference_capital 不再硬编码 1e6（改为配置注入）
# ---------------------------------------------------------------------------
def test_reference_capital_is_injected_from_config():
    assert V13_CONFIG.params["reference_capital"] == 100_000.0
    assert V14_CONFIG.params["reference_capital"] == 100_000.0

    strategy = XGBoostStrategy(config=V13_CONFIG)
    assert strategy._resolve_reference_capital() == V13_CONFIG.params["reference_capital"]
    assert strategy._resolve_reference_capital() != 1_000_000.0


def test_reference_capital_fallback_is_conservative_and_explicit():
    """拿不到配置时用**显式且保守**的 10 万，而不是默认超买的 1e6。"""
    bare_config = StrategyConfig(name="bare", version="V0")
    strategy = XGBoostStrategy(config=bare_config)

    resolved = strategy._resolve_reference_capital()
    assert resolved == FALLBACK_REFERENCE_CAPITAL == 100_000.0
    assert resolved != 1_000_000.0


def test_reference_capital_rejects_non_positive():
    bad_config = StrategyConfig(
        name="bad", version="V0", params={"reference_capital": 0}
    )
    with pytest.raises(ValueError):
        XGBoostStrategy(config=bad_config)._resolve_reference_capital()


def test_source_no_longer_hardcodes_one_million():
    """源码级回归锁：算法里不得再出现 1e6 这个本金字面量。

    用 AST 扫**数字字面量**（注释/文档字符串里提到历史值不算），
    避免「注释里写了 1_000_000 就判失败」这种假阳性。
    """
    import ast

    tree = ast.parse(Path("domain/strategies/xgboost_strategy.py").read_text(encoding="utf-8"))
    numbers = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
    }
    assert 1_000_000 not in numbers
    assert 1_000_000.0 not in numbers


def test_order_sizing_uses_injected_capital_not_one_million():
    """0.17 权重 × 10 元：注入 10 万 → 1,700 股；改前的 100 万会算出 17,000 股。"""
    strategy = XGBoostStrategy(config=V13_CONFIG)
    signal = Signal(
        symbol="600000.SH",
        action=SignalAction.BUY,
        weight=0.17,
        score=1.0,
        reason="test",
        metadata={"price": 10.0},
    )
    orders = strategy.generate_orders([signal])
    assert len(orders) == 1
    assert orders[0].quantity == 1_700
    assert orders[0].quantity != 17_000


# ---------------------------------------------------------------------------
# ③b 因子覆盖度过低必须显式失败（不再静默 fillna(0) 继续预测）
# ---------------------------------------------------------------------------
class _StubModel:
    """最小可用的假模型：记录被喂进来的特征矩阵。"""

    def __init__(self) -> None:
        self.seen_columns = None

    def predict(self, features):  # noqa: ANN001, ANN201
        self.seen_columns = list(features.columns)
        return [0.0] * len(features)


def _strategy_with_stub_model(config=V13_CONFIG, n_factors: int = 8):
    strategy = XGBoostStrategy(config=config)
    strategy.model = _StubModel()
    strategy.factors = [f"f{i}" for i in range(n_factors)]
    return strategy


def test_predict_returns_refuses_low_factor_coverage():
    import pandas as pd

    strategy = _strategy_with_stub_model(n_factors=8)  # 覆盖度 3/8 = 37.5% < 50%
    frame = pd.DataFrame({f"f{i}": [1.0] for i in range(3)})

    with pytest.raises(ValueError, match="factor coverage"):
        strategy._predict_returns(frame)


def test_predict_returns_still_predicts_above_threshold():
    import pandas as pd

    strategy = _strategy_with_stub_model(n_factors=8)  # 覆盖度 5/8 = 62.5% >= 50%
    frame = pd.DataFrame({f"f{i}": [1.0] for i in range(5)})

    result = strategy._predict_returns(frame)

    assert list(result) == [0.0]
    assert strategy.model.seen_columns == [f"f{i}" for i in range(8)]


def test_predict_returns_threshold_is_configurable():
    import pandas as pd

    config = StrategyConfig(
        name="strict", version="V0", params={"min_factor_coverage": 0.9}
    )
    strategy = _strategy_with_stub_model(config=config, n_factors=8)  # 5/8 = 62.5% < 90%
    frame = pd.DataFrame({f"f{i}": [1.0] for i in range(5)})

    with pytest.raises(ValueError, match="factor coverage"):
        strategy._predict_returns(frame)


def test_default_min_factor_coverage_is_documented_value():
    assert DEFAULT_MIN_FACTOR_COVERAGE == 0.5


# ---------------------------------------------------------------------------
# ④ strategy_execute_all 对缺 ok 的返回体判失败（改前：恒判成功）
# ---------------------------------------------------------------------------
def test_classify_strategy_entry_missing_keys_is_failed():
    from infrastructure.jobs.strategy_trading_job import (
        ENTRY_FAILED,
        ENTRY_SKIPPED,
        ENTRY_SUCCESS,
        classify_strategy_entry,
    )

    # 改前的 use case 返回体形状（没有 success / ok / status）→ 必须判失败
    legacy_payload = {"date": "2026-10-05", "orders": [], "signals": []}
    status, reason = classify_strategy_entry(legacy_payload)
    assert status == ENTRY_FAILED
    assert "missing" in reason

    # 改前的写法 entry.get('success', True) 会判成功 —— 明确钉住这个反向行为
    assert legacy_payload.get("success", True) is True

    assert classify_strategy_entry({"ok": False, "reason": "model_not_loaded"})[0] == ENTRY_FAILED
    assert classify_strategy_entry({"ok": True})[0] == ENTRY_SUCCESS
    assert classify_strategy_entry({"status": "skipped"})[0] == ENTRY_SKIPPED
    assert classify_strategy_entry({"status": "success"})[0] == ENTRY_SUCCESS
    assert classify_strategy_entry({"status": "bogus"})[0] == ENTRY_FAILED
    assert classify_strategy_entry("not-a-dict")[0] == ENTRY_FAILED
    assert classify_strategy_entry({})[0] == ENTRY_FAILED


def test_strategy_execute_all_logs_missing_ok_as_failed(monkeypatch, caplog):
    """端到端：缺 ok 的条目在任务日志里必须是 failed（不是 success）。

    用假 StrategyExecutor / 假 trader 替换，避免触库、避免真发通知。
    """
    import adapters.outbound.repositories.simulation_position_repository as pos_repo_mod
    import application.strategies as strategies_pkg
    import infrastructure.jobs.strategy_trading_job as job_mod
    import live_trading.simulation_trader as trader_mod

    class _FakeExecutor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def execute_all(self, date):  # noqa: ANN001, ANN201
            return {
                "date": date,
                "success": True,  # executor 自己的汇总标志：仍然会说 True
                "V13": {"date": date, "orders": []},  # 缺 ok/status → 必须判失败
                "V14": {"ok": True, "status": "success"},  # 显式成功
            }

    monkeypatch.setattr(strategies_pkg, "StrategyExecutor", _FakeExecutor)
    monkeypatch.setattr(trader_mod, "SimulationTrader", lambda **kwargs: object())
    monkeypatch.setattr(pos_repo_mod, "SimulationPositionRepository", lambda **kwargs: object())

    with caplog.at_level(logging.INFO, logger=JOB_LOGGER):
        result = job_mod.strategy_execute_all(date="2026-10-05")

    assert result["V13"] == {"date": "2026-10-05", "orders": []}

    text = caplog.text
    assert "V13: failed" in text, text
    assert "V13: success" not in text, text
    assert "V14: success" in text, text
    assert "判定为失败的策略: V13" in text, text
