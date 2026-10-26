"""t2 验收用例②：统一取价前置（FR-2，architecture.md: 取价集合=symbol 集合）

骨架契约：激活规则按 symbol **去重**后统一取价，取价输入集合 == 激活
symbol 集合 —— 取价在判定**之前**，持仓状态/到期与否不过滤取价范围。
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2.engine import WatchEngineV2


class FakeRuleRepo:
    def __init__(self, rules):
        self._rules = rules
        self.events = []

    def list_by_state(self, state):
        self.events.append(('load', state))
        return list(self._rules)


class FakeQuoteService:
    def __init__(self, fail_symbols=()):
        self.events = []
        self._fail_symbols = set(fail_symbols)

    def get_realtime_quote(self, symbol):
        self.events.append(('quote', symbol))
        if symbol in self._fail_symbols:
            raise RuntimeError(f'provider down: {symbol}')
        return SimpleNamespace(symbol=symbol, price=10.0)


def _engine(rules, fail_symbols=()):
    repo = FakeRuleRepo(rules)
    quote = FakeQuoteService(fail_symbols=fail_symbols)
    return WatchEngineV2(rule_repo=repo, quote_service=quote), repo, quote


def _rule(symbol, position_state='none'):
    return SimpleNamespace(symbol=symbol, position_state=position_state)


def test_quote_input_set_equals_active_symbol_set():
    rules = [_rule('600000.SH'), _rule('000001.SZ'), _rule('300750.SZ')]
    engine, _, quote = _engine(rules)

    result = engine.tick()

    quoted = sorted(quote.events)
    assert quoted == [('quote', '000001.SZ'), ('quote', '300750.SZ'),
                      ('quote', '600000.SH')]
    assert sorted(result.quotes) == ['000001.SZ', '300750.SZ', '600000.SH']


def test_quotes_deduplicated_across_rules():
    rules = [_rule('600000.SH'), _rule('600000.SH'), _rule('600000.SH')]
    engine, _, quote = _engine(rules)

    result = engine.tick()

    assert quote.events == [('quote', '600000.SH')]   # 同 symbol 只取价一次
    assert result.symbols == ['600000.SH']
    assert len(result.rules) == 3                     # 规则本身不去重，取价才去重


def test_quote_is_before_judgement_and_unfiltered_by_position():
    # 取价前置：holding / none 两种持仓状态都进取价集合（持仓是判定维度，
    # 不是取价过滤条件 —— 需求文档流程图 ②「统一实时取价（前置，不过滤）」）
    rules = [_rule('600000.SH', position_state='holding'),
             _rule('000001.SZ', position_state='none')]
    engine, repo, quote = _engine(rules)

    engine.tick()

    assert repo.events == [('load', 'active')]
    assert [e[0] for e in quote.events] == ['quote', 'quote']
    assert {s for _, s in quote.events} == {'600000.SH', '000001.SZ'}


def test_single_symbol_quote_failure_does_not_break_tick():
    rules = [_rule('600000.SH'), _rule('000001.SZ')]
    engine, _, quote = _engine(rules, fail_symbols={'600000.SH'})

    result = engine.tick()

    assert result.quotes['600000.SH'] is None          # 失败票留 None（fail-open）
    assert result.quotes['000001.SZ'] is not None      # 其余 symbol 照常取到
    assert sorted(quote.events) == [('quote', '000001.SZ'), ('quote', '600000.SH')]
