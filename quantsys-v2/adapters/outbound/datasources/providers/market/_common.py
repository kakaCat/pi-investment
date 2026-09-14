"""market 域 provider 共用辅助（2026-09-14，w-2129d492，REQ-48d896）

股东/基金/千股千评类数据由**多个源**（akshare、东财直连）实现，这些辅助必须只有
一份实现 —— 否则两个源会各自演化出不同口径（本仓"平行实现"已出过多次事故）。

包含：
  · TTL 缓存          —— 全市场接口（2.5 万行级）跨源共用，避免每请求打上游
  · 前缀/报告期/季度   —— 符号与报告期口径的唯一实现（前缀规则复用 industry_chain）
  · df_records        —— DataFrame → JSON 安全 records（日期必须转字符串）
  · is_transport_error—— 「传输故障」与「该期间无数据」的分流依据
"""
import threading
import time as _time
from datetime import datetime
from typing import Optional


# ── TTL 缓存（全市场接口跨源共用）──────────────────────────────────────────
SENTIMENT_CACHE: dict = {}
SENTIMENT_CACHE_LOCK = threading.Lock()
SENTIMENT_CACHE_TTLS = {
    'inner_trades': 300.0,    # 内部人交易按日更新
    'stock_comment': 600.0,   # 千股千评盘中会变
    'fund_hold': 1800.0,      # 基金/机构持仓按季度披露
}


def cached_df(name: str, loader):
    """按 name 做 TTL 缓存的 DataFrame 获取；失败/空**不写入**缓存（下次重试）。"""
    ttl = SENTIMENT_CACHE_TTLS.get(name, 600.0)
    now = _time.monotonic()
    with SENTIMENT_CACHE_LOCK:
        hit = SENTIMENT_CACHE.get(name)
        if hit and now - hit[0] < ttl:
            return hit[1]
    df = loader()
    if df is None or getattr(df, 'empty', False):
        return None
    with SENTIMENT_CACHE_LOCK:
        SENTIMENT_CACHE[name] = (now, df)
    return df


# ── 「传输故障」vs「该期间无数据」──────────────────────────────────────────
# akshare 在「报告期无数据」时抛的是解析异常（ValueError/KeyError），不是网络异常。
# 把「无数据」当故障会让熔断器误伤健康源；把「网络挂」当无数据就是假成功。
_TRANSPORT_ERROR_TYPES = (ConnectionError, TimeoutError)


def is_transport_error(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSPORT_ERROR_TYPES):
        return True
    mod = type(exc).__module__ or ''
    return mod.startswith(('requests', 'urllib3', 'http', 'socket', 'ssl'))


def recent_report_periods(count: int = 4) -> list:
    """最近 count 个候选财报报告期（YYYYMMDD，新→旧）。

    披露有滞后（年报次年 4/30 前、季报次月底前），故这里只给候选序列，
    由调用方按序回退取到数据为止 —— 不猜「哪个已披露」。
    """
    today = datetime.now().date()
    cands = []
    for y in (today.year, today.year - 1, today.year - 2):
        for md in ('1231', '0930', '0630', '0331'):
            d = datetime(int(y), int(md[:2]), int(md[2:])).date()
            if d <= today:
                cands.append(d)
    return [d.strftime('%Y%m%d') for d in sorted(set(cands), reverse=True)[:count]]


def em_prefixed_lower(symbol: str) -> str:
    """600519 → sh600519（东财小写前缀）。

    复用 industry_chain 已有的 market_prefixed（全仓前缀规则唯一实现），
    本处只做大小写转换 —— 不重写一份前缀规则。
    """
    from adapters.outbound.datasources.providers.industry_chain.eastmoney_revenue import (
        market_prefixed,
    )
    return market_prefixed(symbol).lower()


def secucode(symbol: str) -> str:
    """600519 → 600519.SH（东财 datacenter 的 SECUCODE 形式）；无法识别返回 ''。"""
    from adapters.outbound.datasources.providers.industry_chain.eastmoney_revenue import (
        market_prefixed,
    )
    p = market_prefixed(symbol)
    if not p:
        return ''
    return '%s.%s' % (p[2:], p[:2])


def df_records(df) -> list:
    """DataFrame → JSON 安全 records。

    日期/时间列必须转成字符串：\`datetime.date\` 不是 JSON 可序列化类型，
    直接塞进响应会让路由在编码阶段 500。
    """
    records = df.astype(object).where(df.notna(), None).to_dict('records')
    for rec in records:
        for key, val in rec.items():
            if hasattr(val, 'isoformat'):
                rec[key] = val.isoformat()
    return records


def normalize_quarter(quarter) -> Optional[str]:
    """'2024Q4' / '20241231' / '2024-12-31' → 'YYYY-MM-DD'；无法解析返回 None。"""
    if not quarter:
        return None
    q = str(quarter).strip().upper().replace('-', '')
    qmap = {'Q1': '0331', 'Q2': '0630', 'Q3': '0930', 'Q4': '1231'}
    if q.endswith(tuple(qmap)):
        year, qn = q[:4], q[-2:]
        if year.isdigit() and qn in qmap:
            q = year + qmap[qn]
    if len(q) == 8 and q.isdigit():
        return '%s-%s-%s' % (q[:4], q[4:6], q[6:])
    return None
