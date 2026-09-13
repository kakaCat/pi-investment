"""策略评估引擎（2026-09-13 w-a9ec14d7 从 scripts/strategy_lab.py + scripts/strategy_core.py 上迁）

为什么上迁：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
评估器是**策略闭环的守门人**（每周 strategy-loop-weekly 要用它判门槛），属生产能力。

为什么必须有一个自己控制的评估器（原脚本的立项理由，保留）：
官方回测（application/services/strategy_backtest_service.run_backtest_from_signals）**不含任何交易成本**，
且每日校验只看 quant.backtest_results 里最近 30 天的证据、阈值 60 分，0 交易的运行直接得 0 分 →
于是"高分策略"既可能虚高（无成本），"0 分策略"也可能是没跑到交易。

本模块口径（刻意保守，任何一条被改都必须同步改文档与门槛）：
  1. 信号在 T 日收盘产生 → **T+1 开盘成交**（不用当日收盘，避免未来函数）；
  2. **T+1 制度**天然满足（买入次日才可卖）；
  3. 成本：买入 佣金 2.5bp + 滑点 5bp；卖出 佣金 2.5bp + 印花 5bp + 滑点 5bp（约 0.15%/回合）；
  4. 满仓单标的、不加杠杆、不择时加减仓（除策略信号外）；
  5. 篮子模式：多标的各自跑，再等权合成；同时看单标的离散度（防"一只票的运气"）；
  6. **超额口径**：判据一律相对"同池等权买入持有"（同标的、同窗口、同时间轴），
     不是绝对收益 —— 本市场同池等权基准本身 CAGR 就有 +23%，绝对阈值会被 beta 轻易通过。

两类能力：
  · evaluate(...)          单标的信号型策略评估（T+1 开盘、含成本、篮子等权 + 基准超额）
  · overlay_evidence(...)  组合层"等权 core + 风控叠层"证据（波动目标 / 回撤闸门），落盘 JSON
"""
from __future__ import annotations

import statistics
from datetime import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd

# ⚠️ 路径基准：本文件在 application/services/ 下，parents[2] 才是 quantsys-v2/
# （从 scripts/ 上迁时用 parents[1] 会把产物写到 application/config/ 而消费端读 quantsys-v2/config/
#   —— 静默读到旧文件。2026-09-13 core_plan 上迁时实测踩到，见 core_plan_service.py 注释。）
ROOT = Path(__file__).resolve().parents[2]

COST_BUY_BP = 2.5 + 5.0            # 佣金 + 滑点（bp）
COST_SELL_BP = 2.5 + 5.0 + 5.0     # 佣金 + 印花 + 滑点（bp）
COST_ROUND_TRIP_BP = COST_BUY_BP + COST_SELL_BP   # 单边费用（叠层换手用）
BASKET = ["600519", "000858", "601318", "600036", "000333", "600276",
          "002415", "600887", "601857", "600030", "000001", "601888"]

# 2026-09-13（w-a9ec14d7）：窗口收敛到**数据完整覆盖**的区间。
# 实证：quant.daily_klines 2021/2022/2023 分别只有 270/291/300 只标的具备 220+ 根日线，
# 而 2024 年 5023 只、2025 年 5353 只 —— 跨 2023/2024 的回测在混合两个不同的 universe，
# 结论会被污染。故只用 2024-07 起（覆盖完整、universe 稳定）的两段，各约一年。
DEFINE_START, DEFINE_END = "2024-01-01", "2024-06-30"   # 流动性候选集定义期
WINDOWS = [("2024-07-01", "2025-06-30"), ("2025-07-01", "2026-09-11")]
OVERLAY_TEST_WINDOW = ("2024-07-01", "2026-09-11")


# --------------------------------------------------------------------------- #
# DB 访问：统一走 engine（原脚本用 psql subprocess，上迁时一并收口）
# --------------------------------------------------------------------------- #
def _engine():
    from infrastructure.persistence.database.engine import get_engine
    return get_engine()


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    """只读查询 → DataFrame。参数一律用绑定变量（不要拼字符串）。"""
    from sqlalchemy import text
    with _engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def query_rows(sql: str, params: dict | None = None) -> list:
    from sqlalchemy import text
    with _engine().connect() as conn:
        return list(conn.execute(text(sql), params or {}).fetchall())


