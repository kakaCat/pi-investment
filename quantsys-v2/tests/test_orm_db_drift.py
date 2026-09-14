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
* 比对集 = models 包声明的表 + **仓储层内联模型**（2026-09-14 w-2129d492 补盲区）。
  原先只比对 models 包，于是 quant.market_style_state / quant.risk_metrics 两处"同名表
  分叉 + EAV 错结构"长期逃过门禁 —— 前者异步模型声明了 4 个不存在的列，后者异步模型
  至今是 metric_name/metric_value 的错结构（同步版早已修正，异步版没人发现）。
  现由 test_repository_inline_models_match_database + test_no_table_declared_by_two_models
  + test_no_extend_existing_flag 三条共同覆盖。
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

# extend_existing 基线（2026-09-14，w-2129d492）：已收敛 6 处，仅剩这 1 处**活路由**上的
# 遗留，属"需要产品决策"而非纯技术债，故显式登记而不是让门禁变红或被无视。
#
#   sentiment_async_repository.py：模型指向 quant.sentiment_data —— 该表在库中**从未存在**。
#     它是**活路由**（/api/sentiment/market、/api/sentiment/stock/{symbol}），实测
#     恒返回 {"success":true,"data":{}} / {"success":true,"data":null}（假成功，非报错）。
#     库里只有市场级的 quant.market_sentiment_daily（无 symbol 列），**撑不起个股情绪**语义；
#     要真正修好需先定：个股情绪的数据源是什么？是否下线该端点？属产品决策。
#     本基线只挡"新增同类写法"，不代表这处已修 —— 详见工作日志遗留清单。
_EXTEND_EXISTING_BASELINE = frozenset({
    'adapters/outbound/repositories/sentiment_async_repository.py',
})

# 「模型指向不存在的表」基线（2026-09-14，w-2129d492）。
#
# 原先这个方向**只打印不失败** —— "测试库未建表 N 张（跳过）"正是这 3 个长期逃逸的原因：
# 模型映射一张从未存在的表，查询抛 UndefinedTable 被基类 except 吞掉，
# 接口返回 success:true + 空数据（假成功），而门禁一声不吭。
# 现在改为硬失败，仅这 3 个显式豁免；**新增任何悬空模型都会立刻红**。
#
#   public.audit_log      ← AuditLog      策略线（v13/v14）决策审计的唯一写入目标，
#                                        但没有任何迁移创建过它 → log_decision 必然上抛，
#                                        被 _log_to_db 降级成 warning → 审计轨迹从未落库。
#   quant.async_factors   ← AsyncFactor   FactorAnalysisAsyncService 捕获后返回 {}（假成功）。
#   quant.sentiment_data  ← SentimentData 活路由 /api/sentiment/market 与
#                                        /api/sentiment/stock/{symbol} 恒返回假成功。
#
# 三者都要先定产品口径（数据源/是否下线），不在本次机械收敛范围内。
_KNOWN_DANGLING_TABLES = frozenset({
    'public.audit_log',
    'quant.async_factors',
    'quant.sentiment_data',
})

# 「仅测试库缺、生产在位」的表（2026-09-14 交叉核对 quant_investment vs quant_test）：
#   quant.evolution_strategy_runs —— 生产存在，测试库镜像没建 → 是本文件顶部已说明的
#   "测试库是部分镜像"问题，不是模型-库漂移。豁免但打印。
_ENV_ONLY_ABSENT_TABLES = frozenset({
    'quant.evolution_strategy_runs',
})

