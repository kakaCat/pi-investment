"""市场级规则判定器单测（REQ-f08def P6，RFC 014 v3 §1.1，w-c8cae280）

盯盘是紧盯市场的工具——但市场级判定的第一条纪律是：**数据缺失绝不能当成事实**。
（把"涨停家数无数据"当成 0，会被判定成情绪冰点并产出错误信号。）
"""
from domain.watch.models import MarketState
from domain.watch.services.market_rule_evaluator import MarketRuleEvaluator


def _state(**kw):
    base = dict(
        indices={"000300.SH": {"close": 4500.0, "change_pct": -2.5}},
        limit_up_count=15,
        max_streak=3,
        sentiment_score=25.0,
        fear_greed_index=20.0,
        advance_decline_ratio=0.4,
        volume_ratio=0.8,
        sectors={"电力": 1.4, "农林牧渔": -3.0},
    )
    base.update(kw)
    return MarketState(**base)


def test_index_break_below():
    ev = MarketRuleEvaluator()
    hit = ev.evaluate({"type": "index_break", "target": "000300.SH",
                       "params": {"price": 4600, "direction": "below"}}, _state())
    assert hit.triggered is True
    miss = ev.evaluate({"type": "index_break", "target": "000300.SH",
                        "params": {"price": 4400, "direction": "below"}}, _state())
    assert miss.triggered is False


def test_limit_up_count_and_sentiment():
    ev = MarketRuleEvaluator()
    assert ev.evaluate({"type": "limit_up_count",
                        "params": {"count": 20, "direction": "below"}}, _state()).triggered is True
    assert ev.evaluate({"type": "sentiment",
                        "params": {"score": 30, "direction": "below"}}, _state()).triggered is True
    assert ev.evaluate({"type": "sentiment",
                        "params": {"score": 20, "direction": "below", "field": "fear_greed"}},
                       _state()).triggered is False  # 恐贪 20 不大于也不小于 20


def test_sector_and_volume():
    ev = MarketRuleEvaluator()
    assert ev.evaluate({"type": "volume_ratio",
                        "params": {"ratio": 1.0, "direction": "below"}}, _state()).triggered is True
    assert ev.evaluate({"type": "sector_pct", "target": "农林牧渔",
                        "params": {"pct": -2.0, "direction": "below"}}, _state()).triggered is True


def test_missing_data_is_skipped_not_triggered():
    """数据缺失必须 skipped，绝不能当成 0 触发（否则用故障伪造事实）"""
    ev = MarketRuleEvaluator()
    st = _state(limit_up_count=None, sentiment_score=None, sectors={})
    r1 = ev.evaluate({"type": "limit_up_count", "params": {"count": 20, "direction": "below"}}, st)
    assert r1.skipped and not r1.triggered
    r2 = ev.evaluate({"type": "sentiment", "params": {"score": 20}}, st)
    assert r2.skipped and not r2.triggered
    r3 = ev.evaluate({"type": "sector_pct", "target": "电力", "params": {"pct": 1}}, st)
    assert r3.skipped and not r3.triggered


def test_unknown_type_is_skipped():
    ev = MarketRuleEvaluator()
    r = ev.evaluate({"type": "price_break", "params": {"price": 1}}, _state())
    assert r.skipped and not r.triggered
