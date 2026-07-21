#!/usr/bin/env python3
"""
批量从新浪导入 5 分钟 K 线到 quant.minute_klines 表
多线程 + 连接池，处理全市场股票
"""
import os
import sys
import time
import json
import signal
import requests
import psycopg2
import psycopg2.pool
import psycopg2.extras
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "quant_investment",
    "user": "mac",
    "password": "",
}
SINA_URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"

# 全局开关：Ctrl+C 停止
SHUTDOWN = False

def handle_sigint(sig, frame):
    global SHUTDOWN
    print("\n🛑 收到中断信号，正在停止...")
    SHUTDOWN = True
signal.signal(signal.SIGINT, handle_sigint)

# ─── 工具函数 ──────────────────────────────────────────────

def to_sina_code(symbol: str) -> str:
    s = symbol.strip()
    return f"sh{s}" if s.startswith("6") else f"sz{s}"

# ─── 单股票处理 ────────────────────────────────────────────

def process_one(symbol: str, pool, scale: int = 5, datalen: int = 500) -> dict:
    """获取并存入一只股票的 5 分钟 K 线，含重试"""
    global SHUTDOWN
    if SHUTDOWN:
        return {"symbol": symbol, "status": "cancelled"}

    sina_code = to_sina_code(symbol)
    params = {"symbol": sina_code, "scale": str(scale), "ma": "no", "datalen": datalen}

    # 线程内速率控制
    time.sleep(0.6)   # Sina API 限流 ~2 req/s per thread

    t0 = time.time()
    data = None
    for attempt in range(4):
        if SHUTDOWN:
            return {"symbol": symbol, "status": "cancelled"}
        try:
            r = requests.get(SINA_URL, params=params, timeout=30)
            if r.status_code == 456:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = json.loads(r.text)
            break
        except Exception as e:
            if attempt < 3:
                time.sleep(1)
                continue
            return {"symbol": symbol, "status": "fetch_error", "error": str(e)[:100], "elapsed": time.time() - t0}
            break

    if data is None:
        return {"symbol": symbol, "status": "fetch_error", "error": "456 rate limit after retries", "elapsed": time.time() - t0}

    if not isinstance(data, list) or not data:
        return {"symbol": symbol, "status": "no_data", "elapsed": time.time() - t0}

    # 构建 upsert rows
    rows = []
    for bar in data:
        ts = bar.get("day", "")
        if not ts:
            continue
        try:
            o = float(bar["open"])
            h = float(bar["high"])
            l = float(bar["low"])
            c = float(bar["close"])
            v = int(float(bar.get("volume", 0)))
            rows.append((symbol, ts, o, h, l, c, v, c * v))  # amount = close * volume
        except (KeyError, ValueError, TypeError):
            continue

    if not rows:
        return {"symbol": symbol, "status": "parse_empty", "total": len(data), "elapsed": time.time() - t0}

    # DB upsert
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO quant.minute_klines (symbol, trade_datetime, open, high, low, close, volume, amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, trade_datetime)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount
            """
            psycopg2.extras.execute_batch(cur, sql, rows, page_size=200)
        conn.commit()
        inserted = len(rows)
    except Exception as e:
        conn.rollback()
        return {"symbol": symbol, "status": "db_error", "error": str(e), "elapsed": time.time() - t0}
    finally:
        pool.putconn(conn)

    first = rows[0][1]
    last = rows[-1][1]
    return {
        "symbol": symbol, "status": "ok", "inserted": inserted,
        "first": first, "last": last,
        "elapsed": round(time.time() - t0, 3)
    }

# ─── 主流程 ──────────────────────────────────────────────────

def main():
    # 参数解析
    max_workers = int(os.environ.get("MINUTE_WORKERS", "2"))
    datalen = int(os.environ.get("MINUTE_DATALEN", "500"))  # 500 bars ≈ 20 个交易日
    request_delay = float(os.environ.get("MINUTE_DELAY", "0.5"))  # 每线程内请求延迟
    skip_existing = os.environ.get("MINUTE_SKIP_RECENT", "1") == "1"

    # 获取股票列表
    checkpoint_file = "/tmp/minute_import_checkpoint.txt"
    done = set()
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file) as f:
            done = set(line.strip() for line in f)
        print(f"   📍 恢复模式: {len(done)} 只已完成，跳过")

    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        if skip_existing:
            # 只补拉 05-28/05-29 缺失的股票（排除 ST/停牌）
            cur.execute("""
                SELECT s.symbol FROM quant.stocks s
                WHERE s.market = 'A'
                  AND NOT s.is_suspended
                  AND NOT s.is_st
                  AND NOT EXISTS (
                      SELECT 1 FROM quant.minute_klines mk
                      WHERE mk.symbol = s.symbol AND mk.trade_datetime >= '2026-05-28'
                  )
                ORDER BY s.symbol
            """)
        else:
            cur.execute("SELECT symbol FROM quant.stocks WHERE market='A' AND NOT is_suspended AND NOT is_st ORDER BY symbol")
        all_symbols = [row[0] for row in cur.fetchall()]
    conn.close()

    symbols = [s for s in all_symbols if s not in done]
    total = len(symbols)
    batch_num = 0 if skip_existing else "ALL"
    print(f"📊 5-分钟K线批量导入: scale=5min, datalen={datalen}, workers={max_workers}")
    print(f"   标的: {total} 只{' (仅补缺失 05-28+)' if skip_existing else ' (全部)'}")

    if total == 0:
        print("✅ 无需补拉，所有股票 05-28+ 数据已就绪")
        return

    # 连接池
    pool = psycopg2.pool.ThreadedConnectionPool(2, max_workers + 2, **DB_CONFIG)

    # 多线程执行
    ok = fail = skipped = 0
    t_start = time.time()
    bars_total = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_one, s, pool, 5, datalen): s for s in symbols}

        for i, f in enumerate(as_completed(futures)):
            result = f.result()
            pct = (i + 1) / total * 100
            elapsed_delta = time.time() - t_start
            eta = elapsed_delta / (i + 1) * (total - i - 1) if i < total - 1 else 0

            if result["status"] == "ok":
                ok += 1
                bars_total += result["inserted"]
                # 写检查点
                with open(checkpoint_file, "a") as cpf:
                    cpf.write(result["symbol"] + "\n")
                if ok % 100 == 0:
                    elapsed_delta = time.time() - t_start
                    eta = elapsed_delta / ok * (total - ok)
                    print(f"  [{ok:5d}/{total}] {pct:.0f}% | {result['symbol']} +{result['inserted']} bars "
                          f"| {result['first']}→{result['last']} | ETA {eta/60:.1f}min")
            elif result["status"] == "cancelled":
                skipped += 1
                bar = "·"
            else:
                fail += 1
                bar = "✗"
                if fail <= 10:
                    print(f"  ❌ {result['symbol']}: {result['status']} - {result.get('error', '')[:80]}")

        print()  # newline after progress

    pool.closeall()

    total_elapsed = time.time() - t_start
    print(f"\n📊 导入完成: OK={ok}, FAIL={fail}, SKIP={skipped}, {bars_total} bars, {total_elapsed:.1f}s")

    # 验证
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT trade_datetime::DATE AS dt, COUNT(DISTINCT symbol) 
            FROM quant.minute_klines 
            WHERE trade_datetime >= '2026-05-28'
            GROUP BY dt ORDER BY dt DESC
        """)
        for dt, cnt in cur.fetchall():
            print(f"  📅 {dt}: {cnt} stocks")
    conn.close()

if __name__ == "__main__":
    main()
