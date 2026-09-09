"""回归测试：风控规则重构后行为不变

验证 risk_rules.py 重构后，使用默认配置时的行为与原始硬编码值完全一致。
"""

import pytest
import polars as pl
from unittest.mock import Mock, MagicMock
from domain.backtest.engine.risk_rules import (
    check_position_size,
    check_portfolio_concentration,
    check_stop_loss,
    check_daily_drawdown,
    check_max_positions,
)
from infrastructure.config.constants.trading.risk_limits import RiskLimits


class TestRiskRulesRegression:
    """测试风控规则重构后行为不变"""

    def setup_method(self):
        """每个测试前设置 mock"""
        self.ds = Mock()
        # risk_rules 自 c91cd148 起统一为「ds 优先」取 repo（_resolve_repo）。
        # ds 上若残留 auto-Mock 的 kline/stock 等属性会遮蔽下方 monkeypatch 的
        # 模块级全局 repo，因此显式置 None → 这些规则回退走 0 参全局 repo
        # （回归验证的正是「全局 repo + 默认配置」这条路径）。
        self.ds.kline = None
        self.ds.stock = None
        self.ds.portfolio = None
        self.ds.risk = None
        self.ds.factor = None

    def test_check_position_size_default_behavior(self, monkeypatch):
        """测试仓位检查默认行为（20% 限制）"""
        # Mock kline repo
        mock_kline_repo = Mock()
        mock_kline_repo.get_latest_daily_kline.return_value = pl.DataFrame({"close": [10.0]})

        def mock_get_kline_repo():
            return mock_kline_repo

        monkeypatch.setattr(
            "domain.backtest.engine.risk_rules._get_kline_repo",
            mock_get_kline_repo
        )

        # 测试用例 1: 10% 仓位 - 应通过
        result = check_position_size(
            self.ds,
            symbol="600519",
            proposed_quantity=1000,  # 1000 股 * 10 元 = 10,000 元
            account_balance=100000   # 总资产 100,000 元，仓位 10%
        )
        assert result["passed"] is True
        assert result["rule"] == "position_size"

        # 测试用例 2: 25% 仓位 - 应不通过（超过 20%）
        result = check_position_size(
            self.ds,
            symbol="600519",
            proposed_quantity=2500,  # 2500 股 * 10 元 = 25,000 元
            account_balance=100000   # 总资产 100,000 元，仓位 25%
        )
        assert result["passed"] is False
        assert result["rule"] == "position_size"
        assert "20" in result["detail"]  # 错误消息应包含 20%

        # 测试用例 3: 边界值 20% - 应通过
        result = check_position_size(
            self.ds,
            symbol="600519",
            proposed_quantity=2000,  # 2000 股 * 10 元 = 20,000 元
            account_balance=100000   # 总资产 100,000 元，仓位刚好 20%
        )
        assert result["passed"] is True

    def test_check_position_size_default_account_balance(self, monkeypatch):
        """测试默认账户余额（1,000,000 元）"""
        mock_kline_repo = Mock()
        mock_kline_repo.get_latest_daily_kline.return_value = pl.DataFrame({"close": [10.0]})

        monkeypatch.setattr(
            "domain.backtest.engine.risk_rules._get_kline_repo",
            lambda: mock_kline_repo
        )

        # 当账户余额为 None 时，应使用默认值 1,000,000
        result = check_position_size(
            self.ds,
            symbol="600519",
            proposed_quantity=25000,  # 25000 股 * 10 元 = 250,000 元
            account_balance=None      # 默认 1,000,000，仓位 25%
        )
        assert result["passed"] is False  # 超过 20%

    def test_check_portfolio_concentration_default_behavior(self, monkeypatch):
        """测试行业集中度检查默认行为（40% 限制）"""
        # Mock stock repo
        mock_stock_repo = Mock()
        mock_stock_repo.get_by_symbol.return_value = {"industry": "白酒"}

        # Mock portfolio repo
        mock_portfolio_repo = Mock()
        mock_portfolio_repo.get_all_holdings.return_value = [
            {"sector": "白酒", "total_invested": 30000},  # 已有白酒仓位 30,000
        ]

        monkeypatch.setattr(
            "domain.backtest.engine.risk_rules._get_stock_repo",
            lambda: mock_stock_repo
        )
        monkeypatch.setattr(
            "domain.backtest.engine.risk_rules._get_portfolio_repo",
            lambda: mock_portfolio_repo
        )

        # 测试用例 1: 白酒 35% - 应通过
        result = check_portfolio_concentration(
            self.ds,
            symbol="600519",
            proposed_value=5000,   # 新增 5,000 元，总计 35,000
            total_value=100000     # 总资产 100,000，白酒占 35%
        )
        assert result["passed"] is True

        # 测试用例 2: 白酒 45% - 应不通过（超过 40%）
        result = check_portfolio_concentration(
            self.ds,
            symbol="600519",
            proposed_value=15000,  # 新增 15,000 元，总计 45,000
            total_value=100000     # 总资产 100,000，白酒占 45%
        )
        assert result["passed"] is False
        assert "40" in result["detail"]  # 错误消息应包含 40%

    def test_check_stop_loss_default_behavior(self):
        """测试止损检查默认行为（-8%）"""
        # 测试用例 1: 下跌 -5% - 应通过
        result = check_stop_loss(
            self.ds,
            symbol="600519",
            entry_price=100.0,
            current_price=95.0  # 下跌 -5%
        )
        assert result["passed"] is True

        # 测试用例 2: 下跌 -10% - 应不通过（超过 -8%）
        result = check_stop_loss(
            self.ds,
            symbol="600519",
            entry_price=100.0,
            current_price=90.0  # 下跌 -10%
        )
        assert result["passed"] is False
        assert "8" in result["detail"]  # 错误消息应包含 8%

        # 测试用例 3: 边界值 -8% - 应不通过
        result = check_stop_loss(
            self.ds,
            symbol="600519",
            entry_price=100.0,
            current_price=92.0  # 下跌刚好 -8%
        )
        assert result["passed"] is False

    def test_check_daily_drawdown_default_behavior(self):
        """测试日内回撤检查默认行为（5%）"""
        # 测试用例 1: 回撤 3% - 应通过
        result = check_daily_drawdown(
            self.ds,
            today_pnl=-3000,      # 亏损 3,000 元
            account_balance=100000 # 总资产 100,000 元，回撤 3%
        )
        assert result["passed"] is True

        # 测试用例 2: 回撤 6% - 应不通过（超过 5%）
        result = check_daily_drawdown(
            self.ds,
            today_pnl=-6000,      # 亏损 6,000 元
            account_balance=100000 # 总资产 100,000 元，回撤 6%
        )
        assert result["passed"] is False
        assert "5" in result["detail"]  # 错误消息应包含 5%

        # 测试用例 3: 盈利 - 应通过
        result = check_daily_drawdown(
            self.ds,
            today_pnl=5000,       # 盈利 5,000 元
            account_balance=100000
        )
        assert result["passed"] is True
        assert "盈利" in result["detail"]

    def test_check_max_positions_default_behavior(self, monkeypatch):
        """测试最大持仓数检查默认行为（10 只）"""
        mock_portfolio_repo = Mock()

        monkeypatch.setattr(
            "domain.backtest.engine.risk_rules._get_portfolio_repo",
            lambda: mock_portfolio_repo
        )

        # 测试用例 1: 持仓 8 只 - 应通过
        mock_portfolio_repo.get_all_holdings.return_value = [{}] * 8
        result = check_max_positions(self.ds)
        assert result["passed"] is True

        # 测试用例 2: 持仓 10 只 - 应不通过（达到上限）
        mock_portfolio_repo.get_all_holdings.return_value = [{}] * 10
        result = check_max_positions(self.ds)
        assert result["passed"] is False
        assert "10" in result["detail"]  # 错误消息应包含 10

        # 测试用例 3: 持仓 12 只 - 应不通过
        mock_portfolio_repo.get_all_holdings.return_value = [{}] * 12
        result = check_max_positions(self.ds)
        assert result["passed"] is False

    def test_custom_config_overrides_defaults(self, monkeypatch):
        """测试自定义配置可以覆盖默认值"""
        mock_kline_repo = Mock()
        mock_kline_repo.get_latest_daily_kline.return_value = pl.DataFrame({"close": [10.0]})

        monkeypatch.setattr(
            "domain.backtest.engine.risk_rules._get_kline_repo",
            lambda: mock_kline_repo
        )

        # 使用自定义配置：仓位限制改为 15%
        custom_config = RiskLimits(MAX_SINGLE_POSITION_RATIO=0.15)

        # 18% 仓位 - 默认配置应通过，自定义配置应不通过
        result_default = check_position_size(
            self.ds,
            symbol="600519",
            proposed_quantity=1800,
            account_balance=100000
        )
        assert result_default["passed"] is True  # 默认 20%，18% 通过

        result_custom = check_position_size(
            self.ds,
            symbol="600519",
            proposed_quantity=1800,
            account_balance=100000,
            config=custom_config
        )
        assert result_custom["passed"] is False  # 自定义 15%，18% 不通过
        assert "15" in result_custom["detail"]  # 错误消息应包含 15%

    def test_backward_compatibility_no_config_param(self, monkeypatch):
        """测试向后兼容：不传 config 参数的旧代码仍能工作"""
        mock_kline_repo = Mock()
        mock_kline_repo.get_latest_daily_kline.return_value = pl.DataFrame({"close": [10.0]})

        monkeypatch.setattr(
            "domain.backtest.engine.risk_rules._get_kline_repo",
            lambda: mock_kline_repo
        )

        # 旧代码调用方式（不传 config 参数）
        result = check_position_size(
            self.ds,
            "600519",
            2500,
            100000
        )
        # 应使用默认配置（20%），25% 仓位应不通过
        assert result["passed"] is False
