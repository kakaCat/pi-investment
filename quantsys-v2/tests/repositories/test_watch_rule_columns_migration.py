"""watch_rules position_state / interval_sec 迁移测试（RFC 017 §2.2/§2.3/§3，2026-10-21）

## 为什么这样测

迁移的验收点是「幂等」与「回填口径」，两者都是**SQL 行为**——用 mock 断言"调用了
ALTER/UPDATE"证明不了口径。故每个用例在 quant_test 里建一个**临时 schema**，
放入 `watch_rules` / `simulation_positions` 的最小镜像，跑迁移模块里**真实的**
建列/回填 SQL，结束后 `DROP SCHEMA ... CASCADE`：

- 不碰共享库 `quant.watch_rules` 的存量数据（迁移可能已被 --apply 到测试库）；
- 不依赖共享库是否已迁移（测试自己造 schema）；
- 回填口径逐条可验：linked_account 匹配、多账户同标的、后缀归一/冲突、
  正持仓过滤、空账户/空白账户、幂等重跑、单向晋升。

迁移模块文件名以数字开头（不能直接 import），按路径加载（与
tests/services/test_runtime_complete.py 同一手法）。
"""
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (REPO_ROOT / 'infrastructure' / 'persistence' / 'migrations'
                  / '20261021_watch_rules_position_interval.py')


