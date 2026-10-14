#!/usr/bin/env python
"""V13 定时任务的**接线**测试（REQ-261004154902-a7cd · t2 / FR-1 / FR-2）。

## 2026-10-04 重写说明（这是一次「假绿灯」清理）

原文件三条 `test_*` 的写法是 `return True / return False`——pytest **忽略返回值**，
于是它们在控制台打印「❌ Job执行失败」「❌ 任务不存在」的同时报 **3 passed**。
实测输出（改前）：

    tests/test_v13_scheduler.py ... 3 passed, 4 warnings
    （-s 可见：❌ Job执行失败 / ❌ 任务不存在）

现在改为**真断言**，并且不再依赖库里那条 `v13-simulation-trading` 任务行是否存在
（它会随运维动作启用/停用，例如 2026-10-04 的止血就把它停用了）——
改为断言**接线关系**：job 薄壳转发、handler 转发、注册脚本的定义意图。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


# ── [1/3] job 薄壳必须转发到统一实现 ────────────────────────────────────────

def test_job_module_delegates_to_unified_service(monkeypatch):
    """`v13_daily_check` 是兼容薄壳：必须把 'v13' 转发给统一入口。"""
    from infrastructure.jobs import strategy_trading_job as job

    forwarded = {}

    def fake_strategy_daily_check(strategy_name, **params):
        forwarded['strategy_name'] = strategy_name
        forwarded['params'] = params
        return {'strategy': strategy_name, 'status': 'success'}

    monkeypatch.setattr(job, 'strategy_daily_check', fake_strategy_daily_check)

    result = job.v13_daily_check(enable_stop_loss=True, enable_rebalance=True)

    assert forwarded['strategy_name'] == 'v13'
    assert forwarded['params'] == {'enable_stop_loss': True, 'enable_rebalance': True}
    assert result['strategy'] == 'v13'


def test_job_module_is_importable():
    from infrastructure.jobs.strategy_trading_job import v13_daily_check

    assert callable(v13_daily_check)


# ── [2/3] scheduler handler 必须转发到 job ─────────────────────────────────

def test_scheduler_handler_delegates_to_job(monkeypatch):
    """`SchedulerService._handle_v13_daily_check` 只做转发，参数原样透传。"""
    from infrastructure.scheduler.scheduler import SchedulerService

    captured = {}

    def fake_execute(**params):
        captured.update(params)
        return {'status': 'success', 'task': 'v13_daily_check'}

    # handler 内部是延迟导入（`from ... import v13_daily_check as execute`），
    # 所以打在定义模块上才生效（打桩点规则见 CLAUDE.md）
    monkeypatch.setattr(
        'infrastructure.jobs.strategy_trading_job.v13_daily_check',
        fake_execute,
        raising=True,
    )

    scheduler = object.__new__(SchedulerService)  # 跳过 __init__ 的 DB 依赖
    result = scheduler._handle_v13_daily_check({'enable_rebalance': False})

    assert result['status'] == 'success'
    assert captured == {'enable_rebalance': False}


def test_scheduler_has_v13_handler_registered():
    """调度命令表里必须真的有 v13_daily_check → handler 的映射。"""
    from infrastructure.scheduler.scheduler import SchedulerService

    source = Path(SchedulerService.__module__.replace('.', '/') + '.py')
    text = (PROJECT_ROOT / source).read_text(encoding='utf-8')
    assert re.search(r"['\"]v13_daily_check['\"]\s*:", text), '命令表里找不到 v13_daily_check'


# ── [3/3] 注册脚本的定义意图 ───────────────────────────────────────────────

def test_registration_defines_v13_job_with_expected_wiring():
    """注册脚本必须仍声明 v13 日检，且旧名已标注弃用、指向统一入口。

    2026-10-04 实测：脚本里 `v13_daily_check` 条目 `enabled: False` +
    `replaced_by: strategy_execute_all`；统一任务 `strategy_execute_all` 的 cron 是
    `0 30 14 * * 1-5`（工作日 14:30）——这也正是 t5 把库内 cron 改回 14:30 的依据。
    """
    reg = PROJECT_ROOT / 'tools' / 'register_jobs_to_agent_os.py'
    if not reg.exists():  # pragma: no cover - 文件被移动时给出明确失败原因
        pytest.fail(f'注册脚本不存在: {reg}')

    text = reg.read_text(encoding='utf-8')
    assert '"name": "v13_daily_check"' in text, 'v13 日检的注册条目丢失'
    assert '"replaced_by": "strategy_execute_all"' in text, '旧任务未标注被谁取代'
    assert '"name": "strategy_execute_all"' in text, '统一入口任务定义丢失'


def test_registration_declares_the_1430_slot():
    """注册脚本声明的时段必须是 14:30（与 v13.yaml / 文档一致，供 t5 对齐库内 cron）。"""
    reg = PROJECT_ROOT / 'tools' / 'register_jobs_to_agent_os.py'
    text = reg.read_text(encoding='utf-8')
    assert '30 14 * * 1-5' in text, '注册脚本不再声明 14:30 时段——时段口径被谁改了？'


def test_legacy_v13_task_name_is_deprecated_not_primary():
    """旧任务名 v13-daily-check（command=v13_trading，无 handler）不得再被启用。"""
    reg = PROJECT_ROOT / 'tools' / 'register_jobs_to_agent_os.py'
    text = reg.read_text(encoding='utf-8')
    if '"name": "v13_daily_check"' in text or "'name': 'v13_daily_check'" in text:
        # 若脚本里出现旧名，必须同时带 enabled: False
        block = text.split('v13_daily_check', 1)[1][:400]
        assert 'False' in block, '旧任务名出现却未见 enabled=false——它没有 handler，一触发必失败'
