"""ORM ↔ 数据库 schema 漂移门禁（2026-09-14，w-2129d492）。

## 为什么有这个测试

2026-09-13 的 M5 提交（cedfb4ed）给订单模型加了 5 列（decision_price / decision_at /
price_source / fill_price / slippage_bps），DDL 只落在 quant.simulation_pending_orders，
ORM 却定义在 SimulationOrder 上 → 两侧都错位：

  · 立即单（quant.simulation_order）：模型有列、表没有 → SQLAlchemy flush 带上全列
    → INSERT 阶段 100% 报 column "decision_price" ... does not exist，路由返回 500；
  · 挂单（quant.simulation_pending_orders）：表有列、模型没有 → 构造即
    TypeError: 'decision_price' is an invalid keyword argument。

两处都不是单测能发现的——因为**本仓没有迁移框架**（无 alembic / 无 schema 版本表），
模型与 DDL 是两份人工产物、没有任何一致性校验。这个测试就是那道缺失的校验：
凡是"模型声明了、库里没有"的列，一律失败。

## 覆盖范围与诚实边界

* 只断言"**模型有、库没有**"（真会 500 的方向）。库里多出来的列（如两张订单表上的
  genome_version）不报错——多列不影响 ORM 写入，报出来只会变噪声。
* 测试库（.env.test → quant_test）按 migrations/*.sql 幂等升级后再比对：这既是
  "测试库口径 = 迁移声明口径"，也逼着新列必须落成迁移文件（改了模型不写迁移 → 这里红）。
* 测试库里不存在的表跳过（计数写进断言消息）——没建表 ≠ 漂移，但也不假装覆盖了。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / 'migrations'

# 测试库（quant_test）是部分镜像，以下两处模型列只在 quant_investment 建过、测试库里没有。
# DB 侧已核对：生产 quant_investment 两处都在位，缺的只是测试库 → 属"测试库镜像不全"，
# 不是模型-库漂移，故在此豁免（同时打印出来，避免它变成新的静默盲区）。
# quant.pool_change_log.pool_name / quant.strategy_configs.performance_{status,evidence,checked_at} /
# quant.strategy_configs.structure_status
_ENV_ONLY_MISSING = frozenset({
    'quant.pool_change_log.pool_name',
    'quant.strategy_configs.performance_status',
    'quant.strategy_configs.performance_evidence',
    'quant.strategy_configs.performance_checked_at',
    'quant.strategy_configs.structure_status',
})

DECISION_QUALITY_COLUMNS = (
    'decision_price', 'decision_at', 'price_source', 'fill_price', 'slippage_bps',
)


def _load_models():
    """导入全部 ORM 模型并返回 {表名: Table}。

    必须显式 import 该包的**每一个**模块：只 import 包名时，模型注册到什么程度取决于
    收集顺序（谁先 import 了别的仓储/服务）——实测先跑 tests/test_trade_cash_race.py
    会让比对从 35 张表变 59 张，同一份代码给出两种结论。门禁必须确定。
    """
    import importlib
    import pkgutil

    import infrastructure.persistence.orm.models as models_pkg
    from infrastructure.persistence.orm.base import Base

    for mod in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module('%s.%s' % (models_pkg.__name__, mod.name))

    return {t.name: t for t in Base.metadata.tables.values()}


def _resolve_dsn():
    if os.environ.get('QUANT_DATABASE_URL'):
        return os.environ['QUANT_DATABASE_URL']
    if os.environ.get('PGDATABASE'):
        user = os.environ.get('PGUSER') or os.environ.get('USER')
        host = os.environ.get('PGHOST', '127.0.0.1')
        port = os.environ.get('PGPORT', '5432')
        return 'postgresql://%s@%s:%s/%s' % (user, host, port, os.environ['PGDATABASE'])
    return None


@pytest.fixture(scope='module')
def engine():
    from sqlalchemy import create_engine

    dsn = _resolve_dsn()
    if not dsn:
        pytest.skip('未配置测试库（QUANT_DATABASE_URL / PGDATABASE）')
    try:
        eng = create_engine(dsn)
        with eng.connect():
            pass
    except Exception as e:  # noqa: BLE001
        pytest.skip('测试库不可达：%s' % e)
    return eng


@pytest.fixture(scope='module')
def migrations_applied(engine):
    """把 migrations/*.sql 幂等应用到测试库（测试库口径 = 迁移声明口径）。"""
    if not MIGRATIONS_DIR.is_dir():
        pytest.skip('没有 migrations 目录')
    dsn = _resolve_dsn()
    sql_files = sorted(MIGRATIONS_DIR.glob('*.sql'))
    if not sql_files:
        pytest.skip('没有迁移文件')
    applied, skipped = [], []
    for path in sql_files:
        outcome = _apply_migration(dsn, path)
        if outcome == 'applied':
            applied.append(path.name)
        else:
            skipped.append('%s（%s）' % (path.name, outcome))
    engine.dispose()
    return {'applied': applied, 'skipped': skipped}


# 迁移脚本面向生产库的**全量** schema，测试库是部分镜像；且历史上并非每条迁移都写成
# 幂等（已有 ALTER 不带 IF NOT EXISTS）。这几类"环境/既有对象"错误不算漂移：
#   42P01 引用对象不存在（如 public.tasks 在测试库没有）
#   42703 列不存在、42P07 表已存在、42701 列已存在、42P16 约束/索引已存在
_BENIGN_SQLSTATE = {'42P01', '42703', '42P07', '42701', '42P16'}


def _apply_migration(dsn, path) -> str:
    """跑一条迁移；返回 'applied' 或跳过原因（非环境类错误直接失败）。

    每条迁移用**独立连接**：脚本自带 BEGIN/COMMIT、且失败可能把事务留在 aborted 态
    （InFailedSqlTransaction）——共用连接会互相污染，让后续脚本全部假失败。
    原生驱动而非 SQLAlchemy：后者把脚本里的 % 当参数占位符（注释含 % 是常态）。
    """
    import psycopg2

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(path.read_text(encoding='utf-8'))
    except psycopg2.Error as e:
        if e.pgcode in _BENIGN_SQLSTATE:
            return '测试库环境不适用: %s' % e.pgcode
        raise AssertionError('迁移 %s 无法应用：%s' % (path.name, e))
    finally:
        conn.close()
    return 'applied'


def test_orm_columns_all_exist_in_database(engine, migrations_applied):
    """所有 ORM 表：模型声明的每一列都必须真实存在于数据库。"""
    from sqlalchemy import inspect

    tables = _load_models()
    insp = inspect(engine)
    missing = []
    checked = []
    absent = []

    for name, table in sorted(tables.items()):
        schema = table.schema or 'public'
        if not insp.has_table(name, schema=schema):
            absent.append('%s.%s' % (schema, name))
            continue
        db_cols = {c['name'] for c in insp.get_columns(name, schema=schema)}
        model_cols = {c.name for c in table.columns}
        checked.append('%s.%s' % (schema, name))
        for col in sorted(model_cols - db_cols):
            missing.append('%s.%s.%s' % (schema, name, col))

    hard_missing = [m for m in missing if m not in _ENV_ONLY_MISSING]
    env_missing = sorted(set(missing) & _ENV_ONLY_MISSING)
    if env_missing:
        print('测试库镜像不全（DB 侧已核对生产在位，非漂移）：%s' % ', '.join(env_missing))
    assert not hard_missing, (
        'ORM 声明了数据库不存在的列（写入必炸：INSERT 会带上全列）:' + chr(10) + '  - '
        + (chr(10) + '  - ').join(hard_missing)
        + chr(10) + chr(10) + '已比对 %d 张表；测试库未建表 %d 张（跳过）：%s'
        % (len(checked), len(absent), ', '.join(absent) if absent else '无')
        + chr(10) + '修复：加一条 migrations/*.sql 显式 ALTER TABLE，或把该列从模型里删掉。'
    )
    assert checked, '没有可比对的表：测试库疑似未初始化'


def test_order_tables_carry_execution_quality_columns(engine, migrations_applied):
    """回归锚点：M5 的 5 列漂移不许再复现（两张订单表口径必须一致）。"""
    from sqlalchemy import inspect

    insp = inspect(engine)
    for table in ('simulation_order', 'simulation_pending_orders'):
        if not insp.has_table(table, schema='quant'):
            pytest.skip('测试库无 quant.%s' % table)
        db_cols = {c['name'] for c in insp.get_columns(table, schema='quant')}
        missing = [c for c in DECISION_QUALITY_COLUMNS if c not in db_cols]
        assert not missing, 'quant.%s 缺执行质量列 %s' % (table, missing)


def test_decision_quality_columns_live_on_pending_order_model_only():
    """方向断言：立即单模型不得声明这 5 列（埋点全在挂单路径上）。

    立即单表加列是为了两张表口径一致；但**模型**侧声明它们会让 SQLAlchemy 把
    quant.simulation_order 的 INSERT 带上这 5 列——那正是 09-14 的 500 根因。
    """
    tables = _load_models()
    order_cols = {c.name for c in tables['simulation_order'].columns}
    for col in DECISION_QUALITY_COLUMNS:
        assert col not in order_cols, (
            'SimulationOrder（立即单）不该声明 %s；决策质量列属于挂单路径' % col
        )
    pending_cols = {c.name for c in tables['simulation_pending_orders'].columns}
    for col in DECISION_QUALITY_COLUMNS:
        assert col in pending_cols, (
            'SimulationPendingOrder（挂单）缺 %s：create_pending_order 会传它，缺列即 TypeError' % col
        )
