"""概念/行业成分 provider（RFC 015 §2.3 优先级 3：**低置信候选与补全**）—— 通道 ②

通道：**东财延迟行情域 push2delay.eastmoney.com 的板块清单 + 板块成分**（不经 akshare）。
与 akshare_concept.py（通道 ①，上游实为**新浪**行业分类）是**不同上游**：
①板块分类体系不同（东财概念 504 / 东财行业 496 vs 新浪 49）；
②取数链路不同（直连东财延迟域 vs akshare→新浪）。

它**不是**成员归位的硬证据——只用于：①候选发现（seed 未覆盖的同类标的）；②交叉校验
（与主营构成冲突时以主营构成为准，RFC §2.3）。故 evidence_kind 写「概念成分」或
「行业分类」，confidence=low/medium，**绝不冒充**主营构成。

## 真实响应打样（2026-09-11 本机实测，直连，全部真数据）

板块清单（概念 m:90+t:3 / 行业 m:90+t:2，pz 实测上限 100，需翻页）：

    GET /api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:3&fields=f12,f14,f3
    {"rc":0,...,"data":{"total":504,"diff":[
       {"f3":2.54,"f12":"BK0976","f14":"被动元件概念"},
       {"f3":2.03,"f12":"BK1716","f14":"反转股"}, ...]}}
    → 概念 total=504；行业（fs=m:90+t:2）total=496。字段序 f12=板块代码 / f14=板块名 / f3=涨跌幅%
    → **pz>100 无效**：pz=500 仍只回 100 条；翻页 pn=1..N 逐页取（本 provider 已实现）。

板块成分（fs=b:<板块代码>）：

    GET /api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:BK0546&fields=f12,f14,f3
    → total=17，diff 按 f3 降序：九鼎新材002201(+10.02) / 凯盛新能600876 / 长海股份300196
      / 山东玻纤605006 / 国际复材301526 / 北玻股份002613 / 振石股份601112 / 中国巨石600176 ...
    → f12=证券代码 / f14=证券名称 / f3=涨跌幅%（**实测返回中不含价格字段**，
      故本 provider 只透出 change_pct，不臆造 price）
    → 成分表含 **B 股**（200012 南  玻Ｂ / 900918 耀皮Ｂ股）与非 A 段代码，
      本 provider 只保留 6 位 A 股代码段（00/30/60/68/92 等），其余过滤并计数。

## 为什么之前记为「打样失败」

原记录（akshare_concept.py 的失败通道表）：`ak.stock_board_concept_name_em` /
`stock_board_industry_cons_em` → ProxyError（走 17.push2.eastmoney.com 被封）。
**根因是入口域被封，不是数据不存在**：换成 push2delay 延迟域后直连 200。akshare 不是解法。

## 已知限制（实测）

| 限制 | 实测 |
|---|---|
| pz 上限 100 | pz=500 只回 100 条 → list_chains 需翻页 6 次（概念 504）/ 5 次（行业 496） |
| 必须绕过系统代理 | 与分钟线同域，经本机代理返回 rc=102 / data=null |
| 涨跌幅字段 | `fltt=2` 下 f3 是百分数（10.02 = +10.02%）；不传 fltt 会变成 1002 的整数 |
| 证据口径 | 板块成分**不是**主营构成，不参与环节归位裁决（与 akshare_concept 同定位） |
"""
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

from domain.industry_chain.ports.IIndustryChainProvider import IIndustryChainProvider

logger = logging.getLogger(__name__)

_CONCEPT_PREFIX = 'em_concept:'
_INDUSTRY_PREFIX = 'em_industry:'

# 板块类型 → (fs 选择器, chain_id 前缀, 证据类型, 置信度)
_BOARD_KINDS = {
    'concept': ('m:90+t:3', _CONCEPT_PREFIX, '概念成分', 'low'),
    'industry': ('m:90+t:2', _INDUSTRY_PREFIX, '行业分类', 'medium'),
}

# A 股代码段（与 minute_kline.base.to_prefixed_code 同口径）：B 股(200/900)、
# 港美股等一律排除——B 股/外股不属于 A 股产业链候选
_A_SHARE_PREFIXES = ('00', '30', '60', '68', '92', '43', '83', '87', '88')
_NON_TRADEABLE_SUFFIX = 'Ｂ'


