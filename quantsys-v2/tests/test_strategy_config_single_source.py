"""策略参数单一来源 + 生效值可见（REQ-261004154902-a7cd · FR-5 · t-979319）

覆盖三条判据：

1. **运行时值 = 声明值**：`StrategyService._create_trader` 必须把声明源的**全部**策略参数
   覆盖到 trader **真正读取**的位置（`trader.config['strategy']` 与 `risk_controller.*`）。
   历史 bug：只覆盖 `rebalance_days` 与 `single_stop_loss` → 账户实际持 **5** 只，而声明 **8** 只。
   ——用假 config 字典 + 打桩 trader，**不连数据库**。
2. **一致性检查器**：声明 == 生效退 0；「声明≠生效」退 2；缺键无法判定退 3（不假装通过）。
3. **声明源失真数字已改正**：`v13.yaml` 的 `factors_count` == 真实因子数/模型特征数（75）；
   无人读取的 `min_score` 已删除并注明理由。

全部用例零数据库写入、零真实通知。
"""
from __future__ import annotations

import copy
import json
import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECKER = PROJECT_ROOT / 'tools' / 'check_strategy_config_effective.py'
V13_YAML = PROJECT_ROOT / 'live_trading' / 'configs' / 'strategies' / 'v13.yaml'
V14_YAML = PROJECT_ROOT / 'live_trading' / 'configs' / 'strategies' / 'v14.yaml'
EXECUTION_YAML = PROJECT_ROOT / 'live_trading' / 'config_simulation.yaml'
VALID_FACTORS = PROJECT_ROOT / 'live_trading' / 'models' / 'valid_factors.json'
V13_MODEL = PROJECT_ROOT / 'live_trading' / 'models' / 'v13_model.json'

#: 执行环境（config_simulation.yaml）里的策略类参数——即历史 bug 中「静默生效」的那份
_EXECUTION_DEFAULTS = {
    'strategy': {'rebalance_days': 7},
    'risk_control': {
        'top_n': 5,
        'single_stock_stop_loss': -0.12,
        'portfolio_stop_loss': -0.20,
        'max_position': 0.90,
        'min_position': 0.70,
        'max_single_weight': 0.18,
    },
}


def _bare_service():
    """不触发任何 IO 的 StrategyService（沿用既有测试的 __new__ 写法）。"""
    from application.services.strategy_service import StrategyService

    service = StrategyService.__new__(StrategyService)
    service._configs_cache = {}
    service.config_dir = PROJECT_ROOT / 'live_trading' / 'configs' / 'strategies'
    return service


def _v13_like_config() -> dict:
    """v13 声明源的等价字典（值取自 live_trading/configs/strategies/v13.yaml）。"""
    return {
        'strategy': {'name': 'V13 XGBoost Multi-Factor', 'account_name': 'v13_simulation'},
        'model': {'model_path': 'live_trading/models/v13_model.json',
                  'factors_path': 'live_trading/models/valid_factors.json',
                  'factor_calculator': 'v13', 'factors_count': 75},
        'trading': {'rebalance_days': 5, 'max_positions': 8,
                    'max_position_pct': 0.85, 'top_n': 8},
        'risk': {'single_stock_stop_loss': -0.15, 'portfolio_stop_loss': -0.20,
                 'single_stock_weight': 0.15, 'min_position': 0.70},
    }


def _v14_like_config() -> dict:
    """v14 声明源的等价字典（值取自 live_trading/configs/strategies/v14.yaml）。"""
    return {
        'strategy': {'name': 'V14', 'account_name': 'v14_simulation'},
        'model': {'model_path': 'live_trading/models/v14_p0_model.json',
                  'factors_path': 'live_trading/models/v14_p0_valid_factors.json',
                  'factor_calculator': 'v14', 'factors_count': 75},
        'trading': {'rebalance_days': 7, 'max_positions': 5,
                    'max_position_pct': 0.90, 'top_n': 5},
        'risk': {'single_stock_stop_loss': -0.12, 'portfolio_stop_loss': -0.20,
                 'single_stock_weight': 0.18},
    }


def _stub_trader() -> MagicMock:
    """打桩 trader：配置字典与 risk_controller 都是「可写可读」的普通对象（不连库）。"""
    trader = MagicMock()
    trader.account_name = 'v13_simulation'
    trader.config = copy.deepcopy(_EXECUTION_DEFAULTS)
    trader.risk_controller = SimpleNamespace(
        top_n=5, single_stop_loss=-0.12, portfolio_stop_loss=-0.20,
        max_position=0.90, min_position=0.70, max_single_weight=0.18,
    )
    return trader


def _run_checker(*args: str) -> subprocess.CompletedProcess:
    """以子进程方式跑检查器（不传 --deep = 不连库）。"""
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180,
    )


# ── ① 运行时值 = 声明值（本卡核心判据） ─────────────────────────────────────

