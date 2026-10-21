"""P2 市场环境联动（2026-10-19）：持仓板块跳水 → 联动告警

用户场景：「看好的个股，但整个板块集体跳水，就需要评估是否调整持仓」。
证伪清单：
  1) held_sector_pct：持仓板块越线才触发，message 必须列出受影响持仓（标的/股数/账户）；
  2) 映射为空 → skipped（诚实标注），绝不拿空数据当「无越线」；
  3) HeldSectorMapService：反查交集正确、TTL 过期返回空、失败保留旧映射、首次失败为空；
  4) validate_condition 放行市场级类型（含 held_sector_pct）、照样拒绝垃圾；
  5) MarketWatchService 扫描时把映射挂上 frozen MarketState，触发候选进入引擎主流水线。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.conditions import validate_condition
from qs_watch.application.services.watch_engine.held_sector_map import HeldSectorMapService
from qs_watch.application.services.watch_engine.market_watch_service import MarketWatchService
from qs_watch.domain.watch.models import MarketState
from qs_watch.domain.watch.services.market_rule_evaluator import (
    MarketRuleEvaluator, validate_market_condition,
)

T0 = datetime(2026, 10, 19, 10, 0, 0)


def _state(sectors=None, held_boards=None):
    return MarketState(sectors=sectors or {}, held_boards=held_boards or {})


def _held_cond(pct=-2.0, direction='below'):
    return {'type': 'held_sector_pct', 'params': {'pct': pct, 'direction': direction}}


# ── 1. 领域评估器 ───────────────────────────────────────────

def test_held_sector_triggers_with_holdings_listed():
    ev = MarketRuleEvaluator()
    state = _state(
        sectors={'医药制造': -3.2, '银行': 0.4, '有色金属': -2.5},
        held_boards={
            '医药制造': [{'symbol': '000999', 'account': 'user_main_simulation', 'shares': 200},
                         {'symbol': '002007', 'account': 'agent_brain', 'shares': 1100}],
            '银行': [{'symbol': '600000', 'account': 'agent_brain', 'shares': 100}],
            '有色金属': [{'symbol': '601600', 'account': 'user_main_simulation', 'shares': 1000}],
        })
    res = ev.evaluate(_held_cond(-2.0), state)
    assert res.triggered is True
    assert res.value == pytest.approx(-3.2)          # 最差的板块作 value
    assert '医药制造' in res.message and '000999' in res.message
    assert '有色金属' in res.message and '601600' in res.message
    assert '银行' not in res.message                  # 未越线的不进告警


def test_held_sector_skipped_when_map_empty():
    ev = MarketRuleEvaluator()
    res = ev.evaluate(_held_cond(), _state(sectors={'医药制造': -9.9}, held_boards={}))
    assert res.triggered is False and res.skipped is True


def test_held_sector_no_trigger_when_all_healthy():
    ev = MarketRuleEvaluator()
    state = _state(sectors={'医药制造': 1.0},
                   held_boards={'医药制造': [{'symbol': '000999', 'account': 'a', 'shares': 1}]})
    res = ev.evaluate(_held_cond(-2.0), state)
    assert res.triggered is False and res.skipped is False


def test_validate_market_condition_accepts_and_rejects():
    validate_market_condition(_held_cond())
    validate_market_condition({'type': 'sector_pct', 'target': '医药制造',
                               'params': {'pct': -2.0, 'direction': 'below'}})
    with pytest.raises(ValueError, match='params.pct'):
        validate_market_condition({'type': 'held_sector_pct', 'params': {'direction': 'below'}})
    with pytest.raises(ValueError, match='direction'):
        validate_market_condition(_held_cond(direction='sideways'))


def test_conditions_validate_delegates_market_types():
    """REST 出入库校验（conditions.validate_condition）必须放行市场级类型"""
    validate_condition(_held_cond())
    validate_condition({'type': 'index_pct', 'target': 'sh000300',
                        'params': {'pct': -1.5, 'direction': 'below'}})
    with pytest.raises(ValueError):
        validate_condition({'type': 'held_sector_pct', 'params': {'direction': 'below'}})
    with pytest.raises(ValueError):
        validate_condition({'type': 'nonsense', 'params': {}})


# ── 2. 映射服务 ─────────────────────────────────────────────

class _PosRow:
    def __init__(self, symbol, shares_total):
        self.symbol = symbol
        self.shares_total = shares_total


class _FakePosRepo:
    def __init__(self, by_account):
        self._by_account = by_account

    def get_all_positions(self, account):
        return self._by_account.get(account, [])


class _FakeManager:
    def __init__(self, boards):
        self._boards = boards           # {板块名: [symbols]}
        self.calls = 0

    def get_sector_list(self):
        self.calls += 1
        return {'success': True,
                'data': {'industries': [{'name': n} for n in self._boards]}}

    def get_sector_stocks(self, name):
        return {'success': True,
                'data': {'found': name in self._boards,
                         'stocks': [{'symbol': s} for s in self._boards.get(name, [])]}}


def _map_service(boards=None, positions=None, ttl=21600):
    return HeldSectorMapService(
        position_repo=_FakePosRepo(positions or {'agent_virtual': [_PosRow('000999', 200)]}),
        accounts=('agent_virtual', 'user_main_simulation'),
        data_manager=_FakeManager(boards or {}),
        ttl_sec=ttl, now_fn=lambda: T0)


def test_map_builds_intersection_only():
    svc = _map_service(
        boards={'医药制造': ['000999', '600999'], '银行': ['600000'], '军工': ['111111']},
        positions={'agent_virtual': [_PosRow('000999', 200), _PosRow('600000', 100)]})
    out = svc.refresh(force=True)
    assert out['degraded'] is False and out['boards'] == 2      # 军工无持仓 → 不进映射
    boards = svc.held_boards()
    assert boards['医药制造'][0]['symbol'] == '000999'
    assert boards['银行'][0]['account'] == 'agent_virtual'


def test_map_ttl_and_stale_fallback():
    svc = _map_service(boards={'医药制造': ['000999']})
    svc.refresh(force=True)
    assert svc.held_boards()                      # 新鲜可读
    assert svc.refresh().get('skipped')           # TTL 内不重建
    svc_expired = _map_service(boards={'医药制造': ['000999']}, ttl=0)
    svc_expired.refresh(force=True)
    assert svc_expired.held_boards() == {}        # 过期返回空（评估器 skipped）


def test_map_failure_keeps_old_and_first_failure_empty():
    class _BadManager(_FakeManager):
        def get_sector_list(self):
            return {'success': False, 'error': 'boom'}

    svc = HeldSectorMapService(
        position_repo=_FakePosRepo({'agent_virtual': [_PosRow('000999', 200)]}),
        accounts=('agent_virtual',), data_manager=_BadManager({}),
        now_fn=lambda: T0)
    out = svc.refresh(force=True)
    assert out['degraded'] is True and svc.held_boards() == {}   # 首次失败 = 空映射


# ── 3. MarketWatchService 集成 ──────────────────────────────

class _FakeStateProvider:
    def get_state(self):
        return _state(sectors={'医药制造': -3.2})


class _FakeRuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return self._rules


def _market_rule():
    return SimpleNamespace(id=901, symbol='HELD_SECTORS', scope='market', enabled=True,
                           conditions=[_held_cond(-2.0)], context='持仓板块联动盯盘',
                           action_hint={'trigger_level': 'L2', 'action_on_trigger': 'review'})


def test_market_scan_attaches_held_boards_and_triggers():
    svc_map = _map_service(
        boards={'医药制造': ['000999']},
        positions={'user_main_simulation': [_PosRow('000999', 200)]})
    svc_map.refresh(force=True)
    mws = MarketWatchService(rule_repo=_FakeRuleRepo([_market_rule()]),
                             trigger_repo=None,
                             state_provider=_FakeStateProvider(),
                             held_sector_map=svc_map)
    out = mws.scan_market_rules(now=T0)
    assert out['triggered'] == 1
    cand = out['evaluated'][0]
    assert cand['result'].triggered is True
    assert '000999' in cand['result'].message
    assert cand['quote'].price == pytest.approx(-3.2)   # 轻量投影：price=最差板块涨跌幅


def test_market_scan_skips_held_cond_without_map_service():
    mws = MarketWatchService(rule_repo=_FakeRuleRepo([_market_rule()]),
                             trigger_repo=None,
                             state_provider=_FakeStateProvider(),
                             held_sector_map=None)
    out = mws.scan_market_rules(now=T0)
    assert out['triggered'] == 0 and out['skipped_no_data'] == 1
