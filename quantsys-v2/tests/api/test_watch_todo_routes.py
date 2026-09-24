"""待办闭环路由测试（REQ-c9f899 t5）

自己挂 router（不依赖 main.py —— 路由注册由 t12 负责），用 FastAPI TestClient
断言 200/400/404/409，并走**真实适配器 + 真实库**（不是 fake）：

  · 200：列表 / 认领（L1→L2）/ 关闭（含 L3+audit 合法路径）；
  · 400：terminal 非法 / ignored 缺 next_condition / L3+trade 缺 decision_audit_id；
  · 404：待办不存在；
  · 409：已终态再关闭、已终态再认领。

测试库说明（重要）：
  quant_test 尚未跑 20260918 迁移（t1 只对 quant_investment 建了 watch_todos）。本模块在
  **测试库** 准备所需的表结构（不碰 quant_investment、不执行迁移脚本）；无库则整体 skip
  （不伪造通过）。

  表结构口径：直接复用迁移文件里的 watch_todos 建表 DDL 与索引（importlib 读取常量），
  **不用 ORM create_all** —— ORM 只声明 level/closed_pair 两条 CHECK，迁移里另有
  ignored_needs_next / action_needs_audit，且三个索引只存在于迁移；用 ORM 建表会给测试库
  留下"半迁移"结构，反而让 t11 的迁移验收失真。若发现已有表缺这两条约束（半迁移残留），
  本 fixture 会按迁移口径重建它。
  ⚠️ 因此本文件同时验证了**应用层校验**（路由 400/404/409）与**DB 约束落位**（建表断言）；
  迁移幂等/回滚演练仍属 t11。
"""
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_todo_async import router
from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models.watch_todo import WatchTodo

#: 哨兵：测试账户 + 标的（便于 list 过滤与清理，远离真实数据）
TEST_ACCOUNT = 't5_sentinel_account'
TEST_SYMBOL = 'T5WATCH.SZ'
TEST_RULE_ID = 9990001


# ── REQ-ad0a t5：close 处置结论回执的外发拦截 ──────────────────────────────
# close 路由已接真实回执链（watch_loop_wiring.build_receipt_service → Agent OS/飞书）。
# 路由测试只验证「receipt 字段被真实填充」，绝不真发飞书：统一替换为内存 fake。
class _FakeReceiptRepo:
    def __init__(self):
        self.rows = []

    def record(self, todo_id, kind, channel=None, delivery_status=None,
               message_id=None, payload_digest=''):
        row = dict(todo_id=todo_id, kind=kind, channel=channel,
                   delivery_status=delivery_status, message_id=message_id,
                   payload_digest=payload_digest)
        self.rows.append(row)
        return row

    def list_by_todo(self, todo_id):
        return [r for r in self.rows if r['todo_id'] == todo_id]

    def exists(self, todo_id, kind, payload_digest=''):
        return any(r['todo_id'] == todo_id and r['kind'] == kind
                   and r['payload_digest'] == payload_digest for r in self.rows)


#: 本模块 close 触发的回执发送载荷（fixture 每个用例前清空）
RECEIPT_SENT = []


@pytest.fixture(autouse=True)
def _capture_receipt_sends(monkeypatch):
    """拦 close 回执的真实外发（Agent OS/飞书）与名称解析 DB 依赖。"""
    from types import SimpleNamespace

    from application.services.watch_engine import watch_loop_wiring as wiring
    from application.services.watch_engine.receipt_service import ReceiptService
    RECEIPT_SENT.clear()
    monkeypatch.setattr(
        wiring, 'build_receipt_service',
        lambda: ReceiptService(_FakeReceiptRepo(), sender=RECEIPT_SENT.append))
    monkeypatch.setattr(
        wiring, 'build_name_resolver',
        lambda: SimpleNamespace(
            resolve_batch=lambda symbols: {
                str(s).split('.')[0].strip(): '测试名' for s in symbols}))
    yield