def test_create_trader_overrides_every_declared_param():
    """全量覆盖：top_n / 止损 / 仓位 / 权重 / 调仓周期 一律取声明源（而非执行环境）"""
    service = _bare_service()
    stub = _stub_trader()

    with patch('application.services.strategy_service.SimulationTrader',
               return_value=stub) as MockTrader:
        trader = service._create_trader(_v13_like_config())

    # trader 真正读取的位置
    assert trader.config['strategy']['rebalance_days'] == 5        # 声明 5（执行环境写 7）
    assert trader.risk_controller.top_n == 8                       # 声明 8（执行环境写 5）★本卡核心
    assert trader.risk_controller.single_stop_loss == pytest.approx(-0.15)
    assert trader.risk_controller.portfolio_stop_loss == pytest.approx(-0.20)
    assert trader.risk_controller.max_position == pytest.approx(0.85)      # 执行环境写 0.90
    assert trader.risk_controller.min_position == pytest.approx(0.70)
    assert trader.risk_controller.max_single_weight == pytest.approx(0.15)  # 执行环境写 0.18

    # config 字典同步覆盖（生效值可见：任何人读 trader.config 都不会再看到 5 只）
    assert trader.config['risk_control']['top_n'] == 8
    assert trader.config['risk_control']['max_position'] == pytest.approx(0.85)

    # 账户/因子计算器仍走构造注入
    _, ctor_kwargs = MockTrader.call_args
    assert ctor_kwargs['account_name'] == 'v13_simulation'
    assert ctor_kwargs['factor_calculator'] == 'v13'


def test_create_trader_is_per_strategy_not_global():
    """覆盖值取各自声明源：v14 生效 top_n=5，不得被 v13 的 8 污染"""
    service = _bare_service()
    stub = _stub_trader()
    stub.config = copy.deepcopy(_EXECUTION_DEFAULTS)

    with patch('application.services.strategy_service.SimulationTrader', return_value=stub):
        trader = service._create_trader(_v14_like_config())

    assert trader.config['strategy']['rebalance_days'] == 7
    assert trader.risk_controller.top_n == 5
    assert trader.risk_controller.single_stop_loss == pytest.approx(-0.12)
    assert trader.risk_controller.max_single_weight == pytest.approx(0.18)


def test_declared_params_missing_key_is_none_not_guessed():
    """声明源没写的键 → None（不猜默认值），从而沿用执行环境并被告警"""
    from application.services.strategy_service import StrategyService

    declared = StrategyService.declared_params(_v14_like_config())
    assert declared['min_position'] is None          # v14.yaml 未声明 min_position
    assert declared['top_n'] == 5
    assert declared['max_position'] == pytest.approx(0.90)


def test_apply_declared_overrides_reports_before_and_is_in_place():
    """纯函数契约：就地覆盖 trader 的配置，并回报覆盖前/后取值（检查器靠它算生效值）"""
    from application.services.strategy_service import StrategyService

    declared = StrategyService.declared_params(_v13_like_config())
    execution = copy.deepcopy(_EXECUTION_DEFAULTS)
    before_snapshot = copy.deepcopy(execution)

    result = StrategyService.apply_declared_overrides(execution, declared)

    assert result['before']['top_n'] == 5            # 覆盖前的执行环境值
    assert result['effective']['top_n'] == 8         # 覆盖后的生效值
    assert result['before']['max_single_weight'] == pytest.approx(0.18)
    assert result['effective']['max_single_weight'] == pytest.approx(0.15)
    # 就地写入（trader 读的就是这个 dict）；声明源本身不被改动
    assert execution['risk_control']['top_n'] == 8
    assert before_snapshot['risk_control']['top_n'] == 5
    assert declared['top_n'] == 8


def test_create_trader_accepts_caller_overrides():
    """调用方显式覆盖（含历史参数名 stop_loss_pct）优先级最高"""
    service = _bare_service()
    stub = _stub_trader()

    with patch('application.services.strategy_service.SimulationTrader', return_value=stub):
        trader = service._create_trader(_v13_like_config(), top_n=3, stop_loss_pct=-0.05)

    assert trader.risk_controller.top_n == 3
    assert trader.risk_controller.single_stop_loss == pytest.approx(-0.05)


def test_dead_kwargs_are_loud(caplog):
    """死参数（enable_stop_loss / enable_rebalance）要求关闭时必须响亮——不许静默忽略"""
    service = _bare_service()
    stub = _stub_trader()

    with caplog.at_level(logging.WARNING, logger='application.services.strategy_service'):
        with patch('application.services.strategy_service.SimulationTrader', return_value=stub):
            service._create_trader(_v13_like_config(),
                                   enable_rebalance=False, enable_stop_loss=False)

    messages = '\n'.join(record.getMessage() for record in caplog.records)
    assert 'enable_rebalance' in messages and '不生效' in messages
    assert 'enable_stop_loss' in messages


def test_effective_params_are_logged(caplog):
    """生效值可见：日志必须逐项打印「声明值 / 执行环境 / 生效值」，并对不一致项告警"""
    service = _bare_service()
    stub = _stub_trader()

    with caplog.at_level(logging.INFO, logger='application.services.strategy_service'):
        with patch('application.services.strategy_service.SimulationTrader', return_value=stub):
            service._create_trader(_v13_like_config())

    text = '\n'.join(record.getMessage() for record in caplog.records)
    assert '策略参数单一来源核对' in text
    assert '声明值' in text and '生效值' in text
    # top_n 声明 8 / 执行环境 5 → 必须有一条说明以哪份为准的告警
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any('top_n' in m and '以声明源为准' in m for m in warnings)


