"""
补填 quant.stocks 空列：
  - circulating_mv: 腾讯财经批量接口（qt.gtimg.cn，字段45=流通市值亿元）
  - list_date: 东方财富 emweb 单股接口（fxxg.ssrq）
  - (total_mv 已由 SQL 复制 market_cap 完成)

腾讯接口限制：≥50只/次批量，请求间隔 0.1s。
emweb 接口限制：单股，请求间隔 0.3s（约 48min 跑完 5800只）。

用法：
  python scripts/backfill_stocks.py               # 全跑
  python scripts/backfill_stocks.py --skip-circulating  # 只跑 list_date
  python scripts/backfill_stocks.py --skip-list-date     # 只跑 circulating_mv
  python scripts/backfill_stocks.py --resume-list-date    # 断点续传 list_date
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import psycopg2
from psycopg2.extras import execute_values

from infrastructure.persistence.database.engine import _resolve_db_dsn

# ── 环境净化 ──────────────────────────────────────────
for _k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
            'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy'):
    os.environ.pop(_k, None)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── 配置 ──────────────────────────────────────────────
TENCENT_BATCH_SIZE = 50       # 每批请求股票数
TENCENT_DELAY = 0.12          # 批次间延迟（秒）
EMWEB_DELAY = 0.30            # 单股延迟（秒）
PROGRESS_FILE = Path(__file__).parent.parent / ".backfill_list_date_progress.json"
REQUEST_TIMEOUT = 10


# ── 数据库 ────────────────────────────────────────────
def get_conn():
    dsn = _resolve_db_dsn()
    if not dsn:
        raise RuntimeError("未配置数据库连接")
    return psycopg2.connect(dsn)


def get_symbols_to_fill(conn, column: str) -> list[str]:
    """获取需要补填的股票代码列表"""
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT symbol FROM quant.stocks
            WHERE {column} IS NULL
            ORDER BY symbol
        """)
        return [row[0] for row in cur.fetchall()]


# ── Phase A: 腾讯财经 → circulating_mv ─────────────────

def fetch_tencent_batch(symbols: list[str]) -> dict[str, float | None]:
    """
    批量调用腾讯财经行情接口。
    返回 {symbol: circulating_mv_亿元}，None=未获取到。
    """
    # 转换 symbol 格式: 600519 → sh600519, 000858 → sz000858
    tencent_codes = []
    for s in symbols:
        if s.startswith(('6', '9')):
            tencent_codes.append(f'sh{s}')
        else:
            tencent_codes.append(f'sz{s}')

    url = f"https://qt.gtimg.cn/q={','.join(tencent_codes)}"
    
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT,
                        headers={'User-Agent': 'Mozilla/5.0'})
        r.encoding = 'gbk'
    except Exception as e:
        print(f"    [腾讯API] 请求失败: {e}")
        return {}

    results = {}
    for line in r.text.strip().split('\n'):
        if not line.strip() or '="' not in line:
            continue
        try:
            # v_sh600519="1~贵州茅台~600519~...~"
            code_part = line.split('="')[1].rstrip('";\n')
            fields = code_part.split('~')
            if len(fields) < 46:
                continue
            symbol = fields[2]  # 600519
            # field 45 = 流通市值（亿元）
            cmv = _safe_float(fields[45])
            results[symbol] = cmv
        except (IndexError, ValueError):
            continue

    return results


