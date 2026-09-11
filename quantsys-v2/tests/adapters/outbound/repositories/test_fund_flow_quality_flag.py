"""资金流表 quality_flag 的 upsert 保护锁（2026-09-11，w-f436d4ea）

背景：quant.stock_fund_flow 存在系统性历史污染（14,314/81,335 行收盘价与权威 K 线
偏差 >0.5%，两次全市场事故：2026-09-10 与 2026-09-01）。根因已在 fund_flow_update_job
修掉，存量靠 quality_flag 标记（NULL=干净）。

**本测试锁的是一个极易被改回去的陷阱**：batch_upsert 的 ON CONFLICT DO UPDATE
原先枚举**全部**表列——一旦 quality_flag 进入更新集，任何一次对同一
(symbol, trade_date) 的重新写入都会把已标记的坏行擦成 NULL，
**等于把已知污染重新伪装成干净数据**（静默、无告警、事后不可察）。

不触网不写库：session 为桩，只编译语句。
"""
from datetime import date

import pytest
from sqlalchemy.dialects import postgresql

from adapters.outbound.repositories.fund_flow_repository import FundFlow, FundFlowORMRepository


class _StubSession:
    def __init__(self):
        self.stmt = None

    def execute(self, stmt):
        self.stmt = stmt

    def commit(self):
        pass

    def rollback(self):
        pass


class _Repo(FundFlowORMRepository):
    """session 在基类是无 setter 的 property —— 用子类覆写注入桩，避免触真库。"""

    def __init__(self, stub):
        self._stub = stub

    @property
    def session(self):
        return self._stub


def _repo_with_stub():
    sess = _StubSession()
    return _Repo(sess), sess


def _compiled(repo, sess):
    return str(sess.stmt.compile(dialect=postgresql.dialect(),
                                 compile_kwargs={'literal_binds': True}))


def test_模型确实带quality_flag列():
    assert 'quality_flag' in {c.name for c in FundFlow.__table__.columns}


def test_upsert的更新集不得包含quality_flag():
    repo, sess = _repo_with_stub()
    n = repo.batch_upsert([{
        'symbol': '600176', 'trade_date': date(2026, 9, 10),
        'close_price': 43.46, 'change_pct': 1.85, 'source': 'test',
    }])
    assert n == 1 and sess.stmt is not None

    sql = _compiled(repo, sess)
    assert 'ON CONFLICT' in sql.upper(), '应生成 upsert 语句'
    set_clause = sql.split('DO UPDATE SET', 1)[1] if 'DO UPDATE SET' in sql else ''
    assert set_clause, '应有 DO UPDATE SET 子句'
    assert 'quality_flag' not in set_clause, (
        'quality_flag 必须在 DO UPDATE SET 之外：否则重新写入同一 (symbol, trade_date) '
        '会把已标记的坏行擦成 NULL，把已知污染伪装成干净数据'
    )


def test_插入行不含quality_flag因而新数据为NULL():
    """写入路径不产出质量标记——这是设计：新数据靠 job 的两道闸门保证质量。"""
    repo, sess = _repo_with_stub()
    repo.batch_upsert([{'symbol': '600176', 'trade_date': date(2026, 9, 10), 'source': 'test'}])
    sql = _compiled(repo, sess)
    assert 'quality_flag' not in sql, 'insert 列表也不应写入该列（新行恒为 NULL）'
