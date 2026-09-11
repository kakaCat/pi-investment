"""domain/events/service.py 契约测试（纯逻辑，零 I/O）

覆盖被判据驱动、且**出错就会造成资金风险**的行为：
  R1 evidence_hash 幂等锚 / 归一化边界
  R2 归并去重（权威度）
  R3 多源合并 + 分歧留痕（不静默取其一）
  R4 重要度推断（解禁占比 / 政策主体 / 词表纪律）
  行契约 fail-loud（缺日期不编造今天；非 dict 行必须如实回报）
"""
from datetime import date, timedelta

import pytest

from domain.events.model import (
    AUTHORITY_CNINFO, AUTHORITY_EASTMONEY, EventScope, EventType, MarketEvent,
    source_authority,
)
from domain.events.service import (
    MarketEventService, compute_evidence_hash, infer_event_type, infer_importance,
    infer_scope, normalize_title,
)

SVC = MarketEventService()

# 两源对同一条公告的真实标题（2026-09-11 打样：东财带公司名前缀，巨潮不带前缀）
EM_TITLE = '中国船舶:关于北海造船厂一货轮火灾事故有关情况的公告'
CN_TITLE = '关于北海造船厂一货轮火灾事故有关情况的公告'


def _row(**overrides):
    row = {
        'scope': 'individual',
        'type': None,
        'title': '关于部分限售股上市流通的公告',
        'effective_date': '2026-09-20',
        'announce_date': '2026-09-11',
        'importance': None,
        'symbols': ['600150'],
        'industries': [],
        'source': 'eastmoney_notice',
        'url': '',
        'summary': '',
        'raw': {},
    }
    row.update(overrides)
    return row


def _event(title, authority, source, **kwargs):
    event = MarketEvent(
        event_id=title[:16],
        scope=kwargs.pop('scope', EventScope.INDIVIDUAL),
        type=kwargs.pop('type', EventType.REGULATORY),
        title=title,
        effective_date=kwargs.pop('effective_date', '2026-09-20'),
        symbols=kwargs.pop('symbols', ['600150']),
        authority=authority,
    )
    event.source = source
    return event


# ─────────────────────────────── R1 证据哈希 ───────────────────────────────

def test_同一锚的evidence_hash稳定且对标的顺序不敏感():
    a = compute_evidence_hash('individual', 'regulatory', ['600150', '000001'], '2026-09-20', EM_TITLE)
    b = compute_evidence_hash(EventScope.INDIVIDUAL, EventType.REGULATORY,
                              ['000001', '600150'], '2026-09-20', EM_TITLE)
    assert a == b, '标的顺序不同不应改变幂等锚'
    assert a == compute_evidence_hash('individual', 'regulatory', ['600150', '000001'],
                                      '2026-09-20 00:00:00', EM_TITLE), '日期应只取前 10 位'


def test_不同标的或不同日期必须得到不同哈希():
    base = compute_evidence_hash('individual', 'regulatory', ['600150'], '2026-09-20', EM_TITLE)
    assert base != compute_evidence_hash('individual', 'regulatory', ['600151'], '2026-09-20', EM_TITLE)
    assert base != compute_evidence_hash('individual', 'regulatory', ['600150'], '2026-09-21', EM_TITLE)
    assert base != compute_evidence_hash('macro', 'regulatory', ['600150'], '2026-09-20', EM_TITLE)


def test_两源对同一公告的标题必须归一为同一锚():
    """东财「中国船舶:关于…」与巨潮「关于…」归一后相同 —— R1 是幂等去重的唯一锚。"""
    assert normalize_title(EM_TITLE) == normalize_title(CN_TITLE)
    assert compute_evidence_hash('individual', 'regulatory', ['600150'], '2026-09-11', EM_TITLE) == \
        compute_evidence_hash('individual', 'regulatory', ['600150'], '2026-09-11', CN_TITLE)


def test_归一化不改写语义_不同事件的标题仍不同():
    """宁可多留一条，也不要把两件事合并成一件（合并错了会漏掉排雷风险）。"""
    a = normalize_title('关于重大资产重组的公告')
    b = normalize_title('关于终止重大资产重组的公告')
    assert a != b


