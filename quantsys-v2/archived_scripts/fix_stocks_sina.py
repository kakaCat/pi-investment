"""
修复 stocks 表：名称修正 + 市场数据刷新。
使用新浪财经 API（比东方财富更稳定，周末也可用）。
"""

import os, sys, re, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import urllib3
import psycopg2

from infrastructure.persistence.database.base_repository import _resolve_db_dsn

urllib3.disable_warnings()

# 清除代理环境变量
for _k in list(os.environ.keys()):
    if 'proxy' in _k.lower():
        os.environ.pop(_k, None)


# ═══════════════════════════════════════
# 新浪财经数据获取
# ═══════════════════════════════════════

def build_sina_codes(symbols: list[str]) -> list[str]:
    """将纯数字代码转为新浪格式: sh600519, sz000001, bj430047"""
    codes = []
    for s in symbols:
        s = s.strip()
        if not s:
            continue
        if s.startswith('6'):
            codes.append(f'sh{s}')
        elif s.startswith(('0', '3')):
            codes.append(f'sz{s}')
        elif s.startswith(('4', '8')):
            codes.append(f'bj{s}')
        else:
            codes.append(f'sz{s}')  # fallback
    return codes


def fetch_sina_batch(sina_codes: list[str]) -> list[dict]:
    """
    批量从新浪获取股票数据。
    每批最多 400 只（新浪限制 ~800 只/请求）
    """
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.sina.com.cn',
    })

    results = []
    batch_size = 350  # 保守批量，避免 URL 过长

    for i in range(0, len(sina_codes), batch_size):
        batch = sina_codes[i:i + batch_size]
        url_codes = ','.join(batch)
        url = f'https://hq.sinajs.cn/list={url_codes}'

        try:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                print(f"    ⚠️ 批次 {i//batch_size+1}: HTTP {r.status_code}")
                continue

            # 新浪返回 GBK 编码
            r.encoding = 'gbk'
            text = r.text

            # 解析每一行
            for line in text.strip().split('\n'):
                line = line.strip()
                if not line.startswith('var hq_str_'):
                    continue

                # var hq_str_sz000001="平安银行,10.650,..."
                match = re.match(r'var hq_str_(\w+)="(.+)"', line)
                if not match:
                    continue

                sina_code = match.group(1)
                fields = match.group(2).split(',')

                # 提取纯数字代码
                symbol = sina_code[2:]  # 去掉 sh/sz/bj 前缀

                name = fields[0].strip()
                open_price = _safe_float(fields[1])
                prev_close = _safe_float(fields[2])
                price = _safe_float(fields[3])
                high = _safe_float(fields[4])
                low = _safe_float(fields[5])

                # 退市检测：价格为0且名称为空或异常
                is_delisted = (price == 0 or price is None) and (
                    not name or name == symbol or
                    '退市' in name or 'PT' in name
                )

                results.append({
                    'symbol': symbol,
                    'sina_code': sina_code,
                    'name': name,
                    'price': price,
                    'open': open_price,
                    'prev_close': prev_close,
                    'high': high,
                    'low': low,
                    'is_delisted': is_delisted,
                })

            time.sleep(0.1)  # 避免限流

        except Exception as e:
            print(f"    ⚠️ 批次 {i//batch_size+1} 失败: {e}")
            time.sleep(1)

    return results


def _safe_float(v: str | None) -> float | None:
    if v is None:
        return None
    v = v.strip()
    if v in ('', '-', '--', 'null', 'None'):
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ═══════════════════════════════════════
# 名称标准化
# ═══════════════════════════════════════

_FULLWIDTH = str.maketrans(
    'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
    'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
    '０１２３４５６７８９'
    '（）　',
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    'abcdefghijklmnopqrstuvwxyz'
    '0123456789'
    '() '
)


def normalize_name(name: str) -> str:
    """标准化名称"""
    if not name:
        return name
    name = name.translate(_FULLWIDTH)
    name = re.sub(r'\s+', '', name)  # 删除所有空格
    return name.strip()


def is_valid_name(name: str, symbol: str) -> bool:
    """名称是否有效"""
    if not name or name in ('', 'nan', 'null', 'None'):
        return False
    if name == symbol:
        return False
    if re.match(r'^[0-9]+$', name):
        return False
    return True


# ═══════════════════════════════════════
# 主流程
# ═══════════════════════════════════════

