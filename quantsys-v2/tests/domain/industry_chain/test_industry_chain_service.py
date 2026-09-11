"""domain/industry_chain/service.py 契约测试（纯逻辑，零 I/O）

覆盖三条规则里**错了就让整条链归位全错**的部分：
  R1 拓扑自校验（对称性 / 引用完整性 / 环节位置非法）
  R2 归并去重（同节点留最高证据；同环节多节点是合法事实）
  R3 证据冲突裁决（跨 stage 才叫冲突；主营构成优先；同级矛盾必须暴露而非假装已裁决）
  成员归位（主营构成硬证据 / 产品构成文本 / 单位归一 / 未命中如实回报）
"""
import logging

import pytest

from domain.industry_chain.model import (
    ChainMember, ChainNode, ChainStage, EvidenceKind, RevenueExposure,
)
from domain.industry_chain.service import (
    IndustryChainService, _match_node, _to_ratio,
)

SVC = IndustryChainService()

NODES = [
    ChainNode(node_id='gfy', name='玻纤纱', stage='upstream',
              keywords=['玻璃纤维', '玻纤'], upstream_of=['dbb']),
    ChainNode(node_id='dbb', name='电子布', stage='upstream',
              keywords=['电子级玻璃纤维', '电子布'],
              upstream_of=['pcb'], downstream_of=['gfy']),
    ChainNode(node_id='pcb', name='覆铜板', stage='midstream',
              keywords=['覆铜板', 'CCL'], downstream_of=['dbb']),
]


def member(symbol, stage, node_id, kind, source, ratio=None, name='X'):
    exposure = (RevenueExposure(ratio=ratio, basis='测试口径', as_of='2026-06-30')
                if ratio is not None else None)
    return ChainMember(
        symbol=symbol, name=name, stage=stage, exposure=exposure,
        evidence='测试证据', confidence=EvidenceKind.parse(kind).confidence,
        node_id=node_id, node_name=node_id, evidence_kind=kind, source=source,
    )


def node_row(node_id, node_name, stage, *, upstream_of=(), downstream_of=(),
             keywords=(), members=()):
    return {
        'node_id': node_id, 'node_name': node_name, 'stage': stage,
        'upstream_of': list(upstream_of), 'downstream_of': list(downstream_of),
        'rationale': '人工判断', 'keywords': list(keywords), 'members': list(members),
    }


# ───────────────────────────── R1 拓扑自校验 ─────────────────────────────

def test_对称声明的拓扑通过校验():
    IndustryChainService.validate_topology(NODES)


def test_引用了不存在的节点必须失败而不是跳过():
    broken = [ChainNode(node_id='a', name='A', stage='upstream', upstream_of=['ghost'])]
    with pytest.raises(ValueError, match='不存在'):
        IndustryChainService.validate_topology(broken)


def test_单项声明上下游必须失败_fail_loud():
    """拓扑错了会让整条链归位全错，不能静默容忍。"""
    one_sided = [
        ChainNode(node_id='a', name='A', stage='upstream', upstream_of=['b']),
        ChainNode(node_id='b', name='B', stage='midstream'),
    ]
    with pytest.raises(ValueError, match='拓扑不对称'):
        IndustryChainService.validate_topology(one_sided)


def test_节点id重复必须失败():
    dup = [ChainNode(node_id='a', name='A', stage='upstream'),
           ChainNode(node_id='a', name='A2', stage='midstream')]
    with pytest.raises(ValueError, match='重复'):
        IndustryChainService.validate_topology(dup)


def test_非法环节位置必须失败而不是归到默认环节():
    with pytest.raises(ValueError):
        ChainNode(node_id='a', name='A', stage='中盘')


def test_拓扑序按上游到下游排列():
    order = IndustryChainService.chain_topology_order(NODES)
    assert order.index('gfy') < order.index('dbb') < order.index('pcb')


def test_存在环时退回声明顺序并告警而不静默给出错误顺序(caplog):
    cyclic = [
        ChainNode(node_id='a', name='A', stage='upstream', upstream_of=['b'], downstream_of=['b']),
        ChainNode(node_id='b', name='B', stage='midstream', upstream_of=['a'], downstream_of=['a']),
    ]
    with caplog.at_level(logging.WARNING):
        order = IndustryChainService.chain_topology_order(cyclic)
    assert order == ['a', 'b']
    assert any('环' in r.message for r in caplog.records)


# ─────────────────────────────── 单位归一 ───────────────────────────────

