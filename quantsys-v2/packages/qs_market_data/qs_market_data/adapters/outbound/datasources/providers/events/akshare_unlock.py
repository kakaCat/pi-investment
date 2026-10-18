"""解禁排队 provider（RFC 015 §3.3 优先级 3：**结构化**解禁事件，akshare 通道）

## 真实响应打样（2026-09-11 本机实测，非文档/mock）

通道 A（按标的，akshare `stock_restricted_release_queue_em(symbol="600150")`）实测：
    列 = ['序号','解禁时间','解禁股东数','解禁数量','实际解禁数量','未解禁数量','实际解禁数量市值',
          '占总市值比例','占流通市值比例','解禁前一交易日收盘价','限售股类型',
          '解禁前20日涨跌幅','解禁后20日涨跌幅']   共 5 行
    行样本 = {'序号':1, '解禁时间': datetime.date(2025, 9, 16), '解禁股东数':1,
              '解禁数量': 3053192530.0000005, '实际解禁数量市值': 113090251311.2,
              '占总市值比例': 0.405706374684, '占流通市值比例': 0.405706374684,
              '限售股类型': '定向增发机构配售股份',
              '解禁前一交易日收盘价': 37.04,
              '解禁前20日涨跌幅': 0.02597403, '解禁后20日涨跌幅': -5.76473643}

通道 B（全市场窗口，akshare `stock_restricted_release_detail_em(start_date='20260901', end_date='20261031')`）实测：
    列 = ['序号','股票代码','股票简称','解禁时间','限售股类型','解禁数量','实际解禁数量',
          '实际解禁市值','占解禁前流通市值比例','解禁前一交易日收盘价','解禁前20日涨跌幅',
          '解禁后20日涨跌幅']   共 37 行（2026-09-02 ~ 2026-10-30）
    行样本 = {'股票代码':'603028','股票简称':'赛福天','解禁时间':'2026-09-02',
              '限售股类型':'股权激励限售股份','实际解禁市值': 9067800.0,
              '占解禁前流通市值比例': 0.004449, '解禁前一交易日收盘价': 7.14}

⚠️ 单位/口径陷阱（实测）：
- 占比列已是**小数**（0.405706 = 40.57%），不是百分数。本 provider 原样透传给 raw，
  领域层 infer_importance 按小数口径判"<1% 影响有限"。
- 通道 A 的 `解禁时间` 是 `datetime.date`，通道 B 是 `str`，统一 str()[:10]。
- 通道 A 返回该标的**全部历史**解禁（600150 最新一条是 2025-09-16，属过去）→
  必须按窗口过滤，否则会把 2023 年的解禁当"即将解禁"报出来（严重的过期事件告警）。
- akshare 的封装源码里已含列名映射，本 provider 按**实测列名**读取；读不到列名直接抛
  （2026-09-11 分红 provider 全 0 事故的教训：宁失败，不静默返回全 0）。

## 独立通道声明（§1.5.2 硬约束 1）
akshare 的解禁通道上游是**东财数据中心**（不是公告流 np-anotice-stock），
与 eastmoney_notice / cninfo_disclosure 是不同数据集、不同端点、不同字段；
它提供公告流给不出的**结构化解禁规模与占比**（决策真正需要的量），故单列一个 provider。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from domain.events.model import AUTHORITY_AKSHARE
from domain.events.ports.IMarketEventProvider import IMarketEventProvider

logger = logging.getLogger(__name__)

# 采集窗口：往前 30 天（复盘用）+ 往后 180 天（解禁是提前已知的事件，远期也要能预警）
_BACK_DAYS = 30
_FORWARD_DAYS = 180
_MAX_SYMBOLS = 20
#: 逐只查排队明细的标的数上限（超过则只走全市场窗口，避免 N 次上游请求拖慢 ingest）
_DIRECT_QUEUE_MAX_SYMBOLS = 10
#: 全市场模式（symbols=None）的前向窗口：90 天（实测 180 天会把行数从 441 翻到 948，噪声 > 价值）
_MARKET_FORWARD_DAYS = 90
_QUEUE_COLUMNS = ('解禁时间', '解禁股东数', '解禁数量', '实际解禁数量市值',
                  '占总市值比例', '占流通市值比例', '限售股类型', '解禁前一交易日收盘价')
_DETAIL_COLUMNS = ('股票代码', '股票简称', '解禁时间', '限售股类型', '解禁数量',
                   '实际解禁数量', '实际解禁市值', '占解禁前流通市值比例', '解禁前一交易日收盘价')


def _as_date(value) -> str:
    """datetime.date / '2026-09-02' / '2026-09-02 00:00:00' → 'YYYY-MM-DD'（解析不到返回 ''）"""
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    text = str(value).strip()[:10]
    try:
        datetime.strptime(text, '%Y-%m-%d')
        return text
    except ValueError:
        return ''


def _require_columns(df, columns, source_label: str) -> None:
    """列名契约校验：缺列直接抛（禁止静默按错列名读出全 0）"""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise RuntimeError(
            f'{source_label} 列名契约不匹配，缺少 {missing}；实际列={list(df.columns)}'
            '（上游改版？禁止按猜测列名继续，避免重演"读错列名→全 0→被当成无数据"）'
        )


class AkshareUnlockProvider(IMarketEventProvider):
    """解禁排队（个股事件通道 3；权威度 50：结构化二次加工）"""

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self.last_fetched_at: Optional[str] = None

    @property
    def name(self) -> str:
        return 'akshare_unlock'

    # ------------------------------------------------------------------ 政策

    def fetch_policy(self) -> Optional[List[Dict]]:
        """解禁通道不提供政策 → []（空结果 ≠ 故障）"""
        return []

    # -------------------------------------------------------------- 个股事件

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """解禁事件（窗口内解禁一次取全市场表 + 按目标过滤 + 小范围补历史明细）

        为什么默认走全市场窗口而不是逐只查（2026-09-11 实测）：
        逐只 stock_restricted_release_queue_em 每次一个上游请求，默认采集池 24 只就要 24 次，
        而"窗口内解禁"本身是一张全市场表——一次 detail 请求即可覆盖所有标的，
        逐只查既慢又只得到同一数据集的一个子集。

        两步策略（实测数据支撑，2026-09-11）：
        - 给了 symbols：全市场表拉到后**按标的过滤**。实测 180 天全市场窗口有 948 行，
          落在默认采集池（持仓∪盯盘）的只有 3 行——不过滤就等于每天往库里灌近千条
          与持仓无关的事件。另对 ≤_DIRECT_QUEUE_MAX_SYMBOLS 只的小范围，补逐只排队明细
          （含窗口外的历史解禁，供排雷看"最近刚解禁过"）。
        - symbols=None（显式全市场模式）：返回窗口内全市场解禁，前向窗口收到
          _MARKET_FORWARD_DAYS=90 天（实测 90 天 441 行 vs 180 天 948 行，3 个月内够用）。
        """
        self.last_error = None
        targets = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        try:
            import akshare as ak
            today = date.today()
            low = today - timedelta(days=_BACK_DAYS)
            high = today + timedelta(days=_FORWARD_DAYS)
            rows: List[Dict] = []

            # ① 窗口内解禁（一次上游请求拿到全市场表）
            market_high = high if targets else today + timedelta(days=_MARKET_FORWARD_DAYS)
            df = ak.stock_restricted_release_detail_em(
                start_date=low.strftime('%Y%m%d'), end_date=market_high.strftime('%Y%m%d'))
            _require_columns(df, _DETAIL_COLUMNS, 'stock_restricted_release_detail_em')
            target_set = set(targets)
            for record in df.to_dict('records'):
                if target_set and str(record.get('股票代码') or '').strip() not in target_set:
                    continue          # 只保留目标标的（否则一天近千条与持仓无关的事件）
                row = self._map_detail(record, low, market_high)
                if row:
                    rows.append(row)

            # ② 小范围时补充逐只排队明细（含窗口外的历史解禁）
            if targets and len(targets) <= _DIRECT_QUEUE_MAX_SYMBOLS:
                for symbol in targets[:min(len(targets), _MAX_SYMBOLS)]:
                    df = ak.stock_restricted_release_queue_em(symbol=symbol)
                    _require_columns(df, _QUEUE_COLUMNS, 'stock_restricted_release_queue_em')
                    for record in df.to_dict('records'):
                        row = self._map_queue(record, symbol, low, high)
                        if row:
                            rows.append(row)
            self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
            return rows
        except Exception as exc:  # noqa: BLE001 —— fail-loud
            self.last_error = f'{type(exc).__name__}: {exc}'
            logger.warning('akshare_unlock fetch failed: %s', self.last_error)
            return None

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _in_window(effective: str, low: date, high: date) -> bool:
        try:
            day = datetime.strptime(effective, '%Y-%m-%d').date()
        except ValueError:
            return False
        return low <= day <= high

    def _map_queue(self, record: Dict, symbol: str, low: date, high: date) -> Optional[Dict]:
        effective = _as_date(record.get('解禁时间'))
        if not effective or not self._in_window(effective, low, high):
            return None
        ratio = record.get('占流通市值比例')
        shares = record.get('解禁数量')
        value = record.get('实际解禁数量市值')
        kind = str(record.get('限售股类型') or '')
        # 标题口径与 _map_detail 保持一致（只用 "占流通市值 X%" 一种写法）：
        # 两条子通道对同一解禁会给同一标的各出一条，口径不统一会让领域层判成"两个事件"
        # 并落两条近似重复行（实测）。
        pct = f'（占流通市值 {float(ratio) * 100:.2f}%）' if isinstance(ratio, (int, float)) else ''
        return {
            'scope': 'individual',
            'type': 'unlock',
            'title': f'{symbol} 限售股解禁：{kind or "限售股"}{pct}',
            'effective_date': effective,
            'announce_date': '',
            'importance': None,
            'symbols': [symbol],
            'industries': [],
            'source': self.name,
            'url': f'https://data.eastmoney.com/dxf/q/{symbol}.html',
            'summary': f'解禁股东数={record.get("解禁股东数")}；解禁数量={shares}；解禁市值={value}',
            'external_id': f'unlock-{symbol}-{effective}',
            'authority': AUTHORITY_AKSHARE,
            'raw': {k: record.get(k) for k in _QUEUE_COLUMNS} | {'ratio': ratio},
        }

    def _map_detail(self, record: Dict, low: date, high: date) -> Optional[Dict]:
        symbol = str(record.get('股票代码') or '').strip()
        effective = _as_date(record.get('解禁时间'))
        if not symbol or not effective or not self._in_window(effective, low, high):
            return None
        ratio = record.get('占解禁前流通市值比例')
        name = str(record.get('股票简称') or '')
        kind = str(record.get('限售股类型') or '')
        return {
            'scope': 'individual',
            'type': 'unlock',
            'title': f'{name or symbol} 限售股解禁：{kind or "限售股"}'
                     + (f'（占流通市值 {float(ratio) * 100:.2f}%）'
                        if isinstance(ratio, (int, float)) else ''),
            'effective_date': effective,
            'announce_date': '',
            'importance': None,
            'symbols': [symbol],
            'industries': [],
            'source': self.name,
            'url': f'https://data.eastmoney.com/dxf/q/{symbol}.html',
            'summary': f'解禁数量={record.get("解禁数量")}；解禁市值={record.get("实际解禁市值")}'
                       f'（口径：占解禁前流通市值；upstream 字段名 占解禁前流通市值比例）',
            'external_id': f'unlock-{symbol}-{effective}',
            'authority': AUTHORITY_AKSHARE,
            'raw': {k: record.get(k) for k in _DETAIL_COLUMNS} | {'ratio': ratio, 'name': name},
        }