def test_归一化对空输入与全角字符的安全行为():
    assert normalize_title(None) == ''
    assert normalize_title('') == ''
    assert normalize_title('ＡＢＣ　１２３') == 'abc123'


# ─────────────────────────── 行契约 fail-loud ───────────────────────────

def test_缺effective_date的行必须被拒绝而不是用今天兜底():
    events, rejected = SVC.parse_rows([_row(effective_date='', announce_date='')])
    assert events == []
    assert len(rejected) == 1 and 'effective_date' in rejected[0]['reason']


def test_缺title的行必须被拒绝():
    events, rejected = SVC.parse_rows([_row(title='')])
    assert events == []
    assert len(rejected) == 1 and 'title' in rejected[0]['reason']


def test_非dict行必须计入rejected而不是静默丢弃():
    """静默失败清单 §4：只处理一种形态会让另一种形态整批消失。

    manager 返回领域对象（而非 dict）时，若无如实回报，下游只会看到『今天没有事件』，
    与『上游改版了』无法区分。
    """
    events, rejected = SVC.parse_rows([_row(), _event('关于X的公告', 60, 'eastmoney_notice')])
    assert len(events) == 1
    assert len(rejected) == 1
    assert '不是 dict' in rejected[0]['reason']


def test_importance越界不得静默截断而是如实拒绝():
    """5 星制当成 3 星制是本项目已记录的口径事故类型。"""
    events, rejected = SVC.parse_rows([_row(importance=5)])
    assert events == []
    assert 'importance' in rejected[0]['reason']


def test_单行坏数据不得炸掉整批():
    events, rejected = SVC.parse_rows([_row(importance=9), _row(title='关于股东大会的通知')])
    assert len(events) == 1 and len(rejected) == 1


def test_effective_date缺失时回落到announce_date而不是编造今天():
    """契约允许 announce_date 兜底（源只给公告日时），但两者都缺必须拒绝。"""
    events, rejected = SVC.parse_rows([_row(effective_date='', announce_date='2026-09-11')])
    assert len(events) == 1 and events[0].effective_date == '2026-09-11' and rejected == []


def test_provider显式importance优先于领域推断():
    events, _ = SVC.parse_rows([_row(importance=1, title='2026年半年度报告')])
    assert events[0].importance == 1, 'provider 更了解自己的口径，领域层只补 None'


def test_行契约的source与authority按名映射():
    events, _ = SVC.parse_rows([_row(source='cninfo_disclosure')])
    assert events[0].authority == AUTHORITY_CNINFO


# ─────────────────────────── R2 归并去重 ───────────────────────────

def test_同哈希只保留权威度最高的源():
    low = _event('关于部分限售股上市流通的公告', AUTHORITY_EASTMONEY, 'eastmoney_notice')
    high = _event('关于部分限售股上市流通的公告', AUTHORITY_CNINFO, 'cninfo_disclosure')
    for e in (low, high):
        e.evidence_hash = 'same-hash'
    kept = MarketEventService.dedupe([low, high])
    assert len(kept) == 1 and kept[0].source == 'cninfo_disclosure'


def test_同权威度时保留先出现者_provider注册顺序即优先级():
    first = _event('A', AUTHORITY_EASTMONEY, 'first')
    second = _event('A', AUTHORITY_EASTMONEY, 'second')
    for e in (first, second):
        e.evidence_hash = 'h'
    assert MarketEventService.dedupe([first, second])[0].source == 'first'


# ─────────────────────── R3 多源合并 + 分歧留痕 ───────────────────────

def test_多源同一事件合并保留权威源且分歧留痕():
    em = _event(EM_TITLE, AUTHORITY_EASTMONEY, 'eastmoney_notice')
    cn = _event(CN_TITLE, AUTHORITY_CNINFO, 'cninfo_disclosure')
    merged, divergences = SVC.merge([em, cn])
    assert len(merged) == 1 and merged[0].source == 'cninfo_disclosure'
    assert len(divergences) == 1
    dropped = divergences[0].dropped
    assert [d['source'] for d in dropped] == ['eastmoney_notice'], '分歧不得静默丢弃'
    assert divergences[0].kept_source == 'cninfo_disclosure'


