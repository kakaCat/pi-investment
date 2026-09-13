"""指数日线入库/刷新（2026-09-11，w-f4aa1f6a；2026-09-13 定时错配修复，w-32314d00）

背景：quant.index_daily 新建后，指数数据需有稳定的采集通道。实测：
- akshare 的 index_zh_a_hist 走 80.push2.eastmoney.com，本机经代理时好时坏（ProxyError）；
- akshare 的 stock_zh_index_daily 走新浪，实测稳定可用且量级正确
  （上证50 2904 / 上证指数 3934 / 中证500 7717，与同码深市个股的 2.46/11.85/9.46 完全区分开）。

用法：
  python tools/backfill_index_daily.py                # 默认窗口 400 天，全部指数
  python tools/backfill_index_daily.py --days 60
  python tools/backfill_index_daily.py --dry-run
  python tools/backfill_index_daily.py --days 30 --require-fresh
  python tools/backfill_index_daily.py --days 30 --require-fresh --retry-until 23:15 --retry-interval 900

退出码：
  0  写入完成（--require-fresh 时同时表示已追平 market_latest）
  3  --require-fresh 且到截止时刻仍未追平 market_latest（fail-loud，供 launchd 暴露"跑成功但数据旧"）
  1  参数/连接/未知异常

为什么会有 --require-fresh / --retry-until（2026-09-13 事故，w-32314d00）：
  原 launchd 作业 com.pi-investment.index-daily-refresh 只在工作日 16:30 跑一次。
  实测 2026-09-11 16:30 那次新浪尚未发布当日指数 EOD，脚本把"截至 09-10"的数据
  照单全收、**exit 0**，于是 quant.index_daily 静默停在 09-10：数据契约
  freshness(trade_date, mode=market_latest)（max_lag_days=0，判定器每日 23:40 跑）
  在 09-11、09-12 连续两次判 high 违约（事件 81d8f56c = 000300.SH，
  397def4e244c4d71 = 整表口径）。
  "跑成功但没有新数据"是最危险的形态——没有任何一处会报警。故：
  ① --require-fresh 把"滞后"变成非零退出（launchd 状态/日志可见）；
  ② --retry-until 在该时刻前反复重采（upsert 幂等，多采无害），
     这样无需猜"新浪几点发布当日 EOD"——发布即采到，截至 23:15（契约判定 23:40 之前）。
  定时见 deployment/launchd/com.pi-investment.index-daily-refresh-final.plist（原件留档；
  注意 quantsys-v2/.gitignore 忽略整个 scripts/，定时设置不要放那里）。

陷阱留档：本次修复第一版只补了 000300.SH，严格模式立刻报出**第二个**静默滞后的键
  399300.SZ（深市侧沪深300，2026-09-11 分表时从 daily_klines 迁来的遗留键，
  当时没有任何通道刷新它）——它拖住的是表级契约 quant.index_daily（整表 max）。
  结论：清洗/迁移遗留键必须逐个核实"谁负责刷新它"。
"""
import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

# 指数 → 新浪代码（带市场前缀）
INDEX_SINA = {
    '000001.SH': 'sh000001',  # 上证指数
    '000016.SH': 'sh000016',  # 上证50（歧义码：*ST康佳A）
    '000300.SH': 'sh000300',  # 沪深300
    '000852.SH': 'sh000852',  # 中证1000（歧义码：石化机械）
    '000905.SH': 'sh000905',  # 中证500（歧义码：厦门港务）
    '000906.SH': 'sh000906',  # 中证800
    '399001.SZ': 'sz399001',  # 深证成指
    '399006.SZ': 'sz399006',  # 创业板指
    # 深市侧的沪深300（与 000300.SH 同一指数、同一序列；新浪 sz399300 实测与 sh000300
    # 逐日收盘一致）。它是 2026-09-11 指数分表时从 daily_klines 迁来的遗留键，
    # 且被 utils/symbol_classifier 当作指数码使用——不刷新它，**表级契约
    # quant.index_daily（整表 max(trade_date)）会天天判违约**（2026-09-13 实测：
    # 000300.SH 修好后仍被 399300.SZ 拖住，事件 397def4e244c4d71 就是它）。
    '399300.SZ': 'sz399300',  # 沪深300（深）
}

EXIT_OK = 0
EXIT_STALE = 3

# market_latest 口径与数据契约一致（tools/check_data_contracts.py）：
# quant.daily_klines 中"行数 ≥ 500 的完整交易日"的最大 trade_date（盘中残留个位数行被剔除）
MARKET_MIN_ROWS = 500

UPSERT = """
INSERT INTO quant.index_daily (symbol, trade_date, open, high, low, close, volume, amount, source, updated_at)
VALUES (:symbol, :trade_date, :open, :high, :low, :close, :volume, :amount, :source, now())
ON CONFLICT (symbol, trade_date) DO UPDATE
   SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
       volume = EXCLUDED.volume, amount = EXCLUDED.amount, source = EXCLUDED.source, updated_at = now()
"""


def select_rows(df, cutoff: str, symbol: str, source: str) -> list:
    """DataFrame → 待 upsert 的行（纯函数，便于单测）。

    cutoff（含）之前的行丢弃；date 取前 10 位（新浪返回 '2026-09-11'）。
    """
    rows = []
    for _, r in df[df['date'].astype(str) >= cutoff].iterrows():
        volume = r.get('volume')
        amount = r.get('amount')
        rows.append({
            'symbol': symbol,
            'trade_date': str(r['date'])[:10],
            'open': float(r['open']), 'high': float(r['high']),
            'low': float(r['low']), 'close': float(r['close']),
            'volume': float(volume) if volume == volume and volume is not None else 0.0,
            'amount': float(amount) if amount == amount and amount is not None else 0.0,
            'source': source,
        })
    return rows


