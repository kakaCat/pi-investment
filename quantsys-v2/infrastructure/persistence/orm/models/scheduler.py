"""
调度任务ORM模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, JSON
from sqlalchemy.dialects.postgresql import JSONB
from infrastructure.persistence.orm.base import Base


class SchedulerTaskConfig(Base):
    """调度任务配置表"""
    __tablename__ = 'scheduler_task_configs'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}
    
    config_id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(255), unique=True, nullable=False, comment='任务名称')
    description = Column(Text, comment='任务描述')
    cron_expression = Column(String(100), nullable=False, comment='Cron表达式')
    command = Column(String(500), nullable=False, comment='执行命令/函数路径')
    params = Column(JSONB, comment='任务参数')
    is_enabled = Column(Boolean, default=True, comment='是否启用')
    executor = Column(String(50), default='default', comment='执行器类型')
    max_instances = Column(Integer, default=1, comment='最大并发实例数')
    misfire_grace_time = Column(Integer, default=300, comment='错过执行的容忍时间(秒)')
    coalesce = Column(Boolean, default=True, comment='是否合并错过的任务')
    created_at = Column(DateTime, comment='创建时间')
    updated_at = Column(DateTime, comment='更新时间')
    created_by = Column(String(100), comment='创建人')
    updated_by = Column(String(100), comment='更新人')
    
    def __repr__(self):
        return f"<SchedulerTaskConfig(task_name='{self.task_name}', enabled={self.is_enabled})>"


class SchedulerRun(Base):
    """调度任务执行记录表"""
    __tablename__ = 'scheduler_runs'
    __table_args__ = {'schema': 'quant', 'extend_existing': True}
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(255), nullable=False, comment='任务ID', index=True)
    status = Column(String(50), nullable=False, comment='执行状态: success/error/timeout')
    started_at = Column(DateTime, nullable=False, comment='开始时间', index=True)
    completed_at = Column(DateTime, comment='完成时间')
    duration_ms = Column(Integer, comment='执行耗时(毫秒)')
    result = Column(JSONB, comment='执行结果')
    error = Column(Text, comment='错误信息')
    
    def __repr__(self):
        return f"<SchedulerRun(task_id='{self.task_id}', status='{self.status}')>"
