"""巨潮资讯 provider 契约测试（monkeypatch 模块级 session，不触网）

锁住的契约：
  <em> 高亮标签必须剥掉；毫秒时间戳按 UTC+8 换算（不依赖运行机时区）
  **主路径必须是 stock=<code>,<orgId>**（orgId 由 topSearch 解析）；
  searchkey 全文检索只是回退路径，且回退必须可见（回归：searchkey=000001 会命中
  一堆「公告编号里含 000001」的别家公告 → 过滤后 0 条 → 被当成「这只票没公告」）
  announcements 缺失：totalAnnouncement=0 视为该窗口无公告（空结果），>0 视为上游改版（故障）
  截断必须标注

⚠️ 2026-09-14（w-32314d00）修测试与实现的**脱节**：
    本文件写在 d2ffb396，而 provider 在 b640cf0c 引入了 orgId 解析 —— 此后**每只标的是
    两次 HTTP**（topSearch 解析 orgId + hisAnnouncement 查询），测试仍只喂一个响应：
      · 第一个用例就必然耗尽 fake（AssertionError）→ 被外层 except 吞成 None；
      · 而它把 orgId 写进了**模块级**失败缓存，后续用例于是静默走 searchkey 回退路径 ——
        **测试"通过"，但测的根本不是主路径**（这正是这个 provider 自身要防的静默少收模式，
        只不过发生在测试层）。故本版：① 按真实调用序列喂响应；② 加 autouse 夹具清缓存；
        ③ 显式补两条用例分别锁住主路径与回退路径。
"""
import pytest

from adapters.outbound.datasources.providers.events import cninfo_disclosure as mod
from adapters.outbound.datasources.providers.events.cninfo_disclosure import (
    _MAX_SYMBOLS, CninfoDisclosureProvider, _ms_to_date, _strip_tags,
)

from _fakes import FakeResponse, FakeSession

# 实测响应中的 announcementTime（2026-09-11 的公告）
MS_2026_09_11 = 1789126467000

# 实测：600150 中国船舶 -> gssh0600150（orgId 无法按规则推导，必须查 topSearch）
ORG_600150 = 'gssh0600150'


def _item(**overrides):
    item = {
        'secCode': '600150',
        'secName': '<em>中国船舶</em>',
        'orgId': ORG_600150,
        'announcementId': '1225558999',
        'announcementTitle': '关于北海造船厂一货轮火灾事故有关情况的公告',
        'announcementTime': MS_2026_09_11,
        'adjunctUrl': 'finalpage/2026-09-11/1225558999.PDF',
        'adjunctType': 'PDF',
        'pageColumn': 'SZCY',
    }
    item.update(overrides)
    return item


def _org_resp(symbol, org=ORG_600150):
    """topSearch/query 的响应替身：**数组**，元素含 code / orgId（按实测形状）"""
    return FakeResponse([{'code': symbol, 'orgId': org, 'zwjc': '中国船舶'}])


def _ok_resp(items=None, total=1):
    return FakeResponse({'announcements': items if items is not None else [_item()],
                         'totalAnnouncement': total})


def _provider(monkeypatch, responses):
    provider = CninfoDisclosureProvider(timeout=1)
    fake = FakeSession(responses)
    monkeypatch.setattr(mod, '_session', lambda: fake)
    return provider, fake


@pytest.fixture(autouse=True)
def _clear_org_cache():
    """orgId 缓存是模块级全局，必须逐用例清理（见模块 docstring 的脱节说明）"""
    mod._ORG_CACHE.clear()
    mod._ORG_FAIL_CACHE.clear()
    yield
    mod._ORG_CACHE.clear()
    mod._ORG_FAIL_CACHE.clear()


def _ann_calls(fake):
    """只取 hisAnnouncement 查询调用（排除 topSearch）"""
    return [c for c in fake.calls if 'stock' in (c.get('data') or {})]


def test_毫秒时间戳按UTC8换算():
    """本机时区虽为 +08:00，但显式 +8h 才能保证换机器后日期不差一天。"""
    assert _ms_to_date(MS_2026_09_11) == '2026-09-11'
    assert _ms_to_date(0) == '' and _ms_to_date(None) == '' and _ms_to_date('abc') == ''


