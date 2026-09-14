"""EastmoneyMarketProvider —— 东方财富直连（market 域第二源）

2026-09-14（w-2129d492，REQ-48d896 t9）：为股东/基金/千股千评类数据增设东财直连源。

## 为什么需要它（第二个理由更重要）

1. **多源故障转移**：这 5 类数据此前只有 akshare 一个源 —— 第三方包一旦失效即无兜底；
2. **修上游解析缺陷**：akshare 对这几个接口用的是**位置式列名**（把 N 个名字按顺序硬套到
   东财返回的数组上），东财字段顺序一变就整体错位。实测 `stock_report_fund_hold`
   返回的表：「股票简称」列装的才是 6 位代码、「股票代码」列是 -4.2e10 的浮点、
   「持有基金家数」列是 '01'。**直连按字段名取值，从结构上不可能发生错位**。

## 覆盖范围（4 个方法）

| 方法 | 东财接口 |
|---|---|
| `get_top_holders` | `RPT_F10_EH_HOLDERS` / `RPT_F10_EH_FREEHOLDERS` |
| `get_holder_changes` | `RPT_HOLDERNUM_DET` |
| `get_top_fund_stocks` | `data.eastmoney.com/dataapi/zlsj/list` |
| `get_stock_comment` | `RPT_DMSK_TS_STOCKNEW` |

**不覆盖 `get_fund_holdings`**：东财对应的 `RPT_MAINDATA_MAIN_POSITIONDETAILS` 混装
银行/保险/券商等所有机构类型，且 `ORG_TYPE_NAME` 实测为 None，无法可靠筛出"基金"——
硬筛会改变契约语义（该方法约定「哪些基金持有该股」）。而 akshare 那条走的是**新浪**
（`vip.stock.finance.sina.com.cn`），上游本就独立，无兜底缺口。

## 契约：与 akshare 源返回**相同的键**

两个源可能轮流服务同一个请求，若键不同则端点的字段会随源漂移。
因此这里把东财英文字段**显式映射**为 akshare 源的中文键（见各方法内的 `_MAP` 注释），
映射不到列就**省略**该键（不编造）。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests

from adapters.outbound.datasources.base import BaseDataProvider
from adapters.outbound.datasources.models import MarketData
from adapters.outbound.datasources.providers.market._common import (
    is_transport_error,
    recent_report_periods,
    secucode,
)

logger = logging.getLogger(__name__)

_DC_URL = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
_ZLSJ_URL = 'http://data.eastmoney.com/dataapi/zlsj/list'
_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'),
    'Referer': 'https://data.eastmoney.com/',
}

# 主力数据的 org type（与东财页面一致）
_ZLSJ_TYPE = {
    'all': '1', 'fund': '1', '基金': '1', '基金持仓': '1',
    'qfii': '2', 'QFII持仓': '2',
    'social_security': '3', 'social': '3', '社保持仓': '3',
    'broker': '4', '券商持仓': '4',
    'insurance': '5', '保险持仓': '5',
    'trust': '6', '信托持仓': '6',
}
_ZLSJ_TYPE_NAME = {
    '1': '基金持仓', '2': 'QFII持仓', '3': '社保持仓',
    '4': '券商持仓', '5': '保险持仓', '6': '信托持仓',
}


_SCHEMA_DRIFT_MSG = (
    '上游返回了 %d 行但**无一字段可映射**（疑似字段改名/结构变更）——拒绝当作"无数据"静默处理'
)


def _strip_empty_records(records: list, synthesized: tuple = ()) -> list:
    """丢掉**上游字段全为 None** 的记录。

    为什么必须这么做：本 provider 是**显式字段映射**（东财英文字段 → 中文键）。
    一旦上游把字段改名（或换了返回结构），映射结果就是「结构存在、值全 None」的记录。
    照原样返回等于**用空值冒充数据**：调用方看到 total=10、每格却都是 None，
    而上游其实已经换了字段 —— 典型的静默 schema 漂移，正是本需求要消灭的东西。

    ⚠️ `synthesized` 必须排除**本地合成**的字段（如「序号」）：它们恒非 None，
    会让"全 None"判定永远为假、漂移检测失效（实测漏判：top_fund_stocks 因「序号」恒有值，
    字段改名后仍报 total=1）。
    """
    out = []
    for rec in records:
        if any(v is not None for k, v in rec.items() if k not in synthesized):
            out.append(rec)
    return out


def _iso(value) -> Optional[str]:
    """'2026-06-30 00:00:00' → '2026-06-30'；非字符串原样返回。"""
    if value is None:
        return None
    s = str(value)
    return s[:10] if len(s) >= 10 and s[4] == '-' else s


class EastmoneyMarketProvider(BaseDataProvider[MarketData]):
    """东方财富直连 provider（market 域）。

    ⚠️ 刻意**不继承 `MarketProvider`**：那个 ABC 强制实现 get_market_overview /
    get_lhb_stock / get_lhb_daily，而本源不提供这三类数据。若为满足 ABC 写"返回 None"
    的空实现，`_try_providers` 每次查行情/龙虎榜都会调用它并记一次失败 —— 反而污染健康分。
    继承 BaseDataProvider 并只实现本域方法，`_try_providers` 的 `hasattr` 检查会
    正确跳过本源（见 manager.py L339）。
    """

    def __init__(self):
        super().__init__()
        self.timeout = 10
        self.last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return 'eastmoney'

    # ---------- 内部工具 ----------

    def _get_json(self, url: str, params: Dict):
        r = requests.get(
            url, params=params, headers=_HEADERS, timeout=self.timeout,
            proxies={'http': None, 'https': None},
        )
        r.raise_for_status()
        return r.json()

    def _dc(self, report: str, filter_: str, extra: Optional[Dict] = None) -> List[Dict]:
        """datacenter-web 通用查询：失败抛异常，健康空返回 []。"""
        params = {
            'reportName': report,
            'columns': 'ALL',
            'pageSize': '200',
            'pageNumber': '1',
            'filter': filter_,
            'source': 'WEB',
            'client': 'WEB',
        }
        params.update(extra or {})
        js = self._get_json(_DC_URL, params)
        return ((js.get('result') or {}).get('data')) or []

    def _fail(self, exc: BaseException, what: str) -> None:
        """记录故障原因。

        `last_error` 是框架判定「真故障」的**主要**依据（provider 自报 last_error 才计故障
        且原因可见；否则 None 会被记成 _INVALID_RESULT_MARKER，**具体原因丢失**）。

        本方法仍坚持"不外抛"，但理由是**保原因**，不是"否则会穿透" ——
        2026-09-14（独立审查 L3 更正）：此前这里声称「_try_providers 只捕获超时，
        其它异常会穿透整个 failover 循环」**是错的**。manager.py:411 有兜底
        `except Exception`，会记录 provider_errors 并继续下一个源（审查实测：
        `_try_providers([Boom(), Good()], 'get_x')` → success=True, source=good）。
        外抛的代价是**丢失可读原因**（只剩「类名: msg」），不是崩溃。
        """
        self.last_error = '%s: %s' % (what, str(exc)[:180])
        logger.warning('%s.%s 失败: %s', self.name, what, exc)

    def _empty(self, data_type: str, payload: Dict) -> MarketData:
        payload = dict(payload)
        payload['empty'] = True
        return MarketData(
            data_type=data_type, data=payload,
            source=self.name, timestamp=datetime.now().isoformat(),
        )

    def _ok(self, data_type: str, payload: Dict) -> MarketData:
        return MarketData(
            data_type=data_type, data=payload,
            source=self.name, timestamp=datetime.now().isoformat(),
        )

    # ---------- 1. 十大股东 ----------

    def get_top_holders(self, symbol: str, holder_type: str = 'top10') -> Optional[MarketData]:
        """十大股东 / 十大流通股东。

        键映射（→ akshare 源同名键）：
          HOLDER_RANK→名次, HOLDER_NAME→股东名称, HOLD_NUM→持股数,
          HOLD_NUM_RATIO→占总股本持股比例（流通股东用 FREE_HOLDNUM_RATIO→占总流通股本持股比例）,
          HOLD_NUM_CHANGE→增减, CHANGE_RATIO→变动比率
        （东财该报表不含「股份类型/股东性质」→ 省略，不编造）
        """
        self.last_error = None
        try:
            code = secucode(symbol)
            if not code:
                self.last_error = '无法识别市场前缀: %s' % symbol
                return None
            want_free = str(holder_type or '').lower() in ('free', 'circulating', 'free_float')
            report = 'RPT_F10_EH_FREEHOLDERS' if want_free else 'RPT_F10_EH_HOLDERS'
            rows = self._dc(
                report, '(SECUCODE="%s")' % code,
                {'sortColumns': 'END_DATE,HOLDER_RANK', 'sortTypes': '-1,1'},
            )
            raw_count = len(rows)   # 报告期过滤会缩减 rows；漂移判定要用**上游原始行数**
            if not rows:
                return self._empty('top_holders', {
                    'symbol': symbol, 'holder_type': 'free' if want_free else 'top10',
                    'report_date': None, 'holders': [], 'total': 0,
                })
            latest = max(_iso(r.get('END_DATE')) or '' for r in rows)
            rows = [r for r in rows if _iso(r.get('END_DATE')) == latest]
            rows.sort(key=lambda r: (r.get('HOLDER_RANK') or 999))
            ratio_key = '占总流通股本持股比例' if want_free else '占总股本持股比例'
            ratio_field = 'FREE_HOLDNUM_RATIO' if want_free else 'HOLD_NUM_RATIO'
            holders = _strip_empty_records([{
                '名次': r.get('HOLDER_RANK'),
                '股东名称': r.get('HOLDER_NAME'),
                '持股数': r.get('HOLD_NUM'),
                ratio_key: r.get(ratio_field),
                '增减': r.get('HOLD_NUM_CHANGE'),
                '变动比率': r.get('CHANGE_RATIO'),
            } for r in rows])
            if not holders:
                # 行在、字段全对不上 → 上游 schema 漂移：报真故障（不静默成"无数据"）
                self.last_error = _SCHEMA_DRIFT_MSG % raw_count
                logger.error('%s.%s %s', self.name, 'get_top_holders', self.last_error)
                return None
            return self._ok('top_holders', {
                'symbol': symbol, 'holder_type': 'free' if want_free else 'top10',
                'report_date': latest or None, 'holders': holders, 'total': len(holders),
            })
        except Exception as e:  # noqa: BLE001
            self._fail(e, 'get_top_holders')
            return None

    # ---------- 2. 股东户数变化 ----------

    def get_holder_changes(self, symbol: str, periods: int = 4) -> Optional[MarketData]:
        """股东户数变化（RPT_HOLDERNUM_DET），最新在前。

        键映射：END_DATE→股东户数统计截止日, HOLDER_NUM→股东户数-本次, PRE_HOLDER_NUM→上次,
        HOLDER_NUM_CHANGE→增减, HOLDER_NUM_RATIO→增减比例, AVG_MARKET_CAP→户均持股市值,
        AVG_HOLD_NUM→户均持股数量, TOTAL_MARKET_CAP→总市值, TOTAL_A_SHARES→总股本,
        CHANGE_SHARES→股本变动, CHANGE_REASON→股本变动原因, HOLD_NOTICE_DATE→股东户数公告日期
        """
        self.last_error = None
        try:
            code = secucode(symbol)
            if not code:
                self.last_error = '无法识别市场前缀: %s' % symbol
                return None
            rows = self._dc(
                'RPT_HOLDERNUM_DET', '(SECUCODE="%s")' % code,
                {'sortColumns': 'END_DATE', 'sortTypes': '-1'},
            )
            raw_count = len(rows)
            if not rows:
                return self._empty('holder_changes', {
                    'symbol': symbol, 'periods': [], 'total': 0,
                })
            n = max(1, int(periods or 4))
            rows = rows[:n]
            records = [{
                '股东户数统计截止日': _iso(r.get('END_DATE')),
                '区间涨跌幅': r.get('INTERVAL_CHRATE'),
                '股东户数-本次': r.get('HOLDER_NUM'),
                '股东户数-上次': r.get('PRE_HOLDER_NUM'),
                '股东户数-增减': r.get('HOLDER_NUM_CHANGE'),
                '股东户数-增减比例': r.get('HOLDER_NUM_RATIO'),
                '户均持股市值': r.get('AVG_MARKET_CAP'),
                '户均持股数量': r.get('AVG_HOLD_NUM'),
                '总市值': r.get('TOTAL_MARKET_CAP'),
                '总股本': r.get('TOTAL_A_SHARES'),
                '股本变动': r.get('CHANGE_SHARES'),
                '股本变动原因': r.get('CHANGE_REASON'),
                '股东户数公告日期': _iso(r.get('HOLD_NOTICE_DATE')),
                '代码': r.get('SECURITY_CODE'),
                '名称': r.get('SECURITY_NAME_ABBR'),
            } for r in rows]
            records = _strip_empty_records(records)
            if not records:
                self.last_error = _SCHEMA_DRIFT_MSG % raw_count
                logger.error('%s.%s %s', self.name, 'get_holder_changes', self.last_error)
                return None
            return self._ok('holder_changes', {
                'symbol': symbol, 'periods': records, 'total': len(records),
            })
        except Exception as e:  # noqa: BLE001
            self._fail(e, 'get_holder_changes')
            return None

    # ---------- 3. 机构重仓股排行 ----------

    def get_top_fund_stocks(self, fund_type: str = 'all', limit: int = 50) -> Optional[MarketData]:
        """机构重仓股排行（主力数据 zlsj/list）。

        这是本 provider 存在的**主要理由**：akshare 的同一接口因位置式列名而错位
        （把 SECURITY_CODE 塞进「股票简称」列、把 HOLDCHA_VALUE 塞进「股票代码」列）。
        这里按字段名映射，输出**语义正确**的数据：
          SECURITY_CODE→股票代码, SECURITY_NAME_ABBR→股票简称, HOULD_NUM→持有基金家数,
          TOTAL_SHARES→持股总数, HOLD_VALUE→持股市值,
          HOLDCHA→持股变化（增仓/减仓）, HOLDCHA_NUM→持股变动数值, HOLDCHA_RATIO→持股变动比例
        """
        self.last_error = None
        try:
            key = str(fund_type or 'all')
            # 2026-09-14（独立审查 L6 修复）：未知 fund_type 此前**静默降级**为基金持仓，
            # 调用方以为查的是 QFII/社保却拿到基金数据。现改为显式失败。
            # 另注：「all」在本数据源里等价于「基金持仓」（东财该页签默认口径），
            # 不是"全部机构"——已在路由 docstring 与响应 fundType 字段中写明。
            type_id = _ZLSJ_TYPE.get(key) or _ZLSJ_TYPE.get(key.lower())
            if type_id is None:
                self.last_error = (
                    'get_top_fund_stocks 未知 fund_type=%r（可选：%s）'
                    % (fund_type, '、'.join(sorted(set(_ZLSJ_TYPE_NAME.values()))))
                )
                logger.warning('%s.%s %s', self.name, 'get_top_fund_stocks', self.last_error)
                return None
            type_name = _ZLSJ_TYPE_NAME[type_id]

            rows, used_period = [], None
            last_exc = None
            for period in recent_report_periods(4):
                date_str = '%s-%s-%s' % (period[:4], period[4:6], period[6:])
                try:
                    js = self._get_json(_ZLSJ_URL, {
                        'date': date_str, 'type': type_id, 'zjc': '0',
                        'sortField': 'HOULD_NUM', 'sortDirec': '1',
                        'pageNum': '1', 'pageSize': '500', 'p': '1', 'pageNo': '1',
                    })
                except Exception as e:  # noqa: BLE001
                    if is_transport_error(e):
                        raise
                    last_exc = e
                    continue
                data = js.get('data') or []
                if data:
                    rows, used_period = data, date_str
                    break
            if last_exc is not None and not rows:
                self._fail(last_exc, 'get_top_fund_stocks')
                return None
            if not rows:
                return self._empty('top_fund_stocks', {
                    'fund_type': type_name, 'report_date': None, 'stocks': [], 'total': 0,
                })

            raw_count = len(rows)
            n = max(1, int(limit or 50))
            records = [{
                '序号': i + 1,
                '股票代码': r.get('SECURITY_CODE'),
                '股票简称': r.get('SECURITY_NAME_ABBR'),
                '持有基金家数': r.get('HOULD_NUM'),
                '持股总数': r.get('TOTAL_SHARES'),
                '持股市值': r.get('HOLD_VALUE'),
                '持股变化': r.get('HOLDCHA'),
                '持股变动数值': r.get('HOLDCHA_NUM'),
                '持股变动比例': r.get('HOLDCHA_RATIO'),
            } for i, r in enumerate(rows[:n])]
            # 「序号」是本地合成的，不能计入"上游是否有内容"的判定
            records = _strip_empty_records(records, synthesized=('序号',))
            if not records:
                self.last_error = _SCHEMA_DRIFT_MSG % raw_count
                logger.error('%s.%s %s', self.name, 'get_top_fund_stocks', self.last_error)
                return None
            return self._ok('top_fund_stocks', {
                'fund_type': type_name, 'report_date': used_period,
                'stocks': records, 'total': len(records),
            })
        except Exception as e:  # noqa: BLE001
            self._fail(e, 'get_top_fund_stocks')
            return None

    # ---------- 4. 千股千评 ----------

    def get_stock_comment(self, symbol: str) -> Optional[MarketData]:
        """个股千股千评（RPT_DMSK_TS_STOCKNEW，按代码过滤，单行）。

        键映射：SECURITY_CODE→代码, SECURITY_NAME_ABBR→名称, CLOSE_PRICE→最新价,
        CHANGE_RATE→涨跌幅, TURNOVERRATE→换手率, PE_DYNAMIC→市盈率, PRIME_COST→主力成本,
        ORG_PARTICIPATE→机构参与度, TOTALSCORE→综合得分, RANK_UP→上升, RANK→目前排名,
        FOCUS→关注指数, TRADE_DATE→交易日
        （akshare 的 stock_comment_em 同样是位置式列名：30 个名字硬套 —— 这里按字段名取）
        """
        self.last_error = None
        try:
            bare = str(symbol or '').split('.')[0]
            if not (len(bare) == 6 and bare.isdigit()):
                self.last_error = '非法股票代码: %s' % symbol
                return None
            rows = self._dc('RPT_DMSK_TS_STOCKNEW', '(SECURITY_CODE="%s")' % bare)
            if not rows:
                return self._empty('stock_comment', {
                    'symbol': symbol, 'comment': None, 'empty': True,
                })
            r = rows[0]
            comment = {
                '代码': r.get('SECURITY_CODE'),
                '名称': r.get('SECURITY_NAME_ABBR'),
                '最新价': r.get('CLOSE_PRICE'),
                '涨跌幅': r.get('CHANGE_RATE'),
                '换手率': r.get('TURNOVERRATE'),
                '市盈率': r.get('PE_DYNAMIC'),
                '主力成本': r.get('PRIME_COST'),
                '机构参与度': r.get('ORG_PARTICIPATE'),
                '综合得分': r.get('TOTALSCORE'),
                '上升': r.get('RANK_UP'),
                '目前排名': r.get('RANK'),
                '关注指数': r.get('FOCUS'),
                '交易日': _iso(r.get('TRADE_DATE')),
            }
            if not any(v is not None for v in comment.values()):
                self.last_error = _SCHEMA_DRIFT_MSG % len(rows)  # 单行查询，rows 即原始行
                logger.error('%s.%s %s', self.name, 'get_stock_comment', self.last_error)
                return None
            return self._ok('stock_comment', {
                'symbol': symbol, 'comment': comment, 'empty': False,
            })
        except Exception as e:  # noqa: BLE001
            self._fail(e, 'get_stock_comment')
            return None
