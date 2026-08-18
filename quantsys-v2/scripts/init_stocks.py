"""
初始化 A 股全量数据到 PostgreSQL quant.stocks 表。

v3 修复版：
  - 绕过 akshare 的 session/分页问题，直接调东方财富 API
  - 名称标准化（全角→半角、去除多余空格）
  - 对 code==name 的股票，从交易所数据源修正名称
  - 补充行业分类数据
  - 请求间自动延迟，避免限流
"""

import os
import sys
import re
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import psycopg2
from psycopg2.extras import execute_values

from infrastructure.persistence.database.engine import _resolve_db_dsn

# ── 修复代理问题 ──────────────────────────────────────
for _k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
            'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy'):
    os.environ.pop(_k, None)


# ── 东方财富 API 客户端 ──────────────────────────────

class EastMoneyClient:
    """东方财富 API 请求封装，带自动延迟"""

    BASE_URL = "https://82.push2.eastmoney.com/api/qt/clist/get"
    REQUEST_DELAY = 0.3  # 请求间延迟（秒），避免限流

    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.verify = False  # macOS Python 3.13 TLS 兼容问题
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/',
        })
        # 禁用 SSL 警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _get(self, **params) -> dict:
        """发送请求，自动延迟"""
        time.sleep(self.REQUEST_DELAY)
        r = self.session.get(self.BASE_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get('rc') != 0:
            raise RuntimeError(f"API error: {data}")
        return data

    def fetch_all_stocks(self) -> list[dict]:
        """拉取全量 A 股列表（分页）"""
        all_stocks = []
        page = 1
        page_size = 500

        print("    分页拉取中...")
        while True:
            data = self._get(
                pn=str(page),
                pz=str(page_size),
                po="1",
                np="1",
                ut="bd1d9ddb04089700cf9c27f6f7426281",
                fltt="2",
                invt="2",
                fid="f12",
                fs="m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
                fields="f2,f3,f9,f12,f14,f20,f115,f152",
            )

            items = data.get('data', {}).get('diff', [])
            if not items:
                break

            for item in items:
                all_stocks.append({
                    'code': str(item.get('f12', '')).strip(),
                    'name': str(item.get('f14', '')).strip(),
                    'price': _safe_float(item.get('f2')),
                    'pe': _safe_float(item.get('f9')),       # 市盈率(动态)
                    'market_cap': _safe_float(item.get('f20')),  # 总市值
                })

            total = data.get('data', {}).get('total', 0)
            print(f"    第 {page} 页，累计 {len(all_stocks)}/{total} 只", end='\r')
            page += 1

            if len(all_stocks) >= total:
                break

        print(f"\n    共拉取 {len(all_stocks)} 只股票")
        return all_stocks

    def fetch_industry_list(self) -> list[str]:
        """拉取所有行业板块名称"""
        data = self._get(
            pn="1", pz="500",
            po="1", np="1",
            ut="bd1d9ddb04089700cf9c27f6f7426281",
            fltt="2", invt="2",
            fid="f3", fs="m:90 t:2",
            fields="f14",
        )
        items = data.get('data', {}).get('diff', [])
        return [str(item['f14']).strip() for item in items if item.get('f14')]

    def fetch_industry_stocks(self, industry_name: str) -> list[str]:
        """拉取行业板块成分股代码列表"""
        data = self._get(
            pn="1", pz="500",
            po="1", np="1",
            ut="bd1d9ddb04089700cf9c27f6f7426281",
            fltt="2", invt="2",
            fid="f3",
            fs=f"b:{industry_name}",
            fields="f12",
        )
        items = data.get('data', {}).get('diff', [])
        return [str(item['f12']).strip() for item in items if item.get('f12')]


# ── 名称标准化 ──────────────────────────────────────────

_FULLWIDTH_MAP = {
    'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E',
    'Ｆ': 'F', 'Ｇ': 'G', 'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J',
    'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N', 'Ｏ': 'O',
    'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T',
    'Ｕ': 'U', 'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y', 'Ｚ': 'Z',
    'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd', 'ｅ': 'e',
    'ｆ': 'f', 'ｇ': 'g', 'ｈ': 'h', 'ｉ': 'i', 'ｊ': 'j',
    'ｋ': 'k', 'ｌ': 'l', 'ｍ': 'm', 'ｎ': 'n', 'ｏ': 'o',
    'ｐ': 'p', 'ｑ': 'q', 'ｒ': 'r', 'ｓ': 's', 'ｔ': 't',
    'ｕ': 'u', 'ｖ': 'v', 'ｗ': 'w', 'ｘ': 'x', 'ｙ': 'y', 'ｚ': 'z',
    '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
    '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
    '　': '',
    '（': '(', '）': ')',
}


def normalize_name(name: str) -> str:
    """标准化股票名称：全角→半角、去除空格"""
    if not name:
        return name
    for full, half in _FULLWIDTH_MAP.items():
        name = name.replace(full, half)
    name = re.sub(r'\s+', '', name)
    return name.strip()


def is_valid_name(name: str, code: str) -> bool:
    """判断名称是否有效"""
    if not name or name == 'nan':
        return False
    if name == code:
        return False
    if re.match(r'^[0-9]+$', name):
        return False
    return True


def _safe_float(value) -> float | None:
    """安全转换为 float"""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            if value in ('-', '—', '', 'nan'):
                return None
        v = float(value)
        if v != v:
            return None
        return v
    except (ValueError, TypeError):
        return None


# ── 主流程 ────────────────────────────────────────────

def run():
    dsn = _resolve_db_dsn()
    if not dsn:
        print("ERROR: 未配置数据库连接。")
        sys.exit(1)

    print("=" * 60)
    print("A 股全量数据初始化 (v3 直接 API 版)")
    print("=" * 60)

    client = EastMoneyClient()

    # ── Phase 1: 拉取全量股票列表 ──
    print("\n📊 Phase 1: 拉取全量股票列表")
    stocks = client.fetch_all_stocks()
    print(f"   有效股票（名称≠代码）: {sum(1 for s in stocks if is_valid_name(s['name'], s['code']))}/{len(stocks)}")

    # 名称标准化
    for s in stocks:
        s['name'] = normalize_name(s['name'])

    # 统计仍需修复的
    bad_names = [s for s in stocks if not is_valid_name(s['name'], s['code'])]
    print(f"   需要修复名称: {len(bad_names)} 只")

    # ── Phase 2: 修正名称（交易所数据源） ──
    if bad_names:
        print("\n📊 Phase 2: 从交易所数据源修正名称")
        # 尝试用 akshare 的 stock_info_a_code_name（需要 akshare 可用）
        try:
            import akshare as ak
        except ImportError:
            print("    akshare 不可用，跳过交易所名称修正")
            ak = None

        if ak:
            try:
                exchange_df = ak.stock_info_a_code_name()
                if exchange_df is not None and not exchange_df.empty:
                    exchange_names = {}
                    for _, row in exchange_df.iterrows():
                        code = str(row.get('code', '')).strip()
                        name = str(row.get('name', '')).strip()
                        if code and name and name != 'nan':
                            exchange_names[code] = normalize_name(name)
                    print(f"    交易所名称: {len(exchange_names)} 只")

                    fixed = 0
                    for s in stocks:
                        if not s['name'] or s['name'] == s['code']:
                            if s['code'] in exchange_names:
                                s['name'] = exchange_names[s['code']]
                                fixed += 1
                    print(f"    修正: {fixed} 只")
                else:
                    print("    交易所数据为空，跳过")
            except Exception as e:
                print(f"    交易所名称拉取失败: {e}")

    # ── Phase 3: 补充行业分类 ──
    print("\n📊 Phase 3: 补充行业分类数据")
    try:
        industries = client.fetch_industry_list()
        print(f"    行业板块: {len(industries)} 个")

        code_to_industry: dict[str, str] = {}
        for i, ind in enumerate(industries):
            try:
                codes = client.fetch_industry_stocks(ind)
                for c in codes:
                    if c not in code_to_industry:  # 第一个匹配的行业优先
                        code_to_industry[c] = ind
            except Exception as e:
                pass  # 单个行业失败不影响整体

            if (i + 1) % 10 == 0:
                print(f"    进度: {i+1}/{len(industries)}, 已映射 {len(code_to_industry)} 只", end='\r')

        print(f"\n    共映射 {len(code_to_industry)} 只股票到行业")

        # 填充到 stocks
        industry_count = 0
        for s in stocks:
            if s['code'] in code_to_industry:
                s['industry'] = code_to_industry[s['code']]
                industry_count += 1
        print(f"    已补充行业信息: {industry_count}/{len(stocks)} 只")

    except Exception as e:
        print(f"    行业分类拉取失败: {e}")

    # ── Phase 4: 入库 ──
    print("\n📊 Phase 4: 批量入库到 quant.stocks")

    conn = psycopg2.connect(dsn)
    conn.autocommit = False

    records = []
    skipped = 0
    for s in stocks:
        if not is_valid_name(s['name'], s['code']):
            skipped += 1
            continue

        records.append((
            s['code'],
            s['name'],
            'A',
            s.get('industry'),
            s.get('pe'),
            s.get('market_cap'),
        ))

    print(f"    准备 UPSERT: {len(records)} 只（跳过无名称: {skipped} 只）")

    upsert_sql = """
        INSERT INTO quant.stocks (symbol, name, market, industry, pe, market_cap, updated_at)
        VALUES %s
        ON CONFLICT (symbol)
        DO UPDATE SET
            name = EXCLUDED.name,
            market = EXCLUDED.market,
            industry = COALESCE(EXCLUDED.industry, quant.stocks.industry),
            pe = COALESCE(EXCLUDED.pe, quant.stocks.pe),
            market_cap = COALESCE(EXCLUDED.market_cap, quant.stocks.market_cap),
            updated_at = NOW()
    """
    template = "(%s, %s, %s, %s, %s, %s, NOW())"

    with conn.cursor() as cur:
        execute_values(cur, upsert_sql, records, template=template)
        conn.commit()

    conn.close()

    print("\n" + "=" * 60)
    print("✅ 初始化完成！")
    print(f"   入库股票: {len(records)} 只")
    print(f"   跳过（无名称）: {skipped} 只")
    print("=" * 60)


if __name__ == "__main__":
    run()
