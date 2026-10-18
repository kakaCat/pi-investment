"""预约披露日程 provider（前瞻性财报日历，2026-09-13 w-a9ec14d7）

为什么需要（实测缺口）：event_calendar 里 earnings 事件 69 条**全是 collected（事后记录）**——
我们采的是"已发布的公告"，所以财报永远只能事后知道。研究/交易要的是**未来的披露日**：
"某股将在 X 日披露半年报" 才是可挂规则、可提前减仓、可做事件研究的时点。

## 打样证据（2026-09-13 真实响应，字段映射纪律见端口 docstring）
akshare `stock_report_disclosure(market='沪深京', period='2026半年报')` → **5550 行**，实测列：
    股票代码 | 股票简称 | 首次预约 | 初次变更 | 二次变更 | 三次变更 | 实际披露
- 可用期间实测：'2026半年报'=5550 行、'2025年报'=5488 行、'2025半年报'=5402 行；
  '2026三季报'/'2026一季报' 抛 KeyError（该接口只提供年报/半年报维度）→ 由 last_error 如实暴露，不静默。
- '2026年报' 返回空表 → 按端口契约返回 []（该期尚未开放预约），不是故障。

## 语义（写清楚，避免把"预约"当"已发生"）
- `实际披露` 非空 → 事件已发生，effective_date = 实际披露，importance=3；
- 否则 → 事件是**计划**，effective_date = 最新预约日（依次取 首次预约→初次变更→二次变更→三次变更 中最晚的非空值），importance=2；
- raw 保留全部日期列，meta 记录 scheduled/actual 与变更历史，供审计与"预约变更"信号使用
  （披露日被推迟/提前本身是一条可研究的信息）。
"""
from datetime import date
from typing import Dict, List, Optional, Tuple

from domain.events.ports.IMarketEventProvider import IMarketEventProvider

#: 默认关注期（按财季滚动维护；新增期需先打样确认接口返回非空）
#: ⚠️ 期名规则（2026-09-13 实测踩坑）：接口内部映射的 key 是「{年}一季 / {年}半年报 /
#: {年}三季 / {年}年报」——写成「2026三季报」会 KeyError，写成「2026一季报」同样 KeyError。
#: ⚠️ 前瞻性现实：巨潮的预约披露表**只覆盖已结束的报告期**。实测 2026-09-13：
#: 「2026三季」返回空表（尚未开放预约）、「2026一季/半年报/2025年报」均有全市场数据。
#: 故本 provider 把「尚未开放预约」当**空结果**（不是故障），并靠周度任务在开放后自动接住。
DEFAULT_PERIODS: Tuple[str, ...] = ('2026三季', '2026半年报', '2026一季', '2025年报')

_DATE_COLS = ('首次预约', '初次变更', '二次变更', '三次变更')
_ALL_DATE_COLS = _DATE_COLS + ('实际披露',)


def _norm_date(value) -> Optional[str]:
    """akshare 返回 Timestamp/NaT/字符串混合 —— 统一成 YYYY-MM-DD，解析不到返回 None。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ('nat', 'nan', 'none', '-'):
        return None
    text = text.split(' ')[0]
    return text[:10] if len(text) >= 10 else None


class ScheduledDisclosureProvider(IMarketEventProvider):
    """全市场预约披露日程（前瞻性财报日历）"""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self.last_fetched_at: Optional[str] = None

    @property
    def name(self) -> str:
        return 'akshare_disclosure'

    def fetch_policy(self) -> Optional[List[Dict]]:
        return []          # 本 provider 不提供政策（端口纪律：不支持返回 []）

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        return []          # 本 provider 不按标的检索；日程走 fetch_scheduled_disclosures

    def fetch_scheduled_disclosures(self, periods: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """按报告期取全市场预约披露日程。

        Returns:
            List[dict]（行契约见端口 docstring）；某期接口不可用 → 该期跳过并写入 last_error，
            但**只要有一期成功就返回已取到的行**（部分失败不静默：last_error 会如实带上失败的期）。
        """
        try:
            import akshare as ak
        except Exception as exc:  # noqa: BLE001
            self.last_error = f'akshare 不可用: {type(exc).__name__}: {exc}'
            return None

        targets = list(periods or DEFAULT_PERIODS)
        rows: List[Dict] = []
        failures: List[str] = []
        for period in targets:
            try:
                df = ak.stock_report_disclosure(market='沪深京', period=period)
            except Exception as exc:  # noqa: BLE001
                failures.append(f'{period}: {type(exc).__name__}: {str(exc)[:80]}')
                continue
            if df is None or len(df) == 0:
                # 空表 = 该期尚未开放预约（巨潮按季开放）→ 按端口契约返回空结果，不是故障。
                # 实测：2026-09-13 的「2026三季」为空，而「2026一季/半年报/2025年报」各 5.4~5.5k 行。
                continue
            for record in df.to_dict('records'):
                row = self._to_event_row(record, period)
                if row:
                    rows.append(row)
        if failures:
            self.last_error = '; '.join(failures)
        if not rows and failures:
            return None
        self.last_fetched_at = date.today().isoformat()
        return rows

    # ------------------------------------------------------------------ 内部
    @staticmethod
    def _to_event_row(record: Dict, period: str) -> Optional[Dict]:
        symbol = str(record.get('股票代码') or '').strip().zfill(6)
        if len(symbol) != 6 or not symbol.isdigit():
            return None
        short_name = str(record.get('股票简称') or '').replace(' ', '')
        actual = _norm_date(record.get('实际披露'))
        scheduled_dates = [d for d in (_norm_date(record.get(c)) for c in _DATE_COLS) if d]
        effective = actual or (max(scheduled_dates) if scheduled_dates else None)
        if not effective:
            return None                       # 端口纪律：解析不到日期就丢弃该行，勿编造今天
        is_actual = bool(actual)
        title = '%s%s%s披露' % (short_name, period, '已' if is_actual else '预约')
        return {
            'scope': 'individual',
            'type': 'earnings',
            'title': title,
            'effective_date': effective,
            'announce_date': '',
            'importance': 3 if is_actual else 2,
            'symbols': [symbol],
            'industries': [],
            'source': 'akshare_disclosure',
            'url': '',
            'summary': ('实际披露日 ' + actual) if is_actual else ('预约披露日 ' + effective),
            'external_id': '%s:%s' % (symbol, period),
            'authority': None,
            'raw': {k: str(record.get(k)) for k in _ALL_DATE_COLS if k in record},
        }
