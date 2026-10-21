"""政策盯盘路由服务单测（2026-10-21 政策盯盘闭环）

覆盖验收判据：
  0. 解析路由：命中板块 → 成分股 → ∩持仓/候选池；无关板块不打扰；
     映射缺失 fail-open（不据此判「与我无关」）；取数失败 ≠「无政策利空」。
  1. 装配：factory 起独立 daemon 扫描线程（不阻断启动、异常不杀线程）；
     引擎 bootstrap 照常返回句柄。
  2. 板块映射复用现有口径（policy_lexicon 的别名表 + sector_resonance_service 的
     板块取数适配/裸码归一/TTL），不维护第二份；只告警「与我有关」（候选池不发卡）。

设计纪律：所有外呼/落库依赖均以替身注入，单测零网络、零数据库。
"""
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

# 机械验收用的 pytest 未必是装了 editable 包的 venv：按仓库布局兜底源码路径
# （等价的 pip install -e ./packages/*），让本文件在裸解释器下也能直接收集。
_PACKAGES = Path(__file__).resolve().parents[2] / 'packages'
if _PACKAGES.is_dir():
    for _pkg in sorted(_PACKAGES.iterdir()):
        if _pkg.is_dir() and (_pkg / _pkg.name).is_dir() and str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))

from qs_watch.application.services.watch_engine import factory as factory_mod  # noqa: E402
from qs_watch.application.services.watch_engine import policy_lexicon as pl  # noqa: E402
from qs_watch.application.services.watch_engine import policy_watch_service as pw  # noqa: E402
from qs_watch.application.services.watch_engine import sector_resonance_service as sr  # noqa: E402
from qs_watch.application.services.watch_engine.policy_news_source import (  # noqa: E402
    PolicyNewsSource,
)
from qs_watch.application.services.watch_engine.policy_watch_service import (  # noqa: E402
    ACTION_ALERT,
    ACTION_CONFIRM,
    ACTION_SKIPPED,
    ACTION_UNRELATED,
    PolicyWatchService,
    SectorConstituentIndex,
)

NOW = datetime(2026, 10, 21, 14, 0)   # 周二盘中


# ── 替身 ─────────────────────────────────────────────────────

class _NewsSource:
    """假政策新闻源：fetch() 返回固定结构并记录调用次数。"""

    def __init__(self, out):
        self.out = out
        self.calls = 0

    def fetch(self, limit=None):
        self.calls += 1
        return self.out


class _SectorSource:
    """假板块端口（与 DataProviderManager 的 list_sectors/get_members 同形）。"""

    def __init__(self, members=None, *, boards=None, list_error=None,
                 member_error=None):
        self.members = dict(members or {})
        self.boards = list(boards) if boards is not None else list(self.members)
        self.list_error = list_error
        self.member_error = member_error
        self.calls = []

    def list_sectors(self):
        self.calls.append('<list>')
        if self.list_error is not None:
            raise self.list_error
        return list(self.boards)

    def get_members(self, board):
        self.calls.append(board)
        if self.member_error is not None:
            raise self.member_error
        return list(self.members.get(board, []))


