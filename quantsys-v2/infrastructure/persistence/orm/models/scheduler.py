"""
调度任务ORM模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from infrastructure.persistence.orm.base import Base


class SchedulerTaskConfig(Base):
    """调度任务配置表（映射 quant.scheduler_tasks）"""
    __tablename__ = 'scheduler_tasks'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True, comment='任务名称')
    description = Column(Text, comment='任务描述')
    cron_expression = Column(Text, nullable=False, comment='Cron表达式')
    command = Column(Text, nullable=False, comment='执行命令/函数路径')
    params = Column(JSONB, comment='任务参数', default={})
    is_enabled = Column(Boolean, default=True, comment='是否启用')
    task_type = Column(String(20), nullable=False, default='cron', comment='任务类型: cron/delay/interval/once')
    
    # 运行时状态
    last_run_at = Column(DateTime(timezone=True), comment='上次执行时间')
    last_status = Column(Text, comment='上次执行状态')
    last_error = Column(Text, comment='上次错误信息')
    next_run_at = Column(DateTime(timezone=True), comment='下次执行时间')
    
    # 补偿机制
    compensation_enabled = Column(Boolean, default=False, comment='是否启用补偿')
    compensation_check_after = Column(Time, comment='补偿检查时间')
    compensation_max_attempts = Column(Integer, default=1, comment='最大补偿尝试次数')
    misfire_grace_time_seconds = Column(Integer, comment='错过执行的容忍时间(秒)')
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f"<SchedulerTaskConfig(name='{self.name}', enabled={self.is_enabled})>"


class SchedulerRun(Base):
    """调度任务执行记录表（映射 quant.scheduler_runs）"""
    __tablename__ = 'scheduler_runs'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, nullable=False, comment='任务ID', index=True)
    status = Column(String(50), nullable=False, comment='执行状态: running/success/failed/skipped')
    started_at = Column(DateTime(timezone=True), nullable=False, comment='开始时间', index=True)
    completed_at = Column(DateTime(timezone=True), comment='完成时间')
    duration_ms = Column(Integer, comment='执行耗时(毫秒)')
    result = Column(JSONB, comment='执行结果')
    error = Column(Text, comment='错误信息')
    
    def __repr__(self):
        return f"<SchedulerRun(task_id='{self.task_id}', status='{self.status}')>"
