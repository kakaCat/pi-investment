"""东财延迟域概念/行业通道（eastmoney_delay_concept）契约与分页回归锁（2026-09-11，w-62dd5259）

本通道此前**从未被审查过**，本文件锁三组不变量：

1）分页与截断（静默截断是最危险的失败形态之一）
   - total 缺失时**必须继续翻页**（旧判据 len(rows) >= reported_total 在 total=0 时恒真 →
     只取第 1 页就静默停止，与 _fetch_boards 已修的 total=0 缺陷同源）；
   - total 明确时取够即停；本页不满一页即停；
   - 到达分页安全阀时必须 page_limited=True 且写进 evidence（不许静默丢成员）。

2）四态契约（与全仓统一）
   - 「该源没有这个板块」/「板块没有 A 股成分」= 健康无数据 → **[] + last_note**；
   - 清单/成分取数失败、结构不符 = 真故障 → None + last_error；
   - 长生命周期单例：last_error / last_note / last_channel 每次入口复位，不跨调用泄漏。

3）行契约（ports/IIndustryChainProvider）
   - evidence_kind ∈ {概念成分, 行业分类}，confidence ∈ {low, medium}（**绝不冒充 high/主营构成**）；
   - 不臆造成员数/占比；list_chains 行不得泄漏内部私有键。

全部离线：monkeypatch 模块级 requests.get（不发真实请求、不写库）。
"""
import pytest

from adapters.outbound.datasources.providers.industry_chain import eastmoney_delay_concept as mod
from adapters.outbound.datasources.providers.industry_chain.eastmoney_delay_concept import (
    EastmoneyDelayConceptProvider,
)


class StubResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def json(self):
        return self._payload


class StubRequests:
    """按 params 回放响应的假 requests 模块（模块级 monkeypatch，不触网）"""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, params=None, headers=None, proxies=None, timeout=None):
        self.calls.append(dict(params or {}))
        return StubResponse(self.handler(dict(params or {})))

    def pages(self, fs):
        return [c for c in self.calls if c.get('fs') == fs]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """去掉限流退避（≤3s）与翻页间隔（0.2s），测试保持毫秒级。"""
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)


def _patch(monkeypatch, handler):
    stub = StubRequests(handler)
    # 缝变更（2026-09-11，w-f436d4ea）：provider 改用进程级共享 Session 复用连接
    # （原先每次 requests.get 新建 TCP，连打数十次后上游/代理开始拒连）。
    # 必须同时：①把桩装到 _shared_session ②清掉模块级缓存 —— 少了②会把上一次
    # 真实 Session 从缓存里取回来，测试**静默真打上游**（比失败更危险：会「通过」）。
    monkeypatch.setattr(mod, '_SHARED_SESSION', None)
    monkeypatch.setattr(mod, '_shared_session', lambda: stub)
    monkeypatch.setattr(mod, 'requests', stub)
    return stub


# ─────────────────────────────── 数据构造 ───────────────────────────────

def _item(code, name, pct=1.23):
    return {'f12': code, 'f14': name, 'f3': pct}


def _a_rows(n, prefix='60'):
    return [_item(f'{prefix}{i:04d}', f'股{i:04d}') for i in range(n)]


def _board_list(kind, rows=None, total=None):
    if rows is None:
        rows = [_item('BK0546', '玻璃玻纤', 2.54)]
        if kind == 'concept':
            rows = [_item('BK0976', '被动元件概念', 2.54)]
    data = {'diff': rows}
    if total is not None:
        data['total'] = total
    return {'rc': 0, 'data': data}


def _members_payload(rows, total=None):
    data = {'diff': rows}
    if total is not None:
        data['total'] = total
    return {'rc': 0, 'data': data}


def _default_handler(members_handler=None):
    def handler(params):
        fs = params.get('fs')
        if fs == 'm:90+t:2':
            return _board_list('industry', total=1)
        if fs == 'm:90+t:3':
            return _board_list('concept', total=1)
        if fs and fs.startswith('b:'):
            return members_handler(params)
        raise AssertionError(f'未预期的 fs: {fs!r}')
    return handler


def _provider(monkeypatch, handler=None):
    stub = _patch(monkeypatch, handler or _default_handler())
    return EastmoneyDelayConceptProvider(), stub


# ══════════════════════════ 1) 分页与截断 ══════════════════════════

def test_total缺失时必须继续翻页而不是只取第一页(monkeypatch):
    """回归锁：total 缺失（=0）时旧判据 len(rows) >= 0 恒真 → 只取第 1 页就静默截断。"""
    page1, page2 = _a_rows(100), _a_rows(5, prefix='00')

    def members(params):
        return _members_payload(page1 if params['pn'] == 1 else page2)   # 不给 total

    provider, stub = _provider(monkeypatch, _default_handler(members))
    rows, total, page_limited = provider._fetch_members('BK0546')
    assert len(rows) == 105, f'total 缺失也必须翻到最后一页，实际 {len(rows)} 行'
    assert total == 0, '上游没给 total 就如实记 0（不臆造）'
    assert page_limited is False
    assert len(stub.pages('b:BK0546')) == 2, '必须请求了第 2 页'


