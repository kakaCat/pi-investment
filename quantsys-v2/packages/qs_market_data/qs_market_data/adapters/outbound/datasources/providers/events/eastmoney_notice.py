"""东财公告 provider（RFC 015 §3.3 优先级 1：个股事件通道）

## 真实响应打样（2026-09-11 本机实测，非文档/mock）

接口：`GET https://np-anotice-stock.eastmoney.com/api/security/ann`
参数：`sr=-1&page_size=20&page_index=1&ann_type=A&client_source=web&stock_list=600150&f_node=0&s_node=0`
（**不传 stock_list 即为全市场公告流**，实测每页返回沪深京全部当日公告）

实测响应（2026-09-11 19:36，HTTP 200，直连**不用代理**——本机系统代理 127.0.0.1:7897
对东财 np-anotice 可用但无必要；provider 统一 trust_env=False 走直连）：

    {"data": {"list": [
        {"art_code": "AN202609111829239408",
         "codes": [{"ann_type": "A,SHA", "inner_code": "43302177340683",
                    "market_code": "1", "short_name": "中国船舶", "stock_code": "600150"}],
         "columns": [{"column_code": "001002006016", "column_name": "重大事故损失"}],
         "display_time": "2026-09-11 00:29:07:363",     # 注意：末尾是 :363 毫秒，不是 .363
         "eiTime": "2026-09-11 00:30:08:000",
         "notice_date": "2026-09-11 00:00:00",
         "sort_date": "2026-09-11 12:00:00",
         "title": "中国船舶:关于北海造船厂一货轮火灾事故有关情况的公告",
         "title_ch": "...", "title_en": ""},
        ...]}, "success": true, ...}

字段映射结论（逐列核对，非猜测）：
- `art_code`      → external_id（东财公告唯一 ID，用于拼详情页 URL）
- `codes[0].stock_code` → symbols；`codes[0].short_name` → 名称（落 raw，供审计）
- `columns[0].column_name` → 东财自己的**栏目分类**（如"重大事故损失"/"增发提示性公告"/"诉讼仲裁"）
  ——本 provider 只把它放进 raw，**不直接当事件类型**：栏目粒度是"公告栏目"不是"事件性质"，
  映射会错（例："重大事故损失"栏目下既有事故也有保险理赔）。类型统一交给领域层关键词推断。
- `notice_date`    → effective_date（东财的"公告日"，实测与标题同日）
- `display_time`   → announce_date（精确到毫秒的入库时间；两者不同时才分开记）
- `title`          → title（保留原文，公司名前缀的归一化在领域层做）

⚠️ 单位/格式陷阱（实测）：
- `display_time` 的毫秒用冒号分隔（"19:36:56:580"），`datetime.strptime('%H:%M:%S')` **会失败**；
  本 provider 只取前 10 位日期，不做毫秒解析（事件排序只需要到天）。
- 详情页 URL 形如 `https://data.eastmoney.com/notices/detail/{stock_code}/{art_code}.html`
  （stock_code 为 6 位、无市场前缀）。

## 独立通道声明（§1.5.2 硬约束 1）
本 provider 打的是 **np-anotice-stock**（公告流）。
东财还有 datacenter-web 的 `RPT_PUBLIC_BS_APPOIN`（财报**预约披露日**，实测可用，返回
`SECURITY_CODE/REPORT_TYPE_NAME/APPOINT_PUBLISH_DATE/ACTUAL_PUBLISH_DATE`）——
它与本通道同属东财一家（**不算独立通道**），故未另立 provider；
如需"未来财报日"能力，应由本 provider 增加一个端点分支并在 docstring 注明同源。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests

from domain.events.model import AUTHORITY_EASTMONEY
from domain.events.ports.IMarketEventProvider import IMarketEventProvider

logger = logging.getLogger(__name__)

_URL = 'https://np-anotice-stock.eastmoney.com/api/security/ann'
_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
# 每只标的的公告条数上限（排雷够用，避免无界翻页）
_PAGE_SIZE = 20
# 单次调用的标的数上限（防止一次 ingest 打上百次上游触发 WAF/熔断）
_MAX_SYMBOLS = 30
# symbols=None 时的全市场流条数（大盘公告流的采样，不是全量）
_MARKET_PAGE_SIZE = 50

_SESSION: Optional[requests.Session] = None


def _session() -> requests.Session:
    """进程级共享 Session（连接池复用，实测能显著降低上游拒连率）

    trust_env=False：绕开本机系统代理（与 industry_chain/minure_kline provider 同口径）。
    """
    global _SESSION
    if _SESSION is None:
        session = requests.Session()
        session.trust_env = False
        adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        _SESSION = session
    return _SESSION


def _date_only(value) -> str:
    """'2026-09-11 00:00:00' / '2026-09-11 19:36:56:580' → '2026-09-11'（解析不到返回 ''）"""
    text = str(value or '').strip()
    if len(text) < 10:
        return ''
    head = text[:10]
    try:
        datetime.strptime(head, '%Y-%m-%d')
        return head
    except ValueError:
        return ''


class EastmoneyNoticeProvider(IMarketEventProvider):
    """东财公告流（个股事件通道 1；权威度 60：聚合转载，非原始披露）"""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self.last_fetched_at: Optional[str] = None
        # 截断标注（静默失败清单 §2：取前 N 条必须标注）：标的数超 _MAX_SYMBOLS 时，
        # 未被采集的代码写进这里，调用方（EventFeedService / 入站响应）负责如实透出。
        self.truncated_symbols: List[str] = []
        self.truncation_note: str = ''

    @property
    def name(self) -> str:
        return 'eastmoney_notice'

    # ------------------------------------------------------------------ 政策

    def fetch_policy(self) -> Optional[List[Dict]]:
        """东财公告流不提供政策文件 → 返回 []（不是 None：空结果 ≠ 故障）"""
        return []

    # -------------------------------------------------------------- 个股事件

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """个股公告（按标的查询；symbols=None 时取全市场当日公告流采样）

        失败 → 返回 None 且写 self.last_error（真异常必须显式，禁止静默空）。
        """
        self.last_error = None
        self.truncated_symbols = []
        self.truncation_note = ''
        targets = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        try:
            if not targets:
                return self._fetch_market()
            queried = targets[:_MAX_SYMBOLS]
            if len(targets) > _MAX_SYMBOLS:
                # 不静默截断：把"哪些标的这次没被采集"如实标注出来（含日志告警）
                self.truncated_symbols = targets[_MAX_SYMBOLS:]
                self.truncation_note = (
                    '%s: 请求标的 %d 只，超过单次上限 %d 只，本次仅采集前 %d 只；'
                    '未采集 %d 只（%s）'
                    % (self.name, len(targets), _MAX_SYMBOLS, _MAX_SYMBOLS,
                       len(self.truncated_symbols),
                       ','.join(self.truncated_symbols[:10])
                       + ('…' if len(self.truncated_symbols) > 10 else ''))
                )
                logger.warning(self.truncation_note)
            rows: List[Dict] = []
            for symbol in queried:
                rows.extend(self._fetch_one(symbol))
            self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
            return rows
        except Exception as exc:  # noqa: BLE001 —— fail-loud：写 last_error 让 manager 记为故障
            self.last_error = f'{type(exc).__name__}: {exc}'
            logger.warning('eastmoney_notice fetch failed: %s', self.last_error)
            return None

    # ------------------------------------------------------------------ 内部

    def _params(self, page_size: int) -> Dict:
        return {
            'sr': -1, 'page_size': page_size, 'page_index': 1, 'ann_type': 'A',
            'client_source': 'web', 'f_node': 0, 's_node': 0,
        }

    def _request(self, params: Dict) -> List[Dict]:
        resp = _session().get(_URL, params=params, headers={'User-Agent': _UA}, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f'HTTP {resp.status_code} from np-anotice-stock')
        payload = resp.json()
        data = payload.get('data') if isinstance(payload, dict) else None
        items = (data or {}).get('list')
        if items is None:
            raise RuntimeError('响应结构异常：data.list 缺失（上游可能改版或被 WAF 拦截）')
        return items

    def _fetch_one(self, symbol: str) -> List[Dict]:
        params = self._params(_PAGE_SIZE)
        params['stock_list'] = symbol
        items = self._request(params)
        out = []
        for item in items:
            row = self._map(item)
            if row:
                out.append(row)
        return out

    def _fetch_market(self) -> List[Dict]:
        items = self._request(self._params(_MARKET_PAGE_SIZE))
        out = []
        for item in items:
            row = self._map(item)
            if row:
                out.append(row)
        return out

    def _map(self, item: Dict) -> Optional[Dict]:
        """原始行 → provider 行契约（字段映射见模块 docstring 的打样结论）"""
        title = str(item.get('title') or item.get('title_ch') or '').strip()
        if not title:
            return None
        codes = item.get('codes') or []
        symbols = [str(c.get('stock_code')) for c in codes if c.get('stock_code')]
        names = [str(c.get('short_name')) for c in codes if c.get('short_name')]
        art_code = str(item.get('art_code') or '')
        effective = _date_only(item.get('notice_date')) or _date_only(item.get('sort_date')) \
            or _date_only(item.get('display_time'))
        if not effective:
            # 不编造日期：拿不到就丢弃该行（丢弃量会被 domain 的 rejected 如实回报）
            return None
        url = ''
        if art_code and symbols:
            url = f'https://data.eastmoney.com/notices/detail/{symbols[0]}/{art_code}.html'
        columns = [str(c.get('column_name')) for c in (item.get('columns') or []) if c.get('column_name')]
        return {
            'scope': 'individual' if symbols else 'macro',
            'title': title,
            # type 交给领域层关键词推断（东财"栏目"是公告栏目而非事件性质，映射会错）
            'type': None,
            'effective_date': effective,
            'announce_date': _date_only(item.get('display_time')) or effective,
            'importance': None,
            'symbols': symbols,
            'industries': [],
            'source': self.name,
            'url': url,
            'summary': '；'.join(columns),
            'external_id': art_code,
            'authority': AUTHORITY_EASTMONEY,
            'raw': {
                'art_code': art_code,
                'columns': columns,
                'short_names': names,
                'display_time': item.get('display_time'),
                'notice_date': item.get('notice_date'),
                'source_type': item.get('source_type'),
            },
        }
