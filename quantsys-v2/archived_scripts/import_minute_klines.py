#!/usr/bin/env python3
"""
从新浪财经导入 A 股分钟 K 线数据到 quant.minute_klines 表
支持 scale=5 (5分钟)、scale=15、scale=30、scale=60
"""
import requests
import json
import sys
import os
import time
import psycopg2
import psycopg2.extras
from datetime import datetime

# DB config
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "quant_investment",
    "user": "mac",
    "password": "",
}

SINA_MINUTE_URL = (
    "https://money.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/CN_MarketData.getKLineData"
)

# 股票代码映射: 纯数字 → 新浪前缀
def to_sina_code(symbol: str) -> str:
    symbol = symbol.strip()
    if symbol.startswith("6"):
        return f"sh{symbol}"
    else:
        return f"sz{symbol}"


def fetch_minute_klines(symbol: str, scale: int = 5, datalen: int = 2000) -> list:
    """从新浪获取分钟K线数据"""
    sina_code = to_sina_code(symbol)
    params = {
        "symbol": sina_code,
        "scale": str(scale),
        "ma": "no",
        "datalen": datalen,
    }
    try:
        r = requests.get(SINA_MINUTE_URL, params=params, timeout=60)
        r.raise_for_status()
        data = json.loads(r.text)
        if not isinstance(data, list):
            print(f"  ⚠️  {symbol}: 返回非列表数据: {type(data)}")
            return []
        return data
    except Exception as e:
        print(f"  ❌ {symbol}: 获取失败 - {e}")
        return []


def insert_minute_klines(conn, symbol: str, bars: list) -> int:
    """插入分钟K线到 PostgreSQL，使用 UPSERT"""
    inserted = 0
    sql = """
        INSERT INTO quant.minute_klines (symbol, trade_datetime, open, high, low, close, volume)
        VALUES (%(symbol)s, %(trade_datetime)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s)
        ON CONFLICT (symbol, trade_datetime)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
    """
    rows = []
    for bar in bars:
        try:
            ts = bar.get("day", "")
            if not ts:
                continue
            rows.append({
                "symbol": symbol,
                "trade_datetime": ts,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": int(float(bar.get("volume", 0))),
            })
        except (KeyError, ValueError, TypeError) as e:
            continue

    if not rows:
        return 0

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
        inserted = cur.rowcount
    conn.commit()
    return inserted


def main():
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["688981", "688256", "002371", "603501"]
    scale = int(os.environ.get("MINUTE_SCALE", "5"))

    print(f"📊 导入分钟K线: scale={scale}min, stocks={symbols}")
    conn = psycopg2.connect(**DB_CONFIG)
    
    try:
        for symbol in symbols:
            print(f"\n🔍 {symbol}...")
            bars = fetch_minute_klines(symbol, scale=scale)
            if not bars:
                print(f"  ⚠️  无数据，跳过")
                continue

            n = insert_minute_klines(conn, symbol, bars)
            first_ts = bars[0]["day"]
            last_ts = bars[-1]["day"]
            print(f"  ✅ 插入 {n} 条 ({len(bars)} 获取), 范围: {first_ts} → {last_ts}")
            time.sleep(1)  # 避免请求过快
    finally:
        conn.close()

    # 验证
    conn2 = psycopg2.connect(**DB_CONFIG)
    try:
        with conn2.cursor() as cur:
            for symbol in symbols:
                cur.execute(
                    "SELECT COUNT(*), MIN(ts), MAX(ts) FROM quant.minute_klines WHERE symbol=%s",
                    (symbol,)
                )
                row = cur.fetchone()
                if row and row[0] > 0:
                    print(f"\n📦 {symbol}: {row[0]} bars, {row[1]} → {row[2]}")
                else:
                    print(f"\n📦 {symbol}: 0 bars")
    finally:
        conn2.close()

    print("\n✅ 导入完成")


if __name__ == "__main__":
    main()
