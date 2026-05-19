#!/usr/bin/env python3
"""
AkShare Bridge - TypeScript -> Python -> akshare

Usage:
    python3 akshare_bridge.py <function_name> [json_args]

Example:
    python3 akshare_bridge.py get_stock_info '{"symbol": "600519"}'
    python3 akshare_bridge.py get_sector_list '{}'
"""
import sys
import json
import traceback
import os
import signal
import math
from functools import wraps
from datetime import datetime
import logging

# 禁用 tqdm 进度条（避免污染 stdout）
os.environ['TQDM_DISABLE'] = '1'

# Add path to quant module for strategy combiner
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'quant'))

from quantsys.strategies.combiner import StrategyCombiner, Signal as CombinerSignal, CombinerConfig
from risk_bridge import RiskBridge

# Setup logger
logger = logging.getLogger(__name__)


# ===== JSON 序列化辅助函数 =====
def clean_nan_values(obj):
    """
    递归清理对象中的 NaN 和 Infinity 值，转换为 None
    """
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj


def json_serializer(obj):
    """
    自定义 JSON 序列化器，处理不可序列化对象
    """
    return str(obj)


def safe_json_dumps(obj, **kwargs):
    """
    安全的 JSON 序列化，自动处理 NaN/Infinity
    """
    # 先清理 NaN/Infinity
    cleaned_obj = clean_nan_values(obj)

    kwargs.setdefault('ensure_ascii', False)
    kwargs.setdefault('default', json_serializer)
    return json.dumps(cleaned_obj, **kwargs)


