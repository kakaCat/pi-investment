"""数据契约表 quant.data_contracts（步3 契约驱动监控，2026-09-11，w-f4aa1f6a）

背景（实测）：
- 系统已多次因**数据静默过期/错位**出事：K 线冻结期间 m4 熔断读到冻结回撤（差点误触发）、
  CSI300 冻结在 2026-08-27 九天后仍产出"看起来正常"的归因超额、quant.trading_calendar
  今天被查出**完全空表**却仍有代码在读它。
- 当前数据质量检查是"一个数据集一个脚本"（如 scripts/benchmark-freshness-check.sh 只查
  沪深300 一条），新增一个数据源就要新增一个脚本，不可扩展、覆盖不全。

本迁移：把"这个数据集长什么样才算健康"从散落的脚本里抽出来，变成**库里的一张声明式契约表**，
由统一校验器 tools/check_data_contracts.py 求值；违约写入既有台账 public.error_events
（source='v2'，fingerprint 以 'data-contract:' 前缀），自动进入采集→处置闭环。

契约族（每列一个检查族，jsonb 配置，可空表示不检查）：
  freshness    {"column","mode":"market_latest|expected_trading_day","max_lag_days",
                "max_lag_weekdays","holiday_slack_weekdays","filter":{...},"severity"}
               mode=market_latest：最新日期 >= 市场最新交易日
                                   （= quant.daily_klines 中行数达完整性的最大 trade_date）
               mode=expected_trading_day：最新日期 >= 期望交易日（墙钟/交易日历口径，抓"整体冻结"）
  value_ranges [{"column","op","value","severity","note"}]
  uniqueness   [{"columns":[...],"severity"}]
  nullability  [{"column","severity","max_null_ratio"}]
  rowcount     {"min","max","severity"}   ← 空表必须报警（trading_calendar 的洞）
  severity     契约缺省级别（high 违约会让校验器 exit 1）

幂等：DDL 用 IF NOT EXISTS；种子用 ON CONFLICT (dataset) DO UPDATE，可重复执行。

用法：
  ./venv/bin/python infrastructure/persistence/migrations/20260911_data_contracts.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _engine():
    """复用项目 engine 的 DSN 解析（.env → QUANT_DATABASE_URL → libpq 默认）。"""
    from sqlalchemy import create_engine

    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / '.env')
    except Exception:  # noqa: BLE001 —— .env 缺失不致命，后面还有 PG* 兜底
        pass

    dsn = os.environ.get('QUANT_DATABASE_URL') or os.environ.get('DATABASE_URL') \
        or os.environ.get('POSTGRES_DSN')
    if not dsn:
        try:
            from infrastructure.persistence.database.engine import _resolve_db_dsn

            dsn = _resolve_db_dsn()
        except Exception:  # noqa: BLE001 —— 兼容层无配置属预期
            dsn = None
    if not dsn:
        dsn = 'postgresql+psycopg2:///quant_investment'  # libpq 默认（PGDATABASE/PGUSER）
    return create_engine(dsn)


DDL = """
CREATE TABLE IF NOT EXISTS quant.data_contracts (
    id            serial PRIMARY KEY,
    dataset       text        NOT NULL UNIQUE,
    table_schema  text        NOT NULL DEFAULT 'quant',
    table_name    text        NOT NULL,
    owner         text,
    freshness     jsonb,
    value_ranges  jsonb,
    uniqueness    jsonb,
    nullability   jsonb,
    rowcount      jsonb,
    severity      text        NOT NULL DEFAULT 'medium',
    enabled       boolean     NOT NULL DEFAULT true,
    notes         text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE quant.data_contracts IS
    '声明式数据契约（步3 契约驱动监控，2026-09-11 w-f4aa1f6a）：一个数据集一行健康定义，由 tools/check_data_contracts.py 求值，违约写 public.error_events（fingerprint=data-contract:*）';
COMMENT ON COLUMN quant.data_contracts.dataset IS
    '逻辑数据集名，唯一键。形如 quant.daily_klines；同一物理表的不同切片用 "表:过滤值"（如 quant.index_daily:000300.SH）';
COMMENT ON COLUMN quant.data_contracts.freshness IS
    '新鲜度契约 {"column","mode":"market_latest|expected_trading_day","max_lag_days","filter",...}；market_latest 以 quant.daily_klines 的完整交易日为准';
COMMENT ON COLUMN quant.data_contracts.rowcount IS
    '行数契约 {"min":N,"max":N}；min>=1 即"空表必须报警"';
CREATE INDEX IF NOT EXISTS idx_data_contracts_enabled ON quant.data_contracts (enabled);
"""

# ---------------------------------------------------------------------------
# 种子契约：只覆盖**确实在被系统读取**的表（读路径已 grep 核实）
# ---------------------------------------------------------------------------
SEEDS = [
    # ── 1. 市场基准真源：自己的新鲜度要锚定墙钟/交易日历，否则"整体冻结"会被自洽地放过 ──
    dict(
        dataset='quant.daily_klines',
        table_name='daily_klines',
        owner='w-f4aa1f6a',
        freshness={
            'column': 'trade_date',
            'mode': 'expected_trading_day',
            'max_lag_weekdays': 1,
            'holiday_slack_weekdays': 3,
            'severity': 'high',
        },
        value_ranges=[{'column': 'close', 'op': '>', 'value': 0, 'severity': 'high',
                       'note': '收盘价必须为正（0/负=坏行）'}],
        rowcount={'min': 1000000, 'severity': 'medium'},
        severity='high',
        notes='市场真源（kline 读路径 100+ 文件）。它冻结=全系统失明；故新鲜度锚定墙钟而非自身 max。'
              '2026-09 曾出现 18 行的"未完整交易日"，校验器用 market_min_rows 门槛剔除。',
    ),
    # ── 2. 指数日线（2026-09-11 新建的指数专用表）──
    dict(
        dataset='quant.index_daily',
        table_name='index_daily',
        owner='w-f4aa1f6a',
        freshness={'column': 'trade_date', 'mode': 'market_latest', 'max_lag_days': 0,
                   'severity': 'medium'},
        rowcount={'min': 100, 'severity': 'medium'},
        severity='medium',
        notes='指数价格专用表（symbol 带市场后缀，如 000300.SH）。全表口径给 medium：'
              '部分指数非每日更新；基准切片（下一行）单独 high。',
    ),
    # ── 3. 收敛 scripts/benchmark-freshness-check.sh：000300.SH 新鲜度 + 合理区间 ──
    dict(
        dataset='quant.index_daily:000300.SH',
        table_name='index_daily',
        owner='w-f4aa1f6a',
        freshness={'column': 'trade_date', 'mode': 'market_latest', 'max_lag_days': 0,
                   'filter': {'symbol': '000300.SH'}, 'severity': 'high'},
        value_ranges=[{'column': 'close', 'op': '>=', 'value': 1000, 'severity': 'high',
                       'note': '合理指数下界；元级股票数据必然低于此（抓"指数/个股同码错配"）'},
                      {'column': 'close', 'op': '<=', 'value': 20000, 'severity': 'high',
                       'note': '合理指数上界'}],
        rowcount={'min': 200, 'filter': {'symbol': '000300.SH'}, 'severity': 'high'},
        severity='high',
        notes='等价于 scripts/benchmark-freshness-check.sh 的两项检查（新鲜度 + 收盘价量级）。'
              '该脚本与 launchd 任务保留不动，是否下线由人工决定。',
    ),
    # ── 4. 组合权益快照（回撤/归因数据源）──
    dict(
        dataset='quant.simulation_equity_snapshot',
        table_name='simulation_equity_snapshot',
        owner='w-f4aa1f6a',
        freshness={'column': 'snapshot_date', 'mode': 'market_latest', 'max_lag_days': 0,
                   'severity': 'high'},
        value_ranges=[{'column': 'total_value', 'op': '>', 'value': 0, 'severity': 'high',
                       'note': '总资产必须为正'}],
        rowcount={'min': 1, 'severity': 'medium'},
        severity='high',
        notes='risk_metrics / performance_tracker / daily_snapshot_service 的数据源。'
              '冻结时会静默复用旧权益曲线 → 回撤失真（2026-09 出过同类事故）。',
    ),
    # ── 5. 交易日历：今天刚出过"完全空表仍有代码在读"的洞 ──
    dict(
        dataset='quant.trading_calendar',
        table_name='trading_calendar',
        owner='w-f4aa1f6a',
        freshness={'column': 'trade_date', 'mode': 'market_latest', 'max_lag_days': 0,
                   'severity': 'high'},
        rowcount={'min': 1, 'severity': 'high'},
        severity='high',
        notes='行数下限 > 0：空表必须报警（2026-09-11 实测 0 行，而 trade_guard_service/'
              'data_pipeline_service 等仍按日历判交易日）。最新 trade_date 也不得早于市场最新交易日。',
    ),
    # ── 6. 模拟账户主表 ──
    dict(
        dataset='quant.simulation_account',
        table_name='simulation_account',
        owner='w-f4aa1f6a',
        value_ranges=[{'column': 'total_value', 'op': '>', 'value': 0, 'severity': 'high',
                       'note': '账户总资产必须为正'}],
        uniqueness=[{'columns': ['account_name'], 'severity': 'high'}],
        rowcount={'min': 1, 'severity': 'medium'},
        severity='medium',
        notes='交易/账户读路径主表（account_info、trade_guard、performance_tracker）。',
    ),
    # ── 7. 股票基础表 ──
    dict(
        dataset='quant.stocks',
        table_name='stocks',
        owner='w-f4aa1f6a',
        nullability=[{'column': 'name', 'severity': 'medium', 'max_null_ratio': 0.0}],
        uniqueness=[{'columns': ['symbol'], 'severity': 'high'}],
        rowcount={'min': 1000, 'severity': 'medium'},
        severity='medium',
        notes='全市场基础表（stock_repository、symbol_classifier 歧义码判定等都读它）。',
    ),
    # ── 8. 个股资金流（capital_scorer / fund_flow 读路径）──
    dict(
        dataset='quant.stock_fund_flow',
        table_name='stock_fund_flow',
        owner='w-f4aa1f6a',
        freshness={'column': 'trade_date', 'mode': 'market_latest', 'max_lag_days': 3,
                   'severity': 'medium'},
        rowcount={'min': 1000, 'severity': 'medium'},
        severity='medium',
        notes='资金流评分数据源（capital_scorer / sentiment_service）。上游 akshare 偶发停更，'
              '容忍 3 个自然日滞后。',
    ),
    # ── 9. 市场情绪日频（market_perception / retail_panic_index 读路径）──
    dict(
        dataset='quant.market_sentiment_daily',
        table_name='market_sentiment_daily',
        owner='w-f4aa1f6a',
        freshness={'column': 'trade_date', 'mode': 'market_latest', 'max_lag_days': 1,
                   'severity': 'medium'},
        rowcount={'min': 1, 'severity': 'medium'},
        severity='medium',
        notes='情绪/恐慌指数序列（market_perception_service、retail_panic_index_service）。',
    ),
    # ── 10. 指数成分股（index_constituents 工具读路径）──
    dict(
        dataset='quant.index_constituents',
        table_name='index_constituents',
        owner='w-f4aa1f6a',
        uniqueness=[{'columns': ['index_code', 'constituent_symbol'], 'severity': 'medium'}],
        rowcount={'min': 300, 'severity': 'medium'},
        severity='medium',
        notes='指数成分（沪深300/科创50/创业板指等）。成分缺失会静默缩小选股/归因基准池。',
    ),
    # ── 11. 模拟持仓（position_list / performance_tracker 读路径）──
    dict(
        dataset='quant.simulation_positions',
        table_name='simulation_positions',
        owner='w-f4aa1f6a',
        value_ranges=[{'column': 'avg_cost', 'op': '>', 'value': 0, 'severity': 'medium',
                       'note': '成本价必须为正'}],
        uniqueness=[{'columns': ['account_name', 'symbol'], 'severity': 'medium'}],
        severity='medium',
        notes='持仓明细表；同账户同标的重复行会让持仓/盈亏被重复计算。',
    ),
]

UPSERT = """
INSERT INTO quant.data_contracts
    (dataset, table_schema, table_name, owner, freshness, value_ranges, uniqueness,
     nullability, rowcount, severity, enabled, notes, created_at, updated_at)
VALUES
    (:dataset, :table_schema, :table_name, :owner,
     CAST(:freshness AS jsonb), CAST(:value_ranges AS jsonb), CAST(:uniqueness AS jsonb),
     CAST(:nullability AS jsonb), CAST(:rowcount AS jsonb), :severity, :enabled, :notes,
     now(), now())
ON CONFLICT (dataset) DO UPDATE SET
    table_schema = EXCLUDED.table_schema,
    table_name   = EXCLUDED.table_name,
    owner        = EXCLUDED.owner,
    freshness    = EXCLUDED.freshness,
    value_ranges = EXCLUDED.value_ranges,
    uniqueness   = EXCLUDED.uniqueness,
    nullability  = EXCLUDED.nullability,
    rowcount     = EXCLUDED.rowcount,
    severity     = EXCLUDED.severity,
    enabled      = EXCLUDED.enabled,
    notes        = EXCLUDED.notes,
    updated_at   = now()
RETURNING dataset, (xmax = 0) AS inserted
"""


def _j(v):
    return None if v is None else json.dumps(v, ensure_ascii=False)


def run_migration() -> int:
    from sqlalchemy import text

    engine = _engine()
    inserted = updated = 0
    with engine.begin() as conn:
        # 用 exec_driver_sql 而非 text()：DDL 的 COMMENT 文本里含 ":"/"%" 字面量，
        # 走 SQLAlchemy text() 会被当成 bind 参数/参数转义（实测报 "A value is required
        # for bind parameter 'N'"）。原生执行可原样下发给 psycopg2。
        conn.exec_driver_sql(DDL)
        print('[迁移] quant.data_contracts 已就绪（CREATE TABLE IF NOT EXISTS）')
        for seed in SEEDS:
            row = conn.execute(text(UPSERT), {
                'dataset': seed['dataset'],
                'table_schema': seed.get('table_schema', 'quant'),
                'table_name': seed['table_name'],
                'owner': seed.get('owner'),
                'freshness': _j(seed.get('freshness')),
                'value_ranges': _j(seed.get('value_ranges')),
                'uniqueness': _j(seed.get('uniqueness')),
                'nullability': _j(seed.get('nullability')),
                'rowcount': _j(seed.get('rowcount')),
                'severity': seed.get('severity', 'medium'),
                'enabled': seed.get('enabled', True),
                'notes': seed.get('notes'),
            }).fetchone()
            if row[1]:
                inserted += 1
                print(f"[迁移] + 新增契约 {row[0]}")
            else:
                updated += 1
                print(f"[迁移] ~ 更新契约 {row[0]}")
        total = conn.execute(text('SELECT count(*) FROM quant.data_contracts')).scalar()
    print(f'[迁移] 完成：新增 {inserted}，更新 {updated}，表内共 {total} 条契约')
    return 0


if __name__ == '__main__':
    raise SystemExit(run_migration())
