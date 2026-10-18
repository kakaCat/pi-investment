"""主营构成 provider（RFC 015 §2.3 优先级 1/2：**成员归位的唯一硬证据**）

本模块承载**两条独立上游通道**（§1.5.2 硬约束 1：同一数据类型的 provider 必须来自不同上游）：

| class | name | 上游通道 | 提供 |
|---|---|---|---|
| EastmoneyRevenueProvider | eastmoney_revenue | 东财 F10 emweb.securities.eastmoney.com | 主营构成：按产品/按行业分类的**营收占比** |
| ThsRevenueProvider | ths_revenue | 同花顺 F10 basic.10jqka.com.cn | 产品构成：产品名称/产品类型/主营业务（**无占比**，作为关键词证据与独立佐证） |

## 返回值的四态契约（2026-09-11 全仓统一，manager._try_providers 消费）

| 返回 | last_error | last_note | 语义 |
|---|---|---|---|
| 行列表（非空） | None | '' | 取到数据 |
| **[]** | **None** | **<诊断文本>** | **健康无数据**（上游 200 但该标的没有主营构成/未披露）→ manager 计入 empty_sources，**不计故障、不影响熔断与健康分**，并继续降级下一源 |
| None | <原因> | '' | **真故障**（HTTP 异常/重试耗尽/页面改版/结构不符/代码无法映射）→ 计故障 |
| None | 空 | 空 | ⚠️ 禁止（两头不靠：manager 既判不了故障，也判不了健康空；会被记成"非空但无效"） |

⚠️ provider 是**长生命周期单例**：每次入口（含 business_scope）必须重置 last_error **与 last_note**，
否则上一次调用的诊断会泄漏到下一次（"无数据说明"挂到一次真故障上会误导排障）。

## 真实响应打样（2026-09-11 本机实测，非文档/mock）

1) 东财 F10（**可用**，实测 0.4s）：
   GET https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax?code=SH600176
   顶层键: ['zyfw', 'zygcfx', 'jyps']；`zygcfx` 200 行，真实列名：
     SECUCODE / SECURITY_CODE / REPORT_DATE('2026-06-30 00:00:00') / MAINOP_TYPE('1'|'2'|'3') /
     ITEM_NAME('玻纤及其制品相关') / MAIN_BUSINESS_INCOME / **MBI_RATIO(0.973241，小数非百分数)** /
     MAIN_BUSINESS_COST / MBC_RATIO / MAIN_BUSINESS_RPOFIT / MBR_RATIO / GROSS_RPOFIT_RATIO / RANK
   MAINOP_TYPE 口径（与 akshare stock_zygc_em 源码一致）：1=按行业分类，2=按产品分类，3=按地区分类。
   ⚠️ 单位陷阱：MBI_RATIO 已是小数；若按百分数处理会得到 0.97%，与"97.3%"差 100 倍——
   本 provider 统一走 _to_ratio 归一，越界值由领域模型抛错（不静默变 0）。
   ⚠️ **同上游的另一条路不算独立通道**：akshare 的 stock_zygc_em 源码就是打同一 URL
   （emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax），故**不另立 provider**
   （§1.5.2：禁止把同一个上游 API 包两个类充数）。

2) 同花顺 F10（**可用**，实测 0.3s，GBK）：
   GET http://basic.10jqka.com.cn/600176/operate.html
   真实页面片段（实测原文）：<span class="hltip f12">主营业务：</span><p>玻璃纤维及制品的生产、销售。</p>
     <span class="hltip f12">产品类型：</span><p>玻纤纱及制品</p>
     <span class="hltip f12">产品名称：</span><p>电子布、粗纱及制品</p>
   注意：同花顺的**数值型**主营构成表是 JS 异步加载的，静态页面只有文本字段 → 本 provider
   只提供关键词证据（ratio=None），由领域层作为 PRODUCT_PROFILE 证据使用（优先级低于主营构成）。

3) 打样失败/不可用通道（如实记录，未注册）：
   - 东财概念/行业成分 push2/17.push2.eastmoney.com：经本机代理被拒（ProxyError），详见 akshare_concept.py
   - 同花顺概念成分 q.10jqka.com.cn/gn/detail/...：返回 401（需 JS token）
   - 富途概念成分 stock_concept_cons_futu：目标概念名不存在（KeyError），未采用
"""
import logging
import re
import time
from datetime import date
from typing import Dict, List, Optional

