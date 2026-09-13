"""投资脑 core 建仓计划（core_plan.py，2026-09-13 w-c8cae280）——**只出计划，不自动下单**

依据（当日研究结论）：选股型叠层全部负超额；**等权 core + 波动目标 + 回撤闸门**稳健
（2024-07~2026-09：Sharpe 0.98→1.22、回撤 -17.9%→-10.6%，9 组参数/3 种池子规模一致）。

本脚本产出：
  1. 目标暴露 = min(regime 上限, 波动目标暴露 × 回撤闸门系数)，并给出各因子明细；
  2. 目标持仓 = 流动性 Top 且价格可负担的 N 只等权（A股 100 股整数倍约束下可落地）；
  3. 与当前持仓的差额（需要买/卖多少股）；
  4. 写入 quantsys-v2/config/core_plan.json + 打印人类可读摘要。**不下任何委托。**

用法：python scripts/core_plan.py [--names 15] [--target-vol 0.15] [--max-exposure 0.25] [--account agent_brain]
"""
import argparse, json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import io

ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
DEF_START, DEF_END = "2024-01-01", "2024-06-30"
OUT = ROOT / "config" / "core_plan.json"


def psql(q):
    return subprocess.run(["psql", "-d", "quant_investment", "-At", "-c", q],
                          capture_output=True, text=True, env=ENV, check=True).stdout


