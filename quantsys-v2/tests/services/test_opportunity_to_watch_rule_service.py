"""OpportunityToWatchRuleService：结构证据与账户契约回归。"""
from datetime import datetime
from unittest.mock import Mock, create_autospec

import pytest

from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
from qs_watch.application.services.opportunity_to_watch_rule_service import OpportunityToWatchRuleService
from qs_watch.application.services.watch_engine.watch_rule_write_service import WatchRuleWriteService


@pytest.fixture
def repo():
    # autospec 按真实仓储签名校验 kwargs，禁止 Mock 吞掉线上必败的失效字段。
    mock = create_autospec(WatchRuleRepository, instance=True)
    mock.list_rules.return_value = []

    def create(**kwargs):
        rule = Mock()
        rule.id = 999
        rule.symbol = kwargs['symbol']
        rule.conditions = kwargs['conditions']
        rule.context = kwargs['context']
        rule.account = kwargs.get('account')
        rule.linked_account = kwargs.get('linked_account')
        return rule

    mock.create_rule.side_effect = create
    return mock


@pytest.fixture
def service(repo):
    change_repo = Mock()
    change_repo.record.return_value = Mock(id=1)
    decision_repo = Mock()
    decision_repo.get_decision.return_value = {
        'decision_id': 'DA-scan', 'related_entity_type': 'pool', 'related_entity_id': 'scan-pool',
    }
    write_service = WatchRuleWriteService(
        repo, change_repo, decision_repo=decision_repo)
    return OpportunityToWatchRuleService(rule_repo=repo, write_service=write_service)


def opportunity(**overrides):
    value = {
        'symbol': '600519', 'name': '贵州茅台', 'score': 85, 'signal_type': 'buy',
        'risk_level': 'medium', 'reasons': ['前高突破', '资金流入'], 'data_as_of': '2026-11-18',
        'entry_setup': {
            'structure_price': 100.0, 'invalidation_price': 97.0, 'target_price': 108.0,
            'invalidation_action': '观察', 'structure_basis': '2026-11-17 前高 100 元',
            'direction': 'above',
        },
    }
    value.update(overrides)
    return value


def test_complete_structure_creates_explicit_price_rule(service, repo):
    result = service.auto_create_rules(
        [opportunity()], account='agent_brain', decision_audit_id='DA-scan')[0]

    assert result['action'] == 'created'
    assert result['ownership'] == 'account'
    call = repo.create_rule.call_args.kwargs
    assert call['account'] == 'agent_brain'
    assert call['linked_account'] == 'agent_brain'
    assert call['conditions'] == [{'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}}]
    assert call['intent'] == 'trend_observe'
    assert call['trigger_channel'] == 'direct'
    assert call['action_hint']['invalidation_price'] == 97.0
    assert call['action_hint']['target_price'] == 108.0
    assert 'cooldown_sec' not in call['conditions'][0]
    assert call['expires_at'] > datetime.now()


def test_no_structure_skips_instead_of_multiplying_latest_price(service, repo):
    candidate = opportunity(entry_setup=None, score_breakdown={'technical': {'details': {'latest_price': 81.39}}})

    result = service.auto_create_rules([candidate])[0]

    assert result['action'] == 'skipped'
    assert result['reason_code'] == 'missing_or_invalid_structural_entry'
    repo.create_rule.assert_not_called()


def test_reason_text_and_score_never_become_structure(service, repo):
    candidate = opportunity(entry_setup=None, reasons=['当前价 23.45 形态不错'])

    result = service.auto_create_rules([candidate])[0]

    assert result['action'] == 'skipped'
    repo.create_rule.assert_not_called()


@pytest.mark.parametrize('setup', [
    {'structure_price': 100, 'invalidation_price': 101, 'target_price': 110,
     'invalidation_action': '观察', 'structure_basis': '前高'},
    {'structure_price': 100, 'invalidation_price': 97, 'target_price': 101,
     'invalidation_action': '观察', 'structure_basis': '前高'},
    {'structure_price': 100, 'invalidation_price': 97, 'target_price': 108,
     'invalidation_action': '观察', 'structure_basis': ''},
])
def test_invalid_structure_or_reward_risk_is_rejected(service, repo, setup):
    assert service.auto_create_rules([opportunity(entry_setup=setup)])[0]['action'] == 'skipped'
    repo.create_rule.assert_not_called()


def test_missing_account_is_explicit_global_observation(service, repo):
    result = service.auto_create_rules([opportunity()], decision_audit_id='DA-scan')[0]

    assert result['action'] == 'created'
    assert result['ownership'] == 'global_observation'
    call = repo.create_rule.call_args.kwargs
    assert call['account'] is None
    assert call['linked_account'] is None
    assert call['action_hint']['ownership'] == 'global_observation'
    assert '全局观察' in call['context']
    assert '不允许交易' in call['context']


def test_filters_and_duplicate_guard_still_apply(service, repo):
    assert service.auto_create_rules([opportunity(score=60)])[0]['action'] == 'skipped'
    assert service.auto_create_rules([opportunity(signal_type='sell')])[0]['action'] == 'skipped'
    repo.list_rules.return_value = [Mock(id=1)]
    assert service.auto_create_rules([opportunity()])[0]['action'] == 'skipped'
    repo.create_rule.assert_not_called()


def test_auto_create_requires_real_audit_and_authorized_account(service, repo):
    missing = service.auto_create_rules([opportunity()], account='agent_brain')[0]
    assert missing['action'] == 'failed'
    forbidden = service.auto_create_rules(
        [opportunity()], account='user_main_simulation', decision_audit_id='DA-scan')[0]
    assert forbidden['action'] == 'failed'
    repo.create_rule.assert_not_called()


def test_auto_create_without_unified_write_service_fails_closed(repo):
    raw = OpportunityToWatchRuleService(rule_repo=repo)
    result = raw.auto_create_rules(
        [opportunity()], account='agent_brain', decision_audit_id='DA-scan')[0]
    assert result['action'] == 'failed'
    assert 'WatchRuleWriteService' in result['reason']
    repo.create_rule.assert_not_called()