# ⚠️ 本门禁的已知盲区（诚实登记）：它以**测试库**为准，因此当一张表
# "测试库有、生产没有"时它看不见 —— 实测 quant.async_factors 正是这种：
#   PROD: 不存在      TEST: 存在
# 即模型在测试里能用、在生产必炸，而本门禁会放行。该形态只能靠以生产为口径的
# 只读探针（tools/oneoff/orm_drift_probe.py）发现。两者的 DSN 口径不同，互为补充，
# 不能互相替代。


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
    env_absent = [t for t in absent if t in _ENV_ONLY_ABSENT_TABLES]
    if env_absent:
        print('仅测试库缺表（生产在位，非漂移）：%s' % ', '.join(env_absent))
    unexpected_absent = [
        t for t in absent
        if t not in _KNOWN_DANGLING_TABLES and t not in _ENV_ONLY_ABSENT_TABLES
    ]
    assert not unexpected_absent, (
        '模型映射了数据库中不存在的表（查询抛 UndefinedTable 会被静默吞成"假成功"）:'
        + chr(10) + '  - ' + (chr(10) + '  - ').join(unexpected_absent)
        + chr(10) + '修好模型或补迁移；确属已知悬空请显式登记进 _KNOWN_DANGLING_TABLES。'
    )


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

# ===========================================================================
# 盲区补齐（2026-09-14，w-2129d492）：仓储层内联模型 + 同名表分叉
#
# 背景：本仓出现过三次**同一根因**的线上静默故障 —— 同一张表被声明两遍，且带
# extend_existing=True，第二次声明会把列**追加**到已存在的 Table 对象上，污染第一个
# 模型的 __table__，查询遍历 table.columns 时撞上未被映射的列 → 被 except 吞掉 → 接口恒空：
#   · ffc221de  /api/ml/models 恒返回空且日志刷 AttributeError
#   · f00fd8fe  /api/positions、/api/data-quality/report 恒返回空列表
#   · risk_repository 的 EAV 错结构（metric_name/metric_value）→ 风险指标查询恒空
# 此前门禁只比对 models 包，以上三处全在门外。以下三条即是那道门。
# ===========================================================================

REPO_PACKAGE = 'adapters.outbound.repositories'


def _import_repository_modules():
    """导入仓储层全部模块（否则 _class_registry 里没有内联模型）。

    返回导入失败的模块列表 —— 不静默吞掉：少 import 一个模块就可能少覆盖一张表。
    """
    import importlib
    import pkgutil

    failures = []
    pkg = importlib.import_module(REPO_PACKAGE)
    for mod in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + '.'):
        try:
            importlib.import_module(mod.name)
        except Exception as e:  # noqa: BLE001
            failures.append('%s: %s' % (mod.name, e))
    return failures


def _load_all_models():
    """全部 mapped class → {(schema, table): {(module, class): set(列名)}}。

    用 Base.registry 而不是遍历模块属性：这样同一个类无论被 import 多少次都只算一条，
    不会把"重复 import"误报成"重复定义"。
    """
    from infrastructure.persistence.orm.base import Base

    out = {}
    for cls in list(Base.registry._class_registry.values()):
        if not isinstance(cls, type) or not hasattr(cls, '__mapper__'):
            continue
        try:
            mapper = class_mapper(cls)
        except Exception:  # noqa: BLE001 - 未完成映射的类跳过
            continue
        table = mapper.persist_selectable
        key = (table.schema or 'public', table.name)
        out.setdefault(key, {})[(cls.__module__, cls.__name__)] = {
            c.name for c in mapper.columns
        }
    return out


def test_no_table_declared_by_two_models():
    """同一张表不得被两个模型类声明（同名表分叉 = 三次静默故障的共同根因）。"""
    failures = _import_repository_modules()
    models = _load_all_models()
    assert len(models) >= 40, (
        '只发现 %d 张被模型声明的表，疑似仓储模块没导入成功（否则覆盖形同虚设）。'
        '导入失败：%s' % (len(models), failures or '无')
    )
    dupes = {k: v for k, v in models.items() if len(v) > 1}
    if dupes:
        lines = []
        for (schema, table), defs in sorted(dupes.items()):
            lines.append('  %s.%s（%d 个定义）' % (schema, table, len(defs)))
            for (mod, cn) in sorted(defs):
                lines.append('      - %s.%s' % (mod, cn))
            colsets = [frozenset(c) for c in defs.values()]
            if len(set(colsets)) > 1:
                lines.append('      ⚠️ 列集合不一致 —— 这正是会静默污染 __table__ 的形态')
        pytest.fail(
            '同名表被重复声明（必须收敛为单一事实源：异步仓储从权威仓储 import 模型）:'
            + chr(10) + chr(10).join(lines)
        )


