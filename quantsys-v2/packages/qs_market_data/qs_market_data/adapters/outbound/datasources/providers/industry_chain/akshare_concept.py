"""概念/行业成分 provider（RFC 015 §2.3 优先级 3：**低置信候选与补全**）

通道：新浪行业分类（经 akshare `stock_sector_spot` + `stock_sector_detail`）。
它**不是**成员归位的硬证据——只用于：①候选发现（seed 未覆盖的同类标的）；②交叉校验
（与主营构成冲突时以主营构成为准，RFC §2.3）。

## 真实响应打样（2026-09-11 本机实测）

`ak.stock_sector_spot(indicator='新浪行业')` → 实测 0.1s / 49 行，真实列名：
  label('new_blhy') / 板块('玻璃行业') / 公司家数(19) / 平均价格 / 涨跌额 / 涨跌幅 /
  总成交量 / 总成交额 / 股票代码 / 个股-涨跌幅 / 个股-当前价 / 个股-涨跌额 / 股票名称
`ak.stock_sector_detail(sector='new_blhy')` → 实测 0.2s / 19 行，真实列名：
  symbol('sh600176') / code('600176') / name('中国巨石') / trade / pricechange / changepercent / ...
`ak.stock_sector_detail(sector='new_dlhy')` → 实测 62 行（电力行业）——通道稳定可用。

## 打样**失败**的通道（如实记录，均未注册）

| 通道 | 实测结果 | 结论 |
|---|---|---|
| 东财概念/行业成分 `ak.stock_board_concept_name_em` / `stock_board_industry_cons_em` | ProxyError: 17.push2.eastmoney.com 经本机代理被拒（多次重试均失败） | 不可用 |
| 东财 push2 直连 `push2.eastmoney.com/api/qt/clist/get` | 3 次重试全部 ProxyError（更早一次成功过 → 不稳定） | 不稳定，不注册 |
| 同花顺概念成分 `q.10jqka.com.cn/gn/detail/.../301558/` | HTTP 401（需 JS token） | 不可用 |
| 富途概念成分 `ak.stock_concept_cons_futu` | KeyError（概念名不在其字典内） | 未采用 |
| 巨潮行业分类 `ak.stock_industry_category_cninfo` | 200 但只返回**分类树**，无个股归属 | 无个股维度，未采用 |

⚠️ 诚实标注：本 provider 的**上游实为新浪**（行业分类），不是"东财概念"。文件名为交付清单
约定（akshare_concept.py），证据类型写 `行业分类`、置信 medium，**绝不冒充**主营构成。
"""
import logging
from typing import Dict, List, Optional

from domain.industry_chain.ports.IIndustryChainProvider import IIndustryChainProvider

logger = logging.getLogger(__name__)

_SECTOR_PREFIX = 'sina_sector:'