@pytest.mark.parametrize('raw,expected', [
    (97.3, 0.973),      # 百分数 → 小数
    (0.973, 0.973),     # 已是小数
    (100.0, 1.0),
    (1.0, 1.0),
])
def test_占比归一_百分数与小数都能正确归一(raw, expected):
    assert _to_ratio(raw) == pytest.approx(expected)


@pytest.mark.parametrize('raw', [None, float('nan'), '', 'abc', 0, -1.49])
def test_无效占比返回None而绝不静默变0(raw):
    """NaN/负占比（如东财「公司内各业务部间相互抵销 -1.49%」）不得被当成有效证据。"""
    assert _to_ratio(raw) is None


def test_占比越界必须由模型抛错而不是静默接受():
    """契约：provider 负责把百分数归一为小数；150 这类越界值必须暴露。"""
    with pytest.raises(ValueError, match='越界'):
        RevenueExposure(ratio=150.0)


# ───────────────────────────── 关键词归位 ─────────────────────────────

def test_最长关键词优先_电子布不得被归到玻纤纱():
    """2026-09-11 实测：按声明顺序取首个命中会把电子布标的归到玻纤纱（静默错位）。"""
    assert _match_node('电子级玻璃纤维布', NODES).node_id == 'dbb'
    assert _match_node('无碱玻璃纤维无捻粗纱', NODES).node_id == 'gfy'


def test_未命中关键词返回None():
    assert _match_node('白酒销售', NODES) is None


def test_节点无关键词时用节点名兜底():
    nodes = [ChainNode(node_id='x', name='覆铜板', stage='midstream')]
    assert _match_node('高频覆铜板', nodes).node_id == 'x'


# ──────────────────────────── R2 归并去重 ────────────────────────────

def test_同一节点同一标的只保留证据最强的一条():
    weak = member('600176', 'upstream', 'gfy', '产品构成', 'ths_revenue')
    strong = member('600176', 'upstream', 'gfy', '主营构成', 'eastmoney_revenue', 0.97)
    kept = IndustryChainService.dedupe([weak, strong])
    assert len(kept) == 1 and kept[0].evidence_kind == '主营构成'


def test_同一环节位置的不同节点必须都能留下():
    """中国巨石同时做玻纤纱与电子布：同一来源支持两个节点，不能互相覆盖。"""
    a = member('600176', 'upstream', 'gfy', '主营构成', 'eastmoney_revenue', 0.97)
    b = member('600176', 'upstream', 'dbb', '主营构成', 'eastmoney_revenue', 0.24)
    kept = IndustryChainService.dedupe([a, b])
    assert {m.node_id for m in kept} == {'gfy', 'dbb'}


def test_同环节上弱证据被强证据裁掉避免用行业标签塞无关节点():
    strong = member('600176', 'upstream', 'gfy', '主营构成', 'eastmoney_revenue', 0.97)
    weak = member('600176', 'upstream', 'dbb', '概念成分', 'akshare_concept')
    kept = IndustryChainService.dedupe([strong, weak])
    assert {m.node_id for m in kept} == {'gfy'}


def test_不同环节位置的成员互不影响():
    a = member('600176', 'upstream', 'gfy', '主营构成', 'em', 0.97)
    b = member('600176', 'midstream', 'pcb', '概念成分', 'akshare_concept')
    kept = IndustryChainService.dedupe([a, b])
    assert {m.node_id for m in kept} == {'gfy', 'pcb'}


# ──────────────────────────── R3 冲突裁决 ────────────────────────────

def test_单一环节位置不产生冲突():
    claims = [member('600176', 'upstream', 'gfy', '主营构成', 'em', 0.97),
              member('600176', 'upstream', 'dbb', '策展', 'curated')]
    kept, conflicts, multi = SVC.resolve_conflicts(claims)
    assert len(kept) == 2 and conflicts == [] and multi == []
    assert all(m.primary for m in kept)


def test_跨环节冲突以主营构成为准且弱证据被裁掉但留痕():
    claims = [
        member('600176', 'upstream', 'gfy', '主营构成', 'eastmoney_revenue', 0.97),
        member('600176', 'midstream', 'pcb', '概念成分', 'akshare_concept'),
    ]
    kept, conflicts, _ = SVC.resolve_conflicts(claims)
    assert [m.node_id for m in kept] == ['gfy']
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.resolved is True and conflict.winner_node_id == 'gfy'
    assert len(conflict.claims) == 2, '被裁掉的主张必须写进 claims 供人工复核'


