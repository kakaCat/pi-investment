"""分钟线 provider 基类 + 周期/取数窗口公共工具

RFC 015 §4.3 / §1.5（2026-09-11 REQ-cf627b）：
- 分钟线 provider 必须来自**不同上游通道**（腾讯 / 东财 / 新浪 / 本地 DB 各算一个）
- 契约：成功返回 List[MinuteKline]（可为空列表=该源无数据），
  失败返回 None 且写 self.last_error（失败与空结果语义分离，禁止静默空数组）
- 单位契约：volume 一律为**股**，amount 为**元**；provider 负责把上游的「手」×100 归一

返回三态（2026-09-11『空结果≠故障』契约对齐，manager._try_providers 按此处置）：

  List（非空）            → 成功：记成功、重置连续失败、返回该源数据
  []（空列表）            → **健康**：该源对此查询无数据 → manager 计入 empty_sources，
                            **不计故障、不计连续失败、不影响熔断**，继续尝试下一个源
  None + self.last_error  → **真故障**（异常 / HTTP 失败 / 结构异常 / 映射体检失败）
  [] + self.last_note     → 健康无数据 + 诊断说明（last_note 默认 ""）

为什么不把「无数据」写成 last_error（2026-09-11 P10 修复）：契约本就规定空列表=无数据，
实现却写成 last_error+None —— manager 按真故障计，累计 consecutive_failures 直至熔断，
把一个「这个查询它没有」升级成「这个源坏了」，该源被整体跳过。

为什么还要 last_note：把「无数据」从 last_error 挪走后，若不单独透出诊断，调用方只会
看到「返回空数据」——而「腾讯无 600150 的 m5 数据（代码不存在或该时段无交易）」
「DB 无该标的在窗口内的缓存」这类说明是排障的唯一线索。空结果不计故障，
但**原因必须可见**：manager 会把 last_note 拼进 provider_errors[name]。
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models.market_data import MinuteKline

# 周期别名 → 分钟数
_PERIOD_ALIASES = {
    '1': 1, '1m': 1, '1min': 1,
    '5': 5, '5m': 5, '5min': 5,
    '15': 15, '15m': 15, '15min': 15,
    '30': 30, '30m': 30, '30min': 30,
    '60': 60, '60m': 60, '60min': 60, '1h': 60,
}

# A股连续竞价时段分钟数（9:30-11:30 + 13:00-15:00 = 240 分钟）
_SESSION_MINUTES = 240


def period_minutes(period: str) -> int:
    """周期 → 分钟数（无法识别抛 ValueError，不静默兜底）"""
    key = str(period or '').strip().lower()
    if key not in _PERIOD_ALIASES:
        raise ValueError(f"不支持的分钟周期: {period!r}（支持 1m/5m/15m/30m/60m）")
    return _PERIOD_ALIASES[key]


def period_label(period: str) -> str:
    """周期 → 规范标签（'5' / '5m' / '5min' → '5m'）"""
    return f"{period_minutes(period)}m"


def bars_per_day(period: str) -> int:
    """单日该周期的最大K线根数（240 分钟连续竞价）"""
    return max(1, _SESSION_MINUTES // period_minutes(period))


def bars_needed(period: str, start_date: Optional[str], end_date: Optional[str],
                limit: int, max_bars: int) -> int:
    """估算「最近 N 根」型上游接口需要取多少根，才能覆盖 [start_date, end_date]

    上游（腾讯 mkline / 新浪 getKLineData）都只支持「最近 N 根」，没有日期参数，
    因此回溯根数 = 从今天回到 start_date（缺省取 end_date）的自然日跨度 × 单日根数
    × 1.6（周末/节假日冗余），上限由 provider 的 max_bars 决定（新浪 datalen
    上限实测 1023）。

    实测教训（2026-09-11）：按「end_date 距今天数」算会漏掉请求日自身——
    取 09-10 全天的 5m 线只回 28 根（11:15~15:00），因为窗口只回溯到 09-10 下午。
    必须以 start_date（更早的一端）为回溯基准。
    """
    limit = max(1, int(limit or 1))
    if not end_date:
        return min(max_bars, limit)

    from datetime import date as _date, datetime as _datetime
    try:
        end = _datetime.strptime(str(end_date)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return min(max_bars, limit)

    earliest = end
    if start_date:
        try:
            earliest = min(earliest, _datetime.strptime(str(start_date)[:10], '%Y-%m-%d').date())
        except (ValueError, TypeError):
            pass

    today = _date.today()
    span_days = max(1, (today - earliest).days + 1)
    return int(min(max_bars, max(limit, span_days * bars_per_day(period) * 1.6)))


def in_date_range(dt_str: str, start_date: Optional[str], end_date: Optional[str]) -> bool:
    """'YYYY-MM-DD HH:MM:SS' 是否落在 [start_date, end_date]（闭区间，日期粒度）"""
    d = str(dt_str)[:10]
    if start_date and d < str(start_date)[:10]:
        return False
    if end_date and d > str(end_date)[:10]:
        return False
    return True


def limit_klines(klines: List[MinuteKline], limit: int) -> List[MinuteKline]:
    """只保留最近 limit 根（上游按时间升序返回）"""
    if not limit or limit <= 0 or len(klines) <= limit:
        return klines
    return klines[-int(limit):]


def to_prefixed_code(symbol: str, separator: str = '') -> Optional[str]:
    """600519 → sh600519；300001 → sz300001；920023 → bj920023；399006 → sz399006

    无法映射（非 A 股代码段）返回 None —— 调用方必须显式失败，不得用错误前缀硬试。
    """
    bare = str(symbol or '').split('.')[0]
    if not bare.isdigit() or len(bare) != 6:
        return None
    # '39' 为深市指数代码段（399001 深成指、399006 创业板指）
    if bare.startswith(('60', '68', '11', '51', '39', '50', '58')):
        prefix = 'sh'
    elif bare.startswith(('00', '30', '12', '15', '16', '18')):
        prefix = 'sz'
    elif bare.startswith(('4', '8', '92')):
        prefix = 'bj'
    else:
        return None
    return f'{prefix}{separator}{bare}'


def ohlc_sanity(klines: List[MinuteKline]) -> Optional[str]:
    """OHLC 恒等式体检：high >= max(open, close) >= min(open, close) >= low

    为什么要有这一层（2026-09-11）：腾讯分钟线的字段序是
    [时间, 开, **收**, 高, 低, 量]，与直觉的「开高低收」不同——按直觉写映射
    不会报错、不会为 0，只会**静默产出错位的高低价**（正是分红 provider
    「读错列名 → 全 0 假结论」同一类事故）。本函数是字段映射的运行时闸门：
    超过 20% 的行违反恒等式即判该源映射有误，返回错误描述让 provider fail-loud。

    Returns:
        None = 通过；str = 错误描述
    """
    if not klines:
        return None
    bad = 0
    for k in klines:
        if not (k.high >= max(k.open, k.close) - 1e-6 and k.low <= min(k.open, k.close) + 1e-6):
            bad += 1
    if bad and bad / len(klines) > 0.2:
        return (f"OHLC 恒等式违反 {bad}/{len(klines)} 行"
                "（疑似字段错位：需核对上游列序）")
    return None


class MinuteKlineProvider(ABC):
    """分钟线 provider 抽象基类

    实现类必须：
    1. 提供唯一 name（注册进 DataProviderManager.minute_kline_providers）
    2. 把上游成交量归一为**股**、成交额归一为**元**
    3. 失败时返回 None 并写 self.last_error（不得返回空数组冒充失败）
    4. 「该源无此标的 / 该时段无数据 / 库内无缓存」返回**空列表**，并把诊断文本写进
       self.last_note（**不得**写成 last_error —— 那会让 manager 计真故障）

    实现类应把 last_error 与 last_note 都作为实例属性在 __init__ 里初始化为 None / ""，
    并在每次 get_minute_klines 入口重置两者（provider 通常是长生命周期单例，
    上一次调用的说明不得泄漏到这一次）。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称（唯一）"""
        pass

    @abstractmethod
    def get_minute_klines(
        self,
        symbol: str,
        period: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> Optional[List[MinuteKline]]:
        """见 domain.trading.ports.IMinuteKlineProvider.get_minute_klines"""
        pass