# ── ② 一致性检查器（声明 vs 生效） ─────────────────────────────────────────

def test_checker_exit_0_when_declared_equals_effective():
    """当前仓库配置：三个受检参数声明 == 生效 → 退 0"""
    completed = _run_checker('--strategy', 'v13')

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '✅ 声明 == 生效' in completed.stdout


def test_checker_exit_2_when_declared_not_effective(tmp_path):
    """声明≠生效必须退 2。

    2026-10-04 修正：本用例原先直接依赖「线上 v13.yaml 声明 8、执行环境 5」这一**当时的历史形态**；
    用户裁定「保留 5 只」后声明源已改成 5，该前提消失。改为**合成一份声明源**（top_n=8）
    来复现「声明 8 ≠ 生效 5」，这样它测的是**检查器的检测能力**，而不是线上配置恰好处于哪种状态。
    """
    config = yaml.safe_load(V13_YAML.read_text(encoding='utf-8'))
    config['trading']['top_n'] = 8
    config['trading']['max_positions'] = 8
    declared_8 = tmp_path / 'v13_declared_8.yaml'
    declared_8.write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')

    # 只覆盖 rebalance_days + stop_loss（历史覆盖集）→ top_n 生效值取执行环境的 5
    completed = _run_checker('--strategy-config', str(declared_8),
                             '--keys', 'rebalance_days,single_stock_stop_loss')

    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert 'MISMATCH' in completed.stdout
    assert 'top_n' in completed.stdout
    # 合成声明源写 8，执行环境是 5 → 报「声明 8 ≠ 生效 5」
    assert '声明 8 ≠ 生效 5' in completed.stdout


def test_checker_exit_3_when_declaration_missing_key(tmp_path):
    """声明源缺受检键 → 无法判定 → 退 3（不许假装通过）"""
    config = yaml.safe_load(V13_YAML.read_text(encoding='utf-8'))
    config['trading'].pop('top_n')
    config['trading'].pop('max_positions')
    broken = tmp_path / 'v13_without_top_n.yaml'
    broken.write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')

    completed = _run_checker('--strategy-config', str(broken))

    assert completed.returncode == 3, completed.stdout + completed.stderr
    assert '无法判定' in completed.stdout
    assert 'top_n' in completed.stdout


def test_checker_check_configs_detects_mismatch_without_database():
    """检查器核心是纯函数：喂「声明 8 / 执行环境 5 + 旧覆盖集」即判 2（零 DB 依赖）"""
    tool = _load_checker_module()
    declared = _v13_like_config()
    result = tool.check_configs(declared, copy.deepcopy(_EXECUTION_DEFAULTS),
                                keys=('rebalance_days', 'single_stock_stop_loss'))

    assert result['mismatches'] == ['top_n']
    assert result['undetermined'] == []
    top_n_row = next(row for row in result['rows'] if row['key'] == 'top_n')
    assert top_n_row['declared'] == 8 and top_n_row['effective'] == 5


def test_checker_check_configs_ok_with_full_coverage():
    """全量覆盖表 → 三项一致（同样不连库）"""
    tool = _load_checker_module()
    result = tool.check_configs(_v13_like_config(), copy.deepcopy(_EXECUTION_DEFAULTS))

    assert result['mismatches'] == [] and result['undetermined'] == []


def _load_checker_module():
    """按路径导入检查器（tools/ 不是包）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location('check_strategy_config_effective', CHECKER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ── ③ 声明源失真数字已改正 ────────────────────────────────────────────────

def test_v13_declared_factor_count_matches_real_artifacts():
    """factors_count 必须等于真实因子数（原写 68，失真已改正为 75）"""
    config = yaml.safe_load(V13_YAML.read_text(encoding='utf-8'))
    valid_factors = json.loads(VALID_FACTORS.read_text(encoding='utf-8'))

    assert config['model']['factors_count'] == len(valid_factors) == 75

    import xgboost as xgb

    model = xgb.XGBRegressor()
    model.load_model(str(V13_MODEL))          # load_model 就地加载，返回 None
    assert model.get_booster().num_features() == 75


def test_v13_min_score_removed_with_reason():
    """无人读取的 min_score 已删除（声明一个没人读的阈值正是本需求要消灭的假声明）"""
    config = yaml.safe_load(V13_YAML.read_text(encoding='utf-8'))
    assert 'min_score' not in config['trading']
    assert 'min_score' in V13_YAML.read_text(encoding='utf-8')   # 留注释说明理由


def test_config_simulation_is_marked_as_execution_only():
    """执行环境文件必须显式标注「策略参数以声明源为准」，避免再被当作生效值来源"""
    text = EXECUTION_YAML.read_text(encoding='utf-8')

    assert '执行环境配置' in text
    assert 'configs/strategies/<name>.yaml' in text
    # 冲突项就地标注（不得再出现「静默的第二份声明」）
    assert '⚠️ 兜底值' in text or '兜底值' in text
