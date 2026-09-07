#!/usr/bin/env python3
"""
从新浪源回填 daily_klines 缺失的历史K线数据（M3-2 数据地基修复）

背景：quantsys-v2 网络数据源（tencent/baostock/akshare）全部不可用，
但新浪源 (quotes.sina.cn) 可用且与数据库已有数据一致（已交叉验证 600519）。
回测引擎直接读 quant.daily_klines 表，因此回填数据即可解锁 M3-2 回测矩阵。

用法：
    python3 tools/backfill_daily_klines_sina.py              # 回填默认10只蓝筹池
    python3 tools/backfill_daily_klines_sina.py 600519 000858  # 指定标的

注意：幂等（ON CONFLICT DO NOTHING），可重复执行。
"""
import json
import os
import re
import sys
import time
from datetime import datetime

import psycopg2
import requests

DATABASE_URL = os.environ.get(
    "QUANT_DATABASE_URL", "postgresql://mac@127.0.0.1:5432/quant_investment"
)
SINA_URL = (
    "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_="
    "/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={datalen}"
)

# M3-2 执行计划的 10 只蓝筹股
DEFAULT_SYMBOLS = [
    "600519", "000858", "600036", "600000", "601318",
    "600030", "000333", "601166", "601288", "600900",
]

# 回填起始日期（覆盖 M3-2 三个区间：2023 牛市 / 2024H1 震荡 / 2024H2 熊市）
BACKFILL_START = "2022-06-01"


def sina_symbol(code: str) -> str:
    """A股代码 → 新浪带交易所前缀代码"""
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    raise ValueError(f"无法识别交易所前缀: {code}")


def fetch_sina_klines(code: str, datalen: int = 1600) -> list:
    """从新浪拉取日K线（scale=240=日线），返回 [{day, open, high, low, close, volume}]"""
    url = SINA_URL.format(symbol=sina_symbol(code), datalen=datalen)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    text = resp.text
    # 去掉 JSONP 包装：/*<script>...</script>*/ var _=([...]);
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"新浪返回格式异常: {text[:200]}")
    return json.loads(text[start : end + 1])


def main():
    symbols = sys.argv[1:] or DEFAULT_SYMBOLS
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    total_inserted = 0
    total_skipped = 0
    for code in symbols:
        try:
            klines = fetch_sina_klines(code)
        except Exception as e:
            print(f"[FAIL] {code}: 新浪拉取失败 {e}")
            continue

        # 过滤出回填区间内的数据
        rows = []
        for k in klines:
            day = k["day"]
            if day < BACKFILL_START:
                continue
            # 只补缺失区间（2022-06 ~ 2024-06 为缺口重灾区，也可整体补，用 ON CONFLICT 幂等）
            rows.append((
                code, day,
                float(k["open"]), float(k["high"]), float(k["low"]), float(k["close"]),
                float(k["volume"]),
                0.0,  # amount 新浪日线不提供
                0.0,  # turnover_rate 新浪日线不提供
                "sina-backfill",
            ))

        inserted = 0
        skipped = 0
        for r in rows:
            cur.execute(
                """
                INSERT INTO quant.daily_klines
                    (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, trade_date) DO NOTHING
                """,
                r,
            )
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        conn.commit()
        total_inserted += inserted
        total_skipped += skipped
        print(f"[OK] {code}: 新浪拉取 {len(klines)} 条, 区间内 {len(rows)} 条, 新插入 {inserted}, 已存在跳过 {skipped}")

    cur.close()
    conn.close()
    print(f"\n完成: 共回填 {len(symbols)} 只, 新插入 {total_inserted} 条, 跳过 {total_skipped} 条")


if __name__ == "__main__":
    main()
