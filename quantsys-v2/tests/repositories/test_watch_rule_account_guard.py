"""仓储层铁律：没有账户的规则不能进入买卖（2026-09-11，w-aebfddcd）

为什么在仓储层也拦：规则可能由 API 之外的路径创建（内部服务/定时任务/生命周期补挂），
只在入口校验会被绕过。这里直接对 WatchRuleRepository 验证。
"""
import pytest

from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
from domain.watch.services.rule_guard import TradeRuleWithoutAccount

COND = [{"type": "price_break", "params": {"direction": "below", "price": 10.0}}]


@pytest.fixture
def repo():
    return WatchRuleRepository()


def _cleanup(repo, rule_id):
    repo.delete_by_id(rule_id)


def test_repo_blocks_trade_rule_without_account(repo):
    with pytest.raises(TradeRuleWithoutAccount):
        repo.create_rule(symbol="000001.SZ", conditions=COND, intent="entry")


def test_repo_allows_trade_rule_with_account_and_normalizes(repo):
    rule = repo.create_rule(symbol="000001.SZ", conditions=COND, intent="entry",
                            account="agent_virtual")
    try:
        fresh = repo.get_by_id(rule.id)
        assert fresh.account == "agent_virtual"
        assert fresh.linked_account == "agent_virtual"   # 两字段归一
    finally:
        _cleanup(repo, rule.id)


def test_repo_allows_observe_rule_without_account(repo):
    rule = repo.create_rule(symbol="000002.SZ", conditions=COND, intent="trend_observe")
    try:
        assert repo.get_by_id(rule.id).linked_account is None
    finally:
        _cleanup(repo, rule.id)


def test_repo_blocks_update_to_trade_without_account(repo):
    rule = repo.create_rule(symbol="000003.SZ", conditions=COND, intent="trend_observe")
    try:
        with pytest.raises(TradeRuleWithoutAccount):
            repo.update_fields(rule.id, intent="entry")
        # 补账户后放行，且两字段都落
        repo.update_fields(rule.id, intent="entry", linked_account="agent_brain")
        fresh = repo.get_by_id(rule.id)
        assert fresh.intent == "entry" and fresh.linked_account == "agent_brain"
    finally:
        _cleanup(repo, rule.id)


def test_repo_blocks_clearing_account_on_trade_rule(repo):
    rule = repo.create_rule(symbol="000004.SZ", conditions=COND, intent="exit_stop",
                            linked_account="agent_virtual")
    try:
        with pytest.raises(TradeRuleWithoutAccount):
            repo.update_fields(rule.id, linked_account=None)
    finally:
        _cleanup(repo, rule.id)