def test_胜出环节内的其他节点主张不得被静默丢弃():
    """回归（2026-09-11）：裁决只保留 top_claims 时，同 stage 不同 node 的策展主张
    既不在 dropped 也不在 retained、更没标注 —— 属"不静默取其一"红线。"""
    claims = [
        member('600176', 'upstream', 'gfy', '主营构成', 'eastmoney_revenue', 0.97),
        member('600176', 'upstream', 'dbb', '策展', 'curated'),
        member('600176', 'midstream', 'pcb', '概念成分', 'akshare_concept'),
    ]
    kept, conflicts, _ = SVC.resolve_conflicts(claims)
    assert {m.node_id for m in kept} == {'gfy', 'dbb'}, '策展主张（同环节另一节点）必须保留'
    voted = [c for c in conflicts[0].claims if c['node_id'] == 'dbb']
    assert voted, '被保留的策展主张也必须出现在冲突记录里供复核'


def test_人工策展主张即使落败也保留供复核():
    claims = [
        member('600176', 'upstream', 'gfy', '主营构成', 'eastmoney_revenue', 0.97),
        member('600176', 'midstream', 'pcb', '策展', 'curated'),
    ]
    kept, conflicts, _ = SVC.resolve_conflicts(claims)
    assert {m.node_id for m in kept} == {'gfy', 'pcb'}
    curated = [m for m in kept if m.node_id == 'pcb'][0]
    assert curated.conflict, '人工主张要由人来推翻，必须标注原因'


def test_同一来源横跨多环节记为跨环节经营而非冲突():
    """通威股份：硅料（上游）+ 电池组件（下游），同一来源同一证据类型。"""
    claims = [member('600438', 'upstream', 'gfy', '主营构成', 'eastmoney_revenue', 0.6),
              member('600438', 'midstream', 'pcb', '主营构成', 'eastmoney_revenue', 0.4)]
    kept, conflicts, multi = SVC.resolve_conflicts(claims)
    assert len(kept) == 2 and len(multi) == 1
    assert multi[0]['primary_node_id'] == 'gfy', '主环节按占比最高判定'
    assert multi[0]['primary_stage'] == 'upstream'


def test_同级证据并列矛盾必须暴露为未裁决而不是假装已裁决():
    claims = [member('600002', 'upstream', 'gfy', '策展', 'curator_a'),
              member('600002', 'midstream', 'pcb', '策展', 'curator_b')]
    kept, conflicts, _ = SVC.resolve_conflicts(claims)
    assert len(conflicts) == 1 and conflicts[0].resolved is False
    assert len(kept) == 2, '未裁决时全部保留'
    assert all('未裁决' in m.conflict for m in kept)


def test_多标的互不干扰_按标的分别裁决():
    claims = [
        member('600176', 'upstream', 'gfy', '主营构成', 'em', 0.97),
        member('600176', 'midstream', 'pcb', '概念成分', 'akshare_concept'),
        member('000001', 'midstream', 'pcb', '主营构成', 'em', 0.5),
    ]
    kept, conflicts, _ = SVC.resolve_conflicts(claims)
    assert {m.symbol for m in kept} == {'600176', '000001'}
    assert [m.node_id for m in kept if m.symbol == '600176'] == ['gfy']
    assert len(conflicts) == 1


# ─────────────────────────── 成员归位（主营构成） ───────────────────────────

def _row(item, ratio, classification='按产品分类', report_date='2026-06-30'):
    return {'item': item, 'ratio': ratio, 'classification': classification,
            'report_date': report_date, 'basis': '东财F10主营构成', 'source': 'eastmoney_revenue'}


def test_主营构成归位带上占比与证据等级():
    members, unmatched = SVC.attribute_by_exposure(
        '600176', '中国巨石', [_row('玻纤及其制品相关', 97.3)], NODES)
    assert unmatched == []
    assert len(members) == 1 and members[0].node_id == 'gfy'
    assert members[0].evidence_kind == '主营构成' and members[0].confidence == 'high'
    assert members[0].exposure.ratio == pytest.approx(0.973), '97.3 必须归一为小数'


def test_未命中的主营构成行必须如实返回而不是静默丢弃():
    members, unmatched = SVC.attribute_by_exposure(
        '600176', '中国巨石', [_row('玻纤及其制品相关', 97.3), _row('其他业务收入', 2.7)], NODES)
    assert len(members) == 1
    assert [u['item'] for u in unmatched] == ['其他业务收入']
    assert unmatched[0]['reason'] == '未命中任何节点关键词'