class AkshareConceptProvider(IIndustryChainProvider):
    """新浪行业成分（经 akshare）：候选成员与交叉校验用，低/中置信

    返回值的四态契约（2026-09-11 全仓统一，manager._try_providers 消费）

    | 返回 | last_error | last_note | 语义 |
    |---|---|---|---|
    | 非空行列表 | None | '' | 取到数据 |
    | **[]** | **None** | **<诊断文本>** | **健康无数据**：如「新浪行业里没有这个板块名」
（跨源命名差异）、该板块无可用成分。manager 会继续降级下一通道 |
    | None | <原因> | '' | **真故障**：板块清单/成分取数失败、异常 |
    | None | 空 | 空 | ⚠️ 禁止（manager 两头都判不了，会被记成"非空但无效"） |

    ⚠️ provider 是**长生命周期单例**：每个入口都要重置 last_error / last_note /
    last_channel，否则上一次调用的诊断会挂到下一次调用上（"没这个板块"被当成取数失败
    会打掉健康分与熔断余量）。
    """

    def __init__(self):
        self.last_error: Optional[str] = None
        self.last_note: str = ''
        self.last_channel: str = ''

    @property
    def name(self) -> str:
        return 'akshare_concept'

    # ------------------------------------------------------------------ 数据

    @staticmethod
    def _akshare():
        import akshare  # 局部导入：避免 manager 导入期就拉起重库
        return akshare

    def _sector_list(self) -> List[Dict]:
        """新浪行业板块清单（label / 板块名 / 家数）"""
        ak = self._akshare()
        frame = ak.stock_sector_spot(indicator='新浪行业')
        rows: List[Dict] = []
        for _, item in frame.iterrows():
            label = str(item.get('label') or '').strip()
            if not label:
                continue
            rows.append({
                'label': label,
                'sector': str(item.get('板块') or '').strip(),
                'company_count': int(item.get('公司家数') or 0),
            })
        return rows

    def _sector_members(self, label: str) -> List[Dict]:
        """板块成员（symbol 带交易所前缀、code、name）"""
        ak = self._akshare()
        frame = ak.stock_sector_detail(sector=label)
        rows: List[Dict] = []
        for _, item in frame.iterrows():
            code = str(item.get('code') or '').strip()
            if not code:
                continue
            rows.append({
                'symbol': code,
                'name': str(item.get('name') or '').strip(),
                'prefixed': str(item.get('symbol') or '').strip(),
                'price': item.get('trade'),
                'change_pct': item.get('changepercent'),
            })
        return rows

    # -------------------------------------------------------------- 契约实现

    def list_chains(self) -> Optional[List[Dict]]:
        """候选链清单（新浪行业板块）。注意：这些是**行业板块**，不是策展产业链拓扑"""
        self.last_error = None
        self.last_note = ''
        self.last_channel = ''
        try:
            sectors = self._sector_list()
        except Exception as exc:
            self.last_error = f"新浪行业清单取数失败: {type(exc).__name__}: {exc}"
            logger.warning(self.last_error)
            return None
        self.last_channel = 'sina_sector_list'
        return [{
            'chain_id': _SECTOR_PREFIX + row['label'],
            'name': row['sector'],
            'description': '新浪行业板块（低置信候选源，非策展产业链拓扑）',
            'node_count': 1,
            'member_count': row['company_count'],
            'updated_at': '',
            'source': self.name,
            'stale': False,
            'candidate': True,
        } for row in sectors]

    def get_chain(self, chain_id_or_name: str) -> Optional[List[Dict]]:
        """按板块名/label 返回该板块成员（合成单节点，node_id=sector:<label>）

        四态（2026-09-11，与 eastmoney_delay_concept 同口径）：命中→节点行；
        **该源没有这个板块 / 板块无可用成分 → [] + last_note**（健康无数据，不得冒充
        故障）；板块清单或成分取数失败 → None + last_error。
        """
        self.last_error = None
        self.last_note = ''
        self.last_channel = ''
        key = str(chain_id_or_name or '').strip()
        key = key[len(_SECTOR_PREFIX):] if key.startswith(_SECTOR_PREFIX) else key
        try:
            sectors = self._sector_list()
        except Exception as exc:
            self.last_error = f"新浪行业清单取数失败: {type(exc).__name__}: {exc}"
            logger.warning(self.last_error)
            return None

        matched = None
        for row in sectors:
            if key == row['label'] or key == row['sector']:
                matched = row
                break
        if matched is None:
            for row in sectors:
                if key and key in row['sector']:
                    matched = row
                    break
        if matched is None:
            # 健康无数据（2026-09-11，w-f436d4ea）：上游清单取回来了、回答得好好的，
            # 只是它的分类体系里没有这个名字（跨源命名差异，如策展叫"造船"、新浪叫
            # "船舶制造"）。判成真故障会打掉本通道健康分、把候选通道①挤出竞争，
            # 正是 RFC 015 §1.5.1 禁止的「多源退化成单源」。
            self.last_note = (
                f"新浪行业中没有 {chain_id_or_name!r} 对应板块（可用: "
                f"{', '.join(r['sector'] for r in sectors[:30])} ...）"
            )
            return []

        try:
            members = self._sector_members(matched['label'])
        except Exception as exc:
            self.last_error = f"新浪行业成分取数失败（{matched['sector']}）: {type(exc).__name__}: {exc}"
            logger.warning(self.last_error)
            return None
        if not members:
            # 健康无数据：板块在、成分接口也正常返回，只是没有可用成分——不是取数故障。
            # 返回「零成员节点」会被下游当成有效节点，故与兄弟通道同口径返回 [] + last_note。
            self.last_note = f"新浪行业板块 {matched['sector']}({matched['label']}) 无可用成分"
            return []
        self.last_channel = 'sina_sector_detail'
        return [{
            'chain_id': _SECTOR_PREFIX + matched['label'],
            'chain_name': matched['sector'],
            'node_id': 'sector:' + matched['label'],
            'node_name': matched['sector'],
            'stage': 'midstream',
            'upstream_of': [],
            'downstream_of': [],
            'rationale': '新浪行业板块（非策展拓扑）：仅作候选与交叉校验，不参与环节归位裁决',
            'keywords': [matched['sector']],
            'members': [{
                'symbol': member['symbol'],
                'name': member['name'],
                'stage': 'midstream',
                'role': '',
                'exposure_ratio': None,
                'exposure_basis': '',
                'evidence': '新浪行业分类「%s」成分（akshare stock_sector_detail，抓取时点见响应 as_of）'
                            % matched['sector'],
                'evidence_kind': '行业分类',
                'confidence': 'medium',
                'source': self.name,
                'candidate': True,
            } for member in members],
            'source': self.name,
            'candidate': True,
        }]

    def get_revenue_exposure(self, symbol: str) -> Optional[List[Dict]]:
        """本通道不提供主营构成：[] = 该源无此类数据（非失败）"""
        self.last_error = None
        # 结构性缺能力（不是取数失败，也不是「这只票没有」）：明确写进 last_note，
        # 使 manager 的 empty_sources 诊断能如实说明「为什么这个源没有数据」。
        self.last_note = (
            '新浪行业分类源不提供主营构成（结构性：该接口只有行业归属，无营收占比），'
            f'故 {symbol} 无数据可返回——不是取数失败'
        )
        return []
