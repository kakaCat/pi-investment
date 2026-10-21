"""PolicyNewsSource 单测（2026-10-21 政策盯盘闭环）

覆盖验收判据：
  0. 成功 / 空 / 异常 fail-open / 字段归一 / 去重；
  1. 全市场新闻方法契约——只经 DataProviderManager.get_market_news()，不直连 akshare；
  2. 取数失败不得被当成「无利空」：skipped 如实标注，且与「健康空」可区分。
"""
import ast
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

# 机械验收用的 pytest 未必是装了 editable 包的 venv：按仓库布局兜底源码路径
# （等价的 pip install -e ./packages/*），让本文件在裸解释器下也能直接收集。
_PACKAGES = Path(__file__).resolve().parents[2] / 'packages'
if _PACKAGES.is_dir():
    for _pkg in sorted(_PACKAGES.iterdir()):
        if _pkg.is_dir() and (_pkg / _pkg.name).is_dir() and str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))

from qs_watch.application.services.watch_engine import policy_news_source  # noqa: E402
from qs_watch.application.services.watch_engine.policy_news_source import (  # noqa: E402
    DEFAULT_LIMIT,
    MAX_LIMIT,
    PolicyNewsSource,
)

_MODULE_PATH = Path(policy_news_source.__file__)


class _Manager:
    """假 DataProviderManager：记录调用、按需返回/抛错。"""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def get_market_news(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


def _payload(records):
    """真实 manager 成功时 data 是不剥壳的 MarketData（载荷在 .data）。"""
    return SimpleNamespace(
        data_type='market_news',
        data={'records': list(records), 'total': len(records)},
        source='akshare',
    )


def _result(records=None, *, source='akshare', success=True, **extra):
    out = {'success': success, 'source': source}
    if records is not None:
        out['data'] = _payload(records)
    out.update(extra)
    return out


# ── 判据 0：成功 / 字段归一 ────────────────────────────────────────────
def test_fetch_success_normalises_english_fields():
    manager = _Manager(_result([
        {'title': '央行宣布降准 0.5 个百分点', 'time': '2026-10-21 09:00:00',
         'source': '新华社', 'url': 'https://example.com/a'},
    ]))
    out = PolicyNewsSource(manager).fetch()

    assert out['skipped'] is False
    assert out['empty'] is False
    assert out['reason'] == ''
    assert out['provider'] == 'akshare'
    assert out['records'] == [{
        'title': '央行宣布降准 0.5 个百分点',
        'time': '2026-10-21 09:00:00',
        'source': '新华社',
        'url': 'https://example.com/a',
    }]
    assert out['fetched_at']
    datetime.fromisoformat(out['fetched_at'])   # 必须是可解析的 ISO 时间


def test_fetch_normalises_chinese_columns():
    """akshare 原始列名是中文——统一键必须能映射过去。"""
    manager = _Manager(_result([
        {'关键词': '降准', '新闻标题': '国常会部署稳增长政策',
         '发布时间': '2026-10-21 10:30:00', '文章来源': '证券时报',
         '新闻链接': 'https://example.com/b'},
    ]))
    out = PolicyNewsSource(manager).fetch()

    assert out['skipped'] is False
    record = out['records'][0]
    assert set(record) == {'title', 'time', 'source', 'url'}   # 只有统一四字段
    assert record['title'] == '国常会部署稳增长政策'
    assert record['time'] == '2026-10-21 10:30:00'
    assert record['source'] == '证券时报'
    assert record['url'] == 'https://example.com/b'


def test_fetch_accepts_plain_list_payload():
    """不同 manager 实现可能直接给 list（不套 MarketData/data.records）。"""
    manager = _Manager({'success': True, 'source': 'akshare',
                        'data': [{'title': '政策 A'}, {'title': '政策 B'}]})
    out = PolicyNewsSource(manager).fetch()
    assert [r['title'] for r in out['records']] == ['政策 A', '政策 B']
    assert out['skipped'] is False


def test_fetch_accepts_single_record_dict_payload():
    manager = _Manager({'success': True, 'source': 'akshare',
                        'data': {'title': '单条政策'}})
    out = PolicyNewsSource(manager).fetch()
    assert [r['title'] for r in out['records']] == ['单条政策']


def test_fetch_uses_provider_as_source_fallback():
    """文章来源缺失时用本次 provider 兜底（来源可追溯，而不是空串）。"""
    manager = _Manager(_result([{'title': '无来源政策'}]))
    out = PolicyNewsSource(manager).fetch()
    assert out['records'][0]['source'] == 'akshare'


def test_fetch_normalises_datetime_and_nan():
    manager = _Manager(_result([{
        'title': '带时间对象',
        '发布时间': datetime(2026, 10, 21, 11, 0),
        '文章来源': float('nan'),
    }]))
    out = PolicyNewsSource(manager).fetch()
    record = out['records'][0]
    assert record['time'] == '2026-10-21T11:00:00'
    assert record['source'] == 'akshare'   # NaN → 空 → provider 兜底


# ── 判据 0：去重 / 截断 ──────────────────────────────────────────────
def test_fetch_deduplicates_by_title_first_wins():
    manager = _Manager(_result([
        {'title': '央行降准', 'time': '09:00', 'source': '新华社',
         'url': 'https://example.com/first'},
        {'title': '  央行降准  ', 'time': '09:05', 'source': '转载',
         'url': 'https://example.com/second'},   # 同题不同源 → 只留首条
        {'title': '证监会答记者问', 'time': '09:10', 'source': '证监会'},
    ]))
    out = PolicyNewsSource(manager).fetch()

    assert len(out['records']) == 2
    assert out['records'][0]['title'] == '央行降准'
    assert out['records'][0]['url'] == 'https://example.com/first'
    assert out['records'][1]['title'] == '证监会答记者问'


def test_fetch_limit_truncates_after_dedup():
    manager = _Manager(_result([
        {'title': 'A'}, {'title': 'A'}, {'title': 'B'}, {'title': 'C'},
    ]))
    out = PolicyNewsSource(manager).fetch(limit=2)
    assert [r['title'] for r in out['records']] == ['A', 'B']

    # 非法 limit 退回默认，不静默返回 0 条
    out = PolicyNewsSource(manager).fetch(limit='bad')
    assert len(out['records']) == 3
    out = PolicyNewsSource(manager).fetch(limit=0)
    assert len(out['records']) == 3


def test_default_and_hard_limit():
    assert DEFAULT_LIMIT > 0 and MAX_LIMIT >= DEFAULT_LIMIT
    manager = _Manager(_result([{'title': 't%d' % i} for i in range(MAX_LIMIT + 20)]))
    out = PolicyNewsSource(manager).fetch(limit=10 ** 6)
    assert len(out['records']) == MAX_LIMIT


def test_records_drop_missing_title_but_keep_others():
    manager = _Manager(_result([
        {'title': '', 'time': '09:00'},
        {'新闻标题': '有效政策'},
        {'time': '09:05'},   # 连标题键都没有
    ]))
    out = PolicyNewsSource(manager).fetch()
    assert out['skipped'] is False
    assert [r['title'] for r in out['records']] == ['有效政策']


# ── 判据 0/2：空 / 异常 fail-open ─────────────────────────────────────
def test_fetch_healthy_empty_is_not_skipped():
    """源健康但无数据：empty=True、skipped=False（确实没有 ≠ 没取到）。"""
    manager = _Manager({'success': True, 'data': [],
                        'source': None, 'empty': True,
                        'empty_sources': ['akshare']})
    out = PolicyNewsSource(manager).fetch()

    assert out['records'] == []
    assert out['skipped'] is False
    assert out['empty'] is True
    assert out['reason']   # 空态要有原因，不能沉默
    assert out['attempted_sources'] == []


def test_fetch_exception_is_fail_open_and_skipped():
    manager = _Manager(error=RuntimeError('network down'))
    out = PolicyNewsSource(manager).fetch()   # 不得抛异常

    assert out['records'] == []
    assert out['skipped'] is True
    assert out['empty'] is False
    assert 'network down' in out['reason']
    assert 'RuntimeError' in out['reason']


def test_fetch_success_false_is_skipped_with_provider_errors():
    manager = _Manager({
        'success': False,
        'error': 'All data providers failed',
        'provider_errors': {'akshare': 'connection reset'},
        'attempted_sources': ['akshare'],
    })
    out = PolicyNewsSource(manager).fetch()

    assert out['skipped'] is True
    assert out['empty'] is False
    assert out['records'] == []
    assert 'All data providers failed' in out['reason']
    assert 'akshare=connection reset' in out['reason']
    assert out['attempted_sources'] == ['akshare']


def test_failure_never_looks_like_no_news():
    """判据 2：失败与「健康空」都返回 records=[]，但 skipped 必须能区分两者。"""
    failed = PolicyNewsSource(_Manager(error=RuntimeError('boom'))).fetch()
    healthy_empty = PolicyNewsSource(_Manager({'success': True, 'data': []})).fetch()

    assert failed['records'] == healthy_empty['records'] == []
    assert failed['skipped'] is True
    assert healthy_empty['skipped'] is False


@pytest.mark.parametrize('result, expected_reason', [
    (None, '非 dict'),
    ('garbage', '非 dict'),
    ({'data': []}, '缺少 success 标记'),
    ({'success': True}, 'data 为空'),
    ({'success': True, 'data': 'garbage'}, '不可识别'),
    ({'success': True, 'data': {'records': 'not-a-list'}}, '不是列表'),
    ({'success': True, 'data': {}}, '不可识别'),
    ({'success': True, 'data': {'records': [{'time': '09:00'}]}}, '均无法归一'),
])
def test_unusable_payloads_are_skipped_not_empty(result, expected_reason):
    out = PolicyNewsSource(_Manager(result)).fetch()
    assert out['skipped'] is True
    assert out['empty'] is False
    assert expected_reason in out['reason']


def test_manager_resolution_failure_is_fail_open(monkeypatch):
    def _boom():
        raise RuntimeError('manager unavailable')

    monkeypatch.setattr(policy_news_source, '_default_manager', _boom)
    out = PolicyNewsSource().fetch()   # 未注入 manager → 走默认解析

    assert out['skipped'] is True
    assert 'manager unavailable' in out['reason']


# ── 判据 1：只经 DataProviderManager 的契约 ──────────────────────────
def test_calls_data_provider_manager_get_market_news_only():
    manager = _Manager(_result([{'title': '契约测试'}]))
    PolicyNewsSource(manager).fetch()

    assert len(manager.calls) == 1
    args, kwargs = manager.calls[0]
    assert args == () and kwargs == {}   # 全市场口径就是无参调用（symbol 空）


def test_default_manager_is_resolved_lazily(monkeypatch):
    manager = _Manager(_result([{'title': '默认解析'}]))
    monkeypatch.setattr(policy_news_source, '_default_manager', lambda: manager)

    out = PolicyNewsSource().fetch()
    assert [r['title'] for r in out['records']] == ['默认解析']
    assert len(manager.calls) == 1


def test_module_never_imports_akshare_directly():
    """判据 1：源码层面不得直连 akshare（只能经 DataProviderManager）。"""
    tree = ast.parse(_MODULE_PATH.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert 'akshare' not in imported
    assert 'tushare' not in imported


# ── 政策口径（2026-10-21 实测修正：全市场新闻是个股/盘面快讯，政策浓度极低）──
class _PolicyManager(_Manager):
    """假 manager：额外实现 get_policy_news（新数据引擎口径）。"""

    def __init__(self, policy=None, policy_error=None, **kwargs):
        super().__init__(**kwargs)
        self._policy = policy
        self._policy_error = policy_error
        self.policy_calls = []

    def get_policy_news(self, limit=50):
        self.policy_calls.append(limit)
        if self._policy_error is not None:
            raise self._policy_error
        return self._policy


def test_fetch_prefers_policy_channel_and_skips_market():
    manager = _PolicyManager(
        policy=_result([{'title': '证监会：稳步推进注册制改革', 'time': '2026-10-21 09:00',
                         'source': '财联社电报', 'url': ''}]),
        result=_result([{'title': '盘面快讯', 'time': '', 'source': 'x', 'url': ''}]),
    )
    out = PolicyNewsSource(manager=manager, limit=10).fetch()
    assert out['channel'] == 'policy'
    assert out['records'][0]['title'].startswith('证监会')
    assert manager.policy_calls, '应调用政策方法'
    assert manager.calls == [], '政策成功时不得回落全市场口径'


def test_policy_hard_failure_falls_back_to_market():
    manager = _PolicyManager(
        policy=_result(None, success=False, error='akshare down'),
        result=_result([{'title': '盘面快讯', 'time': '', 'source': 'x', 'url': ''}]),
    )
    out = PolicyNewsSource(manager=manager, limit=10).fetch()
    assert out['channel'] == 'market'
    assert out['records'][0]['title'] == '盘面快讯'


def test_policy_healthy_empty_does_not_fall_back():
    """健康但为空 = 真的没有政策消息；回落全市场会把盘面快讯灌进来（噪音）。"""
    manager = _PolicyManager(
        policy=_result([]),
        result=_result([{'title': '盘面快讯', 'time': '', 'source': 'x', 'url': ''}]),
    )
    out = PolicyNewsSource(manager=manager, limit=10).fetch()
    assert out['channel'] == 'policy'
    assert out['records'] == [] and out['empty'] is True and out['skipped'] is False
    assert manager.calls == []


def test_policy_exception_falls_back_to_market():
    manager = _PolicyManager(
        policy_error=RuntimeError('boom'),
        result=_result([{'title': '盘面快讯', 'time': '', 'source': 'x', 'url': ''}]),
    )
    out = PolicyNewsSource(manager=manager, limit=10).fetch()
    assert out['channel'] == 'market' and out['records'][0]['title'] == '盘面快讯'