def backfill_circulating_mv(conn):
    print("\n" + "=" * 60)
    print("Phase A: 补填 circulating_mv（腾讯财经批量接口）")
    print("=" * 60)

    symbols = get_symbols_to_fill(conn, 'circulating_mv')
    if not symbols:
        print("    ✅ circulating_mv 已全部填充！")
        return

    print(f"    待填充: {len(symbols)} 只")
    
    # 批量获取
    all_data: dict[str, float | None] = {}
    batch_count = (len(symbols) + TENCENT_BATCH_SIZE - 1) // TENCENT_BATCH_SIZE
    
    for i in range(0, len(symbols), TENCENT_BATCH_SIZE):
        batch = symbols[i:i + TENCENT_BATCH_SIZE]
        batch_num = i // TENCENT_BATCH_SIZE + 1
        
        data = fetch_tencent_batch(batch)
        all_data.update(data)
        
        if batch_num % 20 == 0 or batch_num == batch_count:
            print(f"    进度: {min(i + TENCENT_BATCH_SIZE, len(symbols))}/{len(symbols)}"
                  f" ({batch_num}/{batch_count}), 获取 {len(all_data)} 只", end='\r')
        time.sleep(TENCENT_DELAY)
    
    print(f"\n    共获取 {len(all_data)}/{len(symbols)} 只")
    
    # 入库
    records = [(sym, cmv) for sym, cmv in all_data.items() if cmv is not None]
    with conn.cursor() as cur:
        execute_values(cur, """
            UPDATE quant.stocks AS s
            SET circulating_mv = v.cmv, updated_at = NOW()
            FROM (VALUES %s) AS v(symbol, cmv)
            WHERE s.symbol = v.symbol
        """, records, template="(%s, %s::double precision)")
    conn.commit()
    
    print(f"    入库: {len(records)} 只")
    
    # 验证
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM quant.stocks WHERE circulating_mv IS NOT NULL")
        filled = cur.fetchone()[0]
    print(f"    验证: {filled}/{get_total(conn)} 只有 circulating_mv")


# ── Phase B: 东方财富 emweb → list_date ────────────────

def fetch_emweb(symbol: str) -> dict:
    """调用东方财富 emweb 公司概况接口"""
    # 转换: 600519 → SH600519, 000858 → SZ000858
    if symbol.startswith(('6', '9')):
        code = f'SH{symbol}'
    else:
        code = f'SZ{symbol}'

    url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax?code={code}"
    
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                            'Referer': 'https://emweb.securities.eastmoney.com/',
                        })
        data = r.json()
    except Exception as e:
        return {'error': str(e)}

    result = {}
    fxxg = data.get('fxxg', {})
    if fxxg.get('ssrq'):
        result['list_date'] = str(fxxg['ssrq']).strip()

    jbzl = data.get('jbzl', {})
    if jbzl.get('sshy'):
        result['industry'] = str(jbzl['sshy']).strip()

    return result


def _is_valid_date(val: str) -> bool:
    """校验是否为合法日期 YYYY-MM-DD"""
    if not val or not isinstance(val, str):
        return False
    val = val.strip()
    if val in ('--', '-', '', 'N/A', 'null', 'None'):
        return False
    import re
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', val))


def backfill_list_date(conn, resume=False):
    print("\n" + "=" * 60)
    print("Phase B: 补填 list_date（东方财富 emweb 接口）")
    print("=" * 60)

    symbols = get_symbols_to_fill(conn, 'list_date')
    if not symbols:
        print("    ✅ list_date 已全部填充！")
        return

    # 断点续传
    completed = set()
    if resume and PROGRESS_FILE.exists():
        completed = set(json.loads(PROGRESS_FILE.read_text()))
        symbols = [s for s in symbols if s not in completed]
        print(f"    断点续传: {len(completed)} 已完成, 剩余 {len(symbols)}")

    print(f"    待填充: {len(symbols)} 只 (预计 {len(symbols) * EMWEB_DELAY / 60:.0f} min)")

    batch = []
    failed = 0

    for i, symbol in enumerate(symbols):
        try:
            data = fetch_emweb(symbol)
        except Exception as e:
            if failed < 5:
                print(f"\n    [{symbol}] 异常: {e}")
            failed += 1
            data = {}

        ld = data.get('list_date', '')
        if _is_valid_date(ld):
            batch.append((symbol, ld))

        completed.add(symbol)

        # 进度
        if (i + 1) % 100 == 0:
            print(f"    进度: {i+1}/{len(symbols)} ({(i+1)*100//len(symbols)}%), "
                  f"已获 {len(batch)} 条, 失败 {failed}", end='\r')

            # 批量入库
            _upsert_list_date_batch(conn, batch)
            batch = []

            # 保存进度
            PROGRESS_FILE.write_text(json.dumps(list(completed)))

        time.sleep(EMWEB_DELAY)

    # 最后一批
    if batch:
        _upsert_list_date_batch(conn, batch)
    PROGRESS_FILE.write_text(json.dumps(list(completed)))

    print(f"\n    完成: {len(completed)} 只")

    # 验证
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM quant.stocks WHERE list_date IS NOT NULL")
        filled = cur.fetchone()[0]
    print(f"    验证: {filled}/{get_total(conn)} 只有 list_date")

    # 清理进度文件
    PROGRESS_FILE.unlink(missing_ok=True)


