"""产业链领域服务：成员归位 / 去重 / 证据冲突检测（RFC 015 §2.1）

严格的领域层：**零 I/O、零外部依赖**（不 import requests/akshare/ORM/adapters），
输入是 provider 的原始行（dict），输出是领域模型 + 冲突记录。可独立单测。

三条规则（可质疑，故写清判据）：

R1 拓扑自校验（validate_topology）
   seed 里每个节点同时声明 downstream_of 与 upstream_of（冗余声明）。冗余的用途是
   **互相校验**：A 说下游有 B，则 B 必须说上游有 A；引用不存在的 node_id 直接失败。
   fail-loud —— 拓扑错了会让整条链的归位全错，不能静默。

R2 成员去重（dedupe）
   同一 (symbol, node_id) 只保留**证据优先级最高**的一条；
   同一 symbol 在**同一 stage** 下若被多个来源塞进不同 node_id，只保留最高证据的那条
   （避免"概念成分"把票塞到同一环节位置的其他节点，造成同一环节重复计数）。

R3 证据冲突裁决（resolve_conflicts）
   - 同一 symbol 落到**不同 stage** 才叫冲突；同一 stage 多节点是合法事实（中国巨石同时做
     玻纤纱与电子布）。
   - 冲突时**以主营构成为准**（RFC §2.3）：保留主营构成支持的 stage，丢弃其他来源的归位，
     并把全部主张写入 EvidenceConflict（不静默取其一，供人工复核）。
   - 若全部主张来自**同一来源同一证据类型**（例如主营构成自身横跨上下游，如通威股份
     硅料+电池组件），这不是"来源冲突"而是"公司跨环节经营"：全部保留，记入 multi_stage，
     并按占比最高者给出 primary 环节。
   - 若最高优先级证据出现**并列不同 stage**（如两条策展互相矛盾）→ resolved=False，
     全部保留 + 明确标注"需人工复核"（宁可暴露矛盾，不可假装已裁决）。
"""
import logging
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from domain.industry_chain.model import (
    CONFIDENCE_ORDER, ChainMember, ChainNode, ChainStage, EvidenceConflict,
    EvidenceKind, IndustryChain, RevenueExposure,
)

logger = logging.getLogger(__name__)

# 按地区分类不能用于归位（地区不是环节）
_NON_ATTRIBUTION_CLASSIFICATIONS = ('按地区分类', '按地区', '地区分类')


def _match_node(item: str, nodes: Sequence[ChainNode]) -> Optional[ChainNode]:
    """主营构成条目 → 环节节点（**最长关键词优先**）

    实测教训（2026-09-11，中国巨石/宏和科技打样）：
      条目「电子级玻璃纤维布」同时命中上游「玻纤纱」节点的宽关键词「玻璃纤维」和
      「电子布」节点的「电子级玻璃纤维」。按声明顺序取首个命中会把电子布标的归到玻纤纱，
      这是**静默错位**（比报错危险）。故改为最长匹配：命中的关键词越长越具体，优先级越高；
      等长时按节点声明顺序（seed 顺序即人工判断顺序）。
    """
    best: Optional[ChainNode] = None
    best_len = 0
    for node in nodes:
        for keyword in (node.keywords or [node.name]):
            if keyword and keyword in item and len(keyword) > best_len:
                best, best_len = node, len(keyword)
    return best


