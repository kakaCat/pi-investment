"""t5 验收用例：失效判定 invalidation（FR-6，architecture.md IF-3）

六边界（沿用 2026-10-22 V1 验证脚本口径 + 用户裁定场景）：

1. 超阈标 invalid（目标类规则，如止盈 250 现价 300）
2. 止损豁免（保护线穿越=触发，不作废）
3. 未超阈不标
4. 缺阈值（NULL）跳过不误标
5. 持仓票同样判（覆盖全激活票）
6. 未持仓票同样判（作废范围不因空仓而缺失）
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import invalidation


def _rule(intent='exit_take_profit', price=250.0, threshold=20.0,
          state='holding', rid=306, symbol='300750.SZ'):
    return SimpleNamespace(
        id=rid,
        symbol=symbol,
        intent=intent,
        conditions=[{'type': 'price_break', 'params': {'price': price, 'direction': 'above'}}],
        invalidation_threshold_pct=threshold,
        position_state=state,
    )


def _quote(price):
    return SimpleNamespace(symbol='300750.SZ', price=price)


class TestInvalidation:
    def test_deviation_over_threshold_marks_invalid(self):
        """① 止盈 250 / 现价 300 → 偏离 20% 不超（等于阈）；310 → 24% 超线。"""
        rule = _rule(price=250.0, threshold=20.0)
        event = invalidation.check_invalidation(rule, _quote(310.0))
        assert event is not None
        assert event.deviation_pct == 24.0
        assert event.rule_id == 306
        assert '失效线' in event.reason

    def test_deviation_equal_threshold_not_invalid(self):
        """边界：偏离 == 阈值不算超（严格大于）。"""
        rule = _rule(price=250.0, threshold=20.0)
        event = invalidation.check_invalidation(rule, _quote(300.0))
        assert event is None

    def test_stop_loss_exempt(self):
        """② 止损豁免：即便偏离超线也不判失效（保护线穿越是触发）。"""
        rule = _rule(intent='exit_stop', price=200.0, threshold=10.0)
        event = invalidation.check_invalidation(rule, _quote(150.0))  # 偏离 25%
        assert event is None

    def test_under_threshold_not_invalid(self):
        """③ 未超阈不标。"""
        rule = _rule(price=250.0, threshold=20.0)
        event = invalidation.check_invalidation(rule, _quote(260.0))  # 偏离 4%
        assert event is None

    def test_missing_threshold_skips(self):
        """④ 缺阈值（NULL）→ 跳过不误标（agent 未设定失效线）。"""
        rule = _rule(price=250.0, threshold=None)
        event = invalidation.check_invalidation(rule, _quote(500.0))
        assert event is None

    def test_holding_rule_checked(self):
        """⑤ 持仓票同样判。"""
        rule = _rule(intent='exit_take_profit', state='holding')
        assert invalidation.check_invalidation(rule, _quote(320.0)) is not None

    def test_unpositioned_rule_checked(self):
        """⑥ 未持仓票同样判（作废范围覆盖，D-4 用户裁定）。"""
        rule = _rule(intent='entry', price=200.0, state='none')
        event = invalidation.check_invalidation(rule, _quote(260.0))
        assert event is not None
        assert event.symbol == '300750.SZ'

    def test_no_quote_skips(self):
        rule = _rule()
        assert invalidation.check_invalidation(rule, None) is None

    def test_multiple_price_lines_worst_wins(self):
        rule = _rule(price=250.0, threshold=10.0)
        rule.conditions.append({'type': 'price_break', 'params': {'price': 100.0}})
        event = invalidation.check_invalidation(rule, _quote(260.0))
        assert event is not None
        # 250→260 偏离 4%（不超 10%）；100→260 偏离 160%（超）→ 取最严重
        assert event.trigger_price == 100.0
