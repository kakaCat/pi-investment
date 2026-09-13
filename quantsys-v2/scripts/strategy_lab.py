"""策略实验室（strategy_lab.py，2026-09-13 w-c8cae280）

为什么需要它：官方回测（application/services/strategy_backtest_service.run_backtest_from_signals）
**不含任何交易成本**，且每日校验只看 quant.backtest_results 里最近 30 天的证据、阈值 60 分，
0 交易的运行直接得 0 分 → 于是"高分策略"既可能虚高（无成本），"0 分策略"也可能是没跑到交易。
要回答"有没有好策略"，必须有一个自己控制的、苛刻的评估器。

本脚本口径（刻意保守）：
  1. 信号在 T 日收盘产生 → **T+1 开盘成交**（不用当日收盘，避免未来函数）；
  2. **T+1 制度**天然满足（买入次日才可卖）；
  3. 成本：买入 佣金2.5bp+滑点5bp；卖出 佣金2.5bp+印花5bp+滑点5bp（合计约 0.15%/回合）；
  4. 满仓单标的、不加杠杆、不择时加减仓（除策略信号外）；
  5. 篮子模式：多标的各自跑，再等权合成；同时看单标的离散度（防"一只票的运气"）。

用法：
  python scripts/strategy_lab.py eval <strategy_id> [--split] [--start 2023-01-01] [--end 2026-09-11]
  python scripts/strategy_lab.py eval-code <path.py> [--split]
"""
import argparse, json, sys, statistics
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

COST_BUY_BP = 2.5 + 5.0      # 佣金 + 滑点（bp）
COST_SELL_BP = 2.5 + 5.0 + 5.0   # 佣金 + 印花 + 滑点（bp）
BASKET = ["600519", "000858", "601318", "600036", "000333", "600276",
          "002415", "600887", "601857", "600030", "000001", "601888"]


def load_klines(symbol: str, start: str, end: str) -> pd.DataFrame:
    """从 quant.daily_klines 取日线（前复权口径以库内为准）。"""
    from infrastructure.services.service_factory import ServiceFactory  # noqa: F401  (保持与线上同源)
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    from domain.ports import IKlineRepository
    repo = EnhancedServiceFactory.resolve(IKlineRepository)
    df = repo.get_daily_klines(symbol, start_date=start, end_date=end)
    if df is None:
        return pd.DataFrame()
    pdf = df.to_pandas() if isinstance(df, pl.DataFrame) else pd.DataFrame(df)
    if pdf.empty or 'close' not in pdf.columns:
        return pd.DataFrame()
    pdf['trade_date'] = pd.to_datetime(pdf['trade_date'])
    return pdf.sort_values('trade_date').reset_index(drop=True)