#: 迁移文件（t1）：本模块的表结构**唯一事实源**，不另抄一份 DDL
_MIGRATION_FILE = (Path(__file__).resolve().parents[2]
                   / 'infrastructure' / 'persistence' / 'migrations'
                   / '20260918_watch_todo_loop.py')

#: 迁移建表必有的约束（ORM 只声明 level_check / closed_pair，其余仅存在于迁移；
#: 任一缺失即"半迁移"残留，本 fixture 会按迁移口径重建）
_REQUIRED_CONSTRAINTS = (
    'watch_todos_ignored_needs_next',    # terminal=ignored ⇒ next_condition 非空
    'watch_todos_action_needs_audit',    # 动作类终态 ⇒ decision_audit_id 非空
    'watch_todos_terminal_check',        # terminal 枚举
    'watch_todos_autonomy_check',        # autonomy 枚举
    'watch_todos_flow_state_check',      # flow_state 枚举
    'watch_todos_owner_kind_check',      # owner_kind 枚举
)


def _dsn():
    from infrastructure.persistence.database.engine import _resolve_db_dsn
    return _resolve_db_dsn()


def _db_available() -> bool:
    import psycopg2
    dsn = _dsn()
    if not dsn:
        return False
    try:
        psycopg2.connect(dsn).close()
    except Exception:  # noqa: BLE001
        return False
    return True


def _migration_ddl():
    """从迁移文件读 watch_todos 的 DDL 与索引（模块顶层只有常量，加载无副作用）"""
    spec = spec_from_file_location('_t5_watch_todo_migration', str(_MIGRATION_FILE))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    table_ddl = next(ddl for name, ddl in module.TABLES if name == 'watch_todos')
    indexes = [(name, target) for name, target in module.INDEXES
               if 'watch_todos' in target]
    return table_ddl, indexes


def _table_exists(cur) -> bool:
    cur.execute("SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'quant' AND table_name = 'watch_todos'")
    return cur.fetchone() is not None


def _ensure_schema() -> None:
    """把测试库的 quant.watch_todos 对齐到迁移口径（幂等）

    短连接 + autocommit，用完即关：不在请求线程的 scoped session 上做 DDL，
    避免"读事务持有 ACCESS SHARE 锁 → DDL 阻塞"（这正是本 fixture 第一版 DROP 挂死的原因）。
    """
    import psycopg2
    table_ddl, indexes = _migration_ddl()
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        if _table_exists(cur):
            cur.execute("SELECT conname FROM pg_constraint "
                        "WHERE conrelid = 'quant.watch_todos'::regclass")
            names = {row[0] for row in cur.fetchall()}
            missing = [c for c in _REQUIRED_CONSTRAINTS if c not in names]
            if missing:
                # 半迁移残留（如 ORM create_all 建的表）：按迁移口径重建，别留错误结构
                cur.execute('DROP TABLE quant.watch_todos')
        if not _table_exists(cur):
            cur.execute(table_ddl)
        for name, target in indexes:
            cur.execute('CREATE INDEX IF NOT EXISTS %s ON %s' % (name, target))
    finally:
        conn.close()


@pytest.fixture(scope='module')
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope='module')
def todo_table():
    if not _db_available():
        pytest.skip('test database unavailable')
    _ensure_schema()
    yield
    # 不删表：此刻表结构已与迁移目标一致，留给 t11 的迁移验收与其它用例；
    # 造出的行由 make_todo 逐条清理（见下）。



@pytest.fixture
def repo(todo_table):
    return WatchTodoRepository()


