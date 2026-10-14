"""非交易日净值行清理迁移的验收测试（REQ-261006190953-fc43 · 卡 F）

被测对象（**只在测试库 `quant_test` 上跑**）：
  · `infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py`
  · `tools/verify_equity_snapshot_consistency.py`

对应卡 F 验收 ①~⑧（② 已按 2026-10-06 的口径裁定改写）：
  ① dry-run 前后表行数与校验和一致（零副作用）
  ② 白名单语义：**窗口内、不在交易日清单里**的行要删；**窗口之外**的行一律不动
  ③ 待删行数与预期不符时脚本**非零退出**并打印差异
  ④ 备份行数 < 待删行数时中止
  ⑤ `--apply` 后判据 SQL（非交易日净值行数）为 0
  ⑥ 重算后一致性校验工具逐账户 `diff=0` 且退出码 0
  ⑦ 幂等：`--apply` 连跑两次，第二次删除 0 行且重算结果不变
  ⑧ `--rollback` 恢复行数并**响亮打印**「正在恢复 N 行非交易日净值行」

## 删除口径（2026-10-06 裁定：白名单语义）

本仓 `quant.trading_calendar` 是**白名单**（生产 23373 行 `is_trading_day` 全 true、一条 false 都没有），
所以**非交易日 = 快照日期落在日历覆盖范围内（`min(trade_date) ~ max(trade_date)`）、且不在交易日清单里**。
旧的 `is_trading_day is false` 谓词在这张日历上匹配 **0 行**（故 ② 的原断言"日历缺行的日期不动"
在新口径下**恰好相反**）。本测试因此自己插**交易日行**（`is_trading_day = true, exchange = 'ALL'`）
造出覆盖窗口，让"窗口内、清单外"的日期当脏行；**防误删改由「覆盖范围」承担**——
窗口之外的日期一律不动（这才是现在承担"宁可漏删不可误删"的判据）。

## 数据设计（为什么是 5 账户 × 7 天）

生产实测待删 = 35 行 = 5 账户 × 7 个非交易日，故哨兵**照同一形状造**：
覆盖窗口 = `2030-01-02 ~ 2030-01-31`（由两行交易日定界，当日无需有快照）；
窗口内、**在交易日清单里**的 4 天（`01-03 / 01-04 / 01-09 / 01-10`）保留，也是重算的基准；
窗口内、**不在清单里**的 7 天（`01-05 / 01-06 / 01-12 / 01-13 / 01-19 / 01-20 / 01-26`）
即"缺行 = 非交易日" → **待删**；窗口之外再放 1 天（`2031-06-06`）→ **一律不动**。
合计 12 行/账户 × 5 = 60 行，其中待删 **35** 行 —— 正好命中脚本缺省 `--expect 35`。

账户 1 在 `2030-01-09` 多一笔 **deposit**（非成立资金），用来锁"重算复用
`external_flow_on`、把注资从日收益里扣掉"：同一天所有账户的 total_value 相同，
唯独账户 1 的 `daily_return` 不同（扣掉 5000 注资后由 +0.49% 翻成 -0.44%）。

## 自清

模块级 fixture 在每个用例前后清掉**哨兵账户/快照/流水/日历行 + 备份表里哨兵账户的行**；
`quant.trading_calendar` 跑完必须回到**空表**（本仓测试库原本就是空的，别的用例依赖这一点）。
不动测试库里任何既有数据（迁移一律带 `--accounts` 哨兵过滤，重放也只覆盖哨兵账户）。
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from datetime import date, datetime, time as dtime
from pathlib import Path

import pytest
from sqlalchemy import text

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from infrastructure.persistence.database.engine import _resolve_db_dsn
from infrastructure.persistence.orm.models import (
    SimulationAccount,
    SimulationCashFlow,
    SimulationEquitySnapshot,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = REPO_ROOT / 'infrastructure/persistence/migrations' / \
    '20261006_purge_nontrading_equity_snapshots.py'
VERIFIER = REPO_ROOT / 'tools/verify_equity_snapshot_consistency.py'

ACCOUNTS = [f'__fc43_purge_{i}__' for i in range(1, 6)]
INITIAL = 100000.0

# 日期取 **2030 年**（而不是生产实测的 2026-08-08/09-05/…）的理由：
# 测试库是**共享**的，别的用例在那些真实脏日期上也有行；若哨兵日历把 2026-08-08 标成
# 非交易日，那些行会被判据 SQL 一起算进去，⑤"判据为 0"就永远不成立。
# 挪到无人使用的 2030 年后，判据 SQL 可以在**全库**口径上被断言为 0（与上线后的 psql 判据同形）。
# 形状与生产一致：5 账户 × 7 个"窗口内、清单外"日（周六/周日/工作日的休市日各占）
# + 4 个交易日 + 1 个窗口外日。
#: 覆盖窗口下沿（日历行 `is_trading_day=true`；该日无需有快照，只负责把 `min(trade_date)` 定住）
WINDOW_FIRST = date(2030, 1, 2)
#: 覆盖窗口上沿（同上，定住 `max(trade_date)`）
WINDOW_LAST = date(2030, 1, 31)
#: 交易日清单（`is_trading_day=true`，**窗口内** → 保留；也是重算时的"上一交易日"基准）
TRADING_DAYS = [date(2030, 1, 3), date(2030, 1, 4), date(2030, 1, 9), date(2030, 1, 10)]
#: **窗口内、不在交易日清单里**（白名单语义下即非交易日 → 待删）
DIRTY_DAYS = [date(2030, 1, 5), date(2030, 1, 6), date(2030, 1, 12),
              date(2030, 1, 13), date(2030, 1, 19), date(2030, 1, 20), date(2030, 1, 26)]
#: **窗口之外**（日历覆盖范围之外）：一律不动 —— 防误删现在由覆盖范围承担
OUTSIDE_DAY = date(2031, 6, 6)

TOTALS = {
    date(2030, 1, 3): 101000.0,
    date(2030, 1, 4): 101500.0,
    date(2030, 1, 5): 101700.0,
    date(2030, 1, 6): 101900.0,
    date(2030, 1, 9): 102000.0,
    date(2030, 1, 10): 101800.0,
    date(2030, 1, 12): 102100.0,
    date(2030, 1, 13): 102300.0,
    date(2030, 1, 19): 100400.0,
    date(2030, 1, 20): 100600.0,
    date(2030, 1, 26): 100800.0,
    OUTSIDE_DAY: 100500.0,           # 峰谷回落：让 drawdown 有真实变化，且证明窗口外行不动
}
SNAPSHOT_DAYS = sorted(TOTALS)

#: 账户 1 在 01-09 的追加入金（非成立资金）→ 必须从当日日收益里扣掉
EXTRA_DEPOSIT_DAY = date(2030, 1, 9)
EXTRA_DEPOSIT_AMOUNT = 5000.0
DEPOSIT_ACCOUNT = ACCOUNTS[0]

EXPECT_DELETED = len(DIRTY_DAYS) * len(ACCOUNTS)            # 35
EXPECT_REMAINING = len(SNAPSHOT_DAYS) * len(ACCOUNTS)        # 60
EXPECT_KEPT = EXPECT_REMAINING - EXPECT_DELETED              # 25 = 5 天（4 交易日 + 1 窗口外）× 5

#: 要插进/清出 `quant.trading_calendar` 的日期（只有交易日行；本测试不插 `false` 行）
CAL_DAYS = sorted({WINDOW_FIRST, WINDOW_LAST} | set(TRADING_DAYS))


SNAPSHOT_CHECKSUM = """
select count(*), coalesce(md5(string_agg(
        account_name || '|' || snapshot_date::text || '|' ||
        coalesce(total_value::text, '') || '|' || coalesce(daily_return::text, '') || '|' ||
        coalesce(cumulative_return::text, '') || '|' || coalesce(drawdown::text, ''),
        ',' order by account_name, snapshot_date)), 'empty')
