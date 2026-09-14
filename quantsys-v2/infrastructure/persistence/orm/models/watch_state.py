"""Watch 状态类两张表（quant.watch_digest_state / quant.watch_interventions）。

建立背景（2026-09-14，w-8b43d3b8，REQ-24e15d B4-c5）：
    这两张表此前**没有 ORM 模型**，读写全部落在
    adapters/outbound/repositories/watch_state_repository.py 的裸 SQL
    （6 处 text()，含一处 ON CONFLICT upsert 与一处 CASE 条件递增）。
    收口后表结构由模型唯一确定，写路径不再靠手写列名字符串。

语义要点：
    · watch_digest_state 是**单行配置表**（恒为 id=1）：记录摘要门的"上次唤醒时间
      /唤醒所属日期/当日唤醒次数"。存进程内存会在重启后清零，使每日预算形同虚设
      （2026-09-11 实测），故必须落库。写路径是 upsert：ON CONFLICT (id) DO UPDATE，
      且 wake_count 按 **wake_date 是否跨日**决定"自增 1"还是"重置为 1"。
      ⚠️ 跨日比较用的是**冲突行自己的 wake_date 旧值**（不是新写入的值）——
      PostgreSQL 的 ON CONFLICT SET 中所有表达式都按旧行求值。
    · watch_interventions 是**追加写**的介入台账：agent 每被唤醒介入一次留一行
      （规则/标的/意图/类型/结果/消耗 token/成本/审计 id）。不更新旧行。
    · created_at 由**数据库默认值 now()** 填充（原 INSERT 未列该列）——模型用
      server_default 而不是 Python 侧 default，以免把"DB 时钟"悄悄换成"应用时钟"。
    · 两表的 id 都由数据库/序列负责：watch_digest_state.id 是**外部约定值 1**（非自增），
      watch_interventions.id 是 identity 序列。
"""
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, func, text

from ..base import Base

__all__ = ['WatchDigestState', 'WatchIntervention']


class WatchDigestState(Base):
    """盯盘摘要门状态（单行配置表，恒 id=1）

    对应数据库表：quant.watch_digest_state
    主键：id（语义上恒为 1，非自增）
    """
    __tablename__ = 'watch_digest_state'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, comment='固定为 1（单行配置表）')
    last_wake_at = Column(DateTime(timezone=False), nullable=True, comment='上次唤醒 agent 的时间')
    wake_date = Column(Date, nullable=True, comment='上次唤醒所属日期（跨日则当日计数重置）')
    wake_count = Column(Integer, nullable=True, server_default=text('0'), comment='当日唤醒次数')
    last_digest_at = Column(DateTime(timezone=False), nullable=True, comment='上次摘要生成时间')
    note = Column(Text, nullable=True, comment='备注')
    updated_at = Column(DateTime(timezone=False), nullable=True, server_default=func.now(), comment='更新时间')

    def __repr__(self):
        return (f"<WatchDigestState(id={self.id}, wake_date={self.wake_date}, "
                f"wake_count={self.wake_count})>")


class WatchIntervention(Base):
    """介入记账（agent 被唤醒介入的留痕，追加写）

    对应数据库表：quant.watch_interventions
    主键：id（自增）
    """
    __tablename__ = 'watch_interventions'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, nullable=True, comment='来源盯盘规则 id（可能为空=市场级介入）')
    symbol = Column(String, nullable=True, comment='标的代码')
    intent = Column(String, nullable=True, comment='介入意图（如 exit_stop）')
    trigger_kind = Column(String, nullable=True, comment='触发类型（price/market/...）')
    outcome = Column(String, nullable=True, comment='结果（escalated/handled/reviewed/ignored）')
    trigger_ids = Column(Text, nullable=True, comment='关联触发 id 列表（逗号分隔的文本）')
    tokens = Column(Integer, nullable=True, comment='本次介入消耗的 token 数')
    cost_yuan = Column(Float, nullable=True, server_default=text('0'), comment='本次介入的成本（元）')
    decision_audit_id = Column(String, nullable=True, comment='关联的决策审计 id')
    created_at = Column(DateTime(timezone=False), nullable=True, server_default=func.now(), comment='落账时间（DB 时钟）')

    def __repr__(self):
        return (f"<WatchIntervention(id={self.id}, rule_id={self.rule_id}, "
                f"symbol='{self.symbol}', outcome='{self.outcome}')>")
