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

## 独立性审查发现的三个坑（2026-09-14 w-0f022172 复查，均已在此修掉）

1. **比对集曾取决于 import 历史**：Base 被 models 包与 adapters/**/repositories/* 共用，
   只"补 import"没法排除别的模块先注册进来的表 —— 全套跑（import 73 个仓储）时
   metadata 有 79 张表、隔离跑只有 40 张，于是同一份代码在全套里红、在隔离里绿。
   现在按"**声明该表的 mapped class 是否属于 models 包**"过滤，实测两种场景都恒为 40 张。
2. **库不可达时静默全绿**：原来 pytest.skip，唯一能挡本次复现的用例等于不存在。
   现在：未配置 → fail；连不上 → fail（明确写清原因）；只有显式
   DSH_ALLOW_MISSING_TEST_DB=1 才允许 skip。
3. **fixture 会对 QUANT_DATABASE_URL 指向的任意库执行 DDL**：会重放 migrations/*.sql。
   现在要求库名以 _test 结尾，否则直接 fail —— 该 fixture 的写副作用只允许落在测试库。

## 覆盖范围与诚实边界

* 只断言"**模型有、库没有**"（真会 500 的方向）。库里多出来的列（如两张订单表上的
  genome_version）不报错——多列不影响 ORM 写入，报出来只会变噪声。
* 比对集 = models 包声明的表；同库里由仓储层重复定义的表（如 p2_async_repositories 里
  extend_existing 的 automation_tasks）不在门禁范围内，属已知同类隐患（见工作日志遗留）。
* 测试库是**部分镜像**：脚下面 _ENV_ONLY_MISSING 里的列经核对"生产在位、测试库缺"，
  豁免但打印；硬缺列一律失败。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.orm import class_mapper

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / 'migrations'
MODELS_PACKAGE = 'infrastructure.persistence.orm.models'

DECISION_QUALITY_COLUMNS = (
    'decision_price', 'decision_at', 'price_source', 'fill_price', 'slippage_bps',
)

# 测试库（quant_test）是部分镜像，以下模型列只在 quant_investment 建过、测试库里没有。
# DB 侧已核对：生产 quant_investment 这些列**全部在位** → 属"测试库镜像不全"，不是
# 模型-库漂移，故豁免（同时打印，避免它变成新的静默盲区）。
_ENV_ONLY_MISSING = frozenset({
    'quant.pool_change_log.pool_name',
    'quant.strategy_configs.performance_status',
    'quant.strategy_configs.performance_evidence',
    'quant.strategy_configs.performance_checked_at',
    'quant.strategy_configs.structure_status',
    'quant.event_calendar.evidence_hash',
    'quant.event_calendar.scope',
    'quant.event_calendar.source_url',
    'quant.event_calendar.symbols',
})

# 允许"没有测试库也能跑"的唯一出口：显式环境变量。默认不允许静默跳过。
_ALLOW_MISSING_DB_ENV = 'DSH_ALLOW_MISSING_TEST_DB'


def _load_models():
    """返回 {表名: Table}，只含 **models 包自己声明**的表。

    不能直接用 Base.metadata：Base 被 models 包与 adapters/**/repositories/* 共用，
    别的模块 import 进来多少，metadata 就有多少张表 —— 同一份代码在全套跑与隔离跑
    会得到不同的比对集（实测 79 vs 40）。这里按"声明该表的 mapped class 的
    __module__ 是否属于 models 包"过滤，两种场景恒为同一集合。
    """
    import importlib
    import pkgutil

    import infrastructure.persistence.orm.models as models_pkg
    from infrastructure.persistence.orm.base import Base

    for mod in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module('%s.%s' % (models_pkg.__name__, mod.name))

    tables = {}
    for cls in list(Base.registry._class_registry.values()):
        if not hasattr(cls, '__mapper__'):
            continue
        if not str(getattr(cls, '__module__', '')).startswith(MODELS_PACKAGE):
            continue
        try:
            table = class_mapper(cls).persist_selectable
        except Exception:  # noqa: BLE001 - 未完成映射的类跳过
            continue
        tables[table.name] = table
    return tables


def _resolve_dsn():
    """测试库 DSN。缺配置返回 None（调用方 fail/按显式开关 skip）。"""
    if os.environ.get('QUANT_DATABASE_URL'):
        return os.environ['QUANT_DATABASE_URL']
    if os.environ.get('PGDATABASE'):
        user = os.environ.get('PGUSER') or os.environ.get('USER')
        host = os.environ.get('PGHOST', '127.0.0.1')
        port = os.environ.get('PGPORT', '5432')
        return 'postgresql://%s@%s:%s/%s' % (user, host, port, os.environ['PGDATABASE'])
    return None


def _require_test_dsn():
    """取 DSN 并校验；拿不到或指向非测试库一律 fail（不静默）。"""
    dsn = _resolve_dsn()
    if not dsn:
        if os.environ.get(_ALLOW_MISSING_DB_ENV) == '1':
            pytest.skip('未配置测试库，且 %s=1（显式允许）' % _ALLOW_MISSING_DB_ENV)
        pytest.fail('未配置测试库（QUANT_DATABASE_URL / PGDATABASE）。'
                    '本门禁必须连库才有意义；确实无库时请显式设 %s=1' % _ALLOW_MISSING_DB_ENV)
    db_name = (make_url(dsn).database or '')
    if not db_name.endswith('_test'):
        pytest.fail(
            '拒绝在非测试库上跑本门禁：DSN 指向 %r（要求库名以 _test 结尾）。'
            '本 fixture 会重放 migrations/*.sql 的 DDL，只允许打在测试库上。' % db_name
        )
    return dsn


@pytest.fixture(scope='module')
def engine():
    from sqlalchemy import create_engine

    dsn = _require_test_dsn()
    try:
        eng = create_engine(dsn)
        with eng.connect():
            pass
    except Exception as e:  # noqa: BLE001
        pytest.fail('测试库不可达（%s）：%s。本门禁不允许"无库=通过"。' % (dsn, e))
    return eng


@pytest.fixture(scope='module')
def migrations_applied(engine):
    """把 migrations/*.sql 幂等应用到测试库（测试库口径 = 迁移声明口径）。"""
    if not MIGRATIONS_DIR.is_dir():
        pytest.fail('没有 migrations 目录：无法确认测试库口径来自何处')
    dsn = _require_test_dsn()
    sql_files = sorted(MIGRATIONS_DIR.glob('*.sql'))
    if not sql_files:
        pytest.fail('没有迁移文件：无法确认测试库口径来自何处')
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
#   42P01 引用对象不存在、42703 列不存在、42P07 表已存在、42701 列已存在、42P16 约束/索引已存在
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
    """models 包声明的每一列都必须真实存在于数据库。"""
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
        + chr(10) + chr(10) + '已比对 %d 张表（models 包声明集）；测试库未建表 %d 张（跳过）：%s'
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

    立即单**表**加列是为了两张表口径一致（该列的写入方是后续"立即单执行质量"设计）；
    但**模型**侧声明它们会让 SQLAlchemy 把 quant.simulation_order 的 INSERT 带上这 5 列
    ——那正是 09-14 的 500 根因。这条断言是本次复现的唯一硬闸门：全模型比对在"迁移
    已应用"的库上抓不到它（列被迁移补上了）。
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
