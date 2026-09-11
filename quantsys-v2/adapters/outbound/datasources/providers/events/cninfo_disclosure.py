"""巨潮资讯网公告 provider（RFC 015 §3.3 优先级 2：**法定披露，权威源**）

## 真实响应打样（2026-09-11 本机实测，非文档/mock）

接口：`POST http://www.cninfo.com.cn/new/hisAnnouncement/query`（表单参数，非 JSON）
实测参数：`pageNum=1&pageSize=20&column=szse&tabName=fulltext&searchkey=600150&seDate=2026-08-12~2026-09-18&isHLtitle=true`

实测响应（2026-09-11，HTTP 200，直连不用代理）：

    {"totalAnnouncement": 22, "totalRecordNum": 22, "announcements": [
        {"secCode": "600150",
         "secName": "<em>中国船舶</em>",                     # ⚠️ 带高亮标签 <em>
         "orgId": "gssh0600150",
         "announcementId": "1225558999",
         "announcementTitle": "关于北海造船厂一货轮火灾事故有关情况的公告",
         "announcementTime": 1789126467000,                  # 毫秒时间戳
         "adjunctUrl": "finalpage/2026-09-11/1225558999.PDF",
         "adjunctSize": 235, "adjunctType": "PDF",
         "columnId": "09020202||160203||250301||251302",
         "announcementType": "01010901||010112||011015||011999||012903",
         "pageColumn": "SZCY"},
        ...]}

字段映射结论（逐列核对）：
- `announcementId`   → external_id（巨潮公告唯一 ID，拼 PDF 链接）
- `secCode`          → symbols
- `secName`          → 名称，**必须剥掉 `<em>` 高亮标签**（实测 searchkey 查询会加高亮）
- `announcementTitle` → title（**无公司名前缀**——与东财「中国船舶:关于…」不同，
  这正是领域层 normalize_title 要解决的两源差异）
- `announcementTime` → announce_date（毫秒时间戳，按 **UTC+8** 换算；本机时区虽为 +08:00，
  但显式加 8 小时不依赖运行环境，避免服务器换时区后日期错一天）
- `adjunctUrl`       → url = `http://static.cninfo.com.cn/{adjunctUrl}`（实测 PDF 可下载）
- effective_date 取公告日：公告类事件的"生效"就是"披露"，巨潮不提供另行生效日。

⚠️ 陷阱（实测）：`stock=600150` 参数**无效**（返回 total=0）；必须用 `searchkey=600150`。
而 searchkey 是全文检索，会命中**提及该代码的其他公司公告**（如法律意见书），
故 provider 必须按 `secCode == 目标代码` 过滤，否则会把别家事件算到本标的头上。

## 独立通道声明（§1.5.2 硬约束 1）
巨潮 = 深沪交易所指定的法定信息披露平台，与东财公告流（聚合转载）**上游完全独立**，
且权威度更高（90 > 60）：两源对同一公告都会出条目 → 由领域层 R3 合并、保留巨潮、差异留痕。
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

from domain.events.model import AUTHORITY_CNINFO
from domain.events.ports.IMarketEventProvider import IMarketEventProvider

logger = logging.getLogger(__name__)

_URL = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
_STATIC = 'http://static.cninfo.com.cn/'
_TAG = re.compile(r'<[^>]+>')
# 公告检索窗口（往后 7 天：公告一般不发未来，保留一点富余；往前 30 天：排雷要最近的）
_WINDOW_BACK_DAYS = 30
_WINDOW_FWD_DAYS = 7
_PAGE_SIZE = 20
_MAX_SYMBOLS = 20
_MARKET_PAGE_SIZE = 50


def _session() -> requests.Session:
    global _SESSION
    try:
        return _SESSION
    except NameError:
        pass
    session = requests.Session()
    session.trust_env = False
    adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    globals()['_SESSION'] = session
    return session


def _strip_tags(text) -> str:
    """剥掉 <em> 等高亮标签（巨潮 searchkey 查询会给标题加高亮）"""
    return _TAG.sub('', str(text or '')).strip()


def _ms_to_date(ms) -> str:
    """毫秒时间戳 → 'YYYY-MM-DD'（按 UTC+8 换算，不依赖运行机时区）

    用 timezone-aware 的 fromtimestamp 而非已废弃的 utcfromtimestamp —— 后者在
    Python 3.13 已发 DeprecationWarning，未来版本移除后本函数会在 ingest 路径直接抛错。
    """
    try:
        seconds = float(ms) / 1000.0
    except (TypeError, ValueError):
        return ''
    if seconds <= 0:
        return ''
    return (datetime.fromtimestamp(seconds, timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d')


class CninfoDisclosureProvider(IMarketEventProvider):
    """巨潮资讯网法定披露（个股事件通道 2；**权威源**，权威度 90）"""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self.last_fetched_at: Optional[str] = None
        # 截断标注（静默失败清单 §2）：标的数超 _MAX_SYMBOLS 时列出未采集的代码
        self.truncated_symbols: List[str] = []
        self.truncation_note: str = ''

    @property
    def name(self) -> str:
        return 'cninfo_disclosure'

    # ------------------------------------------------------------------ 政策

    def fetch_policy(self) -> Optional[List[Dict]]:
        """巨潮公告流不含政策文件 → 返回 []（空结果 ≠ 故障）"""
        return []

    # -------------------------------------------------------------- 个股事件

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """个股法定披露公告（按标的检索；symbols=None 时取当日全市场公告采样）"""
        self.last_error = None
        self.truncated_symbols = []
        self.truncation_note = ''
        targets = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        try:
            today = date.today()
            se_date = '%s~%s' % (
                (today - timedelta(days=_WINDOW_BACK_DAYS)).strftime('%Y-%m-%d'),
                (today + timedelta(days=_WINDOW_FWD_DAYS)).strftime('%Y-%m-%d'),
            )
            rows: List[Dict] = []
            if not targets:
                rows.extend(self._query('', se_date, _MARKET_PAGE_SIZE, columns=('szse',)))
                rows.extend(self._query('', se_date, _MARKET_PAGE_SIZE, columns=('sse',)))
            else:
                queried = targets[:_MAX_SYMBOLS]
                if len(targets) > _MAX_SYMBOLS:
                    # 不静默截断：超出上限的标的必须被如实标注（含日志告警）
                    self.truncated_symbols = targets[_MAX_SYMBOLS:]
                    self.truncation_note = (
                        '%s: 请求标的 %d 只，超过单次上限 %d 只，本次仅检索前 %d 只；'
                        '未检索 %d 只（%s）'
                        % (self.name, len(targets), _MAX_SYMBOLS, _MAX_SYMBOLS,
                           len(self.truncated_symbols),
                           ','.join(self.truncated_symbols[:10])
                           + ('…' if len(self.truncated_symbols) > 10 else ''))
                    )
                    logger.warning(self.truncation_note)
                for symbol in queried:
                    rows.extend(self._query(symbol, se_date, _PAGE_SIZE))
            self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
            return rows
        except Exception as exc:  # noqa: BLE001 —— fail-loud
            self.last_error = f'{type(exc).__name__}: {exc}'
            logger.warning('cninfo_disclosure fetch failed: %s', self.last_error)
            return None

    # ------------------------------------------------------------------ 内部

    def _query(self, searchkey: str, se_date: str, page_size: int,
               columns=('szse',)) -> List[Dict]:
        out: List[Dict] = []
        for column in columns:
            payload = {
                'pageNum': 1, 'pageSize': page_size, 'column': column, 'tabName': 'fulltext',
                'stock': '', 'searchkey': searchkey, 'secid': '', 'plate': '', 'category': '',
                'trade': '', 'seDate': se_date, 'sortName': '', 'sortType': '', 'isHLtitle': 'true',
            }
            resp = _session().post(_URL, data=payload,
                                   headers={'User-Agent': _UA, 'Referer': 'http://www.cninfo.com.cn/'},
                                   timeout=self.timeout)
            if resp.status_code != 200:
                raise RuntimeError(f'HTTP {resp.status_code} from cninfo hisAnnouncement ({column})')
            body = resp.json()
            items = body.get('announcements')
            if items is None:
                # 明确区分"没数据"（空列表）与"结构异常"：后者必须 fail-loud
                if body.get('totalAnnouncement') == 0 and body.get('announcements') is None:
                    continue
                raise RuntimeError('响应结构异常：announcements 缺失（上游可能改版）')
            for item in items:
                row = self._map(item, searchkey)
                if row:
                    out.append(row)
        return out

    def _map(self, item: Dict, searchkey: str) -> Optional[Dict]:
        title = _strip_tags(item.get('announcementTitle'))
        if not title:
            return None
        symbol = str(item.get('secCode') or '').strip()
        # searchkey 是全文检索 → 必须过滤掉"提及该代码但不是该标的自述"的公告
        if searchkey and symbol and symbol != searchkey:
            return None
        announce_date = _ms_to_date(item.get('announcementTime'))
        if not announce_date:
            return None
        adjunct = str(item.get('adjunctUrl') or '')
        return {
            'scope': 'individual' if symbol else 'macro',
            'title': title,
            'type': None,                     # 交领域层按标题关键词推断
            'effective_date': announce_date,
            'announce_date': announce_date,
            'importance': None,
            'symbols': [symbol] if symbol else [],
            'industries': [],
            'source': self.name,
            'url': _STATIC + adjunct if adjunct else '',
            'summary': str(item.get('pageColumn') or ''),
            'external_id': str(item.get('announcementId') or ''),
            'authority': AUTHORITY_CNINFO,
            'raw': {
                'secCode': symbol,
                'secName': _strip_tags(item.get('secName')),
                'orgId': item.get('orgId'),
                'announcementTime': item.get('announcementTime'),
                'announcementType': item.get('announcementType'),
                'columnId': item.get('columnId'),
                'adjunctType': item.get('adjunctType'),
            },
        }
