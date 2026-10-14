"""一次性真端到端探针：休市日执行体是否真的只留痕、不干活（REQ-261006093620-a315 · t5）

**刻意不进 `tests/` 测试集**：断言依赖"今天恰好不是交易日"，进集会随日历假红。
它跑在 pytest 下（借根 conftest 的**测试库**自动切换，避免污染生产库），由人手工调用：

    ./venv/bin/python -m pytest docs/requirements/REQ-261006093620-a315/notes/test_e2e_holiday_skip_probe.py -q

与 `tests/infrastructure/test_scheduler_skip_ledger.py` 的分工：
- 那边用假仓储/假门验**分支语义**（含 manual 旁路与零调用断言）；
- 这边用**真仓储 + 真门 + 真库**验"接线真的通了"：门→skipped 落账→命令未执行。
  门若没接上，`_execute_command` 会真去跑 `__nonexistent_probe__`（快速失败，不会拖慢）。
"""
from __future__ import annotations

import time

from sqlalchemy import text

from infrastructure.persistence.orm import get_session
from infrastructure.scheduler import job_executor as je


def test_holiday_skip_end_to_end():
    session = get_session()
    task_id = None
    skip_probe = f'__t5_e2e_{int(time.time())}__'
    try:
        task_id = session.execute(text(
            "insert into quant.scheduler_tasks "
            "(name, cron_expression, command, is_enabled, trading_day_policy) "
            "values (:n, '25 9 * * 1-5', '__nonexistent_probe__', true, 'trading-days') returning id"
        ), {'n': skip_probe}).scalar()
        session.commit()

        je._execute_scheduled_job_impl(task_id)      # 自动到点（manual 缺省 False）

        row = session.execute(text(
            "select status, error, result from quant.scheduler_runs "
            "where task_id = :i order by id desc limit 1"
        ), {'i': task_id}).mappings().first()

        print('\n[e2e] run.status =', row['status'])
        print('[e2e] run.error  =', row['error'])
        print('[e2e] result     =', dict(row['result'] or {}))

        assert row['status'] == 'skipped', '休市日自动到点必须只留痕'
        assert row['error'] is None, '跳过不是失败'
        assert row['result']['skipped'] is True
        assert row['result']['trading_day_source'] == 'trading-calendar-holiday'
        assert row['result']['policy'] == 'trading-days'
    finally:
        if task_id is not None:
            session.execute(text("delete from quant.scheduler_runs where task_id = :i"), {'i': task_id})
            session.execute(text("delete from quant.scheduler_tasks where id = :i"), {'i': task_id})
            session.commit()
        session.close()