@pytest.fixture
def make_todo(repo):
    """造一条待办并登记，测试结束按 id 清理（只删自己造的行）"""
    created = []

    def _make(**over):
        kwargs = dict(symbol=TEST_SYMBOL, rule_id=TEST_RULE_ID, account=TEST_ACCOUNT,
                      level='P1', flow_state='L3', owner_kind='agent',
                      owner_ref='agent-dh', autonomy='autonomous', sla_seconds=1800,
                      due_at=datetime.now(timezone.utc) + timedelta(minutes=30))
        kwargs.update(over)
        todo = repo.create(**kwargs)
        created.append(todo.id)
        return todo

    yield _make
    session = get_session()
    if created:
        session.query(WatchTodo).filter(WatchTodo.id.in_(created)).delete(
            synchronize_session=False)
        session.commit()


def _fresh(todo_id):
    """绕过 ORM identity map 重新读（否则断言的是本线程缓存的旧值）"""
    get_session().expire_all()
    return WatchTodoRepository().get(todo_id)


# ── 表结构：与迁移口径一致（DB 侧双保险真的在）──────────────

def test_schema_matches_migration_contract(todo_table):
    """测试库的 watch_todos 必须与迁移口径一致（否则本文件的 DB 覆盖名不副实）"""
    import psycopg2
    conn = psycopg2.connect(_dsn())
    try:
        cur = conn.cursor()
        cur.execute("SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'quant.watch_todos'::regclass")
        names = {row[0] for row in cur.fetchall()}
        assert set(_REQUIRED_CONSTRAINTS) <= names, names
        cur.execute("SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'quant' AND tablename = 'watch_todos'")
        idx = {row[0] for row in cur.fetchall()}
        assert {'idx_watch_todos_overdue', 'idx_watch_todos_account',
                'idx_watch_todos_rule'} <= idx, idx
    finally:
        conn.close()


def test_db_check_rejects_ignored_without_next_condition(todo_table):
    """DB 双保险：绕过应用层直写，ignored 缺 next_condition 必须被 CHECK 拒绝"""
    import psycopg2
    from psycopg2 import IntegrityError
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        with pytest.raises(IntegrityError):
            cur.execute(
                "INSERT INTO quant.watch_todos "
                "(symbol, level, flow_state, sla_seconds, due_at, terminal, closed_at) "
                "VALUES ('T5DB.SZ','P2','L1',1800, now(), 'ignored', now())")
    finally:
        conn.close()


def test_db_check_rejects_action_without_audit(todo_table):
    """DB 双保险：terminal=handled + action_kind=trade 缺 decision_audit_id 必须被拒"""
    import psycopg2
    from psycopg2 import IntegrityError
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    try:
        cur = conn.cursor()
        with pytest.raises(IntegrityError):
            cur.execute(
                "INSERT INTO quant.watch_todos "
                "(symbol, level, flow_state, sla_seconds, due_at, terminal, closed_at, "
                " action_kind) "
                "VALUES ('T5DB.SZ','P2','L3',1800, now(), 'handled', now(), 'trade')")
    finally:
        conn.close()


# ── GET /api/watch/todos ─────────────────────────────────────

def test_list_todos_200(client, todo_table, make_todo):
    todo = make_todo()
    resp = client.get(f'/api/watch/todos?account={TEST_ACCOUNT}&limit=50')
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['success'] is True
    items = body['data']['items']
    assert body['data']['total'] == len(items)
    item = next(i for i in items if i['id'] == todo.id)
    assert item['symbol'] == TEST_SYMBOL
    assert item['level'] == 'P1'
    assert item['flow_state'] == 'L3'
    assert item['owner_kind'] == 'agent'
    assert item['terminal'] is None
    assert item['due_at']                      # ISO 字符串（datetime 不可直接 JSON 化）
    assert item['escalate_count'] == 0


def test_list_todos_default_excludes_terminal(client, todo_table, make_todo, repo):
    open_todo = make_todo()
    closed = make_todo()
    repo.close(closed.id, 'handled', action_kind='observe')

    resp = client.get(f'/api/watch/todos?account={TEST_ACCOUNT}&limit=200')
    assert resp.status_code == 200
    ids = [i['id'] for i in resp.json()['data']['items']]
    assert open_todo.id in ids
    assert closed.id not in ids               # 缺省只给未收敛（工作队列视图）

    resp_all = client.get(f'/api/watch/todos?account={TEST_ACCOUNT}&terminal=*&limit=200')
    assert closed.id in [i['id'] for i in resp_all.json()['data']['items']]


