"""会话（Session）释放回归 —— session_leak_detected 治理（2026-09-13，w-32314d00，事件 a6780ec3）

现象：session_leak_detected（ERROR，48 次聚合）连续出现，线程分布以 ThreadPoolExecutor-N 与
asyncio_0 / job-* 为主，age 311~359s（刚过 300s 阈值）。

机制：ORM 读操作会 autobegin 一个事务（SQLAlchemy 默认行为），若线程随后做长时间非 DB 工作
（网络抓取、模型训练）或池化线程归还池中，该 Session 仍挂在线程本地注册表且 in_transaction()==True
→ 一直占着连接池的一个连接（idle in transaction）→ session_guard 判泄漏并 rollback+close 止血。

审计出的主要持有者（日志签名）：
  · opportunity_scoring_service._score_single_stock → stock_repository.get_by_symbol（10+ 个池化线程）
  · data_jobs._run → stock_repository.get_all（asyncio.to_thread 线程）
  · scheduler_tasks.handle_model_train_auto → _check_train_needed（训练线程）
  · daily_jobs_bootstrap._job_financial_statements → financial_statement_update_job.execute（宿主任务线程）

本文件锁定「这些路径自己归还会话」，防止再次靠 guard 兜底。
"""
import asyncio
from types import SimpleNamespace

import pytest

import infrastructure.persistence.orm as orm_pkg


@pytest.fixture
def released(monkeypatch):
    """记录线程会话释放调用次数。"""
    calls = []
    monkeypatch.setattr(orm_pkg, "close_session", lambda: calls.append(1), raising=False)
    return calls


class _Gate:
    """数据质量门替身：直接判不足（走 _score_single_stock 早退分支，但 finally 必须执行）。"""
    def check(self, symbol, klines):
        return SimpleNamespace(repairs=[], ok=False, skip_reason='insufficient_klines', klines=klines)


def test_score_single_stock_releases_session(released):
    from application.services.opportunity_scoring_service import OpportunityScoringService
    svc = OpportunityScoringService(kline_repo=None, stock_repo=None, factor_adapter=None,
                                    quality_gate=_Gate())
    out = svc._score_single_stock('600519', [], None, {})
    assert out == {'_skipped': 'insufficient_klines'}
    assert released, "评分 worker 必须自行归还会话（池化线程长期存活）"


def test_data_update_job_releases_outer_thread_session(released, monkeypatch):
    from application.jobs.data_jobs import DataUpdateJob
    import adapters.outbound.repositories as repos

    class _Stocks:
        def get_all(self, limit=500):
            return []
    monkeypatch.setattr(repos, "StockORMRepository", lambda *a, **k: _Stocks())
    job = DataUpdateJob()
    res = asyncio.run(job.execute({}))
    assert res.success is True
    assert released, "asyncio.to_thread 线程读完后必须归还会话"


class _SvcDown:
    def get_financial_data(self, symbol, statement_type="income", periods=4):
        raise Exception('All providers failed')


class _Repo:
    def upsert_income_statements(self, records):
        return len(records)

    def upsert_balance_sheets(self, records):
        return 0


def test_financial_job_releases_session_even_on_probe_failure(released, monkeypatch):
    """探活失败会早退——此时宇宙读取的事务也必须已归还，否则又是一次泄漏。"""
    from infrastructure.jobs import financial_statement_update_job as job
    import application.services.financial_data_service_adapter as ad
    import adapters.outbound.repositories.financial_repository as fr

    monkeypatch.setattr(ad, "FinancialDataServiceAdapter", lambda *a, **k: _SvcDown())
    monkeypatch.setattr(fr, "FinancialORMRepository", lambda *a, **k: _Repo())
    res = job.execute(symbols=["003021", "600519"], periods=1)
    assert res["success"] is False and res.get("probe_failed") is True
    assert released, "早退分支同样要归还会话"