# --------------------------------------------------------------------------- #
# 单标的信号型策略评估
# --------------------------------------------------------------------------- #
def load_klines(symbol: str, start: str, end: str) -> pd.DataFrame:
    """从 quant.daily_klines 取日线（前复权口径以库内为准）。走 IKlineRepository 端口，与线上同源。"""
    from domain.ports import IKlineRepository
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    repo = EnhancedServiceFactory.resolve(IKlineRepository)
    df = repo.get_daily_klines(symbol, start_date=start, end_date=end)
    if df is None:
        return pd.DataFrame()
    try:
        import polars as pl
        pdf = df.to_pandas() if isinstance(df, pl.DataFrame) else pd.DataFrame(df)
    except ImportError:  # pragma: no cover - polars 是硬依赖，仅为防御
        pdf = pd.DataFrame(df)
    if pdf.empty or "close" not in pdf.columns:
        return pd.DataFrame()
    pdf["trade_date"] = pd.to_datetime(pdf["trade_date"])
    return pdf.sort_values("trade_date").reset_index(drop=True)


def run_snippet(code: str, df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """按框架约定执行策略代码：命名空间给 df / params / pd / np，返回带 buy/sell 列的 df。

    策略代码本来就来自库里的 code_content（与官方回测同源），故 exec 是既定契约。
    """
    ns = {"pd": pd, "np": np, "df": df.copy(), "params": dict(params or {})}
    exec(compile(code, "<strategy>", "exec"), ns)  # noqa: S102
    out = ns.get("df")
    if out is None or len(out) != len(df):
        raise ValueError("策略未返回与输入等长的 df")
    return out


def extract_signals(sig: pd.DataFrame) -> pd.DataFrame:
    """兼容 buy/sell 与 buy_tierN/sell_tierN 两种列约定 → 统一为 buy/sell 布尔列。"""
    s = pd.DataFrame(index=sig.index)
    if "buy" in sig.columns and "sell" in sig.columns:
        s["buy"] = sig["buy"].fillna(False).astype(bool)
        s["sell"] = sig["sell"].fillna(False).astype(bool)
        return s
    buy = pd.Series(False, index=sig.index)
    sell = pd.Series(False, index=sig.index)
    for t in (1, 2, 3):
        bc, sc = f"buy_tier{t}", f"sell_tier{t}"
        if bc in sig.columns:
            buy = buy | sig[bc].fillna(False).astype(bool)
        if sc in sig.columns:
            sell = sell | sig[sc].fillna(False).astype(bool)
    s["buy"], s["sell"] = buy, sell
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
                           "days": i - (entry_idx if entry_idx is not None else i)})
            shares, entry_price = 0.0, None
        pending = None
        if i + 1 < len(df):
            b, s = bool(sig["buy"].iloc[i]), bool(sig["sell"].iloc[i])
            if b and shares == 0.0:
                pending = "buy"
            elif s and shares > 0.0:
                pending = "sell"
        equity.append(cash + shares * c)
    return pd.Series(equity, index=df["trade_date"]), trades


