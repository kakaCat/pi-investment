#!/usr/bin/env python
"""清理「非交易日净值快照」+ 全序列重算派生字段（2026-10-06 · REQ-261006190953-fc43 卡 F）

## 为什么需要

`quant.simulation_equity_snapshot` 里有 35 行落在非交易日（5 账户 × 7 天：
2026-08-08 / 08-15 / 08-29 / 09-05 / 09-06 / 09-12 / 10-02）。写入闸门（卡 B）只堵住
**未来**，存量脏行必须清掉：它们会被风险指标当成交易日点、把跨节假日的涨跌算成
"假日日收益"、并让最大回撤/波动率失真。删除会让**后续行的基准整体前移**，
所以删完必须逐账户按 `snapshot_date` 升序**全序列重放**（见 design/data-model.md §4）。

## 删除口径（唯一判据，可复跑）

**白名单语义**（2026-10-06 用户裁定，代码见 `_non_trading()`）：

```sql
delete from quant.simulation_equity_snapshot s
where s.snapshot_date between (select min(trade_date) from quant.trading_calendar where exchange='ALL')
                        and (select max(trade_date) from quant.trading_calendar where exchange='ALL')
  and not exists (select 1 from quant.trading_calendar c
                   where c.exchange='ALL' and c.trade_date=s.snapshot_date
                     and c.is_trading_day is true);
```

⚠️ **为什么不是 `is_trading_day = false`**：实测生产日历**没有任何 false 行**（23373 行全 true）——
它是白名单，缺行即非交易日。按 `is false` 匹配得到 **0 行**，清不掉任何脏数据。

⚠️ **防误删靠覆盖范围**：只删 `min~max(trade_date)`（实测 1994-03-01~2026-12-31）**之内**的日期；
范围外一律不动（宁可漏删，不可误删）。

⚠️ **待删行数必须等于预期**：默认 `--expect 35`（生产实测）。不等就**打印差异并非零退出**，
一行都不写（可能是期间又落了新脏行，也可能日历口径变了 —— 两种情况都不许悄悄执行）。

## 重算口径（与写入口径一致，不另造公式）

| 字段 | 口径 |
|---|---|
| `daily_return` | **复用** `SimulationORMRepository.calculate_daily_return`（基准=上一交易日有效快照；扣当日 `external_flow_on` 入金；无基准写 NULL） |
| `drawdown` | `peak` 从 `initial_capital` 起逐行 `max(peak, total_value)`，`drawdown = total_value/peak - 1`（负号口径，与 `_snapshot_one` / `backfill_account` 一致） |
| `cumulative_return` | `total_value / initial_capital - 1`（行内自洽） |
| 账户 `peak_value` / `max_drawdown` | 调 `SimulationORMRepository.recompute_account_max_drawdown`（唯一真源=净值序列） |

## dry-run 是真的零副作用（不是"只打印"）

**dry-run 走的是与 `--apply` 完全相同的代码路径**：建备份表 → 备份 → 删除 → 重放，
最后 `ROLLBACK`（PG 的 DDL/DML 都可回滚）→ 库内零改动。这样"dry-run 说的"和
"apply 做的"不可能分叉；测试用 dry-run 前后 **表行数 + 校验和** 相等来锁这一条。

唯一的例外是账户表：`recompute_account_max_drawdown` 内部会 commit（既有方法，不改），
会破坏"零副作用"，故 dry-run **只预估**账户级 `max_drawdown`（不写）。

**中途失败怎么补**：快照表 commit 之后、账户级重算之前若进程挂掉，账户表可能滞后。
此时重跑 `--apply --expect 0 --accounts <受影响账户>`：待删 0 行、不发生删除，
但**显式列出的账户会被完整重放**并重算账户字段（幂等，同输入同输出）。

## 用法（注意 `PYTHONPATH=.` —— 库层不自行改 sys.path）

```bash
# dry-run（缺省；生产实测应打印「将删除 35 行」且零改动）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py

# 落库（生产：必须显式 --apply；非 *_test 库还要 --allow-production，见下）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py --apply

# 测试库（显式 DSN；*_test 结尾不需要 --allow-production）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py \
    --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test --accounts __sentinel_a__,__sentinel_b__

# 从备份表恢复（会写回非交易日行 —— 脚本内显式 SQL，不经写入闸门）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py --rollback
```

`--accounts a,b`（可选）把整套动作限定在指定账户：测试靠它把自己造的哨兵账户
与测试库里的其它数据隔开，生产可用它做单账户核对。不给 = 全库。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功（dry-run 已回滚 / apply 已落库 / rollback 已恢复） |
| 2 | 待删行数 ≠ 预期（打印差异，零写入） |
| 3 | 备份覆盖不足（备份行数 < 待删行数）→ 中止，零写入 |
| 4 | 删除行数/删除后判据不符（已在事务内回滚，零写入） |
| 5 | 用法或环境错误（如非测试库未加 `--allow-production`） |
| 6 | 回滚失败（备份表无对应行等） |
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.engine import make_url

#: 备份表（design/data-model.md §2；命名沿用本仓 bak_* 惯例）
BACKUP_TABLE = 'quant.bak_equity_snapshot_nontrading_w_0a409569'
#: 备份行上的原因标记（可追溯是哪条需求、哪次执行）
REASON = 'REQ-261006190953-fc43 purge non-trading equity snapshot'
#: 生产实测待删行数（design/data-model.md §3）；可用 --expect 覆盖
DEFAULT_EXPECT = 35
#: 本仓既有要求：DDL 必须带锁超时，否则会挂在 `idle in transaction` 上无限等锁
LOCK_TIMEOUT = '30s'
#: 浮点比较容差（与仓储既有 `abs(...) > 1e-4` 口径一致；列本身是 numeric(_,4)）
TOL = 1e-4

EXIT_OK = 0
EXIT_COUNT_MISMATCH = 2
EXIT_BACKUP_SHORTFALL = 3
EXIT_DELETE_MISMATCH = 4
EXIT_USAGE = 5
EXIT_ROLLBACK_FAILED = 6

DDL = f"""
create table if not exists {BACKUP_TABLE} (
  account_name      varchar(50)   not null,
  snapshot_date     date          not null,
  cash              numeric(15,2) not null,
  position_value    numeric(15,2) not null,
  total_value       numeric(15,2) not null,
  daily_return      numeric(10,4),
  cumulative_return numeric(10,4),
  drawdown          numeric(10,4),
  created_at        timestamp,
  backed_up_at      timestamp     not null default now(),
  deleted_reason    text          not null,
  primary key (account_name, snapshot_date)
)
"""

def _non_trading(alias: str) -> str:
    """「这行落在非交易日」的判据 —— **唯一实现**，五处 SQL 共用同一份。

    ## 白名单语义（2026-10-06 用户裁定；原设计谓词在此库上匹配 0 行）

    本仓 `quant.trading_calendar` 是**白名单**：它只列交易日 —— 实测生产 23373 行
    `is_trading_day` **全是 true，一条 false 都没有**。因此"非交易日"的正确读法是
    **覆盖范围内、不在清单里**（`TradingDayGuard` 也是这么判的：`source='trading-calendar-holiday'`），
    而不是"显式标了 false"。

    原设计写的是 `join calendar … where is_trading_day is false`（本意"宁可漏删不可误删"），
    在这张日历上待删 = 0 行、`--expect 35` 永不成立 → **一行都清不掉**。这不是脚本 bug，
    是判据对数据模型理解错误；改成白名单语义后 35 行全部命中。

    ## 防误删由「覆盖范围」承担

    只管 `min(trade_date) ~ max(trade_date)`（实测 1994-03-01~2026-12-31）**之内**的日期：
    范围外（例如日历还没铺到的未来日期）一律不动 —— 保住了原谓词"宁可漏删"的意图。
    """
    return (
        f"{alias}.snapshot_date between\n"
        f"      (select min(trade_date) from quant.trading_calendar where exchange = 'ALL')\n"
        f"      and (select max(trade_date) from quant.trading_calendar where exchange = 'ALL')\n"
        f"  and not exists (\n"
        f"      select 1 from quant.trading_calendar c\n"
        f"       where c.exchange = 'ALL'\n"
        f"         and c.trade_date = {alias}.snapshot_date\n"
        f"         and c.is_trading_day is true\n"
        f"  )"
    )


#: 待删行（= 判据的唯一实现；`:accounts` 缺省不存在）
PENDING_SQL = """
select s.account_name, s.snapshot_date, s.total_value, s.daily_return,
       s.cumulative_return, s.drawdown
