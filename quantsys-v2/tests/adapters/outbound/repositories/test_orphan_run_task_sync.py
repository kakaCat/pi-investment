"""孤儿 run 回收必须同步任务行（2026-09-11，w-f436d4ea）

背景（实测任务 232『每日数据质量检查』）：APScheduler 跑在 API 进程内，进程重启会打断
run 的收尾记账。recover_orphan_runs 启动时把 run 闭环为 failed —— 但**原先完全不碰任务行**，
于是任务列表呈现为「failed 且 last_error 为空」+「next_run_at 停在被打断那一刻」，
排查入口（scheduler_tasks.last_error）读不到任何原因，原因只躺在 scheduler_runs.error 里。
证据：任务 232 的 updated_at 停在 22:00:00.09（= create_run 那一刻），而 run 在 22:06:45
被回收 —— 说明回收路径从未更新过该行。

本测试锁住：回收 run 的同时必须回写任务行的 last_status / last_error / next_run_at，
且 managed_by_agent_ 伪任务不参与 next_run 计算（与 complete_run 同口径）。

不触网不写库：session 为桩。
"""
from datetime import datetime, timedelta, timezone

from adapters.outbound.repositories.scheduler_repository import SchedulerRepository


class _Run:
    def __init__(self, rid, task_id, started_at, status='running'):
        self.id, self.task_id, self.started_at, self.status = rid, task_id, started_at, status
        self.completed_at = None
        self.error = None
        self.duration_ms = None


class _Config:
    def __init__(self, task_id, cron, last_status=None, last_error=None, next_run_at=None):
        self.id = task_id
        self.cron_expression = cron
        self.last_status = last_status
        self.last_error = last_error
        self.next_run_at = next_run_at


class _Query:
    def __init__(self, runs):
        self._runs = runs

    def filter(self, *a, **kw):
        return self

    def all(self):
        return self._runs


class _Session:
    def __init__(self, runs, configs):
        self._runs, self._configs = runs, configs
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        return _Query(self._runs)

    def get(self, model, pk):
        return self._configs.get(pk)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _repo(runs, configs):
    # session 是只读 property（读 self._session），直接设 _session 注入桩
    r = SchedulerRepository.__new__(SchedulerRepository)
    r._session = _Session(runs, configs)
    return r


def test_回收时同步回写任务行的状态与原因():
    old = datetime.now(timezone.utc) - timedelta(hours=2)   # 早于 60s 竞争护栏
    run = _Run(9001, 232, old)
    cfg = _Config(232, '0 22 * * *', last_status='running', next_run_at=None)

    repo = _repo([run], {232: cfg})
    recovered = repo.recover_orphan_runs()

    assert recovered == [9001]
    assert run.status == 'failed' and run.error                     # run 仍照常闭环
    assert cfg.last_status == 'failed'
    assert cfg.last_error, '失败必须留下原因——否则看板显示 failed 却无可解释信息（本次事故本体）'
    assert '孤儿' in cfg.last_error
    assert cfg.next_run_at is not None, 'next_run_at 必须推进，不能停在被打断那一刻'


def test_刚创建的run不回收也不误标任务():
    """60 秒竞争护栏：同进程并发启动的 run 不得被回收。"""
    fresh = datetime.now(timezone.utc)
    run = _Run(9002, 233, fresh)
    cfg = _Config(233, '0 22 * * *', last_status='running')

    repo = _repo([run], {233: cfg})
    assert repo.recover_orphan_runs() == []
    assert cfg.last_status == 'running', '未回收就不该把任务标成 failed'
    assert cfg.last_error is None


def test_managed_by_agent伪任务不计算next_run():
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    run = _Run(9003, 240, old)
    cfg = _Config(240, 'managed_by_agent_os', last_status='running')

    repo = _repo([run], {240: cfg})
    repo.recover_orphan_runs()

    assert cfg.last_status == 'failed' and cfg.last_error
    assert cfg.next_run_at is None, '伪任务无真实调度，不得计算 next_run（同 complete_run 口径）'


def test_任务行缺失时不炸():
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    repo = _repo([_Run(9004, 999, old)], {})
    assert repo.recover_orphan_runs() == [9004]