def test_total明确时取够即停(monkeypatch):
    page1, page2 = _a_rows(100), _a_rows(5, prefix='00')

    def members(params):
        return _members_payload(page1 if params['pn'] == 1 else page2, total=105)

    provider, stub = _provider(monkeypatch, _default_handler(members))
    rows, total, page_limited = provider._fetch_members('BK0546')
    assert (len(rows), total, page_limited) == (105, 105, False)
    assert len(stub.pages('b:BK0546')) == 2, '取够即停，不该再打第 3 页'


def test_total含被过滤的非A段时判据用原始条目数(monkeypatch):
    """旧判据拿"过滤后的 A 股行数"去比"含 B 股的 total"，永远取不够 → 白打空页。"""
    page1 = _a_rows(98) + [_item('200012', '南玻B'), _item('900918', '耀皮B股')]

    def members(params):
        if params['pn'] == 1:
            return _members_payload(page1, total=100)
        raise AssertionError('原始条目数已达 total，不该再翻页')

    provider, stub = _provider(monkeypatch, _default_handler(members))
    rows, total, _ = provider._fetch_members('BK0546')
    assert len(rows) == 98, 'B 股必须被过滤'
    assert total == 100, 'total 是上游口径（含 B 股），如实透出'
    assert len(stub.pages('b:BK0546')) == 1


def test_分页触顶必须显式标注而不是静默截断(monkeypatch):
    provider, stub = _provider(
        monkeypatch,
        _default_handler(lambda params: _members_payload(_a_rows(100), total=5000)),
    )
    rows, total, page_limited = provider._fetch_members('BK0546')
    assert len(rows) == provider._MAX_PAGES * provider._PAGE_SIZE
    assert page_limited is True, '到安全阀时还有后续页 → 必须显式标注'
    assert total == 5000


def test_分页触顶会写进evidence与行字段(monkeypatch):
    provider, stub = _provider(
        monkeypatch,
        _default_handler(lambda params: _members_payload(_a_rows(100), total=5000)),
    )
    node = provider.get_chain('玻璃行业')[0]
    assert node['members_page_limited'] is True
    assert node['members_truncated'] is True
    assert '分页安全阀' in node['members'][0]['evidence'], '截断必须可追溯（evidence 里写明）'
    assert len(node['members']) == provider._MEMBER_CAP, '策略性上限仍然生效'


def test_策略性截断单独标注为按涨跌幅前N只(monkeypatch):
    provider, _ = _provider(
        monkeypatch,
        _default_handler(lambda params: _members_payload(_a_rows(150), total=150)),
    )
    node = provider.get_chain('玻璃行业')[0]
    assert node['members_page_limited'] is False
    assert node['members_truncated'] is True
    assert f'按涨跌幅截取前 {provider._MEMBER_CAP} 只' in node['members'][0]['evidence']


def test_change_pct非数值占位符归None不冒充数字(monkeypatch):
    rows = [_item('600176', '中国巨石', 10.02), _item('605006', '山东玻纤', '-')]
    provider, _ = _provider(monkeypatch, _default_handler(lambda p: _members_payload(rows, total=2)))
    members = provider.get_chain('玻璃行业')[0]['members']
    by_symbol = {m['symbol']: m['change_pct'] for m in members}
    assert by_symbol['600176'] == pytest.approx(10.02)
    assert by_symbol['605006'] is None, '上游占位值 - 必须归 None，不得当数字透出'


# ══════════════════════════ 2) 四态契约 ══════════════════════════

def test_该源没有这个板块是健康空不是故障(monkeypatch):
    provider, _ = _provider(monkeypatch)
    got = provider.get_chain('不存在的板块XYZ')
    assert got == [], '该源没有这条链 → []（健康无数据）'
    assert provider.last_error is None, '不得判故障（否则打掉健康分并挤出候选通道②）'
    assert '没有' in provider.last_note and 'XYZ' in provider.last_note


def test_板块无A股成分是健康空不是故障(monkeypatch):
    only_b = [_item('200012', '南玻B'), _item('900918', '耀皮B股')]
    provider, _ = _provider(
        monkeypatch, _default_handler(lambda p: _members_payload(only_b, total=2)))
    got = provider.get_chain('玻璃行业')
    assert got == []
    assert provider.last_error is None
    assert '无 A 股成分' in provider.last_note


def test_板块清单取数失败是真故障(monkeypatch):
    def boom(params):
        if params.get('fs', '').startswith('m:'):
            raise RuntimeError('HTTP 502')
        raise AssertionError('清单失败后不得继续取成分')

    provider, _ = _provider(monkeypatch, boom)
    assert provider.get_chain('玻璃行业') is None
    assert provider.last_error and '板块解析失败' in provider.last_error
    assert provider.last_note == ''


