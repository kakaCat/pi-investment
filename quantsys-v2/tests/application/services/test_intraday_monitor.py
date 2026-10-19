"""IntradayMonitor 账户解析（account_type 事实源）+ 分级止损口径测试（全 mock，不触库）

锁定五条契约：
  1. 账户清单的单一事实源 = quant.simulation_account.account_type 列：
     agent+active → 自动执行（check_stop_loss）；
     user+active → 只告警不执行（evaluate_stop_loss，**零卖单**）；
     strategy/legacy/status!='active'（frozen/archived）/查无此行 → 不监控；
     account_type 为 NULL/空串/未识别值 → 一律 alert-only（盯着但不动钱）。
  2. fail-closed：账户表查询失败 → 自动执行清单为空，兜底清单一律 alert-only
     （宁可不自动执行也绝不动用户的钱）。
  3. MONITOR_CONFIG 显式覆盖（accounts / alert_only_accounts）仅调试用，给了就不读表。
  4. 单账户失败隔离：一个账户抛错不影响其余账户，结果按账户分组汇报。
  5. 分级止损口径：创业板/科创板（30/68 开头）-10%，其余 -8%；止盈 +15% 不变。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from qs_trading.application.services.intraday_monitor import (
    DEFAULT_FALLBACK_ACCOUNTS,
    IntradayMonitor,
)
from qs_trading.application.services.intraday_risk_policy import stop_loss_pct

REPO_PATH = "adapters.outbound.repositories.SimulationORMRepository"
ENGINE_PATH = "application.trading.paper_trading_engine.PaperTradingEngine"


# ---------------------------------------------------------------
# 分级止损口径（纯函数）
# ---------------------------------------------------------------

class TestStopLossPct:
    @pytest.mark.parametrize("symbol", ["300750.SZ", "300750", "688981.SH", "688981", "301236.SZ"])
    def test_gem_star_board_10pct(self, symbol):
        assert stop_loss_pct(symbol) == pytest.approx(0.10)

    @pytest.mark.parametrize("symbol", ["600519.SH", "000001.SZ", "002594.SZ", "601318.SH"])
    def test_other_boards_8pct(self, symbol):
        assert stop_loss_pct(symbol) == pytest.approx(0.08)


# ---------------------------------------------------------------
# 测试工具
# ---------------------------------------------------------------

def _account_row(name, account_type, status="active"):
    return SimpleNamespace(account_name=name, account_type=account_type, status=status)


def _make_trade_result(strategy_name: str, symbol: str = "600519.SH"):
    """伪造一个成功的 TradeResult（止损/止盈卖出回执）"""
    signal = SimpleNamespace(strategy_name=strategy_name)
    r = MagicMock()
    r.success = True
    r.signal = signal
    r.to_dict.return_value = {"symbol": symbol, "strategy_name": strategy_name}
    return r


def _make_trigger(trigger_type: str = "stop_loss", symbol: str = "600519.SH"):
    return {
        "symbol": symbol,
        "type": trigger_type,
        "pnl_pct": -0.09,
        "threshold": -0.08,
        "avg_cost": 100.0,
        "current_price": 91.0,
        "shares_available": 100,
    }


def _engine_with_positions(positions, stop_results=(), triggers=()):
    engine = MagicMock()
    engine.get_current_positions.return_value = positions
    engine.check_stop_loss.return_value = list(stop_results)
    engine.evaluate_stop_loss.return_value = list(triggers)
    return engine


def _stub_monitor(monitor):
    """绕过重依赖：交易时段恒真、行情/大盘异动/通知打桩"""
    monitor._is_trading_time = lambda t: True
    monitor._get_realtime_prices = lambda symbols: {s: 100.0 for s in symbols}
    monitor._check_index_alert = lambda: None
    monitor._notify_user_stop_alert = MagicMock()
    return monitor


def _run_with_table(monitor, rows, engine_factory):
    """以给定的账户表行 + 引擎工厂跑一次 check"""
    _stub_monitor(monitor)
    repo = MagicMock()
    repo.list_accounts.return_value = rows
    engines = {}

    def factory(account_name, **kw):
        engine = engine_factory(account_name)
        engines[account_name] = engine
        return engine

    with patch(REPO_PATH, return_value=repo), patch(ENGINE_PATH, side_effect=factory):
        results = monitor.check()
    return results, engines, repo


# ---------------------------------------------------------------
# 账户解析：account_type 事实源
# ---------------------------------------------------------------

class TestAccountResolution:
    def test_unknown_type_falls_into_alert_only(self):
        """account_type 为 NULL/空串/未识别值的 active 账户 → 一律 alert-only：
        出现在监控清单、零卖单、有告警（2026-10-19 裁定：盯着但不动钱，绝不静默失明）"""
        rows = [
            _account_row("agent_virtual", "agent"),
            _account_row("mystery_null", None),      # NULL
            _account_row("mystery_blank", "  "),     # 空串
            _account_row("mystery_typo", "agnet"),   # 未识别值
        ]

        def factory(account_name):
            return _engine_with_positions(
                [{"symbol": "600519.SH"}], triggers=[_make_trigger("stop_loss")]
            )

        monitor = IntradayMonitor()  # 缺省 = 读表
        results, engines, _ = _run_with_table(monitor, rows, factory)

        assert results["account_source"] == "table"
        # 三个类型缺失账户全部被监控，且一律 alert-only
        for name in ("mystery_null", "mystery_blank", "mystery_typo"):
            assert name in engines, f"{name} 不应静默失明"
            assert results["accounts"][name]["mode"] == "alert_only"
            assert results["accounts"][name]["status"] == "completed"
            # 铁律：类型未知 → 绝不动钱
            engines[name].check_stop_loss.assert_not_called()
            engines[name].evaluate_stop_loss.assert_called_once()
        # 只有 agent_virtual 是自动执行
        assert results["accounts"]["agent_virtual"]["mode"] == "auto_execute"
        # 告警照常产出（3 个未知账户各 1 条止损告警）
        unknown_alerts = [
            a for a in results["alerts"] if a.get("account", "").startswith("mystery_")
        ]
        assert len(unknown_alerts) == 3
        assert results["stop_loss_triggered"] == []  # 零已执行卖单

    def test_table_is_source_of_truth(self):
        """agent→自动执行；user→alert-only；strategy/legacy→不监控"""
        rows = [
            _account_row("agent_virtual", "agent"),
            _account_row("agent_brain", "agent"),
            _account_row("user_main_simulation", "user"),
            _account_row("v13_simulation", "strategy"),
            _account_row("v14_simulation", "strategy"),
            _account_row("rotation_main", "legacy"),
            _account_row("default", "legacy"),
        ]

        def factory(account_name):
            return _engine_with_positions([{"symbol": "600519.SH"}])

        monitor = IntradayMonitor()  # 缺省 = 读表
        results, engines, repo = _run_with_table(monitor, rows, factory)

        # 只查 active（frozen/archived 由 SQL 层滤除）
        repo.list_accounts.assert_called_once_with(status="active")
        assert results["account_source"] == "table"
        # 只有 agent/user 账户被实例化引擎
        assert set(engines) == {"agent_virtual", "agent_brain", "user_main_simulation"}
        assert results["accounts"]["agent_virtual"]["mode"] == "auto_execute"
        assert results["accounts"]["agent_brain"]["mode"] == "auto_execute"
        assert results["accounts"]["user_main_simulation"]["mode"] == "alert_only"
        # strategy/legacy 不出现在结果里
        for excluded in ("v13_simulation", "v14_simulation", "rotation_main", "default"):
            assert excluded not in results["accounts"]

    def test_frozen_and_archived_filtered_by_status(self):
        """status!='active' 的账户不进入监控（frozen 的 v14 已退役）——
        仓储按 status='active' 过滤，本测试锁调用口径"""
        monitor = IntradayMonitor()
        _stub_monitor(monitor)
        repo = MagicMock()
        repo.list_accounts.return_value = []  # active 过滤后为空（frozen 行被滤掉）

        with patch(REPO_PATH, return_value=repo):
            auto, alert, source = monitor._resolve_accounts()

        repo.list_accounts.assert_called_once_with(status="active")
        assert (auto, alert, source) == ([], [], "table")

    def test_query_failure_fails_closed(self):
        """账户表查询失败：零自动执行，兜底清单一律 alert-only（绝不动用户的钱）"""
        monitor = IntradayMonitor()

        def factory(account_name):
            return _engine_with_positions(
                [{"symbol": "600519.SH"}], triggers=[_make_trigger("stop_loss")]
            )

        _stub_monitor(monitor)
        engines = {}
        with patch(REPO_PATH, side_effect=RuntimeError("db down")), patch(
            ENGINE_PATH,
            side_effect=lambda account_name, **kw: engines.setdefault(
                account_name, factory(account_name)
            ),
        ):
            results = monitor.check()

        assert results["account_source"] == "fallback_fail_closed"
        # 兜底清单全部 alert-only：任何账户都没有下过卖单
        assert set(engines) == set(DEFAULT_FALLBACK_ACCOUNTS)
        for engine in engines.values():
            engine.check_stop_loss.assert_not_called()
        assert results["stop_loss_triggered"] == []
        assert results["take_profit_triggered"] == []
        # 告警照常产出
        assert len(results["alerts"]) == len(DEFAULT_FALLBACK_ACCOUNTS)

    def test_config_override_skips_table(self):
        """显式 config 覆盖 = 调试通道：不读表"""
        monitor = IntradayMonitor(config={
            "accounts": ("debug_agent",),
            "alert_only_accounts": ("debug_user",),
        })
        _stub_monitor(monitor)
        engines = {}

        with patch(REPO_PATH, side_effect=AssertionError("不该读表")), patch(
            ENGINE_PATH,
            side_effect=lambda account_name, **kw: engines.setdefault(
                account_name, _engine_with_positions([{"symbol": "600519.SH"}])
            ),
        ):
            results = monitor.check()

        assert results["account_source"] == "config_override"
        assert set(engines) == {"debug_agent", "debug_user"}
        assert results["accounts"]["debug_agent"]["mode"] == "auto_execute"
        assert results["accounts"]["debug_user"]["mode"] == "alert_only"

    def test_alert_only_wins_when_account_in_both_lists(self):
        """同名账户同时在两个覆盖清单时 alert-only 优先（安全方向）"""
        monitor = IntradayMonitor(config={
            "accounts": ("agent_virtual",),
            "alert_only_accounts": ("agent_virtual",),
        })
        _stub_monitor(monitor)
        engines = {}

        with patch(ENGINE_PATH, side_effect=lambda account_name, **kw: engines.setdefault(
            account_name, _engine_with_positions([{"symbol": "600519.SH"}])
        )):
            results = monitor.check()

        assert results["accounts"]["agent_virtual"]["mode"] == "alert_only"
        engines["agent_virtual"].check_stop_loss.assert_not_called()


# ---------------------------------------------------------------
# 账户遍历行为（显式覆盖清单下的执行/告警/隔离语义）
# ---------------------------------------------------------------

AUTO = ("agent_virtual", "agent_brain")
ALERT = ("user_main_simulation",)
ALL_ACCOUNTS = list(AUTO) + list(ALERT)


def _override_monitor():
    return IntradayMonitor(config={"accounts": AUTO, "alert_only_accounts": ALERT})


def _patched_monitor(engine_factory):
    monitor = _override_monitor()
    _stub_monitor(monitor)
    return monitor, patch(ENGINE_PATH, side_effect=engine_factory)


class TestAccountCoverage:
    def test_fallback_tuple_exists_and_is_alert_only_only(self):
        """硬编码元组已降级为表查询失败时的 alert-only 兜底"""
        assert DEFAULT_FALLBACK_ACCOUNTS == ("agent_virtual", "agent_brain", "user_main_simulation")

    def test_check_iterates_all_accounts(self):
        created = []

        def factory(account_name, risk_config=None, **kw):
            created.append((account_name, risk_config))
            return _engine_with_positions([{"symbol": "600519.SH", "created_at": "2026-10-01"}])

        monitor, patcher = _patched_monitor(factory)
        with patcher:
            results = monitor.check()

        # 自动执行账户在前，alert-only 账户在后，逐账户实例化
        assert [a for a, _ in created] == ALL_ACCOUNTS
        # 每个账户都拿到了分级止损口径
        for _, rc in created:
            assert callable(rc["stop_loss_pct_fn"])
        assert results["status"] == "completed"
        assert results["positions_checked"] == 3
        for acct in ALL_ACCOUNTS:
            assert results["accounts"][acct]["status"] == "completed"
        assert results["accounts"]["agent_virtual"]["mode"] == "auto_execute"
        assert results["accounts"]["user_main_simulation"]["mode"] == "alert_only"

    def test_alert_only_account_never_sells(self):
        """user_main 触发止损：绝不调用 check_stop_loss（无卖单），只有告警 + 通知"""
        engines = {}

        def factory(account_name, **kw):
            if account_name == "user_main_simulation":
                engine = _engine_with_positions(
                    [{"symbol": "600519.SH"}], triggers=[_make_trigger("stop_loss")]
                )
            else:
                engine = _engine_with_positions([{"symbol": "600519.SH"}])
            engines[account_name] = engine
            return engine

        monitor, patcher = _patched_monitor(factory)
        with patcher:
            results = monitor.check()

        user_engine = engines["user_main_simulation"]
        # 铁律：alert-only 账户绝不下卖单
        user_engine.check_stop_loss.assert_not_called()
        # 只走了纯评估
        user_engine.evaluate_stop_loss.assert_called_once()
        # 告警落结果（分组 + 顶层），带账户归属
        acct = results["accounts"]["user_main_simulation"]
        assert acct["status"] == "completed"
        assert acct["mode"] == "alert_only"
        assert len(acct["alerts"]) == 1
        assert acct["alerts"][0]["type"] == "stop_loss"
        assert acct["alerts"][0]["account"] == "user_main_simulation"
        assert any(
            a.get("account") == "user_main_simulation" and a.get("type") == "stop_loss"
            for a in results["alerts"]
        )
        # 顶层"已执行"清单里没有 user_main 的卖单
        assert results["stop_loss_triggered"] == []
        assert results["take_profit_triggered"] == []
        # 走了通知通道请用户裁定
        monitor._notify_user_stop_alert.assert_called_once()
        notify_account, notify_triggers = monitor._notify_user_stop_alert.call_args[0]
        assert notify_account == "user_main_simulation"
        assert len(notify_triggers) == 1

    def test_auto_execute_accounts_still_sell(self):
        """对照组：agent 自治账户照常自动执行卖单"""
        def factory(account_name, **kw):
            return _engine_with_positions(
                [{"symbol": "600519.SH"}],
                stop_results=[_make_trade_result("stop_loss")],
            )

        monitor, patcher = _patched_monitor(factory)
        with patcher:
            results = monitor.check()

        assert len(results["stop_loss_triggered"]) == 2  # 两个自治账户各 1 笔
        assert {e["account"] for e in results["stop_loss_triggered"]} == {
            "agent_virtual", "agent_brain",
        }

    def test_account_failure_isolated(self):
        """agent_brain 抛错不影响其余账户，结果按账户分组"""
        def factory(account_name, **kw):
            if account_name == "agent_brain":
                engine = MagicMock()
                engine.get_current_positions.side_effect = RuntimeError("db down")
                return engine
            return _engine_with_positions(
                [{"symbol": "600519.SH"}],
                stop_results=[_make_trade_result("stop_loss")],
            )

        monitor, patcher = _patched_monitor(factory)
        with patcher:
            results = monitor.check()

        assert results["accounts"]["agent_brain"]["status"] == "error"
        assert "db down" in results["accounts"]["agent_brain"]["error"]
        assert results["accounts"]["agent_virtual"]["status"] == "completed"
        assert results["accounts"]["user_main_simulation"]["status"] == "completed"
        assert results["status"] == "completed"
        # 顶层汇总只有 agent_virtual 一笔（agent_brain 失败、user_main 只评估无触发）
        assert len(results["stop_loss_triggered"]) == 1
        assert results["stop_loss_triggered"][0]["account"] == "agent_virtual"

    def test_all_accounts_no_positions(self):
        def factory(account_name, **kw):
            return _engine_with_positions([])

        monitor, patcher = _patched_monitor(factory)
        with patcher:
            results = monitor.check()

        assert results["status"] == "no_positions"
        for acct in ALL_ACCOUNTS:
            assert results["accounts"][acct]["status"] == "no_positions"

    def test_no_accounts_resolved(self):
        """覆盖清单为空 → 明确报 no_accounts"""
        monitor = IntradayMonitor(config={"accounts": (), "alert_only_accounts": ()})
        _stub_monitor(monitor)
        results = monitor.check()
        assert results["status"] == "no_accounts"

    def test_not_trading_time_skips(self):
        monitor = IntradayMonitor()
        monitor._is_trading_time = lambda t: False
        assert monitor.check() == {"status": "skipped", "reason": "not trading time"}


# ---------------------------------------------------------------
# PaperTradingEngine 分级止损执行（mock broker/repo，不触库）
# ---------------------------------------------------------------

def _position(symbol: str, avg_cost: float):
    return SimpleNamespace(
        symbol=symbol,
        shares_available=100,
        shares_total=100,
        avg_cost=avg_cost,
    )


def _make_engine(positions, risk_config):
    import application.trading.paper_trading_engine as pte

    with patch.object(pte, "SimulationBroker"), patch.object(pte, "SimulationORMRepository"):
        engine = pte.PaperTradingEngine(account_name="agent_virtual", risk_config=risk_config)
    engine.repo = MagicMock()
    engine.repo.get_all_positions.return_value = positions
    engine._execute_sell = MagicMock(side_effect=lambda signal, price: signal.strategy_name)
    return engine


class TestEngineTieredStopLoss:
    RISK = {"stop_loss_pct_fn": stop_loss_pct, "take_profit_pct": 0.15}

    def test_gem_stock_tolerates_9pct_but_stops_at_10pct(self):
        # 创业板 300750：-9.5% 不触发（口径 -10%）
        engine = _make_engine([_position("300750.SZ", 100.0)], dict(self.RISK))
        assert engine.check_stop_loss({"300750.SZ": 90.5}) == []
        engine._execute_sell.assert_not_called()

        # -10.1% 触发止损
        engine = _make_engine([_position("300750.SZ", 100.0)], dict(self.RISK))
        out = engine.check_stop_loss({"300750.SZ": 89.9})
        assert out == ["stop_loss"]

    def test_main_board_stops_at_8pct(self):
        # 主板 600519：-7.5% 不触发
        engine = _make_engine([_position("600519.SH", 100.0)], dict(self.RISK))
        assert engine.check_stop_loss({"600519.SH": 92.5}) == []

        # -8.1% 触发
        engine = _make_engine([_position("600519.SH", 100.0)], dict(self.RISK))
        out = engine.check_stop_loss({"600519.SH": 91.9})
        assert out == ["stop_loss"]

    def test_star_market_68_prefix_10pct(self):
        # 科创板 688981：-9% 不触发，-10.5% 触发
        engine = _make_engine([_position("688981.SH", 100.0)], dict(self.RISK))
        assert engine.check_stop_loss({"688981.SH": 91.0}) == []

        engine = _make_engine([_position("688981.SH", 100.0)], dict(self.RISK))
        assert engine.check_stop_loss({"688981.SH": 89.5}) == ["stop_loss"]

    def test_take_profit_unchanged_15pct(self):
        engine = _make_engine([_position("300750.SZ", 100.0)], dict(self.RISK))
        assert engine.check_stop_loss({"300750.SZ": 114.9}) == []
        engine = _make_engine([_position("300750.SZ", 100.0)], dict(self.RISK))
        assert engine.check_stop_loss({"300750.SZ": 115.0}) == ["take_profit"]

    def test_scalar_fallback_without_fn(self):
        """不传 stop_loss_pct_fn 时维持旧行为：全市场 -8%"""
        engine = _make_engine([_position("300750.SZ", 100.0)], {})
        # 创业板在旧口径下 -8.5% 即触发
        assert engine.check_stop_loss({"300750.SZ": 91.5}) == ["stop_loss"]


class TestEngineEvaluateOnly:
    """evaluate_stop_loss：纯评估，任何情况下都不下卖单（alert-only 的引擎侧地基）"""

    RISK = {"stop_loss_pct_fn": stop_loss_pct, "take_profit_pct": 0.15}

    def test_evaluate_returns_triggers_without_selling(self):
        engine = _make_engine(
            [_position("600519.SH", 100.0), _position("300750.SZ", 100.0)],
            dict(self.RISK),
        )
        # 主板 -9%（触发止损）、创业板 +16%（触发止盈）
        triggers = engine.evaluate_stop_loss({"600519.SH": 91.0, "300750.SZ": 116.0})

        assert len(triggers) == 2
        by_symbol = {t["symbol"]: t for t in triggers}
        assert by_symbol["600519.SH"]["type"] == "stop_loss"
        assert by_symbol["600519.SH"]["threshold"] == pytest.approx(-0.08)
        assert by_symbol["300750.SZ"]["type"] == "take_profit"
        assert by_symbol["300750.SZ"]["threshold"] == pytest.approx(0.15)
        # 铁律：评估路径绝不下卖单
        engine._execute_sell.assert_not_called()

    def test_evaluate_respects_gem_tier(self):
        # 创业板 -9.5%：分级口径下不触发
        engine = _make_engine([_position("300750.SZ", 100.0)], dict(self.RISK))
        assert engine.evaluate_stop_loss({"300750.SZ": 90.5}) == []
        engine._execute_sell.assert_not_called()

        # 创业板 -10.1%：触发
        engine = _make_engine([_position("300750.SZ", 100.0)], dict(self.RISK))
        triggers = engine.evaluate_stop_loss({"300750.SZ": 89.9})
        assert [t["type"] for t in triggers] == ["stop_loss"]
        assert triggers[0]["threshold"] == pytest.approx(-0.10)
        engine._execute_sell.assert_not_called()

    def test_evaluate_no_trigger(self):
        engine = _make_engine([_position("600519.SH", 100.0)], dict(self.RISK))
        assert engine.evaluate_stop_loss({"600519.SH": 100.0}) == []
        engine._execute_sell.assert_not_called()
