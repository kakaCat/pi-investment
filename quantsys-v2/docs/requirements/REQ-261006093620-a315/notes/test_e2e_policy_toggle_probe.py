"""一次性真端到端探针：**改一行策略即生效、无需 reload**（REQ-261006093620-a315 · t8 回滚演练）

验的是设计里那条关键承诺（FR-7）：门放在**执行期**，所以回滚 = 把策略改回 `always`，
**不需要重启、不需要 POST /api/scheduler/reload**。

刻意不进 `tests/` 测试集（依赖"今天不是交易日"），由人手工调用：

    ./venv/bin/python -m pytest docs/requirements/REQ-261006093620-a315/notes/test_e2e_policy_toggle_probe.py -q -s

跑在 pytest 下 → 借根 conftest 的**测试库**自动切换，不污染生产库；自建自删。
"""
from __future__ import annotations

import time

from sqlalchemy import text

from infrastructure.persistence.orm import get_session
from infrastructure.scheduler import job_executor as je


def _runs(session, task_id):
    return session.execute(text(
        "select status, result from quant.scheduler_runs where task_id = :i order by id"
    ), {'i': task_id}).mappings().all()


def test_policy_toggle_takes_effect_without_reload(monkeypatch):
    """⚠️ 必须打两处桩（2026-10-06 首版被 notify-guard 判红，实测）：

    首版故意让第 ② 步执行一个不存在的命令 → 执行失败 → 触发 `_report_failure_to_sink`
    → 起了真通知链并**尝试向 Agent OS 外发**（被 `tests/notify_guard.py` 拦截，`egress=0`，
    用户无感知，但用例被判 "发生真实通知外发"）。
    本探针只想验"策略改一行即生效"，不该顺带验通知——故：
      ① 把 `_execute_command` 换成无害成功（不碰 JobRegistry，不制造失败）；
      ② 顺手把 `_report_failure_to_sink` 也换成空实现（双保险）。
    """
    monkeypatch.setattr(je, '_execute_command', lambda command, params: {'status': 'success'})
    monkeypatch.setattr(je, '_report_failure_to_sink', lambda *a, **k: None)

    session = get_session()
    task_id = None
    probe = f'__t8_toggle_{int(time.time())}__'
    try:
        task_id = session.execute(text(
            "insert into quant.scheduler_tasks "
            "(name, cron_expression, command, is_enabled, trading_day_policy) "
            "values (:n, '25 9 * * 1-5', '__nonexistent_probe__', true, 'trading-days') returning id"
        ), {'n': probe}).scalar()
        session.commit()

        # ① 策略 = trading-days（今日休市）→ 应跳过、不执行
        je._execute_scheduled_job_impl(task_id)
        first = _runs(session, task_id)[-1]
        print('\n[① trading-days] status =', first['status'])
        assert first['status'] == 'skipped'

        # ② 只改一行策略（不重启、不 reload）→ 下一次执行**立即**照跑
        session.execute(text(
            "update quant.scheduler_tasks set trading_day_policy='always' where id=:i"
        ), {'i': task_id})
        session.commit()

        je._execute_scheduled_job_impl(task_id)
        second = _runs(session, task_id)[-1]
        print('[② always]      status =', second['status'], '（不再跳过 ⇒ 门已按新策略放行）')
        assert second['status'] != 'skipped', '策略改回 always 后必须照跑（免 reload 生效）'

        # ③ 再改回 trading-days → 又跳（回滚是可逆的）
        session.execute(text(
            "update quant.scheduler_tasks set trading_day_policy='trading-days' where id=:i"
        ), {'i': task_id})
        session.commit()
        je._execute_scheduled_job_impl(task_id)
        third = _runs(session, task_id)[-1]
        print('[③ 改回]        status =', third['status'])
        assert third['status'] == 'skipped'

        print('[结论] 策略改动即时生效、无需 reload；回滚 = 改回 always，可逆。')
    finally:
        if task_id is not None:
            session.execute(text("delete from quant.scheduler_runs where task_id = :i"), {'i': task_id})
            session.execute(text("delete from quant.scheduler_tasks where id = :i"), {'i': task_id})
            session.commit()
        session.close()
