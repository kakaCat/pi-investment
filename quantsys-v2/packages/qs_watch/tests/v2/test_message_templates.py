"""t8 验收用例：notify_feishu + feishu_templates（FR-7/FR-10）

覆盖：
- 六类型模板各自渲染关键字段（持仓含成本/浮亏/可卖量；非持仓含买点/失效线）
- 两个发群入口（agent 判断后 / 循环第 10 次直通）
- 未注册键回落通用模板
- 两通道文件级分离：notify_feishu 不 import notify_agent
- sender 未接线不伪造成功
"""
import ast
import pathlib
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import feishu_templates, notify_feishu


def _rule(intent='exit_stop', rid=260, symbol='000425.SZ', account='user_main_simulation'):
    return SimpleNamespace(
        id=rid,
        symbol=symbol,
        intent=intent,
        account=account,
        cost_price=10.0,
        invalidation_threshold_pct=20.0,
        conditions=[{'type': 'price_break', 'params': {'price': 9.0}}],
    )


def _judgment(intent='exit_stop', price=8.8):
    return SimpleNamespace(
        intent=intent,
        triggered=True,
        hit_conditions=[{'message': '下破 9.0'}],
        quote=SimpleNamespace(symbol='000425.SZ', price=price),
        pnl_pct=-12.0,
        sellable=1000,
    )


class TestTemplates:
    def test_stop_template_has_cost_pnl_sellable(self):
        title, body = notify_feishu.render(_rule('exit_stop'), _judgment(), 'holding')
        assert '止损' in title
        assert '9.0' in body          # 止损线
        assert '10.0' in body         # 成本
        assert '-12.0' in body        # 浮亏
        assert '1000' in body         # 可卖量

    def test_take_profit_template(self):
        title, body = notify_feishu.render(
            _rule('exit_take_profit'), _judgment('exit_take_profit', 12.5), 'holding')
        assert '止盈' in title
        assert '12.5' in body

    def test_add_position_template(self):
        title, _ = notify_feishu.render(_rule('add_position'), _judgment('add_position'), 'holding')
        assert '增仓' in title

    def test_reduce_template(self):
        title, _ = notify_feishu.render(_rule('exit_reduce'), _judgment('exit_reduce'), 'holding')
        assert '减仓' in title

    def test_entry_template_has_buy_and_invalidation(self):
        title, body = notify_feishu.render(
            _rule('entry'), _judgment('entry', 30.5), 'none')
        assert '买入' in title
        assert '30.5' in body
        assert '20.0' in body          # 失效线

    def test_observe_template(self):
        title, _ = notify_feishu.render(_rule('trend_observe'), _judgment('trend_observe'), 'none')
        assert '观察' in title

    def test_six_keys_registered(self):
        keys = feishu_templates.registered_keys()
        for k in [('holding', 'add_position'), ('holding', 'exit_take_profit'),
                  ('holding', 'exit_stop'), ('holding', 'exit_reduce'),
                  ('none', 'entry'), ('none', 'trend_observe')]:
            assert k in keys, f'缺模板键 {k}'

    def test_unregistered_key_falls_back(self):
        title, body = feishu_templates.get('holding', 'nope')
        assert '盯盘触发' in title


class TestEntries:
    def test_after_agent_entry(self):
        calls = []

        def sender(title, body):
            calls.append((title, body))
            return True

        d = notify_feishu.send(_rule(), _judgment(), 'holding',
                               entry=notify_feishu.ENTRY_AFTER_AGENT, sender=sender)
        assert d.delivered is True
        assert d.entry == 'after_agent'
        assert len(calls) == 1

    def test_direct_entry_on_tenth_cycle(self):
        d = notify_feishu.send(_rule(), _judgment(), 'holding',
                               entry=notify_feishu.ENTRY_DIRECT,
                               sender=lambda t, b: True)
        assert d.delivered is True
        assert d.entry == 'direct'

    def test_sender_not_wired(self):
        d = notify_feishu.send(_rule(), _judgment(), 'holding', sender=None)
        assert d.delivered is False
        assert d.error == 'sender_not_wired'

    def test_sender_exception_isolated(self):
        d = notify_feishu.send(_rule(), _judgment(), 'holding',
                               sender=lambda t, b: (_ for _ in ()).throw(RuntimeError('feishu down')))
        assert d.delivered is False
        assert 'feishu down' in d.error


class TestChannelFileSeparation:
    def test_notify_feishu_does_not_import_notify_agent(self):
        path = pathlib.Path(notify_feishu.__file__)
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
        assert not any('notify_agent' in m for m in imported), \
            f'notify_feishu 不得 import notify_agent，实际: {imported}'