def evaluate_freshness(latest_by_symbol: dict, market_latest) -> tuple:
    """严格判定：(是否新鲜, 滞后明细)。

    market_latest 为 None（daily_klines 空/不可读）时不判定滞后——用不可信基准
    判定会制造假告警（对齐 2026-09-10 新鲜度巡检的教训）。
    """
    if not market_latest:
        return True, []
    expected = str(market_latest)[:10]
    stale = [(s, d) for s, d in sorted(latest_by_symbol.items()) if str(d)[:10] < expected]
    return (not stale, [f'{s}: 最新={str(d)[:10]} < market_latest={expected}' for s, d in stale])


def parse_deadline(hhmm, ref: datetime):
    """'23:15' → 今天 23:15；None/空 → None；格式非法 → ValueError。"""
    if not hhmm:
        return None
    hh, _, mm = str(hhmm).partition(':')
    if not (hh.isdigit() and mm.isdigit()) or not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
        raise ValueError(f'--retry-until 需为 HH:MM，收到 {hhmm!r}')
    return ref.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)


def read_market_latest(conn):
    """quant.daily_klines 的 market_latest（完整交易日口径，与契约判定器同源）。"""
    return conn.execute(text("""
        SELECT max(trade_date) FROM (
            SELECT trade_date FROM quant.daily_klines
             GROUP BY trade_date HAVING count(*) >= :min_rows
        ) t
    """), {'min_rows': MARKET_MIN_ROWS}).scalar()


def sync_once(engine, ak, cutoff: str) -> tuple:
    """一轮采集（幂等 upsert）+ 库内真实新鲜度判定 → (写入行数, 是否新鲜, 明细)。

    判定取"库内真实状态"而非本次抓到的行数：部分源失败/空返回都不该被当成功。
    """
    total = 0
    with engine.begin() as conn:
        for symbol, sina_code in INDEX_SINA.items():
            try:
                df = ak.stock_zh_index_daily(symbol=sina_code)
            except Exception as e:  # noqa: BLE001
                print(f"[index] {symbol} 拉取失败: {type(e).__name__}: {str(e)[:80]}")
                continue
            if df is None or df.empty:
                print(f"[index] {symbol} 无数据")
                continue
            rows = select_rows(df, cutoff, symbol, 'sina:stock_zh_index_daily')
            for params in rows:
                conn.execute(text(UPSERT), params)
            total += len(rows)
            last = rows[-1]['trade_date'] if rows else '-'
            print(f"[index] {symbol:10s} ({sina_code}) 写入 {len(rows):4d} 行，最新 {last}")

        db_latest = dict(conn.execute(text(
            "SELECT symbol, max(trade_date) FROM quant.index_daily GROUP BY symbol"
        )).fetchall())
        market_latest = read_market_latest(conn)

    ok, detail = evaluate_freshness({k: str(v) for k, v in db_latest.items()}, market_latest)
    return total, ok, detail, market_latest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=400)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--dsn', default=None)
    ap.add_argument('--require-fresh', action='store_true',
                    help='写入后校验是否追平 quant.daily_klines 的 market_latest，未追平 exit 3')
    ap.add_argument('--retry-until', default=None,
                    help='HH:MM：到该时刻前反复重采，直到追平（配合 --require-fresh）')
    ap.add_argument('--retry-interval', type=int, default=900, help='重试间隔秒数，默认 900')
    args = ap.parse_args()

    import akshare as ak

    engine = create_engine(args.dsn) if args.dsn else create_engine('postgresql+psycopg2:///quant_investment')
    cutoff = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    try:
        deadline = parse_deadline(args.retry_until, datetime.now())
    except ValueError as e:
        print(f"[index] 参数错误：{e}")
        return 1

    attempt = 0
    while True:
        attempt += 1
        print(f"[index] 第 {attempt} 轮采集（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}，窗口 {cutoff}~今天）")
        total, ok, detail, market_latest = sync_once(engine, ak, cutoff)
        print(f"[index] 已写入：合计 {total} 行")
        print(f"[index] freshness: market_latest={str(market_latest)[:10] if market_latest else '未知'}"
              f" → {'OK（全部指数已追平）' if ok else 'STALE'}")
        for d in detail:
            print(f"[index]   STALE {d}")

        if ok or not args.require_fresh:
            return EXIT_OK
        if deadline is None:
            print("[index] --require-fresh 判定滞后且未设 --retry-until → exit 3")
            return EXIT_STALE
        now = datetime.now()
        if now >= deadline:
            print(f"[index] 已到截止时刻 {deadline.strftime('%H:%M')} 仍未追平 → exit 3"
                  f"（源未发布当日 EOD 或采集通道异常，需人工确认）")
            return EXIT_STALE
        wait = min(args.retry_interval, int((deadline - now).total_seconds()))
        print(f"[index] 未追平，{wait}s 后重试（截止 {deadline.strftime('%H:%M')}）")
        time.sleep(max(wait, 1))


if __name__ == '__main__':
    raise SystemExit(main())
