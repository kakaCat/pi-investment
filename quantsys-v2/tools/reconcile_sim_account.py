#!/usr/bin/env python
"""模拟账户账本对账器（**只读**）——REQ-261004154902-a7cd · t-900179 / FR-10

## 为什么需要它

`v13_simulation` 的账本**自相矛盾**（2026-10-04 取证）：有 4 只标的**累计卖出 > 累计买入**，

    300045 买 1000 / 卖 2000     300561 买 700 / 卖 1400
    300765 买 300  / 卖 600      300469 买 200 / 卖 400

合计凭空多出 ≈ **¥49,425** 卖出收入（≈初始资金 10 万的 49%）→ 账户显示的累计收益 +32.99%
含虚增。成因是**双数据源**并存：`quant.simulation_positions`（持仓表）与
`quant.simulation_trades`（流水净额）；某些卖出路径读的是持仓表，而持仓表又与流水净额不一致
（`SimulationTrader._rebuild_portfolio_from_trades` 已把那几只算成 0）。

本工具把"账本自不自洽"变成一条**可跑、可验收的判据**，三件事：

1. **逐标的买卖净额表**（真源 = 流水）+ 与持仓表的差异（双源实证）；
2. **现金重放**：`初始资金 + Σ卖出收入 - Σ买入成本` 与
   `quant.simulation_account.cash_available` 的差额，并**逐项解释**（含舍入/费用口径）；
3. **超卖清单**（`卖出股数 > 买入股数` 的标的，如实列出，含虚增金额）。

## 用法

    python tools/reconcile_sim_account.py --account v13_simulation
    python tools/reconcile_sim_account.py --account v13_simulation --json

## 退出码（fail-loud）

    0 = 账本自洽（无超卖 且 现金差额可解释）
    2 = 有超卖，或现金重放差额**无法解释**
    3 = 工具自身出错（连不上库 / 账户不存在 / 读不到数据）

## 只读承诺

只发 `SELECT`；**不写任何表**、不发任何通知、不改任何历史成交/持仓/现金数据；
"历史虚增"的处置（标记为脏、从统计排除）由单独一张卡承担，本工具只报不改。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

EXIT_OK = 0
EXIT_INCONSISTENT = 2
EXIT_TOOL_ERROR = 3

#: 现金重放的舍入容差（分位累积的浮点/取整残差）：≤ 该值视为"可解释"
CASH_TOLERANCE = 0.05


# ---------------------------------------------------------------------------
# 取数口径（逐笔成交 → 现金流）
# ---------------------------------------------------------------------------

#: 已知脏数据清单（REQ-261004154902-a7cd · t-174c1d · 用户 2026-10-04 裁定）。
#: 口径：**不删不改**历史成交，只在判定里排除；被排除项仍要打印出来（不隐藏）。
DIRTY_MANIFEST = (pathlib.Path(__file__).resolve().parents[1]
                  / 'config' / 'known_dirty_simulation_data.json')


def _dirty_entry(account_name: str) -> dict:
    """读脏清单里该账户的条目；读不到/未启用 → 返回空（即按原始流水判定，旧口径）。"""
    try:
        data = json.loads(DIRTY_MANIFEST.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001 - 清单缺失只影响"排除"，不影响判定本身
        return {}
    if not data.get('enabled'):
        return {}
    return (data.get('accounts') or {}).get(account_name) or {}


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row_fees(row: Mapping[str, Any]) -> float:
    return (_num(row.get('commission')) + _num(row.get('stamp_duty'))
            + _num(row.get('transfer_fee')))


def _buy_cost(row: Mapping[str, Any]) -> Tuple[float, bool]:
    """一笔买入占用的现金（正数）。返回 ``(cost, derived)``——derived=True 表示由
    ``amount+费用`` 推算（该行 ``total_cost`` 为空；本仓 BUY 行实测如此，只有
    ``total_revenue`` 带负值）。"""
    total_cost = row.get('total_cost')
    if total_cost is not None:
        return _num(total_cost), False
    return _num(row.get('amount')) + _row_fees(row), True


def _sell_revenue(row: Mapping[str, Any]) -> Tuple[float, bool]:
    """一笔卖出换回的现金（正数，已扣费用）。返回 ``(revenue, derived)``。"""
    total_revenue = row.get('total_revenue')
    if total_revenue is not None:
        return _num(total_revenue), False
    return _num(row.get('amount')) - _row_fees(row), True


def _sort_key(row: Mapping[str, Any]) -> Tuple[str, int]:
    return (str(row.get('trade_date') or ''), int(row.get('id') or 0))


def _position_consistent(position_shares: Optional[int], net_shares: int) -> bool:
    """持仓表与流水净额是否一致。

    口径（**只有这三种形态算矛盾**，避免把"两边都没有这只票"报成 20 行噪声）：
    - 持仓表有该行且股数 != 流水净额；
    - 流水净额为负（超卖：账本说"负持有"，持仓表说"没有"）；
    - 流水净额为正、持仓表却没有该行（持仓丢了）。
    两者都"没有该标的"（持仓无行 + 流水净额 0）视为一致。
    """
    if position_shares is None:
        return net_shares == 0
    return position_shares == net_shares


def _phantom_sell_revenue(
    sells: Sequence[Tuple[Mapping[str, Any], int, float]], buy_shares: int
) -> float:
    """**无对应买入**的那部分卖出换回了多少现金（LIFO：先算最近的卖出）。

    口径说明（本工具的选择，写在这里以免成为第二个暗口径）：超卖股数 =
    ``Σ卖出股数 - Σ买入股数``；这部分股数按**从最新往前**对齐到卖出笔上，
    收入按股数比例分摊。实测 v13_simulation 的结果正好等于 2026-08-21 那 4 笔重复卖出的
    净收入合计 ¥49,424.96（与设计文档取证的 ≈¥49,425 一致）。
    """
    oversold = sum(shares for _, shares, _ in sells) - buy_shares
    if oversold <= 0:
        return 0.0

    remaining = oversold
    revenue = 0.0
    for _row, shares, rev in reversed(sells):
        if remaining <= 0:
            break
        take = min(remaining, shares)
        if shares > 0:
            revenue += rev * (take / shares)
        remaining -= take
    return revenue


# ---------------------------------------------------------------------------
# 报告（纯函数：不碰库，便于单测喂假数据）
# ---------------------------------------------------------------------------

def build_report(
    account_name: str,
    trades: Iterable[Mapping[str, Any]],
    account: Mapping[str, Any],
    positions: Optional[Iterable[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """把「账户行 + 成交流水 + 持仓表」算成对账报告（**纯函数**，零 IO）。"""
    trades = [dict(t) for t in trades]
    positions = [dict(p) for p in (positions or [])]

    per_symbol: Dict[str, Dict[str, Any]] = {}
    derived_flows = 0
    unknown_actions = 0
    fees = {'commission': 0.0, 'stamp_duty': 0.0, 'transfer_fee': 0.0}
    sell_revenue_total = 0.0
    buy_cost_total = 0.0

    for row in sorted(trades, key=_sort_key):
        symbol = str(row.get('symbol') or '')
        action = str(row.get('action') or '').strip().upper()
        shares = int(_num(row.get('shares')))
        slot = per_symbol.setdefault(symbol, {
            'symbol': symbol, 'buy_shares': 0, 'sell_shares': 0,
            'buy_cost': 0.0, 'sell_revenue': 0.0, 'fees': 0.0,
            'sells': [], 'first_over_sell_date': None,
            'derived_flows': 0,
        })
        slot['fees'] += _row_fees(row)
        for key in fees:
            fees[key] += _num(row.get(key))

        if action == 'BUY':
            cost, derived = _buy_cost(row)
            slot['buy_shares'] += shares
            slot['buy_cost'] += cost
            buy_cost_total += cost
        elif action == 'SELL':
            revenue, derived = _sell_revenue(row)
            slot['sell_shares'] += shares
            slot['sell_revenue'] += revenue
            slot['sells'].append((row, shares, revenue))
            sell_revenue_total += revenue
            # 首次越界：累计卖出 > 累计买入 的那一笔（口径与下方超卖判定同源）
            if (slot['first_over_sell_date'] is None
                    and slot['sell_shares'] > slot['buy_shares']):
                slot['first_over_sell_date'] = str(row.get('trade_date') or '')
        else:
            unknown_actions += 1
            continue

        if derived:
            derived_flows += 1
            slot['derived_flows'] += 1

    position_shares = {str(p.get('symbol') or ''): int(_num(p.get('shares_total')))
                       for p in positions}

    symbols: List[Dict[str, Any]] = []
    oversold: List[Dict[str, Any]] = []
    for symbol in sorted(per_symbol):
        slot = per_symbol[symbol]
        net_shares = slot['buy_shares'] - slot['sell_shares']
        phantom_shares = max(0, slot['sell_shares'] - slot['buy_shares'])
        phantom_revenue = _phantom_sell_revenue(slot['sells'], slot['buy_shares'])
        pos_shares = position_shares.get(symbol)
        entry = {
            'symbol': symbol,
            'buy_shares': slot['buy_shares'],
            'sell_shares': slot['sell_shares'],
            'net_shares': net_shares,
            'buy_cost': round(slot['buy_cost'], 2),
            'sell_revenue': round(slot['sell_revenue'], 2),
            'net_flow': round(slot['sell_revenue'] - slot['buy_cost'], 2),
            'fees': round(slot['fees'], 2),
            'position_shares': pos_shares,
            'position_matches_trades': _position_consistent(pos_shares, net_shares),
            'derived_flows': slot['derived_flows'],
            'oversold': slot['sell_shares'] > slot['buy_shares'],
            'phantom_sell_shares': phantom_shares,
            'phantom_revenue': round(phantom_revenue, 2),
            'first_over_sell_date': slot['first_over_sell_date'],
        }
        symbols.append(entry)
        if entry['oversold']:
            oversold.append(entry)

    # 持仓表 ↔ 流水净额 的差异（双数据源的实证；只报不改）
    mismatch: List[Dict[str, Any]] = []
    for symbol in sorted(set(position_shares) | {s['symbol'] for s in symbols}):
        pos_shares = position_shares.get(symbol)
        net_shares = next((s['net_shares'] for s in symbols if s['symbol'] == symbol), 0)
        if not _position_consistent(pos_shares, net_shares):
            mismatch.append({
                'symbol': symbol,
                'position_shares': pos_shares,
                'trades_net_shares': net_shares,
                'delta': None if pos_shares is None else pos_shares - net_shares,
            })

    initial_capital = _num(account.get('initial_capital'))
    cash_available = _num(account.get('cash_available'))
    cash_frozen = _num(account.get('cash_frozen'))
    cash_expected = initial_capital + sell_revenue_total - buy_cost_total
    diff = cash_available - cash_expected
    explained = abs(diff) <= CASH_TOLERANCE
    phantom_total = round(sum(s['phantom_revenue'] for s in oversold), 2)

    explanations: List[str] = []
    if explained:
        explanations.append(
            f'现金重放与流水**自洽**：差额 ¥{diff:,.2f}（≤ 容差 ¥{CASH_TOLERANCE}，'
            f'属分位取整残差）'
        )
    else:
        explanations.append(
            f'现金重放差额 ¥{diff:,.2f} **超出容差 ¥{CASH_TOLERANCE}**，'
            f'账本与流水不一致且本工具无法用既有口径解释 → 需人工定位'
        )
    if oversold:
        explanations.append(
            f'超卖 {len(oversold)} 只（{", ".join(s["symbol"] for s in oversold)}）：'
            f'无对应买入的卖出收入合计 ¥{phantom_total:,.2f}（LIFO 口径）'
            f'——**已计入 cash_available**，所以它不是上方差额的来源，'
            f'而是流水本身的矛盾（现金与流水自洽 ≠ 账本正确）'
        )
    if mismatch:
        explanations.append(
            f'持仓表(quant.simulation_positions)与流水净额不一致 {len(mismatch)} 只：'
            + '；'.join(
                f"{m['symbol']} 持仓表={m['position_shares']} vs 流水={m['trades_net_shares']}"
                for m in mismatch)
            + '（真源 = 流水；持仓表只应由它派生）'
        )
    explanations.append(
        f'费用（佣金 ¥{fees["commission"]:,.2f} + 印花税 ¥{fees["stamp_duty"]:,.2f} '
        f'+ 过户费 ¥{fees["transfer_fee"]:,.2f}）**已包含在**成交收入/成本里，不重复扣减'
    )
    if derived_flows:
        explanations.append(
            f'{derived_flows} 笔成交缺 total_cost 字段，其买入成本由 "amount + 费用" 推算'
            f'（本仓 BUY 行的既有形态）'
        )
    if unknown_actions:
        explanations.append(f'跳过 {unknown_actions} 笔 action 既非 BUY 也非 SELL 的流水行')

    # ── 已知脏数据排除（REQ-261004154902-a7cd · t-174c1d · 用户裁定）──────────
    dirty = _dirty_entry(account_name)
    known = set((dirty.get('oversold_symbols') or {}).keys())
    for row in oversold:
        row['known_dirty'] = row.get('symbol') in known
    oversold_known = [r for r in oversold if r['known_dirty']]
    oversold_unexpected = [r for r in oversold if not r['known_dirty']]
    if oversold_known:
        explanations.append(
            '已登记为脏数据并排除 {} 只超卖（{}）：用户 2026-10-04 裁定「标记为脏并从统计排除」，'
            '不删不改历史成交；依据见 '
            'docs/requirements/REQ-261004154902-a7cd/notes/legacy-cash-disposition.md'.format(
                len(oversold_known), ', '.join(r['symbol'] for r in oversold_known)))
    if dirty.get('return_note'):
        explanations.append('收益率口径：' + str(dirty['return_note']))

    exit_code = EXIT_OK
    if oversold_unexpected or not explained:
        exit_code = EXIT_INCONSISTENT

    return {
        'account': account_name,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'account_row': {
            'cash_available': cash_available,
            'cash_frozen': cash_frozen,
            'position_value': _num(account.get('position_value')),
            'total_value': _num(account.get('total_value')),
            'initial_capital': initial_capital,
            'cumulative_return': _num(account.get('cumulative_return')),
            'last_rebalance_date': str(account.get('last_rebalance_date') or ''),
            'status': str(account.get('status') or ''),
        },
        'symbols': symbols,
        'cash_replay': {
            'initial_capital': round(initial_capital, 2),
            'sell_revenue_total': round(sell_revenue_total, 2),
            'buy_cost_total': round(buy_cost_total, 2),
            'cash_expected': round(cash_expected, 2),
            'cash_available': round(cash_available, 2),
            'diff': round(diff, 2),
            'tolerance': CASH_TOLERANCE,
            'explained': explained,
            'fees_total': round(sum(fees.values()), 2),
        },
        'oversold': oversold,
        'oversold_unexpected': oversold_unexpected,
        'oversold_known_dirty': oversold_known,
        'known_dirty_manifest': dirty,
        'oversold_phantom_revenue_total': phantom_total,
        'position_mismatch': mismatch,
        'explanations': explanations,
        'exit_code': exit_code,
    }


# ---------------------------------------------------------------------------
# 取数（只读 SELECT）
# ---------------------------------------------------------------------------

def load_inputs(account_name: str) -> Tuple[Mapping[str, Any], List[Dict[str, Any]],
                                            List[Dict[str, Any]]]:
    """只读加载账户行 / 成交流水 / 持仓表（全部 SELECT）。"""
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        account = conn.execute(
            text("""
                SELECT account_name, cash_available, cash_frozen, position_value,
                       total_value, initial_capital, cumulative_return,
                       last_rebalance_date, status
                FROM quant.simulation_account WHERE account_name = :a
            """),
            {'a': account_name},
        ).mappings().first()

        trades = conn.execute(
            text("""
                SELECT id, symbol, action, shares, filled_price, amount, commission,
                       stamp_duty, transfer_fee, total_cost, total_revenue, trade_date
                FROM quant.simulation_trades WHERE account_name = :a
                ORDER BY trade_date, id
            """),
            {'a': account_name},
        ).mappings().all()

        positions = conn.execute(
            text("""
                SELECT symbol, shares_total, shares_available, avg_cost
                FROM quant.simulation_positions WHERE account_name = :a
            """),
            {'a': account_name},
        ).mappings().all()

    return account, [dict(r) for r in trades], [dict(r) for r in positions]


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _display_width(text: str) -> int:
    """按终端显示宽度算（CJK 全角算 2），让中文表头不歪。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + ' ' * max(0, width - _display_width(text))