def _to_ratio(value) -> Optional[float]:
    """上游占比 → 0-1 小数（百分数自动归一；None/NaN → None，绝不静默变 0）

    2026-09-11 分红事故的同型风险：源给 97.3 而被当成 0.973 读成 97.3%，或给 NaN 被当成 0。
    归一化只做一件事：>1 且 <=100 视为百分数除以 100；其余越界交给 RevenueExposure 抛错。
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    if number <= 0:
        # 实测（2026-09-11，中远海控 601919）：东财主营构成含「公司内各业务部间相互抵销 -1.49%」
        # 这类**负占比**。它不是业务占比，若当占比用会直接触发 RevenueExposure 越界报错，
        # 或（更糟）被当成有效证据。故显式归零为 None，由调用方计入 unmatched 并说明原因。
        return None
    return number


def _as_exposure(row: Dict) -> Optional[RevenueExposure]:
    ratio = _to_ratio(row.get('exposure_ratio', row.get('ratio')))
    if ratio is None:
        return None
    return RevenueExposure(
        ratio=ratio,
        basis=str(row.get('exposure_basis') or row.get('basis') or ''),
        as_of=str(row.get('exposure_as_of') or row.get('as_of') or ''),
    )


class IndustryChainService:
    """产业链领域规则（纯计算）"""

    # ------------------------------------------------------------------ 拓扑

    @staticmethod
    def validate_topology(nodes: Sequence[ChainNode]) -> None:
        """R1：上下游声明对称性 + 引用完整性（不通过直接抛 ValueError）"""
        ids = {node.node_id for node in nodes}
        if len(ids) != len(nodes):
            dupes = [n for n in ids if [x.node_id for x in nodes].count(n) > 1]
            raise ValueError(f"节点 node_id 重复: {dupes}")
        for node in nodes:
            for target in node.downstream_of:
                if target not in ids:
                    raise ValueError(f"节点 {node.node_id}.downstream_of 引用了不存在的 node_id: {target}")
                other = next(n for n in nodes if n.node_id == target)
                if node.node_id not in other.upstream_of:
                    raise ValueError(
                        f"拓扑不对称：{node.node_id}.downstream_of 含 {target}，"
                        f"但 {target}.upstream_of 未反向声明 {node.node_id}"
                    )
            for source in node.upstream_of:
                if source not in ids:
                    raise ValueError(f"节点 {node.node_id}.upstream_of 引用了不存在的 node_id: {source}")
                other = next(n for n in nodes if n.node_id == source)
                if node.node_id not in other.downstream_of:
                    raise ValueError(
                        f"拓扑不对称：{node.node_id}.upstream_of 含 {source}，"
                        f"但 {source}.downstream_of 未反向声明 {node.node_id}"
                    )

    @staticmethod
    def chain_topology_order(nodes: Sequence[ChainNode]) -> List[str]:
        """按上下游关系给出 node_id 的拓扑序（同层按上游→下游 stage 排）；有环则按原序返回

        仅用于展示顺序（不让环路静默通过：有环时 warning 并保留原序）。
        """
        stage_rank = {
            ChainStage.UPSTREAM: 0, ChainStage.MIDSTREAM: 1,
            ChainStage.DOWNSTREAM: 2, ChainStage.TERMINAL: 3,
        }
        # 字段读法（全仓统一，见 model.ChainNode docstring）：
        #   X.upstream_of  = [「我是谁的上游」的节点] → 这些是本节点的**下游（子）**
        #   X.downstream_of = [「我是谁的下游」的节点] → 这些是本节点的**上游（父）**
        # 因此入度（父）取自 downstream_of，子取自 upstream_of。
        indegree = {n.node_id: 0 for n in nodes}
        for node in nodes:
            for parent in node.downstream_of:
                if parent in indegree:
                    indegree[node.node_id] += 1
        queue = sorted(
            [n for n in nodes if indegree[n.node_id] == 0],
            key=lambda n: (stage_rank[n.stage], n.node_id),
        )
        order: List[str] = []
        while queue:
            node = queue.pop(0)
            order.append(node.node_id)
            for child_id in node.upstream_of:
                if child_id not in indegree:
                    continue
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    child = next(n for n in nodes if n.node_id == child_id)
                    queue.append(child)
            queue.sort(key=lambda n: (stage_rank[n.stage], n.node_id))
        if len(order) != len(nodes):
            logger.warning("产业链拓扑存在环，展示顺序退回声明顺序: %s", [n.node_id for n in nodes])
            return [n.node_id for n in nodes]
        return order

    # ------------------------------------------------------------ 行 → 领域

    @staticmethod
    def parse_node_rows(node_rows: Sequence[Dict]) -> List[ChainNode]:
        """provider 行契约 B → ChainNode 列表（stage 无法识别时抛错）"""
        nodes: List[ChainNode] = []
        for row in node_rows or []:
            nodes.append(ChainNode(
                node_id=str(row.get('node_id') or '').strip(),
                name=str(row.get('node_name') or row.get('name') or '').strip(),
                stage=row.get('stage'),
                upstream_of=row.get('upstream_of') or [],
                downstream_of=row.get('downstream_of') or [],
                rationale=str(row.get('rationale') or ''),
                keywords=row.get('keywords') or [],
            ))
        return nodes

    @staticmethod
    def parse_member_rows(node_rows: Sequence[Dict], default_source: str = '') -> List[ChainMember]:
        """provider 行契约 B 展开为 ChainMember 列表（保留 node 归属）"""
        members: List[ChainMember] = []
        for row in node_rows or []:
            node_id = str(row.get('node_id') or '')
            node_name = str(row.get('node_name') or row.get('name') or '')
            node_stage = row.get('stage')
            for item in row.get('members') or []:
                kind = EvidenceKind.parse(item.get('evidence_kind') or EvidenceKind.CURATED.value)
                members.append(ChainMember(
                    symbol=str(item.get('symbol') or '').strip(),
                    name=str(item.get('name') or ''),
                    stage=item.get('stage') or node_stage,
                    exposure=_as_exposure(item),
                    role=str(item.get('role') or ''),
                    evidence=str(item.get('evidence') or ''),
                    confidence=str(item.get('confidence') or kind.confidence),
                    node_id=node_id,
                    node_name=node_name,
                    evidence_kind=kind.value,
                    source=str(item.get('source') or default_source or ''),
                ))
        return [m for m in members if m.symbol]

    # -------------------------------------------------------------- R2 去重

    @staticmethod
    def dedupe(members: Iterable[ChainMember]) -> List[ChainMember]:
        """R2：同 (symbol, node_id) 留最高证据；同 (symbol, stage) 跨 node 只留最高证据那一组"""
        by_node: Dict[Tuple[str, str], ChainMember] = {}
        for member in members:
            key = (member.symbol, member.node_id)
            current = by_node.get(key)
            if current is None or _claim_rank(member) > _claim_rank(current):
                by_node[key] = member

        # 槽位键 = (来源, node_id)：**同一来源在同一环节位置下的多个节点必须都能留下**
        # （2026-09-11 实测：同一东财主营构成同时支持"玻纤及其制品"与"电子纱及电子布"两个上游节点，
        #  若按来源去重会互相覆盖，只剩后写入的那个 → 静默丢成员）
        by_stage: Dict[Tuple[str, str], Dict[Tuple[str, str], ChainMember]] = {}
        for member in by_node.values():
            stage_key = (member.symbol, member.stage.value)
            slot = by_stage.setdefault(stage_key, {})
            slot_key = (member.source or '_', member.node_id)
            existing = slot.get(slot_key)
            if existing is None or _claim_rank(member) > _claim_rank(existing):
                slot[slot_key] = member

        result: List[ChainMember] = []
        for stage_key, by_source in by_stage.items():
            claims = list(by_source.values())
            best_kind = max(EvidenceKind.parse(c.evidence_kind).priority for c in claims)
            kept_nodes: set = set()
            # 第一轮：保留最高证据类型的主张（同 stage 多节点全部保留——合法的多节点经营）
            for claim in claims:
                if EvidenceKind.parse(claim.evidence_kind).priority == best_kind:
                    result.append(claim)
                    kept_nodes.add(claim.node_id)
            # 第二轮：**其他强证据来源**在未被覆盖的节点上的主张也保留
            # （例：中国巨石最新报告期主营构成已合并披露"玻纤及其制品"，但策展依据 2026Q1
            #  主营构成「电子纱及电子布 24.30%」把它也归到电子布节点——丢弃这条会丢掉真实事实；
            #  而"概念成分/行业分类"这类弱证据仍会被裁掉，避免同一环节位置被塞进无关节点。）
            for claim in claims:
                if EvidenceKind.parse(claim.evidence_kind).priority == best_kind:
                    continue
                if EvidenceKind.parse(claim.evidence_kind).priority < EvidenceKind.PRODUCT_PROFILE.priority:
                    continue
                if claim.node_id in kept_nodes:
                    continue
                result.append(claim)
                kept_nodes.add(claim.node_id)
        return result

    # ---------------------------------------------------------- R3 冲突裁决

    def resolve_conflicts(
        self, members: Sequence[ChainMember]
    ) -> Tuple[List[ChainMember], List[EvidenceConflict], List[Dict]]:
        """R3：证据冲突检测与裁决

        Returns:
            (保留的成员, 冲突记录, 跨环节并存记录 multi_stage)
        """
        deduped = self.dedupe(members)
        grouped: Dict[str, List[ChainMember]] = {}
        for member in deduped:
            grouped.setdefault(member.symbol, []).append(member)

        kept: List[ChainMember] = []
        conflicts: List[EvidenceConflict] = []
        multi_stage: List[Dict] = []

        for symbol, claims in grouped.items():
            stages = {c.stage for c in claims}
            if len(stages) <= 1:
                # 单一环节位置且无来源分歧 → 该标的的主环节就是它（primary 用于给下游快速定位主归位）
                for claim in claims:
                    claim.primary = True
                kept.extend(claims)
                continue

            kinds = {EvidenceKind.parse(c.evidence_kind) for c in claims}
            sources = {c.source for c in claims}
            same_channel = len(kinds) == 1 and len(sources) == 1

            if same_channel:
                # 同一来源横跨多个环节 = 公司跨环节经营（如通威：硅料+电池组件），不是来源冲突
                ordered = sorted(claims, key=lambda c: (c.exposure.ratio if c.exposure else -1), reverse=True)
                multi_stage.append({
                    'symbol': symbol,
                    'name': ordered[0].name,
                    'stages': [c.stage.value for c in ordered],
                    'nodes': [c.node_id for c in ordered],
                    'source': ordered[0].source,
                    'primary_node_id': ordered[0].node_id,
                    'primary_stage': ordered[0].stage.value,
                    'reason': '同一来源（%s）支持该标的跨环节经营，全部保留；主环节按主营占比最高判定'
                              % (ordered[0].source or ordered[0].evidence_kind),
                })
                kept.extend(claims)
                continue

            # 真正的来源冲突：按证据优先级裁决，主营构成优先
            top_priority = max(EvidenceKind.parse(c.evidence_kind).priority for c in claims)
            top_claims = [c for c in claims if EvidenceKind.parse(c.evidence_kind).priority == top_priority]
            top_stages = {c.stage for c in top_claims}
            top_kinds = {EvidenceKind.parse(c.evidence_kind) for c in top_claims}
            top_sources = {c.source for c in top_claims}

            # 子情形：最高优先级的主张**同类型且同源**（但整组主张里还有别的类型，故未走同源分支）——
            # 例如"主营构成"这一个口径自身支持该标的横跨上下游（隆基：光伏产品销售 93% 在产品环节、
            # 光伏电站 3% 在下游环节）。这不是来源之间的分歧，而是**公司跨环节经营**：
            # 全部保留，主环节按占比最高判定，不标"未裁决"（避免把事实当成矛盾）。
            if len(top_kinds) == 1 and len(top_stages) > 1 and len(top_sources) == 1:
                best = max(top_claims, key=lambda c: (c.exposure.ratio if c.exposure else -1))
                for claim in top_claims:
                    claim.primary = (claim is best)
                    claim.conflict = ('同类证据（%s）支持该标的跨环节经营，主环节=%s（占比最高）'
                                      % (claim.evidence_kind, best.node_id))
                retained_same = [c for c in claims
                                 if c not in top_claims
                                 and EvidenceKind.parse(c.evidence_kind).priority >= EvidenceKind.CURATED.priority]
                for claim in retained_same:
                    claim.conflict = ('%s主张的 %s 环节未被最高优先级证据（%s）直接支持，保留供人工复核'
                                      % (claim.evidence_kind, claim.stage.value, best.evidence_kind))
                conflicts.append(EvidenceConflict(
                    symbol=symbol,
                    reason='同类最高优先级证据（%s）支持多个环节' % next(iter(top_kinds)).value,
                    claims=[{
                        'source': c.source, 'node_id': c.node_id, 'stage': c.stage.value,
                        'evidence_kind': c.evidence_kind, 'evidence': c.evidence,
                        'ratio': c.exposure.ratio if c.exposure else None,
                    } for c in sorted(claims, key=_claim_rank, reverse=True)],
                    winner_node_id=best.node_id,
                    winner_stage=best.stage.value,
                    resolved=True,
                    resolution=('同一类型证据（%s）支持该标的跨环节经营，全部保留；主环节按占比最高判定为 %s'
                                % (best.evidence_kind, best.node_id)),
                ))
                kept.extend(top_claims)
                kept.extend(retained_same)
                continue
            conflict_claims = [{
                'source': c.source,
                'node_id': c.node_id,
                'stage': c.stage.value,
                'evidence_kind': c.evidence_kind,
                'evidence': c.evidence,
                'ratio': c.exposure.ratio if c.exposure else None,
            } for c in sorted(claims, key=_claim_rank, reverse=True)]

            winner = max(top_claims, key=lambda c: (c.exposure.ratio if c.exposure else -1))
            resolved = len(top_stages) == 1
            # 被裁掉的主张（仅限**弱证据**：产品构成/行业分类/概念成分）。
            # 人工策展主张即使落败也**保留**并标注：人工主张要由人来推翻（"不静默取其一"），
            # 而机器弱证据（概念成分/行业分类）不保留，避免用行业标签往链里塞无关节点。
            losers = [c for c in claims if c.stage != winner.stage]
            dropped = [c for c in losers
                       if EvidenceKind.parse(c.evidence_kind).priority < EvidenceKind.CURATED.priority]
            retained = [c for c in losers if c not in dropped]
            conflict = EvidenceConflict(
                symbol=symbol,
                reason=('多来源归位冲突：%s' % '、'.join(sorted({c.evidence_kind for c in claims}))),
                claims=conflict_claims,
                winner_node_id=winner.node_id,
                winner_stage=winner.stage.value,
                resolved=resolved,
                resolution=(
                    '以%s为准（优先级 %d 最高），主张节点 %s；裁掉 %d 条弱证据归位，保留 %d 条人工主张供复核'
                    % (winner.evidence_kind, top_priority, winner.node_id, len(dropped), len(retained))
                    if resolved else
                    '最高优先级证据（%s）并列支持多个环节，全部保留待人工复核' % winner.evidence_kind
                ),
            )
            conflicts.append(conflict)

            if resolved:
                winners = [c for c in top_claims if c.stage == winner.stage]
                for claim in winners:
                    claim.conflict = ('来源冲突已裁决：%s 支持 %s；详见 evidence_conflicts'
                                      % (claim.evidence_kind, claim.stage.value))
                    claim.primary = True
                for claim in retained:
                    claim.conflict = (
                        '来源冲突：本主张（%s）与%s主张的 %s 环节不一致，按 RFC §2.3 以%s为准；'
                        '该人工主张保留供复核' % (claim.evidence_kind, winner.evidence_kind,
                                             winner.stage.value, winner.evidence_kind)
                    )
                kept.extend(winners)
                kept.extend(retained)
            else:
                for claim in claims:
                    claim.conflict = '来源冲突未裁决（同级证据矛盾），保留全部主张待人工复核'
                kept.extend(claims)

        return kept, conflicts, multi_stage

    # ----------------------------------------------------------- 成员归位

    def attribute_by_exposure(
        self,
        symbol: str,
        name: str,
        revenue_rows: Sequence[Dict],
        nodes: Sequence[ChainNode],
        source: str = '',
        role: str = '',
    ) -> Tuple[List[ChainMember], List[Dict]]:
        """用**主营构成**把标的归位到环节（唯一的硬证据路径，RFC §2.3）

        匹配方式：取最新报告期的 按产品分类/按行业分类 行，按 node.keywords（缺省用
        node.name）做包含匹配；同一节点取占比最高的那条作为该节点的归位证据。

        Returns:
            (members, unmatched_rows)——未匹配上的主营构成行**如实返回**（不静默丢弃），
            便于人看到"哪些收入没被归位"，从而发现 seed 缺环节。
        """
        rows = self._latest_attribution_rows(revenue_rows)
        members: List[ChainMember] = []
        unmatched: List[Dict] = []

        for row in rows:
            item = str(row.get('item') or '')
            matched = _match_node(item, nodes)
            ratio = _to_ratio(row.get('ratio'))
            if matched is None or ratio is None:
                unmatched.append({
                    'item': item,
                    'ratio': ratio,
                    'classification': row.get('classification'),
                    'report_date': row.get('report_date'),
                    'reason': '未命中任何节点关键词' if matched is None else '占比缺失',
                })
                continue
            exposure = RevenueExposure(
                ratio=ratio,
                basis='主营构成：%s（%s，%s）' % (item, row.get('basis') or source, row.get('report_date') or ''),
                as_of=str(row.get('report_date') or ''),
            )
            members.append(ChainMember(
                symbol=symbol,
                name=name,
                stage=matched.stage,
                exposure=exposure,
                role=role,
                evidence='主营构成归位：%s 占营收 %.2f%%（%s，报告期 %s）'
                         % (item, exposure.pct, row.get('basis') or source, row.get('report_date') or ''),
                confidence=EvidenceKind.MAIN_BUSINESS.confidence,
                node_id=matched.node_id,
                node_name=matched.name,
                evidence_kind=EvidenceKind.MAIN_BUSINESS.value,
                source=source or str(row.get('source') or ''),
            ))

        # 同一节点只保留占比最高的一条（同一节点多个产品名是常见情况）
        best: Dict[str, ChainMember] = {}
        for member in members:
            current = best.get(member.node_id)
            if current is None or (member.exposure and current.exposure
                                   and member.exposure.ratio > current.exposure.ratio):
                best[member.node_id] = member
        return list(best.values()), unmatched

    def attribute_by_profile(
        self,
        symbol: str,
        name: str,
        profile_rows: Sequence[Dict],
        nodes: Sequence[ChainNode],
        source: str = '',
        role: str = '',
    ) -> Tuple[List[ChainMember], List[Dict]]:
        """用**产品构成文本**（同花顺 F10：产品名称/产品类型/主营业务）把标的归位到环节

        与 attribute_by_exposure 的分工：本方法**没有营收占比**，证据等级为 PRODUCT_PROFILE
        （优先级 3，低于主营构成 4）——用于东财主营构成不可用时的独立通道兜底，
        或对主营构成未覆盖标的做关键词佐证。经营范围（工商登记范围）不参与归位（太宽泛）。
        """
        usable = [
            row for row in (profile_rows or [])
            if str(row.get('classification') or '') in ('产品构成', '主营业务描述')
            and str(row.get('item') or '').strip()
        ]
        members: List[ChainMember] = []
        unmatched: List[Dict] = []
        for row in usable:
            item = str(row.get('item') or '').strip()
            matched = _match_node(item, nodes)
            if matched is None:
                unmatched.append({
                    'item': item,
                    'ratio': None,
                    'classification': row.get('classification'),
                    'report_date': row.get('report_date'),
                    'reason': '未命中任何节点关键词',
                })
                continue
            members.append(ChainMember(
                symbol=symbol,
                name=name,
                stage=matched.stage,
                exposure=None,
                role=role,
                evidence='产品构成归位：%s（%s，抓取 %s）——无营收占比，证据等级低于主营构成'
                         % (item, row.get('basis') or source, row.get('as_of') or row.get('report_date') or ''),
                confidence=EvidenceKind.PRODUCT_PROFILE.confidence,
                node_id=matched.node_id,
                node_name=matched.name,
                evidence_kind=EvidenceKind.PRODUCT_PROFILE.value,
                source=source or str(row.get('source') or ''),
            ))

        best: Dict[str, ChainMember] = {}
        for member in members:
            best.setdefault(member.node_id, member)
        return list(best.values()), unmatched

    @staticmethod
    def _latest_attribution_rows(revenue_rows: Sequence[Dict]) -> List[Dict]:
        """取**最新报告期**的、非地区分类的主营构成行（口径优先级：按产品分类 > 按行业分类）

        为什么优先"含按产品分类的最新报告期"：实测发现同一报告期内两种口径并存
        （如中国巨石 2026-06-30 同时有 按产品分类「玻纤及其制品相关」97.3% 与
        按行业分类明细），而部分公司在最新报告期只披露粗口径的行业分类、
        产品级明细要到前一报告期才有（如 2026Q1 的「电子纱及电子布 24.30%」）。
        规则：先取含"按产品分类"的最新报告期；若该期不存在，退回整体最新报告期。
        两个口径同时保留时，按产品分类的行优先参与归位（更细、更接近业务实质）。
        """
        usable = []
        for row in (revenue_rows or []):
            if str(row.get('classification') or '') in _NON_ATTRIBUTION_CLASSIFICATIONS:
                continue
            # 跳过「其中:XXX」子项：它是上一行大类金额的**明细拆分**，两行金额同源，
            # 同时参与归位会把同一笔收入算到两个节点（2026-09-11 实测：宏和科技
            # 「其中:E玻璃纤维布 64.54%」与「电子级玻璃纤维布 98.56%」并存）。
            if str(row.get('item') or '').strip().startswith('其中'):
                continue
            usable.append(row)
        if not usable:
            return []
        # **每个分类口径各取自己的最新报告期**，再取并集。
        # 为什么不是"全体最新报告期"：实测（2026-09-11）工业富联同报告期内
        #   按产品分类「3C电子产品 99.8%」过于粗糙（分不出服务器/消费电子），
        #   而按行业分类「云计算 66.75%」正好是算力终端的证据；
        # 反过来也有公司只在按产品分类披露细分（隆基「光伏产品销售 93%」）。
        # 两个口径各自最新、并集参与归位，覆盖最全且不丢证据。
        by_classification: Dict[str, List[Dict]] = {}
        for row in usable:
            by_classification.setdefault(str(row.get('classification') or '未分类'), []).append(row)
        out: List[Dict] = []
        for rows in by_classification.values():
            latest = max(str(row.get('report_date') or '') for row in rows)
            out.extend(row for row in rows if str(row.get('report_date') or '') == latest)
        return out

    # --------------------------------------------------------------- 聚合根

    def build_chain(
        self,
        chain_id: str,
        name: str,
        node_rows: Sequence[Dict],
        *,
        description: str = '',
        rationale: str = '',
        source: str = '',
        as_of: str = '',
        extra_members: Optional[Sequence[ChainMember]] = None,
    ) -> Tuple[IndustryChain, List[EvidenceConflict], List[Dict]]:
        """行集合 → 聚合根（含拓扑自校验、去重、冲突裁决）

        Returns: (chain, conflicts, multi_stage)
        Raises: ValueError（拓扑不对称 / stage 非法 / 占比越界——一律 fail-loud）
        """
        nodes = self.parse_node_rows(node_rows)
        if not nodes:
            raise ValueError(f"产业链 {name or chain_id} 没有任何环节节点（seed/provider 返回空）")
        self.validate_topology(nodes)
        members = self.parse_member_rows(node_rows, default_source=source)
        if extra_members:
            members.extend(extra_members)
        kept, conflicts, multi_stage = self.resolve_conflicts(members)

        order = self.chain_topology_order(nodes)
        rank = {node_id: idx for idx, node_id in enumerate(order)}
        nodes.sort(key=lambda n: (rank.get(n.node_id, 999), n.node_id))

        chain = IndustryChain(
            chain_id=chain_id,
            name=name,
            nodes=nodes,
            members=kept,
            description=description,
            rationale=rationale,
            source=source,
            as_of=as_of,
        )
        return chain, conflicts, multi_stage


def _claim_rank(member: ChainMember) -> Tuple[int, float, int]:
    """归位主张的排序键：证据优先级 → 占比 → 置信度"""
    ratio = member.exposure.ratio if member.exposure else -1.0
    return (
        EvidenceKind.parse(member.evidence_kind).priority,
        ratio,
        CONFIDENCE_ORDER.get(member.confidence, 0),
    )