def test_不同事件即使日期标的相同也不得合并():
    a = _event('关于部分限售股上市流通的公告', AUTHORITY_EASTMONEY, 'eastmoney_notice')
    b = _event('关于2026年半年度报告的公告', AUTHORITY_CNINFO, 'cninfo_disclosure')
    merged, divergences = SVC.merge([a, b])
    assert len(merged) == 2 and divergences == []


def test_标的不同的事件不进入同一个桶():
    a = _event(EM_TITLE, AUTHORITY_EASTMONEY, 'eastmoney_notice', symbols=['600150'])
    b = _event(CN_TITLE, AUTHORITY_CNINFO, 'cninfo_disclosure', symbols=['600151'])
    merged, divergences = SVC.merge([a, b])
    assert len(merged) == 2 and divergences == []


def test_prepare流水线如实回报每一步计数():
    rows = [_row(source='eastmoney_notice', title=EM_TITLE, authority=AUTHORITY_EASTMONEY),
            _row(source='cninfo_disclosure', title=CN_TITLE, authority=AUTHORITY_CNINFO),
            _row(title='')]
    result = SVC.prepare(rows)
    assert result['parsed'] == 2, 'parse 阶段两条都成立（标题原文不同）'
    assert result['deduped'] == 1, '同哈希在 dedupe 阶段合并为 1（归一化锚生效）'
    assert len(result['events']) == 1 and result['events'][0].source == 'cninfo_disclosure'
    assert len(result['rejected']) == 1


# ─────────────────────────── R4 重要度推断 ───────────────────────────

@pytest.mark.parametrize('title,expected', [
    ('2026年半年度报告', 3),
    ('2026年半年度业绩预增公告', 3),
    ('关于部分限售股上市流通的公告', 3),
    ('关于向特定对象发行股票的公告', 3),
    ('关于收到中国证监会立案告知书的公告', 3),
    ('关于收到监管问询函的公告', 2),
    ('关于2026年第一季度利润分配方案的公告', 2),
    ('关于召开2026年第一次临时股东大会的通知', 2),
    ('关于控股股东部分股份解除质押的公告', 1),
])
def test_个股事件重要度按能否改变持仓决策分级(title, expected):
    event_type = infer_event_type(title)
    assert infer_importance(EventScope.INDIVIDUAL, event_type, title, ['600150']) == expected


def test_解禁占比低于1pertencent降级为中等():
    assert infer_importance('individual', 'unlock', '解禁', ['600176'], {'ratio': 0.004}) == 2
    assert infer_importance('individual', 'unlock', '解禁', ['600176'], {'ratio': 0.4}) == 3


def test_解禁占比字段缺失时不得当成0而调低重要度():
    """占比缺失 ≠ 占比 0：缺失应保守判为高影响。"""
    assert infer_importance('individual', 'unlock', '解禁', ['600176'], {}) == 3
    assert infer_importance('individual', 'unlock', '解禁', ['600176'], {'ratio': None}) == 3


def test_政策事件按发布主体与行业影响分级():
    assert infer_importance('macro', 'policy', '国务院关于促进人工智能发展的意见') == 3
    assert infer_importance('macro', 'policy', '国务院办公厅关于加强中小企业回款难问题治理有关工作的通知') == 3
    assert infer_importance('macro', 'policy', '某部门关于开展内部培训的通知') == 2


# ────────────────────── 词表纪律（实测踩坑回归） ──────────────────────

@pytest.mark.parametrize('title,expected', [
    # 2026-09-11 实测：'业绩预增' 未入表时被判成 other，漏掉财报事件
    ('2026年半年度业绩预增公告', EventType.EARNINGS),
    # 2026-09-11 实测：POLICY 词表含 '公告/决定/规定' 会把事故公告判成 policy
    (EM_TITLE, EventType.REGULATORY),
    # 2026-09-11 实测：POLICY 词表含 '通知/管理办法' 会误判公司公告（14 条）
    ('关于获得《药品补充申请批准通知书》的公告', EventType.OTHER),
    ('关于公司高级管理人员薪酬管理办法的公告', EventType.OTHER),
    ('国务院关于印发XX的通知', EventType.POLICY),
])
def test_事件类型词表不得把公司公告误判为政策(title, expected):
    assert infer_event_type(title) == expected


