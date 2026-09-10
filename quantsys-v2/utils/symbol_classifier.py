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
