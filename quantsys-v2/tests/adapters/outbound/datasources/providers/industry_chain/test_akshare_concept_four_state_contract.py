"""新浪行业成分 provider 的**四态契约**回归锁（2026-09-11，w-f436d4ea）

背景：本轮全仓统一空结果契约时，兄弟候选通道 eastmoney_delay_concept 已把
「该源没有这个板块」从真故障改为健康无数据；本通道当时仍是 `None + last_error`
（连 last_note 字段都没有），导致**两条候选通道对同一件事给出相反的故障语义**：
「板块名不存在」在通道①算真故障、在通道②算健康无数据 → 通道①健康分被打掉，
被挤出竞争。这正是 RFC 015 §1.5.1 禁止的「多源退化成单源」。

契约（与 manager._try_providers 的消费口径一致）：

    []   + last_error=None + last_note=<诊断>  → 健康无数据（不计故障、不打健康分）
    None + last_error=<原因>                   → 真故障
    None + last_error=None                     → ⚠️ 禁止（两头不靠）

另锁**长生命周期单例的状态不跨调用泄漏**：上一次的 last_note 不得挂到下一次的
真故障上，上一次的 last_error / last_channel 也不得残留到下一次调用。

全部离线：_sector_list / _sector_members 被 monkeypatch，不触网、不写库。
"""
import pytest

from adapters.outbound.datasources.providers.industry_chain.akshare_concept import (
    AkshareConceptProvider,
    _SECTOR_PREFIX,
)


@pytest.fixture
def provider():
    return AkshareConceptProvider()


_SECTORS = [
    {'label': 'new_blhy', 'sector': '玻璃行业', 'company_count': 2},
    {'label': 'new_cbzz', 'sector': '船舶制造', 'company_count': 3},
]
_MEMBERS = [
    {'symbol': '600176', 'name': '中国巨石', 'prefixed': 'sh600176',
     'price': 10.0, 'change_pct': 1.2},
]


def _stub(monkeypatch, p, sectors=None, members=None,
          sectors_exc=None, members_exc=None):
    def _list():
        if sectors_exc:
            raise sectors_exc
        return list(_SECTORS if sectors is None else sectors)

    def _members(label):
        if members_exc:
            raise members_exc
        return list(_MEMBERS if members is None else members)

    monkeypatch.setattr(p, '_sector_list', _list)
    monkeypatch.setattr(p, '_sector_members', _members)


# ─────────────── 健康无数据 vs 真故障：形状必须可分 ───────────────

def test_未命中板块是健康无数据而不是真故障(monkeypatch, provider):
    """核心回归：跨源命名差异（策展叫'造船'、新浪叫'船舶制造'）不是故障。

    修前行为：last_error=... + return None（被 manager 计真故障、打健康分、
    把本候选通道挤出竞争）。修后：[] + last_note，last_error 保持 None。
    """
    _stub(monkeypatch, provider)
    result = provider.get_chain('这个板块根本不存在')

    assert result == []
    assert provider.last_error is None
    assert provider.last_note and '没有' in provider.last_note


def test_清单取数失败是真故障(monkeypatch, provider):
    _stub(monkeypatch, provider, sectors_exc=RuntimeError('akshare boom'))
    result = provider.get_chain('玻璃行业')

    assert result is None
    assert provider.last_error and '清单取数失败' in provider.last_error
    assert provider.last_note == ''


def test_成分取数失败是真故障(monkeypatch, provider):
    _stub(monkeypatch, provider, members_exc=RuntimeError('sector_detail boom'))
    result = provider.get_chain('玻璃行业')

    assert result is None
    assert provider.last_error and '成分取数失败' in provider.last_error
    assert provider.last_note == ''


def test_板块无可用成分是健康无数据(monkeypatch, provider):
    """板块在、接口正常返回，只是没有成分——不是故障；且不得返回零成员节点。"""
    _stub(monkeypatch, provider, members=[])
    result = provider.get_chain('玻璃行业')

    assert result == []
    assert provider.last_error is None
    assert provider.last_note and '无可用成分' in provider.last_note


def test_命中且成分正常时返回节点行且不写诊断(monkeypatch, provider):
    _stub(monkeypatch, provider)
    result = provider.get_chain('玻璃行业')

    assert isinstance(result, list) and len(result) == 1
    node = result[0]
    assert node['chain_id'] == _SECTOR_PREFIX + 'new_blhy'
    assert node['node_id'] == 'sector:new_blhy'
    assert len(node['members']) == 1
    assert node['members'][0]['symbol'] == '600176'
    assert provider.last_error is None
    assert provider.last_note == ''


def test_不提供主营构成是健康空并说明结构性原因(provider):
    """结构性缺能力：既不是故障，也不是'这只票没有'。"""
    result = provider.get_revenue_exposure('600176')

    assert result == []
    assert provider.last_error is None
    assert provider.last_note and '结构性' in provider.last_note


# ─────────────── 长生命周期单例：状态不得跨调用泄漏 ───────────────

def test_健康空说明不泄漏到下一次真故障(monkeypatch, provider):
    """上一条消息里 best-practice 的反例：诊断挂错对象会误导排障。"""
    _stub(monkeypatch, provider)
    provider.get_chain('不存在的板块')
    assert provider.last_note  # 第一次确实写了说明

    _stub(monkeypatch, provider, sectors_exc=RuntimeError('boom'))
    provider.get_chain('玻璃行业')

    assert provider.last_error and '清单取数失败' in provider.last_error
    assert provider.last_note == ''


def test_上一次的真故障不残留到下一次健康空(monkeypatch, provider):
    _stub(monkeypatch, provider, sectors_exc=RuntimeError('boom'))
    provider.get_chain('玻璃行业')
    assert provider.last_error

    _stub(monkeypatch, provider)
    provider.get_chain('不存在的板块')

    assert provider.last_error is None
    assert provider.last_note


def test_未命中时复位last_channel不残留上次成功通道(monkeypatch, provider):
    """修前 last_channel 只写不复位：失败/未命中后仍显示上一次的成功通道。"""
    _stub(monkeypatch, provider)
    provider.get_chain('玻璃行业')
    assert provider.last_channel == 'sina_sector_detail'

    provider.get_chain('不存在的板块')
    assert provider.last_channel == ''


# ─────────────── list_chains 同口径 ───────────────

def test_list_chains成功时不写诊断(monkeypatch, provider):
    _stub(monkeypatch, provider)
    rows = provider.list_chains()

    assert len(rows) == 2
    assert provider.last_error is None
    assert provider.last_note == ''


def test_list_chains取数失败是真故障(monkeypatch, provider):
    _stub(monkeypatch, provider, sectors_exc=RuntimeError('boom'))
    result = provider.list_chains()

    assert result is None
    assert provider.last_error and '清单取数失败' in provider.last_error
    assert provider.last_note == ''