def test_高亮标签必须剥掉():
    assert _strip_tags('<em>中国船舶</em>') == '中国船舶'


def test_字段映射与URL拼接(monkeypatch):
    provider, _ = _provider(monkeypatch, [_org_resp('600150'), _ok_resp()])
    rows = provider.fetch_symbol_events(['600150'])
    assert len(rows) == 1
    row = rows[0]
    assert row['title'] == '关于北海造船厂一货轮火灾事故有关情况的公告'
    assert row['symbols'] == ['600150'] and row['scope'] == 'individual'
    assert row['effective_date'] == row['announce_date'] == '2026-09-11'
    assert row['url'] == 'http://static.cninfo.com.cn/finalpage/2026-09-11/1225558999.PDF'
    assert row['external_id'] == '1225558999'
    assert row['authority'] == 90
    assert row['raw']['secName'] == '中国船舶'


def test_主路径必须用stock带orgId(monkeypatch):
    """锁住 b640cf0c 修的静默少收：主路径是 stock=<code>,<orgId>，不是 searchkey。

    实测：stock=600150（不带 orgId）返回 0 条；searchkey=600150 是全文检索，
    会命中提及该代码的别家公告，过滤后可能一条不剩（平安银行就这样被静默吞掉）。
    """
    provider, fake = _provider(monkeypatch, [_org_resp('600150'), _ok_resp()])
    provider.fetch_symbol_events(['600150'])

    # 第 1 次调用是 topSearch 解析 orgId
    assert fake.calls[0]['url'] == mod._ORG_URL
    assert fake.calls[0]['data']['keyWord'] == '600150'

    # 第 2 次才是公告查询：stock 带 orgId，searchkey 必须为空
    ann = _ann_calls(fake)
    assert len(ann) == 1
    payload = ann[0]['data']
    assert payload['stock'] == '600150,' + ORG_600150
    assert payload['searchkey'] == ''
    assert payload['pageNum'] == 1


def test_orgId解析失败时必须回退且显式可见(monkeypatch):
    """解析失败 → 回退 searchkey（已知会少收），但**必须**记进 _fallback_symbols /
    truncation_note，不能静默当成"这只票没公告"。"""
    provider, fake = _provider(monkeypatch, [
        FakeResponse([]),                      # topSearch 返回空数组 = 没解析出 orgId
        _ok_resp(),                            # 回退路径的全文检索结果
    ])
    provider.fetch_symbol_events(['600150'])

    assert provider._fallback_symbols == ['600150']
    assert provider.truncation_note and '600150' in provider.truncation_note
    assert _ann_calls(fake)[0]['data']['searchkey'] == '600150'


def test_orgId失败缓存有TTL且命中时仍告警(monkeypatch, caplog):
    """失败**不得**被永久缓存并静默命中（原实现一次抖动 = 进程内永久降级且不再打日志）"""
    import time as _t

    provider, fake = _provider(monkeypatch, [
        FakeResponse([]), _ok_resp(),          # 第一次：解析失败 + 回退
    ])
    provider.fetch_symbol_events(['600150'])
    calls_after_first = len(fake.calls)

    # TTL 内：不再打上游，但每次都要留痕
    caplog.clear()
    with caplog.at_level('WARNING'):
        provider2, _ = _provider(monkeypatch, [FakeResponse([])])
        rows2 = provider2.fetch_symbol_events(['600150'])
    assert rows2 is None                     # fake 被耗尽 → 回退查询抛错 → fail-loud
    assert any('冷却' in r.message or '冷却' in r.getMessage() for r in caplog.records)

    # TTL 过期：必须重新尝试解析（而不是永远走回退）
    mod._ORG_FAIL_CACHE['600150'] = _t.monotonic() - mod._ORG_FAIL_TTL_SECONDS - 1
    provider3, fake3 = _provider(monkeypatch, [_org_resp('600150'), _ok_resp()])
    rows3 = provider3.fetch_symbol_events(['600150'])
    assert len(rows3) == 1
    assert fake3.calls[0]['url'] == mod._ORG_URL