import requests

from domain.industry_chain.ports.IIndustryChainProvider import IIndustryChainProvider

logger = logging.getLogger(__name__)

# 东财 MAINOP_TYPE → 分类口径（与 akshare stock_zygc_em 源码一致，实测核对）
_MAINOP_TYPE = {'1': '按行业分类', '2': '按产品分类', '3': '按地区分类'}

_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
_NO_PROXY = {'http': None, 'https': None}

_SHARED_SESSION: Optional[requests.Session] = None


def _shared_session() -> requests.Session:
    """进程级共享 Session（连接池复用）

    为什么需要（2026-09-11 实测）：build 全部 8 条链要连打 ~80 次东财 F10；
    每次新建 TCP 连接时上游/代理很快开始拒连，失败累计到 10 次触发熔断后，
    后续全部标的静默降级到同花顺（丢掉"带占比"的硬证据）。连接复用把请求耗时与
    连接数都降下来，实测显著减少降级。
    """
    global _SHARED_SESSION
    if _SHARED_SESSION is None:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        _SHARED_SESSION = session
    return _SHARED_SESSION


def market_prefixed(symbol: str) -> str:
    """6 位代码 → 东财/同花顺用的市场前缀形式（600176 → SH600176）

    规则（A 股）：6/9 开头 = 沪市(SH)，0/2/3 开头 = 深市(SZ)，4/8 开头 = 北交所(BJ)。
    无法识别返回 ''（调用方 fail-loud，不猜）。
    """
    code = str(symbol or '').strip().upper()
    code = re.sub(r'^(SH|SZ|BJ)', '', code)
    code = code.split('.')[0]
    if not re.fullmatch(r'\d{6}', code):
        return ''
    if code[0] in ('6', '9'):
        return 'SH' + code
    if code[0] in ('0', '2', '3'):
        return 'SZ' + code
    if code[0] in ('4', '8'):
        return 'BJ' + code
    return ''