def test_空标题回落到默认类型而不是抛错():
    assert infer_event_type('') == EventType.OTHER


# ─────────────────────────── 范围与影响判定 ───────────────────────────

def test_有标的即判为个股_无标的政策按行业关键词判范围():
    assert infer_scope('任何标题', EventType.REGULATORY, ['600150']) == EventScope.INDIVIDUAL
    assert infer_scope('工业和信息化部关于印发光伏行业规范条件的通知', EventType.POLICY, []) == \
        EventScope.INDUSTRY
    assert infer_scope('国务院办公厅关于做好某项工作的通知', EventType.POLICY, []) == EventScope.MACRO


def test_宏观事件影响所有标的_行业事件不猜标的():
    macro = _event('国务院政策', 80, 'gov_policy', scope=EventScope.MACRO, type=EventType.POLICY)
    industry = _event('光伏行业政策', 80, 'gov_policy', scope=EventScope.INDUSTRY,
                      type=EventType.POLICY, symbols=[])
    individual = _event('公告', 60, 'eastmoney_notice', symbols=['600150'])
    assert macro.affects('600150') is True
    assert industry.affects('600150') is False, '行业→标的需要调用方显式映射，领域层不猜'
    assert individual.affects('600150') is True
    assert individual.affects('000001') is False
    assert MarketEventService.affects([macro, individual], '600150') == [macro, individual]


def test_is_upcoming含今天且不含已过去的事件():
    today = date.today()
    feb = lambda d: (today + timedelta(days=d)).strftime('%Y-%m-%d')
    event = _event('公告', 60, 'eastmoney_notice', effective_date=feb(3))
    assert event.is_upcoming(7) is True
    assert event.is_upcoming(1) is False
    assert _event('公告', 60, 'e', effective_date=feb(0)).is_upcoming(0) is True
    assert _event('公告', 60, 'e', effective_date=feb(-1)).is_upcoming(30) is False


# ───────────────────────── 盯盘建议（只建议不代建） ─────────────────────────

def test_只对解禁与财报且即将发生的个股事件给出盯盘建议():
    today = date.today()
    soon = (today + timedelta(days=5)).strftime('%Y-%m-%d')
    later = (today + timedelta(days=400)).strftime('%Y-%m-%d')
    unlock = _event('600176 限售股解禁：定向增发', 50, 'akshare_unlock',
                    type=EventType.UNLOCK, effective_date=soon, symbols=['600176'])
    far = _event('600176 限售股解禁', 50, 'akshare_unlock',
                 type=EventType.UNLOCK, effective_date=later, symbols=['600176'])
    dividend = _event('分红公告', 60, 'eastmoney_notice',
                      type=EventType.DIVIDEND, effective_date=soon, symbols=['600176'])
    suggestions = MarketEventService.watch_suggestions([unlock, far, dividend], days=30)
    assert len(suggestions) == 1
    item = suggestions[0]
    assert item['symbol'] == '600176' and item['event_type'] == 'unlock'
    assert item['auto_created'] is False, '只产建议，建规则必须经人/agent 复核'
    assert item['suggested_condition']


def test_盯盘建议不自动编造阈值_无价格线索时用占位条件():
    soon = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
    plain = _event('财报', 60, 'eastmoney_notice', type=EventType.EARNINGS,
                   effective_date=soon, symbols=['600150'])
    hinted = _event('财报', 60, 'eastmoney_notice', type=EventType.EARNINGS,
                    effective_date=soon, symbols=['600150'])
    hinted.raw = {'price_hint': 12.5}
    assert MarketEventService.watch_suggestions([plain])[0]['suggested_condition'] == 'price>0'
    assert MarketEventService.watch_suggestions([hinted])[0]['suggested_condition'] == 'price<12.5'


# ───────────────────────────── 源权威度 ─────────────────────────────

def test_权威度显式值优先_未知源取最低档之上():
    assert source_authority('cninfo_disclosure') == AUTHORITY_CNINFO
    assert source_authority('cninfo_disclosure', 42) == 42
    assert source_authority('unknown_source') == 21
    assert source_authority(None) == 21
