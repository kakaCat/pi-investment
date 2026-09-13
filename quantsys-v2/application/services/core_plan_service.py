"""投资脑 core 建仓计划服务（2026-09-13 w-a9ec14d7 从 scripts/core_plan.py 上迁）

为什么上迁：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
本文件原先在 scripts/core_plan.py，但它是**账户建仓决策的入口**（工作日 09:05 例行任务 core_plan_generate 生成、09:10 由 agent 读取），
属于生产能力而非一次性脚本 —— 故迁入 application 层，并由 core_plan_generate 定时任务驱动。

数据访问（2026-09-13 B7 收口）：原先以 subprocess 调 psql 取数（原脚本写法），现已全部改走
infrastructure 的 SQLAlchemy engine + **绑定变量**。为什么必须收口（不是洁癖）：
  ① psql 是外部二进制 + 依赖 PATH 拼装，在 launchd 托管环境下属"能跑但不可控"的隐式依赖；
  ② 拼接 SQL 意味着账户名等外部值直接进语句（R-019 要求账户来自 agents.json，不该经字符串进 SQL）；
  ③ check=True 把数据库侧原始报错压成 CalledProcessError，"查询失败"与"查询成功但为空"难分辨。

原始说明如下 ——

**只出计划，不自动下单**

依据（当日研究结论）：选股型叠层全部负超额；**等权 core + 波动目标 + 回撤闸门**稳健
（2024-07~2026-09：Sharpe 0.98→1.22、回撤 -17.9%→-10.6%，9 组参数/3 种池子规模一致）。

本服务产出：
  1. 目标暴露 = min(regime 上限, 波动目标暴露 × 回撤闸门系数)，并给出各因子明细；
  2. 目标持仓 = 流动性 Top 且价格可负担的 N 只等权（A股 100 股整数倍约束下可落地）+ 成长板独立子额度；
  3. 写入 quantsys-v2/config/core_plan.json + 打印人类可读摘要。**不下任何委托。**

⚠️ 文档/实现对齐（2026-09-13 B7 复核）：原文案第 3 条写"与当前持仓的差额（需要买/卖多少股）"，
但**代码从未实现**——本服务不读 position_list，产出的 holdings 是"目标组合"而非"待下委托"。
差额要由消费方（agent）读当前持仓自行比对。此处按实现改正，避免计划文件被当成下单清单。

用法：由定时任务 core_plan_generate 驱动（工作日 09:05，task id 337）。
      不要用 python 直接跑本模块——它是 application 层服务，不是可执行入口。
      手动补跑：POST /api/scheduler/tasks/337/trigger
"""
import decimal
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ⚠️ 路径基准（2026-09-13 上迁时实测踩到）：本文件从 scripts/ 迁到 application/services/ 后，
# parents[1] 变成了 application/ 而不是 quantsys-v2/ —— 计划会被写到 application/config/core_plan.json，
# 而 09:10 的任务读的是 quantsys-v2/config/core_plan.json → **静默读到旧文件**。故用 parents[2]。
ROOT = Path(__file__).resolve().parents[2]
DEF_START, DEF_END = "2024-01-01", "2024-06-30"
OUT = ROOT / "config" / "core_plan.json"


# --------------------------------------------------------------------------- #
# DB 访问：统一走 engine（B7，2026-09-13 w-a9ec14d7）
# --------------------------------------------------------------------------- #
def _engine():
    from infrastructure.persistence.database.engine import get_engine
    return get_engine()


