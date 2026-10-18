"""证监会/交易所发布页 provider（RFC 015 §3.3 政策事件优先级 2）

## 真实响应打样（2026-09-11 本机实测，非文档/mock）

### 通道 A：中国证监会「政策解读」（可用）
GET http://www.csrc.gov.cn/csrc/c100039/common_list.shtml → HTTP 200（utf-8 需显式设 encoding），
条目结构（逐字段核对）：
    <li><a href="/csrc/c100028/c7634324/content.shtml" target="_blank" >
        中国证监会等八部门联合印发《综合整治非法跨境证券期货基金经营活动实施方案》</a>
        <span class="date">2026-05-22</span></li>
实测最新 5 条日期：2026-05-22 / 2026-05-22 / 2026-05-15 / 2026-04-24 / 2026-04-10
→ 能取到真实条目，但**发布节奏低**（政策解读不是天天有），故政策 ingest 不能只靠这一条通道，
  必须与 gov_policy（国务院/发改委，日更）并联（RFC §3.3 要求 ≥2 通道 + 人工兜底）。

### 通道 B：交易所发布页（打样失败，未实现，如实记录）
- 上交所 https://www.sse.com.cn/lawandrules/sselawsrules/ ：HTTP 200，但条目由 JS 渲染，
  静态 HTML 里抓到的 a 标签全是导航链接（"一网通办"/"English"），无业务规则条目。
- 上交所 http://query.sse.com.cn/commonSoaQuery.do?...&sqlId=BS_GGLL ：
  返回 SOA service missing parameter [siteId]（缺站点签名参数，直连取不到）。
- 上交所 http://query.sse.com.cn/infodisplay/queryLatestBulletinNew.do ：HTTP 200 但 data 为空
  （BULLETIN_HEADING 全为 null）——需要站点会话/签名。
- 深交所 https://www.szse.cn/lawrule/notice/index.html ：404；
  https://www.szse.cn/api/report/ShowReport/data?CATALOGID=lgzc_new ：HTTP 200 但 recordcount=0
  （CATALOGID 需按其站内 JS 选取，本次打样未定位到可用 ID）。
→ 结论：交易所通道本次**未打通**，不写"假装能用"的 provider（§1.5.2 硬约束 3：未验证不得注册）；
  交易所政策暂由 gov_policy（国务院/发改委覆盖证券监管口径）+ 人工策展兜底。

### 其他证监会栏目的时效（实测，说明为什么不选它们）
- c100028（证监会要闻）：最新 2021-12-10（静态页停更）
- c100029（新闻发布会）：最新 2024-04-12
- c100030（辖区监管动态）：最新 2021-12-11
→ 只有 c100039（政策解读）具备可用时效，故选它。
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests

from domain.events.model import AUTHORITY_CSRC
from domain.events.ports.IMarketEventProvider import IMarketEventProvider

logger = logging.getLogger(__name__)

_BASE = 'http://www.csrc.gov.cn'
_LIST = _BASE + '/csrc/c100039/common_list.shtml'
_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
_WINDOW_DAYS = 180          # 政策解读低频：窗口放到 180 天，避免长期空转
_MAX_ITEMS = 40
_ITEM = re.compile(r'<a\s+href="([^"]+)"[^>]*>\s*(.*?)\s*</a>\s*<span class="date">([^<]+)</span>', re.S)
_TAG = re.compile(r'<[^>]+>')
_CJK = re.compile(r'[\u4e00-\u9fa5]')
_SESSION: Optional[requests.Session] = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        session = requests.Session()
        session.trust_env = False
        adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        _SESSION = session
    return _SESSION


class CsrcPolicyProvider(IMarketEventProvider):
    """证监会政策解读（政策事件通道 2；权威度 85）"""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self.last_fetched_at: Optional[str] = None

    @property
    def name(self) -> str:
        return 'csrc_policy'

    # ------------------------------------------------------------------ 政策

    def fetch_policy(self) -> Optional[List[Dict]]:
        self.last_error = None
        try:
            resp = _session().get(_LIST, headers={'User-Agent': _UA}, timeout=self.timeout)
            if resp.status_code != 200:
                raise RuntimeError(f'HTTP {resp.status_code} from csrc c100039')
            resp.encoding = 'utf-8'
            today = date.today()
            low = today - timedelta(days=_WINDOW_DAYS)
            rows: List[Dict] = []
            for href, inner, date_text in _ITEM.findall(resp.text):
                title = _TAG.sub('', inner).strip()
                effective = str(date_text).strip()[:10]
                # ⚠️ 实测踩坑（2026-09-11）：页面导航链接也带 <span class="date">，
                # 正则会把 "English" 这类导航项当条目（入库标题是 "English\r\n"）。
                # 三重过滤：①必须是 /csrc/ 正文链接 ②标题含 ≥4 个汉字 ③长度 ≥8。
                if not title or not href.startswith('/csrc/'):
                    continue
                if len(title) < 8 or len(_CJK.findall(title)) < 4:
                    continue
                try:
                    day = datetime.strptime(effective, '%Y-%m-%d').date()
                except ValueError:
                    continue
                if not (low <= day <= today):
                    continue
                url = _BASE + href
                rows.append({
                    'scope': None,
                    'type': 'policy',
                    'title': title,
                    'effective_date': effective,
                    'announce_date': effective,
                    'importance': None,
                    'symbols': [],
                    'industries': [],
                    'source': self.name,
                    'url': url,
                    'summary': '中国证监会·政策解读',
                    'external_id': url,
                    'authority': AUTHORITY_CSRC,
                    'raw': {'sub_channel': 'csrc.gov.cn/csrc/c100039',
                            'note': '证监会政策解读栏目（低频，实测最新条目 2026-05-22）'},
                })
                if len(rows) >= _MAX_ITEMS:
                    break
            self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
            return rows          # 可能为空（该栏目本窗口确实没有新政策）——空结果不是故障
        except Exception as exc:  # noqa: BLE001 —— fail-loud
            self.last_error = f'{type(exc).__name__}: {exc}'
            logger.warning('csrc_policy fetch failed: %s', self.last_error)
            return None

    # -------------------------------------------------------------- 个股事件

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        return []
