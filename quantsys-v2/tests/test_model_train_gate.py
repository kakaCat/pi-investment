"""模型重训门控回归（REQ-a458a6 t1，2026-09-14 w-4db568de）

锁定三个已实证缺陷（见 REQ-a458a6 与 quant.scheduler_runs 3706/3676）：

1. **阈值语义**：判定原为 (now - train_date).days（向下取整）配 > 7，等价「满 8 天才算
   过期」，且与「每 7 天训一次」的节律自我抵消 —— 03:00:11 训出的模型在下周一 03:00
   复查只有 6d23h59m（floor=6）→ 必然跳过。遗留证据：2026-09-13 03:30 的 runs 记
   age=7d，而该模型真实年龄 7.69 天。现改为秒级阈值 6 天（节律 7 天，留 1 天余量）。
2. **train_date 缺失**：原把整段年龄判断放在 if train_date_str 内，缺失时 days_old
   从未赋值却在函数末尾 f-string 中被引用 → UnboundLocalError，任务异常结束且无 reason。
3. **acc 缺值**：原末尾 f-string 直接格式化 test_accuracy，None 会 TypeError。
"""
from datetime import datetime, timedelta

import application.services.scheduler_tasks as st


class _Repo:
    def __init__(self, record):
        self._record = record

    def get_by_type_version(self, model_type, version):
        return self._record


def _check(monkeypatch, *, train_date, test_acc=0.60, version='20260914_030011'):
    """打桩数据源与线程会话释放，返回 _check_train_needed 的判定。"""
    import adapters.shared.ml_helpers as H

    record = {'model_type': 'lightgbm', 'version': version,
              'train_date': train_date, 'test_accuracy': test_acc}
    monkeypatch.setattr(H, '_resolve_latest_version', lambda _t: version, raising=True)
    monkeypatch.setattr(H, '_get_model_repo', lambda: _Repo(record), raising=True)
    monkeypatch.setattr(st, '_release_thread_session', lambda: None, raising=True)
    return st._check_train_needed('lightgbm')


def _days_ago(d):
    return datetime.now().astimezone() - timedelta(days=d)


def test_fresh_model_skips_with_age_and_threshold(monkeypatch):
    ok, reason = _check(monkeypatch, train_date=_days_ago(5.9))

    assert ok is False
    assert '仍有效' in reason
    assert '5.9d' in reason, reason       # 一位小数：不再只给 floor 整数
    assert '6d' in reason and '0.6000' in reason


def test_seven_day_old_model_must_train(monkeypatch):
    """回归核心：7.0 天在旧实现里 floor=7 → 判「仍有效」跳过；现在必须重训。"""
    ok, reason = _check(monkeypatch, train_date=_days_ago(7.0))

    assert ok is True
    assert '未更新' in reason and '阈值6天' in reason


def test_age_just_under_threshold_still_skips(monkeypatch):
    ok, _ = _check(monkeypatch, train_date=_days_ago(5.99))
    assert ok is False


def test_age_at_threshold_trains(monkeypatch):
    ok, _ = _check(monkeypatch, train_date=_days_ago(6.0) - timedelta(seconds=1))
    assert ok is True


def test_eight_day_old_model_trains(monkeypatch):
    ok, _ = _check(monkeypatch, train_date=_days_ago(8.0))
    assert ok is True


def test_low_accuracy_trains_even_when_fresh(monkeypatch):
    ok, reason = _check(monkeypatch, train_date=_days_ago(1), test_acc=0.54)

    assert ok is True
    assert '性能低' in reason and '0.54' in reason


def test_missing_train_date_trains_with_reason(monkeypatch):
    """原实现此处抛 UnboundLocalError；现在必须给出明确 reason。"""
    ok, reason = _check(monkeypatch, train_date=None)

    assert ok is True
    assert '缺 train_date' in reason


def test_unparsable_train_date_trains_with_reason(monkeypatch):
    ok, reason = _check(monkeypatch, train_date='not-a-date')

    assert ok is True
    assert '缺 train_date' in reason


def test_missing_accuracy_does_not_crash(monkeypatch):
    ok, reason = _check(monkeypatch, train_date=_days_ago(1), test_acc=None)

    assert ok is False
    assert 'acc=N/A' in reason


def test_naive_train_date_treated_as_local_wall_clock(monkeypatch):
    naive = (datetime.now() - timedelta(days=3)).replace(microsecond=0)

    ok, reason = _check(monkeypatch, train_date=naive)

    assert ok is False
    assert '3.0d' in reason, reason