def test_no_extend_existing_flag():
    """全仓不得再出现 extend_existing=True。

    它是同名表分叉的**开关**：没有它，SQLAlchemy 会在第二个定义处直接抛
    "Table X is already defined"，错误当场暴露；有了它，错误被静默吞掉，
    变成"接口恒返回空"。禁止它 = 让这类 bug 在启动时就炸，而不是在用户侧静默。
    """
    offenders = []
    for path in sorted((REPO_ROOT / 'adapters').rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        if rel in _EXTEND_EXISTING_BASELINE:
            continue
        for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if 'extend_existing' in line and not line.lstrip().startswith('#'):
                offenders.append('%s:%d' % (rel, lineno))
    assert not offenders, (
        '检测到 extend_existing（同名表静默分叉的开关），请改为 import 单一模型定义:'
        + chr(10) + '  - ' + (chr(10) + '  - ').join(offenders)
    )


def test_repository_inline_models_match_database(engine, migrations_applied):
    """仓储层内联模型的列也必须真实存在于数据库（models 包之外的第二类模型）。"""
    from sqlalchemy import inspect

    failures = _import_repository_modules()
    models = _load_all_models()
    insp = inspect(engine)
    missing, absent, absent_detail, inline_seen, env_only = [], [], [], 0, set()

    for (schema, table), defs in sorted(models.items()):
        repo_defs = {k: v for k, v in defs.items() if k[0].startswith(REPO_PACKAGE)}
        if not repo_defs:
            continue
        inline_seen += 1
        if not insp.has_table(table, schema=schema):
            absent.append('%s.%s' % (schema, table))
            absent_detail.append('%s.%s（%s）' % (
                schema, table, ', '.join(cn for _, cn in sorted(repo_defs))))
            continue
        db_cols = {c['name'] for c in insp.get_columns(table, schema=schema)}
        for (mod, cn), cols in sorted(repo_defs.items()):
            for col in sorted(cols - db_cols):
                key = '%s.%s.%s' % (schema, table, col)
                # 与 models 包门禁同一豁免口径：测试库是部分镜像，这些列生产在位
                if key in _ENV_ONLY_MISSING:
                    env_only.add(key)
                else:
                    missing.append('%s  ← %s.%s' % (key, mod, cn))

    if env_only:
        print('测试库镜像不全（DB 侧已核对生产在位，非漂移）：%s' % ', '.join(sorted(env_only)))
    assert inline_seen >= 20, (
        '只覆盖到 %d 个仓储内联模型，疑似导入不全。导入失败：%s' % (inline_seen, failures or '无')
    )
    assert not missing, (
        '仓储内联模型声明了数据库不存在的列（查询必炸/被吞成空）:' + chr(10) + '  - '
        + (chr(10) + '  - ').join(missing)
        + chr(10) + chr(10) + '已比对 %d 个内联模型；测试库未建表 %d 张：%s'
        % (inline_seen, len(absent_detail), ', '.join(absent_detail) if absent_detail else '无')
    )
    env_absent = [t for t in absent if t in _ENV_ONLY_ABSENT_TABLES]
    if env_absent:
        print('仅测试库缺表（生产在位，非漂移）：%s' % ', '.join(env_absent))
    unexpected_absent = [
        t for t in absent
        if t not in _KNOWN_DANGLING_TABLES and t not in _ENV_ONLY_ABSENT_TABLES
    ]
    assert not unexpected_absent, (
        '仓储内联模型映射了数据库中不存在的表（查询抛 UndefinedTable 被吞成"假成功"）:'
        + chr(10) + '  - ' + (chr(10) + '  - ').join(unexpected_absent)
        + chr(10) + '修好模型或补迁移；确属已知悬空请显式登记进 _KNOWN_DANGLING_TABLES。'
    )
