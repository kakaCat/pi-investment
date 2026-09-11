"""events_for_symbol 覆盖状态回报（2026-09-11，w-f436d4ea）

背景：个股事件通道**只采集 default_universe**（持仓 ∪ 启用中的盯盘规则）。实测
quant.event_calendar 的 individual 事件只覆盖 **24 只标的**，池外标的（如 600176）
调用 stock_events 只能拿到宏观事件。原实现对此不做任何说明，调用方无法区分：
    · 在池内且无个股事件 → **确实没有**（排雷可放心）
    · 不在池内           → **未知**（是"没抓过"，不是"没有"）
对"买入前排雷（解禁/减持/定增）"这一用途，把两者混成同一个空结果 = 拿"没查"冒充
"没问题"。本测试锁住覆盖状态必须如实回报。

不触网不写库：仓储为桩。
"""
import pytest

from application.services.event_feed_service import EventFeedService


def _macro_row(title='2026年9月 CPI/PPI 发布'):
    return {'title': title, 'type': 'cpi_ppi', 'scope': 'macro',
            'effective_date': '2026-09-11', 'announce_date': '', 'symbols': [],
            'industries': [], 'source': 'nbs', 'url': '', 'summary': '', 'raw': {}}


def _individual_row(symbol='600176', title='600176 限售股解禁：定向增发机构配售股份'):
    return {'title': title, 'type': 'unlock', 'scope': 'individual',
            'effective_date': '2026-09-20', 'announce_date': '', 'symbols': [symbol],
            'industries': [], 'source': 'akshare_unlock', 'url': '', 'summary': '',
            'raw': {}}


class _Repo:
    def __init__(self, rows=(), covered=None, boom=False):
        self._rows, self._covered, self._boom = list(rows), covered, boom

    def for_symbol(self, symbol, limit=50):
        return list(self._rows)

    def is_in_default_universe(self, symbol):
        if self._boom:
            raise RuntimeError('db down')
        return self._covered


def _call(rows=(), covered=None, boom=False):
    return EventFeedService(manager=None, repository=_Repo(rows, covered, boom)) \
        .events_for_symbol('600176')


def test_池内标的回报covered且无额外提示():
    out = _call(rows=[_individual_row()], covered=True)
    assert out['success'] is True
    assert out['individual_coverage'] == 'covered'
    assert out['note'] is None


def test_池外标的必须回报not_covered并说明是未采集():
    out = _call(rows=[_macro_row()], covered=False)
    assert out['individual_coverage'] == 'not_covered'
    assert out['note'] and '未采集' in out['note']
    assert '确实没有' in out['note'], '必须点明与「确实没有」的区别'
    assert 'watch_manage' in out['note'], '要给出可行动出路'


def test_池外但确有个股事件时不得声称不含个股事件():
    """边界：持仓/盯盘规则变动后可能残留池外事件——此时文案不能自相矛盾。"""
    out = _call(rows=[_macro_row(), _individual_row()], covered=False)
    assert out['individual_coverage'] == 'not_covered'
    assert out['note'] is None, '已有个股事件就不该再说「返回中不含个股事件」'


def test_覆盖检查失败时降级为unknown且不影响主结果():
    out = _call(rows=[_macro_row()], boom=True)
    assert out['success'] is True, '覆盖检查失败不得让主查询失败'
    assert out['individual_coverage'] == 'unknown'
    assert out['note'] is None
    assert out['count'] == 1


def test_仓储无该能力时也降级为unknown():
    """旧仓储/FakeRepo 没有 is_in_default_universe 时不得抛异常（并行窗口的既有测试）。"""
    class _Bare:
        def for_symbol(self, symbol, limit=50):
            return [_macro_row()]

    out = EventFeedService(manager=None, repository=_Bare()).events_for_symbol('600176')
    assert out['success'] is True
    assert out['individual_coverage'] == 'unknown'
