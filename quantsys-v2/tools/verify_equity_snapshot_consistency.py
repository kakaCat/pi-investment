#!/usr/bin/env python
"""净值快照一致性校验：逐账户**独立复算**并与库内值比对（REQ-261006190953-fc43 卡 F）

## 它回答什么问题

`20261006_purge_nontrading_equity_snapshots.py` 删掉非交易日行后，逐账户按
`snapshot_date` 升序全序列重放了 `daily_return` / `drawdown` / `cumulative_return`，
并调 `recompute_account_max_drawdown` 写了账户表。本工具**不看迁移脚本的中间结果**，
只从库里读出序列、**独立**复算一遍，逐行/逐账户比对：

| 字段 | 独立复算口径（与目标口径同义，写在两处以便互为对照） |
|---|---|
| `daily_return` | 基准 = `snapshot_date` 之前**最近一个交易日**（`trading_calendar.exchange='ALL' and is_trading_day`）且估值完整的行（`total_value > 0 且 total_value >= cash`）；`(total_value - 当日外部入金 - 基准) / 基准`；无基准 = `None` |
| 外部入金 | `simulation_cash_flow.flow_type='deposit'`，**排除该账户首笔 deposit（成立资金）**；只算 `created_at` 落在当日者（与 `external_flow_on` 同义） |
| 快照 `drawdown` | `peak` 从 `initial_capital` 起逐行 `max(peak, total_value)`；`total_value/peak - 1` |
| `cumulative_return` | `total_value / initial_capital - 1`（`initial_capital<=0` 时为 0） |
| 账户 `max_drawdown` | 峰谷口径、负号：跳过 `total_value<=0 或 total_value<cash` 的行，`worst = min(worst, total_value/peak - 1)`，全程未回撤为 0 |
| 账户 `peak_value` | 序列峰值；仓储只做**单调抬升**（`max(已有, 序列峰值)`），故本工具只在"库内值 < 序列峰值"时报差异（历史更高的峰值不算错，见 `recompute_account_max_drawdown` docstring） |

⚠️ **日历不可得时**（`trading_calendar` 里没有任何 `is_trading_day = true` 的行）本工具
打印告警并退回"上一行"基准口径 —— 与 `trading_day_set()` 返回 `None` 时仓储的行为一致，
**不是**默默按空集过滤。

## 用法

```bash
PYTHONPATH=. ./venv/bin/python tools/verify_equity_snapshot_consistency.py
PYTHONPATH=. ./venv/bin/python tools/verify_equity_snapshot_consistency.py \
    --accounts agent_virtual,user_main_simulation,v13_simulation,v14_simulation,v15_simulation
PYTHONPATH=. ./venv/bin/python tools/verify_equity_snapshot_consistency.py \
    --dsn postgresql://mac@127.0.0.1:5432/quant_test --accounts __sentinel__
```

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 逐账户 `diff=0`（零差异） |
| 2 | 存在差异（逐条打印） |
| 3 | 工具自身出错（连不上库 / 表不存在等） |
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple

TOL_DEFAULT = 1e-4
MAX_DETAIL = 20

EXIT_OK = 0
EXIT_DIFF = 2
EXIT_ERROR = 3


def _parse(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='净值快照一致性校验（独立复算，diff=0 即零差异）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（缺省取 QUANT_DATABASE_URL / 生产库）')
    ap.add_argument('--accounts', default=None, help='限定账户（逗号分隔；缺省=库内全部有快照的账户）')
    ap.add_argument('--tolerance', type=float, default=TOL_DEFAULT,
                    help=f'浮点容差（缺省 {TOL_DEFAULT}；列本身是 numeric(_,4)）')
    ap.add_argument('--max-detail', type=int, default=MAX_DETAIL, help='最多打印多少条差异明细')
    return ap.parse_args(argv)


def _resolve_dsn(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    return os.environ.get('QUANT_DATABASE_URL') or 'postgresql:///quant_investment'


def _psycopg2_dsn(dsn: str) -> str:
    """把 SQLAlchemy 风格 DSN 降成 psycopg2 能吃的形状（去掉 `+driver`）。"""
    if '://' not in dsn:
        return dsn
    scheme, rest = dsn.split('://', 1)
    return f'{scheme.split("+")[0]}://{rest}'


def _close(a, b, tol: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse(argv)
    accounts = [a.strip() for a in (args.accounts or '').split(',') if a.strip()]
    tol = args.tolerance
    try:
        import psycopg2
    except ImportError as exc:  # noqa: BLE001
        print(f'[verify][error] psycopg2 不可用：{exc}')
        return EXIT_ERROR

    dsn = _resolve_dsn(args.dsn)
    try:
        conn = psycopg2.connect(_psycopg2_dsn(dsn))
    except Exception as exc:  # noqa: BLE001
        print(f'[verify][error] 连库失败：{type(exc).__name__}: {exc}')
        return EXIT_ERROR

    try:
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
        where_acct = ''
        params: List = []
        if accounts:
            where_acct = ' and account_name = any(%s)'
            params = [accounts]

        # 交易日集合：与 trading_day_set('ALL') 同口径（只认 is_trading_day = true）
        cur.execute("select trade_date from quant.trading_calendar "
                    "where exchange = 'ALL' and is_trading_day = true")
        trading_days: Optional[Set] = {r[0] for r in cur.fetchall()} or None
        if trading_days is None:
            print('[verify][warn] 交易日历不可得（ALL 无 is_trading_day=true 行）→ '
                  '退回「上一行」基准口径（与 trading_day_set() 返回 None 时一致）')
        else:
            print(f'[verify] 交易日历：{len(trading_days)} 个交易日')

        cur.execute(
            'select id, account_name, snapshot_date, cash, total_value, '
            f'daily_return, cumulative_return, drawdown '
            f'from quant.simulation_equity_snapshot where true{where_acct} '
            'order by account_name, snapshot_date',
            params,
        )
        rows = cur.fetchall()

        cur.execute(
            'select account_name, initial_capital, max_drawdown, peak_value '
            f'from quant.simulation_account where true{where_acct}',
            params,
        )
        acct_meta: Dict[str, Tuple[float, object, object]] = {
            r[0]: (float(r[1] or 0), r[2], r[3]) for r in cur.fetchall()
        }

        cur.execute(
            'select account_name, flow_type, created_at, amount, id '
            'from quant.simulation_cash_flow order by account_name, created_at, id'
        )
        deposits: Dict[str, List] = {}
        for account, ftype, created, amount, _rid in cur.fetchall():
            if ftype != 'deposit':
                continue
            deposits.setdefault(account, []).append((created, float(amount or 0)))
        external: Dict[Tuple[str, object], float] = {}
        for account, items in deposits.items():
            # items[0] = 该账户首笔 deposit（成立资金）→ 不计入任何一日的"外部入金"
            for created, amount in items[1:]:
                if created is None:
                    continue
                key = (account, created.date())
                external[key] = external.get(key, 0.0) + amount
        cur.close()
    except Exception as exc:  # noqa: BLE001
        print(f'[verify][error] 查询失败：{type(exc).__name__}: {exc}')
        conn.close()
        return EXIT_ERROR

    by_account: Dict[str, List] = {}
    for row in rows:
        by_account.setdefault(row[1], []).append(row)

    print(f'[verify] 库={_dsn_dbname(dsn)} 账户={accounts or "全部"} 容差={tol:g} '
          f'快照 {len(rows)} 行 / {len(by_account)} 个账户')

    details: List[str] = []
    total_diff = 0
    for account in sorted(by_account):
        acc_rows = by_account[account]
        initial, stored_max_dd, stored_peak = acct_meta.get(account, (0.0, None, None))
        peak = float(initial or 0)
        series_peak: Optional[float] = None
        prev_valid: Optional[float] = None
        diffs = {'daily_return': 0, 'drawdown': 0, 'cumulative_return': 0}
        for (_rid, _acct, day, cash, total, s_dr, s_cr, s_dd) in acc_rows:
            total_f = float(total or 0)
            cash_f = float(cash or 0)
            ext = external.get((account, day), 0.0)

            e_dr = None
            if prev_valid is not None and prev_valid > 0:
                e_dr = (total_f - ext - prev_valid) / prev_valid
            e_cr = (total_f / initial - 1) if initial > 0 else 0.0
            peak = max(peak, total_f)
            e_dd = (total_f / peak - 1) if peak > 0 else 0.0

            for name, stored, expected in (('daily_return', s_dr, e_dr),
                                           ('drawdown', s_dd, e_dd),
                                           ('cumulative_return', s_cr, e_cr)):
                if not _close(stored, expected, tol):
                    diffs[name] += 1
                    if len(details) < args.max_detail:
                        details.append(
                            f'{account} {day} {name}: 库内={_f(stored)} 复算={_f(expected)}')

            if total_f > 0:
                series_peak = total_f if series_peak is None else max(series_peak, total_f)
            # 基准候选：必须**估值完整**且（日历可得时）**是交易日** ——
            # 与 `SimulationORMRepository.previous_valid_snapshot` 同一口径；
            # 少了这一条就会把周末/节假日行当基准，正是本需求要修的那个口径错位
            if (total_f > 0 and total_f >= cash_f
                    and (trading_days is None or day in trading_days)):
                prev_valid = total_f

        # 账户级：与 recompute_account_max_drawdown 同口径（peak 从首个有效行起，不回退到 initial）
        a_peak, worst = None, 0.0
        for (_rid, _acct, _day, cash, total, *_rest) in acc_rows:
            total_f = float(total or 0)
            cash_f = float(cash or 0)
            if total_f <= 0 or total_f < cash_f:
                continue
            a_peak = total_f if a_peak is None else max(a_peak, total_f)
            if a_peak > 0:
                worst = min(worst, total_f / a_peak - 1.0)

        max_dd_diff = not _close(stored_max_dd, worst, tol)
        # peak_value 是单调抬升量（仓储只抬不降）：只在"库内 < 序列峰值"时才算差异
        peak_diff = series_peak is not None and (
            stored_peak is None or float(stored_peak or 0) < series_peak - tol)
        if max_dd_diff:
            diffs['max_drawdown'] = 1
            details.append(f'{account} max_drawdown: 库内={_f(stored_max_dd)} 复算={_f(worst)}')
        if peak_diff:
            diffs['peak_value'] = 1
            details.append(f'{account} peak_value: 库内={_f(stored_peak)} < 序列峰值={_f(series_peak)}')

        n = sum(diffs.values())
        total_diff += n
        print(f'[verify] {account}: rows={len(acc_rows)} diff={n}'
              f' (daily_return={diffs["daily_return"]} drawdown={diffs["drawdown"]}'
              f' cumulative_return={diffs["cumulative_return"]}'
              f' max_drawdown={diffs.get("max_drawdown", 0)}'
              f' peak_value={diffs.get("peak_value", 0)})')

    if details:
        print('[verify] 差异明细（最多 %d 条）：' % args.max_detail)
        for line in details:
            print(f'[verify]   ! {line}')

    conn.close()
    if total_diff:
        print(f'[verify] 结论：存在差异 {total_diff} 处 → 退出码 {EXIT_DIFF}')
        return EXIT_DIFF
    print(f'[verify] 结论：逐账户 diff=0（{len(by_account)} 个账户 / {len(rows)} 行）→ 退出码 0')
    return EXIT_OK


def _f(v) -> str:
    return 'None' if v is None else f'{float(v):.6f}'


def _dsn_dbname(dsn: str) -> str:
    try:
        from sqlalchemy.engine import make_url
        return make_url(dsn).database or '?'
    except Exception:  # noqa: BLE001
        return dsn.rsplit('/', 1)[-1]


if __name__ == '__main__':
    sys.exit(main())
