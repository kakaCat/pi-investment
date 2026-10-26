"""t2 验收用例①：激活规则加载（FR-1，architecture.md: 激活数=库一致）

骨架契约：tick 内 ``rule_repo.list_by_state('active')`` 取**全部**激活规则，
加载层不做任何过滤（持仓/到期/失效都是判定阶段的对比维度）。
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2.engine import (
    TickResult,
    WatchEngineV2,
)


class FakeRuleRepo:
    """记录调用并返回预置规则的假仓储（黑盒复用 list_by_state 接口形状）。"""

    def __init__(self, rules):
        self._rules = rules
        self.calls = []

    def list_by_state(self, state):
        self.calls.append(state)
        return list(self._rules)


class FakeQuoteService:
    def __init__(self):
        self.calls = []

    def get_realtime_quote(self, symbol):
        self.calls.append(symbol)
        return SimpleNamespace(symbol=symbol, price=1.0)


def _engine(rules):
    repo = FakeRuleRepo(rules)
    quote = FakeQuoteService()
    return WatchEngineV2(rule_repo=repo, quote_service=quote), repo, quote


def test_load_active_rules_uses_list_by_state_active():
    rules = [SimpleNamespace(id=1, symbol='600000.SH'),
             SimpleNamespace(id=2, symbol='000001.SZ')]
    engine, repo, _ = _engine(rules)

    loaded = engine.load_active_rules()

    assert repo.calls == ['active']          # 只按 active 状态查一次
    assert loaded == rules                   # 激活数 = 库一致，全量返回


def test_tick_returns_tick_result_snapshot():
    rules = [SimpleNamespace(id=1, symbol='600000.SH')]
    engine, _, _ = _engine(rules)

    result = engine.tick()

    assert isinstance(result, TickResult)
    assert result.rules == rules
    assert result.symbols == ['600000.SH']   # 取价集合 == 激活 symbol 集合
    assert set(result.quotes) == {'600000.SH'}


def test_tick_calls_load_once_per_tick():
    rules = [SimpleNamespace(id=1, symbol='600000.SH')]
    engine, repo, _ = _engine(rules)

    engine.tick()
    engine.tick()

    assert repo.calls == ['active', 'active']  # 每拍重新加载（激活数随时可变）


def test_run_forever_stops_via_stop_event(monkeypatch):
    rules = [SimpleNamespace(id=1, symbol='600000.SH')]
    engine, _, _ = _engine(rules)

    ticks = []

    def _tick():
        ticks.append(1)
        if len(ticks) >= 2:
            engine.stop()          # 第二拍后请求退出
        return None

    monkeypatch.setattr(engine, 'tick', _tick)
    engine.run_forever()

    assert len(ticks) == 2          # stop() 后循环不再继续
