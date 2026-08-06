"""
调度器配置ORM Repository
"""
from typing import List, Optional, Dict, Any
import structlog

from infrastructure.persistence.orm import BaseORMRepository
from infrastructure.persistence.orm.models import SchedulerTaskConfig

logger = structlog.get_logger(__name__)

__all__ = ['SchedulerConfigORMRepository']


class SchedulerConfigORMRepository(BaseORMRepository[SchedulerTaskConfig]):
    """调度器配置ORM Repository

    示例用法：
        repo = SchedulerConfigORMRepository()

        # 获取所有启用的任务
        enabled_tasks = repo.get_enabled_tasks()

        # 创建新任务配置
        task = repo.create_task_config({
            'task_name': 'daily_sync',
            'description': '每日数据同步',
            'cron_expression': '0 9 * * *',
            'command': 'sync_data',
            'params': {'source': 'tushare'}
        })
    """

    model = SchedulerTaskConfig

    def get_enabled_tasks(self, command: Optional[str] = None) -> List[SchedulerTaskConfig]:
        """获取所有启用的任务配置

        Args:
            command: 按命令过滤（可选）

        Returns:
            启用的任务配置列表
        """
        try:
            query = self.session.query(SchedulerTaskConfig).filter(
                SchedulerTaskConfig.is_enabled == True
            )

            if command:
                query = query.filter(SchedulerTaskConfig.command == command)

            return query.order_by(SchedulerTaskConfig.task_name).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting enabled tasks: {e}")
            return []

    def get_task_by_name(self, task_name: str) -> Optional[SchedulerTaskConfig]:
        """根据任务名称获取配置

        Args:
            task_name: 任务名称

        Returns:
            任务配置对象，不存在返回None
        """
        try:
            return self.session.query(SchedulerTaskConfig).filter(
                SchedulerTaskConfig.task_name == task_name
            ).first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting task by name {task_name}: {e}")
            return None

    def create_task_config(self, config_data: Dict[str, Any]) -> Optional[SchedulerTaskConfig]:
        """创建任务配置

        Args:
            config_data: 配置数据字典

        Returns:
            创建的任务配置对象
        """
        try:
            task = SchedulerTaskConfig(
                task_name=config_data['task_name'],
                description=config_data.get('description'),
                cron_expression=config_data['cron_expression'],
                command=config_data['command'],
                params=config_data.get('params', {}),
                is_enabled=config_data.get('is_enabled', True),
                executor=config_data.get('executor', 'default'),
                max_instances=config_data.get('max_instances', 1),
                misfire_grace_time=config_data.get('misfire_grace_time', 300),
                coalesce=config_data.get('coalesce', True),
                created_by=config_data.get('created_by'),
            )
            return self.create(task)
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error creating task config: {e}")
            return None

    def update_task_config(
        self,
        task_name: str,
        updates: Dict[str, Any]
    ) -> bool:
        """更新任务配置

        Args:
            task_name: 任务名称
            updates: 要更新的字段字典

        Returns:
            成功返回True
        """
        try:
            task = self.get_task_by_name(task_name)
            if not task:
                return False

            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)

            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating task config {task_name}: {e}")
            self.session.rollback()
            return False

    def delete_task_config(self, task_name: str) -> bool:
        """删除任务配置

        Args:
            task_name: 任务名称

        Returns:
            成功返回True
        """
        try:
            task = self.get_task_by_name(task_name)
            if not task:
                return False

            self.session.delete(task)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting task config {task_name}: {e}")
            self.session.rollback()
            return False

    def enable_task(self, task_name: str) -> bool:
        """启用任务

        Args:
            task_name: 任务名称

        Returns:
            成功返回True
        """
        return self.update_task_config(task_name, {'is_enabled': True})

    def disable_task(self, task_name: str) -> bool:
        """禁用任务

        Args:
            task_name: 任务名称

        Returns:
            成功返回True
        """
        return self.update_task_config(task_name, {'is_enabled': False})

    def get_tasks_by_command(self, command: str) -> List[SchedulerTaskConfig]:
        """根据命令获取所有任务配置

        Args:
            command: 命令名称

        Returns:
            任务配置列表
        """
        try:
            return self.session.query(SchedulerTaskConfig).filter(
                SchedulerTaskConfig.command == command
            ).order_by(SchedulerTaskConfig.task_name).all()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting tasks by command {command}: {e}")
            return []
