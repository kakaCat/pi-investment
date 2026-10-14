"""规则写入口的升级策略归一测试（REQ-261007133807-eda6 t10 · FR-4）

守四件事（对应 FR-4 的"规则上看得见什么时候会叫我"）：
1) **缺省即写显式默认值**（不再落 NULL/{}——存量 7 条规则实测全是空）；
2) 给了策略 → 与默认值**合并**后写入（可覆写，半个策略不留坑）；
3) 非法值 → 400（`anomaly_change_pct ≤ 0` 会让每次触发都升级，必须挡住）；
4) 修改入口**不传策略就不动策略**（读不篡改、写不越权）。

写入口有三个（单条创建 / 修改 / 批量），三个都要覆盖——漏一个就是静默缺口。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_async import router

VALID_CONDITIONS = [{'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}}]
DEFAULT_POLICY = {'auto_escalate': True, 'anomaly_change_pct': 5.0}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _create(client, **extra):
    body = {'symbol': '000001.SZ', 'conditions': VALID_CONDITIONS, 'context': 'policy 测试'}
    body.update(extra)
    resp = client.post('/api/watch/rules', json=body)
    return resp


@pytest.fixture
def cleanup(client):
    created = []
    yield created
    for rid in created:
        client.delete(f'/api/watch/rules/{rid}')


def test_create_without_policy_writes_explicit_default(client, cleanup):
    resp = _create(client)
    assert resp.status_code == 200, resp.json()
    rule = resp.json()['data']['rule']
    cleanup.append(rule['id'])
    assert rule['escalation_policy'] == DEFAULT_POLICY


def test_create_with_partial_policy_merges_default(client, cleanup):
    """只给阈值 → 总开关仍要有显式值（半个策略会让"何时叫我"又看不见）。"""
    resp = _create(client, escalation_policy={'anomaly_change_pct': 3.5})
    assert resp.status_code == 200, resp.json()
    rule = resp.json()['data']['rule']
    cleanup.append(rule['id'])
    assert rule['escalation_policy'] == {'auto_escalate': True, 'anomaly_change_pct': 3.5}


def test_create_accepts_string_boolean(client, cleanup):
    """JSONB 宽容度：字符串 "false" 与布尔 false 等价（既有数据里有字符串形态）。"""
    resp = _create(client, escalation_policy={'auto_escalate': 'false'})
    rule = resp.json()['data']['rule']
    cleanup.append(rule['id'])
    assert rule['escalation_policy']['auto_escalate'] is False


def test_create_rejects_non_object_policy(client):
    resp = _create(client, escalation_policy=[1, 2])
    assert resp.status_code == 400
    assert 'escalation_policy' in resp.json()['error']


def test_create_rejects_non_positive_threshold(client):
    """阈值 ≤ 0 = 每次触发都升级（静默放大打扰次数）→ 必须 400。"""
    for bad in (0, -1, 'abc'):
        resp = _create(client, escalation_policy={'anomaly_change_pct': bad})
        assert resp.status_code == 400, bad
        assert 'anomaly_change_pct' in resp.json()['error']


def test_update_without_policy_does_not_touch_policy(client, cleanup):
    """修改入口不传策略 → 既有策略原样保留（不许被"顺手重置"）。"""
    rid = _create(client, escalation_policy={'anomaly_change_pct': 7.0}).json()['data']['rule']['id']
    cleanup.append(rid)
    resp = client.put(f'/api/watch/rules/{rid}', json={'enabled': False})
    assert resp.status_code == 200, resp.json()
    assert resp.json()['data']['rule']['escalation_policy']['anomaly_change_pct'] == 7.0


def test_update_with_policy_merges_default(client, cleanup):
    rid = _create(client).json()['data']['rule']['id']
    cleanup.append(rid)
    resp = client.put(f'/api/watch/rules/{rid}', json={'escalation_policy': {'anomaly_change_pct': 2.0}})
    assert resp.status_code == 200, resp.json()
    assert resp.json()['data']['rule']['escalation_policy'] == {
        'auto_escalate': True, 'anomaly_change_pct': 2.0}


def test_update_rejects_invalid_policy(client, cleanup):
    rid = _create(client).json()['data']['rule']['id']
    cleanup.append(rid)
    resp = client.put(f'/api/watch/rules/{rid}', json={'escalation_policy': {'anomaly_change_pct': 0}})
    assert resp.status_code == 400


def test_created_rule_policy_is_explicit_in_db(client, cleanup):
    """**psql 等价回读**（pytest 下已切测试库）：库里落的是显式默认值，不是 NULL/{}。

    为什么单独一条：响应体可能来自 ORM 对象（未落库也能看到），只有直接读库才能证明
    "缺省即写显式值"这条 FR-4 判据真的落到了行上。
    """
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    resp = _create(client)
    assert resp.status_code == 200, resp.json()
    rid = resp.json()['data']['rule']['id']
    cleanup.append(rid)
    with get_engine().connect() as conn:
        row = conn.execute(text('select escalation_policy from quant.watch_rules where id=:i'),
                           {'i': rid}).first()
    assert row is not None, '规则未落库'
    assert row[0] == DEFAULT_POLICY, row[0]


def test_batch_create_without_policy_writes_default(client, cleanup):
    """批量入口同样归一（三个写入口一个都不能漏）。"""
    resp = client.post('/api/watch/rules/batch', json={
        'reason': 'policy 测试', 'source_trigger_id': 0,
        'actions': [{'op': 'create', 'symbol': '000002.SZ', 'conditions': VALID_CONDITIONS}],
    })
    assert resp.status_code == 200, resp.json()
    data = resp.json()['data']
    assert data['results'][0]['success'] is True, data
    rid = data['results'][0]['rule_id']
    cleanup.append(rid)
    listed = client.get('/api/watch/rules?symbol=000002.SZ').json()['data']['rules']
    rule = next(r for r in listed if r['id'] == rid)
    assert rule['escalation_policy'] == DEFAULT_POLICY


# ── t11（FR-4）：读接口回显「何时会叫我」───────────────────────────────
def test_list_rules_explains_when_it_will_wake_me(client, cleanup):
    resp = _create(client)
    rid = resp.json()['data']['rule']['id']
    cleanup.append(rid)
    listed = client.get('/api/watch/rules?symbol=000001.SZ').json()['data']['rules']
    rule = next(r for r in listed if r['id'] == rid)
    assert rule['escalation_explain'], '说明不得为空（空串 = 规则侧又看不见了）'
    assert '叫我' in rule['escalation_explain']
    assert rule['escalation_policy'] == DEFAULT_POLICY, '原字段必须原样保留（纯追加）'


def test_legacy_rule_explains_undeclared_and_read_does_not_rewrite(client, cleanup):
    """存量规则（策略 NULL）→ 说明如实写「未声明」，且**读不篡改数据**。"""
    from sqlalchemy import text

    from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
    from infrastructure.persistence.database.engine import get_engine

    rule = WatchRuleRepository().create_rule(symbol='000003.SZ', conditions=VALID_CONDITIONS,
                                             context='t11 存量')
    rid = rule.id
    cleanup.append(rid)
    with get_engine().begin() as conn:
        conn.execute(text('update quant.watch_rules set escalation_policy = null where id = :i'),
                     {'i': rid})

    listed = client.get('/api/watch/rules?symbol=000003.SZ').json()['data']['rules']
    row = next(r for r in listed if r['id'] == rid)
    assert '未声明' in row['escalation_explain']
    assert row['escalation_policy'] is None, '回复里如实回 NULL，不要假装已声明'

    with get_engine().connect() as conn:
        val = conn.execute(text('select escalation_policy from quant.watch_rules where id = :i'),
                           {'i': rid}).scalar()
    assert val is None, '读接口不得回写数据（显式化只发生在新写入）'
