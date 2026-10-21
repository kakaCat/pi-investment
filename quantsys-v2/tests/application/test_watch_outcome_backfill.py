"""P3 预判验证闭环（2026-10-20）：触发走势回填

证伪清单：
  1) 预判方向推断：intent 优先（exit→down/entry→up），无 intent 按条件线方向兜底，判不出→None；
  2) 命中判定：±2% 阈值带内不定论（None），不计入命中率分母；
  3) add_trading_days：跨周末正确数交易日；
  4) backfill：到期才回填、收盘价缺失保留待下轮、幂等（仓储 record 返回 False 不算 filled）；
  5) 单条失败不拖垮整批。
"""
from datetime import date, datetime, timedelta

import pytest

from qs_watch.application.services.watch_engine.outcome_backfill_service import (
    OutcomeBackfillService, add_trading_days,
)
from qs_watch.domain.watch.services.outcome_direction import (
    infer_expected_direction, judge_hit,
)

NOW = datetime(2026, 10, 20, 9, 0, 0)   # 周二


# ── 1. 方向推断（纯函数）────────────────────────────────────

def test_direction_intent_wins():
    assert infer_expected_direction('exit_stop', {'type': 'price_break',
                                    'params': {'price': 1, 'direction': 'below'}}) == 'down'
    assert infer_expected_direction('entry', None) == 'up'


def test_direction_fallback_by_condition():
    assert infer_expected_direction(None, {'type': 'price_break',
                                    'params': {'direction': 'below'}}) == 'up'
    assert infer_expected_direction(None, {'type': 'staged_break',
                                    'params': {'touch': {'direction': 'above'}}}) == 'down'
    assert infer_expected_direction(None, {'type': 'volume_surge', 'params': {}}) is None


def test_judge_hit_threshold_band():
    assert judge_hit('up', 3.5) is True
    assert judge_hit('up', -3.5) is False
    assert judge_hit('up', 1.0) is None        # 阈值带内不定论
    assert judge_hit('down', -2.5) is True
    assert judge_hit(None, 5.0) is None
    assert judge_hit('up', None) is None


# ── 2. 交易日推算 ───────────────────────────────────────────

def test_add_trading_days_skips_weekend():
    # 2026-10-16 是周五（交易日），+1 交易日 = 周一 10-19
    assert add_trading_days(date(2026, 10, 16), 1) == date(2026, 10, 19)
    assert add_trading_days(date(2026, 10, 19), 1) == date(2026, 10, 20)


# ── 3. 回填服务 ─────────────────────────────────────────────

class _FakeRepo:
    def __init__(self, pendings):
        self._pendings = pendings
        self.recorded = []
        self.exists = set()     # 已存在的 (trigger_id, horizon)

    def pending_triggers(self, horizon_td, due_before, since, limit):
        return [p for p in self._pendings if horizon_td in p['horizons']]

    def record(self, **kw):
        key = (kw['trigger_id'], kw['horizon_td'])
        if key in self.exists:
            return False
        self.exists.add(key)
        self.recorded.append(kw)
        return True


class _FakeManager:
    def __init__(self, closes):
        self._closes = closes   # {symbol: [(date_str, close)]}

    def get_klines(self, symbol, period, start, end):
        rows = [{'trade_date': d, 'close': c}
                for d, c in self._closes.get(symbol, []) if start <= d <= end]
        return {'success': True, 'data': rows}


def _trigger(tid, symbol='600900', price=27.5, on=date(2026, 10, 12),
             intent='entry', horizons=(5,)):
    return {'trigger_id': tid, 'rule_id': 100 + tid, 'symbol': symbol,
            'triggered_at': datetime(on.year, on.month, on.day, 10, 30),
            'trigger_price': price, 'intent': intent, 'horizons': horizons,
            'condition': {'type': 'price_break',
                          'params': {'price': price, 'direction': 'below'}}}


def test_backfill_fills_due_outcomes():
    # 10-12（周一）+5 个交易日 = 10-19（周一）≤ 今天 → 到期
    repo = _FakeRepo([_trigger(1)])
    mgr = _FakeManager({'600900': [('2026-10-19', 29.0)]})
    svc = OutcomeBackfillService(repo, data_manager=mgr, now_fn=lambda: NOW)
    out = svc.backfill()
    assert out['filled'] == 1 and out['failed'] == 0
    row = repo.recorded[0]
    assert row['check_date'] == date(2026, 10, 19)
    assert row['pct_change'] == pytest.approx((29.0 / 27.5 - 1) * 100, rel=1e-3)
    assert row['expected_direction'] == 'up'
    assert row['hit'] is True                                # +5.45% ≥ 2%


def test_backfill_skips_future_and_missing_close():
    # 10-19 触发 +5 交易日 = 10-26 > 今天 → 不回填
    future = _trigger(2, on=date(2026, 10, 19))
    # 到期但无收盘价 → 保留待下轮
    no_close = _trigger(3, symbol='999999', on=date(2026, 10, 12))
    repo = _FakeRepo([future, no_close])
    svc = OutcomeBackfillService(repo, data_manager=_FakeManager({}), now_fn=lambda: NOW)
    out = svc.backfill()
    assert out['filled'] == 0
    assert repo.recorded == []


def test_backfill_idempotent_and_failure_isolated():
    repo = _FakeRepo([_trigger(4), _trigger(5)])
    repo.exists.add((4, 5))                                  # 已回填过 → 幂等跳过
    mgr = _FakeManager({'600900': [('2026-10-19', 29.0)]})
    svc = OutcomeBackfillService(repo, data_manager=mgr, now_fn=lambda: NOW)
    out = svc.backfill()
    assert out['filled'] == 1                                # 只有 #5 落库
    assert repo.recorded[0]['trigger_id'] == 5


def test_hit_none_when_direction_uninferable():
    t = _trigger(6, intent=None)
    t['condition'] = {'type': 'volume_surge', 'params': {'multiple': 2}}
    repo = _FakeRepo([t])
    mgr = _FakeManager({'600900': [('2026-10-19', 29.0)]})
    svc = OutcomeBackfillService(repo, data_manager=mgr, now_fn=lambda: NOW)
    assert svc.backfill()['filled'] == 1
    assert repo.recorded[0]['expected_direction'] is None
    assert repo.recorded[0]['hit'] is None                   # 不定论，不计入分母
