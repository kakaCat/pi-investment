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
import time
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
_ORG_URL = 'http://www.cninfo.com.cn/new/information/topSearch/query'
# orgId 缓存分两张表（2026-09-14 w-32314d00 修静默降级）：
#   成功：进程内长期缓存（orgId 基本不变，值得缓存）
#   失败：**只做短 TTL 缓存**，且每次命中都要再告警一次
# 为什么拆开：原实现把失败也写成空串长期缓存，于是
#   ① 一次瞬时网络抖动 → 该标的**整个进程生命周期**都走 searchkey 回退路径
#      （而回退路径是**已知会少收**的：searchkey 是全文检索，见 fetch_symbol_events 注释）；
#   ② 更糟的是命中缓存时直接 return，**连日志都不再打**——
#      降级从"一次告警"变成"永久静默"。这正是本仓反复出现的静默少收模式。
_ORG_CACHE: Dict[str, str] = {}          # symbol -> orgId（仅缓存成功结果）
_ORG_FAIL_CACHE: Dict[str, float] = {}   # symbol -> 失败时刻（monotonic 秒）
_ORG_FAIL_TTL_SECONDS = 600              # 失败后 10 分钟内不重打上游，超时自动重试


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
        self._fallback_symbols = []   # orgId 解析失败、回退全文检索的标的（会漏，必须可见）
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
                    # 2026-09-13（w-a9ec14d7）**修静默少收 bug**：
                    # 原来直接用 searchkey=<代码> 检索，而巨潮是**全文检索**——
                    # searchkey=000001 会命中一堆「公告编号里含 000001」的别家公司公告，
                    # 再经 secCode==searchkey 过滤后一条不剩 -> 返回 0 条，
                    # 调用方以为「这只票没有公告」（实测平安银行就是这样被静默吞掉的）。
                    # 正确姿势：stock=<代码>,<orgId>（orgId 由 topSearch 解析，见 _resolve_org_id）。
                    org = self._resolve_org_id(symbol)
                    if org:
                        items, _total = self._query_page('szse', '', se_date, _PAGE_SIZE, 1,
                                                         stock='%s,%s' % (symbol, org))
                        for item in items:
                            row = self._map(item, symbol)   # 仍按 secCode 过滤，防串号
                            if row:
                                rows.append(row)
                    else:
                        # 回退：老的全文字段检索（会漏，漏多少无法预知）——
                        # 必须记入 _fallback_symbols 并写进 truncation_note，绝不静默。
                        self._fallback_symbols.append(symbol)
                        rows.extend(self._query(symbol, se_date, _PAGE_SIZE))
            self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
            if self._fallback_symbols:
                note = ('%s: %d 只标的 orgId 解析失败，已回退全文检索（searchkey）——该路径会静默少收，'
                        '本次结果对这些标的不完整：%s'
                        % (self.name, len(self._fallback_symbols), ','.join(self._fallback_symbols[:8])))
                self.truncation_note = (self.truncation_note + ' | ' + note) if self.truncation_note else note
                logger.warning(note)
            return rows
        except Exception as exc:  # noqa: BLE001 —— fail-loud
            self.last_error = f'{type(exc).__name__}: {exc}'
            logger.warning('cninfo_disclosure fetch failed: %s', self.last_error)
            return None

    # ------------------------------------------------------------------ 内部

    def _resolve_org_id(self, symbol: str) -> Optional[str]:
        """查巨潮 orgId（per-symbol 可靠检索的前提）。

        ⚠️ 2026-09-13 实测两条必须记住的结论：
        ① stock=<code>（不带 orgId）无效（返回 0 条）——旧文档只写了这一半，
           其实带 orgId 就有效：stock=000001,gssz0000001 正常返回该股公告；
        ② orgId 无法按规则推导（实测 gssz/gssh 补零共 7 种拼法全 0），
           必须查 topSearch/query：300750 -> GD165627、688981 -> gshk0000981。
        """
        if symbol in _ORG_CACHE:
            return _ORG_CACHE[symbol] or None
        failed_at = _ORG_FAIL_CACHE.get(symbol)
        if failed_at is not None and (time.monotonic() - failed_at) < _ORG_FAIL_TTL_SECONDS:
            # 仍在失败 TTL 内：不重打上游，但**必须每次都留下痕迹** ——
            # 静默降级等于让调用方以为"这只票就是没公告"。
            logger.warning(
                'cninfo orgId 仍在上次失败的重试冷却中（%s），本次继续走 searchkey 回退（会少收）',
                symbol)
            return None
        try:
            resp = _session().post(
                _ORG_URL, data={'keyWord': symbol, 'maxNum': 10},
                headers={'User-Agent': _UA, 'Referer': 'http://www.cninfo.com.cn/'},
                timeout=self.timeout)
            arr = resp.json() if resp.status_code == 200 else []
            org = None
            for it in (arr or []):
                if str(it.get('code')) == str(symbol):
                    org = str(it.get('orgId') or '')
                    break
            if org:
                _ORG_CACHE[symbol] = org
                _ORG_FAIL_CACHE.pop(symbol, None)
                return org
            # 上游 200 但没解析出 orgId：同样按失败处理（短 TTL，不永久缓存）
            logger.warning('cninfo orgId 未命中 %s（topSearch 返回 %s 条，无匹配 code）',
                           symbol, len(arr or []))
            _ORG_FAIL_CACHE[symbol] = time.monotonic()
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning('cninfo orgId 解析失败 %s: %s', symbol, str(exc)[:120])
            _ORG_FAIL_CACHE[symbol] = time.monotonic()
            return None

    def fetch_symbol_history(self, symbols: List[str], start_date: str, end_date: str,
                             page_size: int = 30, max_symbols: int = 0) -> Optional[List[Dict]]:
        """按 标的 x 日期区间 回补历史公告（研究级回补的可靠路径；RFC 015 §4，2026-09-13）

        为什么需要：日期区间全市场路径实测不可用——巨潮忽略 pageNum/column，
        一次只返回 30 条（而全市场一天就有 1358 条），无法支撑研究。
        逐标的路径天然有界（单股单窗口公告数很少），配合按月切片即可完整回补。

        失败语义：单只 orgId 解析失败/查询异常 → 记入 org_unresolved / failed_symbols 并继续，
        但这些「没查到的」必须让调用方看到——禁止把「没查到」当成「没有公告」
        （这正是本日反复出现的静默少收模式）。
        """
        self.last_error = None
        self.truncation_note = ''
        self.failed_symbols = []
        self.org_unresolved = []
        se_date = '%s~%s' % (start_date, end_date)
        targets = [str(s).strip() for s in (symbols or []) if str(s).strip()]
        if max_symbols and len(targets) > max_symbols:
            self.truncation_note = ('%s: 请求 %d 只，超过本轮上限 %d 只，仅处理前 %d 只'
                                    % (self.name, len(targets), max_symbols, max_symbols))
            targets = targets[:max_symbols]
        rows: List[Dict] = []
        seen = set()
        for symbol in targets:
            org = self._resolve_org_id(symbol)
            if not org:
                self.org_unresolved.append(symbol)
                continue
            try:
                items, _total = self._query_page('szse', '', se_date, page_size, 1,
                                                 stock='%s,%s' % (symbol, org))
            except Exception as exc:  # noqa: BLE001
                self.failed_symbols.append('%s:%s' % (symbol, type(exc).__name__))
                continue
            for item in items:
                row = self._map(item, symbol)   # 过滤：只留该标的自述公告
                if not row:
                    continue
                key = row.get('external_id') or (row.get('title'), row.get('announce_date'))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
        if self.org_unresolved or self.failed_symbols:
            self.last_error = ('部分标的不完整：orgId 未解析 %d 只、查询失败 %d 只（%s）'
                               % (len(self.org_unresolved), len(self.failed_symbols),
                                  ','.join((self.org_unresolved + self.failed_symbols)[:8])))
        return rows

    def _query_page(self, column: str, searchkey: str, se_date: str,
                    page_size: int, page_num: int, stock: str = ''):
        """单页查询，返回 (items, totalAnnouncement)。

        与 _query 的区别：把 pageNum 暴露出来，供 fetch_market_events 分页
        （_query 固定 pageNum=1）。**不改 _query 的行为**，避免影响既有调用与测试。
        """
        payload = {
            'pageNum': page_num, 'pageSize': page_size, 'column': column, 'tabName': 'fulltext',
            'stock': stock, 'searchkey': searchkey, 'secid': '', 'plate': '', 'category': '',
            'trade': '', 'seDate': se_date, 'sortName': '', 'sortType': '', 'isHLtitle': 'true',
        }
        resp = _session().post(_URL, data=payload,
                               headers={'User-Agent': _UA, 'Referer': 'http://www.cninfo.com.cn/'},
                               timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f'HTTP {resp.status_code} from cninfo hisAnnouncement ({column})')
        body = resp.json()
        items = body.get('announcements')
        total = int(body.get('totalAnnouncement') or 0)
        if items is None:
            if total == 0:
                return [], 0
            raise RuntimeError('响应结构异常：announcements 缺失（上游可能改版）')
        return items, total

    def fetch_market_events(self, start_date: str, end_date: str,
                            max_pages: int = 10) -> Optional[List[Dict]]:
        """按日期区间分页拉取**全市场**法定披露（研究级回补；RFC 015 §4，2026-09-13）

        实现要点（都对应真实踩坑）：
        · 双通道 szse + sse（巨潮按交易所 column 分开返回）；
        · 按 announcementId 去重（同一公告可能出现在两通道的边界页）；
        · **截断显式标注**：翻到 max_pages 仍未取全（累计 < totalAnnouncement）时写
          self.truncation_note —— "取到一半"与"全市场就这么多"必须可区分，
          否则研究会系统性低估事件密度；
        · 失败返回 None 并写 last_error（沿用端口失败/空结果语义分离纪律）。
        """
        self.last_error = None
        self.truncation_note = ''
        self.last_fetched_at = None
        se_date = '%s~%s' % (start_date, end_date)
        rows: List[Dict] = []
        seen = set()
        truncated = []
        try:
            for column in ('szse', 'sse'):
                total = None
                for page in range(1, max(1, max_pages) + 1):
                    items, total_ann = self._query_page(column, '', se_date,
                                                        _MARKET_PAGE_SIZE, page)
                    if total is None:
                        total = total_ann
                    if not items:
                        break
                    for item in items:
                        row = self._map(item, '')
                        if not row:
                            continue
                        key = row.get('external_id') or (row.get('title'), row.get('announce_date'))
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(row)
                    if len(items) < _MARKET_PAGE_SIZE:
                        break
                # 截断判定：该通道公告总数 > 本次实际抓到的条数
                if total and len([r for r in rows if True]) < total:
                    truncated.append('%s: total=%d' % (column, total))
        except Exception as exc:  # noqa: BLE001
            self.last_error = '%s: %s' % (type(exc).__name__, str(exc)[:160])
            if not rows:
                return None
            # 部分成功：如实返回已取到的行，并把失败写进 last_error（不静默）
        if truncated:
            self.truncation_note = ('%s 日期区间 %s 分页上限 %d 页未取全（%s）；'
                                    '本次取回 %d 行 —— 做事件密度统计前必须先扩 max_pages'
                                    % (self.name, se_date, max_pages, '; '.join(truncated), len(rows)))
        self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
        return rows

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