def test_全文检索命中的其他公司公告必须被过滤(monkeypatch):
    """实测：searchkey=600150 会命中"提及该代码"的法律意见书等别家公告。

    主路径下仍按 secCode 过滤（防串号）——回退路径更依赖它。
    """
    items = [_item(), _item(secCode='000001', secName='平安银行',
                            announcementTitle='关于为600150提供担保的公告')]
    provider, _ = _provider(monkeypatch, [_org_resp('600150'), _ok_resp(items, total=2)])
    rows = provider.fetch_symbol_events(['600150'])
    assert [r['symbols'] for r in rows] == [['600150']]


def test_无公告时返回空列表而不是故障(monkeypatch):
    """totalAnnouncement=0 且 announcements 缺失 = 该窗口确实没有公告（空结果 ≠ 故障）。"""
    provider, _ = _provider(monkeypatch, [
        FakeResponse([]),                      # 该窗口无公告的标的，orgId 也可能解析不到
        FakeResponse({'announcements': None, 'totalAnnouncement': 0}),
    ])
    rows = provider.fetch_symbol_events(['600150'])
    assert rows == [] and provider.last_error is None


def test_结构异常时必须fail_loud(monkeypatch):
    """totalAnnouncement>0 但 announcements 缺失 = 上游改版，不能当成"没有公告"。"""
    provider, _ = _provider(monkeypatch, [
        _org_resp('600150'),
        FakeResponse({'announcements': None, 'totalAnnouncement': 22}),
    ])
    assert provider.fetch_symbol_events(['600150']) is None
    assert '结构异常' in provider.last_error


def test_HTTP非200显式失败(monkeypatch):
    provider, _ = _provider(monkeypatch, [
        FakeResponse({}, status=502),          # topSearch 502 → 回退
        FakeResponse({}, status=502),          # 查询也 502
    ])
    assert provider.fetch_symbol_events(['600150']) is None
    assert 'HTTP 502' in provider.last_error


def test_网络异常显式失败(monkeypatch):
    provider = CninfoDisclosureProvider(timeout=1)

    class _Boom:
        def post(self, *a, **kw):
            raise TimeoutError('read timeout')

    monkeypatch.setattr(mod, '_session', lambda: _Boom())
    assert provider.fetch_symbol_events(['600150']) is None
    assert 'TimeoutError' in provider.last_error


def test_缺标题或缺日期的行被丢弃(monkeypatch):
    items = [_item(), _item(announcementTitle='', announcementTime=0)]
    provider, _ = _provider(monkeypatch, [_org_resp('600150'), _ok_resp(items, total=2)])
    rows = provider.fetch_symbol_events(['600150'])
    assert [r['external_id'] for r in rows] == ['1225558999']


def test_标的数超上限必须标注截断(monkeypatch):
    symbols = ['%06d' % (600000 + i) for i in range(_MAX_SYMBOLS + 3)]
    responses = []
    for s in symbols[:_MAX_SYMBOLS]:
        responses.append(_org_resp(s))
        responses.append(_ok_resp([_item(secCode=s)], total=1))
    provider, fake = _provider(monkeypatch, responses)

    provider.fetch_symbol_events(symbols)

    assert provider.truncated_symbols == symbols[_MAX_SYMBOLS:]
    assert provider.truncation_note and symbols[-1] in provider.truncation_note
    # 断言"只检索了前 _MAX_SYMBOLS 只"——按**公告查询调用数**计（topSearch 也是一次 HTTP，
    # 但它是每标的必发的解析步骤，不能拿它当"检索次数"）
    assert len(_ann_calls(fake)) == _MAX_SYMBOLS


def test_不传标的时同时查深沪两栏(monkeypatch):
    provider, fake = _provider(monkeypatch, [
        FakeResponse({'announcements': [], 'totalAnnouncement': 0}),
        FakeResponse({'announcements': [], 'totalAnnouncement': 0}),
    ])
    provider.fetch_symbol_events(None)
    assert [c['data']['column'] for c in fake.calls] == ['szse', 'sse']


def test_不提供政策时返回空列表且不计故障():
    provider = CninfoDisclosureProvider(timeout=1)
    assert provider.fetch_policy() == [] and provider.last_error is None
