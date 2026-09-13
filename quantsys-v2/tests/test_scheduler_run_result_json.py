"""调度运行记录 JSONB 写入回归（2026-09-13，w-32314d00）

事故链：ingest_events_daily 的 handler 明确成功（712 条事件），但**任务被记成 failed**——
因为 complete_run 把返回值直接写进 JSONB 列，而返回值里含 datetime.date →
SQLAlchemy json 序列化抛 TypeError（Query-invoked autoflush / StatementError /
Object of type date is not JSON serializable），UPDATE 失败。
后果：任务"成功却记失败"，并刷出多张错误事件卡（09-12 17:01 一批即由此而来）。

修复：complete_run 写库前统一过 _json_safe（adapters.shared.json_helpers.sanitize_for_json）。
本文件锁定：①_json_safe 把 date/datetime/Decimal 等转成可序列化形态；②complete_run 写入的
result 一定可 json.dumps；③不得因为"记录写不进去"而丢成功状态。
"""
import json
from datetime import date, datetime, timezone
from decimal import Decimal

from adapters.outbound.repositories.scheduler_repository import SchedulerRepository, _json_safe


def test_json_safe_converts_non_serializable():
    payload = {
        'status': 'success',
        'trade_date': date(2026, 9, 13),
        'ts': datetime(2026, 9, 13, 14, 28, 6, tzinfo=timezone.utc),
        'amount': Decimal('123.45'),
        'nested': [{'d': date(2020, 2, 4)}],
    }
    out = _json_safe(payload)
    json.dumps(out, ensure_ascii=False)          # 不抛即通过
    assert '2026-09-13' in json.dumps(out, ensure_ascii=False)
    assert out['nested'][0]['d'] is not None


def test_json_safe_passthrough_for_plain_values():
    assert _json_safe(None) is None
    assert _json_safe({'a': 1, 'b': 'x'}) == {'a': 1, 'b': 'x'}


class _Run:
    def __init__(self):
        self.task_id = 331
        self.status = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.started_at = datetime(2026, 9, 13, 14, 28, 6, tzinfo=timezone.utc)
        self.duration_ms = None


class _Config:
    cron_expression = '0 17 * * *'
    next_run_at = None


class _Session:
    def __init__(self, run):
        self._run = run
        self.committed = False

    def get(self, model, key):
        return self._run if model.__name__ == 'SchedulerRun' else _Config()

    def commit(self):
        self.committed = True


def _repo_with(run):
    repo = SchedulerRepository.__new__(SchedulerRepository)
    # session 是属性 → 用实例属性遮蔽（测试替身，不碰真库）
    repo.__dict__['_session'] = _Session(run)
    return repo


def test_complete_run_sanitizes_result_before_jsonb_write():
    run = _Run()
    repo = _repo_with(run)
    # 复刻真实 payload：含 date 的成功结果
    ok = repo.complete_run(1, success=True,
                           result={'status': 'success', 'trade_date': date(2026, 9, 13),
                                   'events': [{'d': date(2020, 2, 4)}]})
    assert ok is True
    assert run.status == 'success'
    json.dumps(run.result, ensure_ascii=False)   # 关键断言：写进去的一定可序列化
    assert '2026-09-13' in json.dumps(run.result, ensure_ascii=False)