def test_list_todos_filters_by_level_and_flow(client, todo_table, make_todo):
    p1 = make_todo(level='P1', flow_state='L3')
    make_todo(level='P2', flow_state='L1')
    resp = client.get(f'/api/watch/todos?account={TEST_ACCOUNT}&level=P1&flow_state=L3')
    assert resp.status_code == 200
    ids = [i['id'] for i in resp.json()['data']['items']]
    assert p1.id in ids
    assert all(i['level'] == 'P1' and i['flow_state'] == 'L3'
               for i in resp.json()['data']['items'])


def test_list_todos_invalid_limit_falls_back(client, todo_table):
    resp = client.get(f'/api/watch/todos?account={TEST_ACCOUNT}&limit=abc')
    assert resp.status_code == 200


# ── POST /{id}/claim ─────────────────────────────────────────

def test_claim_200_moves_l1_to_l2(client, todo_table, make_todo):
    todo = make_todo(level='P2', flow_state='L1')
    resp = client.post(f'/api/watch/todos/{todo.id}/claim', json={'owner_ref': 'agent-dh'})
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']['todo']
    assert data['owner_ref'] == 'agent-dh'
    assert data['flow_state'] == 'L2'
    assert data['claimed_at']
    # 落库确实变了（跨线程重新读）
    assert _fresh(todo.id).flow_state == 'L2'


def test_claim_missing_owner_ref_400(client, todo_table, make_todo):
    todo = make_todo(flow_state='L1')
    resp = client.post(f'/api/watch/todos/{todo.id}/claim', json={})
    assert resp.status_code == 400
    assert resp.json()['error'] == 'invalid_request'


def test_claim_not_found_404(client, todo_table):
    resp = client.post('/api/watch/todos/999999999/claim', json={'owner_ref': 'agent-dh'})
    assert resp.status_code == 404
    assert resp.json()['success'] is False
    assert resp.json()['error'] == 'watch_todo_not_found'


def test_claim_already_closed_409(client, todo_table, make_todo, repo):
    todo = make_todo()
    repo.close(todo.id, 'handled', action_kind='observe')
    resp = client.post(f'/api/watch/todos/{todo.id}/claim', json={'owner_ref': 'agent-dh'})
    assert resp.status_code == 409
    assert resp.json()['error'] == 'watch_todo_already_closed'
    # 终态行不得被认领改写（claim 只在未终态时生效）
    fresh = _fresh(todo.id)
    assert fresh.claimed_at is None
    assert fresh.owner_ref == 'agent-dh'         # 建单时的 owner_ref 未被改成别人


# ── POST /{id}/close ─────────────────────────────────────────

def test_close_200_handled(client, todo_table, make_todo):
    todo = make_todo(flow_state='L3', level='P1')
    resp = client.post(f'/api/watch/todos/{todo.id}/close',
                       json={'terminal': 'handled', 'close_reason': '已按预案处置',
                             'action_kind': 'observe'})
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']
    assert data['todo']['terminal'] == 'handled'
    assert data['todo']['closed_at'] is not None
    assert data['todo']['close_reason'] == '已按预案处置'
    # REQ-ad0a t5（FR-14）：close 收敛即发处置结论回执，receipt 字段真实填充
    receipt = data['receipt']
    assert receipt is not None and receipt['kind'] == 'result'
    assert receipt['sent'] is True
    assert '结论：已处置' in receipt['message']
    assert '原因：已按预案处置' in receipt['message']
    assert len(RECEIPT_SENT) == 1             # 发送被拦截捕获（未真发飞书）
    fresh = _fresh(todo.id)
    assert fresh.terminal == 'handled'
    assert fresh.closed_at is not None