class EastmoneyRevenueProvider(IIndustryChainProvider):
    """东财 F10 主营构成（带营收占比：成员归位的硬证据）"""

    _URL = 'https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax'
    _TIMEOUT = 15

    def __init__(self, session=None):
        self._session = session or _shared_session()
        self.last_error: Optional[str] = None
        self.last_note: str = ''

    @property
    def name(self) -> str:
        return 'eastmoney_revenue'

    # -------------------------------------------------------------- 契约实现

    def list_chains(self) -> Optional[List[Dict]]:
        """主营构成源不提供产业链清单：[] = 该源无此类数据（非失败）"""
        self.last_error = None
        self.last_note = ''
        return []

    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]:
        """主营构成源不提供环节拓扑：[] = 该源无此类数据（非失败）"""
        self.last_error = None
        self.last_note = ''
        return []

    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]:
        self.last_error = None
        self.last_note = ''
        code = market_prefixed(symbol)
        if not code:
            # 真故障（入参无法映射市场前缀，是 fail-loud 而不是"这只票没有数据"）
            self.last_error = f"代码 {symbol!r} 无法映射到市场前缀（东财需 SH/SZ/BJ + 6 位数字）"
            return None

        payload = self._fetch(code)
        if payload is None:
            return None          # _fetch 内已写 last_error（真故障）
        rows_raw = payload.get('zygcfx') or []
        if not rows_raw:
            # 健康无数据：上游 200 且结构正常，只是该标的确实没有主营构成（空结果 ≠ 失败）。
            # 契约要求"空列表 + last_note"，**不得**返回 None（None 会被 manager 判成真故障/无效数据）。
            self.last_note = (
                f"东财 F10 未返回 {symbol} 的主营构成（zygcfx "
                f"{'字段缺失' if 'zygcfx' not in payload else '为空'}）——"
                "该标的可能无主营构成数据或尚未披露；交由下一源（同花顺 F10 / DB）继续降级"
            )
            return []

        rows: List[Dict] = []
        for item in rows_raw:
            ratio = item.get('MBI_RATIO')
            rows.append({
                'symbol': str(item.get('SECURITY_CODE') or code[2:]),
                'name': '',
                'report_date': str(item.get('REPORT_DATE') or '')[:10],
                'classification': _MAINOP_TYPE.get(str(item.get('MAINOP_TYPE') or ''), '未分类'),
                'item': str(item.get('ITEM_NAME') or ''),
                'revenue': item.get('MAIN_BUSINESS_INCOME'),
                'ratio': ratio,
                'basis': '东财F10主营构成(BusinessAnalysis/PageAjax)',
                'as_of': str(item.get('REPORT_DATE') or '')[:10],
                'source': self.name,
            })
        return rows

    def business_scope(self, symbol: str) -> Optional[str]:
        """经营范围/主营业务文本（zyfw.BUSINESS_SCOPE）——用于产品关键词佐证

        返回 str 表示命中；None 时**看 last_error 分辨**：last_error 非空=真故障，
        last_error 空 + last_note 非空=上游健康但该标的没有经营范围文本。
        """
        self.last_error = None
        self.last_note = ''
        code = market_prefixed(symbol)
        if not code:
            self.last_error = f"代码 {symbol!r} 无法映射到市场前缀"
            return None
        payload = self._fetch(code)
        if payload is None:
            return None
        for item in payload.get('zyfw') or []:
            scope = item.get('BUSINESS_SCOPE')
            if scope:
                return str(scope)
        self.last_note = f"东财 F10 未返回 {symbol} 的经营范围（zyfw.BUSINESS_SCOPE 为空）"
        return None

    # ------------------------------------------------------------------ HTTP

    def _fetch(self, code: str) -> Optional[Dict]:
        """取 F10 业务分析 JSON（先按系统代理，失败再绕过代理重试——本机代理对国内源时好时坏）"""
        last_exc = None
        # 三次尝试：系统代理 → 绕过代理 → 再走系统代理。
        # 实测（2026-09-11）：本机代理对东财时好时坏，单次失败就降级到同花顺会白丢"带营收占比"
        # 的硬证据（同花顺只有产品名文本），故宁可多打一次也不要静默降级。
        for attempt, proxies in enumerate((None, _NO_PROXY, None)):
            if attempt:
                time.sleep(0.4)
            try:
                kwargs = {'params': {'code': code}, 'headers': {'User-Agent': _UA}, 'timeout': self._TIMEOUT}
                if proxies is not None:
                    kwargs['proxies'] = proxies
                resp = self._session.get(self._URL, **kwargs)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    self.last_error = f"东财 F10 返回结构异常（非 dict）: {type(data).__name__}"
                    return None
                return data
            except Exception as exc:  # 网络/解析失败 = fail-loud
                last_exc = exc
                continue
        self.last_error = f"东财 F10 取数失败（代理/直连均失败）: {type(last_exc).__name__}: {last_exc}"
        logger.warning("Eastmoney revenue provider failed for %s: %s", code, last_exc)
        return None


