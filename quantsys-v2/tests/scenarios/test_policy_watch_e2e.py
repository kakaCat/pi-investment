"""政策消息 e2e 场景（policy-watch-e2e，2026-10-21 政策盯盘闭环）

本文件是 `tests/scenarios` 场景矩阵的续篇，只回答「政策盯盘这条链路到底走不走得通」：

  E1 政策利空命中持仓股全链路
     取数（DataProviderManager `get_market_news` 契约）→ 分级（`policy_lexicon`）
     → 板块解析（政策词表别名 + `_ManagerSectorSource` 行情板块/成分）
     → 持仓发 P0/P2 卡（kind=news_alert）→ 已报留痕（symbol+title 幂等）
  E2 只命中无关板块 → 不打扰
     不发卡、不核验候选池、不写留痕（只解析命中板块的成分，不扫全市场板块）。
  E3 同轮相关/无关混排 → 只告警相关项
     无关项进 unrelated 计数；命中词/板块/标的这三层证据在相关项上都能追溯。
  E4 候选池口径查询可用
     候选池命中 → `NewsWatchService.scan_candidates`（只读、不发卡、不写持仓留痕）；
     同一轮内不重复核验，持仓留痕与候选池口径互不污染。

风格与其它场景文件一致：假件只替换**取数与出口**
（DataProviderManager / 持仓仓储 / 候选池端口 / 已报留痕 / 发卡器），
分级、路由、去重、确认核验全部走生产代码。每个用例都写明证伪点。
"""
import sys
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

from qs_watch.application.services.watch_engine.news_watch_service import (  # noqa: E402
    MODE_CANDIDATE_POOL,
    NewsWatchService,
)
from qs_watch.application.services.watch_engine.policy_news_source import (  # noqa: E402
    PolicyNewsSource,
)
from qs_watch.application.services.watch_engine.policy_watch_service import (  # noqa: E402
    ACTION_ALERT,
    ACTION_CONFIRM,
    ACTION_UNRELATED,
    PolicyWatchService,
    SectorConstituentIndex,
)
from qs_watch.application.services.watch_engine.sector_resonance_service import (  # noqa: E402
    _ManagerSectorSource,
)

NOW = datetime(2026, 10, 21, 14, 0)     # 周二盘中
SEMI_TITLE = '半导体出口管制升级，多家厂商被列入实体清单'
PHARMA_TITLE = '第四批集采落地，药品平均降价50%'
POOL_ID = 7


# ── 假件：取数（全市场新闻 / 行情板块 / 成分股）──────────────
class _FakeManager:
    """DataProviderManager 替身（只实现政策盯盘用到的三个方法）。

    返回形状与真实 manager 一致（{'success', 'source'/'data'}），让
    `PolicyNewsSource` 与 `_ManagerSectorSource` 的归一/剥壳代码真正被执行。
    """

    def __init__(self, news_records=(), *, sectors=(), members=None):
        self.news_records = list(news_records)
        self.sector_names = list(sectors)
        self.members = dict(members or {})
        self.calls = []

    def get_market_news(self, *args, **kwargs):
        self.calls.append('market_news')
        return {'success': True, 'source': 'fake-news',
                'data': {'records': [dict(row) for row in self.news_records]}}

    def get_sector_list(self):
        self.calls.append('sector_list')
        return {'success': True,
                'data': {'industries': [{'name': name}
                                        for name in self.sector_names],
                         'concepts': []}}

    def get_sector_stocks(self, sector):
        self.calls.append('members:%s' % sector)
        symbols = self.members.get(sector)
        if symbols is None:
            return {'success': True, 'data': {'found': False, 'stocks': []}}
        return {'success': True,
                'data': {'found': True,
                         'stocks': [{'symbol': symbol} for symbol in symbols]}}


class _Positions:
    """模拟持仓仓储替身（每账户一批行；Mapping 形状与真实仓储一致）。"""

    def __init__(self, by_account=None):
        self.by_account = dict(by_account or {})
        self.calls = []

    def get_all_positions(self, account):
        self.calls.append(account)
        return [dict(row) for row in self.by_account.get(account, ())]


class _Candidates:
    """候选池成员端口替身（IPoolMemberSource.get_members 形状）。"""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []

    def get_members(self, pool_id):
        self.calls.append(pool_id)
        return [dict(row) for row in self.rows]