def run():
    dsn = _resolve_db_dsn()
    if not dsn:
        print("❌ 未配置数据库连接")
        sys.exit(1)

    print("=" * 60)
    print("📊 从新浪财经修复 stocks 表")
    print("=" * 60)

    # ── Step 1: 从 DB 获取所有股票代码 ──
    conn = psycopg2.connect(dsn)
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("SELECT symbol, name FROM quant.stocks ORDER BY symbol")
        all_stocks = cur.fetchall()

    db_symbols = [row[0] for row in all_stocks]
    db_names = {row[0]: row[1] for row in all_stocks}

    print(f"\n📋 数据库共 {len(all_stocks)} 只股票")
    name_eq_code = sum(1 for s, n in all_stocks if n == s)
    name_null = sum(1 for s, n in all_stocks if not n or n in ('nan', 'null'))
    print(f"   名称=代码: {name_eq_code} 只")
    print(f"   名称为空: {name_null} 只")

    # ── Step 2: 批量从新浪获取名称 ──
    print(f"\n🌐 从新浪批量获取股票数据...")
    sina_codes = build_sina_codes(db_symbols)
    print(f"   共 {len(sina_codes)} 个新浪代码，分 {len(sina_codes)//350 + 1} 批请求")

    sina_data = fetch_sina_batch(sina_codes)
    sina_map = {s['symbol']: s for s in sina_data}

    print(f"   获取到 {len(sina_data)} 只股票数据")

    # ── Step 3: 分析修复 ──
    name_updates = []       # (symbol, new_name)
    delisted_updates = []   # (symbol, name)
    price_updates = []      # (symbol, price)

    for symbol in db_symbols:
        db_name = db_names.get(symbol, '')
        sina = sina_map.get(symbol)

        if sina:
            sina_name = normalize_name(sina['name'])
            sina_valid = is_valid_name(sina_name, symbol)

            if sina_valid and not is_valid_name(db_name, symbol):
                # 数据库中名称无效，新浪有有效名称 → 修正
                name_updates.append((symbol, sina_name))
            elif not sina_valid and not is_valid_name(db_name, symbol):
                # 双方都没有有效名称 → 标记退市
                delisted_updates.append((symbol, db_name or symbol))

            # 价格更新（如果 DB 中 PE 为 NULL 且新浪有价格）
            if sina['price'] is not None and sina['price'] > 0:
                price_updates.append((symbol, sina['price']))
        else:
            # 新浪也获取不到 → 标记退市（如果名称无效）
            if not is_valid_name(db_name, symbol):
                delisted_updates.append((symbol, db_name or symbol))

    print(f"\n📊 修复计划:")
    print(f"   名称修正: {len(name_updates)} 只 (name=code → 真实名称)")
    print(f"   标记退市: {len(delisted_updates)} 只")
    print(f"   价格更新: {len(price_updates)} 只")

    if name_updates:
        print("\n   名称修正示例:")
        for s, n in name_updates[:10]:
            print(f"     {s}: \"{db_names[s]}\" → \"{n}\"")

    # ── Step 4: 执行修复 ──
    if name_updates or delisted_updates or price_updates:
        conn.autocommit = False

        # 4a: 名称修正
        if name_updates:
            with conn.cursor() as cur:
                for symbol, new_name in name_updates:
                    cur.execute(
                        """UPDATE quant.stocks 
                           SET name = %s, updated_at = NOW() 
                           WHERE symbol = %s""",
                        (new_name, symbol)
                    )
            print(f"\n✅ 已修正 {len(name_updates)} 只股票名称")

        # 4b: 标记退市
        if delisted_updates:
            with conn.cursor() as cur:
                for symbol, _name in delisted_updates:
                    cur.execute(
                        """UPDATE quant.stocks 
                           SET is_suspended = true, updated_at = NOW() 
                           WHERE symbol = %s""",
                        (symbol,)
                    )
            print(f"✅ 已标记 {len(delisted_updates)} 只退市股票")

        # 4c: 价格/PE更新 — stocks 表无 price 列，跳过

        conn.commit()
        conn.close()

        print("\n" + "=" * 60)

        # ── Step 5: 验证 ──
        conn = psycopg2.connect(dsn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE name = symbol) as name_eq_code,
                    COUNT(*) FILTER (WHERE is_suspended = true) as suspended,
                    COUNT(*) FILTER (WHERE industry IS NULL OR industry = '') as no_industry,
                    COUNT(*) FILTER (WHERE pe IS NULL AND is_suspended = false) as pe_null,
                    COUNT(*) FILTER (WHERE roe IS NULL AND is_suspended = false) as roe_null
                FROM quant.stocks
            """)
            row = cur.fetchone()
        conn.close()

        print("📊 修复后统计:")
        print(f"   总股票数:   {row[0]}")
        print(f"   名称=代码:  {row[1]} (之前 {name_eq_code})")
        print(f"   已退市标记: {row[2]}")
        print(f"   行业缺失:   {row[3]} (需交易日补充)")
        print(f"   PE缺失:     {row[4]}")
        print(f"   ROE缺失:    {row[5]}")
        print("=" * 60)

    else:
        conn.close()
        print("\n⚠️ 没有需要修复的数据")


if __name__ == "__main__":
    run()