from quant.simulation_equity_snapshot s
where """ + _non_trading('s') + """{acct}
order by s.account_name, s.snapshot_date
"""

#: 备份：把待删行整行搬进备份表（幂等：同键已在库则跳过，保留首次备份内容）
BACKUP_INSERT_SQL = """
insert into """ + BACKUP_TABLE + """
  (account_name, snapshot_date, cash, position_value, total_value,
   daily_return, cumulative_return, drawdown, created_at, backed_up_at, deleted_reason)
select s.account_name, s.snapshot_date, s.cash, s.position_value, s.total_value,
       s.daily_return, s.cumulative_return, s.drawdown, s.created_at, now(), :reason
from quant.simulation_equity_snapshot s
where """ + _non_trading('s') + """{acct}
on conflict (account_name, snapshot_date) do nothing
"""

#: 备份覆盖度：**待删行中有多少行已在备份表里**（判据是"覆盖"而不是"这次插了几行"，
#: 否则 rollback 后再 apply 会被自己的幂等插入误判成"备份不足"）
BACKUP_COVERAGE_SQL = """
select count(*)
from """ + BACKUP_TABLE + """ b
join quant.simulation_equity_snapshot s
  on s.account_name = b.account_name and s.snapshot_date = b.snapshot_date
where """ + _non_trading('s') + """{acct}
"""

DELETE_SQL = """
delete from quant.simulation_equity_snapshot s
where """ + _non_trading('s') + """{acct}
"""

#: 删除后判据（同一谓词；apply 后必须为 0）
JUDGE_SQL = """
select count(*)
from quant.simulation_equity_snapshot s
where """ + _non_trading('s') + """{acct}
"""

ROLLBACK_INSERT_SQL = """
insert into quant.simulation_equity_snapshot
  (account_name, snapshot_date, cash, position_value, total_value,
   daily_return, cumulative_return, drawdown, created_at)
