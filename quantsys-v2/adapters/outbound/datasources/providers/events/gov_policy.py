"""国务院/发改委政策发布页 provider（RFC 015 §3.3 政策事件优先级 1）

## 真实响应打样（2026-09-11 本机实测，非文档/mock）

### 通道 A：中国政府网「最新政策」JSON（**可用，首选**）
GET `https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json` → HTTP 200，application/json，
**顶层就是数组**（实测 1094 条），行结构（逐字段核对）：
    [{"TITLE": "市场监督管理所条例",
      "SUB_TITLE": "",
      "URL": "https://www.gov.cn/zhengce/content/202609/content_7080735.htm",
      "DOCRELPUBTIME": "2026-09-11"},
     {"TITLE": "国务院办公厅关于加强中小企业回款难问题治理有关工作的通知",
      "SUB_TITLE": "", "URL": "...content_7080627.htm", "DOCRELPUBTIME": "2026-09-10"}]
发现路径（值得记录，避免下次重复摸索）：HTML 页面 `https://www.gov.cn/zhengce/zuixin/`
是 JS 渲染的（<li> 里没有条目），其内联脚本里写着
`ajax({url: "./ZUIXINZHENGCE.json"})` —— 静态 HTML 抓不到条目的原因就在这里。
另注：`https://www.gov.cn/zhengce/zuixin/home.htm` 实测 **404**（旧链接已失效）。

### 通道 B：国家发改委「规范性文件」列表页（**可用**）
GET `https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/` → HTTP 200（36928 字节，**utf-8 需显式设 encoding**），
条目结构：`<li><a href="./202607/t20260731_1406815.html" title="《国家发展改革委关于修改、废止一批规章和行政规范性文件的决定》 2026年第45号令">…</a>`
→ **发布日期只能从 href 的 `tYYYYMMDD` 解析**（页面无独立 date 节点）；取不到日期的条目丢弃，不编造。
另注：`https://www.ndrc.gov.cn/xxgk/zcfb/` 返回的是 JS 跳转壳（`window.location.href='./fzggwl/'`），
必须直接打 `fzggwl/` 子页。

## 打样失败的通道（如实记录，未注册）
- `https://www.gov.cn/zhengce/zhengceku/`（政策文件库）：**403 Forbidden**（WAF 拦截）
- `https://sousuo.www.gov.cn/search-gov/data`（政府网搜索 API）：HTTP 200 但 `totalCount=0`、
  `listVO` 为空（需 JS 侧签名参数，直连取不到数据），故不用。
- `https://www.gov.cn/zhengce/zuixin/home.htm`：404

## 语义（§1.5.2 硬约束 5：失败与空结果分离）
两个子通道**任一成功**即返回行；**两个都失败**才返回 None + last_error（fail-loud）。
单通道失败时把 `degraded_sources` 记在 `self.degraded_sources`，调用方透出 degraded=True ——
"今天没有新政策"与"今天没抓到"必须可区分（RFC §3.3 硬要求）。
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

from domain.events.model import AUTHORITY_GOV
from domain.events.ports.IMarketEventProvider import IMarketEventProvider

logger = logging.getLogger(__name__)

_GOV_JSON = 'https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json'
_NDRC_LIST = 'https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/'
_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
# 政策窗口：默认回看 60 天（政策不是高频事件，窗口太短会每天空转）
_WINDOW_DAYS = 60
_MAX_ITEMS = 60
_NDRC_ITEM = re.compile(r'<li>\s*<a\s+href="([^"]+)"[^>]*?(?:title="([^"]*)")?[^>]*>(.*?)</a>', re.S)
_NDRC_DATE = re.compile(r't(\d{4})(\d{2})(\d{2})_')
_TAG = re.compile(r'<[^>]+>')
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


def _clean(text) -> str:
    return _TAG.sub('', str(text or '')).replace('&nbsp;', ' ').strip()


def _in_window(value: str, low: date, high: date) -> bool:
    try:
        day = datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return False
    return low <= day <= high


class GovPolicyProvider(IMarketEventProvider):
    """国务院/发改委发布页政策（政策事件通道 1；权威度 80）"""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self.degraded_sources: List[Dict] = []
        self.last_fetched_at: Optional[str] = None

    @property
    def name(self) -> str:
        return 'gov_policy'

    # ------------------------------------------------------------------ 政策

    def fetch_policy(self) -> Optional[List[Dict]]:
        self.last_error = None
        self.degraded_sources = []
        today = date.today()
        low = today - timedelta(days=_WINDOW_DAYS)

        rows: List[Dict] = []
        errors: List[str] = []
        for label, fetch in (('gov.cn/ZUIXINZHENGCE.json', self._fetch_gov_cn),
                             ('ndrc.gov.cn/zcfb/fzggwl', self._fetch_ndrc)):
            try:
                part = fetch(low, today)
                rows.extend(part)
            except Exception as exc:  # noqa: BLE001 —— 单通道失败降级，不拖垮整体
                errors.append(f'{label}: {type(exc).__name__}: {exc}')
                self.degraded_sources.append({'source': label, 'error': f'{type(exc).__name__}: {exc}'})
                logger.warning('gov_policy 子通道失败 %s: %s', label, exc)

        if not rows and len(errors) == len(('gov.cn', 'ndrc')):
            # 全部子通道失败 → 显式失败（禁止返回空冒充"今天没政策"）
            self.last_error = '；'.join(errors)
            return None
        self.last_fetched_at = datetime.now().isoformat(timespec='seconds')
        return rows

    # -------------------------------------------------------------- 个股事件

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """本通道是政策源，不提供个股事件 → []（空结果 ≠ 故障）"""
        return []

    # ------------------------------------------------------------------ 通道

    def _fetch_gov_cn(self, low: date, high: date) -> List[Dict]:
        resp = _session().get(_GOV_JSON, headers={'User-Agent': _UA}, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f'HTTP {resp.status_code}')
        resp.encoding = 'utf-8'
        payload = resp.json()
        if not isinstance(payload, list):
            raise RuntimeError(f'响应结构异常：期望数组，实际 {type(payload).__name__}（上游改版？）')
        out: List[Dict] = []
        for item in payload[:_MAX_ITEMS * 3]:
            title = str(item.get('TITLE') or '').strip()
            effective = str(item.get('DOCRELPUBTIME') or '').strip()[:10]
            if not title or not _in_window(effective, low, high):
                continue
            sub = str(item.get('SUB_TITLE') or '').strip()
            url = str(item.get('URL') or '').strip()
            out.append({
                'scope': None,                 # 交领域层推断（宏观/行业）
                'type': 'policy',
                'title': f'{title}（{sub}）' if sub else title,
                'effective_date': effective,
                'announce_date': effective,
                'importance': None,
                'symbols': [],
                'industries': [],
                'source': self.name,
                'url': url,
                'summary': '中国政府网·最新政策',
                'external_id': url or title,
                'authority': AUTHORITY_GOV,
                'raw': {'sub_channel': 'gov.cn/ZUIXINZHENGCE.json', 'sub_title': sub},
            })
            if len(out) >= _MAX_ITEMS:
                break
        return out

    def _fetch_ndrc(self, low: date, high: date) -> List[Dict]:
        resp = _session().get(_NDRC_LIST, headers={'User-Agent': _UA}, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f'HTTP {resp.status_code}')
        resp.encoding = 'utf-8'
        out: List[Dict] = []
        for href, title_attr, inner in _NDRC_ITEM.findall(resp.text):
            title = _clean(title_attr) or _clean(inner)
            if not title or href.startswith('../'):
                continue
            match = _NDRC_DATE.search(href)
            if not match:
                continue
            effective = f'{match.group(1)}-{match.group(2)}-{match.group(3)}'
            if not _in_window(effective, low, high):
                continue
            url = urljoin(_NDRC_LIST, href)
            out.append({
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
                'summary': '国家发展改革委·规范性文件',
                'external_id': url,
                'authority': AUTHORITY_GOV,
                'raw': {'sub_channel': 'ndrc.gov.cn/zcfb/fzggwl',
                        'date_basis': 'href 中的 tYYYYMMDD（页面无独立日期节点）'},
            })
            if len(out) >= _MAX_ITEMS:
                break
        return out