def _upsert_list_date_batch(conn, batch):
    """批量 UPSERT list_date（已过滤非法日期）"""
    if not batch:
        return
    records = [(sym, ld) for sym, ld in batch if _is_valid_date(ld)]
    if not records:
        return
    try:
        with conn.cursor() as cur:
            execute_values(cur, """
                UPDATE quant.stocks AS s
                SET list_date = v.ld::date, updated_at = NOW()
                FROM (VALUES %s) AS v(symbol, ld)
                WHERE s.symbol = v.symbol
                  AND s.list_date IS NULL
            """, records, template="(%s, %s)")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\n    [WARN] 批量入库失败: {e}, 跳过本批")
        # 逐个重试
        for sym, ld in records:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE quant.stocks SET list_date = %s::date, updated_at = NOW()
                        WHERE symbol = %s AND list_date IS NULL
                    """, (ld, sym))
                conn.commit()
            except Exception:
                conn.rollback()


# ── 工具函数 ──────────────────────────────────────────
def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip()
            if value in ('', '-', '—', 'nan', 'null'):
                return None
        v = float(value)
        return v if v == v else None
    except (ValueError, TypeError):
        return None


def get_total(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM quant.stocks")
        return cur.fetchone()[0]


# ── 主入口 ────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='补填 quant.stocks 空列')
    parser.add_argument('--skip-circulating', action='store_true', help='跳过 circulating_mv')
    parser.add_argument('--skip-list-date', action='store_true', help='跳过 list_date')
    parser.add_argument('--resume-list-date', action='store_true', help='断点续传 list_date')
    args = parser.parse_args()

    conn = get_conn()
    
    try:
        # 当前状态
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) AS total,
                    COUNT(total_mv) AS tmv,
                    COUNT(circulating_mv) AS cmv,
                    COUNT(list_date) AS ld,
                    COUNT(avg_turnover_rate) AS atr
                FROM quant.stocks
            """)
            total, tmv, cmv, ld, atr = cur.fetchone()
        
        print(f"当前状态: total={total} total_mv={tmv} circulating_mv={cmv} "
              f"list_date={ld} avg_turnover_rate={atr}")

        if not args.skip_circulating:
            backfill_circulating_mv(conn)

        if not args.skip_list_date:
            backfill_list_date(conn, resume=args.resume_list_date)

        # 最终状态
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) AS total,
                    COUNT(total_mv) AS tmv,
                    COUNT(circulating_mv) AS cmv,
                    COUNT(list_date) AS ld,
                    COUNT(avg_turnover_rate) AS atr
                FROM quant.stocks
            """)
            total, tmv, cmv, ld, atr = cur.fetchone()
        
        print("\n" + "=" * 60)
        print(f"✅ 完成！")
        print(f"   total_mv:       {tmv}/{total}")
        print(f"   circulating_mv: {cmv}/{total}")
        print(f"   list_date:      {ld}/{total}")
        print(f"   avg_turnover_rate: {atr}/{total} (需 K 线换手率数据)")
        print("=" * 60)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
