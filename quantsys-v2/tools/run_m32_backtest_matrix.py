#!/usr/bin/env python3
"""
M3-2 回测矩阵执行脚本：5 策略 × 3 市场区间 × 10 蓝筹股 = 150 个回测。

背景：
- 数据地基已修复（tools/backfill_daily_klines_sina.py 补齐 2023/2024H1 K线）
- 5 个经典策略已创建（tools/create_m32_strategies.py → id 635-639）
- 回测引擎 /api/backtest/run 验证可用，结果自动入库 quant.backtest_results

区间：
- 牛市 2023-01-01 ~ 2023-12-31（bull2023）
- 震荡 2024-01-01 ~ 2024-06-30（range24h1）
- 熊市 2024-07-01 ~ 2024-12-31（bear24h2）

用法：
    python3 tools/run_m32_backtest_matrix.py          # 全量 150 个
    python3 tools/run_m32_backtest_matrix.py --dry    # 只打印任务清单
"""
import concurrent.futures
import json
import sys
import time

import requests

API = "http://localhost:5001/api/backtest/run"

STRATEGIES = [
    {"id": 635, "name": "macd-golden-cross-v1"},
    {"id": 636, "name": "bollinger-breakout-v1"},
    {"id": 637, "name": "rsi-oversold-v1"},
    {"id": 638, "name": "dual-ma-cross-v1"},
    {"id": 639, "name": "momentum-breakout-v1"},
]

PERIODS = [
    {"key": "bull2023", "start": "2023-01-01", "end": "2023-12-31", "label": "牛市2023"},
    {"key": "range24h1", "start": "2024-01-01", "end": "2024-06-30", "label": "震荡2024H1"},
    {"key": "bear24h2", "start": "2024-07-01", "end": "2024-12-31", "label": "熊市2024H2"},
]

SYMBOLS = [
    # 蓝筹（低波动基准）
    "600519", "000858", "600036", "600000", "601318",
    "600030", "000333", "601166", "601288", "600900",
    # 成长股（风险预案 6.2 补充：提高趋势策略夏普空间）
    "300750", "002594", "300308", "300274", "688981", "300059",
]


def build_tasks():
    tasks = []
    for s in STRATEGIES:
        for p in PERIODS:
            for sym in SYMBOLS:
                tasks.append({
                    "strategy_id": s["id"],
                    "strategy_name": s["name"],
                    "symbol": sym,
                    "period": p["key"],
                    "period_label": p["label"],
                    "start_date": p["start"],
                    "end_date": p["end"],
                    "initial_capital": 1000000,
                })
    return tasks


def run_one(task):
    payload = {
        "strategy_id": task["strategy_id"],
        "symbol": task["symbol"],
        "start_date": task["start_date"],
        "end_date": task["end_date"],
        "initial_capital": task["initial_capital"],
    }
    try:
        resp = requests.post(API, json=payload, timeout=90)
        d = resp.json()
        if d.get("success"):
            r = d.get("data") or {}
            return {
                **task,
                "status": "ok",
                "total_trades": r.get("totalTrades") or 0,
                "sharpe": r.get("sharpeRatio") or 0,
                "total_return": r.get("totalReturn") or 0,
                "max_drawdown": r.get("maxDrawdown") or 0,
                "win_rate": r.get("winRate") or 0,
                "backtest_id": r.get("BacktestId") or r.get("backtestId"),
            }
        return {**task, "status": "error", "error": d.get("message") or str(d)[:200]}
    except Exception as e:
        return {**task, "status": "exception", "error": str(e)[:200]}


def main():
    tasks = build_tasks()
    if "--dry" in sys.argv:
        print(f"任务总数: {len(tasks)}")
        for t in tasks[:5]:
            print(t)
        return

    print(f"开始执行 {len(tasks)} 个回测任务（并发 10）...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(run_one, t) for t in tasks]
        done = 0
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            results.append(r)
            done += 1
            if r["status"] == "ok":
                print(f"[{done}/{len(tasks)}] {r['strategy_name']} | {r['symbol']} | {r['period']} "
                      f"| trades={r['total_trades']} sharpe={r['sharpe']:.2f} ret={r['total_return']:.1f}%")
            else:
                print(f"[{done}/{len(tasks)}] {r['strategy_name']} | {r['symbol']} | {r['period']} | {r['status']}: {r.get('error')}")

    ok = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] != "ok"]
    print(f"\n完成: 成功 {len(ok)}/{len(tasks)}, 失败 {len(err)}")

    # 汇总：按策略×区间
    print("\n=== 按策略平均夏普（跨全部股票） ===")
    by_strategy = {}
    for r in ok:
        by_strategy.setdefault(r["strategy_name"], []).append(r)
    for name, rs in sorted(by_strategy.items()):
        avg_sharpe = sum(x["sharpe"] for x in rs) / len(rs)
        avg_ret = sum(x["total_return"] for x in rs) / len(rs)
        trades = sum(x["total_trades"] for x in rs)
        print(f"{name}: 平均夏普={avg_sharpe:.3f} 平均收益={avg_ret:.2f}% 总交易={trades} 样本={len(rs)}")

    print("\n=== 按策略×区间平均夏普 ===")
    by_pair = {}
    for r in ok:
        key = (r["strategy_name"], r["period"])
        by_pair.setdefault(key, []).append(r)
    for (name, period), rs in sorted(by_pair.items()):
        avg_sharpe = sum(x["sharpe"] for x in rs) / len(rs)
        print(f"{name} | {period}: 平均夏普={avg_sharpe:.3f} (n={len(rs)})")

    with open("/tmp/m32_matrix_results.json", "w") as f:
        json.dump({"ok": ok, "err": err}, f, ensure_ascii=False, indent=1)
    print("\n结果已保存: /tmp/m32_matrix_results.json")


if __name__ == "__main__":
    main()