class ThsRevenueProvider(IIndustryChainProvider):
    """同花顺 F10 经营分析（产品名称/产品类型/主营业务文本：**独立通道**，无占比）"""

    _URL = 'http://basic.10jqka.com.cn/{symbol}/operate.html'
    _TIMEOUT = 15
    _FIELD_RE = re.compile(r'<span class="hltip[^"]*">([^<：]+)：</span><p>(.*?)</p>', re.S)

    def __init__(self, session=None):
        self._session = session or requests
        self.last_error: Optional[str] = None
        self.last_note: str = ''

    @property
    def name(self) -> str:
        return 'ths_revenue'

    def list_chains(self) -> Optional[List[Dict]]:
        self.last_error = None
        self.last_note = ''
        return []

    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]:
        self.last_error = None
        self.last_note = ''
        return []

    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]:
        """返回产品构成行（ratio=None；classification='产品构成'）

        契约 C 允许 ratio 为 None（文本证据）；领域层据此产出 PRODUCT_PROFILE 归位主张。

        四态（与东财通道同口径）：命中→行列表；上游健康但无可用文本→[] + last_note；
        取数失败/页面改版→None + last_error。**没数据不得返回 None**，否则会被 manager
        判成故障，把"这只票没有产品构成"说成"同花顺挂了"。
        """
        self.last_error = None
        self.last_note = ''
        code = re.sub(r'(SH|SZ|BJ)|\.\w+', '', str(symbol or '').strip().upper())
        if not re.fullmatch(r'\d{6}', code):
            self.last_error = f"代码 {symbol!r} 不是 6 位 A 股代码"
            return None

        fields = self._fetch_fields(code)
        if fields is None:
            return None
        today = date.today().isoformat()
        rows: List[Dict] = []
        for name, text in fields.items():
            # 经营范围是工商登记范围（含大量非主营业务），只作参考不作归位证据，故单独分类
            classification = {'主营业务': '主营业务描述', '经营范围': '经营范围'}.get(name, '产品构成')
            # 产品名称/产品类型/经营范围按顿号拆成条目；主营业务是整句，不拆（拆了会得到"销售。"这种碎片）
            pieces = ([text] if name in ('主营业务', '产品类型')
                      else re.split(r'[、,，;；]', text))
            for piece in pieces:
                piece = piece.strip().strip('。')
                if not piece or len(piece) < 2:
                    continue
                rows.append({
                    'symbol': code,
                    'name': '',
                    'report_date': today,
                    'classification': classification,
                    'item': piece,
                    'revenue': None,
                    'ratio': None,
                    'basis': f'同花顺F10经营分析-{name}',
                    'as_of': today,
                    'source': self.name,
                    'field': name,
                })
        if not rows:
            # 健康无数据：页面字段解析到了，但拆分/清洗后没有可用条目（如值全为碎片）
            self.last_note = (
                f"同花顺 F10 未解析出 {symbol} 的可用产品构成条目"
                f"（页面字段：{'/'.join(fields.keys())}，清洗后均为空/过短）"
            )
            return []
        return rows

    def _fetch_fields(self, code: str) -> Optional[Dict[str, str]]:
        last_exc = None
        for proxies in (None, _NO_PROXY):
            try:
                kwargs = {'headers': {'User-Agent': _UA}, 'timeout': self._TIMEOUT}
                if proxies is not None:
                    kwargs['proxies'] = proxies
                resp = self._session.get(self._URL.format(symbol=code), **kwargs)
                resp.raise_for_status()
                html = resp.content.decode('gbk', errors='ignore')
                fields: Dict[str, str] = {}
                for raw_name, raw_value in self._FIELD_RE.findall(html):
                    value = re.sub(r'<[^>]+>', '', raw_value)
                    value = re.sub(r'\s+', '', value)
                    if value:
                        fields[raw_name.strip()] = value
                if not fields:
                    self.last_error = (
                        "同花顺 F10 页面结构变化（未解析到 主营业务/产品名称 字段）——"
                        "字段映射需重新打样核对，禁止静默返回空"
                    )
                    return None
                return fields
            except Exception as exc:
                last_exc = exc
                continue
        self.last_error = f"同花顺 F10 取数失败: {type(last_exc).__name__}: {last_exc}"
        logger.warning("THS revenue provider failed for %s: %s", code, last_exc)
        return None
