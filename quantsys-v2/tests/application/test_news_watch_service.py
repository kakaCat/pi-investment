"""消息监控服务单测（2026-10-20 流程图 M/N）"""
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

# 机械验收用的 pytest 未必是装了 editable 包的 venv：按仓库布局兜底源码路径
# （等价的 pip install -e ./packages/*），让本文件在裸解释器下也能直接收集（2026-10-20）。
_PACKAGES = Path(__file__).resolve().parents[2] / 'packages'
if _PACKAGES.is_dir():
    for _pkg in sorted(_PACKAGES.iterdir()):
        if _pkg.is_dir() and (_pkg / _pkg.name).is_dir() and str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))

from qs_watch.application.services.watch_engine.news_watch_service import (  # noqa: E402
    NewsWatchService, classify, in_scan_window,
)

NOW = datetime(2026, 10, 20, 10, 0)   # 周二盘中


def _pos(symbols):
    class P:
        def get_all_positions(self, account):
            return [SimpleNamespace(symbol=s, shares_total=100) for s in symbols]
    return P()


class _News:
    def __init__(self, items):
        self._items = items

    def fetch_news(self, symbol, limit=20):
        item = self._items.get(symbol, [])
        if isinstance(item, Exception):
            raise item
        return item


class _Alerts:
    def __init__(self):
        self.seen = set()

    def record(self, symbol, title, words, tier):
        key = (symbol, title)
        if key in self.seen:
            return None
        self.seen.add(key)
        return {'symbol': symbol, 'title': title, 'tier': tier}

    def exists(self, symbol, title):
        return (symbol, title) in self.seen

    def recent(self, limit=50):
        return []


_DEFAULT_POS = object()


def _svc(items, symbols=('300750',), sender=None, alerts=None,
         position_repo=_DEFAULT_POS):
    return NewsWatchService(
        news_source=_News(items),
        alert_repo=alerts if alerts is not None else _Alerts(),
        position_repo=(_pos(symbols) if position_repo is _DEFAULT_POS
                       else position_repo),
        sender=sender, interval_sec=60)


def test_classify_tiers():
    assert classify('证监会立案：公司涉嫌信息披露违规')[0] == 'critical'
    assert classify('股东拟减持不超过2%股份')[0] == 'soft'
    assert classify('业绩说明会纪要发布')[0] == 'none'      # 噪声词降级
    assert classify('关于召开业绩说明会的公告')[0] == 'none'
    assert classify('收到警示函 同时被立案调查')[0] == 'critical'  # critical 压过噪声词


def test_window():
    assert in_scan_window(datetime(2026, 10, 20, 8, 30))
    assert in_scan_window(datetime(2026, 10, 20, 21, 59))
    assert not in_scan_window(datetime(2026, 10, 20, 23, 0))
    assert not in_scan_window(datetime(2026, 10, 18, 10, 0))   # 周日


def test_critical_hit_sends_p0_card_once():
    sent = []
    items = {'300750': [{'title': '宁德时代：实控人收到证监会立案告知书',
                         'time': '2026-10-20 09:30:00', 'source': 'cninfo', 'url': ''}]}
    svc = _svc(items, sender=lambda p: sent.append(p) or True)
    out = svc.scan(now=NOW)
    assert out['scanned'] and out['reported'] == 1
    assert sent and sent[0]['level'] == 'P0'
    assert '立案' in sent[0]['message']
    # 同一条第二轮不再报（留痕幂等）
    out2 = svc.scan(now=NOW.replace(minute=20))
    assert out2['reported'] == 0


def test_soft_hit_p2_and_throttle():
    sent = []
    items = {'300750': [{'title': '股东拟减持不超过1%股份',
                         'time': '2026-10-20 09:00:00', 'source': '', 'url': ''}]}
    svc = _svc(items, sender=lambda p: sent.append(p) or True)
    out = svc.scan(now=NOW)
    assert out['reported'] == 1 and sent[0]['level'] == 'P2'
    out2 = svc.scan(now=NOW.replace(second=30))   # 60s 节流内
    assert out2['scanned'] is False


def test_news_source_failure_skips_symbol():
    class _Bad:
        def fetch_news(self, symbol, limit=20):
            raise RuntimeError('东财挂了')
    svc = NewsWatchService(news_source=_Bad(), alert_repo=_Alerts(),
                           position_repo=_pos(('300750',)), sender=None, interval_sec=60)
    out = svc.scan(now=NOW)
    assert out['errors'] == 1 and out['reported'] == 0   # 不炸整轮


def test_stale_news_ignored():
    sent = []
    items = {'300750': [{'title': '股东拟减持',
                         'time': '2026-10-10 09:00:00', 'source': '', 'url': ''}]}  # 10天前
    svc = _svc(items, sender=lambda p: sent.append(p) or True)
    out = svc.scan(now=NOW)
    assert out['reported'] == 0


# ── 候选池口径（机会闭环 M2 二次核验，2026-10-20）──────────────────

def _n(title, time='2026-10-20 09:30:00', source='cninfo', url=''):
    return {'title': title, 'time': time, 'source': source, 'url': url}