class _SymbolNews:
    """个股新闻源替身（`NewsWatchService._fetch_news` 的取数端口）。"""

    def __init__(self, by_symbol=None):
        self.by_symbol = {key: list(value)
                          for key, value in (by_symbol or {}).items()}
        self.calls = []

    def fetch_news(self, symbol, limit=15):
        self.calls.append(symbol)
        return [dict(item) for item in self.by_symbol.get(symbol, ())]


# ── 假件：出口（已报留痕 / 发卡）────────────────────────────
class _AlertRepo:
    """已报留痕替身：幂等键 (symbol, title)，重复调用返回 None（与真实仓储同语义）。"""

    def __init__(self):
        self.rows = {}
        self.calls = []

    def record(self, symbol, title, matched_words, tier):
        self.calls.append({'symbol': symbol, 'title': title,
                           'matched_words': list(matched_words), 'tier': tier})
        key = (symbol, title)
        if key in self.rows:
            return None
        self.rows[key] = {'symbol': symbol, 'title': title,
                          'matched_words': list(matched_words), 'tier': tier}
        return self.rows[key]


class _Sender:
    """发卡器替身：记录 payload（P0/P2 既有路由的 kind/level 语义）。"""

    def __init__(self, ok=True):
        self.ok = ok
        self.payloads = []

    def __call__(self, payload):
        self.payloads.append(dict(payload))
        return self.ok


# ── 装配（生产代码全链路，替身只在取数/出口）────────────────
def _build(*, news_records, sectors=('半导体', '医药'), members=None,
           positions=None, candidates=(), candidate_news=None,
           sender=None, alert_repo=None, alert_service_repo=None,
           accounts=('agent_virtual',), max_confirm=8):
    manager = _FakeManager(news_records, sectors=sectors, members=members)
    alert_repo = alert_repo if alert_repo is not None else _AlertRepo()
    sender = sender if sender is not None else _Sender()
    symbol_news = _SymbolNews(candidate_news)
    # 确认核验查询口用**真服务**（只读），只替换个股新闻取数；
    # 它自己的留痕仓与持仓留痕分开（候选池口径不写持仓留痕）。
    news_service = NewsWatchService(
        symbol_news, alert_service_repo or _AlertRepo(), None, accounts=())
    candidate_source = _Candidates(candidates)
    service = PolicyWatchService(
        news_source=PolicyNewsSource(manager=manager),
        sector_index=SectorConstituentIndex(_ManagerSectorSource(manager),
                                            now_fn=lambda: NOW),
        position_repo=positions if positions is not None else _Positions(),
        accounts=accounts,
        candidate_source=candidate_source,
        candidate_pool_id=POOL_ID,
        alert_repo=alert_repo,
        news_service=news_service,
        sender=sender,
        max_confirm_per_scan=max_confirm,
        now_fn=lambda: NOW,
    )
    return SimpleNamespace(service=service, manager=manager,
                           alert_repo=alert_repo, sender=sender,
                           symbol_news=symbol_news,
                           candidates=candidate_source, index=service._index)


def _semi_news():
    return {'title': SEMI_TITLE, '发布时间': '2026-10-21 13:50',
            '文章来源': 'fake-news', '新闻链接': 'http://news/1'}


def _pharma_news():
    return {'title': PHARMA_TITLE, 'time': '2026-10-21 13:40',
            'source': 'fake-news', 'url': 'http://news/2'}


# ══════════════════════════════════════════════════════════════
# E1. 政策利空命中持仓股：取数 → 分级 → 板块解析 → 告警 → 留痕
# ══════════════════════════════════════════════════════════════

