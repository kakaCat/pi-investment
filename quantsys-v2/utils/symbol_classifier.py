"""指数 / 伪代码识别（共享工具）。

建立背景（2026-09-10，w-23c70356）：
quant.daily_klines 混入指数伪行（399300 沪深300深 / 399001 深证成指 / 399006 创业板指 /
000300 沪深300），其 volume 是「成分股聚合成交量」，与个股不同量纲。任何
"amount = volume × close" 的估算在指数上都会产出天文数字——实测深证成指
2026-09-01 被估成 949.86 万亿元（全市场真实单日成交额仅约 2 万亿元量级），
共 638 行金额合计 75,830 万亿元。这类行必须被写入路径的估算与自检显式排除，
否则每日同步会持续复现污染。

判定规则（与 application/services/data_backfiller._is_index_symbol 同源，
两处共用本模块以避免逻辑漂移）：
1. 白名单命中即候选；歧义代码（000001 上证指数 vs 平安银行、000016 vs *ST康佳A、
   000905 vs 厦门港务、000852 vs 石化机械）须再查 stocks 表——存在真实股票记录
   （list_date 非空）则按个股处理。查表失败时保守按指数处理。
2. 399xxx（深证指数族）恒为指数，不查表。
3. 含 '.' 的代码（如 600000.SH）为非标准/伪代码，不应参与个股口径的估算与统计。
"""
import logging

logger = logging.getLogger(__name__)

# 常见指数白名单（歧义代码需再过 stocks 表，见 is_index_symbol）
INDEX_WHITELIST = frozenset({
    '000001',  # 上证指数（歧义：平安银行）
    '000300',  # 沪深300
    '399001',  # 深证成指
    '399005',  # 中小板指
    '399006',  # 创业板指
    '399300',  # 沪深300（深）
    '000016',  # 上证50（歧义：*ST康佳A）
    '000905',  # 中证500（歧义：厦门港务）
    '000852',  # 中证1000（歧义：石化机械）
    '000906',  # 中证800
})

# SQL 排除用清单：白名单 + 399 族无法穷举，调用方可只用白名单 +
# symbol ~ '^399' 的方式（见 index_symbols_sql_predicate）。
INDEX_SYMBOLS = tuple(sorted(INDEX_WHITELIST))


def is_index_symbol(symbol: str) -> bool:
    """是否为指数代码（白名单 + stocks 表真实股票校验）。"""
    s = (symbol or '').strip()
    if not s:
        return False
    if s.startswith('399') and len(s) == 6 and s.isdigit():
        return True
    if s not in INDEX_WHITELIST:
        return False
    try:
        from adapters.shared.services import get_stock_repo
        stock = get_stock_repo().get_by_symbol(s)
        if stock is not None and getattr(stock, 'list_date', None) is not None:
            return False
    except Exception as e:  # noqa: BLE001 - 查表失败保守按指数处理
        logger.warning(f"is_index_symbol stocks 校验失败 {s}: {e}")
    return True


def is_pseudo_symbol(symbol: str) -> bool:
    """指数或非标准代码（含 '.'、非 6 位数字）→ 不参与个股口径估算/统计。"""
    s = (symbol or '').strip().upper()
    if not s:
        return True
    if '.' in s:
        return True
    if not (len(s) == 6 and s.isdigit()):
        return True
    return is_index_symbol(s)


def index_symbols_for_exclusion() -> tuple:
    """已确认为指数的代码元组（供 SQL "NOT (symbol = ANY(%s))" 使用）。

    歧义代码（000001 平安银行 / 000016 *ST康佳A / 000905 厦门港务 / 000852 石化机械）
    经 stocks 表核实后仅保留纯指数者，避免误排除真实个股的缺失成交额告警。
    399 族不在本元组内，SQL 侧用 symbol !~ '^399' 覆盖。
    """
    return tuple(sorted(
        s for s in INDEX_WHITELIST
        if not s.startswith('399') and is_index_symbol(s)
    ))


def index_symbols_sql_predicate(column: str = 'symbol') -> str:
    """返回"排除指数行"的 SQL 片段（配合 INDEX_SYMBOLS 参数使用）。"""
    return (f"NOT ({column} = ANY(%s)) AND {column} !~ '^399' AND position('.' in {column}) = 0")