def _render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    widths = [max(_display_width(h), *(_display_width(str(r[i])) for r in rows)) if rows
              else _display_width(h) for i, h in enumerate(headers)]
    lines = ['  '.join(_pad(h, widths[i]) for i, h in enumerate(headers)),
             '  '.join('-' * widths[i] for i in range(len(headers)))]
    lines += ['  '.join(_pad(str(cell), widths[i]) for i, cell in enumerate(row))
              for row in rows]
    return '\n'.join(lines)


def render_text(report: Mapping[str, Any]) -> str:
    acct = report['account_row']
    out: List[str] = []
    out.append('=' * 78)
    out.append(f"账本对账：{report['account']}（只读；真源 = quant.simulation_trades）")
    out.append('=' * 78)
    out.append(
        f"账户：现金 ¥{acct['cash_available']:,.2f}（冻结 ¥{acct['cash_frozen']:,.2f}）"
        f" + 持仓 ¥{acct['position_value']:,.2f} = 总值 ¥{acct['total_value']:,.2f}；"
        f"初始资金 ¥{acct['initial_capital']:,.2f}；"
        f"累计收益 {acct['cumulative_return']:.2%}；状态 {acct['status']}"
    )

    out.append('')
    out.append('① 逐标的买卖净额表（流水口径）')
    rows = [[
        s['symbol'], str(s['buy_shares']), str(s['sell_shares']), str(s['net_shares']),
        f"{s['buy_cost']:,.2f}", f"{s['sell_revenue']:,.2f}", f"{s['net_flow']:,.2f}",
        '-' if s['position_shares'] is None else str(s['position_shares']),
        '❌超卖' if s['oversold'] else ('≠持仓表' if not s['position_matches_trades'] else 'ok'),
    ] for s in report['symbols']]
    out.append(_render_table(
        ['标的', '买入股', '卖出股', '净股数', '买入成本', '卖出收入', '净现金流',
         '持仓表', '判定'], rows))

    replay = report['cash_replay']
    out.append('')
    out.append('② 现金重放（初始资金 + Σ卖出收入 - Σ买入成本 vs 账户现金）')
    replay_rows = [
        ['初始资金', f"{replay['initial_capital']:,.2f}"],
        ['+ Σ卖出收入', f"{replay['sell_revenue_total']:,.2f}"],
        ['- Σ买入成本', f"{replay['buy_cost_total']:,.2f}"],
        ['= 应有现金', f"{replay['cash_expected']:,.2f}"],
        ['账户 cash_available', f"{replay['cash_available']:,.2f}"],
        ['差额', f"{replay['diff']:,.2f}"
                 f"（{'可解释' if replay['explained'] else '⚠️ 无法解释'}，"
                 f"容差 {replay['tolerance']}）"],
    ]
    out.append(_render_table(['项目', '金额(¥)'], replay_rows))

    out.append('')
    out.append(f"③ 超卖清单（卖出 > 买入）：{len(report['oversold'])} 只")
    if report['oversold']:
        os_rows = [[
            s['symbol'], str(s['buy_shares']), str(s['sell_shares']),
            str(s['phantom_sell_shares']), f"{s['phantom_revenue']:,.2f}",
            s['first_over_sell_date'] or '-',
        ] for s in report['oversold']]
        out.append(_render_table(
            ['标的', '买入股', '卖出股', '凭空卖出股数', '虚增卖出收入(¥)', '首次越界日'], os_rows))
        out.append(f"虚增合计：¥{report['oversold_phantom_revenue_total']:,.2f}")
        dirty_rows = report.get('oversold_known_dirty') or []
        if dirty_rows:
            out.append(
                f"其中 {len(dirty_rows)} 只**已登记为脏数据**（不计入判定）："
                + ', '.join(r['symbol'] for r in dirty_rows)
                + '（用户 2026-10-04 裁定：标记为脏并从统计排除；不删不改历史成交）')
        unexpected = report.get('oversold_unexpected') or []
        if unexpected:
            out.append("⚠️ 另有未登记的超卖（必须处理）："
                       + ', '.join(r['symbol'] for r in unexpected))
    else:
        out.append('（无）')

    out.append('')
    out.append('④ 逐项解释')
    for line in report['explanations']:
        out.append(f'  · {line}')

    out.append('')
    if report['exit_code'] == EXIT_OK:
        dirty_n = len(report.get('oversold_known_dirty') or [])
        verdict = ('✅ 自洽（退出码 0）' if not dirty_n
                   else f'✅ 自洽（退出码 0；已排除 {dirty_n} 只已登记的脏数据）')
    else:
        verdict = '❌ 不自洽（退出码 2）：有**未登记**的超卖或差额无法解释'
    out.append(f"结论：{verdict}")
    return '\n'.join(out)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description='模拟账户账本对账器（只读）')
    ap.add_argument('--account', default='v13_simulation',
                    help='账户名（缺省 v13_simulation）')
    ap.add_argument('--json', action='store_true', help='机器可读输出（同一份判定）')
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        account, trades, positions = load_inputs(args.account)
        if account is None:
            print(f'工具自身出错：账户不存在 {args.account}（quant.simulation_account 无此行）',
                  file=sys.stderr)
            return EXIT_TOOL_ERROR
        report = build_report(args.account, trades, account, positions)
    except Exception as exc:  # noqa: BLE001 - 取数失败 = 工具自身出错（与"账本不自洽"分开）
        print(f'工具自身出错：{type(exc).__name__}: {exc}', file=sys.stderr)
        return EXIT_TOOL_ERROR

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))

    if report['exit_code'] != EXIT_OK:
        for s in report['oversold']:
            print(f"超卖：{s['symbol']} 买 {s['buy_shares']} / 卖 {s['sell_shares']}，"
                  f"虚增 ¥{s['phantom_revenue']:,.2f}（首次越界 {s['first_over_sell_date']}）",
                  file=sys.stderr)
        if not report['cash_replay']['explained']:
            print(f"现金重放差额 ¥{report['cash_replay']['diff']:,.2f} 无法解释", file=sys.stderr)
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
