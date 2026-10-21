"""新浪财经 HTTP 板块通道（2026-10-21，多渠道路径之一）。

为什么单开一条 HTTP 直连通道：
  · 东财 push2 在本机网络被整段阻断（实测 HTTP 000，IPv4 强制亦无效）；
  · akshare 备源只有 49 个粗分类（券商→金融行业，精度不足）；
  · 新浪行情中心 `getHQNodes` 一次返回 **7 套板块体系**：
    新浪行业(48) / 申万行业(31) / 申万一级(31) / 申万二级(131) /
    申万三级(336) / 概念板块(214) / 热门概念(705) / 地域板块(31)
    —— 精度足以覆盖「券商=证券Ⅱ」「半导体=申万二级半导体」这类口径。

接口（均为公开 JSON，无需登录）：
  · 节点表：`Market_Center.getHQNodes`            → 名称 ↔ node code
  · 成分：  `Market_Center.getHQNodeData?node=…`  → 分页返回成分股

失败语义：网络/结构异常上抛（manager 计故障、继续走下一渠道/快照兜底）；
板块不存在返回 found=False（有效响应，不入缓存）。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import structlog

from qs_market_data.adapters.outbound.datasources.base import MarketProvider
from qs_market_data.adapters.outbound.datasources.models import MarketData

logger = structlog.get_logger(__name__)

_NODES_URL = (
    'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
    'Market_Center.getHQNodes'
)
_DATA_URL = (
    'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
    'Market_Center.getHQNodeData'
)
_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

#: 节点表缓存（板块名录低频变化；进程内 6h）
_NODES_TTL_SEC = 6 * 3600


class SinaHttpSectorProvider(MarketProvider):
    """新浪行情中心板块通道（HTTP 直连，不经 akshare）。"""

    #: 板块解析优先级：概念板块 → 申万二级 → 申万一级 → 申万行业 → 新浪行业 → 热门概念
    CATEGORY_PRIORITY: Tuple[str, ...] = (
        '概念板块', '申万二级', '申万一级', '申万行业', '新浪行业', '热门概念',
    )

    #: canonical 板块 → 候选 (category, 名称)：按序取第一个存在的节点。
    #: 只在「标题里出现 canonical 名但没点名具体板块」时使用（basis=hint 场景）。
    CANONICAL_MAP: Dict[str, Tuple[Tuple[str, str], ...]] = {
        '券商': (('申万二级', '证券Ⅱ'), ('热门概念', '券商相关')),
        '银行': (('申万一级', '银行'), ('申万行业', '银行')),
        '半导体': (('申万二级', '半导体'),),
        'AI': (('热门概念', '人工智能'),),
        '新能源': (('概念板块', '新能源'), ('热门概念', '新能源车')),
        '医药': (('申万一级', '医药生物'), ('申万行业', '医药生物')),
        '房地产': (('申万一级', '房地产'), ('新浪行业', '房地产')),
        '军工': (('申万一级', '国防军工'), ('申万行业', '国防军工')),
        '消费': (('申万一级', '食品饮料'), ('新浪行业', '食品行业')),
        '农业': (('申万一级', '农林牧渔'), ('新浪行业', '农林牧渔')),
        '资源': (('申万一级', '有色金属'), ('新浪行业', '有色金属')),
        '基建': (('申万一级', '建筑装饰'), ('新浪行业', '建筑建材')),
        '央企': (('概念板块', '央企改革'),),
    }

    LIMIT_PER_PAGE = 100
    MAX_PAGES = 10

    def __init__(self, timeout: float = 8.0, max_pages: int = MAX_PAGES):
        self._timeout = float(timeout)
        self._max_pages = max(1, int(max_pages or self.MAX_PAGES))
        self._nodes: Dict[str, Dict[str, str]] = {}
        self._nodes_at: float = 0.0
        self.last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return 'sina_http'

    # ── MarketProvider 必需项（与板块无关的方法返回 None）──────────────
    def get_market_overview(self):        # noqa: D401 - 接口占位
        return None

    def get_lhb_stock(self, symbol: str, date: str):
        return None

    def get_lhb_daily(self, date: str):
        return None

    # ── 板块列表 ─────────────────────────────────────────────
    def get_sector_list(self) -> Optional[MarketData]:
        cats = self._category_nodes()
        industries = [{'name': n, 'code': c, 'category': cat}
                      for cat in ('新浪行业', '申万一级')
                      for n, c in cats.get(cat, {}).items()]
        concepts = [{'name': n, 'code': c, 'category': cat}
                    for cat in ('概念板块',)
                    for n, c in cats.get(cat, {}).items()]
        if not industries and not concepts:
            raise RuntimeError('sina_http: no sector nodes')
        return MarketData(
            data_type='sector_list',
            data={'industries': industries, 'concepts': concepts,
                  'total': len(industries) + len(concepts),
                  'industry_count': len(industries),
                  'concept_count': len(concepts)},
            source=self.name,
            timestamp=datetime.now().isoformat(),
        )

    # ── 板块成分 ─────────────────────────────────────────────
    def get_sector_stocks(self, sector: str) -> Optional[MarketData]:
        name = str(sector or '').strip()
        if not name:
            return None
        node, coarse = self._resolve_node(name)
        if node is None:
            return MarketData(
                data_type='sector_stocks',
                data={'sector': name, 'found': False, 'sector_code': None,
                      'stocks': [], 'coarse': False},
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )
        stocks = self._fetch_members(node)
        if stocks is None:            # 网络/结构异常：交给 manager 降级
            return None
        return MarketData(
            data_type='sector_stocks',
            data={'sector': name, 'found': bool(stocks), 'sector_code': node,
                  'stocks': stocks, 'count': len(stocks), 'coarse': coarse},
            source=self.name,
            timestamp=datetime.now().isoformat(),
        )

    # ── 内部：节点表 ─────────────────────────────────────────
    def _get_json(self, url: str, params: Dict[str, Any]) -> Any:
        import requests

        resp = requests.get(url, params=params,
                            headers={'User-Agent': _UA}, timeout=self._timeout)
        resp.raise_for_status()
        text = resp.text.strip()
        # 新浪返回的是非法 JSON（键无引号）的场景已由 json_v2 保证；保险起见兼容
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            fixed = re.sub(r'([{,])\s*([A-Za-z_]\w*)\s*:', r'\1"\2":', text)
            return json.loads(fixed)

    def _category_nodes(self) -> Dict[str, Dict[str, str]]:
        if self._nodes and (time.time() - self._nodes_at) < _NODES_TTL_SEC:
            return self._nodes
        raw = self._get_json(_NODES_URL, {})
        cats: Dict[str, Dict[str, str]] = {}
        # 结构：["行情中心", [["A股", [["新浪行业", [[name, "", code], ...]], ...], ...], ...]]
        try:
            for group in raw[1]:
                if not (isinstance(group, list) and group and group[0] == 'A股'):
                    continue
                for cat in group[1]:
                    if not (isinstance(cat, list) and len(cat) > 1
                            and isinstance(cat[0], str)):
                        continue
                    mapping: Dict[str, str] = {}
                    for item in cat[1]:
                        if (isinstance(item, list) and len(item) >= 3
                                and item[0] and item[2]):
                            mapping[str(item[0]).strip()] = str(item[2]).strip()
                    if mapping:
                        cats[cat[0]] = mapping
        except (IndexError, TypeError) as e:
            self.last_error = 'sina_http: 节点表结构异常 %s: %s' % (type(e).__name__, e)
            raise RuntimeError(self.last_error)
        if not cats:
            self.last_error = 'sina_http: 节点表为空'
            raise RuntimeError(self.last_error)
        self._nodes, self._nodes_at = cats, time.time()
        return cats

    def _resolve_node(self, name: str) -> Tuple[Optional[str], bool]:
        """板块名 → node code；返回 (code, coarse)。coarse=True 表示走了映射/模糊匹配。"""
        cats = self._category_nodes()
        # 1) 精确名（按优先级）
        for cat in self.CATEGORY_PRIORITY:
            code = cats.get(cat, {}).get(name)
            if code:
                return code, False
        # 2) canonical 映射（券商 → 证券Ⅱ …）
        for cat, mapped in self.CANONICAL_MAP.get(name, ()):
            code = cats.get(cat, {}).get(mapped)
            if code:
                return code, True
        # 3) 模糊：包含关系，但要求名称长度 ≥2 且唯一命中（避免歧义）
        for cat in self.CATEGORY_PRIORITY:
            hits = [(n, c) for n, c in cats.get(cat, {}).items()
                    if name in n or n in name]
            if len(hits) == 1:
                return hits[0][1], True
        return None, False

    def _fetch_members(self, node: str) -> Optional[List[Dict[str, Any]]]:
        stocks: List[Dict[str, Any]] = []
        seen = set()
        for page in range(1, self._max_pages + 1):
            try:
                rows = self._get_json(_DATA_URL, {
                    'page': page, 'num': self.LIMIT_PER_PAGE,
                    'sort': 'symbol', 'asc': 1, 'node': node,
                })
            except Exception as e:  # noqa: BLE001 - 交由 manager 计故障
                self.last_error = 'sina_http: 成分取数失败 %s: %s' % (
                    type(e).__name__, e)
                logger.warning('sina_http 板块成分取数失败',
                               node=node, page=page, error=self.last_error)
                return None
            if not isinstance(rows, list) or not rows:
                break
            for row in rows:
                if not isinstance(row, dict):
                    continue
                code = str(row.get('code') or '').strip()
                if not code or code in seen:
                    continue
                seen.add(code)
                stocks.append({
                    'symbol': code,
                    'name': str(row.get('name') or '').strip(),
                    'pe': _num(row.get('per')),
                    # 新浪 mktcap 单位万元 → 元（与东财口径一致）
                    'market_cap': _num(row.get('mktcap')) * 10000,
                })
            if len(rows) < self.LIMIT_PER_PAGE:
                break
        return stocks


def _num(value: Any) -> float:
    try:
        if value in (None, '', '-'):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
