"""产业链图谱应用服务（RFC 015 §2.2，2026-09-11 REQ-cf627b P2）

应用层只做**编排**：
- 拓扑/成员/主营构成的取数与多源故障转移 → 注入的 IDataProviderManager（出站适配器侧）
- 领域规则（拓扑自校验/去重/证据冲突裁决/主营归位）→ domain.industry_chain.service
- 持久化 → 注入的 IIndustryChainRepository

依赖方向（ADR-001 红线）：本文件**不得出现任何 adapters 导入**（含函数内局部导入）。
具体实现的装配（组合根）在入站适配器 adapters/inbound/fastapi_app/routes/industry_chain_async.py。

响应契约（RFC §1.5.3 统一）：{success, data, source, attempted_sources, degraded, stale,
cross_source_conflict, as_of}；全源失败 → success=False（**显式失败**，绝不返回空清单冒充成功）。
"""
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.industry_chain.model import (
    CONFIDENCE_HIGH, ChainMember, EvidenceKind, IndustryChain,
)
from domain.industry_chain.service import IndustryChainService as IndustryChainDomainService

logger = logging.getLogger(__name__)

# 证据不足的判定：只有"策展/行业分类/概念成分"这些非财报口径算不足，主营构成/产品构成算足
_STRONG_EVIDENCE = {EvidenceKind.MAIN_BUSINESS.value, EvidenceKind.PRODUCT_PROFILE.value}

_service_instance: Optional['IndustryChainService'] = None


