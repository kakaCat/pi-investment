"""净值写入闸门测试（仓储层）— REQ-261006190953-fc43 卡 B

背景（实测 2026-10-06）：`quant.simulation_equity_snapshot` 有 35 行落在非交易日
（5 账户 × 7 天：08-08/08-15/08-29/09-05/09-06/09-12/10-02）。守卫
`TradingDayGuard.should_write_daily()` 早已存在，但全仓只有 `live_trading/simulation_trader.py`
一处调用——产脏的四条路径一条都没调它。本卡把门设在**写入函数**这一层：
`SimulationORMRepository.upsert_equity_snapshot` 是唯一落库口，门就设在那里。

本文件锁住（对应卡 B 验收 ①~⑧）：
① 休市日拒写且**该日零行**；② 交易日正常写；③ 降级照写（fail-open）；
④ force=True 显式旁路；⑤ get_equity_snapshots 的 limit 语义 = 交易日数；
⑥ 日历不可得时不过滤（不静默清空）；⑦ 基准回退到上一交易日（不是上一行）；
⑧ 残缺快照仍被跳过。另加一条：闸门必须被"以目标日"调用（防各路径另写判定）。

日期取值策略（诚实声明）：**周末用真实判据**（`TradingDayGuard.check` 判 `source='weekend'`，
不依赖交易日历表，测试库日历为空也确定）；**交易日的"应写"路径用打桩**
（测试库日历表为空，工作日会走降级回退，不能作为"干净交易日"的证据）。
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from application.services.evolution.daily_snapshot_service import DailySnapshotService
from application.trading.paper_trading_engine import PaperTradingEngine
from infrastructure.persistence.orm.models import SimulationEquitySnapshot

#: 哨兵账户名：测试自造自清，不碰任何真实账户
ACCOUNT = '__req_fc43_gate_test__'

SAT = date(2026, 9, 5)      # 周六（实测脏行日之一）
SUN = date(2026, 9, 6)      # 周日（实测脏行日之一）
HOLIDAY = date(2026, 10, 2)  # 国庆休市（交易日历判定）
T1 = date(2026, 9, 4)
T2 = date(2026, 9, 9)
T3 = date(2026, 9, 10)
TRADING = {T1, T2, T3, date(2026, 9, 30), date(2026, 10, 8)}


@pytest.fixture()
def repo():
    """真库仓储 + 哨兵账户行自清（前后各清一次，避免互相污染）。"""
    r = SimulationORMRepository()
    _purge(r)
    yield r
    _purge(r)
    try:
        r.session.close()
    except Exception:  # noqa: BLE001 —— 收尾关连接失败不该让用例变红
        pass


def _purge(repo):
    (repo.session.query(SimulationEquitySnapshot)
     .filter(SimulationEquitySnapshot.account_name == ACCOUNT).delete())
    repo.session.commit()


def _rows(repo, day=None):
    query = repo.session.query(SimulationEquitySnapshot).filter(
        SimulationEquitySnapshot.account_name == ACCOUNT)
    if day is not None:
        query = query.filter(SimulationEquitySnapshot.snapshot_date == day)
    return query.all()


def _seed(repo, day, total, cash=0.0, daily_return=0.0):
    """造一行（force=True 显式旁路，测试构造历史序列的正当用途）。"""
    return repo.upsert_equity_snapshot(
        account_name=ACCOUNT, cash=cash, position_value=0.0, total_value=total,
        daily_return=daily_return, cumulative_return=0.0, drawdown=0.0,
        snapshot_date=day, commit=False, force=True,
    )


# ---------------------------------------------------------------- ① 休市日拒写

def test_upsert_refuses_weekend_and_writes_no_row(repo):
    """真实判据（周六 → source='weekend'）→ 返回 None 且该日零行。"""
    assert repo.upsert_equity_snapshot(
        account_name=ACCOUNT, cash=0.0, position_value=0.0, total_value=100000.0,
        daily_return=0.0, snapshot_date=SAT, commit=False,
    ) is None
    assert _rows(repo, SAT) == []


def test_upsert_refuses_sunday_and_writes_no_row(repo):
    assert repo.upsert_equity_snapshot(
        account_name=ACCOUNT, cash=0.0, position_value=0.0, total_value=100000.0,
        daily_return=0.0, snapshot_date=SUN, commit=False,
    ) is None
    assert _rows(repo, SUN) == []


def test_upsert_refuses_calendar_holiday(repo):
    """法定节假日（日历答 source='trading-calendar-holiday'）→ 拒写。"""
    with patch('application.services.trading_day_gate.skip_non_trading_day',
               return_value=(True, {'day': HOLIDAY.isoformat(), 'is_trading_day': False,
                                    'source': 'trading-calendar-holiday', 'degraded': False,
                                    'reason': '交易日历判定为非交易日'})):
        assert repo.upsert_equity_snapshot(
            account_name=ACCOUNT, cash=0.0, position_value=0.0, total_value=100000.0,
            daily_return=0.0, snapshot_date=HOLIDAY, commit=False,
        ) is None
    assert _rows(repo, HOLIDAY) == []


# ---------------------------------------------------------------- ②③ 交易日 / 降级照写

def test_upsert_writes_on_trading_day(repo):
    """闸门说「不跳」→ 正常落库，且 daily_return 原样保留。"""
    with patch('application.services.trading_day_gate.skip_non_trading_day',
               return_value=(False, {'day': T2.isoformat(), 'is_trading_day': True,
                                     'source': 'trading-calendar', 'degraded': False,
                                     'reason': '交易日历判定为交易日'})):
        snap = repo.upsert_equity_snapshot(
            account_name=ACCOUNT, cash=1000.0, position_value=0.0, total_value=100000.0,
            daily_return=0.0123, snapshot_date=T2, commit=False,
        )
    assert snap is not None and snap.snapshot_date == T2
    assert len(_rows(repo, T2)) == 1


def test_upsert_writes_when_calendar_degraded(repo):
    """③ 日历降级（degraded=True）→ fail-open 照写：宁可写一行可疑数据，也不静默停摆。"""
    with patch('application.services.trading_day_gate.skip_non_trading_day',
               return_value=(False, {'day': HOLIDAY.isoformat(), 'is_trading_day': True,
                                     'source': 'weekday-fallback', 'degraded': True,
                                     'reason': '日历链降级：按工作日回退'})):
        snap = repo.upsert_equity_snapshot(
            account_name=ACCOUNT, cash=0.0, position_value=0.0, total_value=100000.0,
            daily_return=0.0, snapshot_date=HOLIDAY, commit=False,
        )
    assert snap is not None
    assert len(_rows(repo, HOLIDAY)) == 1


# ---------------------------------------------------------------- ④ force 旁路

def test_force_bypass_writes_non_trading_row(repo):
    """④ force=True 是显式旁路（运维迁移 / 回滚 / 测试构造），可写非交易日行。"""
    assert _seed(repo, SAT, 101000.0) is not None
    assert len(_rows(repo, SAT)) == 1


# ---------------------------------------------------------------- ⑨ 闸门被以目标日调用

def test_gate_is_consulted_with_target_day(repo):
    """防"某条路径另写一套判定"：闸门必须被调用，且参数是目标日。"""
    calls = []

    def _spy(day=None):
        calls.append(day)
        return True, {'day': str(day), 'source': 'spy', 'degraded': False, 'reason': 'spy'}

    with patch('application.services.trading_day_gate.skip_non_trading_day', side_effect=_spy):
        repo.upsert_equity_snapshot(
            account_name=ACCOUNT, cash=0.0, position_value=0.0, total_value=1.0,
            daily_return=0.0, snapshot_date=SAT, commit=False,
        )
    assert calls == [SAT]


# ---------------------------------------------------------------- ⑤⑥ 读取口径

def test_get_equity_snapshots_trading_days_only_limit_means_trading_days(repo):
    """⑤ limit 语义 = 交易日数：候选里有周六行，取 2 个交易日应是 09-10 与 09-09。"""
    _seed(repo, T1, 100000.0)
    _seed(repo, SAT, 100500.0)   # 脏行：不得占窗口位
    _seed(repo, T2, 101000.0)
    _seed(repo, T3, 101500.0)
    repo.session.commit()

    kept = repo.get_equity_snapshots(ACCOUNT, limit=2, trading_days_only=True,
                                     trading_days=TRADING)
    assert [r.snapshot_date for r in kept] == [T3, T2]      # 倒序，且周六行被排除

    legacy = repo.get_equity_snapshots(ACCOUNT, limit=2)
    assert [r.snapshot_date for r in legacy] == [T3, T2]    # 不传 trading_days_only 时行为不变


def test_get_equity_snapshots_unverified_does_not_filter(repo):
    """⑥ 日历不可得（None）→ 不过滤 + 告警：静默按空集过滤会清空整个净值序列。"""
    _seed(repo, T1, 100000.0)
    _seed(repo, SAT, 100500.0)
    repo.session.commit()
    kept = repo.get_equity_snapshots(ACCOUNT, limit=10, trading_days_only=True, trading_days=None)
    assert len(kept) == 2


# ---------------------------------------------------------------- ⑦⑧ 基准口径

def test_previous_valid_snapshot_skips_non_trading_baseline(repo):
    """⑦ 基准 = 上一**交易日**：09-30 与 10-02(休市) 都在，"10-08 的上一基准"必须是 09-30。"""
    _seed(repo, date(2026, 9, 30), 100000.0)
    _seed(repo, HOLIDAY, 100100.0)          # 假日假快照：不得被当基准
    repo.session.commit()

    with_trading = repo.previous_valid_snapshot(ACCOUNT, date(2026, 10, 8), trading_days=TRADING)
    assert with_trading is not None and with_trading.snapshot_date == date(2026, 9, 30)

    # 不传日历（不可得）→ 退回"上一行"行为，并（由实现）告警；此处只锁行为可预期
    unverified = repo.previous_valid_snapshot(ACCOUNT, date(2026, 10, 8))
    assert unverified is not None and unverified.snapshot_date == HOLIDAY


def test_previous_valid_snapshot_still_skips_incomplete_row(repo):
    """⑧ 残缺判据不变：total_value < cash 的行不得当基准（即便它是交易日）。"""
    _seed(repo, T2, 100000.0)
    _seed(repo, T3, 500.0, cash=99999.0)    # 残缺：总资产 < 现金
    repo.session.commit()
    got = repo.previous_valid_snapshot(ACCOUNT, date(2026, 9, 30), trading_days=TRADING)
    assert got is not None and got.snapshot_date == T2


# ===========================================================================
# 卡 C（REQ-261006190953-fc43）：服务路径与引擎路径对闸门返回值的处理
#
# 为什么另起一段：上面锁的是**仓储层**（门本身），这里锁的是**两个消费方**——
# 它们不许自写交易日判定，也不许把"门拒写（None）"读成"写成功"或直接崩。
# 判据注解除外：两条路径都必须向 `application.services.trading_day_gate` 取值。
#
# 与"今天是不是交易日"无关：目标日显式传入，门的结论一律打桩（`patch` 打在
# `application.services.trading_day_gate.skip_non_trading_day`——两条路径都是
# **惰性 import + 按模块属性取值**，故桩生效；见 tests/test_multi_account_domain.py 的同款口径）。
# ===========================================================================

HOLIDAY_DAY = date(2026, 10, 6)     # 国庆休市（与卡 B 的 HOLIDAY=10-02 区分开，勿混）
TRADING_DAY = date(2026, 9, 30)

_HOLIDAY_FIVE = {
    'day': '2026-10-06',
    'is_trading_day': False,
    'source': 'trading-calendar-holiday',
    'degraded': False,
    'reason': '交易日历判定为非交易日（来源 calendar_table：该日不在交易日历中）',
}
_TRADING_FIVE = {
    'day': '2026-09-30',
    'is_trading_day': True,
    'source': 'trading-calendar',
    'degraded': False,
    'reason': '交易日历判定为交易日（来源 calendar_table）',
}
_FIVE_KEYS = {'day', 'is_trading_day', 'source', 'degraded', 'reason'}


def _account_ns(name):
    return SimpleNamespace(account_name=name, cash_available=1000.0, cash_frozen=0.0,
                           initial_capital=1000.0, peak_value=1000.0)


class _FakeSimRepo:
    """服务路径的假仓储：`upsert_equity_snapshot` 的返回值由用例指定。

    返回 None 即"闸门拒写"（真实仓储在非交易日就是这样）；返回任何非 None 即"已落库"。
    """

    def __init__(self, accounts, upsert_result):
        self._accounts = list(accounts)
        self._upsert_result = upsert_result
        self.upsert_calls = []

    def list_accounts(self, status=None):
        return list(self._accounts)

    def get_all_positions(self, account_name):
        return []

    def upsert_equity_snapshot(self, **kw):
        self.upsert_calls.append(kw)
        return self._upsert_result


class _FakeEngineRepo:
    """引擎路径的假仓储：真库装配由 `object.__new__` 绕开（本段不碰 DB）。"""

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.upsert_calls = []
        self.account_updates = []
        self.drawdown_recomputes = []
        self.account = SimpleNamespace(
            total_value=101000.0, cash_available=90000.0, position_value=11000.0,
            initial_capital=100000.0, peak_value=105000.0, max_drawdown=-0.01)

    def get_account(self, account_name):
        return self.account

    def upsert_equity_snapshot(self, **kw):
        self.upsert_calls.append(kw)
        return self.snapshot

    def recompute_account_max_drawdown(self, account_name):
        self.drawdown_recomputes.append(account_name)
        return -0.02

    def update_account(self, **kw):
        self.account_updates.append(kw)


def _engine(repo):
    """只装配 `take_daily_snapshot` 用到的三个属性（不动 `__init__` 的真库/券商装配）。"""
    engine = object.__new__(PaperTradingEngine)
    engine.account_name = '__req_fc43_gate_probe__'
    engine.initial_capital = 100000.0
    engine.repo = repo
    return engine


def _service(repo):
    """零价格源即可：假账户无持仓 → `all_symbols` 为空，不会走价格取数。"""
    return DailySnapshotService(sim_repo=repo, price_provider=lambda *a: {})


class TestServicePathRefusedCount:
    """① ②：`snapshot_all_accounts` 汇总 refused（拒写账户）与 trading_day 五键"""

    def test_holiday_writes_zero_and_counts_every_account_as_refused(self):
        repo = _FakeSimRepo([_account_ns('acc_a'), _account_ns('acc_b')], upsert_result=None)
        with patch('application.services.trading_day_gate.skip_non_trading_day',
                   return_value=(True, dict(_HOLIDAY_FIVE))):
            out = _service(repo).snapshot_all_accounts(target_date=HOLIDAY_DAY)

        assert out['written'] == 0
        assert out['refused'] == 2, '被闸门拒写的账户不许计入 written'
        assert out['skipped'] == 0, 'refused（门拒写）与 skipped（异常）是两件事'
        assert len(repo.upsert_calls) == 2, '拒写计数来自真实写入尝试，不是提前返回的假设'
        assert set(out['trading_day']) == _FIVE_KEYS
        assert out['trading_day']['source'] == 'trading-calendar-holiday'
        assert out['trading_day']['is_trading_day'] is False

    def test_real_repo_refusal_is_counted_as_refused(self, repo, monkeypatch):
        """① 真仓储联动：门判休市 → `upsert_equity_snapshot` 返回 None → 服务计入 refused 且该日零行。

        上一条用的是假仓储（只验服务的算术）；这一条把**真仓储**接进来，证明
        "None" 这个信号在真实链路上确实会被解读成"拒写"而不是"写入成功"。
        账户枚举打桩成哨兵账户，绝不触碰测试库里的真实账户。
        """
        monkeypatch.setattr(repo, 'list_accounts', lambda status=None: [_account_ns(ACCOUNT)])
        monkeypatch.setattr(repo, 'get_all_positions', lambda account_name: [])
        with patch('application.services.trading_day_gate.skip_non_trading_day',
                   return_value=(True, dict(_HOLIDAY_FIVE))):
            out = _service(repo).snapshot_all_accounts(target_date=HOLIDAY_DAY)

        assert out['written'] == 0
        assert out['refused'] == 1
        assert out['skipped'] == 0
        assert _rows(repo, HOLIDAY_DAY) == []

    def test_trading_day_writes_every_account_and_refuses_none(self):
        repo = _FakeSimRepo([_account_ns('acc_a'), _account_ns('acc_b')],
                            upsert_result=object())        # 非 None = 已落库
        with patch('application.services.trading_day_gate.skip_non_trading_day',
                   return_value=(False, dict(_TRADING_FIVE))):
            out = _service(repo).snapshot_all_accounts(target_date=TRADING_DAY)

        assert out['written'] == 2
        assert out['refused'] == 0
        assert out['trading_day']['is_trading_day'] is True

    def test_gate_is_consulted_with_the_target_day(self):
        """目标日显式传入时，问门的必须是**目标日**（不是"今天"）：否则历史补算会判错日子。"""
        repo = _FakeSimRepo([_account_ns('acc_a')], upsert_result=object())
        with patch('application.services.trading_day_gate.skip_non_trading_day',
                   return_value=(False, dict(_TRADING_FIVE))) as gate:
            _service(repo).snapshot_all_accounts(target_date=TRADING_DAY)
        assert gate.call_args_list[0].args == (TRADING_DAY,)


class TestEngineSnapshotNonePath:
    """③：`take_daily_snapshot` 处理闸门返回 None（不得 AttributeError）"""

    def test_none_snapshot_becomes_skipped_structure(self):
        repo = _FakeEngineRepo(snapshot=None)
        with patch('application.services.trading_day_gate.skip_non_trading_day',
                   return_value=(True, dict(_HOLIDAY_FIVE))):
            out = _engine(repo).take_daily_snapshot()       # 旧实现此处 AttributeError

        assert out['skipped'] is True
        assert '非交易日' in out['reason']
        assert out['trading_day_source'] == 'trading-calendar-holiday'
        assert set(out['trading_day']) == _FIVE_KEYS
        # 不写快照就不动账户表：否则账户表领先净值序列一天（口径分叉）
        assert repo.account_updates == []
        assert repo.drawdown_recomputes == []

    def test_written_snapshot_path_unchanged(self):
        """对照：正常落库时仍返回 nav/daily_return（早退分支不许吃掉原契约）。"""
        repo = _FakeEngineRepo(snapshot=SimpleNamespace(daily_return=0.0123))
        with patch('application.services.trading_day_gate.skip_non_trading_day',
                   return_value=(False, dict(_TRADING_FIVE))):
            out = _engine(repo).take_daily_snapshot()

        assert 'skipped' not in out
        assert out['nav'] == pytest.approx(1.01)
        assert out['daily_return'] == pytest.approx(0.0123)
        assert len(repo.account_updates) == 1


class TestBothPathsUseTheSingleGate:
    """⑥：两条路径都问同一个门（防各自另写判定）"""

    def test_service_and_engine_both_consume_the_shared_verdict(self):
        with patch('application.services.trading_day_gate.skip_non_trading_day',
                   return_value=(True, dict(_HOLIDAY_FIVE))) as gate:
            svc_repo = _FakeSimRepo([_account_ns('acc_a')], upsert_result=None)
            out_svc = _service(svc_repo).snapshot_all_accounts(target_date=HOLIDAY_DAY)
            assert gate.call_count >= 1, '服务路径没问门 → 可能自写了交易日判定'
            assert gate.call_args_list[0].args == (HOLIDAY_DAY,)

            gate.reset_mock()
            eng_repo = _FakeEngineRepo(snapshot=None)
            out_eng = _engine(eng_repo).take_daily_snapshot()
            assert gate.call_count >= 1, '引擎路径没问门 → 可能自写了交易日判定'
            assert gate.call_args_list[0].args == (date.today(),)

        # 两边的注解都必须是门给的那份（自判的话拿不到这个 reason）
        assert out_svc['trading_day'] == _HOLIDAY_FIVE
        assert out_eng['trading_day'] == _HOLIDAY_FIVE

