"""
Automation Tasks ORM Repository

管理自动化任务的数据库操作
"""
from infrastructure.persistence.orm import BaseORMRepository
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from infrastructure.persistence.orm.base import Base
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class AutomationTask(Base):
    """自动化任务模型"""
    __tablename__ = 'automation_tasks'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    task_name = Column(String(100), nullable=False, unique=True)
    task_type = Column(String(20), nullable=False)
    schedule_config = Column(JSONB)
    condition_rules = Column(JSONB)
    agent_tool = Column(String(50))
    api_endpoint = Column(String(200))
    params = Column(JSONB, default={})
    priority = Column(Integer, default=5)
    is_enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
    created_by = Column(String(50))
    description = Column(Text)


class AutomationRun(Base):
    """任务执行历史模型"""
    __tablename__ = 'automation_runs'
    __table_args__ = {'schema': 'quant'}

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, nullable=False)
    run_id = Column(String(50), nullable=False, unique=True)
    trigger_type = Column(String(20), nullable=False)
    trigger_by = Column(String(50))
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    status = Column(String(20), nullable=False)
    result = Column(JSONB)
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    run_metadata = Column('run_metadata', JSONB, default={})


class AutomationTaskRepository(BaseORMRepository[AutomationTask]):
    """自动化任务 Repository"""
    model = AutomationTask

    def list_all(self, enabled_only: bool = False) -> List[AutomationTask]:
        """获取所有任务"""
        try:
            query = self.session.query(self.model)
            if enabled_only:
                query = query.filter(self.model.is_enabled == True)
            return query.order_by(self.model.priority.desc()).all()
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return []

    def get_by_name(self, task_name: str) -> Optional[AutomationTask]:
        """根据名称获取任务"""
        try:
            return self.session.query(self.model).filter(
                self.model.task_name == task_name
            ).first()
        except Exception as e:
            logger.error(f"Error getting task by name: {e}")
            return None

    def create_task(self, task_data: Dict[str, Any]) -> Optional[AutomationTask]:
        """创建任务"""
        try:
            task = self.model(**task_data)
            self.session.add(task)
            self.session.commit()
            return task
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating task: {e}")
            return None

    def update_task(self, task_name: str, updates: Dict[str, Any]) -> bool:
        """更新任务"""
        try:
            task = self.get_by_name(task_name)
            if not task:
                return False

            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)

            task.updated_at = datetime.now()
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating task: {e}")
            return False

    def delete_task(self, task_name: str) -> bool:
        """删除任务"""
        try:
            task = self.get_by_name(task_name)
            if not task:
                return False

            self.session.delete(task)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting task: {e}")
            return False

    def get_scheduled_tasks(self) -> List[AutomationTask]:
        """获取所有启用的定时任务"""
        try:
            return self.session.query(self.model).filter(
                self.model.is_enabled == True,
                self.model.task_type == 'scheduled'
            ).order_by(self.model.priority.desc()).all()
        except Exception as e:
            logger.error(f"Error getting scheduled tasks: {e}")
            return []


class AutomationRunRepository(BaseORMRepository[AutomationRun]):
    """任务执行历史 Repository"""
    model = AutomationRun

    def create_run(self, run_data: Dict[str, Any]) -> Optional[AutomationRun]:
        """创建执行记录"""
        try:
            run = self.model(**run_data)
            self.session.add(run)
            self.session.commit()
            return run
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating run: {e}")
            return None

    def update_run(self, run_id: str, updates: Dict[str, Any]) -> bool:
        """更新执行记录"""
        try:
            run = self.session.query(self.model).filter(
                self.model.run_id == run_id
            ).first()

            if not run:
                return False

            for key, value in updates.items():
                if hasattr(run, key):
                    setattr(run, key, value)

            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating run: {e}")
            return False

    def get_task_history(self, task_id: int, limit: int = 50) -> List[AutomationRun]:
        """获取任务执行历史"""
        try:
            return self.session.query(self.model).filter(
                self.model.task_id == task_id
            ).order_by(self.model.started_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting task history: {e}")
            return []


__all__ = ['AutomationTask', 'AutomationRun', 'AutomationTaskRepository', 'AutomationRunRepository']