select b.account_name, b.snapshot_date, b.cash, b.position_value, b.total_value,
       b.daily_return, b.cumulative_return, b.drawdown, b.created_at
from """ + BACKUP_TABLE + """ b
where true{acct}
on conflict (account_name, snapshot_date) do nothing
"""

#: 将被恢复的行 = 备份表里有、而快照表里**没有**的键（已存在的键按 on conflict 跳过，
#: 故"正在恢复 N 行"的 N 必须按**实际缺的行**数，否则幂等重跑会谎报行数）
ROLLBACK_PENDING_SQL = """
select b.account_name, b.snapshot_date
from """ + BACKUP_TABLE + """ b
left join quant.simulation_equity_snapshot s
  on s.account_name = b.account_name and s.snapshot_date = b.snapshot_date
where s.account_name is null{acct}
order by b.account_name, b.snapshot_date
"""


def _sql(template: str, alias: str, accounts: Sequence[str]) -> str:
    """把受控的 `{acct}` 占位符换成账户过滤片段（不用 str.format：SQL 里有 `{}` 风险）。"""
    return template.replace('{acct}', _clause(alias, accounts))


# --------------------------------------------------------------------------- #
# 参数与连接
# --------------------------------------------------------------------------- #

def _parse(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description='清理非交易日净值快照并全序列重算（缺省 dry-run）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true', help='真正落库（缺省仅 dry-run）')
    mode.add_argument('--rollback', action='store_true', help='从备份表恢复被删的非交易日行')
    mode.add_argument('--dry-run', action='store_true', help='显式声明 dry-run（缺省行为）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（测试库用；例 postgresql://mac@127.0.0.1:5432/quant_test）')
    ap.add_argument('--expect', type=int, default=DEFAULT_EXPECT,
                    help=f'预期待删行数（缺省 {DEFAULT_EXPECT}；apply 第二次跑请显式传 0）')
    ap.add_argument('--accounts', default=None, help='限定账户（逗号分隔；缺省=全库）')
    ap.add_argument('--allow-production', action='store_true',
                    help='非 *_test 库上执行 --apply / --rollback 的显式放行（防呆）')
    return ap.parse_args(argv)


def _resolve_dsn(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    return os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'


def _dbname(dsn: str) -> str:
    return make_url(dsn).database or ''


def _accounts_of(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [a.strip() for a in raw.split(',') if a.strip()]


def _clause(alias: str, accounts: Sequence[str]) -> str:
    """账户过滤片段（占位符 `:accounts` 需 expanding 绑定）。"""
    return f' and {alias}.account_name in :accounts' if accounts else ''


def _run(session, sql: str, accounts: Sequence[str], params: Optional[Dict] = None):
    stmt = text(sql)
    if accounts:
        stmt = stmt.bindparams(bindparam('accounts', expanding=True))
    merged = dict(params or {})
    if accounts:
        merged['accounts'] = list(accounts)
    return session.execute(stmt, merged)


# --------------------------------------------------------------------------- #
# 重放（唯一实现，dry-run 与 apply 共用）
# --------------------------------------------------------------------------- #

def _differs(old, new) -> bool:
    """NULL 与数值都按"真变了"判定；两值皆 None 视为未变（与仓储既有 1e-4 口径一致）。"""
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return abs(float(old) - float(new)) > TOL


def _replay_account(repo, account_name: str, rows, initial_capital: float,
                    collect: int = 0) -> Tuple[int, List[str]]:
    """按 snapshot_date 升序全序列重放，返回 (改动行数, 差异样例)。

    `daily_return` **复用** `SimulationORMRepository.calculate_daily_return`
    （基准=上一交易日有效快照 + 扣 `external_flow_on` 入金），不另写公式。
    每行算完立刻 flush：下一行的基准必须看到本行已更新的 `total_value`。
    """
    peak = float(initial_capital or 0)
    changed = 0
    samples: List[str] = []
    for row in rows:
        total = float(row.total_value or 0)
        old = (row.daily_return, row.cumulative_return, row.drawdown)
        new_dr = repo.calculate_daily_return(account_name, row.snapshot_date, total)
        new_cr = (total / initial_capital - 1) if initial_capital > 0 else 0.0
        peak = max(peak, total)
        new_dd = (total / peak - 1) if peak > 0 else 0.0
        if _differs(old[0], new_dr) or _differs(old[1], new_cr) or _differs(old[2], new_dd):
            changed += 1
            if len(samples) < collect:
                samples.append(
                    f'{account_name} {row.snapshot_date} daily {_fmt(old[0])} -> {_fmt(new_dr)}'
                    f'  cum {_fmt(old[1])} -> {_fmt(new_cr)}  dd {_fmt(old[2])} -> {_fmt(new_dd)}'
                )
            row.daily_return = new_dr
            row.cumulative_return = new_cr
            row.drawdown = new_dd
        repo.session.flush()
    return changed, samples


def _fmt(v) -> str:
    return 'None' if v is None else f'{float(v):.4f}'


def _load_accounts(repo, names: Sequence[str]) -> Dict[str, Tuple[float, object]]:
    from infrastructure.persistence.orm.models import SimulationAccount

    out: Dict[str, Tuple[float, object]] = {}
    for name in names:
        acct = (repo.session.query(SimulationAccount)
                .filter_by(account_name=name).first())
        if acct is None:
            print(f'[warn] 账户不存在：{name}（跳过其账户级重算）')
            continue
        out[name] = (float(acct.initial_capital or 0), acct)
    return out


def _account_rows(repo, account_name: str):
    from infrastructure.persistence.orm.models import SimulationEquitySnapshot

    return (repo.session.query(SimulationEquitySnapshot)
            .filter_by(account_name=account_name)
            .order_by(SimulationEquitySnapshot.snapshot_date.asc())
            .all())


def _max_drawdown_preview(rows) -> Optional[float]:
    """账户级 max_drawdown 的**预估**（与 recompute_account_max_drawdown 同口径）。

    dry-run 不能调那个方法：它会 commit（dry-run 必须零副作用），故这里只做只读预估。
    """
    peak, worst = None, 0.0
    for row in rows:
        total = float(row.total_value or 0)
        cash = float(row.cash or 0)
        if total <= 0 or total < cash:
            continue
        peak = total if peak is None else max(peak, total)
        if peak > 0:
            worst = min(worst, total / peak - 1.0)
    return worst


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def _purge(repo, args, dbname: str) -> int:
    session = repo.session
    accounts = _accounts_of(args.accounts)

    # ── 阶段 0：待删行 + 预期核对（任何写入之前）──────────────────────────
    pending = _run(session, _sql(PENDING_SQL, 's', accounts), accounts).fetchall()
    print(f'[plan] 数据库={dbname} 账户范围={accounts or "全库"}')
    print(f'[plan] 判据（白名单语义）：快照日期落在日历覆盖范围内、且不在交易日清单里')
    print(f'[plan] 待删 {len(pending)} 行；预期 {args.expect} 行')
    for acct, day, total, dr, cr, dd in pending:
        print(f'[plan]   - {acct} {day} total={float(total or 0):.2f} daily={_fmt(dr)}')

    if len(pending) != args.expect:
        print(f'[abort] 待删行数 {len(pending)} ≠ 预期 {args.expect}（差异 '
              f'{len(pending) - args.expect:+d} 行）——**一行都不写**。')
        by_day: Dict[date, int] = {}
        for _a, day, *_rest in pending:
            by_day[day] = by_day.get(day, 0) + 1
        for day in sorted(by_day):
            print(f'[abort]   实际 {day} 有 {by_day[day]} 行')
        print('[abort] 若已确认口径（例如本迁移已执行过一次），显式传 --expect <实际行数> 再跑。')
        session.rollback()
        return EXIT_COUNT_MISMATCH

    # 重放范围 = 待删行涉及账户 ∪ 显式 --accounts：
    # 后者让"进程在 commit 与账户级重算之间挂掉"可以用
    # `--apply --expect 0 --accounts X` 原地补齐（幂等重放同输入同输出）。
    affected = sorted(set(accounts) | {row[0] for row in pending})

    # ── 阶段 1：DDL（lock_timeout 必带）+ 备份 ────────────────────────────
    if not args.apply:
        print(f'[dry-run] 将执行 DDL（lock_timeout={LOCK_TIMEOUT}）：')
        for line in DDL.strip().splitlines():
            print(f'[dry-run]   {line.strip()}')
    session.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
    session.execute(text(DDL))
    session.flush()

    res = _run(session, _sql(BACKUP_INSERT_SQL, 's', accounts), accounts,
               {'reason': REASON})
    print(f'[backup] 本次新备份 {res.rowcount} 行 → {BACKUP_TABLE}')
    covered = _run(session, _sql(BACKUP_COVERAGE_SQL, 's', accounts),
                   accounts).scalar()
    print(f'[backup] 待删行已被备份覆盖 {covered}/{len(pending)} 行')
    if int(covered or 0) < len(pending):
        print(f'[abort] 备份行数 {covered} < 待删行数 {len(pending)} —— 拒绝删除，已回滚。')
        session.rollback()
        return EXIT_BACKUP_SHORTFALL

    # ── 阶段 2：删除 ────────────────────────────────────────────────────
    res = _run(session, _sql(DELETE_SQL, 's', accounts), accounts)
    deleted = res.rowcount or 0
    print(f'[delete] 实际删除 {deleted} 行（预期 {len(pending)} 行）')
    if deleted != len(pending):
        print(f'[abort] 删除行数 {deleted} ≠ 待删行数 {len(pending)} —— 已回滚。')
        session.rollback()
        return EXIT_DELETE_MISMATCH
    session.expire_all()

    # ── 阶段 3：全序列重放（复用仓储口径）────────────────────────────────
    accounts_meta = _load_accounts(repo, affected)
    total_changed = 0
    for name in affected:
        rows = _account_rows(repo, name)
        initial = accounts_meta.get(name, (0.0, None))[0]
        changed, samples = _replay_account(repo, name, rows, initial, collect=8)
        total_changed += changed
        print(f'[replay] {name}: 序列 {len(rows)} 行，派生字段变化 {changed} 行')
        for line in samples:
            print(f'[replay]   {line}')
        if args.apply and name in accounts_meta:
            worst = repo.recompute_account_max_drawdown(name)
            print(f'[replay] {name}: 账户 max_drawdown={_fmt(worst)}（recompute_account_max_drawdown）')
        elif name in accounts_meta:
            print(f'[dry-run] {name}: 账户 max_drawdown 预估 '
                  f'{_fmt(_max_drawdown_preview(rows))}（dry-run 不写账户表）')
    print(f'[replay] 合计重算派生字段 {total_changed} 行')

    # ── 阶段 4：判据复核 ────────────────────────────────────────────────
    left = _run(session, _sql(JUDGE_SQL, 's', accounts), accounts).scalar()
    print(f'[verify] 判据 SQL（非交易日净值行数，本账户范围）={left}')
    if int(left or 0) != 0:
        print('[abort] 删除后判据未清零 —— 已回滚。')
        session.rollback()
        return EXIT_DELETE_MISMATCH

    if not args.apply:
        session.rollback()
        print('[dry-run] 已 ROLLBACK：库内零改动（表行数/校验和与执行前一致）。加 --apply 落库。')
        return EXIT_OK

    session.commit()
    print(f'[apply] 已落库：删除 {deleted} 行、重放 {len(affected)} 个账户、'
          f'重算派生字段 {total_changed} 行')
    print('[apply] 下一步：PYTHONPATH=. ./venv/bin/python tools/verify_equity_snapshot_consistency.py '
          '--accounts ' + ','.join(affected))
    return EXIT_OK


def _rollback(repo, args) -> int:
    session = repo.session
    accounts = _accounts_of(args.accounts)
    try:
        session.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        exists = session.execute(
            text('select to_regclass(:t)'), {'t': BACKUP_TABLE}).scalar()
        if exists is None:
            print(f'[rollback] 备份表 {BACKUP_TABLE} 不存在：无备份可恢复（从未执行过本迁移？）。')
            session.rollback()
            return EXIT_ROLLBACK_FAILED
        rows = _run(session,
                    _sql(ROLLBACK_PENDING_SQL, 'b', accounts), accounts).fetchall()
        n = len(rows)
        # ⑧ 响亮打印：这一步是在写回**非交易日**行，必须让人在日志里一眼看见
        print('=' * 72)
        print(f'⚠️  正在恢复 {n} 行非交易日净值行 —— 这是回滚动作，不是正常写入！')
        print('=' * 72)
        for acct, day in rows[:50]:
            print(f'[rollback]   + {acct} {day}')
        if n > 50:
            print(f'[rollback]   ...（共 {n} 行，此处只列前 50）')
        if n == 0:
            print('[rollback] 备份表无对应行：非交易日行已全部在场（幂等），无需恢复。')
            session.rollback()
            return EXIT_OK

        res = _run(session, _sql(ROLLBACK_INSERT_SQL, 'b', accounts), accounts)
        restored = res.rowcount or 0
        print(f'[rollback] 实际写回 {restored} 行（备份 {n} 行；已存在的键按 on conflict 跳过）')
        session.expire_all()

        affected = sorted({acct for acct, _d in rows})
        accounts_meta = _load_accounts(repo, affected)
        for name in affected:
            acc_rows = _account_rows(repo, name)
            initial = accounts_meta.get(name, (0.0, None))[0]
            changed, _samples = _replay_account(repo, name, acc_rows, initial)
            print(f'[rollback] {name}: 序列 {len(acc_rows)} 行，重放后派生字段变化 {changed} 行')
        session.commit()
        for name in affected:
            if name in accounts_meta:
                worst = repo.recompute_account_max_drawdown(name)
                print(f'[rollback] {name}: 账户 max_drawdown={_fmt(worst)}')
        print(f'[rollback] 完成：恢复 {restored} 行非交易日净值行并重放 {len(affected)} 个账户')
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001 —— 回滚失败必须响亮，且不留半份写入
        session.rollback()
        print(f'[rollback][error] {type(exc).__name__}: {exc}')
        return EXIT_ROLLBACK_FAILED


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse(argv)
    dsn = _resolve_dsn(args.dsn)
    dbname = _dbname(dsn)
    print(f'[dsn] {dbname or "(未解析出库名)"}')

    if (args.apply or args.rollback) and not dbname.endswith('_test') and not args.allow_production:
        print('[abort] 目标库不是 *_test 结尾，却要求 --apply/--rollback。\n'
              '        生产库执行属人工动作，需显式加 --allow-production 放行（防呆）。')
        return EXIT_USAGE

    try:
        from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
        from infrastructure.persistence.orm.config import init_orm
    except ImportError as exc:  # noqa: BLE001 —— 路径没给对时给出可操作的提示
        print(f'[abort] 导入失败：{exc}\n'
              '        请用 `PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/'
              '20261006_purge_nontrading_equity_snapshots.py ...` 运行。')
        return EXIT_USAGE

    init_orm(dsn=dsn)
    repo = SimulationORMRepository()
    try:
        if args.rollback:
            return _rollback(repo, args)
        return _purge(repo, args, dbname)
    finally:
        try:
            repo.session.close()
        except Exception:  # noqa: BLE001 —— 收尾关连接失败不该改变退出码
            pass


if __name__ == '__main__':
    sys.exit(main())