class EastmoneyDelayConceptProvider(IIndustryChainProvider):
    """东财延迟域概念/行业成分：候选成员与交叉校验用，低/中置信（通道 ②）"""

    _NO_PROXY = {'http': None, 'https': None}
    _URL = 'https://push2delay.eastmoney.com/api/qt/clist/get'
    _TIMEOUT = 12
    _PAGE_SIZE = 100          # 实测上限：pz>100 无效
    _MAX_PAGES = 12           # 安全阀（504/100 = 6 页）
    # 单次返回的成员上限：东财概念板块动辄 400+ 只（如「军工」430），全量塞进
    # chain_scan 的候选列表会把响应撑爆且稀释信噪比——截断并**显式标注**截断，
    # 绝不静默丢数据（宁少不假：截断行数会写进 evidence 文本）
    _MEMBER_CAP = 120

    def __init__(self):
        self.last_error: Optional[str] = None
        self.last_channel: str = ''
        self.as_of: str = ''

    @property
    def name(self) -> str:
        return 'eastmoney_delay_concept'

    # ------------------------------------------------------------------ 取数

    @staticmethod
    def _cooldown(attempt: int):
        """限流退避（实测该域连续 11+ 次请求后会整段返回 rc=102，静置数秒即恢复）"""
        time.sleep(min(3.0, 1.0 * attempt))

    def _get(self, params: Dict, _attempts: int = 4) -> Dict:
        """单次 GET + 有界重试

        为什么必须重试（2026-09-11 实测）：该域在**突发连续请求**下会返回
        HTTP 200 + rc=0 但 `data:null`（同一 board_code 静置 1s 后重试即 200/正常）。
        把这种瞬时限流当成硬失败会让候选通道随机整块掉线（本 provider 首轮打样时
        BK0546/BK0428 就是这样被判失败的）。故对「连接类异常」与「data 为空」做
        3 次退避重试；重试耗尽才抛——空结果与失败仍严格分离。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, _attempts + 1):
            try:
                resp = requests.get(
                    self._URL,
                    params=params,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                        'Referer': 'https://quote.eastmoney.com/',
                    },
                    proxies=self._NO_PROXY,
                    timeout=self._TIMEOUT,
                )
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, dict):
                    raise ValueError('东财延迟域返回非 JSON 对象')
                if payload.get('data') is None:
                    # 瞬时限流特征：rc=0 却无 data —— 退避重试，不当硬失败
                    last_exc = ValueError(
                        f"返回空 data（rc={payload.get('rc')}）——疑似瞬时限流"
                    )
                    if attempt < _attempts:
                        self._cooldown(attempt)
                        continue
                    raise last_exc
                return payload
            except Exception as exc:      # 网络异常同样重试
                last_exc = exc
                if attempt < _attempts:
                    self._cooldown(attempt)
                    continue
                raise
        raise last_exc if last_exc else RuntimeError('东财延迟域请求失败')

    def _fetch_boards(self, kind: str) -> List[Dict]:
        """某类板块全清单（翻页取全，实测 pz 上限 100）"""
        selector = _BOARD_KINDS[kind][0]
        rows: List[Dict] = []
        total = None
        for pn in range(1, self._MAX_PAGES + 1):
            payload = self._get({
                'pn': pn, 'pz': self._PAGE_SIZE, 'po': 1, 'np': 1,
                'fltt': 2, 'invt': 2, 'fid': 'f3', 'fs': selector,
                'fields': 'f12,f14,f3',
            })
            data = payload.get('data')
            if not isinstance(data, dict):
                rc = payload.get('rc')
                raise ValueError(f'东财延迟域板块清单无 data（rc={rc}，rc=102 常见于经代理被拒）')
            diff = data.get('diff') or []
            if total is None:
                total = int(data.get('total') or 0)
            if not diff:
                break
            for item in diff:
                code = str(item.get('f12') or '').strip()
                board_name = str(item.get('f14') or '').strip()
                if not code or not board_name:
                    continue
                rows.append({
                    'code': code,
                    'name': board_name,
                    'change_pct': item.get('f3'),
                    'kind': kind,
                })
            # 2026-09-11（w-f436d4ea）审查修复：原写法 `len(rows) >= (total or 0)` 在
            # total=0（falsy）时恒为真 → **只取第 1 页就静默停止**（上游 total 缺失/
            # 为 0 时会静默截断清单，正是本项目反复出现的"静默截断"型隐患）。
            # 现改为：仅当 total 明确 >0 且已取够才提前结束；否则靠「本页不足一页」
            # 判定取完，兜底由 _MAX_PAGES 限制。
            if total and total > 0 and len(rows) >= total:
                break
            if len(diff) < self._PAGE_SIZE:
                break
            time.sleep(0.2)      # 翻页间隔：避免把该域打成限流（实测 0.2s 足以稳定取全）
        if not rows:
            raise ValueError(f'东财延迟域 {kind} 板块清单为空（total={total}）')
        return rows

    def _fetch_members(self, board_code: str) -> Tuple[List[Dict], int]:
        """板块成分（返回 (A 股成员行, 上游 total)）"""
        rows: List[Dict] = []
        reported_total = 0
        for pn in range(1, self._MAX_PAGES + 1):
            payload = self._get({
                'pn': pn, 'pz': self._PAGE_SIZE, 'po': 1, 'np': 1,
                'fltt': 2, 'invt': 2, 'fid': 'f3', 'fs': f'b:{board_code}',
                'fields': 'f12,f14,f3',
            })
            data = payload.get('data')
            if not isinstance(data, dict):
                raise ValueError(f'东财延迟域板块 {board_code} 成分无 data')
            diff = data.get('diff') or []
            if pn == 1:
                reported_total = int(data.get('total') or 0)
            if not diff:
                break
            for item in diff:
                code = str(item.get('f12') or '').strip()
                stock_name = str(item.get('f14') or '').strip()
                if not code or len(code) != 6 or not code.isdigit():
                    continue
                if not code.startswith(_A_SHARE_PREFIXES):
                    continue      # B 股（200/900）/ 其他非 A 段
                if stock_name.endswith(_NON_TRADEABLE_SUFFIX):
                    continue
                rows.append({
                    'symbol': code,
                    # 上游名称带全角空格填充（'南  玻Ａ'）→ 归一为单空格
                    'name': ' '.join(stock_name.split()),
                    'change_pct': item.get('f3'),
                })
            if len(rows) >= reported_total or len(diff) < self._PAGE_SIZE:
                break
            time.sleep(0.2)
        return rows, reported_total

    # -------------------------------------------------------------- 名称解析

    @staticmethod
    def _strip_prefix(key: str) -> Tuple[str, str]:
        if key.startswith(_CONCEPT_PREFIX):
            return key[len(_CONCEPT_PREFIX):], 'concept'
        if key.startswith(_INDUSTRY_PREFIX):
            return key[len(_INDUSTRY_PREFIX):], 'industry'
        return key, ''

    # 通用词/连接词板块：命中它们等于把半个市场当候选（如 '船舶制造概念' 28~430 只），
    # 只有在没有任何更具体板块命中时才降级使用
    _GENERIC_MARKERS = ('概念', '产业链', '风格', '昨日', '今日', '首板', '连板', '涨停', '跌停',
                        '含一字', '融资融券', '标准普尔', '富时罗素', 'MSCI', '举牌', '标的',
                        '预盈预增', '预亏预减', '破净股', '百元股', '次新股', '壳资源')
    # 跨源命名后缀：新浪叫「玻璃行业」/「电力行业」，东财叫「玻璃玻纤」/「电力」
    _NAME_SUFFIXES = ('行业', '板块', '业', '概念')

    @staticmethod
    def _is_generic(board_name: str) -> bool:
        return any(marker in board_name for marker in EastmoneyDelayConceptProvider._GENERIC_MARKERS)

    def _resolve_board(self, chain_id_or_name: str) -> List[Dict]:
        """按 板块代码 / 板块名 / 关键词 解析板块（返回**已排序**候选列表，可能为空）

        为什么要分档 + 打分（2026-09-11 实测教训）：候选通道 ① 的调用方传进来的
        sector_hint 是**新浪口径**（'玻璃行业'、'电力行业'、'船舶制造'、'航空航天'），
        东财板块命名不同（'玻璃玻纤'/'玻璃制造'、'电力'、'船舶制造'、'航空装备'）。
        只做「精确/包含」两级匹配会让东财通道在玻纤这类主流链上**永远空转**
        （实测 candidate_source 只有 akshare_concept，两通道退化成一条）。

        匹配档位（0 最高）：
          0 板块代码精确（BK0546 / bk0546）
          1 板块名精确等于原关键词
          2 去掉跨源后缀后的关键词**前缀**命中（'玻璃行业'→'玻璃' 命中 '玻璃玻纤'；
            前缀而非任意包含，避免 '玻璃基板' 这类同词根、不同行业的误命中）
          3 板块名精确等于去后缀关键词（'电力行业'→'电力'）
          4 板块名包含去后缀关键词
          5 反向包含（关键词含板块名，取更长者更具体）
        同档内：行业优先于概念，其次名称更短更具体者优先；
        通用词板块（概念/产业链/涨停板…）压到最低档。
        """
        key, forced_kind = self._strip_prefix(str(chain_id_or_name or '').strip())
        if not key:
            return []

        boards: List[Dict] = []
        kinds = [forced_kind] if forced_kind else ['industry', 'concept']
        for kind in kinds:
            try:
                boards.extend(self._fetch_boards(kind))
            except Exception as exc:
                self.last_error = f"东财延迟域 {kind} 板块清单取数失败: {type(exc).__name__}: {exc}"
                logger.warning(self.last_error)
                raise

        upper = key.upper()
        stems = [key]
        for suffix in self._NAME_SUFFIXES:
            if key.endswith(suffix) and len(key) > len(suffix):
                stem = key[: -len(suffix)]
                if stem not in stems:
                    stems.append(stem)
                break

        def _tier(board: Dict) -> Optional[int]:
            name = board['name']
            if board['code'].upper() == upper:
                return 0
            if name == key:
                return 1
            # 2026-09-11（w-f436d4ea）：原实现只对「去后缀后的词干」做前缀/包含匹配，
            # 于是**裸词**（无已知后缀可去，如 '玻璃'/'船舶'）匹配不到任何板块 →
            # 该通道静默返回空（通道退化，且不报错）。单测 test_industry_preferred_...
            # 暴露此口子（'玻璃' → []）。改为对原始关键词与词干一起参与匹配。
            for stem in stems:
                if stem != key and name.startswith(stem):
                    return 2
                if stem != key and name == stem:
                    return 3
                if stem == key and name.startswith(stem):
                    return 2
            for stem in stems:
                if stem in name:
                    return 4
            if name in key and len(name) >= 2:
                return 5
            return None

        scored: List[Tuple[Tuple, Dict]] = []
        for board in boards:
            tier = _tier(board)
            if tier is None:
                continue
            rank = (
                1 if self._is_generic(board['name']) else 0,   # 通用词压到最后
                0 if board['kind'] == 'industry' else 1,       # 行业口径更接近产业链
                tier,
                len(board['name']),                            # 更短＝更具体
                board['code'],
            )
            scored.append((rank, board))
        scored.sort(key=lambda item: item[0])
        return [board for _, board in scored]

    def _to_chain_row(self, board: Dict) -> Dict:
        kind = board['kind']
        prefix, evidence_kind, confidence = _BOARD_KINDS[kind][1:]
        stage = 'midstream'
        return {
            'chain_id': prefix + board['code'],
            'name': board['name'],
            'description': (
                f'东财{"概念" if kind == "concept" else "行业"}板块（低置信候选源，'
                '非策展产业链拓扑；板块代码 %s）' % board['code']
            ),
            'node_count': 1,
            'member_count': None,      # 板块清单接口不返回成员数，不臆造
            'updated_at': self.as_of,
            'source': self.name,
            'stale': False,
            'candidate': True,
            'board_code': board['code'],
            'board_kind': kind,
            '_evidence_kind': evidence_kind,
            '_confidence': confidence,
            '_stage': stage,
        }

    # -------------------------------------------------------------- 契约实现

    def list_chains(self) -> Optional[List[Dict]]:
        """候选链清单（东财概念 504 + 行业 496 板块）"""
        self.last_error = None
        self.as_of = datetime.now().isoformat(timespec='seconds')
        rows: List[Dict] = []
        errors: List[str] = []
        for kind in ('industry', 'concept'):
            try:
                boards = self._fetch_boards(kind)
            except Exception as exc:
                errors.append(f'{kind}: {type(exc).__name__}: {exc}')
                continue
            rows.extend(self._to_chain_row(b) for b in boards)
        self.last_channel = 'em_board_list'
        if not rows:
            self.last_error = '东财延迟域板块清单全部取数失败 —— ' + '; '.join(errors)
            logger.warning(self.last_error)
            return None
        if errors:
            # 部分成功：如实记在 last_error 供排障，但仍返回已取到的行（不静默丢通道）
            self.last_error = '部分板块类型取数失败 —— ' + '; '.join(errors)
        for row in rows:
            row.pop('_evidence_kind', None)
            row.pop('_confidence', None)
            row.pop('_stage', None)
        return rows

    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]:
        """按板块代码/名/关键词返回该板块成员（合成单节点，node_id=em_board:<code>）"""
        self.last_error = None
        self.as_of = datetime.now().isoformat(timespec='seconds')
        try:
            matched = self._resolve_board(chain_id_or_name)
        except Exception as exc:
            self.last_error = f"东财延迟域板块解析失败（{chain_id_or_name}）: {type(exc).__name__}: {exc}"
            logger.warning(self.last_error)
            return None

        if not matched:
            self.last_error = (
                f"东财概念/行业板块中没有 {chain_id_or_name!r} 对应板块"
                "（概念 504 个 / 行业 496 个，跨源命名可能不同）"
            )
            return None

        # _resolve_board 已按「档位 → 行业优先 → 更名短优先」排序，取首个
        board = matched[0]
        kind = board['kind']
        prefix, evidence_kind, confidence = _BOARD_KINDS[kind][1:]

        try:
            members, reported_total = self._fetch_members(board['code'])
        except Exception as exc:
            self.last_error = (
                f"东财延迟域板块 {board['name']}({board['code']}) 成分取数失败: "
                f"{type(exc).__name__}: {exc}"
            )
            logger.warning(self.last_error)
            return None

        self.last_channel = 'em_board_members'
        if not members:
            self.last_error = (
                f"东财延迟域板块 {board['name']}({board['code']}) 无 A 股成分"
                f"（上游 total={reported_total}，可能全为 B 股/非 A 段）"
            )
            return None

        board_label = f'东财{"概念" if kind == "concept" else "行业"}板块'
        truncated = len(members) > self._MEMBER_CAP
        evidence = (
            f'{board_label}「{board["name"]}」成分（{self.name}，push2delay.eastmoney.com '
            f'clist fs=b:{board["code"]}，上游 total={reported_total}，快照 {self.as_of}'
            + (f'，按涨跌幅截取前 {self._MEMBER_CAP} 只' if truncated else '')
            + '——板块成分非主营构成，仅作候选/交叉校验，不参与环节归位裁决'
        )
        if truncated:
            members = members[: self._MEMBER_CAP]
        return [{
            'chain_id': prefix + board['code'],
            'chain_name': board['name'],
            'node_id': 'em_board:' + board['code'],
            'node_name': board['name'],
            'stage': 'midstream',
            'upstream_of': [],
            'downstream_of': [],
            'rationale': (
                f'{board_label}（非策展拓扑）：仅作候选与交叉校验，不参与环节归位裁决'
            ),
            'keywords': [board['name'], board['code']],
            'members': [{
                'symbol': member['symbol'],
                'name': member['name'],
                'stage': 'midstream',
                'role': '',
                'exposure_ratio': None,
                'exposure_basis': '',
                'evidence': evidence,
                'evidence_kind': evidence_kind,
                'confidence': confidence,
                'source': self.name,
                'candidate': True,
                'change_pct': member['change_pct'],
            } for member in members],
            'source': self.name,
            'candidate': True,
            'board_code': board['code'],
            'board_kind': kind,
            'matched_total': reported_total,
            'members_returned': len(members),
            'members_truncated': truncated,
            'as_of': self.as_of,
        }]

    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]:
        """本通道不提供主营构成：[] = 该源无此类数据（非失败）"""
        self.last_error = None
        return []
