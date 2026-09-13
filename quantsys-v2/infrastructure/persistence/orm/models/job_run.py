"""进程内定时任务运行台账（quant.inprocess_job_runs）。

建立背景（2026-09-14，w-32314d00，REQ-24e15d t4/B2）：
    这张表此前**没有 ORM 模型**，读写全部散在
    `adapters/inbound/fastapi_app/daily_jobs_bootstrap.py`（建表 + INSERT + UPDATE + 多处 SELECT）
    与 `infrastructure/jobs/financial_timeliness_check_job.py`（当天是否已跑过的去重判断）里，
    以裸 SQL 形式存在。本模型把"任务台账"变成一等公民，SQL 收敛到仓储层。

语义要点：
    · 主键 (job_id, run_date)：同一个 job 每个自然日只应有一条记录
      （bootstrap 侧以 "job_id + run_date 唯一" 为前提做幂等）；
    · status 是**任务级**结论（success/error/...），但**不要只看它**——
      实测外层 success 而 result 里嵌套着失败（见 job_executor.classify_job_result 的下钻逻辑）；
    · run_date 是**自然日**，不是交易日（非交易日也可能跑）。
"""
from sqlalchemy import Column, Date, DateTime, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from ..base import Base

__all__ = ['InProcessJobRun']


class InProcessJobRun(Base):
    """进程内任务运行台账

    对应数据库表：quant.inprocess_job_runs
    主键：(job_id, run_date)
    """
    __tablename__ = 'inprocess_job_runs'
    # 2026-09-14（w-32314d00，B4-c4）：本模型现在是**建表的唯一真源** ——
    # handle: daily_jobs_bootstrap._ensure_table 原先内联一份手写 _DDL，
    # 与模型重复定义同一张表（改一处不改另一处就漂）。现已改为
    # InProcessJobRun.__table__.create(checkfirst=True)，_DDL 删除。
    # 因此这里声明的列/默认值必须与线上表逐列一致 —— 已用 information_schema 比对过。
    __table_args__ = {'schema': 'quant'}

    job_id = Column(Text, primary_key=True, comment='任务标识')
    run_date = Column(Date, primary_key=True, comment='运行日（自然日）')
    status = Column(Text, nullable=False, comment='任务级状态')
    # server_default 必须保留：原手写 DDL 是 timestamptz NOT NULL DEFAULT now()，
    # 不声明则 checkfirst 建出来的表会少这个默认值（新环境与老环境结构不一致）。
    started_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=text('now()'), comment='开始时间')
    finished_at = Column(DateTime(timezone=True), nullable=True, comment='结束时间')
    result = Column(JSONB, nullable=True, comment='handler 返回值')
    error = Column(Text, nullable=True, comment='错误摘要')

    def __repr__(self):
        return f"<InProcessJobRun(job_id='{self.job_id}', date='{self.run_date}', status='{self.status}')>"
