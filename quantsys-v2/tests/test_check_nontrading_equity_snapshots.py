"""巡检器活性测试（REQ-261006190953-fc43 卡 G）

「检查器恒回 0」等于没有检查器。本文件用**造脏行**证明它是活的：
① 有可用日历 + 零违规 → 退出码 0；② 造一行范围内非交易日行 → 退出码 2 且列出账户/日期；
③ 范围外的行 → 只 warn、不计违规；④ 日历空表 → 退出码 3（判不了，不许报成干净）；
⑤ `is_synthetic` 失真声明已从 trading_day_guard 的 docstring 删除。

口径与清理迁移**同源**（白名单语义，裁定 D-6）：违规 = 覆盖范围内 且 不在交易日清单里。
测试全部在 `quant_test` 上跑，前后自清（本仓测试库的日历表基线是**空表**，别的用例依赖这一点）。
"""
from datetime import date

import pytest
from sqlalchemy import text

from tools.check_nontrading_equity_snapshots import (
    EXIT_OK,
    EXIT_UNUSABLE,
    EXIT_VIOLATION,
    check,
)

ACCOUNT = '__req_fc43_check_test__'
LO = date(2030, 3, 1)      # 覆盖窗口下沿（日历里标为交易日）
HI = date(2030, 3, 29)     # 覆盖窗口上沿
DIRTY = date(2030, 3, 13)  # 窗口内、不在清单里 → 非交易日（白名单语义）
OUTSIDE = date(2031, 7, 7)  # 窗口外 → 无法判定


@pytest.fixture()
def session():
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

    repo = SimulationORMRepository()
    s = repo.session
    _clean(s)
    yield s
    _clean(s)
    try:
        s.close()
    except Exception:  # noqa: BLE001 —— 收尾关连接失败不该让用例变红
        pass


def _clean(s):
    s.execute(text("delete from quant.simulation_equity_snapshot where account_name = :a"),
              {'a': ACCOUNT})
    s.execute(text("delete from quant.trading_calendar where trade_date in (:lo, :hi)"),
              {'lo': LO, 'hi': HI})
    s.commit()


def _seed_window(s):
    """造覆盖窗口：只插两沿的**交易日**行（白名单语义下，缺行即非交易日）。"""
    s.execute(text("""
        insert into quant.trading_calendar (trade_date, exchange, is_trading_day)
        values (:lo, 'ALL', true), (:hi, 'ALL', true)
        on conflict do nothing
    """), {'lo': LO, 'hi': HI})
    s.commit()


def _seed_snapshot(s, day):
    s.execute(text("""
        insert into quant.simulation_equity_snapshot
          (account_name, snapshot_date, cash, position_value, total_value,
           daily_return, cumulative_return, drawdown)
        values (:a, :d, 0, 100, 100, 0, 0, 0)
        on conflict (account_name, snapshot_date) do nothing
    """), {'a': ACCOUNT, 'd': day})
    s.commit()


def test_clean_window_exits_zero(session):
    """① 有可用日历 + 零违规 → 退出码 0。"""
    _seed_window(session)
    code, lines = check(session, accounts=ACCOUNT)
    assert code == EXIT_OK, lines
    assert any('零违规' in ln for ln in lines)


def test_in_range_non_trading_row_is_a_violation(session):
    """② 造一行窗口内非交易日行 → 退出码 2，且输出含账户与日期。"""
    _seed_window(session)
    _seed_snapshot(session, DIRTY)
    code, lines = check(session, accounts=ACCOUNT)
    assert code == EXIT_VIOLATION, lines
    assert any(ACCOUNT in ln and str(DIRTY) in ln for ln in lines), lines


def test_out_of_range_row_is_only_a_warning(session):
    """③ 覆盖范围外的行 → warn 单列，不计违规（退出码仍 0）。"""
    _seed_window(session)
    _seed_snapshot(session, OUTSIDE)
    code, lines = check(session, accounts=ACCOUNT)
    assert code == EXIT_OK, lines
    assert any('[warn]' in ln and str(OUTSIDE) in ln for ln in lines), lines
    assert not any(ln.startswith('[violation]') for ln in lines), lines


def test_empty_calendar_is_unusable_not_clean(session):
    """④ 日历空表 → 退出码 3：判不了就是判不了，不许报成"干净"。"""
    _seed_snapshot(session, DIRTY)   # 有行，但日历空 → 无从判定
    code, lines = check(session, accounts=ACCOUNT)
    assert code == EXIT_UNUSABLE, lines
    assert any('无法判定' in ln for ln in lines), lines


def test_is_synthetic_claim_is_gone_from_guard_docstring():
    """⑤ 未实现却被写成既成事实的 `is_synthetic` 声明已删除。"""
    text_src = (
        __import__('pathlib').Path('application/services/trading_day_guard.py')
        .read_text(encoding='utf-8')
    )
    assert 'is_synthetic' not in text_src


def test_checker_own_failure_is_loud():
    """检查器自身异常 → 退出码 3（不是 0，也不是抛栈给调用方）。"""
    from tools.check_nontrading_equity_snapshots import main

    # 用一个必然连不上的 DSN 触发连接失败
    assert main(['--dsn', 'postgresql://nobody@127.0.0.1:1/nope']) == EXIT_UNUSABLE