@pytest.fixture(scope='module')
def migration():
    spec = importlib.util.spec_from_file_location(
        'watch_rules_position_interval_migration', MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def engine():
    from qs_kernel.infrastructure.persistence.database.engine import get_engine
    eng = get_engine()
    with eng.connect() as conn:
        dbname = conn.execute(text('select current_database()')).scalar()
    # 安全阀：迁移测试会执行 DDL，只允许落在 *_test 库（与 conftest 同一铁律）
    assert str(dbname).endswith('_test'), '迁移测试只允许在 *_test 库执行，实际：%s' % dbname
    return eng


@pytest.fixture()
def schema(engine, migration):
    """临时 schema + 最小镜像表；用例结束即销毁。"""
    name = 'wrmig_' + uuid.uuid4().hex[:10]
    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA %s' % name))
        conn.execute(text(
            'CREATE TABLE %s.watch_rules (\n'
            '    id serial PRIMARY KEY,\n'
            '    symbol varchar(20) NOT NULL,\n'
            '    linked_account varchar(60),\n'
            '    account varchar(50),\n'
            '    enabled boolean NOT NULL DEFAULT TRUE)'
            % name))
        conn.execute(text(
            'CREATE TABLE %s.simulation_positions (\n'
            '    id serial PRIMARY KEY,\n'
            '    account_name varchar(64),\n'
            '    symbol varchar(20),\n'
            '    shares_total integer)'
            % name))
    try:
        yield name
    finally:
        with engine.begin() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS %s CASCADE' % name))


# ── 造数/读取小工具（恒用 parameterized SQL，临时 schema 只做标识符拼接）──────

def _add_rule(conn, schema, symbol, linked_account=None):
    return conn.execute(text(
        'INSERT INTO %s.watch_rules (symbol, linked_account) VALUES (:s, :a) RETURNING id' % schema
    ), {'s': symbol, 'a': linked_account}).scalar()


def _add_position(conn, schema, account_name, symbol, shares_total):
    conn.execute(text(
        'INSERT INTO %s.simulation_positions (account_name, symbol, shares_total) '
        'VALUES (:a, :s, :n)' % schema
    ), {'a': account_name, 's': symbol, 'n': shares_total})


def _states(conn, schema):
    rows = conn.execute(text(
        'SELECT id, position_state, interval_sec FROM %s.watch_rules ORDER BY id' % schema
    )).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


# ── 幂等与列元数据 ───────────────────────────────────────────────────────

class TestColumnsIdempotent:

    def test_dry_run_does_not_touch_schema(self, engine, schema, migration):
        with engine.begin() as conn:
            result = migration.apply_migration(conn, schema, apply=False)
            assert [c['status'] for c in result['columns']] == ['would-add', 'would-add']
            assert migration.column_names(conn, schema) >= {'id', 'symbol', 'linked_account'}
            assert not ({'position_state', 'interval_sec'} & migration.column_names(conn, schema))

    def test_apply_twice_is_idempotent_and_verifies_metadata(self, engine, schema, migration):
        with engine.begin() as conn:
            first = migration.apply_migration(conn, schema, apply=True)
            second = migration.apply_migration(conn, schema, apply=True)

            assert [c['status'] for c in first['columns']] == ['added', 'added']
            assert [c['status'] for c in second['columns']] == ['exists', 'exists']
            assert first['backfilled'] == second['backfilled'] == 0

            info = migration.column_info(conn, schema)
            assert info['position_state']['nullable'] == 'NO'
            assert 'none' in (info['position_state']['default'] or '')
            assert info['interval_sec']['nullable'] == 'YES'
            assert info['interval_sec']['default'] is None

    def test_ensure_columns_reports_existing_without_ddl(self, engine, schema, migration):
        with engine.begin() as conn:
            migration.ensure_columns(conn, schema, apply=True)
            # 再跑一次（不抛、不改状态）
            again = migration.ensure_columns(conn, schema, apply=True)
            assert [c['status'] for c in again] == ['exists', 'exists']

    def test_missing_table_raises_clear_error(self, engine, migration):
        with engine.begin() as conn:
            with pytest.raises(RuntimeError):
                migration.ensure_columns(conn, 'no_such_schema_xyz', apply=False)


# ── 回填口径 ─────────────────────────────────────────────────────────────

class TestBackfillSemantics:

    def test_linked_account_match_and_symbol_normalization(self, engine, schema, migration):
        with engine.begin() as conn:
            # 规则存不带后缀 / 带后缀两种写法，持仓一律带后缀（生产常见形态）
            r_code = _add_rule(conn, schema, '600519', 'agent_virtual')
            r_suffix = _add_rule(conn, schema, '600519.SH', 'agent_virtual')
            r_other_account = _add_rule(conn, schema, '600519', 'user_main_simulation')
            # 同代码不同交易所：指数 000001.SH vs 平安银行 000001.SZ，不能串
            r_cross_exchange = _add_rule(conn, schema, '000001.SH', 'agent_virtual')
            _add_position(conn, schema, 'agent_virtual', '600519.SH', 100)
            _add_position(conn, schema, 'agent_virtual', '000001.SZ', 500)
            migration.ensure_columns(conn, schema, apply=True)

            n = migration.backfill_position_state(conn, schema, apply=True)
            states = _states(conn, schema)

        assert n == 2, '只有 600519 的两条规则该被晋升（其它账户/跨交易所不算）'
        assert states[r_code][0] == 'holding'
        assert states[r_suffix][0] == 'holding'
        assert states[r_other_account][0] == 'none'      # linked_account 不匹配 → 不晋升
        assert states[r_cross_exchange][0] == 'none'     # 交易所后缀冲突 → 不晋升

    def test_multi_account_positions_are_per_account(self, engine, schema, migration):
        """同一标的多账户持仓：linked_account 指向哪个账户就按哪个账户判。"""
        with engine.begin() as conn:
            r_agent = _add_rule(conn, schema, '300750.SZ', 'agent_virtual')
            r_user = _add_rule(conn, schema, '300750.SZ', 'user_main_simulation')
            r_absent = _add_rule(conn, schema, '300750.SZ', 'agent_brain')
            r_universal = _add_rule(conn, schema, '300750.SZ', None)
            _add_position(conn, schema, 'agent_virtual', '300750.SZ', 100)
            _add_position(conn, schema, 'user_main_simulation', '300750.SZ', 200)
            migration.ensure_columns(conn, schema, apply=True)

            migration.backfill_position_state(conn, schema, apply=True)
            states = _states(conn, schema)

        assert states[r_agent][0] == 'holding'
        assert states[r_user][0] == 'holding'
        assert states[r_absent][0] == 'none'
        # 无账户规则 = 通用观察：任意账户有持仓即 holding（RFC 017 §3）
        assert states[r_universal][0] == 'holding'

    def test_blank_linked_account_treated_as_universal(self, engine, schema, migration):
        with engine.begin() as conn:
            r_empty = _add_rule(conn, schema, '600036.SH', '')
            r_spaces = _add_rule(conn, schema, '600036.SH', '  agent_virtual  ')
            _add_position(conn, schema, 'agent_virtual', '600036.SH', 100)
            migration.ensure_columns(conn, schema, apply=True)

            migration.backfill_position_state(conn, schema, apply=True)
            states = _states(conn, schema)

        assert states[r_empty][0] == 'holding'   # 空串 == 无账户
        assert states[r_spaces][0] == 'holding'  # 两端空白不阻断匹配

    def test_only_positive_positions_count(self, engine, schema, migration):
        with engine.begin() as conn:
            r_zero = _add_rule(conn, schema, '600000.SH', 'agent_virtual')
            r_null_shares = _add_rule(conn, schema, '600001.SH', 'agent_virtual')
            r_positive = _add_rule(conn, schema, '600002.SH', 'agent_virtual')
            _add_position(conn, schema, 'agent_virtual', '600000.SH', 0)
            _add_position(conn, schema, 'agent_virtual', '600001.SH', None)
            _add_position(conn, schema, 'agent_virtual', '600002.SH', 100)
            migration.ensure_columns(conn, schema, apply=True)

            migration.backfill_position_state(conn, schema, apply=True)
            states = _states(conn, schema)

        assert states[r_zero][0] == 'none'
        assert states[r_null_shares][0] == 'none'
        assert states[r_positive][0] == 'holding'

    def test_backfill_is_idempotent_and_one_way(self, engine, schema, migration):
        """重跑 0 行；不把运行时已写的 holding 刷回去（迁移不是对账器）。"""
        with engine.begin() as conn:
            migration.ensure_columns(conn, schema, apply=True)
            held = _add_rule(conn, schema, '601888.SH', 'agent_virtual')
            plain = _add_rule(conn, schema, '601889.SH', 'agent_virtual')
            _add_position(conn, schema, 'agent_virtual', '601888.SH', 100)
            # 迁移后再由 fill 事件写成 holding、但持仓表已无仓位的规则（模拟运行时状态）
            runtime_holding = _add_rule(conn, schema, '601890.SH', 'agent_virtual')
            conn.execute(text(
                'UPDATE %s.watch_rules SET position_state = :st WHERE id = :i' % schema
            ), {'st': 'holding', 'i': runtime_holding})

            first = migration.backfill_position_state(conn, schema, apply=True)
            states_after_first = _states(conn, schema)
            second = migration.backfill_position_state(conn, schema, apply=True)
            states_after_second = _states(conn, schema)

        assert first == 1
        assert second == 0
        assert states_after_first == states_after_second
        assert states_after_second[held][0] == 'holding'
        assert states_after_second[plain][0] == 'none'
        assert states_after_second[runtime_holding][0] == 'holding'  # 单向：不被刷回

    def test_existing_rows_get_default_none(self, engine, schema, migration):
        """迁移前就存在的规则：列加上后由 DB 默认变 'none'，interval_sec 仍 NULL。"""
        with engine.begin() as conn:
            before = _add_rule(conn, schema, '600887.SH', 'agent_virtual')
            migration.apply_migration(conn, schema, apply=True)
            state, interval = _states(conn, schema)[before]

        assert state == 'none'
        assert interval is None

    def test_dry_run_counts_candidates_without_writing(self, engine, schema, migration):
        with engine.begin() as conn:
            migration.ensure_columns(conn, schema, apply=True)
            _add_rule(conn, schema, '600519', 'agent_virtual')
            _add_position(conn, schema, 'agent_virtual', '600519.SH', 100)
            assert migration.count_backfill_candidates(conn, schema) == 1
            assert migration.backfill_position_state(conn, schema, apply=False) == 1
            assert _states(conn, schema)[1][0] == 'none'   # dry-run 未写

    def test_schema_without_positions_table_is_safe(self, engine, migration):
        """分库/新环境没有持仓表时：建列成功、回填 0、不抛。"""
        name = 'wrmig_' + uuid.uuid4().hex[:10]
        try:
            with engine.begin() as conn:
                conn.execute(text('CREATE SCHEMA %s' % name))
                conn.execute(text(
                    'CREATE TABLE %s.watch_rules (id serial PRIMARY KEY, symbol varchar(20), '
                    'linked_account varchar(60))' % name))
                result = migration.apply_migration(conn, name, apply=True)
                assert [c['status'] for c in result['columns']] == ['added', 'added']
                assert result['backfilled'] == 0
        finally:
            with engine.begin() as conn:
                conn.execute(text('DROP SCHEMA IF EXISTS %s CASCADE' % name))


# ── CLI 入口 ─────────────────────────────────────────────────────────────

class TestMigrationCli:

    def test_cli_dry_run_then_apply(self, engine, schema, migration, capsys):
        dsn = engine.url.render_as_string(hide_password=False)
        assert migration.main(['--schema', schema, '--dsn', dsn]) == 0
        with engine.connect() as conn:
            assert not ({'position_state', 'interval_sec'} & migration.column_names(conn, schema))

        assert migration.main(['--schema', schema, '--dsn', dsn, '--apply']) == 0
        out = capsys.readouterr().out
        assert 'VERIFY OK' in out
        with engine.connect() as conn:
            assert {'position_state', 'interval_sec'} <= migration.column_names(conn, schema)

    def test_cli_rejects_bad_schema_identifier(self, engine, migration):
        dsn = engine.url.render_as_string(hide_password=False)
        with pytest.raises(ValueError):
            migration.main(['--schema', 'quant; DROP TABLE x', '--dsn', dsn])