def test_close_invalid_terminal_400(client, todo_table, make_todo):
    todo = make_todo()
    resp = client.post(f'/api/watch/todos/{todo.id}/close', json={'terminal': 'done'})
    assert resp.status_code == 400
    assert resp.json()['error'] == 'watch_todo_invalid_terminal'
    assert _fresh(todo.id).terminal is None


def test_close_ignored_without_next_condition_400(client, todo_table, make_todo):
    todo = make_todo()
    resp = client.post(f'/api/watch/todos/{todo.id}/close',
                       json={'terminal': 'ignored', 'close_reason': '暂不动'})
    assert resp.status_code == 400
    assert resp.json()['error'] == 'watch_todo_missing_next_condition'
    assert _fresh(todo.id).terminal is None


def test_close_l3_trade_without_audit_400(client, todo_table, make_todo):
    todo = make_todo(flow_state='L3')
    resp = client.post(f'/api/watch/todos/{todo.id}/close',
                       json={'terminal': 'handled', 'action_kind': 'trade',
                             'close_reason': '已减仓'})
    assert resp.status_code == 400
    assert resp.json()['error'] == 'watch_todo_missing_audit'
    assert _fresh(todo.id).terminal is None


def test_close_l3_trade_with_audit_200(client, todo_table, make_todo):
    todo = make_todo(flow_state='L3')
    resp = client.post(f'/api/watch/todos/{todo.id}/close',
                       json={'terminal': 'handled', 'action_kind': 'trade',
                             'close_reason': '已减仓', 'decision_audit_id': 'DA-t5-1'})
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']['todo']
    assert data['decision_audit_id'] == 'DA-t5-1'
    assert _fresh(todo.id).decision_audit_id == 'DA-t5-1'


def test_close_ignored_with_next_condition_200(client, todo_table, make_todo):
    todo = make_todo()
    resp = client.post(f'/api/watch/todos/{todo.id}/close',
                       json={'terminal': 'ignored', 'close_reason': '幅度不够',
                             'next_condition': '放量站上 27 再看', 'action_kind': 'observe'})
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']['todo']
    assert data['terminal'] == 'ignored'
    assert data['next_condition'] == '放量站上 27 再看'


def test_close_already_closed_409(client, todo_table, make_todo):
    todo = make_todo()
    first = client.post(f'/api/watch/todos/{todo.id}/close',
                        json={'terminal': 'handled', 'action_kind': 'observe'})
    assert first.status_code == 200
    second = client.post(f'/api/watch/todos/{todo.id}/close',
                         json={'terminal': 'expired'})
    assert second.status_code == 409
    assert second.json()['error'] == 'watch_todo_already_closed'
    # 终态与首次一致（不被二次改写，I3）
    assert _fresh(todo.id).terminal == 'handled'


def test_close_not_found_404(client, todo_table):
    resp = client.post('/api/watch/todos/999999999/close', json={'terminal': 'handled'})
    assert resp.status_code == 404
    assert resp.json()['error'] == 'watch_todo_not_found'


def test_close_only_writes_terminal_fields(client, todo_table, make_todo):
    """close 只动终态字段：身份/级别/归属/SLA 一律不变"""
    todo = make_todo(flow_state='L3', level='P1')
    before = _fresh(todo.id)
    identity = {f: getattr(before, f) for f in (
        'symbol', 'rule_id', 'account', 'level', 'flow_state', 'owner_kind',
        'owner_ref', 'autonomy', 'sla_seconds', 'due_at', 'escalate_count')}

    resp = client.post(f'/api/watch/todos/{todo.id}/close',
                       json={'terminal': 'expired', 'close_reason': 'SLA 超时机械收敛'})
    assert resp.status_code == 200, resp.text

    after = _fresh(todo.id)
    for field_name, value in identity.items():
        assert getattr(after, field_name) == value, field_name
    assert after.terminal == 'expired'
    assert after.closed_at is not None