# ===== 超时装饰器 =====
def timeout_decorator(seconds=30):
    """为函数添加超时控制（仅 Unix 系统）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")

            # 设置信号处理器
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                # 恢复原信号处理器
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result
        return wrapper
    return decorator


def _safe_float(val, default=0.0, decimals=2):
    try:
        import math
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return default
        return round(v, decimals)
    except (ValueError, TypeError):
        return default


def _clean_symbol(symbol):
    return symbol.replace("sh", "").replace("sz", "").replace("bj", "").strip()


def _sina_symbol(symbol):
    """将6位A股代码转为新浪格式 (sh600519 / sz000858 / bj830946)"""
    s = _clean_symbol(symbol)
    if s.startswith("6"):
        return f"sh{s}"
    elif s.startswith(("0", "3")):
        return f"sz{s}"
    elif s.startswith(("8", "4")):
        return f"bj{s}"
    return f"sh{s}"


def _is_hk_symbol(symbol: str) -> bool:
    """检测是否为港股代码（1-5位数字，或含 .HK 后缀）"""
    s = symbol.upper().strip()
    if s.endswith(".HK"):
        s = s[:-3]
    return s.isdigit() and 1 <= len(s) <= 5


def _hk_code(symbol: str) -> str:
    """标准化港股代码为5位带前导零格式（9988 → 09988，0700 → 00700）"""
    s = symbol.upper().strip()
    if s.endswith(".HK"):
        s = s[:-3]
    return s.zfill(5)

# ===== Sina HTTP helpers =====

def _sina_request(url: str, params: dict = None) -> "object":
    import requests as _req, time as _time
    h = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
    for attempt in range(3):
        try:
            return _req.get(url, params=params, headers=h, timeout=10)
        except Exception:
            if attempt < 2:
                _time.sleep(1)
            else:
                raise


def _parse_sina_realtime(raw: str) -> dict:
    """解析新浪A股实时行情字符串"""
    import re
    m = re.search(r'"([^"]*)"', raw)
    if not m:
        return {}
    fields = m.group(1).strip().split(",")
    if len(fields) < 32:
        return {}
    return {
        "name": fields[0], "open": fields[1], "prev_close": fields[2],
        "price": fields[3], "high": fields[4], "low": fields[5],
        "volume": fields[8], "amount": fields[9],
        "date": fields[30], "time": fields[31],
    }


def _parse_sina_hk_realtime(raw: str) -> dict:
    """解析新浪港股实时行情字符串"""
    import re
    m = re.search(r'"([^"]*)"', raw)
    if not m:
        return {}
    fields = m.group(1).strip().split(",")
    if len(fields) < 8:
        return {}
    return {
        "name": fields[0], "prev_close": fields[2], "open": fields[3],
        "high": fields[4], "low": fields[5], "price": fields[6],
        "change_amount": fields[7],
        "change_pct": fields[8] if len(fields) > 8 else "0",
        "volume": fields[9] if len(fields) > 9 else "0",
        "amount": fields[10] if len(fields) > 10 else "0",
    }


# ===== HK stock functions =====

def get_hk_stock_price(symbol: str) -> dict:
    """港股实时行情（via 新浪）"""
    from datetime import datetime
    code = _hk_code(symbol)
    try:
        r = _sina_request(f"https://hq.sinajs.cn/list=hk{code}")
        r.encoding = "gbk"
        fields = _parse_sina_hk_realtime(r.text)
        if not fields or not fields.get("price"):
            return {"error": f"未找到港股: {symbol} (code={code})"}
        return {
            "symbol": code, "name": fields["name"],
            "price": _safe_float(fields["price"]),
            "change_pct": _safe_float(fields["change_pct"]),
            "change_amount": _safe_float(fields["change_amount"]),
            "volume": _safe_float(fields["volume"], decimals=0),
            "amount": _safe_float(fields["amount"], decimals=0),
            "high": _safe_float(fields["high"]), "low": _safe_float(fields["low"]),
            "open": _safe_float(fields["open"]), "prev_close": _safe_float(fields["prev_close"]),
            "market": "HK",
            "data_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_hk_stock_info(symbol: str) -> dict:
    """港股基本信息（via 新浪实时行情）"""
    from datetime import datetime
    code = _hk_code(symbol)
    try:
        price_data = get_hk_stock_price(symbol)
        if "error" in price_data:
            return price_data
        return {
            "symbol": code, "name": price_data["name"],
            "market": "HK", "price": price_data["price"],
            "change_pct": price_data["change_pct"],
            "pe_ttm": 0.0, "pb": 0.0, "market_cap_billion": 0.0,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_hk_stock_history(symbol: str, period: str = "daily", start_date: str = None, end_date: str = None, adjust: str = "qfq") -> dict:
    """港股历史行情（via stooq），最多返回60条"""
    import requests as _req
    import io
    from datetime import datetime
    code = _hk_code(symbol)
    # stooq interval: d=daily, w=weekly, m=monthly
    interval_map = {"daily": "d", "weekly": "w", "monthly": "m"}
    interval = interval_map.get(period, "d")
    # strip leading zeros for stooq (09988 -> 9988)
    stooq_code = str(int(code))
    try:
        r = _req.get(
            f"https://stooq.com/q/d/l/",
            params={"s": f"{stooq_code}.hk", "i": interval},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            return {"error": f"无历史数据: {symbol}"}
        # CSV: Date,Open,High,Low,Close,Volume
        records = []
        prev_close = None
        for line in lines[1:][-60:]:  # skip header, last 60
            parts = line.strip().split(",")
            if len(parts) < 5:
                continue
            close = _safe_float(parts[4])
            change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            records.append({
                "date": parts[0],
                "open": _safe_float(parts[1]),
                "high": _safe_float(parts[2]),
                "low": _safe_float(parts[3]),
                "close": close,
                "volume": _safe_float(parts[5] if len(parts) > 5 else 0, decimals=0),
                "change_pct": change_pct,
            })
            prev_close = close
        if not records:
            return {"error": f"无历史数据: {symbol}"}
        return {
            "symbol": code, "period": period, "count": len(records),
            "market": "HK", "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ===== All stock functions =====

def _sina_stock_history(symbol: str, datalen: int = 60, scale: int = 240) -> list:
    """通过新浪获取A股历史K线，返回 list of dict"""
    import json as _json
    sina_sym = _sina_symbol(symbol)
    r = _sina_request(
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
        params={"symbol": sina_sym, "scale": scale, "ma": "no", "datalen": datalen}
    )
    return _json.loads(r.text) or []


def get_stock_info(symbol: str) -> dict:
    """A股基本信息（via emweb + 新浪实时）"""
    import requests as _req
    import time as _time
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        # emweb company survey with retry
        mkt = "SH" if symbol.startswith("6") else ("BJ" if symbol.startswith(("8", "4")) else "SZ")
        r = None
        for attempt in range(3):
            try:
                r = _req.get(
                    f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={mkt}{symbol}",
                    timeout=10
                )
                break
            except Exception:
                if attempt < 2:
                    _time.sleep(1)
                else:
                    raise
        d = r.json()
        jbzl = d.get("jbzl", [{}])[0]
        name = jbzl.get("SECURITY_NAME_ABBR", "")
        sector = jbzl.get("EM2016", "")
        # realtime for pe/pb/mktcap
        rt = get_stock_realtime_price(symbol)
        return {
            "symbol": symbol, "name": name, "sector": sector,
            "pe_ttm": rt.get("pe_dynamic", 0.0),
            "pb": rt.get("pb", 0.0),
            "market_cap_billion": rt.get("market_cap_billion", 0.0),
            "total_shares": str(jbzl.get("REG_CAPITAL", "")),
            "circulating_shares": "",
            "listed_date": str(jbzl.get("LISTING_DATE", ""))[:10] if jbzl.get("LISTING_DATE") else "",
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def _fetch_em_quote(symbol: str) -> dict:
    """从东财接口获取PE/PB/市值

    主：datacenter-web RPT_VALUEANALYSIS_DET（可用）
    降级：emweb CompanySurvey 的 zycwzb 字段
    注意：push2.eastmoney.com 在本机被封锁，不使用

    返回值始终包含 pe_source 字段说明数据来源：
      "datacenter"   - 方案1成功
      "emweb"        - 方案2成功
      "unavailable"  - 全部失败，pe_dynamic/pb/market_cap_billion 均为 0
    """
    import requests as _req
    mkt = "SH" if symbol.startswith("6") else ("BJ" if symbol.startswith(("8", "4")) else "SZ")
    h = {"Referer": "https://finance.eastmoney.com", "User-Agent": "Mozilla/5.0"}

    # 方案1：datacenter-web 股票快照接口（含PE/PB/总市值）
    try:
        r = _req.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "reportName": "RPT_VALUEANALYSIS_DET",
                "columns": "SECUCODE,PE_TTM,PB_MRQ,TOTAL_MARKET_CAP",
                "filter": f'(SECUCODE="{symbol}.{mkt}")',
                "pageSize": 1,
            },
            headers=h,
            timeout=8,
        )
        d = r.json()
        if d.get("success") and d.get("result", {}).get("data"):
            row = d["result"]["data"][0]
            pe = _safe_float(row.get("PE_TTM", 0), decimals=2)
            pb = _safe_float(row.get("PB_MRQ", 0), decimals=2)
            mc = _safe_float(row.get("TOTAL_MARKET_CAP", 0), decimals=0)
            if pe > 0 or pb > 0:
                return {
                    "pe_dynamic": pe if pe > 0 else 0.0,
                    "pb": pb if pb > 0 else 0.0,
                    "market_cap_billion": round(mc / 1e8, 2) if mc > 0 else 0.0,
                    "pe_source": "datacenter",
                }
    except Exception:
        pass

    # 方案2：emweb CompanySurvey zycwzb（关键财务指标，含PE/PB）
    try:
        r2 = _req.get(
            f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={mkt}{symbol}",
            timeout=8,
        )
        d2 = r2.json()
        zycwzb = d2.get("zycwzb", [{}])
        if zycwzb:
            latest = zycwzb[0]
            pe = _safe_float(latest.get("PE", latest.get("pe", 0)), decimals=2)
            pb = _safe_float(latest.get("PB", latest.get("pb", 0)), decimals=2)
            if pe > 0 or pb > 0:
                return {
                    "pe_dynamic": pe if pe > 0 else 0.0,
                    "pb": pb if pb > 0 else 0.0,
                    "market_cap_billion": 0.0,
                    "pe_source": "emweb",
                }
    except Exception:
        pass

    # 全部失败：明确标记数据不可用，下游函数可据此判断
    return {
        "pe_dynamic": 0.0,
        "pb": 0.0,
        "market_cap_billion": 0.0,
        "pe_source": "unavailable",
    }


def get_stock_realtime_price(symbol: str) -> dict:
    """A股实时行情（via 新浪行情 + 东财PE/PB补充）"""
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        sina_sym = _sina_symbol(symbol)
        r = _sina_request(f"https://hq.sinajs.cn/list={sina_sym}")
        r.encoding = "gbk"
        fields = _parse_sina_realtime(r.text)
        if not fields or not fields.get("price"):
            return {"error": f"未找到: {symbol}"}
        price = _safe_float(fields["price"])
        prev_close = _safe_float(fields["prev_close"])
        change_amount = round(price - prev_close, 3)
        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
        volume = _safe_float(fields["volume"], decimals=0)  # 手
        amount = _safe_float(fields["amount"], decimals=0)
        # 补充 PE/PB/市值（新浪行情不含这些字段）
        em_data = _fetch_em_quote(symbol)
        return {
            "symbol": symbol, "name": fields["name"],
            "price": price, "change_pct": change_pct, "change_amount": change_amount,
            "volume": volume, "amount": amount,
            "high": _safe_float(fields["high"]), "low": _safe_float(fields["low"]),
            "open": _safe_float(fields["open"]), "prev_close": prev_close,
            "turnover_rate": 0.0,
            "pe_dynamic": em_data["pe_dynamic"],
            "pb": em_data["pb"],
            "market_cap_billion": em_data["market_cap_billion"],
            "data_date": f"{fields['date']} {fields['time']}",
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_batch_realtime_prices(symbols: list) -> dict:
    """批量获取实时价格（优化版：一次请求获取多个股票）"""
    from datetime import datetime
    if not symbols or len(symbols) == 0:
        return {"prices": {}, "errors": [], "timestamp": datetime.now().isoformat()}

    # 清理股票代码
    cleaned_symbols = [_clean_symbol(s) for s in symbols]

    # 构建新浪批量请求（最多100个股票一次请求）
    prices = {}
    errors = []

    # 分批处理（每批100个）
    batch_size = 100
    for i in range(0, len(cleaned_symbols), batch_size):
        batch = cleaned_symbols[i:i+batch_size]
        sina_symbols = [_sina_symbol(s) for s in batch]
        symbols_str = ",".join(sina_symbols)

        try:
            r = _sina_request(f"https://hq.sinajs.cn/list={symbols_str}")
            r.encoding = "gbk"
            lines = r.text.strip().split("\n")

            for idx, line in enumerate(lines):
                if idx >= len(batch):
                    break

                symbol = batch[idx]
                fields = _parse_sina_realtime(line)

                if fields and fields.get("price"):
                    price = _safe_float(fields["price"])
                    if price > 0:
                        prices[symbol] = price
                    else:
                        errors.append({"symbol": symbol, "error": "价格为0"})
                else:
                    errors.append({"symbol": symbol, "error": "未找到数据"})

        except Exception as e:
            for symbol in batch:
                errors.append({"symbol": symbol, "error": str(e)})

    return {
        "prices": prices,
        "errors": errors,
        "count": len(prices),
        "timestamp": datetime.now().isoformat()
    }


def get_stock_history(symbol: str, period: str = "daily", start_date: str = None, end_date: str = None, adjust: str = "qfq") -> dict:
    """A股历史行情（via 新浪 getKLineData）"""
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    scale_map = {"daily": 240, "weekly": 1200, "monthly": 4800}
    scale = scale_map.get(period, 240)
    try:
        raw = _sina_stock_history(symbol, datalen=60, scale=scale)
        if not raw:
            return {"error": f"无历史数据: {symbol}"}
        records = []
        prev_close = None
        for item in raw:
            close = _safe_float(item.get("close", 0))
            change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            records.append({
                "date": item.get("day", ""),
                "open": _safe_float(item.get("open", 0)),
                "high": _safe_float(item.get("high", 0)),
                "low": _safe_float(item.get("low", 0)),
                "close": close,
                "volume": _safe_float(item.get("volume", 0), decimals=0),
                "change_pct": change_pct,
            })
            prev_close = close
        return {"symbol": symbol, "period": period, "count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_financial_indicators(symbol: str) -> dict:
    import akshare as ak
    import sys, traceback
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        df = ak.stock_financial_abstract_ths(symbol=symbol, indicator='按报告期')
        if df.empty:
            return {"error": f"无财务数据: {symbol}"}

        # akshare 返回宽格式：每行一个报告期，每列一个指标
        # 数据按时间正序排列，取最后4个报告期（最新的）
        df = df.tail(4).iloc[::-1]  # 取最后4行并反转，使最新的在前
        quarters = []

        for _, row in df.iterrows():
            # 提取关键指标，处理百分比字符串
            def parse_pct(val):
                if isinstance(val, str) and '%' in val:
                    return _safe_float(val.replace('%', ''))
                return _safe_float(val)

            quarters.append({
                "report_date": str(row['报告期']),
                "roe": parse_pct(row.get('净资产收益率', 0)),
                "gross_margin": parse_pct(row.get('销售毛利率', 0)),
                "net_margin": parse_pct(row.get('销售净利率', 0)),
                "debt_ratio": parse_pct(row.get('资产负债率', 0)),
                "current_ratio": _safe_float(row.get('流动比率', 0)),
            })

        result = {"symbol": symbol, "quarters": quarters, "data": quarters, "data_date": datetime.now().strftime("%Y-%m-%d")}
        sys.stderr.write(f"[DEBUG] get_financial_indicators OK for {symbol}, {len(quarters)} quarters\n")
        sys.stderr.flush()
        return result
    except Exception as e:
        tb = traceback.format_exc()
        sys.stderr.write(f"[DEBUG] get_financial_indicators ERROR for {symbol}: {e}\n{tb}\n")
        sys.stderr.flush()
        return {"error": str(e), "symbol": symbol}


def get_sector_list() -> dict:
    """获取行业板块列表及今日涨跌幅

    数据来源：东方财富网行业资金流向接口
    返回：行业名称、板块指数、今日涨跌幅
    """
    from datetime import datetime
    try:
        import akshare as ak
        df = ak.stock_fund_flow_industry(symbol='即时')
        if df is None or df.empty:
            return {"error": "板块数据暂时不可用", "count": 0, "data": []}
        records = []
        for _, row in df.iterrows():
            records.append({
                "name": str(row.get('行业', '')),
                "code": "",
                "count": int(row.get('公司家数', 0)) if row.get('公司家数') else 0,
                "change_pct": float(row.get('行业-涨跌幅', 0)) if row.get('行业-涨跌幅') else 0,
            })
        return {"count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "count": 0, "data": []}


def screen_stocks_by_sector(sector: str, min_roe: float = None, max_pe: float = None, limit: int = 20) -> dict:
    """按板块筛选股票（东方财富行业板块）

    注意：此功能依赖东方财富网API，可能因网络问题或API变更而不可用
    """
    import akshare as ak
    from datetime import datetime

    try:
        # 获取板块成分股
        df = ak.stock_board_industry_cons_em(symbol=sector)

        if df is None or df.empty:
            return {
                "error": f"未找到板块: {sector}",
                "sector": sector,
                "suggestion": "使用 get_stock_info 查询个股信息"
            }

        # 提取基本信息
        results = []
        for _, row in df.head(limit).iterrows():
            stock = {
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": float(row.get("最新价", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
            }

            # 如果有PE和ROE数据，添加过滤
            if "市盈率-动态" in row:
                stock["pe"] = float(row.get("市盈率-动态", 0))
            if "净资产收益率" in row:
                stock["roe"] = float(row.get("净资产收益率", 0))

            results.append(stock)

        # 应用过滤条件
        if max_pe is not None:
            results = [s for s in results if s.get("pe", 0) > 0 and s["pe"] <= max_pe]
        if min_roe is not None:
            results = [s for s in results if s.get("roe", 0) >= min_roe]

        return {
            "sector": sector,
            "count": len(results),
            "data": results[:limit],
            "data_date": datetime.now().strftime("%Y-%m-%d")
        }

    except Exception as e:
        error_msg = str(e)
        if "Connection" in error_msg or "Proxy" in error_msg or "Remote" in error_msg:
            return {
                "error": f"网络连接失败，无法获取板块数据: {sector}",
                "sector": sector,
                "suggestion": "请检查网络连接或稍后重试。建议使用 get_stock_info 查询个股信息",
                "technical_error": error_msg[:200]
            }
        else:
            return {
                "error": f"板块筛选失败: {error_msg[:200]}",
                "sector": sector,
                "suggestion": "使用 get_stock_info 查询个股信息"
            }


def screen_stocks_quality(sector: str, min_score: int = 50, max_pe: float = None, limit: int = 10) -> dict:
    """选股+质量评分一步完成：先按板块筛选，再对每只股票打质量分，返回按评分排序的候选列表"""
    from datetime import datetime
    try:
        # 第一步：获取板块股票列表
        raw = screen_stocks_by_sector(sector, max_pe=max_pe, limit=30)
        if "error" in raw:
            # Fallback: 模糊匹配行业名
            import akshare as ak
            try:
                sectors_df = ak.stock_board_industry_name_em()
                if sectors_df is not None and not sectors_df.empty:
                    all_sectors = sectors_df['板块名称'].tolist()
                    matches = [s for s in all_sectors if sector in s or s in sector]
                    if matches:
                        return {"error": f"未找到板块: {sector}", "sector": sector,
                                "suggestions": matches[:5], "hint": "请使用建议的板块名重试"}
            except:
                pass
            return raw
        candidates = raw.get("data", [])
        if not candidates:
            return {"error": f"板块无候选股票: {sector}", "sector": sector}

        # 第二步：对每只股票打质量分（取前30只，避免太慢）
        scored = []
        for stock in candidates[:30]:
            sym = str(stock.get("code", stock.get("symbol", "")))
            if not sym:
                continue
            try:
                qs = get_quality_score(sym)
                if "error" not in qs:
                    scored.append({
                        "symbol": sym,
                        "name": stock.get("name", qs.get("symbol", sym)),
                        "pe": stock.get("pe", 0),
                        "price": stock.get("price", 0),
                        "score": qs["score"],
                        "grade": qs["grade"],
                        "roe": qs["details"].get("roe", 0),
                        "debt_ratio": qs["details"].get("debt_ratio", 0),
                        "gross_margin": qs["details"].get("gross_margin", 0),
                    })
            except Exception:
                continue

        # 第三步：过滤 + 排序
        filtered = [s for s in scored if s["score"] >= min_score]
        filtered.sort(key=lambda x: x["score"], reverse=True)
        result = filtered[:limit]

        return {
            "sector": sector,
            "total_screened": len(candidates),
            "qualified": len(filtered),
            "min_score": min_score,
            "data": result,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "sector": sector}


def get_stock_news(symbol: str, num: int = 10) -> dict:
    """个股新闻 (东方财富 + 新浪财经 + 网页抓取，多源汇总)"""
    import akshare as ak
    from datetime import datetime
    raw = _clean_symbol(symbol)
    # stock_news_em 要求大写带市场前缀，如 SH601857 / SZ000858
    if raw.startswith("6"):
        em_symbol = f"SH{raw}"
    elif raw.startswith(("0", "3")):
        em_symbol = f"SZ{raw}"
    elif raw.startswith(("8", "4")):
        em_symbol = f"BJ{raw}"
    else:
        em_symbol = raw

    result = {"symbol": raw, "sources": [], "data": [],
              "data_date": datetime.now().strftime("%Y-%m-%d")}

    # 1. 东方财富 API
    try:
        df = ak.stock_news_em(symbol=em_symbol)
        if df is not None and not df.empty:
            records = [{"title": str(row.get("新闻标题", "")), "date": str(row.get("发布时间", "")),
                        "source": str(row.get("文章来源", "")), "content": str(row.get("新闻内容", ""))[:200]}
                       for _, row in df.head(num).iterrows()]
            result["data"].extend(records)
            result["sources"].append("eastmoney")
    except Exception as e:
        result["eastmoney_error"] = str(e)

    # 2. 新浪财经（并行获取）
    try:
        df2 = ak.stock_news_main_sina()
        if df2 is not None and not df2.empty:
            records2 = [{"title": str(row.get("title", "")), "date": str(row.get("date", "")),
                         "source": "sina", "content": ""}
                        for _, row in df2.head(num).iterrows()]
            result["data"].extend(records2)
            result["sources"].append("sina")
    except Exception as e:
        result["sina_error"] = str(e)

    # 3. 网页抓取（并行获取）
    try:
        import requests
        from bs4 import BeautifulSoup
        url = f"https://guba.eastmoney.com/list,{raw}.html"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.articleh .l3')[:num]
        for item in items:
            link = item.find('a')
            if link:
                result["data"].append({
                    "title": link.get_text(strip=True),
                    "date": "",
                    "source": "eastmoney_guba",
                    "content": "",
                    "url": f"https://guba.eastmoney.com{link.get('href', '')}"
                })
        if any(d.get("source") == "eastmoney_guba" for d in result["data"]):
            result["sources"].append("web_scrape")
    except Exception as e:
        result["scrape_error"] = str(e)

    if not result["data"]:
        result["warning"] = "所有新闻源均无数据"
        result["fallback_action"] = {
            "method": "web_browser",
            "instruction": "请使用浏览器工具访问以下任一URL获取新闻",
            "urls": [
                {"source": "东方财富股吧", "url": f"https://guba.eastmoney.com/list,{raw}.html"},
                {"source": "东方财富资讯", "url": f"https://so.eastmoney.com/news/s?keyword={raw}"},
                {"source": "新浪财经", "url": f"https://finance.sina.com.cn/realstock/company/{raw.lower()}/nc.shtml"},
                {"source": "雪球", "url": f"https://xueqiu.com/S/{raw if raw.startswith('6') else 'SZ' + raw}"}
            ]
        }
    result["count"] = len(result["data"])
    return result


@timeout_decorator(seconds=50)
def get_market_news(num: int = 20) -> dict:
    """财经市场综合新闻 (财新 + 东财 + 百度 + 股吧)"""
    from datetime import datetime
    result = {"sources": [], "data_date": datetime.now().strftime("%Y-%m-%d")}

    # 1. 财新数据通 (财经深度)
    try:
        import akshare as ak
        df = ak.stock_news_main_cx()
        if df is not None and not df.empty:
            items = [{"title": str(row.get("summary", "")), "tag": str(row.get("tag", "")),
                      "url": str(row.get("url", ""))} for _, row in df.head(num // 3).iterrows()]
            result["caixin"] = {"count": len(items), "data": items}
            result["sources"].append("caixin")
    except Exception as e:
        result["caixin_error"] = str(e)

    # 2. 东财新闻 (市场热点)
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol='全部')
        if df is not None and not df.empty:
            items = [{"title": str(row.get("新闻标题", "")), "source": str(row.get("文章来源", "")),
                      "time": str(row.get("发布时间", ""))} for _, row in df.head(num // 3).iterrows()]
            result["eastmoney"] = {"count": len(items), "data": items}
            result["sources"].append("eastmoney")
    except Exception as e:
        result["eastmoney_error"] = str(e)

    # 3. 百度财经 (宏观日历)
    try:
        import akshare as ak
        df = ak.news_economic_baidu()
        if df is not None and not df.empty:
            items = [{"date": str(row.get("日期", "")), "event": str(row.get("事件", "")),
                      "region": str(row.get("地区", ""))} for _, row in df.head(10).iterrows()]
            result["baidu_calendar"] = {"count": len(items), "data": items}
            result["sources"].append("baidu_calendar")
    except Exception as e:
        # Baidu API requires cookies - gracefully skip if unavailable
        pass

    # 4. 东财股吧热帖 (市场情绪)
    try:
        import akshare as ak
        df = ak.stock_comment_em()
        if df is not None and not df.empty:
            items = [{"code": str(row.get("代码", "")), "name": str(row.get("名称", "")),
                      "price": float(row.get("最新价", 0)), "change": float(row.get("涨跌幅", 0))}
                     for _, row in df.head(num // 3).iterrows()]
            result["hot_stocks"] = {"count": len(items), "data": items}
            result["sources"].append("hot_stocks")
    except Exception as e:
        result["hot_stocks_error"] = str(e)

    if not result["sources"]:
        result["error"] = "所有新闻源均不可用"
    return result


def get_hot_stocks(market: str = "A股") -> dict:
    """热搜/热门股票排行 (百度股市通)"""
    import akshare as ak
    from datetime import datetime

    # Validate market parameter
    valid_markets = ["全部", "A股", "港股", "美股"]
    if market not in valid_markets:
        return {
            "error": f"无效的市场参数: {market}",
            "valid_values": valid_markets,
            "suggestion": "使用 get_lhb (龙虎榜) 或 get_sector_fund_flow (板块资金流) 查看市场热点"
        }

    try:
        today = datetime.now().strftime("%Y%m%d")
        df = ak.stock_hot_search_baidu(symbol=market, date=today, time="今日")
        if df is None or df.empty:
            return {"error": f"暂无热搜数据: {market}"}
        records = df.head(20).to_dict(orient="records")
        return {"market": market, "count": len(records), "data": records,
                "data_date": today}
    except (TypeError, KeyError) as e:
        # Baidu API structure changed or deprecated
        return {
            "error": f"百度热搜API已失效 (API structure changed): {str(e)}",
            "market": market,
            "suggestion": "使用 get_lhb (龙虎榜) 或 get_sector_fund_flow (板块资金流) 查看市场热点"
        }
    except Exception as e:
        return {"error": str(e), "market": market}


def get_concept_stocks(concept: str) -> dict:
    """获取概念板块成分股

    数据来源：同花顺概念板块 (stock_board_concept_name_ths + 网页分页解析)
    返回：概念板块成分股列表（股票代码、名称、价格、涨跌幅、市值）

    注意：本函数使用同花顺数据源，与东方财富数据可能有概念名称差异。
    如果输入的概念名称未找到，会尝试模糊匹配。
    """
    import akshare as ak
    import requests
    import re
    from datetime import datetime

    try:
        # 第一步：获取所有概念板块名称，匹配输入的概念名
        df_names = ak.stock_board_concept_name_ths()
        if df_names is None or df_names.empty:
            return {"error": "无法获取概念板块列表", "concept": concept}

        # 精确匹配
        matched = df_names[df_names['name'] == concept]
        if matched.empty:
            # 模糊匹配（包含关系）
            matched = df_names[df_names['name'].str.contains(concept, na=False)]
            if matched.empty:
                # 反向匹配：概念名包含在板块名中
                matched = df_names[df_names['name'].str.contains(concept, na=False, regex=False)]
            if matched.empty:
                return {
                    "error": f"未找到概念: {concept}",
                    "concept": concept,
                    "suggestion": "可使用 get_concept_list 查看所有可用概念名称"
                }

        # 取第一个匹配项
        row = matched.iloc[0]
        concept_name = str(row['name'])
        concept_code = str(row['code'])

        # 第二步：用同花顺网页获取成分股（支持分页）
        session = requests.Session()
        session.trust_env = False  # 忽略系统代理
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }

        all_stocks = []
        page = 1
        max_pages = 10  # 最多爬10页（每页10只，即100只股票）
        empty_pages = 0

        while page <= max_pages:
            url = f'http://q.10jqka.com.cn/gn/detail/code/{concept_code}/page/{page}/'
            try:
                r = session.get(url, headers=headers, timeout=10)
            except Exception:
                break

            if r.status_code != 200:
                break

            # 解析表格行
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)
            page_stocks = []
            for row_html in rows:
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
                if len(cells) < 4:
                    continue
                code_match = re.search(r'(\d{6})', cells[1])
                name = re.sub(r'<[^>]+>', '', cells[2]).strip()
                price = re.sub(r'<[^>]+>', '', cells[3]).strip()
                if not code_match or not name or '序号' in name:
                    continue
                stock_code = code_match.group(1)
                # 提取涨跌幅（在第4列）
                change_pct = 0.0
                if len(cells) >= 5:
                    change_text = re.sub(r'<[^>]+>', '', cells[4]).strip().replace('%', '')
                    try:
                        change_pct = float(change_text)
                    except (ValueError, TypeError):
                        change_pct = 0.0
                page_stocks.append({
                    "code": stock_code,
                    "name": name,
                    "price": _safe_float(price, 0),
                    "change_pct": change_pct,
                })

            if not page_stocks:
                empty_pages += 1
                if empty_pages >= 2:  # 连续2页无数据则终止
                    break
            else:
                empty_pages = 0
                all_stocks.extend(page_stocks)

            page += 1

        # 如果没有从网页获取到数据，回退方案：用 fund_flow_concept 获取领涨股
        if not all_stocks:
            try:
                df_flow = ak.stock_fund_flow_concept()
                if df_flow is not None:
                    # 找匹配的概念
                    matched_flow = df_flow[df_flow['行业'] == concept_name]
                    if not matched_flow.empty:
                        lead_stock = matched_flow.iloc[0]
                        leader_name = str(lead_stock.get('领涨股', ''))
                        leader_price = float(lead_stock.get('当前价', 0))
                        if leader_name and leader_name != '--':
                            all_stocks.append({
                                "code": "",
                                "name": leader_name,
                                "price": _safe_float(leader_price, 0),
                                "change_pct": 0,
                            })
            except Exception:
                pass

        return {
            "concept": concept_name,
            "count": len(all_stocks),
            "data": all_stocks[:50],  # 最多返回50只
            "data_date": datetime.now().strftime("%Y-%m-%d")
        }

    except Exception as e:
        return {
            "error": f"获取概念股数据失败: {str(e)}",
            "concept": concept
        }


def get_concept_list() -> dict:
    """获取所有概念板块列表

    数据来源：同花顺概念板块
    返回：概念板块名称和代码列表
    """
    import akshare as ak
    from datetime import datetime

    try:
        df = ak.stock_board_concept_name_ths()
        if df is None or df.empty:
            # fallback to 资金流接口
            df = ak.stock_fund_flow_concept()
            if df is not None and not df.empty:
                concepts = []
                for _, row in df.iterrows():
                    concepts.append({
                        "name": str(row.get('行业', '')),
                        "code": "",
                        "change_pct": float(row.get('行业-涨跌幅', 0)),
                    })
                return {
                    "count": len(concepts),
                    "data": concepts,
                    "data_date": datetime.now().strftime("%Y-%m-%d"),
                    "source": "fund_flow"
                }
            return {"error": "无法获取概念板块列表", "count": 0, "data": []}

        concepts = []
        for _, row in df.iterrows():
            concepts.append({
                "name": str(row.get('name', '')),
                "code": str(row.get('code', '')),
            })
        return {
            "count": len(concepts),
            "data": concepts,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
            "source": "ths"
        }
    except Exception as e:
        try:
            df = ak.stock_fund_flow_concept()
            if df is not None and not df.empty:
                concepts = []
                for _, row in df.iterrows():
                    concepts.append({
                        "name": str(row.get('行业', '')),
                        "code": "",
                        "change_pct": float(row.get('行业-涨跌幅', 0)),
                    })
                return {
                    "count": len(concepts),
                    "data": concepts,
                    "data_date": datetime.now().strftime("%Y-%m-%d"),
                    "source": "fund_flow"
                }
        except Exception:
            pass
        return {"error": f"获取概念列表失败: {str(e)}", "count": 0, "data": []}


def calculate_technical_indicators(symbol: str) -> dict:
    import pandas as pd
    import numpy as np
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        raw = _sina_stock_history(symbol, datalen=90, scale=240)
        if not raw or len(raw) < 30:
            return {"error": "历史数据不足"}
        import pandas as _pd
        df = _pd.DataFrame(raw)
        close = df["close"].astype(float)
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1] if len(df) >= 60 else None
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, float('nan'))
        rsi = 100 - (100 / (1 + rs))
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        current = _safe_float(close.iloc[-1])
        signals = []
        if current > _safe_float(ma5) > _safe_float(ma20): signals.append("短期多头排列")
        elif current < _safe_float(ma5) < _safe_float(ma20): signals.append("短期空头排列")
        if ma60 and current > _safe_float(ma60): signals.append("站上60日均线")
        elif ma60 and current < _safe_float(ma60): signals.append("跌破60日均线")
        rsi_val = _safe_float(rsi.iloc[-1])
        if rsi_val > 70: signals.append("RSI超买")
        elif rsi_val < 30: signals.append("RSI超卖")
        if _safe_float(dif.iloc[-1]) > _safe_float(dea.iloc[-1]): signals.append("MACD金叉")
        else: signals.append("MACD死叉")
        return {"symbol": symbol, "current_price": current,
                "ma": {"ma5": _safe_float(ma5), "ma10": _safe_float(ma10), "ma20": _safe_float(ma20), "ma60": _safe_float(ma60) if ma60 else None},
                "macd": {"dif": _safe_float(dif.iloc[-1]), "dea": _safe_float(dea.iloc[-1]), "histogram": _safe_float((dif - dea).iloc[-1] * 2)},
                "rsi_14": rsi_val,
                "bollinger": {"upper": _safe_float((bb_mid + 2*bb_std).iloc[-1]), "mid": _safe_float(bb_mid.iloc[-1]), "lower": _safe_float((bb_mid - 2*bb_std).iloc[-1])},
                "signals": signals, "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def calculate_buy_range(symbol: str, current_price: float = None) -> dict:
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        raw = _sina_stock_history(symbol, datalen=90, scale=240)
        if not raw:
            return {"error": f"无历史数据: {symbol}"}
        import pandas as _pd
        df = _pd.DataFrame(raw)
        close = df["close"].astype(float)
        low_col = df["low"].astype(float)
        if current_price is None:
            current_price = _safe_float(close.iloc[-1])
        ma20 = _safe_float(close.rolling(20).mean().iloc[-1])
        ma60 = _safe_float(close.rolling(60).mean().iloc[-1]) if len(df) >= 60 else ma20 * 0.95
        recent_low = _safe_float(low_col.tail(20).min())
        bb_lower = _safe_float((close.rolling(20).mean() - 2 * close.rolling(20).std()).iloc[-1])

        # 基本面支撑价：合理PE × EPS（需要实时PE）
        fundamental_support = None
        try:
            rt = get_stock_realtime_price(symbol)
            pe = rt.get("pe_dynamic", 0.0) if "error" not in rt else 0.0
            if pe and pe > 0 and current_price > 0:
                eps = current_price / pe
                # 用历史PE中位数作为合理PE（需要历史数据）
                # 降级方案：取 PE历史分位数 中的 median_pe，若无则用行业经验值
                pe_info = get_pe_percentile(symbol)
                if "error" not in pe_info and pe_info.get("pe_stats", {}).get("median", 0) > 0:
                    fair_pe = _safe_float(pe_info["pe_stats"]["median"])
                else:
                    # 无历史数据时用格雷厄姆公式：合理PE = min(当前PE, 15)
                    fair_pe = min(pe, 15.0)
                fundamental_support = _safe_float(eps * fair_pe)
        except Exception:
            pass

        # 加权支撑位：技术面70% + 基本面30%（若有基本面数据）
        tech_supports = sorted([ma20, ma60, recent_low, bb_lower])
        tech_support = _safe_float(sum(tech_supports[:2]) / 2)

        if fundamental_support and fundamental_support > 0:
            ideal_buy = _safe_float(tech_support * 0.7 + fundamental_support * 0.3)
            safe_buy = _safe_float(min(tech_supports[0], fundamental_support * 0.95))
        else:
            ideal_buy = tech_support
            safe_buy = _safe_float(tech_supports[0])

        stop_loss = _safe_float(safe_buy * 0.92)  # 8% 止损（比原来5%更合理）
        target = _safe_float(ideal_buy + (ideal_buy - stop_loss) * 2)

        # 差异化建议
        if current_price <= ideal_buy:
            advice = f"当前价{current_price}已在买入区间内，可分批建仓: 安全价{safe_buy}(买40%), 理想价{ideal_buy}(买40%), 留10%等更低价. 止损位{stop_loss}"
        elif current_price <= ma20 * 1.05:
            advice = f"当前价{current_price}接近支撑区，可在{ideal_buy}~{safe_buy}区间分批买入(30%/40%/30%). 止损位{stop_loss}, 目标价{target}"
        else:
            advice = f"当前价{current_price}高于支撑区({ideal_buy})，建议等待回调至{ideal_buy}附近再建仓. 若追入，止损位{stop_loss}, 目标价{target}"

        result = {"symbol": symbol, "current_price": current_price,
                "safe_buy": safe_buy, "ideal_buy": ideal_buy, "stop_loss": stop_loss, "target_price": target,
                "support_levels": {"ma20": ma20, "ma60": ma60, "recent_low_20d": recent_low, "bollinger_lower": bb_lower},
                "advice": advice,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
        if fundamental_support:
            result["fundamental_support"] = fundamental_support
        return result
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_stock_valuation(symbol: str) -> dict:
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        rt = get_stock_realtime_price(symbol)
        if "error" in rt:
            return rt
        current_price = rt["price"]
        pe = rt.get("pe_dynamic", 0.0)
        pb = rt.get("pb", 0.0)
        # pe_dynamic already fetched from EM in get_stock_realtime_price
        # Determine valuation status based on actual PE
        if pe <= 0:
            status = "unknown"
        elif pe < 15:
            status = "cheap"
        elif pe < 25:
            status = "fair"
        elif pe < 40:
            status = "slightly_expensive"
        else:
            status = "expensive"
        fair_value = None
        if pe > 0 and current_price > 0:
            eps = current_price / pe
            fair_value = _safe_float(eps * (8.5 + 2 * 10))
        return {"symbol": symbol, "name": rt.get("name", ""), "current_price": current_price,
                "pe": pe, "pb": pb, "valuation_status": status, "fair_value_estimate": fair_value,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_pe_percentile(symbol: str, years: int = 5) -> dict:
    """PE 历史分位数：当前 PE 在过去 N 年中所处的百分位（0=历史最低，100=历史最高）"""
    import pandas as _pd
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        # Use Sina historical data (up to 1200 days ≈ 5 years)
        datalen = min(years * 250, 1200)
        raw = _sina_stock_history(symbol, datalen=datalen, scale=240)
        if not raw or len(raw) < 60:
            return {"error": f"历史数据不足，无法计算PE分位数: {symbol}", "symbol": symbol}

        # 获取当前实时数据（含PE）
        rt = get_stock_realtime_price(symbol)
        if "error" in rt:
            return rt
        current_pe = rt.get("pe_dynamic", 0.0)
        if current_pe <= 0:
            return {"error": f"当前PE无效（{current_pe}），可能是亏损股或数据缺失", "symbol": symbol}

        current_price = rt["price"]
        eps = current_price / current_pe if current_pe > 0 else None
        if not eps:
            return {"error": "无法计算EPS", "symbol": symbol}

        close = _pd.Series([float(r["close"]) for r in raw])
        hist_pe = close / eps
        hist_pe = hist_pe[hist_pe > 0]

        pe_min = _safe_float(hist_pe.min())
        pe_max = _safe_float(hist_pe.max())
        pe_median = _safe_float(hist_pe.median())
        pe_mean = _safe_float(hist_pe.mean())
        percentile = _safe_float(float((hist_pe < current_pe).sum()) / len(hist_pe) * 100)

        # 判断估值区间
        if percentile <= 20:
            zone = "历史低估区（底部20%）"
            signal = "bullish"
        elif percentile <= 40:
            zone = "偏低估值区（20-40%）"
            signal = "mild_bullish"
        elif percentile <= 60:
            zone = "历史中位区（40-60%）"
            signal = "neutral"
        elif percentile <= 80:
            zone = "偏高估值区（60-80%）"
            signal = "mild_bearish"
        else:
            zone = "历史高估区（顶部20%）"
            signal = "bearish"

        return {
            "symbol": symbol,
            "name": rt.get("name", ""),
            "current_pe": current_pe,
            "pe_percentile": percentile,
            "valuation_zone": zone,
            "signal": signal,
            "pe_stats": {
                "min": pe_min,
                "max": pe_max,
                "median": pe_median,
                "mean": pe_mean,
            },
            "years_of_data": years,
            "data_points": len(hist_pe),
            "note": "历史PE基于当前EPS反推，适合盈利稳定的公司；高成长/周期股仅供参考",
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_quality_score(symbol: str) -> dict:
    """基本面质量评分（0-100）：ROE趋势 + 现金流质量 + 负债率 + 毛利率"""
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        fin = get_financial_indicators(symbol)
        if "error" in fin:
            return fin
        data = fin.get("data", [])
        if not data:
            return {"error": f"无财务数据: {symbol}", "symbol": symbol}
        latest = data[0]
        score = 0
        details = {}

        # ROE 评分（40分）
        roe = _safe_float(latest.get("roe", 0))
        details["roe"] = roe
        if roe >= 20: score += 40
        elif roe >= 15: score += 32
        elif roe >= 12: score += 24
        elif roe >= 8: score += 12
        # ROE 趋势加减分
        if len(data) >= 3:
            # data[0] 是最新，data[2] 是最旧；上升趋势 = 最新 >= 中间 >= 最旧
            roe_trend = [_safe_float(d.get("roe", 0)) for d in data[:3]]
            if roe_trend[2] >= roe_trend[1] >= roe_trend[0]:
                score -= 5; details["roe_trend"] = "下降"
            elif roe_trend[0] >= roe_trend[1] >= roe_trend[2]:
                score += 5; details["roe_trend"] = "上升"
            else:
                details["roe_trend"] = "稳定"

        # 负债率评分（25分）
        debt_ratio = _safe_float(latest.get("debt_ratio", 100))
        details["debt_ratio"] = debt_ratio
        if debt_ratio < 30: score += 25
        elif debt_ratio < 50: score += 18
        elif debt_ratio < 65: score += 10
        elif debt_ratio < 80: score += 3

        # 毛利率评分（20分）
        gross_margin = _safe_float(latest.get("gross_margin", 0))
        details["gross_margin"] = gross_margin
        if gross_margin >= 50: score += 20
        elif gross_margin >= 35: score += 15
        elif gross_margin >= 20: score += 10
        elif gross_margin >= 10: score += 5

        # 净利率评分（15分）
        net_margin = _safe_float(latest.get("net_margin", 0))
        details["net_margin"] = net_margin
        if net_margin >= 20: score += 15
        elif net_margin >= 10: score += 10
        elif net_margin >= 5: score += 5

        score = max(0, min(100, score))
        if score >= 80: grade = "A（优质）"
        elif score >= 65: grade = "B（良好）"
        elif score >= 50: grade = "C（一般）"
        elif score >= 35: grade = "D（较差）"
        else: grade = "E（差）"

        return {
            "symbol": symbol, "score": score, "grade": grade, "details": details,
            "advice": "建议投资" if score >= 65 else ("谨慎考虑" if score >= 50 else "建议回避"),
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_exit_plan(symbol: str, buy_price: float, shares: int = 100) -> dict:
    """止盈计划：基于合理PE估值计算三档止盈价和分批卖出建议"""
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        rt = get_stock_realtime_price(symbol)
        if "error" in rt:
            return rt
        current_price = rt["price"]
        pe = rt.get("pe_dynamic", 0.0)

        # 基于EPS计算合理价值区间
        if pe and pe > 0 and current_price > 0:
            eps = current_price / pe
            # 三档目标价：保守(合理PE×1.2) / 中等(合理PE×1.5) / 激进(合理PE×2.0)
            # 合理PE = 8.5 + 2×10%增速 = 28.5，取当前PE和28.5的较小值作为基准
            base_pe = min(pe, 28.5)
            target_conservative = _safe_float(eps * base_pe * 1.2)
            target_moderate = _safe_float(eps * base_pe * 1.5)
            target_aggressive = _safe_float(eps * base_pe * 2.0)
        else:
            # 无PE数据时用技术面：买入价的 +20% / +40% / +60%
            target_conservative = _safe_float(buy_price * 1.20)
            target_moderate = _safe_float(buy_price * 1.40)
            target_aggressive = _safe_float(buy_price * 1.60)

        # 当前盈亏
        pnl_pct = _safe_float((current_price - buy_price) / buy_price * 100)
        pnl_amount = _safe_float((current_price - buy_price) * shares)

        # 止盈建议
        sell_plan = []
        if current_price >= target_conservative:
            sell_plan.append(f"已达保守目标({target_conservative})，建议卖出30%")
        if current_price >= target_moderate:
            sell_plan.append(f"已达中等目标({target_moderate})，建议再卖40%")
        if current_price >= target_aggressive:
            sell_plan.append(f"已达激进目标({target_aggressive})，建议清仓剩余30%")
        if not sell_plan:
            next_target = target_conservative
            pct_to_target = _safe_float((next_target - current_price) / current_price * 100)
            sell_plan.append(f"距保守目标({next_target})还有{pct_to_target}%，继续持有")

        return {
            "symbol": symbol,
            "name": rt.get("name", ""),
            "buy_price": buy_price,
            "current_price": current_price,
            "shares": shares,
            "pnl_pct": pnl_pct,
            "pnl_amount": pnl_amount,
            "targets": {
                "conservative": target_conservative,   # 卖30%
                "moderate": target_moderate,            # 再卖40%
                "aggressive": target_aggressive,        # 清仓30%
            },
            "sell_plan": sell_plan,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


@timeout_decorator(seconds=50)
def get_macro_data(indicators: list = None) -> dict:
    """宏观经济数据合集：PMI/CPI/GDP，判断经济周期和政策环境

    参数：
    - indicators: 指标列表，可选 ["pmi", "cpi", "gdp"]，不传则返回全部

    返回数据：
    - PMI（制造业采购经理指数）：
      * 最近6个月数据
      * >50 表示扩张，<50 表示收缩
      * 领先指标，预示经济走向

    - CPI（居民消费价格指数）：
      * 最近6个月同比增长率
      * 衡量通胀水平
      * 影响货币政策

    - GDP（国内生产总值）：
      * 最近8个季度累计值（亿元）
      * 衡量经济总量和增速
      * 判断经济周期位置

    数据来源：国家统计局官方数据
    超时控制：每个指标10秒超时，单个失败不影响其他指标
    """
    import akshare as ak
    from datetime import datetime

    all_indicators = indicators or ["pmi", "cpi", "gdp"]
    results = {}

    if "pmi" in all_indicators:
        try:
            # 使用更可靠的 macro_china_pmi 数据源
            df = ak.macro_china_pmi()
            if not df.empty:
                df_valid = df.head(6)  # 取最新6个月
                results["pmi"] = [{"date": str(row['月份']), "value": _safe_float(row['制造业-指数'])}
                                  for _, row in df_valid.iterrows()]
        except Exception as e:
            results["pmi_error"] = str(e)

    if "cpi" in all_indicators:
        try:
            # 使用 macro_china_cpi_monthly 获取月度数据
            df = ak.macro_china_cpi_monthly()
            if not df.empty:
                # 获取最近6个月的数据（数据按时间升序排列，所以取最后6条）
                df_valid = df.tail(6).sort_values('日期', ascending=False)
                results["cpi"] = [{"date": str(row['日期']), "yoy": _safe_float(row['今值'])}
                                  for _, row in df_valid.iterrows()]
        except Exception as e:
            results["cpi_error"] = str(e)

    if "gdp" in all_indicators:
        try:
            # 使用 macro_china_gdp 获取季度GDP数据
            df = ak.macro_china_gdp()
            if not df.empty:
                df_valid = df.head(8)
                results["gdp"] = [{"date": str(row['季度']), "value": _safe_float(row['国内生产总值-绝对值'])}
                                  for _, row in df_valid.iterrows()]
        except Exception as e:
            results["gdp_error"] = str(e)

    results["data_date"] = datetime.now().strftime("%Y-%m-%d")

    # 如果所有指标都失败了，返回错误
    if all(key.endswith("_error") for key in results.keys() if key != "data_date"):
        return {"error": "所有宏观数据API均失败"}

    return results


def get_north_flow() -> dict:
    """北向资金流向：陆股通每日净买入额，判断外资流入流出趋势

    返回最近10个交易日的北向资金数据，包括：
    - 净买入额（亿元）
    - 买入成交额（亿元）
    - 卖出成交额（亿元）

    数据来源：东方财富网陆股通数据

    注意：该接口自 2024-08-19 起数据源失效，返回的历史数据停留在 2024-08-16，
    实时数据全为 0。这是东方财富网数据源问题，非代码问题。
    """
    import akshare as ak
    from datetime import datetime, timedelta
    try:
        # 获取历史数据
        df_hist = ak.stock_hsgt_hist_em(symbol="北向资金")

        # 过滤掉 NaN 值的行
        valid_data = df_hist.dropna(subset=["当日成交净买额"])

        if valid_data.empty:
            return {
                "error": "北向资金数据源失效",
                "detail": "东方财富网北向资金接口无有效数据，建议使用其他市场情绪指标",
                "data": []
            }

        # 检查最新数据的时效性
        latest_date = valid_data['日期'].max()
        days_old = (datetime.now() - datetime.strptime(str(latest_date), "%Y-%m-%d")).days

        if days_old > 30:
            return {
                "error": "北向资金数据过期",
                "detail": f"最新数据停留在 {latest_date}（{days_old} 天前），数据源已失效",
                "last_valid_date": str(latest_date),
                "data": []
            }

        # 返回最近10条有效数据
        records = []
        for _, row in valid_data.tail(10).iterrows():
            records.append({
                "date": str(row.get("日期", "")),
                "amount_billion": _safe_float(row.get("当日成交净买额", 0)),
                "buy": _safe_float(row.get("买入成交额", 0)),
                "sell": _safe_float(row.get("卖出成交额", 0))
            })

        return {
            "data": records,
            "data_date": str(latest_date),
            "warning": f"数据更新至 {latest_date}，可能不是最新" if days_old > 1 else None
        }
    except Exception as e:
        return {"error": f"获取北向资金数据失败: {str(e)}"}


def get_stock_list(market="A"):
    """获取A股列表"""
    import akshare as ak
    try:
        df = ak.stock_zh_a_spot_em()
        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "market_cap": _safe_float(row.get("总市值", 0)) / 100000000,
                "pe": _safe_float(row.get("市盈率-动态", 0)),
                "pb": _safe_float(row.get("市净率", 0)),
            })
        return {"stocks": stocks}
    except Exception as e:
        return {"error": str(e), "stocks": []}


def get_market_overview() -> dict:
    from datetime import datetime
    try:
        # 上证/深证/创业板/沪深300/中证500 via Sina
        codes = {
            "上证指数": "sh000001",
            "深证成指": "sz399001",
            "创业板指": "sz399006",
            "沪深300": "sh000300",
            "中证500": "sz399905",
        }
        list_str = ",".join(codes.values())
        r = _sina_request(f"https://hq.sinajs.cn/list={list_str}")
        r.encoding = "gbk"
        lines = [l.strip() for l in r.text.strip().split("\n") if l.strip()]
        results = {}
        for (name, _), line in zip(codes.items(), lines):
            import re
            m = re.search(r'"([^"]*)"', line)
            if not m:
                continue
            fields = m.group(1).split(",")
            if len(fields) < 4:
                continue
            prev_close = _safe_float(fields[2])
            price = _safe_float(fields[3])
            change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            results[name] = {"price": price, "change_pct": change_pct}
        return {"indices": results, "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e)}


def get_index_history(symbol: str, start_date: str, end_date: str) -> dict:
    """获取指数历史数据

    Args:
        symbol: 指数代码，如 sh000001, sz399001, sz399006
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD

    Returns:
        {"success": True, "data": [{"date": "2024-01-01", "open": 3000, "high": 3100, "low": 2900, "close": 3050, "volume": 1000000}]}
    """
    import akshare as ak
    try:
        # 转换代码格式（去掉 sh/sz 前缀）
        if symbol.startswith('sh'):
            code = symbol[2:]
        elif symbol.startswith('sz'):
            code = symbol[2:]
        else:
            code = symbol

        # 获取指数日线数据
        df = ak.stock_zh_index_daily(symbol=code)

        if df is None or df.empty:
            return {"success": False, "error": f"No data for index {symbol}"}

        # 过滤日期范围
        df['date'] = df['date'].astype(str)
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

        if df.empty:
            return {"success": False, "error": f"No data in date range {start_date} to {end_date}"}

        # 转换为字典列表
        result = []
        for _, row in df.iterrows():
            result.append({
                'date': str(row['date']),
                'open': _safe_float(row.get('open', 0)),
                'high': _safe_float(row.get('high', 0)),
                'low': _safe_float(row.get('low', 0)),
                'close': _safe_float(row.get('close', 0)),
                'volume': _safe_float(row.get('volume', 0), decimals=0),
            })

        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def get_hk_financials(symbol: str) -> dict:
    """港股财务数据（via akshare stock_financial_hk_report_em，长格式pivot）
    返回最近4期：营收、净利润、净利率、负债率、ROE
    """
    import akshare as ak
    from datetime import datetime
    code = _hk_code(symbol)
    results = {}

    def _pivot(df):
        """将长格式财报 pivot 为 {date: {item: value}} 字典"""
        out = {}
        for _, row in df.iterrows():
            d = str(row["REPORT_DATE"])[:10]
            item = str(row["STD_ITEM_NAME"])
            val = _safe_float(row["AMOUNT"], decimals=0)
            if d not in out:
                out[d] = {}
            out[d][item] = val
        return out

    # 利润表
    try:
        df = ak.stock_financial_hk_report_em(stock=code, symbol="利润表", indicator="年度")
        if df is not None and not df.empty:
            pivoted = _pivot(df)
            income = []
            for date in sorted(pivoted.keys(), reverse=True)[:4]:
                row = pivoted[date]
                revenue = row.get("营业额", row.get("营运收入", 0.0))
                net_profit = row.get("股东应占溢利", row.get("除税后溢利", 0.0))
                net_margin = round(net_profit / revenue * 100, 2) if revenue else 0.0
                income.append({
                    "period": date,
                    "revenue": revenue,
                    "net_profit": net_profit,
                    "net_margin": net_margin,
                })
            results["income"] = income
    except Exception as e:
        results["income_error"] = str(e)

    # 资产负债表
    try:
        df = ak.stock_financial_hk_report_em(stock=code, symbol="资产负债表", indicator="年度")
        if df is not None and not df.empty:
            pivoted = _pivot(df)
            latest_date = sorted(pivoted.keys(), reverse=True)[0]
            row = pivoted[latest_date]
            total_assets = row.get("总资产", 0.0)
            total_liab = row.get("总负债", 0.0)
            equity = row.get("股东权益", row.get("总权益", 0.0))
            debt_ratio = round(total_liab / total_assets * 100, 2) if total_assets else 0.0
            roe = 0.0
            if results.get("income") and equity:
                roe = round(results["income"][0]["net_profit"] / equity * 100, 2)
            results["balance"] = {
                "period": latest_date,
                "total_assets": total_assets,
                "total_liabilities": total_liab,
                "equity": equity,
                "debt_ratio": debt_ratio,
                "roe": roe,
            }
    except Exception as e:
        results["balance_error"] = str(e)

    if not results or (results.get("income_error") and results.get("balance_error")):
        return {"error": f"无法获取港股财务数据: {symbol}（akshare港股财报接口可能不支持该股票）", "symbol": symbol}

    results["symbol"] = code
    results["market"] = "HK"
    results["data_date"] = datetime.now().strftime("%Y-%m-%d")
    return results


def get_hk_analysis(symbol: str) -> dict:
    """港股综合分析：价格 + 历史技术面 + 财务（尽力而为）
    专为港股设计，整合所有可用数据源，明确标注哪些数据不可用。
    """
    from datetime import datetime
    import pandas as _pd
    code = _hk_code(symbol)
    result = {"symbol": code, "market": "HK", "data_date": datetime.now().strftime("%Y-%m-%d")}
    unavailable = []

    # 1. 实时价格
    price_data = get_hk_stock_price(symbol)
    if "error" in price_data:
        return {"error": f"无法获取港股实时价格: {price_data['error']}", "symbol": symbol}
    result["price"] = price_data

    # 2. 历史行情 + 技术指标（stooq）
    try:
        hist = get_hk_stock_history(symbol, period="daily")
        if "error" not in hist and hist.get("data"):
            data = hist["data"]
            closes = _pd.Series([r["close"] for r in data])
            result["history_count"] = len(data)
            result["recent_high_20d"] = _safe_float(closes.tail(20).max())
            result["recent_low_20d"] = _safe_float(closes.tail(20).min())
            if len(closes) >= 20:
                result["ma20"] = _safe_float(closes.tail(20).mean())
            if len(closes) >= 60:
                result["ma60"] = _safe_float(closes.tail(60).mean())
            # 简单趋势判断
            current = price_data["price"]
            ma20 = result.get("ma20", 0)
            ma60 = result.get("ma60", 0)
            if ma20 and ma60:
                if current > ma20 > ma60:
                    result["trend"] = "多头排列（短期强势）"
                elif current < ma20 < ma60:
                    result["trend"] = "空头排列（短期弱势）"
                else:
                    result["trend"] = "震荡整理"
        else:
            unavailable.append("历史K线（stooq数据获取失败）")
    except Exception as e:
        unavailable.append(f"历史K线（{e}）")

    # 3. 财务数据（akshare港股财报）
    try:
        fin = get_hk_financials(symbol)
        if "error" not in fin:
            result["financials"] = fin
        else:
            unavailable.append(f"财务报表（{fin['error']}）")
    except Exception as e:
        unavailable.append(f"财务报表（{e}）")

    # 4. 明确标注不支持的功能
    result["not_supported"] = [
        "PE历史分位数（需A股数据源）",
        "龙虎榜（仅A股）",
        "北向资金（仅A股）",
        "融资融券（仅A股）",
        "公告（需港交所接口）",
    ]
    if unavailable:
        result["data_unavailable"] = unavailable

    return result


# ===== 新增：港股工具 ==========================================================

def get_hk_market_overview() -> dict:
    """港股三大指数实时行情：恒生指数、国企指数、恒生科技指数

    数据来源：新浪财经（与 A 股 get_market_overview 相同的 Sina 数据源）
    """
    import requests as _req
    from datetime import datetime
    try:
        r = _req.get(
            "https://hq.sinajs.cn/list=rt_hkHSI,rt_hkHSCEI,rt_hkHSTECH",
            headers={"Referer": "https://finance.sina.com.cn"},
            timeout=10
        )
        r.encoding = "gbk"
        lines = r.text.strip().split("\n")
        indices = []
        # 新浪港股指数格式：
        # var hq_str_rt_hkXXX="name(GBK),open,prev_close,current,high,low,change,change_pct,...,high_52w,low_52w,date,time"

        for line in lines:
            line = line.strip()
            if not line or not line.startswith("var "):
                continue
            # 提取 "=" 号后的引号内容
            eq_idx = line.find("=")
            if eq_idx == -1:
                continue
            raw = line[eq_idx + 1:].strip().strip('"').strip("'").strip(";")
            parts = raw.split(",")
            if len(parts) < 8:
                continue
            code_raw = parts[0]  # e.g. "HSI"
            name_gbk = parts[1]
            # 尝试解码 GBK
            try:
                name_bytes = name_gbk.encode("latin1")
                name = name_bytes.decode("gbk")
            except Exception:
                name = name_gbk

            open_price = _safe_float(parts[2])
            prev_close = _safe_float(parts[3])
            current = _safe_float(parts[4])
            high = _safe_float(parts[5])
            low = _safe_float(parts[6])
            change = _safe_float(parts[7])
            change_pct = _safe_float(parts[8])
            date_str = parts[16] if len(parts) > 16 else ""
            time_str = parts[17] if len(parts) > 17 else ""

            indices.append({
                "code": code_raw,
                "name": name,
                "current": current,
                "change": change,
                "change_pct": change_pct,
                "open": open_price,
                "high": high,
                "low": low,
                "prev_close": prev_close,
                "data_date": date_str,
                "data_time": time_str,
            })

        if not indices:
            return {"error": "无法获取港股指数数据", "indices": []}

        return {
            "indices": indices,
            "data_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        return {"error": f"港股指数数据获取失败: {str(e)}", "indices": []}


def get_hk_south_flow() -> dict:
    """南向资金（港股通）流向

    通过 akshare 获取港股通每日净买入额，判断内地资金流入流出趋势。
    对应 A 股的 get_north_flow（北向资金）。
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 获取南向资金（沪深港通-南向）
        df = ak.stock_hsgt_hist_em(symbol="南向资金")
        if df is None or df.empty:
            return {"error": "无南向资金数据", "data": []}

        records = []
        for _, row in df.tail(10).iterrows():
            records.append({
                "date": str(row.get("日期", "")),
                "net_amount_billion": _safe_float(row.get("当日成交净买额", 0)),
                "buy_amount_billion": _safe_float(row.get("买入成交额", 0)),
                "sell_amount_billion": _safe_float(row.get("卖出成交额", 0)),
            })

        return {
            "data": records,
            "direction": "南向（内地→港股）",
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "data": []}