def test_E1_policy_hit_on_holding_runs_full_chain():
    """一条半导体出口管制新闻命中持仓 600519 → P0 卡 + 留痕 + 候选池核验。

    证伪点：
      · 卡片没有出现「板块 / 命中词 / 标的」→ 告警不可追溯；
      · 候选池标的（300750）被写成卡片 → 候选池口径被当成持仓；
      · 留痕 matched_words 为空 → 复盘时看不出因哪个词命中；
      · 第二轮重复发卡 → 幂等留痕没接进扫描链路。
    """
    bundle = _build(
        news_records=[_semi_news()],
        members={'半导体': ['600519.SH', '300750.SZ', '000001.SZ'],
                 '医药': ['000538.SZ']},
        positions=_Positions({'agent_virtual': [
            {'symbol': '600519.SH', 'shares_total': 100}]}),
        candidates=[{'symbol': '300750.SZ'}],
        candidate_news={'300750': [{'title': '某公司收到立案告知书',
                                   'time': '2026-10-21 09:30'}]},
    )

    out = bundle.service.scan()

    # ① 取数（真实 PolicyNewsSource 归一 + provider 透出）
    assert out['skipped'] is False and out['empty'] is False
    assert out['provider'] == 'fake-news'
    assert out['records'] == 1
    assert 'market_news' in bundle.manager.calls
    assert 'sector_list' in bundle.manager.calls

    # ② 分级 / ③ 板块解析：板块只取「命中板块」的成分，不扫全市场
    item = out['items'][0]
    assert item['action'] == ACTION_ALERT
    assert item['tier'] == 'critical'
    assert item['sectors'] == ['半导体']
    assert item['boards'] == ['半导体']
    assert item['alert_symbols'] == ['600519']
    assert '出口管制' in item['words'] and '实体清单' in item['words']
    assert 'members:半导体' in bundle.manager.calls
    assert 'members:医药' not in bundle.manager.calls
    # 「出口管制」也命中军工行业词表（未点名），军工在假板块列表里认不出 →
    # 该板块按映射缺失 fail-open，但半导体已解析出的持仓告警照常发出。
    assert item['mapping_missing'] == ['军工']

    # ④ 告警：既有 P0/P2 路由（critical → P0），只发给持仓，不发给候选池/无关成分
    assert len(bundle.sender.payloads) == 1
    payload = bundle.sender.payloads[0]
    assert payload['kind'] == 'news_alert'
    assert payload['level'] == 'P0'
    message = payload['message']
    for token in ('600519', '半导体', '出口管制', '实体清单'):
        assert token in message
    assert '300750' not in message and '000001' not in message

    # ⑤ 留痕：symbol + title 幂等，matched_words 是「命中词」证据
    assert len(bundle.alert_repo.rows) == 1
    row = bundle.alert_repo.rows[('600519', SEMI_TITLE)]
    assert row['symbol'] == '600519' and row['tier'] == 'critical'
    assert '出口管制' in row['matched_words']

    # ⑥ 候选池口径查询可用（真 NewsWatchService.scan_candidates，只读不发卡）
    assert out['confirm']['queried'] == 1
    assert out['confirm']['skipped'] is False
    assert bundle.symbol_news.calls == ['300750']
    result = out['confirm']['result']
    assert result['mode'] == MODE_CANDIDATE_POOL
    assert result['symbols'] == 1 and result['critical'] == 1
    assert result['details'][0]['symbol'] == '300750'
    assert bundle.candidates.calls == [POOL_ID]

    # ⑦ 第二轮：同一条新闻不重复发卡、不重复核验
    again = bundle.service.scan()
    assert len(bundle.sender.payloads) == 1
    assert again['alerts'] == [] and again['alerts_deduped'] == 1
    assert again['confirm']['queried'] == 0
    assert bundle.symbol_news.calls == ['300750']
    assert len(bundle.alert_repo.rows) == 1


# ══════════════════════════════════════════════════════════════
# E2. 只命中无关板块 → 不打扰
# ══════════════════════════════════════════════════════════════

def test_E2_unrelated_sector_does_not_disturb():
    """持仓只有半导体，医药集采政策 → unrelated，不发卡/不核验/不写留痕。

    证伪点：只要出现卡片、候选池核验调用或留痕行，就说明「与我有关」的
    交集判定失效（这就是消息洪水的来源）。
    """
    bundle = _build(
        news_records=[_pharma_news()],
        members={'半导体': ['600519.SH'], '医药': ['000538.SZ']},
        positions=_Positions({'agent_virtual': [
            {'symbol': '600519.SH', 'shares_total': 100}]}),
        candidates=[{'symbol': '300750.SZ'}],
        candidate_news={'300750': [{'title': '某公司收到立案告知书',
                                   'time': '2026-10-21 09:30'}]},
    )

    out = bundle.service.scan()

    item = out['items'][0]
    assert item['action'] == ACTION_UNRELATED
    # 无关项仍带判定证据（板块/命中词），但没有任何标的命中
    assert item['sectors'] == ['医药']
    assert '集采' in item['words']
    assert item['alert_symbols'] == [] and item['confirm_symbols'] == []
    assert out['unrelated'] == 1 and out['mapping_missing'] == 0
    assert out['alerts'] == []
    # 只解析「医药」的成分；持仓所在的半导体板块不必去取数
    assert 'members:医药' in bundle.manager.calls
    assert 'members:半导体' not in bundle.manager.calls
    assert bundle.sender.payloads == []
    assert bundle.alert_repo.calls == []
    assert out['confirm']['queried'] == 0
    assert bundle.symbol_news.calls == []