def test_占比缺失的行计入unmatched并说明原因():
    members, unmatched = SVC.attribute_by_exposure(
        '600176', '中国巨石', [_row('玻纤及其制品相关', None)], NODES)
    assert members == [] and unmatched[0]['reason'] == '占比缺失'


def test_按地区分类不参与归位():
    members, unmatched = SVC.attribute_by_exposure(
        '600176', '中国巨石', [_row('华东地区', 30.0, classification='按地区分类')], NODES)
    assert members == [] and unmatched == []


def test_其中子项不参与归位避免同一笔收入被算到两个节点():
    rows = [_row('电子级玻璃纤维布', 98.56), _row('其中:E玻璃纤维布', 64.54)]
    members, _ = SVC.attribute_by_exposure('603256', '宏和科技', rows, NODES)
    assert [m.node_id for m in members] == ['dbb']


def test_每个分类口径各取自己的最新报告期():
    rows = [
        _row('玻纤及其制品相关', 97.3, classification='按产品分类', report_date='2026-06-30'),
        _row('老口径产品', 90.0, classification='按产品分类', report_date='2025-12-31'),
        _row('云计算', 66.75, classification='按行业分类', report_date='2026-06-30'),
    ]
    members, _ = SVC.attribute_by_exposure('601138', '工业富联', rows, NODES)
    items = {m.node_id for m in members}
    assert items == {'gfy'}, '只取各口径自己的最新报告期；过期口径的行不参与'


def test_同一节点取占比最高的那条产品():
    rows = [_row('玻璃纤维纱', 10.0), _row('玻纤纱及制品', 20.0)]
    members, _ = SVC.attribute_by_exposure('600176', '中国巨石', rows, NODES)
    assert len(members) == 1 and members[0].exposure.ratio == pytest.approx(0.20)


# ─────────────────────────── 成员归位（产品构成） ───────────────────────────

def test_产品构成归位无占比且证据等级低于主营构成():
    rows = [{'item': '电子布、粗纱及制品', 'classification': '产品构成',
             'report_date': '2026-09-11', 'basis': '同花顺F10', 'source': 'ths_revenue'}]
    members, unmatched = SVC.attribute_by_profile('600176', '中国巨石', rows, NODES)
    assert unmatched == [] and len(members) == 1
    assert members[0].evidence_kind == '产品构成' and members[0].confidence == 'medium'
    assert members[0].exposure is None


def test_经营范围不参与归位():
    rows = [{'item': '玻璃纤维及制品的生产、销售', 'classification': '经营范围',
             'report_date': '2026-09-11', 'source': 'ths_revenue'}]
    members, unmatched = SVC.attribute_by_profile('600176', '中国巨石', rows, NODES)
    assert members == [] and unmatched == []


# ──────────────────────────────── 聚合根 ────────────────────────────────

def test_空节点集合必须失败而不是产出空链():
    with pytest.raises(ValueError, match='没有任何环节节点'):
        SVC.build_chain('c1', '测试链', [])


def test_build_chain按拓扑序排列节点并裁决成员():
    rows = [
        node_row('pcb', '覆铜板', 'midstream', downstream_of=['dbb'], keywords=['覆铜板'],
                 members=[{'symbol': '600183', 'name': '生益科技', 'evidence_kind': '策展'}]),
        node_row('gfy', '玻纤纱', 'upstream', upstream_of=['dbb'], keywords=['玻璃纤维']),
        node_row('dbb', '电子布', 'upstream', upstream_of=['pcb'], downstream_of=['gfy'],
                 keywords=['电子布']),
    ]
    chain, conflicts, multi = SVC.build_chain('glass', '玻纤链', rows, source='curated')
    assert [n.node_id for n in chain.nodes] == ['gfy', 'dbb', 'pcb']
    assert [m.symbol for m in chain.members] == ['600183']
    assert chain.members[0].source == 'curated'
    assert conflicts == [] and multi == []


def test_build_chain不接受拓扑不对称的输入():
    rows = [
        node_row('a', 'A', 'upstream', upstream_of=['b'], keywords=['a']),
        node_row('b', 'B', 'midstream', keywords=['b']),
    ]
    with pytest.raises(ValueError, match='拓扑不对称'):
        SVC.build_chain('c1', '测试链', rows)
