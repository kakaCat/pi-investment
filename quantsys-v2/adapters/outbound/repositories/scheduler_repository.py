"""
调度任务Repository - 管理任务配置和执行记录
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from infrastructure.persistence.orm.config import get_session
from infrastructure.persistence.orm.models.scheduler import (
    SchedulerTaskConfig,
    SchedulerRun
)

logger = logging.getLogger(__name__)


class SchedulerRepository:
    """调度任务Repository"""
    
    def __init__(self):
        self.session = get_session()

    def _safe_rollback(self):
        """安全回滚当前线程共享事务（scoped_session 线程内共享，
        PG 报错后不回滚会毒化同线程后续所有查询）。
        try/except 包住防二次异常遮蔽原始错误。"""
        try:
            self.session.rollback()
        except Exception as rb_err:
            logger.warning(f"rollback failed: {rb_err}")

    def create_task_config(
        self,
        task_name: str,
        description: str,
        cron_expression: str,
        command: str,
        params: dict = None,
        is_enabled: bool = True,
        executor: str = 'default',
        max_instances: int = 1,
        misfire_grace_time: int = 300
    ) -> SchedulerTaskConfig:
        """创建任务配置"""
        try:
            config = SchedulerTaskConfig(
                task_name=task_name,
                description=description,
                cron_expression=cron_expression,
                command=command,
                params=params or {},
                is_enabled=is_enabled,
                executor=executor,
                max_instances=max_instances,
                misfire_grace_time=misfire_grace_time,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.session.add(config)
            self.session.commit()
            logger.info(f"Task config created: {task_name}")
            return config
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to create task config: {e}")
            raise
    
    def update_task_config(
        self,
        task_name: str,
        **updates
    ) -> Optional[SchedulerTaskConfig]:
        """更新任务配置"""
        try:
            config = self.session.query(SchedulerTaskConfig).filter_by(
                task_name=task_name
            ).first()
            
            if not config:
                return None
            
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            config.updated_at = datetime.now()
            self.session.commit()
            logger.info(f"Task config updated: {task_name}")
            return config
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to update task config: {e}")
            raise
    
    def get_task_config(self, task_name: str) -> Optional[SchedulerTaskConfig]:
        """获取任务配置"""
        try:
            return self.session.query(SchedulerTaskConfig).filter_by(
                task_name=task_name
            ).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Failed to get task config: {e}")
            return None
    
    def list_task_configs(
        self,
        enabled_only: bool = False
    ) -> List[SchedulerTaskConfig]:
        """列出所有任务配置"""
        try:
            query = self.session.query(SchedulerTaskConfig)
            if enabled_only:
                query = query.filter_by(is_enabled=True)
            return query.order_by(SchedulerTaskConfig.task_name).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Failed to list task configs: {e}")
            return []
    
    def delete_task_config(self, task_name: str) -> bool:
        """删除任务配置"""
        try:
            config = self.session.query(SchedulerTaskConfig).filter_by(
                task_name=task_name
            ).first()
            
            if config:
                self.session.delete(config)
                self.session.commit()
                logger.info(f"Task config deleted: {task_name}")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to delete task config: {e}")
            raise
    
    def log_execution(
        self,
        job_id: str,
        status: str,
        scheduled_time: datetime = None,
        start_time: datetime = None,
        end_time: datetime = None,
        result: any = None,
        error: str = None
    ) -> SchedulerRun:
        """记录任务执行"""
        try:
            duration_ms = None
            if start_time and end_time:
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            run = SchedulerRun(
                task_id=job_id,
                status=status,
                started_at=start_time or datetime.now(),
                completed_at=end_time or datetime.now(),
                duration_ms=duration_ms,
                result=result,
                error=error
            )
            self.session.add(run)
            self.session.commit()
            return run
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to log execution: {e}")
            raise
    
    def get_execution_history(
        self,
        job_id: str = None,
        limit: int = 100
    ) -> List[SchedulerRun]:
        """获取执行历史"""
        try:
            query = self.session.query(SchedulerRun)
            if job_id:
                query = query.filter_by(task_id=job_id)
            return query.order_by(SchedulerRun.started_at.desc()).limit(limit).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Failed to get execution history: {e}")
            return []