# ══════════════════════════════════════════════════════════════
# E3. 同一轮相关/无关混排 → 只告警相关项，三层证据可追溯
# ══════════════════════════════════════════════════════════════

def test_E3_mixed_batch_alerts_only_related_and_keeps_traceable_evidence():
    """同轮「半导体（持仓）+ 医药（无关）」→ 1 张卡 + 1 条 unrelated。

    证伪点：两条都发卡（淹没）或一条都不发（漏报）都算失败；相关项的
    命中词 / 板块 / 标的必须同时出现在解析结果、卡片与留痕里。
    """
    bundle = _build(
        news_records=[_semi_news(), _pharma_news()],
        members={'半导体': ['600519.SH'], '医药': ['000538.SZ']},
        positions=_Positions({'agent_virtual': [
            {'symbol': '600519.SH', 'shares_total': 100}]}),
    )

    out = bundle.service.scan()

    actions = [item['action'] for item in out['items']]
    assert actions == [ACTION_ALERT, ACTION_UNRELATED]
    assert out['unrelated'] == 1
    assert len(bundle.sender.payloads) == 1
    message = bundle.sender.payloads[0]['message']
    assert '600519' in message and '半导体' in message
    assert '000538' not in message
    assert len(bundle.alert_repo.rows) == 1

    # 三层证据（命中词 / 板块 / 标的）同时可追溯
    alert_item = out['items'][0]
    assert alert_item['words'] and alert_item['sectors'] \
        and alert_item['alert_symbols']
    row = next(iter(bundle.alert_repo.rows.values()))
    assert row['matched_words'] and row['symbol'] == '600519'

    # 无关项也保留「为什么无关」的板块证据，但没有标的命中
    unrelated_item = out['items'][1]
    assert unrelated_item['sectors'] == ['医药']
    assert unrelated_item['alert_symbols'] == []
    assert unrelated_item['confirm_symbols'] == []


# ══════════════════════════════════════════════════════════════
# E4. 候选池口径查询可用（只读、不发卡、不污染持仓留痕）
# ══════════════════════════════════════════════════════════════

def test_E4_candidate_pool_hit_uses_read_only_query_not_alert():
    """仅候选池命中 → 确认核验查询（scan_candidates），不发卡、不写持仓留痕。

    证伪点：
      · 卡片出现 → 候选池被当成持仓（消息洪水）；
      · 持仓留痕有行 → 候选池写进持仓留痕会让持仓扫描幂等键提前命中而漏报；
      · scan_candidates 没被真调用 → 「候选池口径查询可用」只是空话。
    """
    bundle = _build(
        news_records=[_pharma_news()],
        members={'半导体': ['600519.SH'], '医药': ['000538.SZ']},
        positions=_Positions({'agent_virtual': [
            {'symbol': '600519.SH', 'shares_total': 100}]}),
        candidates=[{'symbol': '000538.SZ'}],
        candidate_news={'000538': [{'title': '公司收到立案告知书',
                                   'time': '2026-10-21 09:30'}]},
    )

    out = bundle.service.scan()

    item = out['items'][0]
    assert item['action'] == ACTION_CONFIRM
    assert item['confirm_symbols'] == ['000538']
    assert bundle.sender.payloads == []                 # 候选池不发卡
    assert bundle.alert_repo.calls == []                # 不写持仓留痕
    assert bundle.alert_repo.rows == {}

    assert out['confirm']['queried'] == 1
    assert bundle.symbol_news.calls == ['000538']
    result = out['confirm']['result']
    assert result['mode'] == MODE_CANDIDATE_POOL
    assert result['negative'] == 1 and result['critical'] == 1
    assert result['details'][0]['symbol'] == '000538'
    assert result['details'][0]['tier'] == 'critical'

    # 第二轮：进程内记忆避免同一政策新闻重复核验同一标的
    again = bundle.service.scan()
    assert again['confirm']['queried'] == 0
    assert bundle.symbol_news.calls == ['000538']
    assert bundle.sender.payloads == []