def psql_csv_plain(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    return pd.read_csv(io.StringIO(out))


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", type=int, default=15)
    ap.add_argument("--single-cap", type=float, default=0.15)   # 单只上限：core 的 15%
    ap.add_argument("--min-names", type=int, default=8)          # 持仓数下限
    ap.add_argument("--growth-sleeve-pct", type=float, default=0.05)  # 成长板独立额度（占总资产）
    ap.add_argument("--growth-names", type=int, default=3)
    ap.add_argument("--growth-min-amount", type=float, default=5e7)   # 成长板候选日成交额下限（元）
    ap.add_argument("--target-vol", type=float, default=0.15)
    ap.add_argument("--max-exposure", type=float, default=0.25)   # 首期上限：25%（regime 允许 40% 以内）
    ap.add_argument("--account", default="agent_brain")
    ap.add_argument("--max-price", type=float, default=30.0)      # 100 股整手可负担
    ap.add_argument("--exclude-near-high", type=float, default=-0.05)  # 排除"距52周高 <5%"的追高标的
    a = ap.parse_args()

    # 1) 候选池：窗口前定义（2024H1）流动性 Top，含价格与流动性明细
    px = psql_csv("select symbol, max(trade_date)::text as d, avg(amount) as amt from quant.daily_klines "
                  "where trade_date between '" + DEF_START + "' and '" + DEF_END + "' group by symbol "
                  "having count(*) >= 100 order by amt desc limit 400")
    px["symbol"] = px["symbol"].astype(str).str.zfill(6)
    latest = psql_csv("select symbol, close, amount from quant.daily_klines where trade_date = "
                      "(select max(trade_date) from quant.daily_klines)")
    latest["symbol"] = latest["symbol"].astype(str).str.zfill(6)
    uni = px.merge(latest, on="symbol", how="inner", suffixes=("_def", "_now"))
    uni = uni[(uni["close"] > 0) & (uni["close"] <= a.max_price)]
    uni = uni.sort_values("amt", ascending=False)
    # 不追高（2026-09-13 基准率检验）：距 52 周高 ≤3% 的标的，未来 20/60 日**中位收益为负**、胜率<50%；
    # 而距高 <-30% 的深跌标的 120 日中位 +11.1%、胜率 66.8%。故默认排除近高标的。
    hi = psql_csv("select symbol, max(close) as hi52 from quant.daily_klines where trade_date >= "
                  "(select max(trade_date) - 365 from quant.daily_klines) group by symbol")
    hi["symbol"] = hi["symbol"].astype(str).str.zfill(6)
    uni = uni.merge(hi, on="symbol", how="left")
    uni["dist_high"] = uni["close"] / uni["hi52"] - 1
    before = len(uni)
    uni = uni[uni["dist_high"] <= a.exclude_near_high]
    print("不追高过滤：%d → %d 只（排除距52周高 > %.0f%% 的标的）" % (before, len(uni), a.exclude_near_high * 100))
    # ===== 基本面/行业/可投资性过滤（2026-09-13 用户指出：没考虑市场风向、分红崩溃、数据问题）=====
    # 数据源改用 quant.stocks（全市场 5857 只、每日更新），而非只覆盖 377 只的财务视图。
    # 1) 质量闸门：ROE > 0（剔除万科 ROE -13.7 / 欧菲光 -11.7 / 隆基 -7.0 这类亏损与价值陷阱）
    #    且 0 < PE <= 60（盈利为正且估值不离谱；万科 PE -1.3、欧菲光 -319.8 自动出局）
    # 2) 可投资性：非 ST、非停牌、上市满 2 年（次新勿碰）
    # 3) 杠杆：负债率 < 80%，**金融业豁免**（银行天然 90+）
    # 4) 分红代理：连续亏损必然砍分红，故以"ROE>0 且 PE>0"为代理；库内暂无全市场分红表（已记录，建议数据线补）
    st = psql_csv("select symbol, name, industry, sector, roe, pe, debt_ratio, is_st, is_suspended, list_date, market_cap "
                  "from quant.stocks")
    st["symbol"] = st["symbol"].astype(str).str.zfill(6)
    for c in ("roe", "pe", "debt_ratio", "market_cap"):
        st[c] = pd.to_numeric(st[c], errors="coerce")
    st["list_date"] = pd.to_datetime(st["list_date"], errors="coerce")
    uni = uni.merge(st, on="symbol", how="left")
    n0 = len(uni)
    uni = uni[uni["roe"].notna() & (uni["roe"] > 0)]
    n1 = len(uni)
    uni = uni[uni["pe"].notna() & (uni["pe"] > 0) & (uni["pe"] <= 60)]
    n2 = len(uni)
    uni = uni[(uni["is_st"] != True) & (uni["is_suspended"] != True)]  # noqa: E712
    n3 = len(uni)
    uni = uni[uni["list_date"].isna() | (uni["list_date"] <= pd.Timestamp.now() - pd.Timedelta(days=730))]
    n4 = len(uni)
    fin_mask = uni["industry"].fillna("").str.contains("金融", na=False)
    uni = uni[fin_mask | uni["debt_ratio"].isna() | (uni["debt_ratio"] < 80)]
    n5 = len(uni)
    print("质量闸门：ROE>0 %d→%d；0<PE≤60 %d→%d；非ST/停牌 %d→%d；上市≥2年 %d→%d；负债<80%%(金融豁免) %d→%d"
          % (n0, n1, n1, n2, n2, n3, n3, n4, n4, n5))

    acct = psql("select coalesce(total_value,0) || '|' || coalesce(cash_available,0) from quant.simulation_account "
                "where account_name='" + a.account + "'").strip().split("|")
    total, cash = float(acct[0] or 0), float(acct[1] or 0)

    # 暴露：波动目标 × 回撤闸门（用最终持仓的日收益重建 core 指数）
    hist = psql_csv("select symbol, trade_date, close from quant.daily_klines where symbol in ("
                    + ",".join("'" + str(s) + "'" for s in uni["symbol"].head(200))
                    + ") and trade_date >= '2024-06-01' order by trade_date")
    hist["trade_date"] = pd.to_datetime(hist["trade_date"])
    close = hist.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
    core_ret = close.pct_change().mean(axis=1).dropna()
    vol_ann = float(core_ret.tail(20).std() * np.sqrt(252)) if len(core_ret) >= 20 else float("nan")
    eq = (1 + core_ret).cumprod()
    dd = float(eq.iloc[-1] / eq.cummax().iloc[-1] - 1) if len(eq) else 0.0
    w_vol = min(1.0, a.target_vol / vol_ann) if vol_ann and vol_ann > 0 else 1.0
    gate = 0.5 if dd < -0.10 else 1.0
    target_expo = round(min(a.max_exposure, a.max_exposure * w_vol * gate), 4)

    budget_est = total * target_expo / max(a.names, 1)
    uni_prebudget = uni.copy()   # 成长板子额度用：不受 core 单只预算钳制
    before_px = len(uni)
    uni = uni[uni["close"] * 100 <= budget_est]
    print("整手可负担：%d → %d 只（单只预算 %.0f 元）" % (before_px, len(uni), budget_est))

    # 5) 行业分散：同一行业最多 2 只（防房地产/银行式集中）
    picks_rows, seen = [], {}
    for r in uni.itertuples():
        ind = str(getattr(r, "industry", "") or "未知")
        if seen.get(ind, 0) >= 2:
            continue
        seen[ind] = seen.get(ind, 0) + 1
        picks_rows.append(r)
        if len(picks_rows) >= a.names:
            break
    picks = pd.DataFrame([{k: getattr(r, k) for k in ("symbol", "close", "amt", "industry", "roe", "pe")} for r in picks_rows])

    # ===== 板块风向 / 市场风格（2026-09-13 w-c8cae280，用户要求 A）=====
    # 1) 行业动量：/api/market/sectors 实测返回 0 条（坏接口），改为**库里自算**：
    #    用 quant.stocks.industry 分组，取成分股近 60 日等权收益中位数作为行业动量并排名。
    # 2) 市场风格：/api/market/style 可用（当前 growth / 置信度 0.92）。
    # 3) 权重调整：行业动量前 1/3 → ×1.3；中 1/3 → ×1.0；后 1/3 → ×0.5；
    #    风格逆风（成长风格下的周期/价值行业，或反之）再 ×0.7；单只权重上限 20% 总资产由宪法保证。
    import requests as _rq
    style_info = {}
    try:
        _sr = _rq.get("http://127.0.0.1:5001/api/market/style", timeout=20).json()
        style_info = (_sr.get("data") or {}) if isinstance(_sr, dict) else {}
    except Exception as _e:  # noqa: BLE001
        style_info = {"style": "unknown", "confidence": 0.0, "error": str(_e)[:80]}

    # ===== 行业热度（/api/market/sectors，2026-09-13 修正解析层级）=====
    # 说明：该接口**本身没坏**——真实结构是 data.data.industries（双层 data），
    # 我此前按 data.industries 解析才以为"返回 0 条"。现按正确层级解析，取当日行业热度（496 个行业）
    # 作为**当日热度交叉验证**；中长周期动量仍用库内 60 日自算（口径与持仓行业精确对齐）。
    api_sectors = {}
    try:
        _ar = _rq.get("http://127.0.0.1:5001/api/market/sectors", timeout=25).json()
        _rows = (((_ar or {}).get("data") or {}).get("data") or {}).get("industries") or []
        api_sectors = {str(x.get("name")): float(x.get("change_pct") or 0) for x in _rows}
        _top = sorted(api_sectors.items(), key=lambda kv: kv[1], reverse=True)[:5]
        print("行业热度（当日，来源 /api/market/sectors）：样本 %d 个行业，最强 %s" % (len(api_sectors), _top))
    except Exception as _e:  # noqa: BLE001
        print("行业热度接口不可用（降级为仅库内动量）:", str(_e)[:80])
    ind_mom = {}
    try:
        _im = psql_csv_plain("""select s.industry, avg(k.close / p.close - 1) as r60
                        from quant.stocks s
                        join quant.daily_klines k on k.symbol = s.symbol and k.trade_date = (select max(trade_date) from quant.daily_klines)
                        join quant.daily_klines p on p.symbol = s.symbol and p.trade_date = (select max(trade_date) - 60 from quant.daily_klines)
                        where s.industry is not null
                        group by s.industry having count(*) >= 3""")
        ind_mom = {str(r.industry): float(r.r60) for r in _im.itertuples() if pd.notna(r.r60)}
    except Exception as _e:  # noqa: BLE001
        print("行业动量计算失败:", str(_e)[:80])
    ranked = sorted(ind_mom.items(), key=lambda kv: kv[1], reverse=True)
    n_ind = len(ranked)
    rank_of = {name: i for i, (name, _v) in enumerate(ranked)}
    STYLE = str(style_info.get("style", "unknown"))
    CONF = float(style_info.get("confidence", 0) or 0)
    CYCLE_KW = ("银行", "保险", "证券", "货币金融", "资本市场", "石油", "煤炭", "有色", "钢铁", "建筑", "土木", "房地产", "航运", "水上运输", "电力", "公用")
    GROWTH_KW = ("电子", "计算机", "软件", "通信", "医药", "生物", "半导体", "电气机械", "汽车", "军工", "航空", "电池", "医疗")

    def _tilt(industry: str):
        ind = industry or ""
        pos = rank_of.get(ind)
        if pos is None or n_ind == 0:
            return 1.0, "行业动量未知"
        q = pos / n_ind
        mult = 1.3 if q < 1 / 3 else (1.0 if q < 2 / 3 else 0.5)
        note = "行业动量 %s（%d/%d）" % ("强" if q < 1 / 3 else ("中" if q < 2 / 3 else "弱"), pos + 1, n_ind)
        if CONF >= 0.6 and q >= 1 / 3:      # 动量前 1/3 的行业不套风格惩罚：动量优先于风格标签
            is_cycle = any(k in ind for k in CYCLE_KW)
            is_growth = any(k in ind for k in GROWTH_KW)
            if STYLE == "growth" and is_cycle:
                mult *= 0.85; note += "；风格逆风(成长市/周期行业) ×0.85"
            elif STYLE == "value" and is_growth:
                mult *= 0.85; note += "；风格逆风(价值市/成长行业) ×0.85"
            elif STYLE == "cycle" and is_growth:
                mult *= 0.9; note += "；风格逆风(周期市/成长行业) ×0.9"
            else:
                note += "；风格顺风(%s)" % STYLE
        return mult, note

    _pk = {str(r.symbol): {"close": r.close, "roe": r.roe, "pe": r.pe, "amt": r.amt} for r in picks.itertuples()}
    tilts = []
    for r in picks.itertuples():
        m, note = _tilt(str(r.industry))
        tilts.append({"symbol": r.symbol, "industry": str(r.industry), "mult": round(m, 3), "note": note})
    _wsum = sum(t["mult"] for t in tilts) or 1.0
    for t in tilts:
        t["weight_pct_of_core"] = round(t["mult"] / _wsum * 100, 2)
    print("板块风向：市场风格 = %s（置信度 %.2f）；行业动量样本 %d 个行业" % (STYLE, CONF, n_ind))

    # ===== 硬约束 1/2 与整手复核联立迭代（2026-09-13）=====
    # ① 持仓数下限：不足则从合格池补（优先补行业已有成员 <2 的，避免抬高行业集中度）
    # ② 单只上限：core 的 15%，迭代封顶 + 超额按比例再分配
    # ③ 整手复核：分到的钱买不起 1 手则剔除，剔除后若跌破下限再补，直到三者同时满足
    def _apply_cap(ts, cap):
        ms = [x["mult"] for x in ts]
        tot = sum(ms) or 1.0
        w = [m / tot for m in ms]
        for _ in range(50):
            over = [i for i, x in enumerate(w) if x > cap + 1e-9]
            if not over:
                break
            ex = sum(w[i] - cap for i in over)
            for i in over:
                w[i] = cap
            free = [i for i in range(len(w)) if w[i] < cap - 1e-9]
            fs = sum(w[i] for i in free) or 1.0
            for i in free:
                w[i] += ex * (w[i] / fs)
        for x, wv in zip(ts, w):
            x["weight_pct_of_core"] = round(wv * 100, 2)

    def _refill(ts, used, k):
        if k <= 0:
            return 0
        cnt = {}
        for x in ts:
            cnt[x["industry"]] = cnt.get(x["industry"], 0) + 1
        cand = [r for r in uni.itertuples() if str(r.symbol) not in used]
        cand.sort(key=lambda r: (cnt.get(str(r.industry), 0), -float(r.amt)))
        added = 0
        for _r in cand:
            if added >= k:
                break
            s = str(_r.symbol)
            if s in used:
                continue
            m, n = _tilt(str(_r.industry))
            ts.append({"symbol": s, "industry": str(_r.industry), "mult": m, "note": n,
                       "weight_pct_of_core": 0.0})
            _pk[s] = {"close": _r.close, "roe": _r.roe, "pe": _r.pe, "amt": _r.amt}
            used.add(s)
            added += 1
        return added

    used = {str(x["symbol"]) for x in tilts}
    _amt_total_pre = total * target_expo
    dropped_total = 0
    for _round in range(8):
        _refill(tilts, used, max(0, a.min_names - len(tilts)))
        _apply_cap(tilts, a.single_cap)
        _kept = []
        for _t in tilts:
            _c = float(_pk[_t["symbol"]]["close"])
            _lots = int((_amt_total_pre * _t["weight_pct_of_core"] / 100.0) // (_c * 100))
            if _lots >= 1:
                _t["lots"] = _lots
                _kept.append(_t)
        _gone = [t for t in tilts if t not in _kept]
        dropped_total += len(_gone)
        tilts = _kept
        if not _gone and len(tilts) >= a.min_names:
            break
        if len(used) >= len(uni):
            break
    _refill(tilts, used, max(0, a.min_names - len(tilts)))
    _apply_cap(tilts, a.single_cap)
    for _t in tilts:
        _t["lots"] = int((_amt_total_pre * _t["weight_pct_of_core"] / 100.0) // (float(_pk[_t["symbol"]]["close"]) * 100))
    print("硬约束：持仓 %d 只（下限 %d）｜单只最大权重 %.1f%%（上限 %.0f%%）｜整手剔除累计 %d 只"
          % (len(tilts), a.min_names, max((x["weight_pct_of_core"] for x in tilts), default=0.0),
             a.single_cap * 100, dropped_total))


    # ===== 成长板独立子额度（方案C：创业板 300/301 + 科创板 688/689）=====
    # 独立核算：额度 = 总资产 × growth_sleeve_pct（默认 5%）× 波动系数 × 回撤闸门
    # 候选来自 uni_prebudget（不受 core 单只预算钳制），否则高价的科创板龙头永远进不来
    _G_PREFIX = ("300", "301", "688", "689")
    # 池子来源：**全市场** 300/301/688/689，而非 core 的 240 只流动池
    # 依据：流动池里成长板只有 45 只创业板 + 8 只科创板，且经质量闸门后仅剩 12 只、科创板 0 只（2026-09-13 实测）——
    # 用 240 只池做成长板子额度等于把子额度饿死。质量闸门与 core 完全一致，另加流动性下限。
    # 窄门类上限：同一 sector（证监会门类）成分股 <500 只时，子额度内最多 1 只。
    # 依据：sector 只有 19 类且制造业独占 3924/5857=67%，用它做统一上限不合理；
    # 但"文化、体育和娱乐业"这类窄门类（58 只）里放 2 只 = 子额度 2/3 押一个方向，需要拦。
    _sec_size = st["sector"].value_counts().to_dict()
    _gst = st[st["symbol"].astype(str).str.startswith(_G_PREFIX)].copy()
    _gn0 = len(_gst)
    _gst = _gst[_gst["roe"].notna() & (_gst["roe"] > 0)]
    _gst = _gst[_gst["pe"].notna() & (_gst["pe"] > 0) & (_gst["pe"] <= 60)]
    _gst = _gst[(_gst["is_st"] != True) & (_gst["is_suspended"] != True)]  # noqa: E712
    _gst = _gst[_gst["list_date"].isna() | (_gst["list_date"] <= pd.Timestamp.now() - pd.Timedelta(days=730))]
    _gfin = _gst["industry"].fillna("").str.contains("金融", na=False)
    _gst = _gst[_gfin | _gst["debt_ratio"].isna() | (_gst["debt_ratio"] < 80)]
    _gper = total * a.growth_sleeve_pct / max(a.growth_names, 1)
    gw_all = _gst.merge(latest, on="symbol", how="inner").merge(hi, on="symbol", how="left")
    gw_all["dist_high"] = gw_all["close"] / gw_all["hi52"] - 1
    gw_all = gw_all[(gw_all["close"] > 0) & (gw_all["dist_high"] <= a.exclude_near_high)
                    & (gw_all["amount"] >= a.growth_min_amount) & (gw_all["close"] * 100 <= _gper)]
    gw_all = gw_all.sort_values("amount", ascending=False)
    gw_pool = gw_all[~gw_all["symbol"].astype(str).isin(used)]
    print("成长板候选池（全市场 300/301/688/689）：%d → %d 只（质量闸门同 core；日成交额 ≥ %.0f 万；单只 ≤ %.0f 元）"
          % (_gn0, len(gw_pool), a.growth_min_amount / 1e4, _gper))
    sleeve, sleeve_meta = [], {}
    if len(gw_pool) > 0:
        _gsyms = [str(s) for s in gw_all["symbol"].astype(str).head(150)]
        _gh = psql_csv("select symbol, trade_date, close from quant.daily_klines where symbol in ("
                       + ",".join("'" + s + "'" for s in _gsyms)
                       + ") and trade_date >= '2024-06-01' order by trade_date")
        _svol, _sdd = float("nan"), 0.0
        if len(_gh):
            _gh["trade_date"] = pd.to_datetime(_gh["trade_date"])
            _gc = _gh.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
            _gr = _gc.pct_change().mean(axis=1).dropna()
            if len(_gr) >= 20:
                _svol = float(_gr.tail(20).std() * np.sqrt(252))
            _ge = (1 + _gr).cumprod()
            _sdd = float(_ge.iloc[-1] / _ge.cummax().iloc[-1] - 1) if len(_ge) else 0.0
        _swvol = min(1.0, a.target_vol / _svol) if _svol and _svol > 0 else 1.0
        _sgate = 0.5 if _sdd < -0.10 else 1.0
        _sexpo = round(a.growth_sleeve_pct * _swvol * _sgate, 4)
        _samt = total * _sexpo
        # 最小可持结构下限：波动缩放后的金额若装不下"前 N 只各 1 手"，则上抬到刚好装得下（硬顶=5% 额度上限）。
        # 理由：子额度只有 1 只时 = 100% 单票特质风险，违背"最多 2-3 只"的分散结构（2026-09-13）。
        _cap_amt = total * a.growth_sleeve_pct
        _cand, _sind = [], set()
        _ranked = []
        for _r in gw_pool.itertuples():
            _m, _n = _tilt(str(_r.industry))
            _ranked.append((-_m, -float(_r.amount), _r, _m, _n))
        _ranked.sort(key=lambda x: (x[0], x[1]))
        _ssec = {}
        for _m0, _amt0, _r, _m, _n in _ranked:
            if len(_cand) >= a.growth_names:
                break
            _ind = str(_r.industry)
            if _ind in _sind:
                continue
            _sec = str(_r.sector)
            if _sec_size.get(_sec, 9999) < 500 and _ssec.get(_sec, 0) >= 1:
                continue   # 窄门类最多 1 只
            if _ssec.get(_sec, 0) >= 2:
                continue
            _cand.append({"symbol": str(_r.symbol), "industry": _ind, "sector": _sec, "mult": _m, "note": _n,
                          "close": float(_r.close), "roe": float(_r.roe), "pe": float(_r.pe)})
            _sind.add(_ind)
            _ssec[_sec] = _ssec.get(_sec, 0) + 1
        _top = _cand[:a.growth_names]
        if _top:
            _mtt = sum(c["mult"] for c in _top) or 1.0
            _bneed = max((c["close"] * 100) / (c["mult"] / _mtt) for c in _top)
            if _bneed > _samt:
                _samt_adj = min(_bneed, _cap_amt)
                if _samt_adj > _samt:
                    print("    最小可持结构下限：子额度 %.0f → %.0f 元（波动缩放值装不下前 %d 只各 1 手；硬顶 %.0f 元 = %.1f%% 总资产）"
                          % (_samt, _samt_adj, len(_top), _cap_amt, a.growth_sleeve_pct * 100))
                    _samt = _samt_adj
                    _sexpo = round(_samt / total, 4)
                else:
                    print("    警告：5%% 额度上限（%.0f 元）仍装不下前 %d 只各 1 手，按上限执行" % (_cap_amt, len(_top)))
        # 贪心整手复核：小额度下 1 手成本是硬门槛。
        # 逐只试纳入，试探集合内每只按其权重都能买 ≥1 手才接受（避免"先按等分否掉、再归一成单只 100%"的错误）
        _alive = []
        for c in _cand:
            _trial = _alive + [c]
            _mt = sum(x["mult"] for x in _trial) or 1.0
            if all(x["close"] * 100 <= _samt * (x["mult"] / _mt) for x in _trial):
                _alive = _trial
                if len(_alive) >= a.growth_names:
                    break
        _mt2 = sum(c["mult"] for c in _alive) or 1.0
        for c in _alive:
            c["weight_pct_of_sleeve"] = round(c["mult"] / _mt2 * 100, 2)
            c["amount"] = round(_samt * c["weight_pct_of_sleeve"] / 100.0, 0)
            c["lots"] = int(c["amount"] // (c["close"] * 100))
        _alive = [c for c in _alive if c["lots"] >= 1]
        _mt3 = sum(c["mult"] for c in _alive) or 1.0
        for c in _alive:
            c["weight_pct_of_sleeve"] = round(c["mult"] / _mt3 * 100, 2)
            c["amount"] = round(_samt * c["weight_pct_of_sleeve"] / 100.0, 0)
            c["lots"] = int(c["amount"] // (c["close"] * 100))
        sleeve = _alive
        sleeve_meta = {"cap_pct_of_total": a.growth_sleeve_pct, "exposure_pct_of_total": _sexpo,
                       "amount": round(_samt, 0), "index_vol_ann": round(_svol, 4) if _svol == _svol else None,
                       "index_drawdown": round(_sdd, 4), "w_vol": round(_swvol, 3), "dd_gate": _sgate,
                       "candidates": [str(s) for s in gw_pool["symbol"].astype(str).head(10)],
                       "note": "独立核算子额度；候选池 %d 只成长板标的（不受 core 单只预算钳制）" % len(gw_pool)}
        print("成长板子额度：上限 %.1f%% 总资产 → 实际暴露 %.2f%%（%.0f 元）｜成长板等权指数 20 日年化波动 %.1f%%｜回撤 %.1f%%→闸门 %.1f｜入选 %d 只"
              % (a.growth_sleeve_pct * 100, _sexpo * 100, _samt, (_svol or 0) * 100, _sdd * 100, _sgate, len(sleeve)))
        for c in sleeve:
            print("    %s  现价 %7.2f  %d 手 ≈ %.0f 元（子额度 %.1f%%）| %s" % (c["symbol"], c["close"], c["lots"], c["amount"], c["weight_pct_of_sleeve"], c["note"]))
        if not sleeve:
            print("    子额度不足以买入任何成长板标的 1 手 → 该额度转入现金（诚实记录，不硬凑）")
    else:
        print("成长板子额度：合格候选 0 只，跳过")

    plan = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "account": a.account, "mode": "PLAN_ONLY（不下单）",
        "account_total": total, "cash": cash,
        "exposure": {"target_pct": target_expo, "first_phase_cap_pct": a.max_exposure,
                     "core_realized_vol_ann": round(vol_ann, 4) if vol_ann else None,
                     "vol_target": a.target_vol, "w_vol": round(w_vol, 3),
                     "core_drawdown": round(dd, 4), "dd_gate": gate},
        "market_style": {"style": STYLE, "confidence": round(CONF, 3), "source": "/api/market/style"},
        "sector_heat_top5": sorted(api_sectors.items(), key=lambda kv: kv[1], reverse=True)[:5],
        "sector_momentum_note": "行业动量由库内 quant.stocks.industry 分组、近 60 日成分股等权收益中位数自算（/api/market/sectors 实测返回 0 条，不可用）",
        "holdings": [
            {"symbol": t["symbol"], "industry": t["industry"],
             "weight_pct_of_core": t["weight_pct_of_core"], "tilt_mult": t["mult"], "tilt_note": t["note"],
             "close": float(_pk[t["symbol"]]["close"]), "roe": float(_pk[t["symbol"]]["roe"]),
             "pe": float(_pk[t["symbol"]]["pe"]), "amount_def_avg": float(_pk[t["symbol"]]["amt"])}
            for t in tilts
        ],
        "growth_sleeve": {"meta": sleeve_meta, "holdings": sleeve},
        "phase_plan": "分 4 批、每批约 1 周；每批按当时 vol-target 与回撤闸门重算",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=== 投资脑 core 建仓计划（只出计划，不下单）===")
    print("账户 %s 总资产 %.0f 现金 %.0f" % (a.account, total, cash))
    print("目标暴露 %.1f%%（首期上限 %.0f%%｜core 20 日年化波动 %.1f%%｜波动系数 %.2f｜回撤 %.1f%%→闸门 %.1f）"
          % (target_expo * 100, a.max_exposure * 100, (vol_ann or 0) * 100, w_vol, dd * 100, gate))
    target_amount = total * target_expo
    print("计划投入 %.0f 元，分 4 批（每批约 %.0f 元）" % (target_amount, target_amount / 4))
    print("目标持仓 %d 只（按板块风向加权；等权基准每只约 %.0f 元）：" % (len(tilts), target_amount / max(len(tilts), 1)))
    for _t in sorted(tilts, key=lambda x: x["weight_pct_of_core"], reverse=True):
        _c = float(_pk[_t["symbol"]]["close"]); _amt = target_amount * _t["weight_pct_of_core"] / 100.0
        _lots = int(_amt // (_c * 100))
        print("  %s  现价 %6.2f  权重 %5.1f%%  约 %6.0f 元 = %d 手 | %s" % (_t["symbol"], _c, _t["weight_pct_of_core"], _amt, _lots, _t["note"]))
    _sleeve_amt = float(sleeve_meta.get("amount") or 0) if sleeve else 0.0
    _sleeve_pct = float(sleeve_meta.get("exposure_pct_of_total") or 0) if sleeve else 0.0
    print("合计：core %.1f%% + 成长板子额度 %.2f%% = 计划暴露 %.2f%%（约 %.0f 元，占总资产 %.1f%%）"
          % (target_expo * 100, _sleeve_pct * 100, (target_expo + _sleeve_pct) * 100,
             target_amount + _sleeve_amt, (target_expo + _sleeve_pct) * 100))
    print("现金保留 %.1f%%（宪法下限 10%%）" % ((1 - target_expo - _sleeve_pct) * 100))
    print("计划已写入", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