def _to_float_if_decimal(df: pd.DataFrame) -> pd.DataFrame:
    """把 Decimal 列收敛为 float64 —— 对齐原 psql 实现的数据形态，**不是**可有可无的美化。

    原实现是 `copy (...) to stdout with csv header` → pd.read_csv，numeric 列一律落 float64；
    改走 engine 后 psycopg 对 numeric 返回 decimal.Decimal，pandas 落 **object** dtype。
    object dtype 会让下游的排序/均值/比较出现静默差异（例如 sort_values 能跑但语义变了、
    pct_change 可能抛错），而"能跑"会掩盖它。故显式对齐。
    （实测：quant.daily_klines 的 close/amount 是 double precision → 本来就是 float；
      仅 quant.simulation_account 的 total_value/cash_available 是 numeric → 需要这一步。）
    """
    for c in df.columns:
        if df[c].dtype == object:
            nn = df[c].dropna()
            if len(nn) and all(isinstance(v, decimal.Decimal) for v in nn.iloc[:50]):
                df[c] = df[c].astype("float64")
    return df


def query_df(sql, params: Optional[dict] = None) -> pd.DataFrame:
    """只读查询 → DataFrame。**绑定变量**，不拼字符串。"""
    from sqlalchemy import text
    stmt = text(sql) if isinstance(sql, str) else sql
    with _engine().connect() as conn:
        df = pd.read_sql(stmt, conn, params=params or {})
    return _to_float_if_decimal(df)


def query_rows(sql, params: Optional[dict] = None) -> list:
    from sqlalchemy import text
    stmt = text(sql) if isinstance(sql, str) else sql
    with _engine().connect() as conn:
        return list(conn.execute(stmt, params or {}).fetchall())


def kline_history(symbols, start: str) -> pd.DataFrame:
    """取若干标的的自 start 起日线（按交易日升序）。symbols 走 expanding 绑定变量。

    原实现把 symbol 列表拼进 IN 子句；此处改为绑定变量（列表本身来自库内，风险低，
    但"拼接"这个形态一旦被复制到别处就是注入面，故不在钱路上留样板）。
    """
    from sqlalchemy import bindparam, text
    syms = [str(s) for s in symbols]
    if not syms:
        return pd.DataFrame(columns=["symbol", "trade_date", "close"])
    stmt = text("select symbol, trade_date, close from quant.daily_klines "
                "where symbol in :syms and trade_date >= :start order by trade_date"
                ).bindparams(bindparam("syms", expanding=True))
    df = query_df(stmt, {"syms": syms, "start": start})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


# --------------------------------------------------------------------------- #
# 账户事实源解析（R-019：账户名不得写死在任务/提示词/代码里）
#
# 背景（2026-09-13 实测）：本服务上迁为 job 后，scheduler 传给 job 的 params 来自任务行
# （{\"command\": ..., \"description\": ...}），**不含 account** → generate() 直接抛
#   ValueError: core_plan generate 需要 account 参数
# 也就是"任务注册成功"并不等于"任务能跑通"：注册只证明 JobRegistry 里有这个类，
# 参数从哪来只有真触发一次才暴露（本次即由 POST /api/scheduler/tasks/337/trigger 抓到）。
#
# 解析顺序（越靠前优先级越高）：
#   1) 调用方显式传入的 account
#   2) 环境变量 DSH_INVESTMENT_ACCOUNT
#   3) profileDir/agents.json 的 instance.account —— **唯一事实源**（R-019）
#   4) 都没有 → 显式报错（不猜、不写死）
# profileDir 解析：环境变量 DSH_PROFILE_DIR，否则仓库内默认位置
#   <repo>/agent-dh/.dsh-home/profiles/investment
# --------------------------------------------------------------------------- #
DEFAULT_PROFILE_DIR = ROOT.parent / "agent-dh" / ".dsh-home" / "profiles" / "investment"