def get_hk_technical(symbol: str) -> dict:
    """港股个股技术分析

    基于 get_hk_stock_history 的历史数据，本地计算技术指标：
    - 均线（MA5/MA10/MA20/MA60）
    - MACD（DIF/DEA/柱）
    - RSI-14
    - 布林带（上/中/下轨）
    - 信号判断

    对应 A 股的 calculate_technical_indicators。
    """
    from datetime import datetime
    import pandas as _pd

    code = _hk_code(symbol)

    # 1. 获取历史行情
    hist = get_hk_stock_history(symbol, period="daily")
    if "error" in hist or not hist.get("data"):
        return {"error": f"无法获取{code}的历史数据", "symbol": code}

    data = hist["data"]
    if len(data) < 30:
        return {"error": f"历史数据不足（{len(data)}条），需要至少30个交易日", "symbol": code}

    closes = _pd.Series([r["close"] for r in data])
    highs = _pd.Series([r["high"] for r in data])
    lows = _pd.Series([r["low"] for r in data])
    volumes = _pd.Series([r["volume"] for r in data])
    dates = [r["date"] for r in data]

    result = {
        "symbol": code,
        "market": "HK",
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }

    # 2. 均线
    ma_periods = {5: "MA5", 10: "MA10", 20: "MA20", 60: "MA60"}
    ma_values = {}
    for period, name in ma_periods.items():
        if len(closes) >= period:
            ma_values[name] = _safe_float(closes.tail(period).mean())
    result["ma"] = ma_values

    # 3. MACD
    if len(closes) >= 26:
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_hist = 2 * (dif - dea)
        result["macd"] = {
            "dif": _safe_float(dif.iloc[-1]),
            "dea": _safe_float(dea.iloc[-1]),
            "histogram": _safe_float(macd_hist.iloc[-1]),
        }
    else:
        result["macd"] = None

    # 4. RSI-14
    if len(closes) >= 15:
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        result["rsi_14"] = _safe_float(rsi.iloc[-1])
    else:
        result["rsi_14"] = None

    # 5. 布林带（20日）
    if len(closes) >= 20:
        ma20 = closes.tail(20).mean()
        std20 = closes.tail(20).std()
        result["bollinger"] = {
            "upper": _safe_float(ma20 + 2 * std20),
            "middle": _safe_float(ma20),
            "lower": _safe_float(ma20 - 2 * std20),
        }
    else:
        result["bollinger"] = None

    # 6. 信号判断
    signals = []
    current = closes.iloc[-1]

    # 均线排列
    ma5 = ma_values.get("MA5")
    ma10 = ma_values.get("MA10")
    ma20_val = ma_values.get("MA20")
    ma60_val = ma_values.get("MA60")

    if ma5 and ma10 and ma20_val and ma60_val:
        if current > ma5 > ma10 > ma20_val > ma60_val:
            signals.append("多头排列（短期强势）")
        elif current < ma5 < ma10 < ma20_val < ma60_val:
            signals.append("空头排列（短期弱势）")
        elif ma5 > ma10 and current > ma20_val:
            signals.append("短期偏多")
        elif ma5 < ma10 and current < ma20_val:
            signals.append("短期偏空")
        else:
            signals.append("震荡整理")

    # MACD 金叉/死叉
    if result.get("macd") and result["macd"]["dif"] and result["macd"]["dea"]:
        if result["macd"]["dif"] > result["macd"]["dea"]:
            signals.append("MACD多头（DIF在DEA上方）")
        else:
            signals.append("MACD空头（DIF在DEA下方）")

        # 金叉/死叉检查
        if len(closes) >= 26:
            # 用前一天的差值判断方向变化
            dif_prev = _safe_float(dif.iloc[-2])
            dea_prev = _safe_float(dea.iloc[-2])
            if dif_prev < dea_prev and result["macd"]["dif"] > result["macd"]["dea"]:
                signals.append("MACD金叉（买入信号）")
            elif dif_prev > dea_prev and result["macd"]["dif"] < result["macd"]["dea"]:
                signals.append("MACD死叉（卖出信号）")

    # RSI
    rsi_val = result.get("rsi_14")
    if rsi_val is not None:
        if rsi_val > 70:
            signals.append("RSI超买（>70）")
        elif rsi_val < 30:
            signals.append("RSI超卖（<30）")

    # 价格与布林带
    boll = result.get("bollinger")
    if boll:
        if current >= boll["upper"]:
            signals.append("价格触及布林上轨")
        elif current <= boll["lower"]:
            signals.append("价格触及布林下轨")

    result["signals"] = signals
    result["current_price"] = _safe_float(current)

    return result