class IndustryChainService:
    """产业链用例编排：list / get / map_symbol / build / scan"""

    def __init__(self, manager=None, repository=None, domain: Optional[IndustryChainDomainService] = None):
        """
        Args:
            manager: IDataProviderManager（产业链 provider 子链路 + 实时行情）——组合根注入
            repository: IIndustryChainRepository（落库与查询）——组合根注入
            domain: 领域规则服务（纯计算，缺省新建）
        """
        self._manager = manager
        self._repository = repository
        self._domain = domain or IndustryChainDomainService()

    # ------------------------------------------------------------------ 依赖

    def _require_manager(self):
        if self._manager is None:
            raise RuntimeError(
                "IndustryChainService 需要注入 IDataProviderManager（组合根见 "
                "adapters/inbound/fastapi_app/routes/industry_chain_async.py）"
            )
        return self._manager

    def _require_repository(self):
        if self._repository is None:
            raise RuntimeError(
                "IndustryChainService 需要注入 IIndustryChainRepository（组合根见 "
                "adapters/inbound/fastapi_app/routes/industry_chain_async.py）"
            )
        return self._repository

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _envelope(data: Any, *, source: Optional[str] = None, attempted: Optional[List[str]] = None,
                  degraded: bool = False, stale: bool = False, error: Optional[str] = None,
                  conflicts: Optional[List[Dict]] = None, **extra) -> Dict:
        payload = {
            'success': error is None,
            'data': data,
            'source': source,
            'attempted_sources': attempted or [],
            'degraded': bool(degraded),
            'stale': bool(stale),
            'cross_source_conflict': conflicts or None,
            'as_of': datetime.now().isoformat(timespec='seconds'),
        }
        if error:
            payload['error'] = error
        payload.update(extra)
        return payload

    @staticmethod
    def _is_stale_source(source: Optional[str]) -> bool:
        return bool(source) and 'database' in str(source)

    def _symbol_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """实时行情（逐只取；失败不隐瞒，逐只记 error）"""
        manager = self._manager
        out: Dict[str, Dict] = {}
        if manager is None or not symbols:
            return out
        for symbol in symbols:
            try:
                resp = manager.get_quote(symbol)
            except Exception as exc:
                out[symbol] = {'error': f'{type(exc).__name__}: {exc}'}
                continue
            # 行情数据的真实形状是 **QuoteData dataclass**（不是 dict）——
            # 2026-09-11 实测踩坑：只判 isinstance(dict) 会把全部行情静默当成"获取失败"
            # （compare 同类教训：字段假设必须用真实响应验证，不能靠想象的数据形状）。
            raw = resp.get('data')
            if resp.get('success') and raw is not None:
                if is_dataclass(raw) and not isinstance(raw, type):
                    quote = asdict(raw)
                elif isinstance(raw, dict):
                    quote = raw
                else:
                    quote = dict(getattr(raw, '__dict__', {}))
                if not quote:
                    out[symbol] = {'error': '行情返回结构无法解析（既非 dataclass 也非 dict）'}
                    continue
                out[symbol] = {
                    'price': quote.get('price'),
                    # 字段名兼容两种命名（QuoteData 用 change_pct，dict 源可能用 changePct）
                    'change_pct': quote.get('change_pct', quote.get('changePct')),
                    'prev_close': quote.get('prev_close', quote.get('prevClose')),
                    'volume': quote.get('volume'),
                    'amount': quote.get('amount'),
                    'source': resp.get('source') or quote.get('source'),
                }
            else:
                out[symbol] = {'error': resp.get('error') or '行情获取失败'}
        return out

    def _chain_absent(self, name: str) -> bool:
        """该名字是否确实不在策展链清单里（用于把 404 与 502 分开）"""
        try:
            catalog = self._manager.list_industry_chains()
        except Exception:
            return False
        if not catalog.get('success'):
            return False
        key = str(name or '').strip()
        for row in catalog.get('data') or []:
            if key in (str(row.get('chain_id') or ''), str(row.get('name') or '')) or key in str(row.get('name') or ''):
                return False
        return True

    @staticmethod
    def _group_by_stage(members: List[ChainMember]) -> Dict[str, List[Dict]]:
        grouped: Dict[str, List[Dict]] = {stage: [] for stage in
                                          ('upstream', 'midstream', 'downstream', 'terminal')}
        for member in members:
            grouped[member.stage.value].append(member.to_dict())
        return grouped

    @staticmethod
    def _weak_evidence(members: List[ChainMember]) -> List[Dict]:
        """证据不足清单（只有策展/行业分类等弱证据的成员）——诚实暴露，不粉饰"""
        out = []
        for member in members:
            if member.evidence_kind not in _STRONG_EVIDENCE:
                out.append({
                    'symbol': member.symbol,
                    'name': member.name,
                    'node_id': member.node_id,
                    'stage': member.stage.value,
                    'evidence_kind': member.evidence_kind,
                    'confidence': member.confidence,
                    'reason': '缺少主营构成/产品构成证据，归位依据为%s' % (member.evidence_kind or '未知'),
                })
        return out

    # --------------------------------------------------------------- 用例 1

    def list_chains(self) -> Dict:
        """产业链清单（策展源 → DB 兜底；附落库状态与成员数）"""
        manager = self._require_manager()
        resp = manager.list_industry_chains()
        if not resp.get('success'):
            return self._envelope(
                None, source=None, attempted=resp.get('attempted_sources'),
                degraded=True, error=resp.get('error') or '产业链清单取数失败（全部源失败）',
                provider_errors=resp.get('provider_errors') or {},
            )
        rows = resp.get('data') or []
        source = resp.get('source')
        stored: Dict[str, Dict] = {}
        repo_error = None
        try:
            stored = {row['chain_id']: row for row in self._require_repository().list_chains()}
        except Exception as exc:
            repo_error = f'{type(exc).__name__}: {exc}'
            logger.warning('list_chains: 落库状态查询失败: %s', exc)

        chains = []
        for row in rows:
            built = stored.get(row['chain_id'])
            chains.append({
                'chain_id': row['chain_id'],
                'name': row['name'],
                'description': row.get('description') or '',
                'node_count': row.get('node_count') or 0,
                'curated_member_count': row.get('member_count') or 0,
                'stored_member_count': (built or {}).get('member_count', 0),
                'built': bool(built),
                'last_built_at': (built or {}).get('updated_at') or '',
                'curated_at': row.get('updated_at') or '',
                'curator': row.get('curator') or '',
                'source': row.get('source') or source,
            })
        # 库里存在但策展已删除的链（历史遗留）单独列出，不混进策展清单
        curated_ids = {row['chain_id'] for row in rows}
        orphans = [{
            'chain_id': cid, 'name': row.get('name'), 'stored_member_count': row.get('member_count', 0),
            'last_built_at': row.get('updated_at') or '', 'note': 'DB 中存在但策展 seed 已无此链',
        } for cid, row in stored.items() if cid not in curated_ids]

        return self._envelope(
            {'chains': chains, 'count': len(chains), 'db_only_chains': orphans},
            source=source, attempted=resp.get('attempted_sources'),
            stale=self._is_stale_source(source),
            repo_error=repo_error,
        )

    # --------------------------------------------------------------- 用例 2

    def get_chain(self, name: str) -> Dict:
        """单链全貌（按环节分组的成员 + 证据 + 冲突）。

        成员来源优先级：**上次 build 落库的成员**（含真实主营构成证据）→ 策展 seed 成员。
        本用例**不打上游网络**（只读），需要刷新证据请调 build_chain（POST）。
        """
        manager = self._require_manager()
        topo = manager.get_industry_chain_topology(name)
        if not topo.get('success'):
            # 区分「这条链不存在」（404）与「取数失败」（502）：若链清单能取到、而该名字不在其中，
            # 说明是查不到（authored 集里没有），不是上游故障。
            payload = self._envelope(
                None, source=None, attempted=topo.get('attempted_sources'), degraded=True,
                error=('产业链拓扑取数失败（人工策展为唯一权威源且不可降级）: %s'
                       % (topo.get('error') or '未找到该产业链')),
                provider_errors=topo.get('provider_errors') or {},
                hint='拓扑必须人工策展（RFC §2.3/§7），缺失即失败；请核对 seed 或 chain_id',
            )
            payload['not_found'] = self._chain_absent(name)
            return payload
        node_rows = topo.get('data') or []
        chain_id = node_rows[0].get('chain_id')
        member_rows = node_rows
        member_source = topo.get('source')
        built_at = ''
        stale = False

        repo = self._require_repository()
        try:
            stored = repo.get_chain(chain_id)
        except Exception as exc:
            stored = None
            logger.warning('get_chain: DB 读取失败，退回策展成员: %s', exc)
        if stored and stored.get('members'):
            # 库成员 + 策展的环节元信息（keywords/rationale 以策展为准）
            by_node: Dict[str, Dict] = {}
            for node in node_rows:
                copy = dict(node)
                copy['members'] = []
                by_node[node['node_id']] = copy
            stored_nodes = {n['node_id']: n for n in stored.get('nodes') or []}
            for node_id, node in by_node.items():
                if node_id in stored_nodes:
                    node['upstream_of'] = stored_nodes[node_id].get('upstream_of') or node['upstream_of']
                    node['downstream_of'] = stored_nodes[node_id].get('downstream_of') or node['downstream_of']
            for member in stored['members']:
                node = by_node.get(member.get('node_id'))
                if node is None:
                    continue
                node['members'].append({
                    'symbol': member.get('symbol'),
                    'name': member.get('name'),
                    'stage': member.get('stage'),
                    'role': member.get('role'),
                    'exposure_ratio': member.get('exposure_ratio'),
                    'exposure_basis': member.get('exposure_basis'),
                    'exposure_as_of': member.get('exposure_as_of'),
                    'evidence': member.get('evidence'),
                    'evidence_kind': member.get('evidence_kind'),
                    'confidence': member.get('confidence'),
                    'source': member.get('source'),
                })
            member_rows = list(by_node.values())
            member_source = 'stored_graph'
            built_at = stored.get('updated_at') or ''

        chain, conflicts, multi_stage = self._domain.build_chain(
            chain_id=chain_id,
            name=node_rows[0].get('chain_name') or name,
            node_rows=member_rows,
            description=node_rows[0].get('description') or '',
            rationale=node_rows[0].get('chain_rationale') or '',
            source=member_source,
            as_of=built_at or datetime.now().isoformat(timespec='seconds'),
        )
        data = chain.to_dict()
        data['nodes'] = [node.to_dict() for node in chain.nodes]
        unresolved = [c.to_dict() for c in conflicts if not c.resolved]

        return self._envelope(
            data,
            source=member_source,
            attempted=topo.get('attempted_sources'),
            stale=stale,
            conflicts=unresolved or None,
            evidence_conflicts=[c.to_dict() for c in conflicts],
            multi_stage=multi_stage,
            weak_evidence=self._weak_evidence(chain.members),
            built=bool(built_at),
            last_built_at=built_at,
            node_rows_used=len(member_rows),
        )

    # --------------------------------------------------------------- 用例 3

    def map_symbol(self, symbol: str) -> Dict:
        """个股 → 所属链/环节/主营占比（链式扫描的关键查询）

        两条腿并用，互为补充：
        1) 落库图谱（build_chain 的结果，含真实主营构成证据）
        2) **实时主营构成**（东财 F10 → 同花顺 F10 → DB 兜底）：即使该标的还没入过链，
           也能给出"它靠什么赚钱"，供人工判断该归哪个环节
        """
        manager = self._require_manager()
        repo = self._require_repository()
        code = str(symbol or '').strip()

        hits: List[Dict] = []
        stored_error = None
        try:
            hits = repo.get_chain_by_symbol(code)
        except Exception as exc:
            stored_error = f'{type(exc).__name__}: {exc}'
            logger.warning('map_symbol: DB 查询失败: %s', exc)

        if not hits:
            # 图谱尚未 build 时也能答：直接扫策展 seed 的成员（低频，无网络调用）
            curated = manager.list_industry_chains()
            if curated.get('success'):
                for chain_row in curated.get('data') or []:
                    chain_rows = manager.get_industry_chain_topology(chain_row['chain_id'])
                    if not chain_rows.get('success'):
                        continue
                    for node in chain_rows.get('data') or []:
                        for member in node.get('members') or []:
                            if str(member.get('symbol')) == code:
                                hits.append({
                                    'chain_id': node.get('chain_id'),
                                    'chain_name': node.get('chain_name'),
                                    'node_id': node.get('node_id'),
                                    'node_name': node.get('node_name'),
                                    'stage': node.get('stage'),
                                    'symbol': code,
                                    'name': member.get('name'),
                                    'role': member.get('role'),
                                    'exposure_ratio': member.get('exposure_ratio'),
                                    'exposure_basis': member.get('exposure_basis'),
                                    'exposure_as_of': member.get('exposure_as_of'),
                                    'evidence': member.get('evidence'),
                                    'evidence_kind': member.get('evidence_kind'),
                                    'confidence': member.get('confidence'),
                                    'source': member.get('source'),
                                    'updated_at': node.get('curated_at') or '',
                                })

        revenue = manager.get_industry_chain_revenue(code)
        revenue_rows = revenue.get('data') or []
        revenue_rows = [row for row in revenue_rows
                        if str(row.get('classification') or '') != '经营范围']
        revenue_rows.sort(key=lambda row: (str(row.get('report_date') or ''), row.get('ratio') or -1),
                           reverse=True)
        symbol_name = next((hit.get('name') for hit in hits if hit.get('name')), '')
        if not symbol_name:
            symbol_name = next((row.get('name') for row in revenue_rows if row.get('name')), '')

        data = {
            'symbol': code,
            'name': symbol_name,
            'chains': [{
                'chain_id': hit.get('chain_id'),
                'chain_name': hit.get('chain_name'),
                'node_id': hit.get('node_id'),
                'node_name': hit.get('node_name'),
                'stage': hit.get('stage'),
                'role': hit.get('role'),
                'exposure': ({
                    'ratio': hit.get('exposure_ratio'),
                    'pct': round((hit.get('exposure_ratio') or 0) * 100, 2),
                    'basis': hit.get('exposure_basis'),
                    'as_of': hit.get('exposure_as_of'),
                } if hit.get('exposure_ratio') is not None else None),
                'evidence': hit.get('evidence'),
                'evidence_kind': hit.get('evidence_kind'),
                'confidence': hit.get('confidence'),
                'source': hit.get('source'),
                'updated_at': hit.get('updated_at') or '',
            } for hit in hits],
            'chain_count': len({hit.get('chain_id') for hit in hits}),
            'revenue_exposure': {
                'rows': revenue_rows[:40],
                'source': revenue.get('source'),
                'attempted_sources': revenue.get('attempted_sources') or [],
                'error': revenue.get('error'),
                'stale': self._is_stale_source(revenue.get('source')),
            },
            'stored_graph_error': stored_error,
            'note': ('chains 为空 = 该标的未在任何已策展产业链中（或图谱未 build）；'
                     'revenue_exposure 单独给出"它靠什么赚钱"，可用于人工归位判断'),
        }
        return self._envelope(
            data,
            source=(revenue.get('source') or ('stored_graph' if hits else None)),
            attempted=revenue.get('attempted_sources'),
            degraded=not revenue.get('success'),
            stale=self._is_stale_source(revenue.get('source')),
            conflicts=[],
            revenue_error=revenue.get('error'),
        )

    # --------------------------------------------------------------- 用例 4

    def build_chain(self, name: str, persist: bool = True) -> Dict:
        """编排：策展拓扑 → 主营构成/产品构成归位 → 领域规则（去重+冲突）→ 落库

        证据链：curated（拓扑与代表标的） + eastmoney_revenue/ths_revenue（归位硬证据）
               + 领域裁决（同标的跨环节时以主营构成为准）
        """
        manager = self._require_manager()
        topo = manager.get_industry_chain_topology(name)
        if not topo.get('success'):
            payload = self._envelope(
                None, source=None, attempted=topo.get('attempted_sources'), degraded=True,
                error='产业链拓扑取数失败（人工策展不可降级）: %s' % (topo.get('error') or '未找到'),
                provider_errors=topo.get('provider_errors') or {},
            )
            payload['not_found'] = self._chain_absent(name)
            return payload

        node_rows = topo.get('data') or []
        chain_id = node_rows[0].get('chain_id')
        nodes = self._domain.parse_node_rows(node_rows)
        curated_members = self._domain.parse_member_rows(node_rows, default_source=topo.get('source') or 'curated')

        symbols: List[str] = []
        meta: Dict[str, Dict] = {}
        for member in curated_members:
            if member.symbol not in symbols:
                symbols.append(member.symbol)
            meta.setdefault(member.symbol, {'name': member.name, 'role': member.role})

        enriched: List[ChainMember] = []
        evidence_report: List[Dict] = []
        revenue_sources: List[str] = []
        attempted: List[str] = []

        for symbol in symbols:
            revenue = manager.get_industry_chain_revenue(symbol)
            attempted.extend(revenue.get('attempted_sources') or [])
            rows = revenue.get('data') or []
            if revenue.get('source'):
                revenue_sources.append(revenue['source'])
            name_ = meta.get(symbol, {}).get('name') or ''
            role = meta.get(symbol, {}).get('role') or ''

            strong, unmatched_strong = self._domain.attribute_by_exposure(
                symbol, name_, rows, nodes, source=revenue.get('source') or '', role=role,
            )
            weak: List[ChainMember] = []
            unmatched_weak: List[Dict] = []
            if not strong and rows:
                weak, unmatched_weak = self._domain.attribute_by_profile(
                    symbol, name_, rows, nodes, source=revenue.get('source') or '', role=role,
                )
            enriched.extend(strong or weak)

            evidence_report.append({
                'symbol': symbol,
                'name': name_,
                'revenue_source': revenue.get('source'),
                'revenue_error': revenue.get('error'),
                'stale': self._is_stale_source(revenue.get('source')),
                'attributed_by': (EvidenceKind.MAIN_BUSINESS.value if strong else
                                  (EvidenceKind.PRODUCT_PROFILE.value if weak else '策展/无')),
                'attributed_nodes': [m.node_id for m in (strong or weak)],
                'unmatched_items': (unmatched_strong or unmatched_weak)[:8],
            })

        chain, conflicts, multi_stage = self._domain.build_chain(
            chain_id=chain_id,
            name=node_rows[0].get('chain_name') or name,
            node_rows=node_rows,
            description=node_rows[0].get('description') or '',
            rationale=node_rows[0].get('chain_rationale') or '',
            source=topo.get('source') or 'curated',
            as_of=datetime.now().isoformat(timespec='seconds'),
            extra_members=enriched,
        )

        persist_result: Optional[Dict] = None
        persist_error = None
        if persist:
            chain_payload = {
                'chain_id': chain.chain_id,
                'name': chain.name,
                'description': chain.description,
                'rationale': chain.rationale,
                'curator': node_rows[0].get('curator') or '',
                'source': chain.source,
                'nodes': [{
                    'node_id': node.node_id,
                    'name': node.name,
                    'stage': node.stage.value,
                    'upstream_of': node.upstream_of,
                    'downstream_of': node.downstream_of,
                    'keywords': node.keywords,
                    'rationale': node.rationale,
                } for node in chain.nodes],
                'members': [{
                    'symbol': member.symbol,
                    'name': member.name,
                    'node_id': member.node_id,
                    'stage': member.stage.value,
                    'role': member.role,
                    'exposure_ratio': member.exposure.ratio if member.exposure else None,
                    'exposure_basis': member.exposure.basis if member.exposure else '',
                    'exposure_as_of': member.exposure.as_of if member.exposure else '',
                    'evidence': member.evidence,
                    'evidence_kind': member.evidence_kind,
                    'confidence': member.confidence,
                    'source': member.source,
                    'conflict': member.conflict,
                } for member in chain.members],
            }
            try:
                persist_result = self._require_repository().upsert_chain(chain_payload)
            except Exception as exc:
                persist_error = f'{type(exc).__name__}: {exc}'
                logger.error('build_chain 落库失败 %s: %s', chain_id, exc)

        data = chain.to_dict()
        data['nodes'] = [node.to_dict() for node in chain.nodes]
        unresolved = [c.to_dict() for c in conflicts if not c.resolved]
        strong_count = sum(1 for item in evidence_report if item['attributed_by'] == EvidenceKind.MAIN_BUSINESS.value)
        weak_count = sum(1 for item in evidence_report if item['attributed_by'] == EvidenceKind.PRODUCT_PROFILE.value)

        return self._envelope(
            data,
            source=topo.get('source'),
            attempted=sorted(set(attempted)),
            stale=any(item['stale'] for item in evidence_report),
            conflicts=unresolved or None,
            evidence_conflicts=[c.to_dict() for c in conflicts],
            multi_stage=multi_stage,
            weak_evidence=self._weak_evidence(chain.members),
            evidence_report=evidence_report,
            attribution_summary={
                'symbols_total': len(symbols),
                'by_main_business': strong_count,
                'by_product_profile': weak_count,
                'curated_only': len(symbols) - strong_count - weak_count,
                'revenue_sources': sorted(set(revenue_sources)),
            },
            persisted=bool(persist_result),
            persist_result=persist_result,
            persist_error=persist_error,
            hint=None if persist_error is None else '落库失败：图谱未更新，请查 persist_error',
        )

    # --------------------------------------------------------------- 用例 5

    def chain_scan(self, name: str, include_quotes: bool = True,
                   include_candidates: bool = True) -> Dict:
        """链式扫描：按环节分组的成员 + 实时行情 + 低置信候选（可挂行情/资金流）

        与 get_chain 的区别：本用例面向"扫"——成员按环节位置分组、挂当前价与涨跌幅，
        并把**行业板块候选**（低置信，未入链）单列，供人工判断是否有遗漏标的。
        """
        base = self.get_chain(name)
        if not base.get('success'):
            return base
        data = base['data']
        members = data.get('by_stage') or {}

        symbols: List[str] = []
        for stage_members in members.values():
            for member in stage_members:
                if member.get('symbol') and member['symbol'] not in symbols:
                    symbols.append(member['symbol'])

        quotes: Dict[str, Dict] = {}
        if include_quotes:
            quotes = self._symbol_quotes(symbols)

        by_stage: Dict[str, List[Dict]] = {}
        for stage, stage_members in members.items():
            enriched_members = []
            for member in stage_members:
                item = dict(member)
                quote = quotes.get(member.get('symbol') or '')
                item['quote'] = quote
                enriched_members.append(item)
            by_stage[stage] = enriched_members

        candidates: List[Dict] = []
        candidate_source = None
        candidate_error = None
        if include_candidates:
            concept = self._manager.get_industry_chain_candidates(self._sector_hint(data))
            candidate_source = concept.get('source')
            if concept.get('success'):
                known = set(symbols)
                for node in concept.get('data') or []:
                    for member in node.get('members') or []:
                        if member.get('symbol') in known:
                            continue
                        candidates.append({
                            'symbol': member.get('symbol'),
                            'name': member.get('name'),
                            'sector': node.get('node_name'),
                            'evidence': member.get('evidence'),
                            'evidence_kind': member.get('evidence_kind'),
                            'confidence': member.get('confidence'),
                            'source': member.get('source'),
                            'candidate': True,
                        })
            else:
                candidate_error = concept.get('error')

        quote_errors = {symbol: info.get('error') for symbol, info in quotes.items() if info.get('error')}
        return self._envelope(
            {
                'chain_id': data.get('chain_id'),
                'name': data.get('name'),
                'rationale': data.get('rationale'),
                'by_stage': by_stage,
                'nodes': data.get('nodes'),
                'symbols': symbols,
                'candidates': candidates,
                'candidate_source': candidate_source,
                'candidate_error': candidate_error,
                'evidence_conflicts': base.get('evidence_conflicts'),
                'multi_stage': base.get('multi_stage'),
                'weak_evidence': base.get('weak_evidence'),
                'built': base.get('built'),
                'last_built_at': base.get('last_built_at'),
            },
            source=base.get('source'),
            attempted=base.get('attempted_sources'),
            stale=base.get('stale'),
            conflicts=base.get('cross_source_conflict'),
            quote_errors=quote_errors or None,
        )

    @staticmethod
    def _sector_hint(chain_data: Dict) -> str:
        """从链名推出行业板块关键词（候选源用；新浪行业板块命名与产业链名不完全一致）"""
        name = str(chain_data.get('name') or '')
        for alias, hint in (
            ('玻纤', '玻璃行业'), ('电力', '电力行业'), ('半导体', '半导体'),
            ('光伏', '光伏'), ('锂电', '锂电池'), ('新能源车', '汽车'),
            ('造船', '船舶制造'), ('航运', '水运'), ('军工', '航空航天'), ('航空', '航空航天'),
            ('化工', '化工行业'),
        ):
            if alias in name or alias in str(chain_data.get('chain_id') or ''):
                return hint
        return name


def get_industry_chain_service() -> Optional[IndustryChainService]:
    """进程级单例（组合根在入站适配器装配后调用 set_industry_chain_service）"""
    return _service_instance


def set_industry_chain_service(service: Optional[IndustryChainService]) -> None:
    global _service_instance
    _service_instance = service
