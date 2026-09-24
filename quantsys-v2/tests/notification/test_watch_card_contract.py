"""REQ-260924104605-ad0a t1 契约测试：WatchCardItem 扩展 / display 名称优先 /
StockNameResolver 端口可注入 / render_receipt 签名扩展。

契约卡的验收锚点（task t-cc7569 acceptance）：
  · 新字段默认值与 display 形态（名称（代码）/缺失降级）用例通过；
  · StockNameResolver 假实现可注入；
  · 既有用例结果与改前一致（不红）。
"""
from types import SimpleNamespace

from application.services.watch_engine.receipt_service import render_receipt
from domain.watch.ports import StockNameResolver
from infrastructure.notification.formatters.watch_level_templates import WatchCardItem


# ── WatchCardItem：新字段默认值（向后兼容——旧调用方一个都不传也不炸）────────
def test_card_item_new_fields_default():
    item = WatchCardItem(symbol='601888', price=51.79, action='进入买区评估建仓')
    assert item.intent == ''
    assert item.stage == ''
    assert item.purpose == ''
    assert item.plan_full == ''
    assert item.stop_loss is None
    assert item.take_profit is None
    assert item.validity_days is None
    assert item.source == ''


def test_card_item_display_name_first():
    """FR-13：名称在前「贵州茅台（600519）」。"""
    item = WatchCardItem(symbol='600519', name='贵州茅台', price=1500.0, action='加仓')
    assert item.display == '贵州茅台（600519）'


def test_card_item_display_name_missing_degrades():
    """FR-13：无名称如实降级「600519（名称缺失）」，不臆造。"""
    item = WatchCardItem(symbol='600519', price=1500.0, action='加仓')
    assert item.display == '600519（名称缺失）'


# ── StockNameResolver：假实现可注入（端口契约）─────────────────────────────
class _FakeResolver(StockNameResolver):
    def __init__(self, mapping):
        self._mapping = mapping

    def resolve_batch(self, symbols):
        return {str(s).split('.')[0].strip(): self._mapping.get(str(s).split('.')[0].strip())
                for s in symbols}


def test_stock_name_resolver_fake_injectable():
    fake = _FakeResolver({'601888': '中国中免'})
    got = fake.resolve_batch(['601888.SH', '601138'])
    assert got['601888'] == '中国中免'
    assert got['601138'] is None  # 未命中 = None（名称缺失降级，不臆造）


# ── render_receipt：签名扩展 + 名称渲染（旧调用兼容）─────────────────────────
def _todo(**over):
    base = dict(id=32, symbol='601888', level='P1', flow_state='L3',
                account='agent_virtual', due_at=None)
    base.update(over)
    return SimpleNamespace(**base)


def test_render_receipt_old_call_compatible():
    """旧调用形态（无新参数）仍渲染（REQ-ad0a t4 后文案为时间人性化一行形态）。"""
    text = render_receipt(_todo(), kind='timeout', period='L3|')
    assert '待办#32' in text
    assert '[超时]' in text


def test_render_receipt_name_first_display():
    text = render_receipt(_todo(), kind='timeout', period='L3|', name='中国中免')
    assert '中国中免（601888）' in text


def test_render_receipt_name_missing_degrades():
    text = render_receipt(_todo(), kind='timeout', period='L3|')
    assert '601888（名称缺失）' in text


def test_render_receipt_result_kwargs_accepted():
    """t5 的三要素参数已被契约接受（默认 None 不影响渲染）。"""
    text = render_receipt(_todo(), kind='result', period='handled|',
                          close_reason='破位放弃', next_condition='站回 22.80 再评估',
                          action_kind='ignore')
    assert '待办#32' in text