def test_query_negative_news_single_symbol_critical():
    alerts = _Alerts()
    sent = []
    items = {'300750': [
        _n('宁德时代：实控人收到证监会立案告知书'),
        _n('股东拟减持不超过1%股份', time='2026-10-20 09:00:00'),
        _n('关于召开业绩说明会的公告', time='2026-10-20 08:30:00'),
        _n('股东拟减持', time='2026-10-10 09:00:00'),          # 超 48h
    ]}
    svc = _svc(items, alerts=alerts, sender=lambda p: sent.append(p) or True)
    out = svc.query_negative_news('300750.SZ', now=NOW)

    assert out['symbol'] == '300750'            # 统一裸代码
    assert out['has_negative'] is True and out['tier'] == 'critical'
    assert out['total'] == 4 and out['checked'] == 3   # 陈旧条目不参与判定
    assert out['skipped'] is False and out['error'] is None
    assert out['hits'] and all(h['tier'] == 'critical' for h in out['hits'])
    assert '立案' in out['hits'][0]['words']
    assert out['hits'][0]['title'].startswith('宁德时代')
    # 只读口径：不发卡、不写持仓留痕
    assert sent == []
    assert alerts.seen == set()


def test_query_negative_news_clean_and_fail_open():
    items = {
        '600000': [_n('关于召开业绩说明会的公告')],
        '000001': RuntimeError('东财挂了'),
    }
    svc = _svc(items)
    clean = svc.query_negative_news('600000', now=NOW)
    assert clean['has_negative'] is False and clean['tier'] == 'none'
    assert clean['hits'] == [] and clean['checked'] == 1

    bad = svc.query_negative_news('000001', now=NOW)
    assert bad['skipped'] is True and bad['error'] == '东财挂了'
    assert bad['has_negative'] is False          # fail-open：不因取数故障冤枉标的

    empty = svc.query_negative_news('', now=NOW)
    assert empty['skipped'] is True and empty['error'] == '空标的'


def test_scan_candidates_summary_and_holdings_isolation():
    alerts = _Alerts()
    sent = []
    items = {
        '300750': [_n('实控人收到证监会立案告知书')],          # critical
        '000001': [_n('股东拟减持不超过1%股份')],              # soft
        '600000': [_n('业绩说明会纪要')],                      # none（噪声词）
        '600519': [_n('股东拟减持', time='2026-10-10 09:00:00')],  # 陈旧 → none
        '000002': RuntimeError('限流'),                        # 取数失败 → skipped
    }
    svc = _svc(items, symbols=('300750',), alerts=alerts,
               sender=lambda p: sent.append(p) or True)

    out = svc.scan_candidates(
        ['300750.SZ', '000001', '600000', '600519', '000002',
         '300750', None, ''], now=NOW)

    assert out['scanned'] is True and out['mode'] == 'candidate_pool'
    assert out['symbols'] == 5                   # 去重 + 空值忽略
    assert (out['negative'], out['critical'], out['soft']) == (2, 1, 1)
    assert out['clean'] == 2 and out['skipped'] == 1
    by_sym = {d['symbol']: d for d in out['details']}
    assert by_sym['300750']['tier'] == 'critical'
    assert by_sym['000001']['tier'] == 'soft'
    assert by_sym['000002']['skipped'] is True
    # 候选池口径不碰持仓留痕、不发卡、不占持仓扫描的节流
    assert alerts.seen == set()
    assert sent == []
    assert svc._last_scan_at is None

    # 之后的持仓扫描仍按原口径报卡（候选池模式没有污染幂等键）
    held = svc.scan(now=NOW)
    assert held['scanned'] is True and held['reported'] == 1
    assert sent and sent[0]['level'] == 'P0'
    assert ('300750', '实控人收到证监会立案告知书') in alerts.seen


def test_scan_candidates_without_position_repo():
    items = {'300750': [_n('收到警示函')]}
    svc = _svc(items, alerts=_Alerts(), position_repo=None)
    out = svc.scan_candidates(['300750'], now=NOW)
    assert out['negative'] == 1 and out['soft'] == 1


def test_scan_candidates_accepts_single_symbol_string():
    """单个代码字符串也按「一个标的」处理，不被逐字符拆开。"""
    items = {'300750': [_n('收到警示函')]}
    svc = _svc(items)
    out = svc.scan_candidates('300750.SZ', now=NOW)
    assert out['symbols'] == 1 and out['soft'] == 1
    assert [d['symbol'] for d in out['details']] == ['300750']


def test_query_negative_news_soft_only_and_ignores_scan_window():
    """单标的查询是只读口：不看运行窗口、不做节流；soft 命中同样算利空。"""
    items = {'300750': [_n('股东拟减持不超过1%股份')]}
    svc = _svc(items)

    sunday_late = datetime(2026, 10, 18, 23, 30)   # 不在持仓扫描窗口
    out = svc.query_negative_news('300750.SZ', now=sunday_late)
    assert out['has_negative'] is True and out['tier'] == 'soft'
    assert [w for h in out['hits'] for w in h['words']] == ['减持']
    # 反复问同一标的仍返回同样结论，且不占持仓扫描的节流
    assert svc.query_negative_news('300750.SZ', now=sunday_late)['has_negative'] is True
    assert svc._last_scan_at is None
    # 同一时刻持仓扫描仍按窗口拒绝（两种口径互不影响）
    assert svc.scan(now=sunday_late)['scanned'] is False