class _Positions:
    """假持仓仓储：每个账户返回同一批行（Mapping 形状，_read 兼容）。"""

    def __init__(self, rows=None, *, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = []

    def get_all_positions(self, account):
        self.calls.append(account)
        if self.error is not None:
            raise self.error
        return self.rows


class _Candidates:
    """假候选池端口（IPoolMemberSource.get_members 形状）。"""

    def __init__(self, rows=None, *, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = []

    def get_members(self, pool_id):
        self.calls.append(pool_id)
        if self.error is not None:
            raise self.error
        return self.rows


class _AlertRepo:
    """假已报留痕：幂等键 (symbol, title)，第二次返回 None（与真实仓储同语义）。"""

    def __init__(self):
        self.rows = set()
        self.calls = []

    def record(self, symbol, title, matched_words, tier):
        self.calls.append((symbol, title, list(matched_words), tier))
        key = (symbol, title)
        if key in self.rows:
            return None
        self.rows.add(key)
        return {'symbol': symbol, 'title': title, 'tier': tier}


class _ConfirmQuery:
    """假确认核验查询口（NewsWatchService.scan_candidates 同签名）。"""

    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def scan_candidates(self, symbols, now=None, limit=15):
        self.calls.append(list(symbols))
        if self.error is not None:
            raise self.error
        return {'scanned': True, 'mode': 'candidate_pool', 'symbols': len(symbols),
                'negative': 0, 'critical': 0, 'soft': 0, 'clean': len(symbols),
                'skipped': 0, 'details': [], 'at': (now or NOW).isoformat()}


class _Sender:
    """假发卡器：记录 payload（P0/P2 既有路由的 kind/level 语义）。"""

    def __init__(self):
        self.payloads = []

    def __call__(self, payload):
        self.payloads.append(dict(payload))
        return True


class _LoggerCapture:
    """structlog 替身（structlog 默认不走 stdlib caplog）。"""

    def __init__(self):
        self.calls = []

    def _record(self, level):
        def _fn(message, **kwargs):
            self.calls.append((level, str(message), kwargs))
        return _fn

    def __getattr__(self, name):
        if name in ('info', 'warning', 'error', 'debug'):
            return self._record(name)
        raise AttributeError(name)

    def of(self, level):
        return [c for c in self.calls if c[0] == level]

    def text(self):
        return ' '.join(c[1] + ' ' + str(c[2]) for c in self.calls)


def _ok(records):
    return {'records': list(records), 'skipped': False, 'empty': not records,
            'reason': '', 'provider': 'fake', 'attempted_sources': [],
            'fetched_at': NOW.isoformat()}


def _service(*, records=(), members=None, boards=None, holdings=(),
             candidates=(), alert_repo=None, sender=None, news_service=None,
             position_repo=None, candidate_source=None, sector_source=None,
             news_source=None, max_alerts=20, max_confirm=8):
    """装配被测服务（全部依赖替身；index 用假板块端口，单测零外呼）。"""
    out = news_source if news_source is not None else _ok(records)
    source = sector_source if sector_source is not None else _SectorSource(
        members, boards=boards)
    index = SectorConstituentIndex(source, now_fn=lambda: NOW)
    return PolicyWatchService(
        news_source=_NewsSource(out),
        sector_index=index,
        position_repo=position_repo if position_repo is not None
        else _Positions(list(holdings)),
        accounts=('agent_virtual',),
        candidate_source=candidate_source if candidate_source is not None
        else _Candidates(list(candidates)),
        alert_repo=alert_repo if alert_repo is not None else _AlertRepo(),
        news_service=news_service if news_service is not None else _ConfirmQuery(),
        sender=sender if sender is not None else _Sender(),
        max_alerts_per_scan=max_alerts,
        max_confirm_per_scan=max_confirm,
        now_fn=lambda: NOW,
    )


# ── 0a. 命中板块 → 成分 → 持仓交集（持仓发 P0 卡）────────────────────

def test_sector_hit_routes_to_holding_alert_and_candidate_query():
    sender = _Sender()
    confirm = _ConfirmQuery()
    service = _service(
        records=[{'title': '半导体出口管制升级，多家厂商被列入实体清单',
                  'time': '2026-10-21 13:50', 'source': 'fake', 'url': 'http://x'}],
        members={'半导体': [{'symbol': '600519.SH'}, {'symbol': '300750'},
                           {'symbol': '000001'}]},
        holdings=[{'symbol': '600519.SH', 'shares_total': 100}],
        candidates=[{'symbol': '300750'}],
        sender=sender, news_service=confirm)

    out = service.scan()

    # 板块命中（行业词表 + 板块名）
    assert out['records'] == 1
    item = out['items'][0]
    assert '半导体' in item['sectors']
    assert item['action'] == ACTION_ALERT
    assert item['alert_symbols'] == ['600519']
    # 持仓命中 → 既有 P0/P2 路由：critical → P0，kind=news_alert，每标的 0/1 张卡
    assert len(sender.payloads) == 1
    payload = sender.payloads[0]
    assert payload['kind'] == 'news_alert'
    assert payload['level'] == 'P0'
    assert '600519' in payload['message']
    assert '半导体' in payload['message']
    # 候选池命中 → 确认核验查询（不发卡）
    assert out['confirm']['queried'] == 1
    assert confirm.calls == [['300750']]
    # 无关成分（000001）既不告警也不进核验
    assert out['alerts'][0]['symbol'] == '600519'
    assert '000001' not in str(sender.payloads)


def test_soft_tier_maps_to_p2_route():
    sender = _Sender()
    service = _service(
        records=[{'title': '半导体设备厂商宣布扩产', 'time': '', 'source': '', 'url': ''}],
        members={'半导体': [{'symbol': '600519'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        sender=sender)

    out = service.scan()

    assert out['items'][0]['tier'] == 'soft'
    assert sender.payloads[0]['level'] == 'P2'


def test_candidate_only_hit_goes_to_confirm_query_without_alert():
    sender = _Sender()
    confirm = _ConfirmQuery()
    service = _service(
        records=[{'title': '第四批集采落地，药品平均降价50%',
                  'time': '', 'source': '', 'url': ''}],
        members={'医药': [{'symbol': '000538'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        candidates=[{'symbol': '000538'}],
        sender=sender, news_service=confirm)

    out = service.scan()

    assert out['items'][0]['sectors'] == ['医药']
    assert out['items'][0]['action'] == ACTION_CONFIRM
    assert sender.payloads == []                    # 候选池不发卡
    assert confirm.calls == [['000538']]


# ── 0b. 无关板块不打扰 ───────────────────────────────────────

def test_unrelated_sector_does_not_disturb():
    sender = _Sender()
    confirm = _ConfirmQuery()
    service = _service(
        records=[{'title': '第四批集采落地，药品平均降价50%',
                  'time': '', 'source': '', 'url': ''}],
        members={'医药': [{'symbol': '000538'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        sender=sender, news_service=confirm)

    out = service.scan()

    assert out['items'][0]['action'] == ACTION_UNRELATED
    assert out['unrelated'] == 1
    assert sender.payloads == []
    assert confirm.calls == []


def test_market_chatter_without_risk_words_is_not_routed():
    """板块名提到了但没有任何事件词（行情/复盘类）→ 不打扰。"""
    sender = _Sender()
    service = _service(
        records=[{'title': '半导体板块午后拉升', 'time': '', 'source': '', 'url': ''}],
        members={'半导体': [{'symbol': '600519'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        sender=sender)

    out = service.scan()

    assert out['items'][0]['action'] == ACTION_SKIPPED
    assert sender.payloads == []


def test_generic_industry_word_without_policy_or_board_name_is_skipped():
    """「多家公司宣布扩产」只命中跨行业通用软词、且非政策新闻 → 不路由。"""
    sender = _Sender()
    service = _service(
        records=[{'title': '多家公司宣布扩产', 'time': '', 'source': '', 'url': ''}],
        members={'半导体': [{'symbol': '600519'}], '新能源': [{'symbol': '300750'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100},
                  {'symbol': '300750', 'shares_total': 100}],
        sender=sender)

    out = service.scan()

    assert out['items'][0]['action'] == ACTION_SKIPPED
    assert sender.payloads == []


# ── 0c. 映射缺失 fail-open ──────────────────────────────────

def test_mapping_missing_is_fail_open_not_unrelated():
    sender = _Sender()
    service = _service(
        records=[{'title': '半导体出口管制升级', 'time': '', 'source': '', 'url': ''}],
        # 行情板块列表里认不出「半导体」（数据源口径差异/降级）
        members={'银行': [{'symbol': '601398'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        sender=sender)

    out = service.scan()

    assert out['alerts'] == []
    assert sender.payloads == []
    assert out['mapping_missing'] == 1
    assert out['skipped_items'] == 1
    item = out['items'][0]
    assert item['action'] == ACTION_SKIPPED
    assert '映射缺失' in item['reason']
    # 关键：映射缺失 ≠ 无关（fail-open 不下结论，不假装「与我无关」）
    assert out['unrelated'] == 0


def test_board_list_failure_is_fail_open():
    sender = _Sender()
    service = _service(
        records=[{'title': '半导体出口管制升级', 'time': '', 'source': '', 'url': ''}],
        sector_source=_SectorSource(list_error=RuntimeError('sector source down')),
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        sender=sender)

    out = service.scan()

    assert sender.payloads == []
    assert out['mapping_missing'] >= 1
    assert out['degraded'] is True
    assert out['items'][0]['action'] == ACTION_SKIPPED


def test_member_fetch_failure_per_board_is_missing_not_empty():
    sender = _Sender()
    service = _service(
        records=[{'title': '半导体出口管制升级', 'time': '', 'source': '', 'url': ''}],
        sector_source=_SectorSource({'半导体': []},
                                    member_error=RuntimeError('members down')),
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        sender=sender)

    out = service.scan()

    assert sender.payloads == []
    assert out['mapping_missing'] >= 1


# ── 0d. 取数失败 ≠「无政策利空」──────────────────────────────

def test_news_fetch_failure_is_skipped_not_no_news():
    sender = _Sender()
    confirm = _ConfirmQuery()
    service = _service(
        news_source={'records': [], 'skipped': True, 'empty': False,
                     'reason': '数据源不可用：boom', 'provider': '',
                     'attempted_sources': [], 'fetched_at': NOW.isoformat()},
        members={'半导体': [{'symbol': '600519'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        sender=sender, news_service=confirm)

    out = service.scan()

    assert out['skipped'] is True
    assert '数据源不可用' in out['reason']
    assert sender.payloads == []
    assert confirm.calls == []


def test_source_exception_is_swallowed_as_skipped():
    class _BoomSource:
        def fetch(self, limit=None):
            raise RuntimeError('fetch exploded')

    sender = _Sender()
    service = PolicyWatchService(
        news_source=_BoomSource(),
        sector_index=SectorConstituentIndex(_SectorSource({}), now_fn=lambda: NOW),
        position_repo=_Positions([]), accounts=('agent_virtual',),
        candidate_source=_Candidates([]), alert_repo=_AlertRepo(),
        news_service=_ConfirmQuery(), sender=sender, now_fn=lambda: NOW)

    out = service.scan()

    assert out['skipped'] is True
    assert 'fetch exploded' in out['reason']
    assert sender.payloads == []


def test_holding_read_failure_degrades_but_candidate_query_still_runs():
    sender = _Sender()
    confirm = _ConfirmQuery()
    service = _service(
        records=[{'title': '第四批集采落地', 'time': '', 'source': '', 'url': ''}],
        members={'医药': [{'symbol': '000538'}]},
        position_repo=_Positions(error=RuntimeError('position db down')),
        candidates=[{'symbol': '000538'}],
        sender=sender, news_service=confirm)

    out = service.scan()

    assert out['degraded'] is True
    assert any('position db down' in err for err in out['target_errors'])
    assert sender.payloads == []
    assert confirm.calls == [['000538']]


# ── 0e. 链路去重（同一条政策新闻只报一次 / 只核验一次）──────────

def test_same_policy_news_reported_once_and_verified_once():
    sender = _Sender()
    confirm = _ConfirmQuery()
    alert_repo = _AlertRepo()
    service = _service(
        records=[{'title': '半导体出口管制升级', 'time': '', 'source': '', 'url': ''}],
        members={},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        candidates=[{'symbol': '300750'}],
        alert_repo=alert_repo, sender=sender, news_service=confirm)
    # 板块成分用更真实的形状（带交易所后缀）
    service._index = SectorConstituentIndex(
        _SectorSource({'半导体': [{'symbol': '600519.SH'},
                                {'symbol': '300750.SZ'}]}),
        now_fn=lambda: NOW)

    first = service.scan()
    second = service.scan()

    assert len(sender.payloads) == 1                 # 第二轮被留痕去重
    assert first['alerts_deduped'] == 0
    assert second['alerts_deduped'] == 1
    assert second['alerts'] == []
    assert confirm.calls == [['300750']]             # 第二轮不再重复核验


def test_alert_repo_failure_does_not_send_duplicate_cards():
    class _BrokenRepo:
        def record(self, *args, **kwargs):
            raise RuntimeError('alert table down')

    sender = _Sender()
    service = _service(
        records=[{'title': '半导体出口管制升级', 'time': '', 'source': '', 'url': ''}],
        members={'半导体': [{'symbol': '600519'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        alert_repo=_BrokenRepo(), sender=sender)

    out = service.scan()

    assert sender.payloads == []
    assert out['alerts_failed']
    assert '去重留痕不可用' == out['alerts_failed'][0]['reason']


# ── 0f. 解析路由的纯函数口径 ─────────────────────────────────

def test_resolve_is_pure_and_reports_actions():
    index = SectorConstituentIndex(
        _SectorSource({'半导体': [{'symbol': '600519'}, {'symbol': '000001'}]}),
        now_fn=lambda: NOW)
    service = PolicyWatchService(
        news_source=_NewsSource(_ok([])), sector_index=index,
        position_repo=_Positions([]), accounts=(),
        candidate_source=_Candidates([]), alert_repo=_AlertRepo(),
        news_service=_ConfirmQuery(), sender=_Sender(), now_fn=lambda: NOW)

    plan = service.resolve(
        [{'title': '半导体出口管制升级', 'time': '', 'source': '', 'url': ''},
         {'title': '第四批集采落地', 'time': '', 'source': '', 'url': ''}],
        holdings={'600519'}, candidates=set())

    assert plan['records'] == 2
    assert plan['alerts'][0]['symbol'] == '600519'
    assert plan['items'][0]['action'] == ACTION_ALERT
    # 医药映射缺失 → skipped（fail-open），不是 unrelated
    assert plan['items'][1]['action'] == ACTION_SKIPPED
    assert plan['unrelated'] == 0
    assert plan['mapping_missing'] == 1


# ── 2a. 板块映射复用现有口径（不维护第二份）────────────────────

def test_sector_mapping_reuses_existing_caliber():
    # 取数适配 / 裸码归一 / TTL 都是现有实现，不是第二份拷贝
    assert pw._ManagerSectorSource is sr._ManagerSectorSource
    assert pw._bare_symbol is sr._bare_symbol
    assert pw.SECTOR_MAP_TTL_SEC == sr.DEFAULT_TTL_SEC
    # 别名与词表口径来自 policy_lexicon（模块内没有第二张表）
    assert not hasattr(pw, 'SECTOR_ALIASES')
    assert not hasattr(pw, 'INDUSTRY_LEXICONS')
    assert pw.TIER_CRITICAL is pl.TIER_CRITICAL
    assert pw._TIER_ORDER is pl.TIER_ORDER

    index = SectorConstituentIndex(
        _SectorSource({'光伏设备': [{'symbol': '601012'}],
                       '风电设备': [{'symbol': '002202'}],
                       '银行': [{'symbol': '601398'}]}),
        now_fn=lambda: NOW)
    # '光伏设备'/'风电设备' 都经 policy_lexicon.SECTOR_ALIASES 归到 canonical「新能源」
    assert index.boards_for('新能源') == ['光伏设备', '风电设备']
    assert index.members_for('新能源')['symbols'] == {'601012', '002202'}
    assert index.members_for('未登记板块')['mapping_missing'] is True


def test_only_holdings_receive_cards_never_candidates():
    sender = _Sender()
    service = _service(
        records=[{'title': '半导体出口管制升级', 'time': '', 'source': '', 'url': ''}],
        members={'半导体': [{'symbol': '600519'}, {'symbol': '300750'}]},
        holdings=[{'symbol': '600519', 'shares_total': 100}],
        candidates=[{'symbol': '300750'}],
        sender=sender)

    service.scan()

    assert len(sender.payloads) == 1
    assert '600519' in sender.payloads[0]['message']
    assert all('300750' not in p['message'] for p in sender.payloads)


# ── 1. factory 装配：独立 daemon 扫描线程，不阻断启动 ───────────────

_ENV_KEYS = (
    'WATCH_POLICY_WATCH_ENABLED',
    'WATCH_POLICY_SCAN_INTERVAL_SEC',
    'WATCH_SECTOR_RESONANCE_POOL_ID',
)


def _clear_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_factory_assembles_policy_watch_service(monkeypatch):
    _clear_env(monkeypatch)

    service = factory_mod.build_policy_watch_service()

    assert isinstance(service, PolicyWatchService)
    assert isinstance(service._news, PolicyNewsSource)          # 全市场新闻源
    assert isinstance(service._index, SectorConstituentIndex)  # 复用现有板块口径
    assert callable(getattr(service._index, 'members_for', None))
    assert service._positions is not None                      # 三账户持仓
    assert service._candidates is not None                     # 候选池（复用共振候选集口径）
    assert service._alerts is not None                         # 已报留痕（与新闻监控同表）
    assert callable(getattr(service._news_service, 'scan_candidates', None))
    assert callable(service._sender)                           # 既有 P0/P2 路由


def test_factory_policy_switch_off_returns_none(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('WATCH_POLICY_WATCH_ENABLED', 'false')

    assert factory_mod.build_policy_watch_service() is None
    service, thread = factory_mod.start_policy_watch_scanner()
    assert (service, thread) == (None, None)


def test_factory_scan_interval_env(monkeypatch):
    _clear_env(monkeypatch)
    assert factory_mod._policy_scan_interval() == \
        factory_mod.DEFAULT_POLICY_SCAN_INTERVAL_SEC == 300.0   # 默认 5 分钟

    monkeypatch.setenv('WATCH_POLICY_SCAN_INTERVAL_SEC', '120')
    assert factory_mod._policy_scan_interval() == 120.0

    monkeypatch.setenv('WATCH_POLICY_SCAN_INTERVAL_SEC', 'not-a-number')
    assert factory_mod._policy_scan_interval() == \
        factory_mod.DEFAULT_POLICY_SCAN_INTERVAL_SEC

    monkeypatch.setenv('WATCH_POLICY_SCAN_INTERVAL_SEC', '5')
    assert factory_mod._policy_scan_interval() == \
        factory_mod.POLICY_SCAN_MIN_INTERVAL_SEC


def test_factory_assembly_failure_degrades_without_raising(monkeypatch):
    _clear_env(monkeypatch)
    capture = _LoggerCapture()
    monkeypatch.setattr(factory_mod, 'logger', capture)

    def _boom(**kwargs):
        raise RuntimeError('policy service unavailable')

    # 服务构造本身失败（stage=service）：装配方必须降级为 None 并留下可诊断日志
    monkeypatch.setattr(pw, 'PolicyWatchService', _boom)

    assert factory_mod.build_policy_watch_service() is None
    errors = capture.of('error')
    assert errors and '政策盯盘扫描装配失败' in errors[-1][1]
    assert errors[-1][2].get('stage') == 'service'
    assert 'policy service unavailable' in errors[-1][2].get('error', '')


def test_factory_news_service_failure_keeps_holdings_route(monkeypatch):
    """确认核验查询装配失败只降级该段：持仓 P0/P2 路由照常（候选池命中标注未核验）。"""
    _clear_env(monkeypatch)
    capture = _LoggerCapture()
    monkeypatch.setattr(factory_mod, 'logger', capture)

    def _boom():
        raise RuntimeError('news repo down')

    monkeypatch.setattr(factory_mod, '_build_news_watch_service', _boom)

    service = factory_mod.build_policy_watch_service()

    assert isinstance(service, PolicyWatchService)
    assert service._news_service is None                     # 只缺确认核验查询
    assert service._positions is not None                    # 持仓路由仍可用
    assert service._alerts is not None
    assert '确认核验查询装配失败' in capture.text()


def _fast_scanner(monkeypatch, service):
    """把启动延迟/间隔/失败退避压到毫秒级，让线程行为可断言。"""
    monkeypatch.setattr(factory_mod, 'POLICY_SCAN_START_DELAY_SEC', 0.0)
    monkeypatch.setattr(factory_mod, 'POLICY_SCAN_FAIL_BACKOFF_SEC', 0.02)
    monkeypatch.setattr(factory_mod, '_policy_scan_interval', lambda: 0.02)
    return service


def test_scanner_thread_is_daemon_and_does_not_block(monkeypatch):
    calls = []

    class _Service:
        def scan(self):
            calls.append(1)
            return {'skipped': False, 'records': 1, 'alerts': [], 'confirm': {},
                    'unrelated': 0, 'mapping_missing': 0}

    service_stub = _fast_scanner(monkeypatch, _Service())
    stop = threading.Event()

    started = time.monotonic()
    service, thread = factory_mod.start_policy_watch_scanner(
        service=service_stub, stop_event=stop)
    elapsed = time.monotonic() - started

    assert elapsed < 0.5                      # 启动立即返回（扫描在后台）
    assert service is service_stub
    assert thread is not None and thread.daemon is True
    assert thread.name == factory_mod.POLICY_SCAN_THREAD_NAME

    deadline = time.monotonic() + 2.0
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    thread.join(1.0)

    assert calls, 'daemon 线程应真的在后台扫描'
    assert not thread.is_alive()


def test_scanner_survives_scan_exception(monkeypatch):
    class _BoomService:
        def __init__(self):
            self.calls = 0

        def scan(self):
            self.calls += 1
            raise RuntimeError('scan exploded')

    service_stub = _fast_scanner(monkeypatch, _BoomService())
    stop = threading.Event()

    _, thread = factory_mod.start_policy_watch_scanner(
        service=service_stub, stop_event=stop)
    deadline = time.monotonic() + 2.0
    while service_stub.calls < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    thread.join(1.0)

    assert service_stub.calls >= 2, '扫描异常后应重试（线程不退出）'


def test_engine_bootstrap_starts_scanner_without_blocking(monkeypatch):
    """引擎 bootstrap 照常返回句柄，政策扫描线程启动被接线（不动 engine）。"""
    engine_stub = SimpleNamespace(
        run_forever=lambda: None,
        spawn_heartbeat_thread=lambda: None,
        confirm_verify_pipeline=None,
        news_watch_service=None,
    )
    monkeypatch.setattr(factory_mod, 'create_watch_engine', lambda: engine_stub)
    started = []
    monkeypatch.setattr(
        factory_mod, 'start_policy_watch_scanner',
        lambda engine=None, stop_event=None, service=None: started.append(engine))

    engine, thread = factory_mod.start_watch_engine_in_thread()

    assert engine is engine_stub
    assert thread.daemon is True
    assert started == [engine_stub]


def test_engine_bootstrap_survives_scanner_start_failure(monkeypatch):
    engine_stub = SimpleNamespace(
        run_forever=lambda: None,
        spawn_heartbeat_thread=lambda: None,
        confirm_verify_pipeline=None,
        news_watch_service=None,
    )
    monkeypatch.setattr(factory_mod, 'create_watch_engine', lambda: engine_stub)
    capture = _LoggerCapture()
    monkeypatch.setattr(factory_mod, 'logger', capture)

    def _boom(*args, **kwargs):
        raise RuntimeError('cannot start thread')

    monkeypatch.setattr(factory_mod, 'start_policy_watch_scanner', _boom)

    engine, thread = factory_mod.start_watch_engine_in_thread()

    assert engine is engine_stub
    assert thread.daemon is True
    assert '政策盯盘扫描线程启动失败' in capture.text()


def test_confirm_query_failure_is_reported_not_raised():
    service = _service(
        records=[{'title': '第四批集采落地', 'time': '', 'source': '', 'url': ''}],
        members={'医药': [{'symbol': '000538'}]},
        candidates=[{'symbol': '000538'}],
        news_service=_ConfirmQuery(error=RuntimeError('news source down')))

    out = service.scan()

    assert out['confirm']['skipped'] is True
    assert 'news source down' in out['confirm']['reason']