def get_hk_hot_rank() -> dict:
    """港股人气热度排行

    通过 akshare 获取东方财富港股人气榜，了解今日港股市场最受关注的个股。
    """
    import akshare as ak
    from datetime import datetime

    try:
        df = ak.stock_hk_hot_rank_em()

        if df is None or df.empty:
            return {"error": "无法获取港股人气排行", "stocks": []}

        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                "rank": int(row.get("当前排名", 0)),
                "symbol": str(row.get("代码", "")),
                "name": str(row.get("股票名称", "")),
                "price": _safe_float(row.get("最新价", 0)),
                "change_pct": _safe_float(row.get("涨跌幅", 0)),
            })

        return {
            "stocks": stocks,
            "total": len(stocks),
            "data_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        return {"error": str(e), "stocks": []}


# ===== End of HK tools =====


def manage_portfolio(action: str, symbol: str = None, quantity: int = None, avg_cost: float = None, notes: str = "") -> dict:
    import os
    from datetime import datetime
    portfolio_path = os.path.join(os.getcwd(), ".pi-invest", "portfolio.json")
    os.makedirs(os.path.dirname(portfolio_path), exist_ok=True)

    if not os.path.exists(portfolio_path):
        data = {"holdings": [], "last_updated": ""}
    else:
        with open(portfolio_path) as f:
            data = json.load(f)

    if action == "get":
        return data
    elif action == "add" and symbol:
        holdings = data["holdings"]
        existing = next((h for h in holdings if h["symbol"] == symbol), None)
        if existing:
            existing.update({"quantity": quantity or existing["quantity"], "avg_cost": avg_cost or existing["avg_cost"], "notes": notes})
        else:
            holdings.append({"symbol": symbol, "quantity": quantity or 0, "avg_cost": avg_cost or 0, "notes": notes, "added_date": datetime.now().strftime("%Y-%m-%d")})
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(portfolio_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": f"已添加/更新 {symbol}"}
    elif action == "remove" and symbol:
        data["holdings"] = [h for h in data["holdings"] if h["symbol"] != symbol]
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(portfolio_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": f"已删除 {symbol}"}
    return {"error": f"未知操作: {action}"}


# ===== Financial statements =====

def _financial_report(symbol: str, report_type: str, recent_n: int = 8) -> dict:
    """通用三表获取：资产负债表 / 利润表 / 现金流量表"""
    import akshare as ak
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    sina_sym = _sina_symbol(symbol)
    try:
        df = ak.stock_financial_report_sina(stock=sina_sym, symbol=report_type)
        if df is None or df.empty:
            return {"error": f"无{report_type}数据: {symbol}"}
        df = df.head(recent_n)
        # 日期列统一格式
        for col in ["报告日", "更新日期"]:
            if col in df.columns:
                df[col] = df[col].astype(str)
        # 替换 NaN 为 None (JSON null)
        df = df.where(df.notna(), None)
        records = df.to_dict(orient="records")
        return {
            "symbol": symbol,
            "report_type": report_type,
            "count": len(records),
            "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_financial_statements(symbol: str, statement: str = "all", recent_n: int = 8) -> dict:
    """三表合集：statement = income/balance/cashflow/all"""
    result = {}
    if statement in ("income", "all"):
        result["income_statement"] = _financial_report(symbol, "利润表", recent_n)
    if statement in ("balance", "all"):
        result["balance_sheet"] = _financial_report(symbol, "资产负债表", recent_n)
    if statement in ("cashflow", "all"):
        cf = _financial_report(symbol, "现金流量表", recent_n)
        result["cash_flow"] = cf
        result["cashflow_statement"] = cf  # 别名，兼容 AI agent 的命名预期
    return result


def get_balance_sheet(symbol: str, recent_n: int = 8) -> dict:
    """资产负债表：总资产、负债、股东权益、应收账款、存货、现金等"""
    return get_financial_statements(symbol, statement="balance", recent_n=recent_n)


def get_income_statement(symbol: str, recent_n: int = 8) -> dict:
    """利润表：营业收入、营业成本、净利润、毛利率、净利率等"""
    return get_financial_statements(symbol, statement="income", recent_n=recent_n)


def get_cash_flow(symbol: str, recent_n: int = 8) -> dict:
    """现金流量表：经营活动现金流、投资活动现金流、筹资活动现金流"""
    return get_financial_statements(symbol, statement="cashflow", recent_n=recent_n)


def get_insider_trades(symbol: str) -> dict:
    """高管增减持：变动人、职务、变动日期、变动股数、成交均价等"""
    import akshare as ak
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    # xueqiu 格式
    if symbol.startswith("6"):
        xq_sym = f"SH{symbol}"
    else:
        xq_sym = f"SZ{symbol}"
    try:
        df = ak.stock_inner_trade_xq(symbol=xq_sym)
        if df is None or df.empty:
            return {"error": f"未找到 {symbol} 的高管交易记录"}
        col_map = {
            "股票代码": "symbol", "股票名称": "name",
            "变动人": "person", "董监高职务": "title",
            "变动日期": "date", "变动股数": "shares_changed",
            "成交均价": "avg_price", "变动后持股数": "shares_after",
            "与董监高关系": "relationship",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["symbol"] = symbol
        if "shares_changed" in df.columns and "avg_price" in df.columns:
            df["transaction_value"] = (
                df["shares_changed"].astype(float, errors="ignore") *
                df["avg_price"].astype(float, errors="ignore")
            )
        records = df.to_dict(orient="records")
        return {
            "symbol": symbol,
            "count": len(records),
            "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


# ===== 龙虎榜 =====

@timeout_decorator(seconds=40)
def get_lhb(symbol: str = None, date: str = None) -> dict:
    """龙虎榜：有 symbol 则查个股统计，无 symbol 则查今日榜单明细

    注意：akshare 最新版中 stock_lhb_stock_statistic_em(symbol) 的 symbol 参数
    实际上表示统计周期（如 "近一月"），而非股票代码。
    个股龙虎榜统计功能暂时不可用。
    """
    import akshare as ak
    from datetime import datetime, timedelta
    if symbol:
        # akShare 新版 API 变更：stock_lhb_stock_statistic_em(symbol) 的
        # symbol 参数实际为 period 字符串，不再支持按股票代码查询。
        # 使用 stock_lhb_detail_em 按日期筛选个股替代
        symbol = _clean_symbol(symbol)
        try:
            # 获取最近 30 天的龙虎榜，按股票代码筛选
            end = datetime.now()
            start = end - timedelta(days=30)
            df = ak.stock_lhb_detail_em(
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                return {"error": f"无龙虎榜数据: {symbol}", "symbol": symbol}
            # 筛选该股票
            stock_df = df[df["代码"] == symbol].copy()
            if stock_df.empty:
                return {"error": f"该股近期未上龙虎榜: {symbol}", "symbol": symbol,
                        "hint": "可使用不带参数的 get_lhb() 查看今日龙虎榜全榜"}
            records = stock_df.head(10).to_dict(orient="records")
            return {"symbol": symbol, "count": len(records), "data": records,
                    "data_date": datetime.now().strftime("%Y-%m-%d"),
                    "note": "个股统计周期为近30日明细（akShare API 变更后替代方案）"}
        except Exception as e:
            return {"error": str(e), "symbol": symbol}
    else:
        # 无 symbol：获取昨日（或指定日期）榜单
        if not date:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        try:
            df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
            if df is None or df.empty:
                return {"error": f"无龙虎榜数据: {date}", "date": date}
            col_map = {
                "代码": "symbol", "名称": "name", "收盘价": "close",
                "涨跌幅": "change_pct", "龙虎榜净买额": "net_buy",
                "龙虎榜买入额": "buy_amount", "龙虎榜卖出额": "sell_amount",
                "净买额占总成交比": "net_buy_ratio", "上榜原因": "reason",
                "解读": "analysis", "换手率": "turnover_rate",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            return {"date": date, "count": len(df),
                    "data": df.head(30).to_dict(orient="records"),
                    "data_date": datetime.now().strftime("%Y-%m-%d")}
        except Exception as e:
            return {"error": str(e), "date": date}


# ===== 机构持仓 =====

def get_fund_holdings(symbol: str) -> dict:
    """基金重仓持股：持有该股的基金列表、持股数量、占流通股比例"""
    import akshare as ak
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        df = ak.stock_institute_hold_detail(stock=symbol, quarter="")
        if df is None or df.empty:
            return {"error": f"无基金持仓数据: {symbol}", "symbol": symbol}
        records = df.head(20).to_dict(orient="records")
        return {"symbol": symbol, "count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_top_fund_stocks() -> dict:
    """基金重仓股排行：被最多基金持有的股票"""
    return {"error": "akshare 已移除 fund_stock_rank_em 接口，该功能暂不可用"}


# ===== 股东信息 =====

def get_top_holders(symbol: str, date: str = None) -> dict:
    """前十大股东：股东名称、持股数量、持股比例、持股变动"""
    import akshare as ak
    from datetime import datetime, timedelta
    raw = _clean_symbol(symbol)
    # stock_gdfx_top_10_em 需要带市场前缀的格式，如 sh600519 / sz000858
    em_symbol = _sina_symbol(raw)
    # 默认取最近一个季度末；支持显式传入 date=YYYYMMDD
    if date:
        date_str = str(date)
    else:
        now = datetime.now()
        quarter_ends = ["0331", "0630", "0930", "1231"]
        # 找最近已过去的季度末
        for qe in reversed(quarter_ends):
            year = now.year
            date_str = f"{year}{qe}"
            if datetime.strptime(date_str, "%Y%m%d") < now:
                break
            date_str = f"{year - 1}{qe}"
    try:
        df = ak.stock_gdfx_top_10_em(symbol=em_symbol, date=date_str)
        if df is None or df.empty:
            return {"error": f"无股东数据: {raw}", "symbol": raw}
        records = df.to_dict(orient="records")
        return {"symbol": raw, "report_date": date_str, "count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "symbol": raw}


def get_holder_changes(symbol: str) -> dict:
    """股东人数变化：历史股东人数趋势（人数减少=筹码集中=看涨信号）"""
    import akshare as ak
    from datetime import datetime
    import signal

    symbol = _clean_symbol(symbol)

    def timeout_handler(signum, frame):
        raise TimeoutError("股东数据获取超时")

    try:
        # 设置15秒超时
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(15)

        df = ak.stock_zh_a_gdhs(symbol=symbol)

        signal.alarm(0)  # 取消超时

        if df is None or df.empty:
            return {"error": f"无股东人数数据: {symbol}", "symbol": symbol}
        records = df.tail(8).to_dict(orient="records")
        return {"symbol": symbol, "count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except TimeoutError:
        signal.alarm(0)
        return {"error": "数据获取超时(15s)，该股票股东数据量较大，建议稍后重试",
                "symbol": symbol, "timeout": True}
    except Exception as e:
        signal.alarm(0)
        return {"error": str(e), "symbol": symbol}


# ===== 融资融券 =====

def get_margin_data(symbol: str) -> dict:
    """融资融券数据：融资余额、融券余额、融资买入额、融券卖出量"""
    import akshare as ak
    from datetime import datetime, timedelta
    import pandas as pd

    symbol = _clean_symbol(symbol)

    # Validate symbol format (6-digit A-share code)
    if not symbol.isdigit() or len(symbol) != 6:
        return {"error": f"无效股票代码格式: {symbol}，需要6位数字", "symbol": symbol}

    # Determine exchange based on first digit
    # SSE: 6xxxxx (主板), 688xxx (科创板)
    # SZSE: 0xxxxx (主板), 002xxx (中小板), 3xxxxx (创业板)
    if symbol.startswith('6'):
        exchange = 'sse'
        api_func = ak.stock_margin_detail_sse
        symbol_col = '标的证券代码'
    elif symbol.startswith(('0', '2', '3')):
        exchange = 'szse'
        api_func = ak.stock_margin_detail_szse
        symbol_col = '证券代码'
    else:
        return {"error": f"不支持的股票代码: {symbol}（仅支持沪深A股）", "symbol": symbol}

    try:
        # akshare API changed: now returns all stocks for a given date, need to filter
        # Try to get recent 10 trading days of data
        results = []
        errors = []
        today = datetime.now()

        for days_back in range(15):  # Try last 15 days to get ~10 trading days
            date_str = (today - timedelta(days=days_back)).strftime("%Y%m%d")

            try:
                df = api_func(date=date_str)

                if df is not None and not df.empty:
                    # Use exact match, not substring
                    if symbol_col not in df.columns:
                        errors.append(f"{date_str}: 列名不匹配 (expected {symbol_col})")
                        continue

                    # Exact match on symbol
                    filtered = df[df[symbol_col].astype(str) == symbol]
                    if not filtered.empty:
                        record = filtered.iloc[0].to_dict()
                        results.append(record)

                        if len(results) >= 10:
                            break
                    # else: symbol not in margin list for this date (not an error)
            except Exception as e:
                errors.append(f"{date_str}: {str(e)[:50]}")
                # Stop early if we hit 3 consecutive failures (likely API issue)
                if len(errors) >= 3 and not results:
                    break
                continue

        if not results:
            if errors:
                return {
                    "error": f"无法获取融资融券数据: {symbol}",
                    "symbol": symbol,
                    "exchange": exchange,
                    "details": f"尝试了 {len(errors)} 个日期，均失败。最近错误: {errors[-1]}"
                }
            else:
                return {
                    "error": f"该股票不在融资融券标的范围内: {symbol}",
                    "symbol": symbol,
                    "exchange": exchange
                }

        return {
            "symbol": symbol,
            "exchange": exchange,
            "count": len(results),
            "data": results,
            "data_date": datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol, "exchange": exchange if 'exchange' in locals() else 'unknown'}


def get_market_margin() -> dict:
    """全市场融资融券余额趋势：判断市场整体杠杆水平

    返回最近30个交易日的融资融券数据，包括：
    - 全市场融资融券余额（亿元）
    - 上海市场融资融券余额（亿元）
    - 深圳市场融资融券余额（亿元）

    数据来源：上交所和深交所官方数据
    用途：
    - 融资余额上升 → 市场情绪乐观，杠杆加大
    - 融资余额下降 → 市场情绪谨慎，去杠杆
    - 通常融资余额与市场走势正相关
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 使用宏观数据 API 获取融资融券数据
        df_sh = ak.macro_china_market_margin_sh()
        df_sz = ak.macro_china_market_margin_sz()

        if (df_sh is None or df_sh.empty) and (df_sz is None or df_sz.empty):
            return {"error": "无市场融资融券数据"}

        # 获取最近30天的数据
        records = []
        if not df_sh.empty and not df_sz.empty:
            # 取最近30条记录
            df_sh_recent = df_sh.tail(30)
            df_sz_recent = df_sz.tail(30)

            # 按日期合并
            for _, sh_row in df_sh_recent.iterrows():
                date = sh_row['日期']
                sz_row = df_sz_recent[df_sz_recent['日期'] == date]

                if not sz_row.empty:
                    sz_row = sz_row.iloc[0]
                    total_margin = _safe_float(sh_row.get('融资融券余额', 0)) + _safe_float(sz_row.get('融资融券余额', 0))
                    records.append({
                        "date": str(date),
                        "total_margin": total_margin / 100000000,  # 转为亿
                        "sh_margin": _safe_float(sh_row.get('融资融券余额', 0)) / 100000000,
                        "sz_margin": _safe_float(sz_row.get('融资融券余额', 0)) / 100000000
                    })

        return {"count": len(records), "data": records[-10:],
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e)}


# ===== 宏观补充 =====

def get_money_supply() -> dict:
    """货币供应量：M0/M1/M2 同比增速，判断流动性环境"""
    import akshare as ak
    from datetime import datetime
    try:
        df = ak.macro_china_money_supply()
        if df is None or df.empty:
            return {"error": "无货币供应量数据"}
        records = df.tail(6).to_dict(orient="records")
        return {"count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e)}


def get_social_finance() -> dict:
    """社会融资规模：新增社融、信贷数据，判断经济扩张/收缩"""
    import akshare as ak
    from datetime import datetime
    try:
        df = ak.macro_china_shrzgm()
        if df is None or df.empty:
            return {"error": "无社融数据"}
        records = df.tail(6).to_dict(orient="records")
        return {"count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e)}


def get_gdp_data() -> dict:
    """GDP 季度数据：同比增速，判断经济周期位置"""
    import akshare as ak
    from datetime import datetime
    try:
        df = ak.macro_china_gdp()
        if df is None or df.empty:
            return {"error": "无GDP数据"}
        records = df.tail(8).to_dict(orient="records")
        return {"count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e)}


# ===== 公告 =====

@timeout_decorator(seconds=30)
def get_announcements(symbol: str) -> dict:
    """个股公告列表：公告标题、日期、类型（业绩/分红/重组等）"""
    import akshare as ak
    from datetime import datetime, timedelta
    raw = _clean_symbol(symbol)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=raw, market="沪深京",
            start_date=start_date, end_date=end_date
        )
        if df is None or df.empty:
            return {"error": f"无公告数据: {raw}", "symbol": raw}
        records = df.head(20).to_dict(orient="records")
        return {"symbol": raw, "count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "symbol": raw}


# ===== 行业资金流向 =====

@timeout_decorator(seconds=30)
def get_sector_fund_flow() -> dict:
    """行业资金流向：各行业今日主力净流入/流出排行

    返回90个行业的实时资金流向数据，包括：
    - 行业名称和指数
    - 涨跌幅
    - 流入资金、流出资金、净额（亿元）
    - 公司家数
    - 领涨股及涨跌幅

    数据来源：东方财富网行业资金流
    用途：识别资金轮动方向，判断市场热点板块
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 使用 stock_fund_flow_industry 获取行业资金流向
        df = ak.stock_fund_flow_industry(symbol='即时')
        if df is None or df.empty:
            return {"error": "无行业资金流向数据"}
        records = df.head(20).to_dict(orient="records")
        return {"count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e)}


@timeout_decorator(seconds=30)
def get_stock_fund_flow(symbol: str) -> dict:
    """个股资金流向：主力/超大单/大单/中单/小单净流入"""
    import akshare as ak
    from datetime import datetime
    symbol = _clean_symbol(symbol)
    try:
        if symbol.startswith("6"):
            market = "sh"
        elif symbol.startswith(("8", "4")):
            market = "bj"
        else:
            market = "sz"
        df = ak.stock_individual_fund_flow(stock=symbol, market=market)
        if df is None or df.empty:
            return {"error": f"无资金流向数据: {symbol}", "symbol": symbol}
        records = df.tail(10).to_dict(orient="records")
        return {"symbol": symbol, "count": len(records), "data": records,
                "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def analyze_price_action(symbol: str) -> dict:
    """技术面深度分析：趋势、动量、波动率、量价与关键价位"""
    import pandas as pd
    import numpy as np
    from datetime import datetime

    symbol = _clean_symbol(symbol)
    if not (symbol.isdigit() and len(symbol) == 6):
        return {"error": "symbol 必须为 6 位 A 股代码", "symbol": symbol}

    try:
        history = get_stock_history(symbol=symbol, period="daily")
        if "error" in history:
            return history

        records = history.get("data", [])
        if len(records) < 60:
            return {"error": "历史数据不足（需要至少60个交易日）", "symbol": symbol}

        df = pd.DataFrame(records).copy()
        if df.empty:
            return {"error": f"无历史数据: {symbol}", "symbol": symbol}

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = df["date"].astype(str)
        df = df.dropna(subset=["high", "low", "close", "volume"]).sort_values("date").reset_index(drop=True)
        if len(df) < 60:
            return {"error": "历史数据不足（有效数据少于60个交易日）", "symbol": symbol}

        recent = df.tail(60).reset_index(drop=True)
        close = recent["close"]
        high = recent["high"]
        low = recent["low"]
        volume = recent["volume"]
        current = float(close.iloc[-1])

        raw_52w = _sina_stock_history(symbol, datalen=260, scale=240)
        if not raw_52w or len(raw_52w) < 250:
            return {"error": "历史数据不足（52周分析至少需要250个交易日）", "symbol": symbol}

        df_52w = pd.DataFrame(raw_52w).copy()
        for col in ["high", "low", "close", "volume"]:
            df_52w[col] = pd.to_numeric(df_52w[col], errors="coerce")
        df_52w["day"] = df_52w["day"].astype(str)
        df_52w = df_52w.dropna(subset=["high", "low", "close", "volume"]).sort_values("day").reset_index(drop=True)
        if len(df_52w) < 250:
            return {"error": "历史数据不足（52周有效数据少于250个交易日）", "symbol": symbol}

        ma5 = close.rolling(5, min_periods=5).mean().iloc[-1]
        ma20 = close.rolling(20, min_periods=20).mean().iloc[-1]
        ma60 = close.rolling(60, min_periods=60).mean().iloc[-1]

        ma20_series = df_52w["close"].rolling(20, min_periods=20).mean()
        ma60_series = df_52w["close"].rolling(60, min_periods=60).mean()
        ma20_prev = ma20_series.iloc[-5] if len(ma20_series.dropna()) >= 5 else ma20_series.iloc[-1]
        ma60_prev = ma60_series.iloc[-5] if len(ma60_series.dropna()) >= 5 else ma60_series.iloc[-1]

        if current > ma5 > ma20 > ma60:
            direction = "上升"
            gap_short = (ma5 - ma20) / ma20 * 100 if ma20 else 0
            gap_mid = (ma20 - ma60) / ma60 * 100 if ma60 else 0
            if ma20 > ma20_prev and ma60 > ma60_prev and gap_short >= 1 and gap_mid >= 2:
                strength = "强"
            elif gap_short >= 0.3 and gap_mid >= 0.8:
                strength = "中"
            else:
                strength = "弱"
        elif current < ma5 < ma20 < ma60:
            direction = "下降"
            gap_short = (ma20 - ma5) / ma20 * 100 if ma20 else 0
            gap_mid = (ma60 - ma20) / ma60 * 100 if ma60 else 0
            if ma20 < ma20_prev and ma60 < ma60_prev and gap_short >= 1 and gap_mid >= 2:
                strength = "强"
            elif gap_short >= 0.3 and gap_mid >= 0.8:
                strength = "中"
            else:
                strength = "弱"
        else:
            direction, strength = "震荡", "弱"

        low_9 = low.rolling(9, min_periods=9).min()
        high_9 = high.rolling(9, min_periods=9).max()
        rsv = (close - low_9) / (high_9 - low_9).replace(0, np.nan) * 100
        rsv = rsv.fillna(50)
        k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
        d = k.ewm(alpha=1 / 3, adjust=False).mean()
        j = 3 * k - 2 * d
        kdj_k = float(k.iloc[-1])
        kdj_d = float(d.iloc[-1])
        kdj_j = float(j.iloc[-1])
        if kdj_k >= 80 and kdj_d >= 80:
            kdj_signal = "超买"
        elif kdj_k <= 20 and kdj_d <= 20:
            kdj_signal = "超卖"
        else:
            kdj_signal = "中性"

        typical_price = (high + low + close) / 3
        cci_ma = typical_price.rolling(20, min_periods=20).mean()
        cci_md = typical_price.rolling(20, min_periods=20).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )
        cci = (typical_price - cci_ma) / (0.015 * cci_md.replace(0, np.nan))
        cci_value = float(cci.iloc[-1])
        if cci_value >= 100:
            cci_signal = "超买"
        elif cci_value <= -100:
            cci_signal = "超卖"
        else:
            cci_signal = "中性"

        prev_close = close.shift(1)
        tr = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        atr = float(tr.rolling(14, min_periods=14).mean().iloc[-1])

        support = float(low.min())
        resistance = float(high.max())

        rolling_peak = close.cummax()
        drawdown = close / rolling_peak - 1
        max_dd = float(drawdown.min() * 100)

        obv = (np.sign(close.diff().fillna(0)) * volume).cumsum()
        obv_anchor = obv.iloc[-5] if len(obv) >= 5 else obv.iloc[0]
        if obv.iloc[-1] > obv_anchor:
            obv_trend = "上升"
        elif obv.iloc[-1] < obv_anchor:
            obv_trend = "下降"
        else:
            obv_trend = "震荡"

        recent_52w = df_52w.tail(250).reset_index(drop=True)
        high_52w = float(recent_52w["high"].max())
        low_52w = float(recent_52w["low"].min())
        distance_to_high_52w_pct = (current - high_52w) / high_52w * 100 if high_52w else 0
        distance_to_low_52w_pct = (current - low_52w) / low_52w * 100 if low_52w else 0

        changes = close.diff().fillna(0)
        streak_direction = "平"
        streak_days = 0
        if changes.iloc[-1] > 0:
            streak_direction = "上涨"
            for value in reversed(changes.iloc[1:].tolist()):
                if value > 0:
                    streak_days += 1
                else:
                    break
        elif changes.iloc[-1] < 0:
            streak_direction = "下跌"
            for value in reversed(changes.iloc[1:].tolist()):
                if value < 0:
                    streak_days += 1
                else:
                    break

        return {
            "symbol": symbol,
            "trend": {
                "ma5": _safe_float(ma5),
                "ma20": _safe_float(ma20),
                "ma60": _safe_float(ma60),
                "direction": direction,
                "strength": strength,
            },
            "momentum": {
                "kdj_k": _safe_float(kdj_k),
                "kdj_d": _safe_float(kdj_d),
                "kdj_j": _safe_float(kdj_j),
                "signal": kdj_signal,
            },
            "cci": {
                "cci": _safe_float(cci_value),
                "signal": cci_signal,
            },
            "support_resistance": {
                "support": _safe_float(support),
                "resistance": _safe_float(resistance),
            },
            "volatility": {
                "atr": _safe_float(atr),
                "atr_pct": _safe_float(atr / current * 100 if current else 0),
                "max_drawdown_pct": _safe_float(max_dd),
            },
            "volume": {
                "obv": _safe_float(obv.iloc[-1], decimals=0),
                "obv_trend": obv_trend,
                "volume_ma5": _safe_float(volume.rolling(5).mean().iloc[-1], decimals=0),
            },
            "price_range_52w": {
                "high_52w": _safe_float(high_52w),
                "low_52w": _safe_float(low_52w),
                "distance_to_high_52w_pct": _safe_float(distance_to_high_52w_pct),
                "distance_to_low_52w_pct": _safe_float(distance_to_low_52w_pct),
            },
            "streak": {
                "direction": streak_direction,
                "days": streak_days,
            },
            "current_price": _safe_float(current),
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def combine_strategy_signals(params: dict) -> dict:
    """
    Combine multiple strategy signals using StrategyCombiner.

    Args:
        params: {
            'signals': [
                {
                    'timestamp': '2026-05-19T10:00:00',
                    'symbol': '600519',
                    'action': 'buy',
                    'price': 1800.0,
                    'strategy_id': 'rsi_reversal',
                    'confidence': 0.8,
                    'reason': 'RSI=28'
                },
                ...
            ],
            'mode': 'vote',  # 'or', 'and', 'vote'
            'weights': {'rsi_reversal': 1.5, 'ma_cross': 1.0},  # optional
            'confidence_threshold': 0.5,  # optional
            'min_agree_count': 1  # optional for AND mode
        }

    Returns:
        {
            'combined_signals': [...],
            'metadata': {...}
        }
    """
    try:
        signals_data = params.get('signals', [])
        mode = params.get('mode', 'vote')
        weights = params.get('weights', {})
        confidence_threshold = params.get('confidence_threshold', 0.5)
        min_agree_count = params.get('min_agree_count', 1)

        # Convert TypeScript signals to Python Signal dataclass
        python_signals = []
        for sig in signals_data:
            timestamp_str = sig.get('timestamp', '')
            # Parse ISO timestamp
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.now()

            python_sig = CombinerSignal(
                timestamp=timestamp,
                symbol=sig.get('symbol', ''),
                action=sig.get('action', 'hold'),
                price=float(sig.get('price', 0)),
                quantity=int(sig.get('quantity', 0)),
                strategy_id=sig.get('strategy_id', ''),
                reason=sig.get('reason', ''),
                confidence=float(sig.get('confidence', 0.5)),
                metadata=sig.get('metadata', {})
            )
            python_signals.append(python_sig)

        # Create combiner config
        config = CombinerConfig(
            mode=mode,
            weights=weights,
            confidence_threshold=confidence_threshold,
            min_agree_count=min_agree_count
        )

        # Combine signals
        combiner = StrategyCombiner(config)
        combined_signals, metadata = combiner.combine_signals(python_signals)

        # Convert back to JSON-serializable format
        result_signals = []
        for sig in combined_signals:
            result_signals.append({
                'timestamp': sig.timestamp.isoformat(),
                'symbol': sig.symbol,
                'action': sig.action,
                'price': sig.price,
                'quantity': sig.quantity,
                'strategy_id': sig.strategy_id,
                'reason': sig.reason,
                'confidence': sig.confidence,
                'metadata': sig.metadata
            })

        return {
            'combined_signals': result_signals,
            'metadata': metadata
        }

    except Exception as e:
        logger.error(f"combine_strategy_signals error: {e}")
        traceback.print_exc()
        return {
            'error': str(e),
            'combined_signals': [],
            'metadata': {'reason': 'python_error', 'error': str(e)}
        }


# ===== Risk Control Functions =====
def check_trade_risk(symbol: str, action: str, price: float, shares: int) -> dict:
    """预交易风控检查"""
    portfolio_db = os.path.join(os.path.dirname(__file__), '..', '.pi-invest', 'portfolio.db')
    quant_db = os.path.join(os.path.dirname(__file__), '..', 'quant', 'quantsys', 'data', 'stocks.db')

    bridge = RiskBridge(portfolio_db, quant_db)
    result = bridge.check_trade_risk(symbol, action, price, shares)
    return result


def calculate_position_size(symbol: str, price: float, signal_strength: float = 1.0) -> dict:
    """Kelly公式计算建议仓位"""
    portfolio_db = os.path.join(os.path.dirname(__file__), '..', '.pi-invest', 'portfolio.db')
    quant_db = os.path.join(os.path.dirname(__file__), '..', 'quant', 'quantsys', 'data', 'stocks.db')

    bridge = RiskBridge(portfolio_db, quant_db)
    result = bridge.calculate_position_size(symbol, price, signal_strength)
    return result


def calculate_stop_loss(symbol: str, entry_price: float, current_price: float = None, highest_price: float = None) -> dict:
    """计算止损价（混合策略）"""
    portfolio_db = os.path.join(os.path.dirname(__file__), '..', '.pi-invest', 'portfolio.db')
    quant_db = os.path.join(os.path.dirname(__file__), '..', 'quant', 'quantsys', 'data', 'stocks.db')

    bridge = RiskBridge(portfolio_db, quant_db)
    result = bridge.calculate_stop_loss(symbol, entry_price, current_price, highest_price)
    return result


# ===== Dispatcher =====
FUNCTIONS = {
    "get_stock_info": get_stock_info,
    "get_stock_realtime_price": get_stock_realtime_price,
    "get_stock_history": get_stock_history,
    "get_financial_indicators": get_financial_indicators,
    "get_sector_list": get_sector_list,
    "screen_stocks_by_sector": screen_stocks_by_sector,
    "screen_stocks_quality": screen_stocks_quality,
    "get_stock_news": get_stock_news,
    "get_concept_stocks": get_concept_stocks,
    "get_concept_list": get_concept_list,
    "calculate_technical_indicators": calculate_technical_indicators,
    "analyze_price_action": analyze_price_action,
    "calculate_buy_range": calculate_buy_range,
    "get_stock_valuation": get_stock_valuation,
    "get_pe_percentile": get_pe_percentile,
    "get_quality_score": get_quality_score,
    "get_exit_plan": get_exit_plan,
    "get_macro_data": get_macro_data,
    "get_north_flow": get_north_flow,
    "get_market_overview": get_market_overview,
    "get_index_history": get_index_history,
    "get_stock_list": get_stock_list,
    "manage_portfolio": manage_portfolio,
    "get_financial_statements": get_financial_statements,
    "get_balance_sheet": get_balance_sheet,
    "get_income_statement": get_income_statement,
    "get_cash_flow": get_cash_flow,
    "get_insider_trades": get_insider_trades,
    # 龙虎榜（合并）
    "get_lhb": get_lhb,
    # 机构持仓
    "get_fund_holdings": get_fund_holdings,
    "get_top_fund_stocks": get_top_fund_stocks,
    # 股东信息
    "get_top_holders": get_top_holders,
    "get_holder_changes": get_holder_changes,
    # 融资融券
    "get_margin_data": get_margin_data,
    "get_market_margin": get_market_margin,
    # 公告
    "get_announcements": get_announcements,
    # 综合新闻
    "get_market_news": get_market_news,
    "get_hot_stocks": get_hot_stocks,
    # 资金流向
    "get_sector_fund_flow": get_sector_fund_flow,
    "get_stock_fund_flow": get_stock_fund_flow,
    # HK stocks — basic
    "get_hk_stock_price": get_hk_stock_price,
    "get_hk_stock_info": get_hk_stock_info,
    "get_hk_stock_history": get_hk_stock_history,
    "get_hk_financials": get_hk_financials,
    "get_hk_analysis": get_hk_analysis,
    # HK stocks — new tools
    "get_hk_market_overview": get_hk_market_overview,
    "get_hk_south_flow": get_hk_south_flow,
    "get_hk_technical": get_hk_technical,
    "get_hk_hot_rank": get_hk_hot_rank,
    # ML functions
    "predict_signal_confidence": lambda features: predict_signal_confidence(features),
    "train_signal_model": lambda days=30, min_samples=50: train_signal_model(days, min_samples),
    "ml_predict_single": lambda symbol: ml_predict_single(symbol),
    # Visualization functions
    "plot_model_accuracy_trend": lambda days=90, output_path='.pi-invest/quant/charts/accuracy_trend.png': plot_model_accuracy_trend(days, output_path),
    "plot_equity_curve": lambda backtest_result, output_path='.pi-invest/quant/charts/equity_curve.png': plot_equity_curve(backtest_result, output_path),
    "plot_strategy_comparison": lambda strategies_performance, output_path='.pi-invest/quant/charts/strategy_comparison.png': plot_strategy_comparison(strategies_performance, output_path),
    "plot_feature_importance": lambda model_path='.pi-invest/quant/models/signal_confidence.pkl', output_path='.pi-invest/quant/charts/feature_importance.png': plot_feature_importance(model_path, output_path),
    # Strategy combiner
    "combine_strategy_signals": lambda **kwargs: combine_strategy_signals(kwargs),
    # Risk control functions
    "check_trade_risk": check_trade_risk,
    "calculate_position_size": calculate_position_size,
    "calculate_stop_loss": calculate_stop_loss,
}


def predict_signal_confidence(features: dict) -> dict:
    """Predict signal confidence using ML model"""
    from ml.signal_predictor import predict_confidence
    return predict_confidence(features)


def train_signal_model(days: int = 30, min_samples: int = 50) -> dict:
    """Train signal confidence model"""
    from ml.signal_trainer import train_model
    return train_model(days, min_samples)


def ml_predict_single(symbol: str) -> dict:
    """Predict single stock using trained ML model"""
    import sys
    import os

    # Add quant directory to path
    quant_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'quant')
    if quant_dir not in sys.path:
        sys.path.insert(0, quant_dir)

    try:
        from scripts.ml_predict import MLPredictor
        from quantsys.data.db import Database

        # Database path
        db_path = os.path.join(quant_dir, 'quantsys', 'data', 'stocks.db')
        if not os.path.exists(db_path):
            return {"error": f"Database not found: {db_path}"}

        # Model path
        model_path = os.path.join(quant_dir, 'quantsys', 'ml', 'models', 'xgboost_model.pkl')
        if not os.path.exists(model_path):
            return {"error": f"Model not found: {model_path}. Please train the model first."}

        # Initialize predictor
        db = Database(db_path)
        predictor = MLPredictor(db, model_path)

        # Load model
        if not predictor.load_model():
            return {"error": "Failed to load model"}

        # Get latest date
        latest_date = predictor.get_latest_date()
        if not latest_date:
            return {"error": "No data available in database"}

        # Predict
        prediction = predictor.predict_stock(symbol, latest_date)

        if not prediction:
            return {"error": f"Failed to predict {symbol}. Check if data exists for this symbol."}

        return prediction

    except Exception as e:
        return {"error": str(e)}


def plot_model_accuracy_trend(days: int = 90, output_path: str = '.pi-invest/quant/charts/accuracy_trend.png') -> dict:
    """Plot model accuracy trend chart"""
    from ml.visualizer import plot_model_accuracy_trend
    return plot_model_accuracy_trend(days, output_path)


def plot_equity_curve(backtest_result: dict, output_path: str = '.pi-invest/quant/charts/equity_curve.png') -> dict:
    """Plot backtest equity curve chart"""
    from ml.visualizer import plot_equity_curve
    return plot_equity_curve(backtest_result, output_path)


def plot_strategy_comparison(strategies_performance: list, output_path: str = '.pi-invest/quant/charts/strategy_comparison.png') -> dict:
    """Plot strategy comparison chart"""
    from ml.visualizer import plot_strategy_comparison
    return plot_strategy_comparison(strategies_performance, output_path)


def plot_feature_importance(model_path: str = '.pi-invest/quant/models/signal_confidence.pkl', output_path: str = '.pi-invest/quant/charts/feature_importance.png') -> dict:
    """Plot feature importance chart"""
    from ml.visualizer import plot_feature_importance
    return plot_feature_importance(model_path, output_path)


def daemon_mode():
    """
    Daemon mode: read JSON-RPC requests from stdin, execute functions, write responses to stdout.

    Request format:
        {"jsonrpc": "2.0", "id": 1, "method": "get_stock_info", "params": {"symbol": "600519"}}

    Response format:
        {"jsonrpc": "2.0", "id": 1, "result": {...}}
        {"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "..."}}
    """
    import sys

    # Ensure stdout is line-buffered for immediate response delivery
    sys.stdout.reconfigure(line_buffering=True)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                # EOF reached, exit gracefully
                break

            line = line.strip()
            if not line:
                continue

            # Parse JSON-RPC request
            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                # Invalid JSON, send error response without ID
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                print(safe_json_dumps(error_response), flush=True)
                continue

            req_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            # Validate request
            if request.get("jsonrpc") != "2.0":
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32600, "message": "Invalid Request: jsonrpc must be '2.0'"}
                }
                print(safe_json_dumps(error_response), flush=True)
                continue

            if not method or not isinstance(method, str):
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32600, "message": "Invalid Request: method is required"}
                }
                print(safe_json_dumps(error_response), flush=True)
                continue

            # Execute function
            func = FUNCTIONS.get(method)
            if not func:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
                print(safe_json_dumps(error_response), flush=True)
                continue

            try:
                result = func(**params)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result
                }
                print(safe_json_dumps(response), flush=True)
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": str(e),
                        "data": {"trace": traceback.format_exc()}
                    }
                }
                print(safe_json_dumps(error_response), flush=True)

        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            break
        except Exception as e:
            # Unexpected error in main loop
            sys.stderr.write(f"Daemon loop error: {str(e)}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--daemon":
        daemon_mode()
    elif len(sys.argv) < 2:
        print(safe_json_dumps({"error": "Usage: akshare_bridge.py <function> [json_args] OR akshare_bridge.py --daemon"}))
        sys.exit(1)
    else:
        # Legacy CLI mode
        func_name = sys.argv[1]
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        func = FUNCTIONS.get(func_name)
        if not func:
            print(safe_json_dumps({"error": f"Unknown function: {func_name}"}))
            sys.exit(1)
        try:
            result = func(**args)
            print(safe_json_dumps(result))
        except Exception as e:
            print(safe_json_dumps({"error": str(e), "trace": traceback.format_exc()}))