from quant.simulation_equity_snapshot
"""
ACCOUNT_CHECKSUM = """
select count(*), coalesce(md5(string_agg(
        account_name || '|' || coalesce(max_drawdown::text, '') || '|' ||
        coalesce(peak_value::text, ''), ',' order by account_name)), 'empty')
from quant.simulation_account
"""
#: 判据 SQL（**白名单语义**，与迁移脚本 `_non_trading()` 同形但独立写出）：
#: 窗口内（`min ~ max(trade_date)`）、且不在交易日清单里。`{scope}` 供账户范围过滤。
JUDGE_SQL = """
select count(*)
from quant.simulation_equity_snapshot s
where {scope} s.snapshot_date between
      (select min(trade_date) from quant.trading_calendar where exchange = 'ALL')
      and (select max(trade_date) from quant.trading_calendar where exchange = 'ALL')
  and not exists (
      select 1 from quant.trading_calendar c
       where c.exchange = 'ALL'
         and c.trade_date = s.snapshot_date
         and c.is_trading_day is true
  )
"""


# --------------------------------------------------------------------------- #
# 基础设施
# --------------------------------------------------------------------------- #

def _test_dsn() -> str:
    """测试库 DSN（**断言 `_test` 结尾**：本文件绝不出手生产库）。"""
    dsn = _resolve_db_dsn() or os.environ.get('QUANT_DATABASE_URL') or ''
    assert dsn, '拿不到测试库 DSN'
    assert dsn.rstrip('/').endswith('_test'), f'拒绝在非测试库上跑：{dsn}'
    return dsn


def _run_script(script: Path, *extra: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env['PYTHONPATH'] = str(REPO_ROOT)
    env['QUANT_DATABASE_URL'] = _test_dsn()
    return subprocess.run(
        [sys.executable, str(script), '--dsn', _test_dsn(), *extra],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=300,
    )


@pytest.fixture(scope='module')
def repo():
    r = SimulationORMRepository()
    yield r
    try:
        r.session.close()
    except Exception:  # noqa: BLE001
        pass


def _clean(repo) -> None:
    """清掉全部哨兵痕迹（快照/账户/流水/日历/备份表）。"""
    s = repo.session
    s.rollback()          # 前一个用例若把会话留在 aborted 状态，先复位
    names = tuple(ACCOUNTS)
    s.query(SimulationEquitySnapshot).filter(
        SimulationEquitySnapshot.account_name.in_(names)).delete(synchronize_session=False)
    s.query(SimulationCashFlow).filter(
        SimulationCashFlow.account_name.in_(names)).delete(synchronize_session=False)
    s.query(SimulationAccount).filter(
        SimulationAccount.account_name.in_(names)).delete(synchronize_session=False)
    s.execute(text("delete from quant.trading_calendar where exchange = 'ALL' "
                   "and trade_date = any(:days)"), {'days': CAL_DAYS})
    if s.execute(text('select to_regclass(:t)'),
                 {'t': 'quant.bak_equity_snapshot_nontrading_w_0a409569'}).scalar():
        s.execute(text('delete from quant.bak_equity_snapshot_nontrading_w_0a409569 '
                       'where account_name = any(:names)'), {'names': list(names)})
        # 备份表是迁移产物：清空后（说明没留下别人的备份）把空表一并收掉 → 测试库回到原样
        if s.execute(text('select count(*) from '
                          'quant.bak_equity_snapshot_nontrading_w_0a409569')).scalar() == 0:
            s.execute(text('drop table quant.bak_equity_snapshot_nontrading_w_0a409569'))
    s.commit()


def _seed(repo) -> None:
    """造哨兵数据（5 账户 × 12 天；派生字段故意填"错值"以示重算确实发生）。"""
    s = repo.session
    for name in ACCOUNTS:
        s.add(SimulationAccount(
            account_name=name, display_name=name, initial_capital=INITIAL,
            cash_available=INITIAL, cash_frozen=0, position_value=0,
            total_value=INITIAL, peak_value=INITIAL, status='active',
        ))
        # 成立资金（首笔 deposit，created_at 早于所有快照日 → 被 external_flow_on 排除）
        s.add(SimulationCashFlow(
            account_name=name, flow_type='deposit', amount=INITIAL,
            balance_after=INITIAL, created_at=datetime(2030, 1, 1, 9, 0),
        ))
        for day in SNAPSHOT_DAYS:
            s.add(SimulationEquitySnapshot(
                account_name=name, snapshot_date=day, cash=0.0, position_value=0.0,
                total_value=TOTALS[day],
                daily_return=0.1234, cumulative_return=0.1234, drawdown=0.1234,
            ))
    # 账户 1 的追加入金（非成立资金）
    s.add(SimulationCashFlow(
        account_name=DEPOSIT_ACCOUNT, flow_type='deposit', amount=EXTRA_DEPOSIT_AMOUNT,
        balance_after=INITIAL + EXTRA_DEPOSIT_AMOUNT,
        created_at=datetime.combine(EXTRA_DEPOSIT_DAY, dtime(9, 30)),
    ))
    # 交易日行：两沿定出覆盖窗口（`min ~ max(trade_date)`），中间 4 天是窗口内的交易日。
    # **不插** `is_trading_day=false` 的行 —— 白名单语义下"缺行"就是非交易日（生产日历一条 false 都没有）。
    for day in CAL_DAYS:
        s.execute(text("insert into quant.trading_calendar (trade_date, exchange, is_trading_day) "
                       "values (:d, 'ALL', true) on conflict do nothing"), {'d': day})
    s.commit()


def _calendar_rows(repo) -> int:
    """测试库 `quant.trading_calendar` 的行数（本仓基线 = 0）。"""
    return repo.session.execute(
        text('select count(*) from quant.trading_calendar')).scalar()


@pytest.fixture()
def sentinel(repo):
    """每个用例：清 → 造 → 跑 → 清。保证用例之间零串扰。"""
    _clean(repo)
    # 前置：覆盖窗口由**全表** `min/max(trade_date)` 决定，故日历必须是空基线
    #（本仓测试库原本就是空的；本文件是它唯一的写入者）。若这里非空，窗口会失真 ——
    # 宁可在这里响亮报错，也不要给下游一个"待删 N ≠ 35"的难懂失败。
    assert _calendar_rows(repo) == 0, '测试库 quant.trading_calendar 基线不是空表（有外部残留）'
    _seed(repo)
    yield repo
    _clean(repo)
    # 自清锁：跑完必须回到空表（本仓别的用例依赖这一点，见模块 docstring）
    assert _calendar_rows(repo) == 0, '测试跑完 quant.trading_calendar 没回到空表'


def _checksums(repo):
    s = repo.session
    return (tuple(s.execute(text(SNAPSHOT_CHECKSUM)).fetchone()),
            tuple(s.execute(text(ACCOUNT_CHECKSUM)).fetchone()))


def _sentinel_rows(repo, account=None):
    q = repo.session.query(SimulationEquitySnapshot).filter(
        SimulationEquitySnapshot.account_name.in_(ACCOUNTS))
    if account:
        q = q.filter(SimulationEquitySnapshot.account_name == account)
    return q.all()


def _row(repo, account, day):
    return (repo.session.query(SimulationEquitySnapshot)
            .filter_by(account_name=account, snapshot_date=day).first())


def _bak_rows(repo):
    """备份表里哨兵账户的行数（表不存在 = 0：dry-run 会把建表 DDL 一起回滚）。"""
    s = repo.session
    if s.execute(text('select to_regclass(:t)'),
                 {'t': 'quant.bak_equity_snapshot_nontrading_w_0a409569'}).scalar() is None:
        return 0
    return s.execute(text(
        'select count(*) from quant.bak_equity_snapshot_nontrading_w_0a409569 '
        'where account_name = any(:names)'), {'names': ACCOUNTS}).scalar()


def _migration_args(*extra):
    return list(extra) + ['--accounts', ','.join(ACCOUNTS)]


def _migration_module():
    """按路径加载迁移模块（复用它的 DDL 常量，不在测试里重写一遍建表语句）。"""
    spec = importlib.util.spec_from_file_location('_fc43_purge_migration', MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# ① dry-run 零副作用
# --------------------------------------------------------------------------- #

def test_dry_run_reports_35_and_changes_nothing(sentinel):
    before = _checksums(sentinel)

    res = _run_script(MIGRATION, *_migration_args())

    assert res.returncode == 0, res.stdout + res.stderr
    assert f'待删 {EXPECT_DELETED} 行' in res.stdout
    assert f'预期 {EXPECT_DELETED} 行' in res.stdout
    assert '已 ROLLBACK' in res.stdout, 'dry-run 必须明确声明已回滚'
    assert _checksums(sentinel) == before, 'dry-run 改了数据（快照表或账户表校验和变了）'
    assert _bak_rows(sentinel) == 0, 'dry-run 不该在备份表里留下行'
    assert len(_sentinel_rows(sentinel)) == EXPECT_REMAINING


# --------------------------------------------------------------------------- #
# ② 白名单语义：窗口内、清单外的要删；窗口外的一律不动
# --------------------------------------------------------------------------- #

def test_apply_deletes_whitelist_missing_and_keeps_out_of_range(sentinel):
    res = _run_script(MIGRATION, *_migration_args('--apply'))

    assert res.returncode == 0, res.stdout + res.stderr
    assert f'实际删除 {EXPECT_DELETED} 行' in res.stdout

    # 前提自检（否则 (b) 的"窗口之外"不成立）：覆盖窗口必须就是哨兵自己插的那一段
    lo, hi = sentinel.session.execute(text(
        "select min(trade_date), max(trade_date) from quant.trading_calendar "
        "where exchange = 'ALL'")).fetchone()
    assert (lo, hi) == (WINDOW_FIRST, WINDOW_LAST), f'覆盖窗口失真：{lo} ~ {hi}'
    assert OUTSIDE_DAY > hi, f'窗口外哨兵 {OUTSIDE_DAY} 竟落在窗口 {lo}~{hi} 之内'

    for name in ACCOUNTS:
        # (a) 窗口内、不在交易日清单里的行 → 白名单语义下即非交易日 → **要删**
        for day in DIRTY_DAYS:
            assert _row(sentinel, name, day) is None, \
                f'窗口内缺日历行的行没被删：{name} {day}'
        # (b) 窗口之外（`max(trade_date)` 之后）→ 一律不动 —— 现在承担"防误删"的就是它
        assert _row(sentinel, name, OUTSIDE_DAY) is not None, \
            f'窗口外的行被误删：{name} {OUTSIDE_DAY}'
        # 窗口内的交易日行也不许动
        for day in TRADING_DAYS:
            assert _row(sentinel, name, day) is not None, f'交易日行被误删：{name} {day}'
    assert len(_sentinel_rows(sentinel)) == EXPECT_KEPT


# --------------------------------------------------------------------------- #
# ③ 待删行数 ≠ 预期 → 非零退出 + 打印差异 + 零写入
# --------------------------------------------------------------------------- #

def test_count_mismatch_exits_nonzero_and_prints_diff(sentinel):
    before = _checksums(sentinel)

    res = _run_script(MIGRATION, *_migration_args('--expect', '999'))

    assert res.returncode != 0, res.stdout
    assert res.returncode == 2, f'期望退出码 2（行数不符），实得 {res.returncode}'
    assert f'待删行数 {EXPECT_DELETED} ≠ 预期 999' in res.stdout
    assert '一行都不写' in res.stdout
    assert _checksums(sentinel) == before, '行数不符时竟然改了数据'
    assert _bak_rows(sentinel) == 0


# --------------------------------------------------------------------------- #
# ④ 备份行数 < 待删行数 → 中止（造真实的部分备份：让备份表对某账户静默吞行）
# --------------------------------------------------------------------------- #

def test_backup_shortfall_aborts_before_delete(sentinel):
    mod = _migration_module()
    s = sentinel.session
    # 先把备份表建出来（dry-run 会回滚 DDL，故此处显式建；用迁移自己的 DDL 常量）
    s.execute(text(mod.DDL))
    s.commit()
    # 触发器：对最后一个哨兵账户的备份行返回 NULL → 该账户 7 行备份不进表
    # （用**持久**函数而不是 pg_temp.*：触发器在另一个进程/会话里被触发）
    s.execute(text("""
        create or replace function quant.fc43_purge_test_skip_backup() returns trigger as $$
        begin
          if new.account_name = '__fc43_purge_5__' then
            return null;
          end if;
          return new;
        end;
        $$ language plpgsql
    """))
    s.execute(text('drop trigger if exists fc43_skip_backup on '
                   'quant.bak_equity_snapshot_nontrading_w_0a409569'))
    s.execute(text('create trigger fc43_skip_backup before insert on '
                   'quant.bak_equity_snapshot_nontrading_w_0a409569 '
                   'for each row execute function quant.fc43_purge_test_skip_backup()'))
    s.commit()
    try:
        res = _run_script(MIGRATION, *_migration_args('--apply'))

        assert res.returncode != 0, res.stdout
        assert res.returncode == 3, f'期望退出码 3（备份不足），实得 {res.returncode}'
        assert f'备份行数 {EXPECT_DELETED - len(DIRTY_DAYS)} < 待删行数 {EXPECT_DELETED}' in res.stdout
        assert '拒绝删除' in res.stdout
        # 中止 = 一行都没删（事务回滚）
        assert len(_sentinel_rows(sentinel)) == EXPECT_REMAINING
        assert _row(sentinel, ACCOUNTS[-1], DIRTY_DAYS[0]) is not None
    finally:
        s.execute(text('drop trigger if exists fc43_skip_backup on '
                       'quant.bak_equity_snapshot_nontrading_w_0a409569'))
        s.execute(text('drop function if exists quant.fc43_purge_test_skip_backup()'))
        s.commit()


# --------------------------------------------------------------------------- #
# ⑤ + ⑥ apply 后判据为 0，且独立复算逐账户 diff=0
# --------------------------------------------------------------------------- #

def test_apply_clears_judgement_and_verifier_reports_zero_diff(sentinel):
    res = _run_script(MIGRATION, *_migration_args('--apply'))
    assert res.returncode == 0, res.stdout + res.stderr
    assert '[verify] 判据 SQL（非交易日净值行数，本账户范围）=0' in res.stdout

    # ⑤ 判据 SQL（白名单语义：覆盖范围内 + 不在交易日清单里 —— 与迁移脚本 `_non_trading()` 同形）
    # 哨兵窗口在 2030-01，测试库其余快照都在 2026 年（范围外）→ 这里可以按**全库**口径断言 0
    assert sentinel.session.execute(
        text(JUDGE_SQL.replace('{scope}', ''))).scalar() == 0
    scoped = sentinel.session.execute(
        text(JUDGE_SQL.replace('{scope}', 's.account_name = any(:names) and')),
        {'names': ACCOUNTS}).scalar()
    assert scoped == 0

    # ⑥ 独立复算：逐账户 diff=0 且退出码 0
    ver = _run_script(VERIFIER, '--accounts', ','.join(ACCOUNTS))
    assert ver.returncode == 0, ver.stdout + ver.stderr
    for name in ACCOUNTS:
        assert f'[verify] {name}: rows=5 diff=0' in ver.stdout, ver.stdout
    assert '逐账户 diff=0' in ver.stdout

    # 注资扣减：同一天所有账户 total_value 相同，唯独账户 1 的日收益不同
    prev = TOTALS[date(2030, 1, 4)]      # 基准 = 上一交易日 01-04（01-05/01-06 非交易日且已被删）
    with_flow = (TOTALS[EXTRA_DEPOSIT_DAY] - EXTRA_DEPOSIT_AMOUNT - prev) / prev
    without_flow = (TOTALS[EXTRA_DEPOSIT_DAY] - prev) / prev
    assert float(_row(sentinel, DEPOSIT_ACCOUNT, EXTRA_DEPOSIT_DAY).daily_return) == \
        pytest.approx(with_flow, abs=5e-5)
    assert float(_row(sentinel, ACCOUNTS[1], EXTRA_DEPOSIT_DAY).daily_return) == \
        pytest.approx(without_flow, abs=5e-5)
    assert abs(with_flow - without_flow) > 0.005, '本用例要的是"扣注资后确实不同"'

    # 首行无基准 → NULL（不得写成 0.0 假平盘）；序列首行 = 最早的交易日 01-03
    first = _row(sentinel, ACCOUNTS[1], min(TRADING_DAYS))
    assert first.daily_return is None


# --------------------------------------------------------------------------- #
# ⑦ 幂等：连跑两次，第二次删 0 行、结果不变
# --------------------------------------------------------------------------- #

def test_apply_twice_is_idempotent(sentinel):
    first = _run_script(MIGRATION, *_migration_args('--apply'))
    assert first.returncode == 0, first.stdout + first.stderr
    after_first = _checksums(sentinel)

    second = _run_script(MIGRATION, *_migration_args('--apply', '--expect', '0'))
    assert second.returncode == 0, second.stdout + second.stderr
    assert '待删 0 行' in second.stdout
    assert '实际删除 0 行' in second.stdout
    assert _checksums(sentinel) == after_first, '第二次跑改了数据（重算结果不稳定）'
    assert len(_sentinel_rows(sentinel)) == EXPECT_KEPT


# --------------------------------------------------------------------------- #
# ⑧ rollback：恢复行数 + 响亮打印
# --------------------------------------------------------------------------- #

def test_rollback_restores_rows_and_prints_loudly(sentinel):
    res = _run_script(MIGRATION, *_migration_args('--apply'))
    assert res.returncode == 0, res.stdout + res.stderr
    assert len(_sentinel_rows(sentinel)) == EXPECT_KEPT

    rb = _run_script(MIGRATION, *_migration_args('--rollback'))
    assert rb.returncode == 0, rb.stdout + rb.stderr
    assert f'正在恢复 {EXPECT_DELETED} 行非交易日净值行' in rb.stdout, rb.stdout
    assert '这是回滚动作，不是正常写入' in rb.stdout
    assert f'实际写回 {EXPECT_DELETED} 行' in rb.stdout

    assert len(_sentinel_rows(sentinel)) == EXPECT_REMAINING
    for name in ACCOUNTS:
        for day in DIRTY_DAYS:
            assert _row(sentinel, name, day) is not None, f'回滚没恢复：{name} {day}'

    # 回滚同样要重放派生字段 → 独立复算应零差异
    ver = _run_script(VERIFIER, '--accounts', ','.join(ACCOUNTS))
    assert ver.returncode == 0, ver.stdout + ver.stderr

    # 幂等：再回滚一次不重复恢复，且不报错
    rb2 = _run_script(MIGRATION, *_migration_args('--rollback'))
    assert rb2.returncode == 0, rb2.stdout + rb2.stderr
    assert '正在恢复 0 行非交易日净值行' in rb2.stdout, rb2.stdout
    assert '无需恢复' in rb2.stdout
    assert len(_sentinel_rows(sentinel)) == EXPECT_REMAINING


# --------------------------------------------------------------------------- #
# 负向：DSN 防呆（非测试库 + --apply 必须显式放行）
# --------------------------------------------------------------------------- #

def test_apply_on_non_test_db_requires_explicit_flag():
    res = subprocess.run(
        [sys.executable, str(MIGRATION), '--apply',
         '--dsn', 'postgresql://mac@127.0.0.1:5432/quant_investment_guarded_probe'],
        cwd=str(REPO_ROOT), env={**os.environ, 'PYTHONPATH': str(REPO_ROOT)},
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 5, res.stdout + res.stderr
    assert '--allow-production' in res.stdout