def resolve_index_symbol(symbol: str) -> 'str | None':
    """把请求里的指数标识规范化为 quant.index_daily 的键（带市场后缀）。

    2026-09-11（w-f4aa1f6a）：指数价格已与个股 K 线**分表**——指数存 quant.index_daily，
    键带市场后缀（000300.SH / 399001.SZ），daily_klines 只放个股。

    接受的写法：'000300'（裸码）、'000300.SH'、'sh000300'（新浪风格）。
    **与指数同码的深市个股返回 None**（000001 平安银行 / 000016 *ST康佳A / 000905 厦门港务 …）
    ——这正是本函数存在的意义：同一串数字，靠 stocks 表定夺它是谁。

    Returns:
        规范化的指数键（如 '000300.SH'），非指数返回 None。
    """
    s = (symbol or '').strip()
    if not s:
        return None
    market_hint = None
    low = s.lower()
    if len(low) > 6 and low[:2] in ('sh', 'sz'):
        market_hint, s = low[:2].upper(), s[2:]
    if '.' in s:
        code, _, mkt = s.partition('.')
        market_hint = (mkt or '').strip().upper() or market_hint
        s = code
    if not s.isdigit() or len(s) != 6:
        return None
    # 2026-09-11（w-348bf585, REQ-733c5e）：显式市场后缀/前缀优先于 stocks 表歧义裁决。
    # 对歧义码（000001 上证指数/平安银行、000016 上证50/*ST康佳A、000905 中证500/厦门港务、
    # 000852 中证1000/石化机械、000906 中证800），'.SH' 后缀或 'sh' 前缀恒为指数——
    # 深市个股不可能挂 .SH（厦门港务是 000905.SZ）。此前 resolve 只查 stocks 表，导致
    # '000905.SH' / 'sh000905' 被错配到同名深市个股（静默返回个股K线，无任何歧义提示）。
    if market_hint == 'SH' and s in INDEX_WHITELIST and not s.startswith('399'):
        return f'{s}.SH'
    if not is_index_symbol(s):   # 白名单 + stocks 表定夺（歧义码在此被排除）
        return None
    # 399 族恒为深证指数；其余白名单指数为沪市
    market = market_hint or ('SZ' if s.startswith('399') else 'SH')
    return f'{s}.{market}'

# ==================== REQ-733c5e：解析元数据 + 歧义告警（w-348bf585, 2026-09-11） ====================

# 指数名称表（告警与展示用；覆盖白名单全部代码）
INDEX_NAMES = {
    '000001': '上证指数',
    '000016': '上证50',
    '000300': '沪深300',
    '399300': '沪深300',
    '399001': '深证成指',
    '399005': '中小板指',
    '399006': '创业板指',
    '000852': '中证1000',
    '000905': '中证500',
    '000906': '中证800',
}


def _bare_code(symbol: str) -> 'tuple[str, bool]':
    """剥掉 sh/sz 前缀与 .XX 后缀，返回 (六位代码, 是否带显式市场标识)。"""
    raw = (symbol or '').strip()
    if not raw:
        return '', False
    hinted = ('.' in raw) or raw.lower()[:2] in ('sh', 'sz')
    code = raw.split('.')[0]
    for p in ('sh', 'sz'):
        if raw.lower().startswith(p):
            code = raw[2:]
    return code, hinted


def build_resolution_meta(symbol: str, resolved_kind: str, resolved_key: str,
                          stock_name: 'str | None' = None) -> dict:
    """组装 K 线响应的解析元数据：解析身份/名称 + 歧义告警（REQ-733c5e）。

    目的：杜绝"指数/股票同码"导致的静默错配——历史上 agent 曾把 000905（厦门港务）
    的 K 线当作中证500 指数回撤用于抄底判断。meta 里显式声明本次解析结果与替代写法。

    Args:
        symbol: 原始入参（可能带 .XX 后缀或 sh/sz 前缀）
        resolved_kind: 'index' 或 'stock'
        resolved_key: 最终用于取数的键（指数带 .SH/.SZ 后缀）
        stock_name: 股票名（stock 路径时传入；指数路径忽略）
    Returns:
        dict：resolved_kind / resolved_symbol / resolved_name(可选) /
              ambiguity_warning 或 ambiguity_note(可选)
    """
    meta: dict = {'resolved_kind': resolved_kind, 'resolved_symbol': resolved_key}
    code, hinted = _bare_code(symbol)
    if resolved_kind == 'index':
        name = INDEX_NAMES.get(code) or INDEX_NAMES.get(resolved_key.split('.')[0])
        if name:
            meta['resolved_name'] = name
    elif stock_name:
        meta['resolved_name'] = stock_name

    # 歧义提示：仅对"白名单歧义码 + 裸码（未带市场标识）"提示——显式 .SH/.SZ 已消歧，不再告警
    if not hinted and code in INDEX_WHITELIST and not code.startswith('399'):
        idx_name = INDEX_NAMES.get(code, code)
        if resolved_kind == 'stock':
            meta['ambiguity_warning'] = (
                f"代码 {code} 存在『指数/股票』歧义：本次已按股票解析"
                + (f"『{meta.get('resolved_name')}』" if meta.get('resolved_name') else '')
                + f"；若你要的是指数『{idx_name}』，请传 {code}.SH 或 sh{code}。"
            )
        else:
            meta['ambiguity_note'] = (
                f"代码 {code} 存在歧义，本次已按指数『{meta.get('resolved_name', idx_name)}』解析；"
                f"若要同名深市个股请传 {code}.SZ。"
            )
    return meta