def perf_metrics(eq: pd.Series, trades: list, min_trades: int = 3) -> dict:
    """净值曲线 + 交易明细 → 收益/回撤/夏普/交易统计。"""
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
    """篮子评估：每只标的各自 T+1 开盘含成本回测，再等权合成；同时算**同池等权买入持有**基准超额。"""
    rows, curves = [], []
    bh_by_symbol = {}
    for sym in symbols:
        df = load_klines(sym, start, end)
        if len(df) < 60:
            continue
        c = df["close"].astype(float)
        # 注意：df["close"] 的索引是整数 RangeIndex，必须重建为 trade_date 索引，
        # 否则后面 reindex(common)（datetime 索引）会全 NaN → dropna 把整段基准丢光（2026-09-13 实测踩到）
        bh_by_symbol[sym] = pd.Series((c / float(c.iloc[0])).to_numpy(), index=df["trade_date"])
        try:
            sig = extract_signals(run_snippet(code, df, params))
        except Exception as e:  # noqa: BLE001
            rows.append({"symbol": sym, "ok": False, "reason": f"策略执行失败: {str(e)[:60]}"})
            continue
        eq, trades = simulate(df, sig)
        m = perf_metrics(eq, trades)
        m["symbol"] = sym
        rows.append(m)
        if m.get("ok"):
            curves.append(eq / eq.iloc[0])
    ok = [r for r in rows if r.get("ok")]
    agg: dict = {}
    if curves:
        common = curves[0].index
        for c in curves[1:]:
            common = common.intersection(c.index)
        mat = pd.concat([c.reindex(common) for c in curves], axis=1).dropna()
        port = mat.mean(axis=1)
        total_trades = sum(int(r.get("trades") or 0) for r in ok)
        agg = perf_metrics(port, [], min_trades=0)
        agg["trades"] = total_trades
        agg["trades_median_per_symbol"] = int(statistics.median([r.get("trades") or 0 for r in ok])) if ok else 0
        agg["n_symbols"] = mat.shape[1]
        cagrs = [r["cagr"] for r in ok]
        agg["cagr_median"] = round(statistics.median(cagrs), 4)
        agg["cagr_best"] = round(max(cagrs), 4)
        agg["cagr_worst"] = round(min(cagrs), 4)
        agg["pct_positive_symbols"] = round(sum(1 for c in cagrs if c > 0) / len(cagrs), 3)

        # 基准与超额：同一批标的、同一窗口的**等权买入持有**。
        # 单标的择时策略的天然对照是"不择时地拿着同样的票"；跨截面策略则是同池等权。
        bh_curves = [bh_by_symbol[r["symbol"]] for r in ok if r["symbol"] in bh_by_symbol]
        if bh_curves:
            matb = pd.concat([c.reindex(common) for c in bh_curves], axis=1).dropna()
            if matb.shape[1] and len(matb) >= 30:
                mb = perf_metrics(matb.mean(axis=1), [], min_trades=0)
                if mb.get("ok"):
                    agg["benchmark_cagr"] = mb["cagr"]
                    agg["benchmark_max_dd"] = mb["max_dd"]
                    agg["benchmark_sharpe"] = mb["sharpe"]
                    agg["excess_cagr"] = round(float(agg["cagr"]) - float(mb["cagr"]), 4)
                    agg["excess_sharpe"] = round(float(agg["sharpe"]) - float(mb["sharpe"]), 2)
                    agg["benchmark_note"] = "同池等权买入持有（同一批标的、同一窗口、同一时间轴）"
    return {"label": label, "period": f"{start}~{end}", "portfolio": agg, "per_symbol": rows}


# --------------------------------------------------------------------------- #
# 策略源码获取（原为 psql subprocess，上迁时收口到 engine）
# --------------------------------------------------------------------------- #
def parse_params(raw) -> dict:
    """parsed_params 有两种形态：dict，或 [{"name","type","default","description"}, ...]。"""
    if isinstance(raw, list):
        return {p.get("name"): p.get("default") for p in raw if isinstance(p, dict) and p.get("name")}
    if isinstance(raw, dict) and "params" in raw:
        return {p.get("name"): p.get("default") for p in (raw["params"] or [])}
    return raw if isinstance(raw, dict) else {}


def fetch_strategy(sid: int):
    """按 id 取策略源码与参数。找不到时抛错（不返回空壳冒充成功）。"""
    import json as _json
    rows = query_rows(
        "select code_content, coalesce(parsed_params::text,'{}') "
        "from quant.strategy_configs where id = :sid", {"sid": int(sid)})
    if not rows:
        raise LookupError(f"策略 {sid} 不存在")
    return rows[0][0], parse_params(_json.loads(rows[0][1] or "{}"))


def strategy_name(sid: int) -> str:
    rows = query_rows("select strategy_name from quant.strategy_configs where id = :sid", {"sid": int(sid)})
    return (rows[0][0] if rows and rows[0][0] else f"strategy_{int(sid)}")


# --------------------------------------------------------------------------- #
# 组合层：等权 core + 风控叠层证据
# --------------------------------------------------------------------------- #
def core_returns(cand: int = 800, min_bars: int = 100) -> pd.Series:
    """等权 core 日收益序列（候选集 = 定义期流动性 Top N）。"""
    syms = [r[0].strip().zfill(6) for r in query_rows(
        "select symbol from (select symbol, avg(amount) a, count(*) c from quant.daily_klines "
        "where trade_date between :s and :e group by symbol having count(*) >= :mb) t "
        "where a is not null order by a desc limit :n",
        {"s": DEFINE_START, "e": DEFINE_END, "mb": min_bars, "n": int(cand)}) if r[0] and r[0].strip()]
    if not syms:
        raise RuntimeError("core 候选集为空：检查 quant.daily_klines 定义期数据")
    df = query_df(
        "select symbol, trade_date, close from quant.daily_klines "
        "where symbol = any(:syms) and trade_date >= :s order by trade_date",
        {"syms": syms, "s": "2024-06-01"})
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    close = df.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
    return close.pct_change().mean(axis=1).dropna()