def resolve_account(explicit: Optional[str] = None) -> str:
    """按 R-019 解析投资账户名：显式 > 环境变量 > agents.json（唯一事实源）> 报错。"""
    if explicit:
        return str(explicit).strip()
    env = (os.environ.get("DSH_INVESTMENT_ACCOUNT") or "").strip()
    if env:
        return env
    import json as _json
    profile_dir = Path(os.environ.get("DSH_PROFILE_DIR") or DEFAULT_PROFILE_DIR)
    agents = profile_dir / "agents.json"
    if agents.exists():
        try:
            doc = _json.loads(agents.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 —— 读不动就是读不动，不能退回默认值
            raise ValueError("账户事实源 %s 解析失败：%s" % (agents, exc))
        acct = ((doc.get("instance") or {}).get("account") or "").strip()
        if acct:
            return acct
        raise ValueError("账户事实源 %s 的 instance.account 为空——请先在 agents.json 指定本实例账户"
                         % agents)
    raise ValueError(
        "无法解析投资账户：未显式传 account、未设 DSH_INVESTMENT_ACCOUNT，且 %s 不存在。"
        "账户唯一事实源是 profileDir/agents.json 的 instance.account（R-019），本服务不内置默认账户名。"
        % agents)



def generate(**kwargs) -> dict:
    class _A:
        pass
    a = _A()
    for k, v in dict(names=15, single_cap=0.15, min_names=8, growth_sleeve_pct=0.05, growth_names=3, growth_min_amount=50000000.0, growth_min_roe=5.0, growth_max_pe=40.0, target_vol=0.15, max_exposure=0.25, account=None, max_price=30.0, exclude_near_high=-0.05, momentum_tilt=False, style_tilt=False).items():
        setattr(a, k, v)
    for k, v in (kwargs or {}).items():
        setattr(a, k, v)
    # R-019：账户来自唯一事实源（agents.json），不写死；调度任务 params 里没有 account 也能跑。
    a.account = resolve_account(a.account)

    # 1) 候选池：窗口前定义（2024H1）流动性 Top，含价格与流动性明细
    px = query_df("select symbol, max(trade_date)::text as d, avg(amount) as amt from quant.daily_klines "
                  "where trade_date between :def_start and :def_end group by symbol "
                  "having count(*) >= 100 order by amt desc limit 400",
                  {"def_start": DEF_START, "def_end": DEF_END})
    px["symbol"] = px["symbol"].astype(str).str.zfill(6)
    # 计划的数据时点（R-013）：写进产物，让计划**自描述**它基于哪天的行情算出来。
    # 为什么必要：产物原先只有 generated_at（生成时刻），没有 data_date（行情时点）——
    # 计划在周末/节假日重跑或行情未同步时，生成时刻是新的、行情却可能是旧的，
    # 只看 generated_at 无法发现。这与"signals.strategy_id 应自描述策略名"是同一条教训。
    _dd = query_rows("select max(trade_date)::text from quant.daily_klines")
    data_date = (_dd[0][0] if _dd else None)

    latest = query_df("select symbol, close, amount from quant.daily_klines where trade_date = "
                      "(select max(trade_date) from quant.daily_klines)")
    latest["symbol"] = latest["symbol"].astype(str).str.zfill(6)
    uni = px.merge(latest, on="symbol", how="inner", suffixes=("_def", "_now"))
    uni = uni[(uni["close"] > 0) & (uni["close"] <= a.max_price)]
    uni = uni.sort_values("amt", ascending=False)
    # 不追高（2026-09-13 基准率检验）：距 52 周高 ≤3% 的标的，未来 20/60 日**中位收益为负**、胜率<50%；
    # 而距高 <-30% 的深跌标的 120 日中位 +11.1%、胜率 66.8%。故默认排除近高标的。
    hi = query_df("select symbol, max(close) as hi52 from quant.daily_klines where trade_date >= "
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
    st = query_df("select symbol, name, industry, sector, roe, pe, debt_ratio, is_st, is_suspended, list_date, market_cap "
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

    # 账户资金：绑定变量（账户名来自 agents.json，不经 SQL 字符串拼接）
    # 原实现查不到行时返回空串 → split 只得 1 段 → float(acct[1]) 抛 IndexError（信息量为零）。
    # 改为显式报错：查不到账户就是**不能出计划**，绝不按 0 元资产继续往下算。
    _acct_rows = query_rows("select coalesce(total_value,0), coalesce(cash_available,0) "
                            "from quant.simulation_account where account_name = :acct",
                            {"acct": a.account})
    if not _acct_rows:
        raise ValueError("账户 %r 不在 quant.simulation_account 中，无法生成建仓计划（不猜资金规模）"
                         % a.account)
    total, cash = float(_acct_rows[0][0] or 0), float(_acct_rows[0][1] or 0)

    # 暴露：波动目标 × 回撤闸门（用最终持仓的日收益重建 core 指数）
    hist = kline_history(uni["symbol"].head(200), "2024-06-01")
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
        _im = query_df("""select s.industry, avg(k.close / p.close - 1) as r60
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
        rank_note = "行业动量 %s（%d/%d）" % ("强" if q < 1 / 3 else ("中" if q < 2 / 3 else "弱"), pos + 1, n_ind)
        if not a.momentum_tilt:
            # 证据收敛（2026-09-13）：动量无预测力，默认不参与加权，仅作信息标注
            mult = 1.0
            note = rank_note + "（未加权：实测无预测力）"
        else:
            mult = 1.3 if q < 1 / 3 else (1.0 if q < 2 / 3 else 0.5)
            note = rank_note
        if a.style_tilt and CONF >= 0.6 and q >= 1 / 3:      # 动量前 1/3 的行业不套风格惩罚：动量优先于风格标签
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
    # 子额度独立质量门槛（比 core 严）：ROE ≥ growth_min_roe 且 0 < PE ≤ growth_max_pe
    _gst = _gst[_gst["roe"].notna() & (_gst["roe"] >= a.growth_min_roe)]
    _gst = _gst[_gst["pe"].notna() & (_gst["pe"] > 0) & (_gst["pe"] <= a.growth_max_pe)]
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
        _gh = kline_history(_gsyms, "2024-06-01")
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

    # 把每只的目标手数/金额**写进产物**（B8，2026-09-13）：
    # 原先只存 weight_pct_of_core，手数仅在下方打印时算一遍就丢了 → 消费方（core-plan 任务）
    # 拿不到"目标股数"，它要求的"与当前持仓的差额"**根本无从算起**，只能每次手工推导；
    # live-order-test 任务也不得不自己按 1 手成本挑标的。存下来即消除这类重复推导。
    # 口径与打印循环完全一致：_amt = 总资产 × 目标暴露 × 权重；手数 = floor(_amt / (价×100))。
    _target_amount = total * target_expo
    _core_rows = []
    for _t in tilts:
        _c = float(_pk[_t["symbol"]]["close"])
        _amt = _target_amount * _t["weight_pct_of_core"] / 100.0
        _core_rows.append({
            "symbol": _t["symbol"], "industry": _t["industry"],
            "weight_pct_of_core": _t["weight_pct_of_core"], "tilt_mult": _t["mult"], "tilt_note": _t["note"],
            "close": _c, "roe": float(_pk[_t["symbol"]]["roe"]),
            "pe": float(_pk[_t["symbol"]]["pe"]), "amount_def_avg": float(_pk[_t["symbol"]]["amt"]),
            "lots": int(_amt // (_c * 100)), "amount": round(_amt, 0),
        })

    plan = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_date": data_date,
        "account": a.account, "mode": "PLAN_ONLY（不下单）",
        "account_total": total, "cash": cash,
        "exposure": {"target_pct": target_expo, "first_phase_cap_pct": a.max_exposure,
                     "core_realized_vol_ann": round(vol_ann, 4) if vol_ann else None,
                     "vol_target": a.target_vol, "w_vol": round(w_vol, 3),
                     "core_drawdown": round(dd, 4), "dd_gate": gate},
        "market_style": {"style": STYLE, "confidence": round(CONF, 3), "source": "/api/market/style"},
        "sector_heat_top5": sorted(api_sectors.items(), key=lambda kv: kv[1], reverse=True)[:5],
        "sector_momentum_note": "行业动量由库内 quant.stocks.industry 分组、近 60 日成分股等权收益中位数自算（/api/market/sectors 实测返回 0 条，不可用）",
        "holdings": _core_rows,
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
    _wm = "按板块风向加权（动量 %s / 风格 %s）" % ("开" if a.momentum_tilt else "关",
                                                 "开" if a.style_tilt else "关")
    print("目标持仓 %d 只（%s；等权基准每只约 %.0f 元）："
          % (len(tilts), _wm, target_amount / max(len(tilts), 1)))
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
    return plan


# 注：原脚本的 `if __name__ == "__main__": raise SystemExit(main())` 已删除 ——
# main() 从未随上迁一起搬过来，这行是**必然 NameError 的死引用**（import 时不触发，故一直没暴露）。
# 本模块是被 job 调用的服务，不是可执行入口；要跑它请用 core_plan_generate 任务。



# --------------------------------------------------------------------------- #
# 只读视图：计划 + 新鲜度 + 与当前持仓的机械差额（B8，2026-09-13 w-a9ec14d7）
#
# 为什么需要：计划落盘在 config/core_plan.json，三个例行任务靠**硬编码文件路径**直接读它
# （agent-brain-core-plan 09:10 / agent-brain-candidate-hunt 08:45 / live-order-test）。
# 直接读文件有三个问题：
#   ① 路径知识散落在各任务提示词里，改一处要改 N 处；
#   ② **读不出"陈不陈"**——周五的计划周一照样读得出来，内容看着完全正常，
#      而 core-plan 任务自己要用 generated_at 手工判新鲜度（这正是最容易被跳过的一步）；
#   ③ 该任务第 2 步要求"核对与当前持仓的差额"，而服务端**从未产出过这个差额**
#      （见本文件顶部"文档/实现对齐"说明），只能靠 agent 每次手工比对。
# 本视图把这三件事一次给全。**只读**：不触发重新生成（生成参数集是已审批的，不该由查询侧启动）。
# --------------------------------------------------------------------------- #

# 例行任务约定：计划须**当天生成且不早于 09:00**（core_plan_generate 的 cron 是 09:05）。
# 这里只做机械判定并给出**理由文本**，不替调用方决定要不要停。
PLAN_DEADLINE_HHMM = "09:00"

# 差额的固有限制——写在返回值里，避免"看到一张差额表就当委托清单"。
DELTA_CAVEATS = [
    "price 用的是**计划生成时的收盘价**（plan_close），不是实时价；下单前必须 data_fetch_quote(source=realtime) 重新取价（R-013）。",
    "未做 T+1 校验：卖出可用量看 shares_available（当日买入次日才可卖，宪法第2条）。",
    "未做 regime/止损复检：下单前必须走 R-001（regime_position_limit + account_info + 风控仓位）与 R-002（止损价）。",
    "本表是「目标组合 vs 当前持仓」的**机械差额**，不含分批节奏——计划本身是分 4 批执行的（见 plan.phase_plan），一次打满是误用。",
    "in_plan=false 的持仓**不等于应卖出**：本计划是建仓计划，不含退出判断；处置走 R-002 止损与组合复核。",
    "未校验单股≤20%/单行业≤40%/现金≥10%（宪法第3条）——机械差额可能超限，下单前必须复核。",
]


def _plan_freshness(plan: dict, now: Optional[datetime] = None) -> dict:
    """计划新鲜度（机械判定 + 理由）。锚点是"今天"，因为例行任务的口径就是"当天生成"。"""
    now = now or datetime.now()
    ga = plan.get("generated_at")
    info = {
        "generated_at": ga, "data_date": plan.get("data_date"),
        "deadline_hhmm": PLAN_DEADLINE_HHMM,
        "age_hours": None, "generated_today": False, "generated_after_deadline": False,
        "is_stale": True, "stale_reason": None,
    }
    if not ga:
        info["stale_reason"] = "计划缺少 generated_at 字段，无法判定新鲜度"
        return info
    try:
        t = datetime.fromisoformat(str(ga))
    except Exception:  # noqa: BLE001
        info["stale_reason"] = "generated_at 无法解析：%r" % (ga,)
        return info
    info["age_hours"] = round((now - t).total_seconds() / 3600.0, 2)
    info["generated_today"] = (t.date() == now.date())
    info["generated_after_deadline"] = bool(
        info["generated_today"] and t.strftime("%H:%M") >= PLAN_DEADLINE_HHMM)
    reasons = []
    if not info["generated_today"]:
        reasons.append("generated_at=%s 不是今天（%s）" % (ga, now.date().isoformat()))
    elif not info["generated_after_deadline"]:
        reasons.append("generated_at=%s 早于当天 %s" % (ga, PLAN_DEADLINE_HHMM))
    info["is_stale"] = bool(reasons)
    info["stale_reason"] = "；".join(reasons) if reasons else None
    return info


def _plan_delta(plan: dict, account: str) -> dict:
    """目标组合 vs 当前持仓的机械差额。只读：不刷行情、不下单、不改库。"""
    from adapters.outbound.repositories.simulation_position_repository import SimulationPositionRepository

    positions = SimulationPositionRepository().get_all_positions(account) or []
    held = {}
    for p in positions:
        held[str(p.symbol).zfill(6)] = p

    rows = query_rows("select coalesce(cash_available,0) from quant.simulation_account "
                      "where account_name = :a", {"a": account})
    cash = float(rows[0][0] or 0) if rows else None

    targets = []
    for h in (plan.get("holdings") or []):
        targets.append(("core", h))
    for h in ((plan.get("growth_sleeve") or {}).get("holdings") or []):
        targets.append(("growth_sleeve", h))

    out_rows, seen = [], set()
    for bucket, h in targets:
        sym = str(h.get("symbol") or "").zfill(6)
        if not sym or sym in seen:
            continue
        seen.add(sym)
        close = float(h.get("close") or 0)
        tgt = int(h.get("lots") or 0) * 100
        p = held.get(sym)
        hv = int(getattr(p, "shares_total", 0) or 0) if p else 0
        av = int(getattr(p, "shares_available", 0) or 0) if p else 0
        d = tgt - hv
        out_rows.append({
            "symbol": sym, "bucket": bucket, "in_plan": True,
            "plan_close": close, "target_lots": int(h.get("lots") or 0), "target_shares": tgt,
            "held_shares": hv, "shares_available": av, "delta_shares": d,
            "action": ("BUY" if d > 0 else ("SELL" if d < 0 else "NONE")),
            "est_amount": round(abs(d) * close, 0),
        })
    for sym in sorted(held):
        if sym in seen:
            continue
        p = held[sym]
        out_rows.append({
            "symbol": sym, "bucket": "held_only", "in_plan": False,
            "plan_close": None, "target_lots": None, "target_shares": None,
            "held_shares": int(getattr(p, "shares_total", 0) or 0),
            "shares_available": int(getattr(p, "shares_available", 0) or 0),
            "delta_shares": None, "action": "REVIEW", "est_amount": None,
        })

    buys = [r for r in out_rows if r["action"] == "BUY"]
    sells = [r for r in out_rows if r["action"] == "SELL"]
    est_buy = round(sum(r["est_amount"] for r in buys), 0)
    return {
        "account": account,
        "cash_available": cash,
        "rows": out_rows,
        "summary": {
            "buy_count": len(buys), "sell_count": len(sells),
            "hold_count": sum(1 for r in out_rows if r["action"] == "NONE"),
            "review_count": sum(1 for r in out_rows if r["action"] == "REVIEW"),
            "est_buy_amount": est_buy,
            "cash_after_full_delta": (round(cash - est_buy, 0) if cash is not None else None),
            "cash_sufficient": (cash is not None and cash >= est_buy),
        },
        "caveats": DELTA_CAVEATS,
    }


def plan_snapshot(account: Optional[str] = None, path: Optional[Path] = None) -> dict:
    """建仓计划的只读视图：计划全文 + 新鲜度 + 与当前持仓的机械差额。

    account 缺省 = 计划文件自身记录的账户（**不是** resolve_account 的默认值）——
    计划只服务一个账户，问别的账户的差额没有意义，故显式传入不同账户时**不给差额**并说明原因。
    """
    p = Path(path) if path else OUT
    base = {
        "plan_file": str(p), "available": False, "unavailable_reason": None,
        "account": None, "requested_account": account, "account_mismatch": False,
        "freshness": None, "plan": None, "delta": None,
    }
    if not p.exists():
        base["unavailable_reason"] = (
            "计划文件不存在：%s。通常意味着 core_plan_generate（工作日 09:05）从未成功运行。"
            "不要手工造计划——生成参数集是已审批的，补跑请 POST /api/scheduler/tasks/337/trigger。" % p)
        return base
    try:
        plan = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        base["unavailable_reason"] = "计划文件无法解析：%s: %s" % (type(exc).__name__, exc)
        return base

    plan_account = (plan.get("account") or "").strip() or None
    base.update({"available": True, "plan": plan, "account": plan_account,
                 "freshness": _plan_freshness(plan)})

    if account and plan_account and str(account).strip() != plan_account:
        base["account_mismatch"] = True
        base["unavailable_reason"] = (
            "计划文件属于账户 %r，与请求的 %r 不一致——本计划只覆盖单一账户，"
            "不计算跨账户差额。" % (plan_account, str(account).strip()))
        return base

    target = plan_account or (str(account).strip() if account else None) or resolve_account(None)
    base["account"] = target
    try:
        base["delta"] = _plan_delta(plan, target)
    except Exception as exc:  # noqa: BLE001 —— 差额失败不该让"读计划"整体失败
        base["unavailable_reason"] = "差额计算失败（计划本身仍可用）：%s: %s" % (type(exc).__name__, exc)
    return base


class CorePlanGenerateJob:
    """core 建仓计划生成定时任务（工作日 09:05，2026-09-13 w-a9ec14d7）

    为什么是 job 而不是脚本：用户 2026-09-13 裁定「脚本不能写进 v2 项目，脚本只能测试用」。
    本能力原先由 scripts/core_plan.py 承担、由 09:10 的 agent 任务用 bash 调脚本 —— 属生产能力。
    上迁为 application 层服务 + 定时任务后，本任务 09:05 生成计划，agent 任务 09:10 只需**读取**计划文件。
    """

    def __init__(self):
        self._name = "core_plan_generate"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "core 建仓计划生成：等权分散 + 波动目标 + 回撤闸门（只出计划，不下单）"

    @property
    def timeout_seconds(self) -> int:
        return 600

    async def execute(self, params=None):
        from application.jobs.job_protocol import JobResult, result_from_dict
        import asyncio
        p = params or {}
        try:
            plan = await asyncio.to_thread(generate, **p)
        except Exception as exc:  # noqa: BLE001 —— 失败必须显式（调度器据此标红）
            import logging
            logging.getLogger(__name__).exception("core_plan_generate failed")
            return JobResult.fail(self._name, "%s: %s" % (type(exc).__name__, exc))
        h = plan.get("holdings") or []
        s = plan.get("growth_sleeve", {}).get("holdings") or []
        return result_from_dict(self._name,
                                "core_plan generated: core=%d sleeve=%d" % (len(h), len(s)),
                                {"account": plan.get("account"), "core": len(h), "sleeve": len(s),
                                 "exposure": plan.get("exposure", {}).get("target_pct")})


def build_core_plan_jobs():
    """构造 core 计划任务（组合根在 main.py 注册进 JobRegistry）"""
    return [CorePlanGenerateJob()]