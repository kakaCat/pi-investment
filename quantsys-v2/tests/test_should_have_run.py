"""「该跑没跑」盘点器 + 探针调度活性判据的回归用例（REQ-261004154902-a7cd · FR-8 · t-5103ce）

覆盖卡片点名的 5 条 + 人工裁决追加的 2 条（配置改动护栏、新判据默认观察模式）：

1. 全部按时跑 → 无漏跑、退出码 0；
2. cron 设为「刚刚已过」而 run 表里没有对应记录 → 判 missed、退出码 2；
3. 同一漏跑重复判定**只产生一次告警**（去重 + 边沿生效）；
4. 取数失败 → 判 unknown（不许假装 ok）；
5. `DISABLE_*` 为真时判不健康；
6. 配置改动护栏：应跑时刻早于 `updated_at` → 不计漏跑（可关）；
7. 新判据默认**观察模式**：算得出、看得见、不外发；`HEALTH_PROBE_SCHEDULER_ALERT=true` 才计入。

**零 DB / 零网络 / 零外发**：取数走 `FakeSource` 注入，端口与新鲜度探针打桩，
通知走注入的 `sender` 假函数（且 dry-run 分支不写节流状态）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from application.services import should_have_run as shr
from tools import check_should_have_run, health_probe

TZ = shr.TZ
OLD_CHANGE = datetime(2026, 9, 1, 9, 0, tzinfo=TZ)  # 与判定无关的"很久以前改过配置"


def mk_task(
    task_id: int = 1,
    name: str = "任务A",
    cron: str = "0 15 * * 1-5",
    updated_at: datetime | None = OLD_CHANGE,
) -> shr.ScheduledTask:
    return shr.ScheduledTask(
        task_id=task_id, name=name, cron_expression=cron, is_enabled=True,
        updated_at=updated_at,
    )


class FakeSource:
    """可注入取数口：假日志（任务清单）+ 假 run 列表，零 DB 零网络。"""

    def __init__(
        self,
        tasks,
        runs=None,
        missed=None,
        handled=None,
        *,
        fail_tasks: bool = False,
        fail_runs: bool = False,
    ) -> None:
        self.tasks = list(tasks)
        self.runs = dict(runs or {})
        self.missed = dict(missed or {})
        #: 已处理（含 skipped）。既有用例只喂 runs → 见 latest_handled_run 的回落，行为不变。
        self.handled = dict(handled or {})
        self.fail_tasks = fail_tasks
        self.fail_runs = fail_runs

    def list_enabled_tasks(self):
        if self.fail_tasks:
            raise RuntimeError("模拟连不上库")
        return self.tasks

    def latest_run(self, task_id):
        if self.fail_runs:
            raise RuntimeError("模拟 run 取数失败")
        return self.runs.get(int(task_id))

    def latest_handled_run(self, task_id):
        """已处理（含 skipped）。**未显式喂 handled 时回落到 runs**，既有用例行为不变。"""
        return self.handled.get(int(task_id)) or self.runs.get(int(task_id))

    def latest_missed_run(self, task_id):
        return self.missed.get(int(task_id))


def run_record(task_id: int, when: datetime, status: str = "success") -> shr.RunRecord:
    return shr.RunRecord(task_id=task_id, status=status, started_at=when)


def verdict_of(report: shr.ShouldHaveRunReport, name: str) -> shr.ShouldHaveRunVerdict:
    return next(v for v in report.verdicts if v.task_name == name)


# ── ① 全部按时跑 → 无漏跑、退出码 0 ──────────────────────────────────────

def test_all_on_time_reports_no_miss():
    """两个任务都在应跑时刻之后跑过 → 无漏跑。"""
    now = datetime(2026, 10, 5, 16, 0, tzinfo=TZ)  # 周一 16:00
    tasks = [mk_task(1, "任务A", "0 15 * * 1-5"), mk_task(2, "任务B", "30 9 * * 1-5")]
    src = FakeSource(tasks, runs={
        1: run_record(1, datetime(2026, 10, 5, 15, 0, 5, tzinfo=TZ)),
        2: run_record(2, datetime(2026, 10, 5, 9, 30, 2, tzinfo=TZ)),
    })

    report = shr.audit_should_have_run(now=now, source=src)

    assert report.ok is True
    assert report.missed == ()
    assert report.unknown == ()
    assert verdict_of(report, "任务A").expected_slot == datetime(2026, 10, 5, 15, 0, tzinfo=TZ)
    assert verdict_of(report, "任务A").verdict == shr.VERDICT_OK


def test_checker_cli_exits_zero_when_all_on_time(monkeypatch, capsys):
    now = datetime(2026, 10, 5, 16, 0, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "任务A", "0 15 * * 1-5")],
        runs={1: run_record(1, datetime(2026, 10, 5, 15, 0, 3, tzinfo=TZ))},
    )
    monkeypatch.setattr(shr, "SqlShouldHaveRunSource", lambda *a, **k: src)

    code = check_should_have_run.main(["--now", now.isoformat()])

    out = capsys.readouterr().out
    assert code == check_should_have_run.EXIT_OK
    assert "任务" in out and "最近应跑" in out and "实际最近 run" in out and "判定" in out
    assert "无漏跑。" in out


# ── ② cron「刚刚已过」+ 无对应 run → missed ─────────────────────────────

def test_slot_just_passed_without_run_is_missed():
    """cron 15:00、现在 15:10、run 表里最新一次是昨天 → 该 15:00 那次漏了。"""
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "刚刚该跑的任务", "0 15 * * 1-5")],
        runs={1: run_record(1, datetime(2026, 10, 2, 15, 0, 3, tzinfo=TZ))},
    )

    report = shr.audit_should_have_run(now=now, source=src)
    v = verdict_of(report, "刚刚该跑的任务")

    assert v.verdict == shr.VERDICT_MISSED
    assert v.expected_slot == datetime(2026, 10, 5, 15, 0, tzinfo=TZ)
    assert v.dedup_key == ("刚刚该跑的任务", "2026-10-05T15:00:00+08:00")
    assert report.ok is False


def test_checker_cli_exits_two_on_missed(monkeypatch, capsys):
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "刚刚该跑的任务", "0 15 * * 1-5")],
        runs={1: run_record(1, datetime(2026, 10, 2, 15, 0, 3, tzinfo=TZ))},
    )
    monkeypatch.setattr(shr, "SqlShouldHaveRunSource", lambda *a, **k: src)

    code = check_should_have_run.main(["--now", now.isoformat()])

    captured = capsys.readouterr()
    assert code == check_should_have_run.EXIT_MISSED
    assert "missed" in captured.out
    assert "漏跑：刚刚该跑的任务" in captured.err


def test_missed_row_in_scheduler_runs_is_not_a_run():
    """`status='missed'` 的留痕**不算跑过**（它的 started_at 正是被跳过的排班时刻）。

    否则 t5 新落库的"被跳过"记录会把本模块要抓的东西原地抹掉。
    """
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    slot = datetime(2026, 10, 5, 15, 0, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "被跳过的任务", "0 15 * * 1-5")],
        runs={},  # latest_run 只返回"真执行"，missed 行在另一条查询里
        missed={1: run_record(1, slot, status="missed")},
    )

    v = verdict_of(shr.audit_should_have_run(now=now, source=src), "被跳过的任务")

    assert v.verdict == shr.VERDICT_MISSED
    assert "跳过" in v.reason
    # 口径锁：SQL 取"最近一次真执行"时必须排掉 missed
    assert "<> 'missed'" in shr.SqlShouldHaveRunSource._RUNS_SQL.format(op="<>")


# ── ③ 同一漏跑只告警一次（去重 + 边沿）───────────────────────────────────

def _probe_kwargs(src, tmp_path: Path, sender, now, *, alert: bool = True):
    return dict(
        host="127.0.0.1", api_port=5001, max_lag_days=1, dry_run=False,
        state_path=tmp_path / "state.json", now=now, source=src, sender=sender,
        env={health_probe.SCHEDULER_ALERT_ENV: "true"} if alert else {},
    )


@pytest.fixture
def patched_probes(monkeypatch):
    """端口/新鲜度探针打桩：本文件不碰网络也不碰库。"""
    monkeypatch.setattr(health_probe, "probe_port",
                        lambda host, port, timeout=3.0: {"name": f"{host}:{port}", "ok": True})
    monkeypatch.setattr(health_probe, "probe_freshness",
                        lambda max_lag_days: {"name": "kline_freshness", "ok": True,
                                             "lag_days": 0, "max_lag_days": max_lag_days})


def test_same_miss_alerts_only_once(patched_probes, tmp_path):
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "刚刚该跑的任务", "0 15 * * 1-5")],
        runs={1: run_record(1, datetime(2026, 10, 2, 15, 0, 3, tzinfo=TZ))},
    )
    sent = []
    kwargs = _probe_kwargs(src, tmp_path, lambda payload: sent.append(payload) or {"ok": True}, now)

    first = health_probe.perform_probe(**kwargs)
    second = health_probe.perform_probe(**kwargs)

    assert first == 2 and second == 2          # 两次都判定不健康
    assert len(sent) == 1                      # 但只发了一次（去重生效）
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "missed:刚刚该跑的任务@2026-10-05T15:00:00+08:00" in state["alerted"]
    assert state["last_healthy"] is False


def test_new_miss_alerts_again_and_recovery_rearms_edge(patched_probes, tmp_path):
    """新漏跑要能再响；恢复健康后再次不健康（边沿）也要响——否则等于静音。"""
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    missed_src = FakeSource(
        [mk_task(1, "任务A", "0 15 * * 1-5")],
        runs={1: run_record(1, datetime(2026, 10, 2, 15, 0, 3, tzinfo=TZ))},
    )
    healthy_src = FakeSource(
        [mk_task(1, "任务A", "0 15 * * 1-5")],
        runs={1: run_record(1, datetime(2026, 10, 5, 15, 0, 3, tzinfo=TZ))},
    )
    sent = []
    sender = lambda payload: (sent.append(payload), {"ok": True})[1]

    assert health_probe.perform_probe(**_probe_kwargs(missed_src, tmp_path, sender, now)) == 2
    assert health_probe.perform_probe(**_probe_kwargs(healthy_src, tmp_path, sender, now)) == 0
    assert health_probe.perform_probe(**_probe_kwargs(missed_src, tmp_path, sender, now)) == 2
    assert len(sent) == 2  # 首报 + 恢复后再坏的边沿（中间那次健康不响）


def test_decide_alert_unit():
    keys = ["check:127.0.0.1:5001"]
    assert health_probe.decide_alert(keys, {"alerted": {}, "last_healthy": None})["should_alert"] is True
    assert health_probe.decide_alert(
        keys, {"alerted": {keys[0]: "2026-10-05T00:00:00+08:00"}, "last_healthy": False}
    )["should_alert"] is False
    # 持续不健康但**键没变** → 不响；恢复过再坏（边沿）→ 响
    assert health_probe.decide_alert(
        keys, {"alerted": {keys[0]: "2026-10-05T00:00:00+08:00"}, "last_healthy": True}
    )["should_alert"] is True


def test_probe_down_alerts_once_then_suppresses(monkeypatch, tmp_path):
    """服务停摆（端口不通）→ 首个周期就发一条；持续停摆**不重复刷屏**（504 条的反面）。

    这条是卡片 T16（`kill -9` 后 ≤2 个探测周期内发出「服务停摆」）的逻辑等价物：
    真去 kill 生产进程属维护窗口动作，这里用打桩把"端口不通"注入进来。
    """
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    monkeypatch.setattr(
        health_probe, "probe_port",
        lambda host, port, timeout=3.0: {"name": f"{host}:{port}", "ok": False,
                                         "error": "ConnectionRefusedError: 模拟停摆"},
    )
    monkeypatch.setattr(
        health_probe, "probe_freshness",
        lambda max_lag_days: {"name": "kline_freshness", "ok": True, "lag_days": 0},
    )
    sent = []
    sender = lambda payload: (sent.append(payload), {"ok": True})[1]
    kwargs = _probe_kwargs(FakeSource([]), tmp_path, sender, now, alert=False)

    first = health_probe.perform_probe(**kwargs)
    second = health_probe.perform_probe(**kwargs)

    assert first == 2 and second == 2
    assert len(sent) == 1                       # 只打扰一次
    assert "模拟停摆" in sent[0]["text"]


def test_dry_run_does_not_send_or_write_state(patched_probes, tmp_path):
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    src = FakeSource([mk_task(1, "任务A", "0 15 * * 1-5")], runs={})
    sent = []
    kwargs = _probe_kwargs(src, tmp_path, lambda p: sent.append(p) or {"ok": True}, now)
    kwargs["dry_run"] = True

    code = health_probe.perform_probe(**kwargs)

    assert code == 2
    assert sent == []
    assert not (tmp_path / "state.json").exists()  # 演练不消耗真实告警额度


# ── ④ 取数失败 → unknown（不许假装 ok）──────────────────────────────────

def test_task_list_fetch_failure_is_unknown_and_exit_3(monkeypatch, capsys):
    src = FakeSource([], fail_tasks=True)
    monkeypatch.setattr(shr, "SqlShouldHaveRunSource", lambda *a, **k: src)

    report = shr.audit_should_have_run(now=datetime(2026, 10, 5, 15, 10, tzinfo=TZ), source=src)
    assert report.verdicts[0].verdict == shr.VERDICT_UNKNOWN
    assert report.source_error and "连不上库" in report.source_error
    assert report.ok is True and report.missed == ()  # 但绝不等于"跑过了"：unknown 单独成桶

    code = check_should_have_run.main([])
    assert code == check_should_have_run.EXIT_CHECKER_ERROR
    assert "检查器自身出错" in capsys.readouterr().err


def test_single_task_run_fetch_failure_is_unknown():
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    src = FakeSource([mk_task(1, "任务A", "0 15 * * 1-5")], fail_runs=True)

    report = shr.audit_should_have_run(now=now, source=src)

    assert report.verdicts[0].verdict == shr.VERDICT_UNKNOWN
    assert "取数失败" in report.verdicts[0].reason


def test_unparseable_cron_is_unknown_not_ok():
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    src = FakeSource([mk_task(1, "脏 cron", "30 6 * * 1-5 9")])

    report = shr.audit_should_have_run(now=now, source=src)

    assert report.verdicts[0].verdict == shr.VERDICT_UNKNOWN
    assert "cron 无法判定" in report.verdicts[0].reason


def test_liveness_check_source_error_is_unhealthy(patched_probes):
    """探针视角：**看不见调度**必须判不健康（旧探针三次静默死亡都发生在"看不见"时）。"""
    check = health_probe.probe_scheduler_liveness(
        now=datetime(2026, 10, 5, 15, 10, tzinfo=TZ),
        source=FakeSource([], fail_tasks=True),
        env={},
    )
    assert check["ok"] is False
    assert "取数失败" in check["error"]


# ── ⑤ DISABLE_* 为真 → 判不健康 ─────────────────────────────────────────

@pytest.mark.parametrize("switch", list(health_probe.DISABLE_SWITCHES))
def test_disable_switch_is_unhealthy(switch):
    check = health_probe.probe_disable_switches(env={switch: "true"})

    assert check["ok"] is False
    assert check["disabled"] == [switch]
    assert switch in check["error"]


def test_disable_switch_false_values_are_healthy():
    check = health_probe.probe_disable_switches(
        env={name: "false" for name in health_probe.DISABLE_SWITCHES}
    )
    assert check["ok"] is True and check["disabled"] == []


def test_disable_switch_counts_toward_health_only_when_enabled(patched_probes, tmp_path):
    """默认观察模式：判不健康但**不外发**；开关打开后才计入 health 并告警。"""
    env_off = {"DISABLE_APSCHEDULER": "true"}
    env_on = {"DISABLE_APSCHEDULER": "true", health_probe.SCHEDULER_ALERT_ENV: "true"}
    src = FakeSource([])

    off = health_probe.probe_disable_switches(env=env_off)
    assert off["ok"] is False and off["observe"] is True and off["counts_toward_health"] is False

    sent = []
    sender = lambda payload: (sent.append(payload), {"ok": True})[1]
    base = dict(dry_run=False, state_path=tmp_path / "s.json", now=None, sender=sender)

    code_off = health_probe.perform_probe(max_lag_days=1, env=env_off, source=src, **base)
    sent_while_observing = list(sent)
    code_on = health_probe.perform_probe(max_lag_days=1, env=env_on, source=src, **base)

    assert code_off == 0 and sent_while_observing == []   # 观察：只记账
    assert code_on == 2 and len(sent) == 1                # 打开后：计入 health 并告警
    assert "调度总开关被打开" in sent[0]["text"]


# ── ⑥ 配置改动护栏（人工裁决 2026-10-04）────────────────────────────────

def test_config_guard_exempts_slot_before_last_change():
    """应跑时刻早于 `updated_at` → 不计漏跑，且"应跑时刻"给出**下一个**（未来）。"""
    now = datetime(2026, 10, 4, 16, 30, tzinfo=TZ)  # 周日 16:30
    changed = datetime(2026, 10, 4, 16, 24, 42, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "v13-simulation-trading", "30 14 * * 1-5", updated_at=changed)],
        runs={1: run_record(1, datetime(2026, 9, 12, 23, 43, tzinfo=TZ))},
    )

    report = shr.audit_should_have_run(now=now, source=src)
    v = verdict_of(report, "v13-simulation-trading")

    assert v.verdict == shr.VERDICT_OK
    assert v.guarded is True
    assert v.pre_change_slot == datetime(2026, 10, 2, 14, 30, tzinfo=TZ)
    assert v.expected_slot == datetime(2026, 10, 5, 14, 30, tzinfo=TZ)  # 下一个工作日
    assert report.missed == () and report.guarded == (v,)


def test_config_guard_can_be_disabled_for_review():
    """护栏可关（复核"改动之前就漏了"的缺口）——关掉后同一输入判 missed。"""
    now = datetime(2026, 10, 4, 16, 30, tzinfo=TZ)
    changed = datetime(2026, 10, 4, 16, 24, 42, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "任务A", "30 14 * * 1-5", updated_at=changed)],
        runs={1: run_record(1, datetime(2026, 9, 12, 23, 43, tzinfo=TZ))},
    )

    report = shr.audit_should_have_run(now=now, source=src, apply_config_guard=False)
    v = verdict_of(report, "任务A")

    assert v.verdict == shr.VERDICT_MISSED
    assert v.guarded is False
    assert v.expected_slot == datetime(2026, 10, 2, 14, 30, tzinfo=TZ)


def test_guard_does_not_excuse_slots_after_the_change():
    """护栏只豁免"改动之前"的 slot：改动之后真的没跑，照样 missed（不许变成永久免罪牌）。"""
    now = datetime(2026, 10, 5, 15, 30, tzinfo=TZ)  # 周一 15:30
    changed = datetime(2026, 10, 4, 16, 24, 42, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "任务A", "0 15 * * 1-5", updated_at=changed)],
        runs={1: run_record(1, datetime(2026, 10, 2, 15, 0, tzinfo=TZ))},
    )

    v = verdict_of(shr.audit_should_have_run(now=now, source=src), "任务A")

    assert v.verdict == shr.VERDICT_MISSED
    assert v.guarded is False
    assert v.expected_slot == datetime(2026, 10, 5, 15, 0, tzinfo=TZ)


# ── ⑦ 观察模式（探针侧）────────────────────────────────────────────────

def test_liveness_observe_mode_records_but_does_not_alert(patched_probes, tmp_path):
    """默认（开关 off）：JSON 里 missed 一条不少，但 healthy=True、exit 0、一个字节不外发。"""
    now = datetime(2026, 10, 5, 15, 10, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "刚刚该跑的任务", "0 15 * * 1-5")],
        runs={1: run_record(1, datetime(2026, 10, 2, 15, 0, 3, tzinfo=TZ))},
    )
    sent = []
    kwargs = _probe_kwargs(src, tmp_path, lambda p: sent.append(p) or {"ok": True}, now, alert=False)

    code = health_probe.perform_probe(**kwargs)

    assert code == 0 and sent == []
    check = health_probe.probe_scheduler_liveness(now=now, source=src, env={})
    assert check["ok"] is False                      # 判定是真的
    assert check["observe"] is True                  # 但只是观察
    assert check["counts_toward_health"] is False
    assert check["missed"][0]["task"] == "刚刚该跑的任务"  # 而且看得见
    assert check["dedup_keys"] == ["刚刚该跑的任务@2026-10-05T15:00:00+08:00"]


def test_scheduler_alert_switch_defaults_off():
    assert health_probe.scheduler_alert_enabled({}) is False
    assert health_probe.scheduler_alert_enabled({health_probe.SCHEDULER_ALERT_ENV: "1"}) is True


# ── 时刻推演本身 ────────────────────────────────────────────────────────

def test_previous_slot_respects_standard_cron_and_local_tz():
    """标准 cron（0=周日）+ 本地时区：`0 12 * * 0` 的最近应跑是**周日** 12:00。"""
    now = datetime(2026, 10, 4, 16, 0, tzinfo=TZ)  # 2026-10-04 是周日

    slot = shr.previous_slot("0 12 * * 0", now)

    assert slot == datetime(2026, 10, 4, 12, 0, tzinfo=TZ)
    assert slot.tzinfo is not None and slot.utcoffset() == timedelta(hours=8)


def test_previous_slot_handles_weekday_window():
    """`* * 1-5` 在周日问"最近应跑" → 上周五（周一整体缺失那条老事故的反面）。"""
    now = datetime(2026, 10, 4, 16, 0, tzinfo=TZ)  # 周日

    assert shr.previous_slot("30 14 * * 1-5", now) == datetime(2026, 10, 2, 14, 30, tzinfo=TZ)


# ── ⑧ `skipped`（交易日门按日历跳过）与"真执行"是两件事（REQ-261006093620-a315 t7）──

def test_gate_skipped_slot_is_not_missed():
    """门跳过的槽位 → **ok**（不算漏跑），理由点明是"被交易日门按日历跳过"。"""
    now = datetime(2026, 10, 7, 10, 0, tzinfo=TZ)          # 周三 10:00
    src = FakeSource(
        [mk_task(1, "pre-market-scan", "25 9 * * 1-5")],
        runs={},                                             # 没有真执行
        handled={1: run_record(1, datetime(2026, 10, 7, 9, 25, tzinfo=TZ), status="skipped")},
    )

    report = shr.audit_should_have_run(now=now, source=src)
    v = verdict_of(report, "pre-market-scan")

    assert v.verdict == shr.VERDICT_OK
    assert v.expected_slot == datetime(2026, 10, 7, 9, 25, tzinfo=TZ)
    assert "交易日门" in v.reason and "skipped" in v.reason
    assert report.missed == ()
    # ★ 关键：呈现用的"最近一次真执行"**不含** skipped —— 跳过没有执行过任何东西
    assert v.last_run_at is None
    assert v.last_run_status is None


def test_real_missed_still_alarms_when_skipped_exists_earlier():
    """N5：`skipped` 只豁免它自己那个槽位；更早的跳过留痕不能把真漏跑洗白。"""
    now = datetime(2026, 10, 7, 10, 0, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "pre-market-scan", "25 9 * * 1-5")],
        runs={},
        handled={1: run_record(1, datetime(2026, 10, 6, 9, 25, tzinfo=TZ), status="skipped")},
    )

    report = shr.audit_should_have_run(now=now, source=src)
    v = verdict_of(report, "pre-market-scan")

    assert v.verdict == shr.VERDICT_MISSED                     # 10-07 那次仍然漏了
    assert "交易日门跳过" in v.reason and "早于应跑时刻" in v.reason


def test_missed_run_row_still_alarms():
    """回归锁：`missed`（该跑没跑）**仍然**告警——本次只豁免正常跳过，不放宽真漏跑。"""
    now = datetime(2026, 10, 7, 10, 0, tzinfo=TZ)
    src = FakeSource(
        [mk_task(1, "pre-market-scan", "25 9 * * 1-5")],
        runs={},
        missed={1: run_record(1, datetime(2026, 10, 7, 9, 25, tzinfo=TZ), status="missed")},
    )

    report = shr.audit_should_have_run(now=now, source=src)
    v = verdict_of(report, "pre-market-scan")

    assert v.verdict == shr.VERDICT_MISSED
    assert "status=missed" in v.reason
    assert report.ok is False


def test_handled_and_real_status_sets_are_distinct():
    """两套状态集是写出来的常量，且 skipped 只进"已处理"、不进"真执行"。"""
    assert "skipped" in shr.HANDLED_STATUSES
    assert "skipped" not in shr.REAL_RUN_STATUSES
    assert "missed" not in shr.HANDLED_STATUSES       # 该跑没跑不算"已处理"
    assert shr.HANDLED_STATUSES == ("success", "failed", "skipped")
    assert shr.REAL_RUN_STATUSES == ("success", "failed")


def test_sql_in_list_rejects_unsafe_literal():
    """拼接 IN 列表只吃本模块常量；非 [a-z_] 的字面量必须响亮拒绝（不静默拼进 SQL）。"""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        shr._in_list(("success'; DROP TABLE x; --",))
