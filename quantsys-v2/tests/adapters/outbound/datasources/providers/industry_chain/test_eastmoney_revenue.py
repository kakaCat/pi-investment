"""主营构成 provider 契约测试（fake session，不触网）

两条通道：
  EastmoneyRevenueProvider（东财 F10，带营收占比 = 归位硬证据）
  ThsRevenueProvider（同花顺 F10，产品构成文本 = 关键词证据，无占比）

锁住的契约：
  市场前缀映射（SH/SZ/BJ，无法识别 → 空串 + last_error，绝不猜）
  MAINOP_TYPE 口径（1=按行业 2=按产品 3=按地区）
  MBI_RATIO 已是小数（按百分数处理会差 100 倍）
  取数失败必须写 last_error（禁止静默降级成"无主营构成"）
  同花顺页面结构变化 → last_error（禁止静默返回空）
  **无数据 → [] + last_note**（2026-09-11 四态契约：None 是"真故障"专用形状，
  "这只票没有主营构成"必须走健康空，否则 manager 判不了故障也判不了空 → 降级链语义错乱）
"""
import pytest

from adapters.outbound.datasources.providers.industry_chain import eastmoney_revenue as mod
from adapters.outbound.datasources.providers.industry_chain.eastmoney_revenue import (
    EastmoneyRevenueProvider, ThsRevenueProvider, market_prefixed,
)

from _fakes import FakeResponse, FakeSession


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """provider 失败重试之间 sleep(0.4)：测试里去掉，保持毫秒级。"""
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)


# ─────────────────────────────── 市场前缀 ───────────────────────────────

@pytest.mark.parametrize('raw,expected', [
    ('600176', 'SH600176'), ('688111', 'SH688111'), ('900901', 'SH900901'),
    ('000001', 'SZ000001'), ('300750', 'SZ300750'), ('200011', 'SZ200011'),
    ('830799', 'BJ830799'), ('430047', 'BJ430047'),
    ('SH600176', 'SH600176'), ('600176.SH', 'SH600176'), ('sz000001', 'SZ000001'),
])
def test_市场前缀映射(raw, expected):
    assert market_prefixed(raw) == expected


@pytest.mark.parametrize('raw', ['', None, '60017', 'ABCDEF', '1234567', 'abcdef'])
def test_无法识别的代码返回空串由调用方fail_loud(raw):
    """6 位数字才映射；非数字/长度不符一律返回空串，由调用方 fail-loud（不猜市场）。"""
    assert market_prefixed(raw) == ''


# ────────────────────────── 东财 F10 主营构成 ──────────────────────────

def _payload(rows=None, **extra):
    payload = {'zygcfx': rows if rows is not None else [_zygcfx_row()], 'zyfw': [], 'jyps': []}
    payload.update(extra)
    return payload


def _zygcfx_row(**overrides):
    row = {
        'SECUCODE': '600176.SH', 'SECURITY_CODE': '600176',
        'REPORT_DATE': '2026-06-30 00:00:00', 'MAINOP_TYPE': '2',
        'ITEM_NAME': '玻纤及其制品相关', 'MAIN_BUSINESS_INCOME': 1.0,
        'MBI_RATIO': 0.973241, 'RANK': 1,
    }
    row.update(overrides)
    return row


def _em(monkeypatch, responses):
    session = FakeSession(responses)
    return EastmoneyRevenueProvider(session=session), session


def test_东财行映射与分类口径(monkeypatch):
    rows = [_zygcfx_row(),
            _zygcfx_row(MAINOP_TYPE='1', ITEM_NAME='玻璃纤维及制品', MBI_RATIO=0.9),
            _zygcfx_row(MAINOP_TYPE='3', ITEM_NAME='华东地区', MBI_RATIO=0.3),
            _zygcfx_row(MAINOP_TYPE='9', ITEM_NAME='未知口径', MBI_RATIO=0.1)]
    provider, session = _em(monkeypatch, FakeResponse(_payload(rows)))
    out = provider.get_revenue_exposure('600176')
    assert [r['classification'] for r in out] == ['按产品分类', '按行业分类', '按地区分类', '未分类']
    assert out[0]['report_date'] == '2026-06-30'
    assert out[0]['ratio'] == pytest.approx(0.973241), 'MBI_RATIO 已是小数，不得再除 100'
    assert out[0]['item'] == '玻纤及其制品相关'
    assert out[0]['source'] == 'eastmoney_revenue'
    assert session.calls[0]['params'] == {'code': 'SH600176'}


def test_无主营构成数据时返回空列表加last_note而不是None(monkeypatch):
    """该标的确实没有主营构成 ≠ 取数失败：返回 **[] + last_note**，不是 None。

    四态契约（2026-09-11）：[] + last_note = 健康无数据（manager 计入 empty_sources，
    不计故障、不影响熔断，并继续降级下一源）；None + last_error = 真故障。
    返回 None 却不写 last_error 属"两头不靠"，会被 manager 记成"非空但无效"。
    """
    provider, _ = _em(monkeypatch, FakeResponse(_payload([])))
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_error is None
    assert 'zygcfx' in provider.last_note and '为空' in provider.last_note


