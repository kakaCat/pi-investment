"""manager 旧适配方法（IDataProviderManager 形态）的空结果契约锁（2026-09-11，w-62dd5259）

背景：_try_providers 在「全源健康无数据」时返回 success=True + data=[]（四态契约的设计）。
这两个方法是**声明了具体返回类型**的旧接口：
    get_market_data(...) -> Optional[MarketData]
    get_stock_data(...)  -> Optional[StockData]
契约（domain/ports/datasource_ports.py 的 IDataProviderManager 声明）是「XxxData 或 None」。
若把空的 data 原样透出，isinstance(data, dict) 为假 → 返回空列表 → 调用方
「if md is None: 走降级」的判据失效（拿空列表当对象继续用）。故空数据必须落回 None。

三向断言（缺一不可）：健康空 → None；正常 dict → dataclass 实例；硬失败 → None。
全程不触网、不写库：被测方法的路由目标用实例属性替换为桩。

⚠️ 顺带记录（本轮未改，超范围）：MarketData/StockData 在
domain/models/market_data.py 与 adapters/outbound/datasources/models.py **各定义了一套同名
dataclass**，跨模块 isinstance 恒为假。manager 与 IDataProviderManager 端口统一用 domain 侧，
测试也必须用 domain 侧，否则会出现「repr 看着对、isinstance 却是 False」的假失败。
"""
from adapters.outbound.datasources.manager import DataProviderManager
# ⚠️ 必须用 domain 侧模型：manager 与 IDataProviderManager 端口都用 domain/models/market_data.py，
# 而 adapters/outbound/datasources/models.py 有**同名另一套** dataclass（isinstance 跨模块为假）
from domain.models.market_data import MarketData, StockData


def _manager(**routed):
    """轻量 manager：不跑 __init__（避免构造真实 provider 链/仓储），只装配被测路径"""
    m = DataProviderManager.__new__(DataProviderManager)
    for name, fn in routed.items():
        setattr(m, name, fn)
    return m


EMPTY = {'success': True, 'data': [], 'source': None, 'empty': True}
HARD_FAIL = {'success': False, 'error': 'All data providers failed',
             'provider_errors': {'p1': 'HTTP 503'}}


# ----------------------------- get_market_data -----------------------------

def test_市场数据健康空返回None而不是空列表():
    m = _manager(get_market_spot=lambda: dict(EMPTY))
    got = m.get_market_data('spot')
    assert got is None, '声明 Optional[MarketData]，健康空必须是 None（返回 [] 会让调用方判据失效）'
    assert got != [], '不得把空结果透出成空列表'


def test_市场数据硬失败返回None():
    m = _manager(get_market_news=lambda: dict(HARD_FAIL))
    assert m.get_market_data('news') is None


def test_市场数据有数据时构造dataclass():
    payload = {'data_type': 'sector', 'data': {'industries': [1, 2]}, 'source': 'test'}
    m = _manager(get_market_spot=lambda: {'success': True, 'data': dict(payload), 'source': 'p1',
                                          'empty': False})
    got = m.get_market_data('spot')
    assert isinstance(got, MarketData)
    assert got.data == {'industries': [1, 2]} and got.source == 'test'


def test_市场数据未知data_type返回None():
    assert _manager().get_market_data('不存在的类型') is None


# ----------------------------- get_stock_data -----------------------------

def test_个股基础数据健康空返回None而不是空列表():
    m = _manager(get_stock_info=lambda symbol: dict(EMPTY))
    got = m.get_stock_data('600176', 'info')
    assert got is None
    assert got != [], '声明 Optional[StockData]，健康空不得返回 []'


def test_个股基础数据硬失败返回None():
    m = _manager(get_news=lambda symbol: dict(HARD_FAIL))
    assert m.get_stock_data('600176', 'news') is None


def test_个股基础数据有数据时构造dataclass():
    payload = {'symbol': '600176', 'data_type': 'news', 'data': [{'title': 'x'}],
               'total': 1, 'source': 'test'}
    m = _manager(get_news=lambda symbol: {'success': True, 'data': dict(payload),
                                          'source': 'p2', 'empty': False})
    got = m.get_stock_data('600176', 'news')
    assert isinstance(got, StockData)
    assert got.symbol == '600176' and got.total == 1


def test_个股基础数据未知data_type返回None():
    assert _manager().get_stock_data('600176', '不存在的类型') is None
