"""净值快照卫生整治（2026-11-03，节假日假快照修复的数据Remediation）

背景（两个已确认的根因）：
1. **节假日假快照**：TradingDayGuard 盘中启发式把节假日工作日误判为交易日
   （2026-10-01 国庆全账户、2026-09-25 中秋、2026-08-08 周六共 47 行），
   orchestrator 的 POST_MARKET 在假日 15:30 写下「旧价标新日」的快照。
2. **真交易日缺口**：2026-10-08 / 10-12~10-14 全账户缺快照（10-08 是 guard 的
   "近7日有K线"启发式在长假后失效；10-12~14 是 daemon 停摆），更早的 8~9 月
   缺口（chip/v13/v14/v15/user_main 等）同理。risk_metrics 的日收益按相邻快照
   差分，缺口把跨日涨跌揉成单日收益。

本脚本（一次性运维，先备份后动刀）：
1. 整表备份到 quant.simulation_equity_snapshot_bak_20261103；
2. 删除不在 quant.trading_calendar 内的快照行（假日假行）；
3. 逐 active 账户锚定回放填补缺失交易日：
   - 持仓份额从开户起全量回放（份额与资金流无关，精确）；
   - 现金从上一个**已有**快照的 cash 起锚，当日叠加交易腿与外部流水
     （deposit/withdraw/adjustment；buy_debit/sell_credit 是交易腿不入账）；
   - 走到下一个已有快照时做现金对账，偏差 >0.1% 报警并以生产值重锚
     （只写缺口日，已有行一律不动）；
4. 全序列重算 daily_return（缺口填上后，缺口后行的基准变了，存量值已过时）；
5. 重算账户 max_drawdown；输出校验报告。

用法：
    ./venv/bin/python tools/oneoff/hygiene_equity_snapshots_20261103.py            # 执行
    ./venv/bin/python tools/oneoff/hygiene_equity_snapshots_20261103.py --dry-run  # 只报告
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

BACKUP_TABLE = 'quant.simulation_equity_snapshot_bak_20261103'
# 现金对账容差：成交额含分位舍入，1 元或 0.1% 取大者
CASH_TOL_ABS = 1.0
CASH_TOL_REL = 0.001


def _close_at(symbol_prices: dict, day: date, default: float = 0.0) -> float:
    key = day.isoformat()
    if key in symbol_prices:
        return symbol_prices[key]
    earlier = [d for d in symbol_prices if d < key]
    return symbol_prices[max(earlier)] if earlier else default


def main() -> int:
    dry_run = '--dry-run' in sys.argv

    from infrastructure.services.service_factory import ServiceFactory
    ServiceFactory.initialize()

    from sqlalchemy import create_engine, text
    from qs_kernel.domain.ports import ISimulationRepository, IKlineRepository
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

    repo = ServiceFactory.resolve(ISimulationRepository)
    kline_repo = ServiceFactory.resolve(IKlineRepository)
    engine = create_engine('postgresql+psycopg2:///quant_investment')

    # ── 1. 备份 ────────────────────────────────────────────────
    with engine.begin() as conn:
        exists = conn.execute(text(
            "SELECT to_regclass(:t) IS NOT NULL"), {'t': BACKUP_TABLE}).scalar()
        if not exists:
            conn.execute(text(f'CREATE TABLE {BACKUP_TABLE} AS TABLE quant.simulation_equity_snapshot'))
            n = conn.execute(text(f'SELECT count(*) FROM {BACKUP_TABLE}')).scalar()
            print(f'[hygiene] 备份完成: {BACKUP_TABLE} ({n} 行)')
        else:
            print(f'[hygiene] 备份已存在，跳过: {BACKUP_TABLE}')

    # ── 2. 删除假日假快照 ──────────────────────────────────────
    with engine.begin() as conn:
        fake = conn.execute(text("""
            SELECT count(*) FROM quant.simulation_equity_snapshot s
            WHERE NOT EXISTS (SELECT 1 FROM quant.trading_calendar c WHERE c.trade_date = s.snapshot_date)
        """)).scalar()
        print(f'[hygiene] 假日假快照行数: {fake}')
        if fake and not dry_run:
            conn.execute(text("""
                DELETE FROM quant.simulation_equity_snapshot s
                WHERE NOT EXISTS (SELECT 1 FROM quant.trading_calendar c WHERE c.trade_date = s.snapshot_date)
            """))
            print(f'[hygiene] 已删除 {fake} 行假日假快照')

    # ── 3. 逐账户锚定回放填补缺口 ──────────────────────────────
    accounts = repo.list_accounts(status='active')
    total_filled = 0
    for acct in accounts:
        name = acct.account_name
        snaps = repo.get_equity_snapshots(name, limit=100000)
        snaps = sorted(snaps, key=lambda s: s.snapshot_date)
        if len(snaps) < 2:
            continue
        lo, hi = snaps[0].snapshot_date, snaps[-1].snapshot_date

        with engine.connect() as conn:
            days = [r[0] for r in conn.execute(text("""
                SELECT DISTINCT trade_date FROM quant.trading_calendar
                WHERE exchange='SSE' AND trade_date BETWEEN :lo AND :hi ORDER BY trade_date
            """), {'lo': lo, 'hi': hi})]
        existing = {s.snapshot_date: s for s in snaps}
        missing = [d for d in days if d not in existing]
        if not missing:
            print(f'[hygiene] {name}: 无缺口，跳过')
            continue
        print(f'[hygiene] {name}: 缺口 {len(missing)} 天 '
              f'({missing[0]} ~ {missing[-1]})，开始锚定回放' + ('（dry-run）' if dry_run else ''))
        if dry_run:
            total_filled += len(missing)
            continue

        trades = sorted(repo.get_trades_by_account(name), key=lambda t: (t.trade_date, t.id or 0))
        ext_flows = _external_flows(engine, name)
        symbols = sorted({t.symbol for t in trades})
        batch = kline_repo.batch_get_kline(symbols, (lo - timedelta(days=10)).isoformat(), hi.isoformat())
        prices = {}
        for sym, df in (batch or {}).items():
            if df is None or getattr(df, 'is_empty', lambda: True)():
                continue
            prices[sym] = {str(r['trade_date'])[:10]: float(r['close'])
                           for r in df.select(['trade_date', 'close']).to_dicts()}

        # 份额回放（全历史，与现金无关）+ 现金行走（锚定已有快照）
        initial = float(acct.initial_capital or 0)
        cash = float(snaps[0].cash or 0)
        peak = max(initial, cash)
        holdings: dict = {}
        ti = 0
        by_date_trades: dict = {}
        for t in trades:
            by_date_trades.setdefault(t.trade_date, []).append(t)
        filled = 0
        for d in days:
            for t in by_date_trades.get(d, []):
                if t.action == 'BUY':
                    cash -= float(t.total_cost or t.amount or 0)
                    holdings[t.symbol] = holdings.get(t.symbol, 0) + t.shares
                elif t.action == 'SELL':
                    cash += float(t.total_revenue or t.amount or 0)
                    holdings[t.symbol] = holdings.get(t.symbol, 0) - t.shares
            cash += ext_flows.get(d, 0.0)
            pos_value = sum(
                sh * _close_at(prices.get(sym, {}), d, default=0.0)
                for sym, sh in holdings.items() if sh > 0
            )
            total = cash + pos_value
            peak = max(peak, total)
            row = existing.get(d)
            if row is not None:
                prod_cash = float(row.cash or 0)
                tol = max(CASH_TOL_ABS, abs(prod_cash) * CASH_TOL_REL)
                if abs(cash - prod_cash) > tol:
                    print(f'[hygiene] ⚠️ {name} {d} 现金对账偏差 '
                          f'{cash:.2f} vs 生产 {prod_cash:.2f} → 以生产值重锚')
                cash = prod_cash  # 锚定生产（已有行本身不动）
                peak = max(peak, float(row.total_value or 0))
                continue
            repo.upsert_equity_snapshot(
                account_name=name, cash=cash, position_value=pos_value, total_value=total,
                cumulative_return=(total / initial - 1) if initial > 0 else 0.0,
                drawdown=(total / peak - 1) if peak > 0 else 0.0,
                snapshot_date=d)
            filled += 1
        print(f'[hygiene] {name}: 回填 {filled} 天')
        total_filled += filled

    if dry_run:
        print(f'[hygiene] dry-run 完毕，预计回填 {total_filled} 天')
        return 0

    # ── 4. 全序列重算 daily_return ─────────────────────────────
    print('[hygiene] 重算 daily_return …')
    sim_repo = SimulationORMRepository()
    for acct in accounts:
        name = acct.account_name
        snaps = sorted(repo.get_equity_snapshots(name, limit=100000), key=lambda s: s.snapshot_date)
        for s in snaps:
            r = sim_repo.calculate_daily_return(name, s.snapshot_date, float(s.total_value or 0))
            if (r is None) != (s.daily_return is None) or (r is not None and abs(float(r) - float(s.daily_return or 0)) > 1e-9):
                sim_repo.session.execute(
                    text('UPDATE quant.simulation_equity_snapshot SET daily_return=:r '
                         'WHERE account_name=:a AND snapshot_date=:d'),
                    {'r': r, 'a': name, 'd': s.snapshot_date})
        sim_repo.session.commit()
        sim_repo.recompute_account_max_drawdown(name)
    sim_repo.session.close()
    print('[hygiene] daily_return 与 max_drawdown 重算完毕')

    # ── 5. 校验 ────────────────────────────────────────────────
    with engine.connect() as conn:
        residual = conn.execute(text("""
            SELECT count(*) FROM quant.simulation_equity_snapshot s
            WHERE NOT EXISTS (SELECT 1 FROM quant.trading_calendar c WHERE c.trade_date = s.snapshot_date)
        """)).scalar()
        print(f'[hygiene] 校验：残余假日假行 = {residual}')
    print('[hygiene] 完成')
    return 0


def _external_flows(engine, account_name: str) -> dict:
    """deposit/withdraw/adjustment 按自然日聚合（buy_debit/sell_credit 是交易腿，不入账）。"""
    from sqlalchemy import text
    out: dict = {}
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT created_at::date AS d, sum(amount) FROM quant.simulation_cash_flow
            WHERE account_name=:a AND flow_type IN ('deposit','withdraw','adjustment')
            GROUP BY 1
        """), {'a': account_name})
        for d, amt in rows:
            if d is not None and amt:
                out[d] = out.get(d, 0.0) + float(amt)
    return out


if __name__ == '__main__':
    raise SystemExit(main())