def test_无法识别的代码直接返回None并写明原因(monkeypatch):
    provider, session = _em(monkeypatch, FakeResponse(_payload()))
    assert provider.get_revenue_exposure('ABCDEF') is None
    assert provider.last_error and '市场前缀' in provider.last_error
    assert session.calls == [], '不合法代码不得打上游'


def test_取数全失败必须写last_error并重试三次(monkeypatch):
    """本机代理对东财时好时坏：单次失败就降级会白丢带占比的硬证据。"""
    session = FakeSession([FakeResponse(status=502), FakeResponse(status=502),
                           FakeResponse(status=502)])
    provider = EastmoneyRevenueProvider(session=session)
    assert provider.get_revenue_exposure('600176') is None
    assert len(session.calls) == 3
    assert provider.last_error and '取数失败' in provider.last_error


def test_代理失败后直连重试成功(monkeypatch):
    session = FakeSession([FakeResponse(status=502), FakeResponse(_payload())])
    provider = EastmoneyRevenueProvider(session=session)
    rows = provider.get_revenue_exposure('600176')
    assert rows and len(session.calls) == 2
    assert session.calls[1]['proxies'] == {'http': None, 'https': None}


def test_响应结构异常必须写last_error(monkeypatch):
    provider, _ = _em(monkeypatch, FakeResponse(['not', 'a', 'dict']))
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_error and '结构异常' in provider.last_error


def test_经营范围读取(monkeypatch):
    payload = _payload([], zyfw=[{'BUSINESS_SCOPE': '玻璃纤维及制品的生产、销售。'}])
    provider, _ = _em(monkeypatch, FakeResponse(payload))
    assert provider.business_scope('600176') == '玻璃纤维及制品的生产、销售。'


def test_不提供拓扑与清单时返回空列表(monkeypatch):
    provider, _ = _em(monkeypatch, FakeResponse(_payload()))
    assert provider.list_chains() == []
    assert provider.get_chain('玻纤') == []
    assert provider.last_error is None


# ────────────────────────── 同花顺 F10 产品构成 ──────────────────────────

THS_HTML = (
    '<span class="hltip f12">主营业务：</span><p>玻璃纤维及制品的生产、销售。</p>'
    '<span class="hltip f12">产品类型：</span><p>玻纤纱及制品</p>'
    '<span class="hltip f12">产品名称：</span><p>电子布、粗纱及制品</p>'
    '<span class="hltip f12">经营范围：</span><p>玻璃纤维、复合材料的生产（依法须经批准的项目）</p>'
)


def _ths(monkeypatch, responses):
    session = FakeSession(responses)
    return ThsRevenueProvider(session=session), session


def _ths_response(html=THS_HTML):
    return FakeResponse(content=html.encode('gbk'), text='')


def test_同花顺产品构成解析与拆分规则(monkeypatch):
    provider, _ = _ths(monkeypatch, _ths_response())
    rows = provider.get_revenue_exposure('600176')
    by_field = {}
    for row in rows:
        by_field.setdefault(row['field'], []).append(row['item'])
    assert '电子布' in by_field['产品名称'] and '粗纱及制品' in by_field['产品名称']
    assert by_field['产品类型'] == ['玻纤纱及制品'], '产品类型是整句不按顿号拆'
    assert by_field['主营业务'] == ['玻璃纤维及制品的生产、销售'], '主营业务不拆（拆了会得到"销售"碎片）'
    assert all(r['ratio'] is None for r in rows), '文本证据没有占比'
    assert all(r['classification'] in ('产品构成', '主营业务描述', '经营范围') for r in rows)


def test_同花顺页面结构变化必须写last_error(monkeypatch):
    """禁止静默返回空（那会让"页面改版"与"这只票没有产品构成"无法区分）。"""
    provider, _ = _ths(monkeypatch, _fake_ok_response('<html>改版了</html>'))
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_error and '结构变化' in provider.last_error


def _fake_ok_response(html):
    return FakeResponse(content=html.encode('gbk'), text='')


def test_同花顺代码带前后缀时先归一再取数(monkeypatch):
    provider, session = _ths(monkeypatch, _ths_response())
    rows = provider.get_revenue_exposure('SH600176.SH')
    assert rows and rows[0]['symbol'] == '600176'
    assert session.calls[0]['url'].endswith('/600176/operate.html')


def test_同花顺代码非法直接返回None且不打上游(monkeypatch):
    provider, session = _ths(monkeypatch, _ths_response())
    assert provider.get_revenue_exposure('abc') is None
    assert provider.last_error and '6 位' in provider.last_error
    assert session.calls == []


def test_同花顺取数失败写last_error(monkeypatch):
    provider, session = _ths(monkeypatch, [FakeResponse(status=500), FakeResponse(status=500)])
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_error and len(session.calls) == 2


def test_同花顺不提供拓扑(monkeypatch):
    provider, _ = _ths(monkeypatch, _ths_response())
    assert provider.list_chains() == [] and provider.get_chain('X') == []