def test_单类清单失败时仍用另一类匹配成功(monkeypatch):
    """限流常态：industry 取数失败不该把整条候选通道判死（concept 还能回答）。"""
    def handler(params):
        fs = params.get('fs')
        if fs == 'm:90+t:2':
            raise RuntimeError('rc=102 疑似瞬时限流')
        if fs == 'm:90+t:3':
            return _board_list('concept', total=1)
        return _members_payload(_a_rows(2), total=2)

    provider, _ = _provider(monkeypatch, handler)
    node = provider.get_chain('BK0976')[0]
    assert node['chain_id'] == 'em_concept:BK0976'
    assert provider.last_error is None, '还有分类给出结果就不是故障'
    assert '部分板块类型取数失败' in provider.last_note


def test_成分取数失败是真故障(monkeypatch):
    def members(params):
        raise RuntimeError('HTTP 500')

    provider, _ = _provider(monkeypatch, _default_handler(members))
    assert provider.get_chain('玻璃行业') is None
    assert provider.last_error and '成分取数失败' in provider.last_error
    assert provider.last_note == ''


def test_list_chains全失败是真故障(monkeypatch):
    def boom(params):
        raise RuntimeError('rc=102 经代理被拒')

    provider, _ = _provider(monkeypatch, boom)
    assert provider.list_chains() is None
    assert provider.last_error and '全部取数失败' in provider.last_error


def test_list_chains部分失败返回数据且不写last_error(monkeypatch):
    def handler(params):
        if params.get('fs') == 'm:90+t:2':
            raise RuntimeError('行业清单 502')
        return _board_list('concept', total=1)

    provider, _ = _provider(monkeypatch, handler)
    rows = provider.list_chains()
    assert rows, '一半成功仍要返回数据（不静默丢通道）'
    assert provider.last_error is None, '返回了数据就不是失败，写 last_error 会自相矛盾'
    assert '部分' in provider.last_note and '行业清单 502' in provider.last_note


def test_健康空说明不跨调用泄漏到真故障(monkeypatch):
    state = {'fail': False}

    def handler(params):
        fs = params.get('fs')
        if fs and fs.startswith('m:') and state['fail']:
            raise RuntimeError('HTTP 502')
        if fs == 'm:90+t:2':
            return _board_list('industry', total=1)
        if fs == 'm:90+t:3':
            return _board_list('concept', total=1)
        return _members_payload(_a_rows(3), total=3)

    provider, _ = _provider(monkeypatch, handler)
    assert provider.get_chain('不存在的板块') == []
    assert provider.last_note, '第一次是健康空'
    assert provider.last_channel == '', '健康空路径没有真正取数，last_channel 必须复位为空'

    state['fail'] = True
    assert provider.get_chain('玻璃行业') is None
    assert provider.last_error
    assert provider.last_note == '', '真故障时不得残留上一次的"无数据"说明'


# ══════════════════════════ 3) 行契约与分级 ══════════════════════════

def test_成员行evidence_kind与confidence分级(monkeypatch):
    provider, _ = _provider(
        monkeypatch, _default_handler(lambda p: _members_payload(_a_rows(3), total=3)))
    node = provider.get_chain('玻璃行业')[0]
    member = node['members'][0]
    assert member['evidence_kind'] == '行业分类', '东财行业板块 → 行业分类'
    assert member['confidence'] == 'medium', '绝不冒充 high/主营构成'
    assert member['exposure_ratio'] is None and member['exposure_basis'] == '', '不臆造占比'
    assert member['source'] == 'eastmoney_delay_concept'
    assert member['stage'] == 'midstream' and member['role'] == ''
    assert node['chain_id'] == 'em_industry:BK0546'
    assert node['upstream_of'] == [] and node['downstream_of'] == []


def test_概念板块走概念分级(monkeypatch):
    def handler(params):
        fs = params.get('fs')
        if fs == 'm:90+t:2':
            return _board_list('industry', rows=[], total=0)   # 行业里没有 → 走概念
        if fs == 'm:90+t:3':
            return _board_list('concept', total=1)
        return _members_payload(_a_rows(2), total=2)

    provider, _ = _provider(monkeypatch, handler)
    node = provider.get_chain('BK0976')[0]
    assert node['chain_id'] == 'em_concept:BK0976'
    assert node['members'][0]['evidence_kind'] == '概念成分'
    assert node['members'][0]['confidence'] == 'low'


def test_list_chains行契约且不泄漏内部私有键(monkeypatch):
    provider, _ = _provider(monkeypatch)
    rows = provider.list_chains()
    assert rows, '两个 kind 都要有行'
    for row in rows:
        assert row['chain_id'].startswith(('em_industry:', 'em_concept:'))
        assert row['name'] and row['source'] == 'eastmoney_delay_concept'
        assert row['node_count'] == 1 and row['stale'] is False
        assert row['updated_at'], 'updated_at 必须有快照时点'
        assert row['member_count'] is None, '板块清单接口不返回成员数 → 不臆造'
        for private in ('_evidence_kind', '_confidence', '_stage'):
            assert private not in row, f'list_chains 行不得泄漏内部键 {private}'


def test_不提供主营构成返回空列表且状态复位(monkeypatch):
    provider, _ = _provider(monkeypatch)
    provider.last_error = '上一次的故障'
    provider.last_note = '上一次的说明'
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_error is None and provider.last_note == ''
