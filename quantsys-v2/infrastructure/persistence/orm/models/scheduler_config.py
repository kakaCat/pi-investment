"""
调度器配置ORM模型
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, TIMESTAMP, JSON
from sqlalchemy.sql import func
from infrastructure.persistence.orm.base import Base


class SchedulerTaskConfig(Base):
    """调度器任务配置模型"""
    __tablename__ = 'scheduler_task_configs'
    __table_args__ = {'schema': 'quant'}

    config_id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    cron_expression = Column(String(100), nullable=False)
    command = Column(String(100), nullable=False)
    params = Column(JSON, default={})
    is_enabled = Column(Boolean, default=True)
    executor = Column(String(50), default='default')
    max_instances = Column(Integer, default=1)
    misfire_grace_time = Column(Integer, default=300)
    coalesce = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))
    updated_by = Column(String(100))

    def to_dict(self):
        """转换为字典"""
        return {
            'config_id': self.config_id,
            'task_name': self.task_name,
            'description': self.description,
            'cron_expression': self.cron_expression,
            'command': self.command,
            'params': self.params,
            'is_enabled': self.is_enabled,
            'executor': self.executor,
            'max_instances': self.max_instances,
            'misfire_grace_time': self.misfire_grace_time,
            'coalesce': self.coalesce,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
        }
