"""t7 验收用例：notify_agent + agent_prompts（FR-7/FR-9/FR-10）

覆盖：
- 账户 → 对应 agent 路由（D-10）：账户 A 的信号到 agent-A，不到 agent-B
- 提示词按 持仓 × 判定类型 分方案（D-21）：持仓含成本/浮亏，非持仓含买点/失效线
- 未映射账户/缺账户：不静默丢（留 warning + 兜底 agent）
- 两通道文件级分离：notify_agent 不 import notify_feishu
- sender 未接线时不伪造成功
"""
import ast
import pathlib
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import agent_prompts, notify_agent


def _rule(account='user_main_simulation', intent='exit_stop', rid=260,
          symbol='000425.SZ'):
    return SimpleNamespace(
        id=rid,
        symbol=symbol,
        intent=intent,
        account=account,
        cost_price=10.0,
        invalidation_threshold_pct=20.0,
        conditions=[{'type': 'price_break', 'params': {'price': 9.0, 'direction': 'below'}}],
    )


def _judgment(intent='exit_stop', quote_price=8.8):
    return SimpleNamespace(
        intent=intent,
        triggered=True,
        hit_conditions=[{'condition': {}, 'value': 8.8, 'message': '下破 9.0'}],
        quote=SimpleNamespace(symbol='000425.SZ', price=quote_price),
        state_mismatch=None,
    )


class TestAccountRouting:
    def test_account_a_routes_to_agent_a(self):
        calls = []

        def sender(agent, account, prompt, context):
            calls.append((agent, account, context))
            return True

        d = notify_agent.send(
            _rule(account='acct_A'), _judgment(),'holding',
            sender=sender,
            account_agent_map={'acct_A': 'agent-A', 'acct_B': 'agent-B'},
        )
        assert d.delivered is True
        assert d.agent == 'agent-A'
        assert calls == [('agent-A', 'acct_A', {'rule_id': 260, 'trigger_ids': []})]

    def test_sender_receives_callback_context(self):
        calls = []
        judgment = _judgment()
        judgment._v2_archive_entries = [
            ('a', SimpleNamespace(trigger_id=88)),
            ('b', SimpleNamespace(trigger_id=89)),
        ]

        notify_agent.send(
            _rule(), judgment, 'holding',
            sender=lambda *args: calls.append(args) or True,
        )

        assert calls[0][3] == {'rule_id': 260, 'trigger_ids': [88, 89]}

    def test_unmapped_account_falls_back_not_silent(self):
        d = notify_agent.send(
            _rule(account='acct_X'), _judgment(), 'holding',
            sender=lambda *a: True,
            account_agent_map={'acct_A': 'agent-A'},
        )
        assert d.agent == notify_agent.DEFAULT_AGENT

    def test_missing_account_falls_back(self):
        d = notify_agent.send(
            _rule(account=''), _judgment(), 'holding',
            sender=lambda *a: True,
        )
        assert d.delivered is True
        assert d.agent == notify_agent.DEFAULT_AGENT


class TestPromptPlans:
    def test_holding_prompt_has_cost_and_pnl(self):
        p = notify_agent.build_prompt(_rule(intent='exit_stop'), _judgment(), 'holding')
        assert '持仓' in p
        assert str(_rule().cost_price) in p

    def test_unpositioned_prompt_has_entry_and_invalidation(self):
        rule = _rule(intent='entry')
        j = _judgment(intent='entry', quote_price=30.5)
        p = notify_agent.build_prompt(rule, j, 'none')
        assert '买入' in p
        assert '失效线' in p

    def test_prompt_keys_cover_both_position_states(self):
        keys = agent_prompts.registered_keys()
        assert ('holding', 'exit_stop') in keys
        assert ('holding', 'exit_take_profit') in keys
        assert ('none', 'entry') in keys
        assert ('none', 'trend_observe') in keys

    def test_unregistered_key_falls_back(self):
        p = agent_prompts.get('holding', 'unknown_type')
        assert '盯盘触发' in p


class TestAgentPriceGate:
    def test_repeat_agent_call_requires_one_percent_price_move(self):
        calls = []
        tracker = {}
        rule = _rule()
        sender = lambda *args: calls.append(args) or True

        first = notify_agent.send(rule, _judgment(quote_price=100.0), 'holding',
                                  sender=sender, price_tracker=tracker)
        second = notify_agent.send(rule, _judgment(quote_price=100.5), 'holding',
                                   sender=sender, price_tracker=tracker)
        third = notify_agent.send(rule, _judgment(quote_price=101.0), 'holding',
                                  sender=sender, price_tracker=tracker)

        assert first.delivered is True
        assert second.delivered is False
        assert second.skipped is True
        assert second.error == notify_agent.PRICE_GATE_SKIP
        assert third.delivered is True
        assert len(calls) == 2, '100.5 较上次 100.0 浮动 0.5% 不发；101.0 达到 1% 再发'
        assert float(tracker[rule.id]) == 101.0

    def test_failed_send_does_not_update_price_baseline(self):
        calls = []
        tracker = {}
        rule = _rule()

        def sender(*args):
            calls.append(args)
            return len(calls) > 1

        first = notify_agent.send(rule, _judgment(quote_price=100.0), 'holding',
                                  sender=sender, price_tracker=tracker)
        retry = notify_agent.send(rule, _judgment(quote_price=100.0), 'holding',
                                  sender=sender, price_tracker=tracker)

        assert first.delivered is False
        assert retry.delivered is True
        assert len(calls) == 2, '上次发送失败不算“已调用 agent”，同价也要补发'
        assert float(tracker[rule.id]) == 100.0

    def test_price_gate_can_be_bypassed_but_baseline_updates(self):
        calls = []
        tracker = {}
        rule = _rule()
        sender = lambda *args: calls.append(args) or True

        notify_agent.send(rule, _judgment(quote_price=100.0), 'holding',
                          sender=sender, price_tracker=tracker)
        bypass = notify_agent.send(rule, _judgment(quote_price=100.5), 'holding',
                                   sender=sender, price_tracker=tracker,
                                   use_price_gate=False)
        gated = notify_agent.send(rule, _judgment(quote_price=100.6), 'holding',
                                  sender=sender, price_tracker=tracker)

        assert bypass.delivered is True
        assert gated.skipped is True, '失效裁决等必达调用绕过门槛后，仍以新价作为下次基线'
        assert len(calls) == 2
        assert float(tracker[rule.id]) == 100.5


class TestSenderContract:
    def test_sender_not_wired_reports_false(self):
        d = notify_agent.send(_rule(), _judgment(), 'holding', sender=None)
        assert d.delivered is False
        assert d.error == 'sender_not_wired'

    def test_sender_exception_isolated(self):
        def boom(*a):
            raise RuntimeError('agent down')

        d = notify_agent.send(_rule(), _judgment(), 'holding', sender=boom)
        assert d.delivered is False
        assert 'agent down' in d.error


class TestChannelFileSeparation:
    def test_notify_agent_does_not_import_notify_feishu(self):
        """D-13：两通道文件级分离（互不 import）。"""
        path = pathlib.Path(notify_agent.__file__)
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
        assert not any('notify_feishu' in m for m in imported), \
            f'notify_agent 不得 import notify_feishu，实际: {imported}'