def run_snippet(code: str, df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """按框架约定执行策略代码：命名空间给 df / params / pd / np，返回带 buy/sell 列的 df。"""
    ns = {"pd": pd, "np": np, "df": df.copy(), "params": dict(params or {})}
    exec(compile(code, "<strategy>", "exec"), ns)  # noqa: S102  —— 策略代码本来就来自库里的 code_content
    out = ns.get("df")
    if out is None or len(out) != len(df):
        raise ValueError("策略未返回与输入等长的 df")
    return out


def extract_signals(sig: pd.DataFrame) -> pd.DataFrame:
    """兼容 buy/sell 与 buy_tierN/sell_tierN 两种列约定 → 统一为 buy/sell 布尔列。"""
    s = pd.DataFrame(index=sig.index)
    if 'buy' in sig.columns and 'sell' in sig.columns:
        s['buy'] = sig['buy'].fillna(False).astype(bool)
        s['sell'] = sig['sell'].fillna(False).astype(bool)
        return s
    buy = pd.Series(False, index=sig.index)
    sell = pd.Series(False, index=sig.index)
    for t in (1, 2, 3):
        bc, sc = f'buy_tier{t}', f'sell_tier{t}'
        if bc in sig.columns:
            buy = buy | sig[bc].fillna(False).astype(bool)
        if sc in sig.columns:
            sell = sell | sig[sc].fillna(False).astype(bool)
    s['buy'], s['sell'] = buy, sell
    return s


def simulate(df: pd.DataFrame, sig: pd.DataFrame, exposure: float = 0.95):
    """T 信号 → T+1 开盘成交；含成本；返回逐日净值与交易明细。"""
    cash, shares = 1.0, 0.0           # 归一化：净值起点 1.0
    equity, trades, pending = [], [], None
    entry_price = entry_idx = None
    for i in range(len(df)):
        o, c = float(df["open"].iloc[i]), float(df["close"].iloc[i])
        if pending == "buy" and shares == 0.0:
            px = o * (1 + COST_BUY_BP / 10000.0)
            shares = (cash * exposure) / px
            cash -= shares * px
            entry_price, entry_idx = px, i
        elif pending == "sell" and shares > 0.0:
            px = o * (1 - COST_SELL_BP / 10000.0)
            cash += shares * px
            trades.append({"entry_i": entry_idx, "exit_i": i,
                           "ret": px / entry_price - 1.0 if entry_price else 0.0,
                           "days": i - (entry_idx or i)})
            shares, entry_price = 0.0, None
        pending = None
        if i + 1 < len(df):
            b, s = bool(sig["buy"].iloc[i]), bool(sig["sell"].iloc[i])
            if b and shares == 0.0:
                pending = "buy"
            elif s and shares > 0.0:
                pending = "sell"
        equity.append(cash + shares * c)
    eq = pd.Series(equity, index=df["trade_date"])
    return eq, trades


def metrics(eq: pd.Series, trades: list, min_trades: int = 3) -> dict:
    if len(eq) < 30:
        return {"ok": False, "reason": "样本太短"}
    ret = eq.iloc[-1] / eq.iloc[0] - 1.0
    days = (eq.index[-1] - eq.index[0]).days or 1
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (365.0 / days) - 1.0
    dd = float((eq / eq.cummax() - 1.0).min())
    dr = eq.pct_change().dropna()
    sharpe = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0
    wins = [t["ret"] for t in trades if t["ret"] > 0]
    return {"ok": True, "total_return": round(ret, 4), "cagr": round(cagr, 4),
            "max_dd": round(dd, 4), "sharpe": round(sharpe, 2),
            "trades": len(trades), "win_rate": round(len(wins) / len(trades), 3) if trades else None,
            "avg_hold_days": round(statistics.mean([t["days"] for t in trades]), 1) if trades else 0,
            "exposure_pct": round(float((eq.pct_change().abs() > 0).mean()) * 100, 1),
            "enough_trades": len(trades) >= min_trades}


def evaluate(code: str, params: dict, symbols, start: str, end: str, label: str) -> dict:
    rows, curves = [], []
    for sym in symbols:
        df = load_klines(sym, start, end)
        if len(df) < 60:
            continue
        try:
            sig = extract_signals(run_snippet(code, df, params))
        except Exception as e:  # noqa: BLE001
            rows.append({"symbol": sym, "ok": False, "reason": f"策略执行失败: {str(e)[:60]}"})
            continue
        eq, trades = simulate(df, sig)
        m = metrics(eq, trades)
        m["symbol"] = sym
        rows.append(m)
        if m.get("ok"):
            curves.append(eq / eq.iloc[0])
    ok = [r for r in rows if r.get("ok")]
    agg = {}
    if curves:
        common = curves[0].index
        for c in curves[1:]:
            common = common.intersection(c.index)
        mat = pd.concat([c.reindex(common) for c in curves], axis=1).dropna()
        port = mat.mean(axis=1)
        # 组合层交易统计：各标的中"该标的曾开过仓"即可，这里用 per_symbol 的 trades 汇总（口径见下）
        total_trades = sum(int(r.get("trades") or 0) for r in ok)
        agg = metrics(port, [], min_trades=0)
        agg["trades"] = total_trades
        agg["trades_median_per_symbol"] = int(statistics.median([r.get("trades") or 0 for r in ok])) if ok else 0
        agg["n_symbols"] = mat.shape[1]
        cagrs = [r["cagr"] for r in ok]
        agg["cagr_median"] = round(statistics.median(cagrs), 4)
        agg["cagr_best"] = round(max(cagrs), 4)
        agg["cagr_worst"] = round(min(cagrs), 4)
        agg["pct_positive_symbols"] = round(sum(1 for c in cagrs if c > 0) / len(cagrs), 3)
    return {"label": label, "period": f"{start}~{end}", "portfolio": agg, "per_symbol": rows}


def subprocess_run_psql_name(sid: int) -> str:
    import subprocess, os
    env = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
    out = subprocess.run(["psql", "-d", "quant_investment", "-At", "-c",
                          f"select strategy_name from quant.strategy_configs where id={int(sid)}"],
                         capture_output=True, text=True, env=env, check=True).stdout.strip()
    return out or f"strategy_{sid}"


def fetch_strategy(sid: int):
    import subprocess, os
    sql = ("select code_content, coalesce(parsed_params::text,'{}') from quant.strategy_configs "
           f"where id={int(sid)}")
    env = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
    out = subprocess.run(["psql", "-d", "quant_investment", "-At", "-F", "\x1f", "-c", sql],
                         capture_output=True, text=True, env=env, check=True).stdout.strip()
    if not out:
        raise SystemExit(f"策略 {sid} 不存在")
    code, pj = out.split("\x1f")
    raw = json.loads(pj or "{}")
    if isinstance(raw, list):
        params = {p.get("name"): p.get("default") for p in raw if isinstance(p, dict) and p.get("name")}
    elif isinstance(raw, dict) and "params" in raw:
        params = {p.get("name"): p.get("default") for p in (raw["params"] or [])}
    else:
        params = raw if isinstance(raw, dict) else {}
    return code, params


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["eval", "eval-code", "screen"])
    ap.add_argument("target")
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-09-11")
    ap.add_argument("--split", action="store_true", help="样本内/样本外分别评估")
    ap.add_argument("--symbols", default=",".join(BASKET))
    args = ap.parse_args()

    from infrastructure.services.service_registry import register_all_services
    register_all_services()

    if args.mode == "screen":
        ids = [int(x) for x in args.target.split(",") if x]
        symbols = [s for s in args.symbols.split(",") if s]
        print("%-6s %-28s %9s %9s %7s %7s %6s" % ("id", "name", "CAGR_IS", "CAGR_OOS", "DD_OOS", "SR_OOS", "交易"))
        for sid in ids:
            try:
                code, params = fetch_strategy(sid)
            except SystemExit as e:
                print("%-6s %s" % (sid, e)); continue
            imp = subprocess_run_psql_name(sid)
            isr = evaluate(code, params, symbols, args.start, "2024-12-31", "is")["portfolio"]
            oos = evaluate(code, params, symbols, "2025-01-01", args.end, "oos")["portfolio"]
            print("%-6s %-28s %9s %9s %7s %7s %6s" % (
                sid, imp[:28],
                isr.get("cagr", "-"), oos.get("cagr", "-"), oos.get("max_dd", "-"),
                oos.get("sharpe", "-"), oos.get("trades", "-")))
        return 0

    if args.mode == "eval":
        import subprocess, os
        sql = ("select code_content, coalesce(parsed_params::text,'{}') from quant.strategy_configs "
               f"where id={int(args.target)}")
        env = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
        out = subprocess.run(["psql", "-d", "quant_investment", "-At", "-F", "\x1f", "-c", sql],
                             capture_output=True, text=True, env=env, check=True).stdout.strip()
        code, pj = out.split("\x1f")
        raw_params = json.loads(pj or "{}")
        # parsed_params 有两种形态：dict，或 [{"name","type","default","description"}, ...]
        if isinstance(raw_params, list):
            params = {p.get("name"): p.get("default") for p in raw_params if isinstance(p, dict) and p.get("name")}
        elif isinstance(raw_params, dict) and "params" in raw_params:
            params = {p.get("name"): p.get("default") for p in (raw_params["params"] or [])}
        else:
            params = raw_params if isinstance(raw_params, dict) else {}
        label = f"strategy_id={args.target}"
    else:
        code = Path(args.target).read_text(encoding="utf-8")
        params, label = {}, f"file={args.target}"

    symbols = [s for s in args.symbols.split(",") if s]
    if args.split:
        mid = "2024-12-31"
        is_res = evaluate(code, params, symbols, args.start, mid, label + " [样本内]")
        oos_res = evaluate(code, params, symbols, "2025-01-01", args.end, label + " [样本外]")
        print(json.dumps({"label": label, "in_sample": is_res["portfolio"], "out_of_sample": oos_res["portfolio"],
                          "oos_per_symbol": oos_res["per_symbol"]}, ensure_ascii=False, indent=1))
    else:
        res = evaluate(code, params, symbols, args.start, args.end, label)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())