def curve_stats(r: pd.Series, turnover: float = 0.0) -> dict:
    eq = (1 + r).cumprod()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.0
    dd = float((eq / eq.cummax() - 1).min())
    sharpe = float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0
    cagr = float(eq.iloc[-1] ** (1 / max(yrs, .1)) - 1)
    return {"cagr": round(cagr, 4), "dd": round(dd, 4), "sharpe": round(sharpe, 2),
            "turnover": round(turnover, 4)}


def overlay_evidence(target_vol: float = 0.15, cand: int = 800,
                     dd_trigger: float = 0.10, dd_restore: float = 0.05,
                     write: bool = True) -> dict:
    """组合层覆盖证据：等权 core 基线 vs 波动目标(A) / 回撤闸门(B) / A+B(C)。

    为什么单独落盘：core 是**组合层覆盖**（调暴露，不选股），评估器与单标的信号框架不同源，
    证据必须显式带着"窗口/universe/口径"走，不能靠人记（R-013）。
    """
    import json as _json
    core_all = core_returns(cand)
    s, e = OVERLAY_TEST_WINDOW
    core = core_all[(core_all.index >= pd.Timestamp(s)) & (core_all.index <= pd.Timestamp(e))]
    if len(core) < 60:
        raise RuntimeError("overlay 窗口样本不足：%d 个交易日" % len(core))
    cost = COST_ROUND_TRIP_BP / 10000.0
    res = {"baseline": curve_stats(core)}

    # A. 波动率目标化（月度调整暴露）
    vol20 = core_all.rolling(20).std() * np.sqrt(252)
    w = pd.Series(1.0, index=core.index)
    cur, cost_a, prev_key = 1.0, 0.0, None
    for d in core.index:
        k = (d.year, d.month)
        if k != prev_key:
            v = vol20.get(d, np.nan)
            if pd.notna(v) and v > 0:
                new = float(min(1.0, target_vol / v))
                cost_a += abs(new - cur) * cost
                cur = new
            prev_key = k
        w[d] = cur
    res["overlay_a"] = curve_stats(core * w, turnover=cost_a)

    # B. 回撤闸门
    eq = (1 + core).cumprod()
    dd = eq / eq.cummax() - 1
    expo = pd.Series(1.0, index=core.index)
    cur, cost_b = 1.0, 0.0
    for d in core.index:
        if cur == 1.0 and dd[d] < -dd_trigger:
            cost_b += abs(0.5 - cur) * cost
            cur = 0.5
        elif cur == 0.5 and dd[d] > -dd_restore:
            cost_b += abs(1.0 - cur) * cost
            cur = 1.0
        expo[d] = cur
    res["overlay_b"] = curve_stats(core * expo, turnover=cost_b)

    # C. A+B
    res["overlay_c"] = curve_stats(core * w * expo, turnover=cost_a + cost_b)

    base, ov = res["baseline"], res["overlay_c"]
    ev = {
        "name": "core-overlay-v1",
        "generated_at": _dt.now().isoformat(timespec="seconds"),
        "kind": "overlay",
        "window": s + "~" + e,
        "universe": "等权 core（流动性 Top %d，2024H1 定义的最活跃池）" % cand,
        "params": {"target_vol": target_vol, "dd_trigger": dd_trigger, "dd_restore": dd_restore},
        "baseline": base,
        "overlay": ov,
        "excess": {"cagr": round(ov["cagr"] - base["cagr"], 4),
                   "sharpe": round(ov["sharpe"] - base["sharpe"], 2),
                   "dd_improvement": round(ov["dd"] - base["dd"], 4)},
        "cost_note": "A/B 叠层各含一次月度/触发换手成本（单边 %.2f%%）" % (COST_ROUND_TRIP_BP / 100.0),
        "why_not_alpha_gate": "覆盖层用收益换风险（超额 CAGR 为负、Sharpe 与回撤改善），"
                              "用 alpha 门槛判它会被误杀——故单列 overlay 门槛",
        "all_variants": {k: v for k, v in res.items()},
    }
    if write:
        out = ROOT / "config" / "core_overlay_evidence.json"
        out.write_text(_json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
        ev["evidence_file"] = str(out)
    return ev
