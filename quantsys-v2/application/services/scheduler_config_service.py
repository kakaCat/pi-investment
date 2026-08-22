"""
APScheduler任务配置管理服务 - ORM版本

提供Web API来动态管理定时任务配置，所有配置存储在数据库中
完全使用ORM，不再直接执行SQL
"""
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from domain.ports import ISchedulerConfigRepository

logger = structlog.get_logger(__name__)


class SchedulerConfigService:
    """调度器配置管理服务（ORM版本）

    功能：
    1. 从数据库读取任务配置
    2. 动态添加/删除/修改任务
    3. 启用/禁用任务
    4. 任务执行历史查询

    迁移状态：✅ 已完成ORM迁移
    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(self, repo: Optional[ISchedulerConfigRepository] = None):
        """初始化服务

        Args:
            repo: 调度器配置仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.repo = repo or ISchedulerConfigRepository()
        logger.info("SchedulerConfigService initialized with ORM")

    def list_configs(
        self,
        enabled_only: bool = False,
        command: str = None
    ) -> List[Dict[str, Any]]:
        """列出所有任务配置

        Args:
            enabled_only: 是否只返回启用的任务
            command: 按命令过滤

        Returns:
            任务配置列表
        """
        try:
            if enabled_only:
                tasks = self.repo.get_enabled_tasks(command=command)
            else:
                tasks = self.repo.get_all()
                if command:
                    tasks = [t for t in tasks if t.command == command]

            return [task.to_dict() for task in tasks]
        except Exception as e:
            logger.error(f"Error listing configs: {e}")
            return []

    def get_config(self, task_name: str) -> Optional[Dict[str, Any]]:
        """获取单个任务配置

        Args:
            task_name: 任务名称

        Returns:
            任务配置字典，不存在返回None
        """
        try:
            task = self.repo.get_task_by_name(task_name)
            return task.to_dict() if task else None
        except Exception as e:
            logger.error(f"Error getting config {task_name}: {e}")
            return None

    def create_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """创建任务配置

        Args:
            config: 配置字典

        Returns:
            创建结果
        """
        try:
            # 检查是否已存在
            existing = self.repo.get_task_by_name(config['task_name'])
            if existing:
                return {
                    'success': False,
                    'message': f"Task {config['task_name']} already exists"
                }

            task = self.repo.create_task_config(config)
            if task:
                return {
                    'success': True,
                    'message': 'Task created successfully',
                    'config_id': task.config_id
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to create task'
                }
        except Exception as e:
            logger.error(f"Error creating config: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def update_config(
        self,
        task_name: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新任务配置

        Args:
            task_name: 任务名称
            updates: 要更新的字段

        Returns:
            更新结果
        """
        try:
            # 添加更新时间
            updates['updated_at'] = datetime.now()

            success = self.repo.update_task_config(task_name, updates)
            if success:
                return {
                    'success': True,
                    'message': 'Task updated successfully'
                }
            else:
                return {
                    'success': False,
                    'message': f'Task {task_name} not found'
                }
        except Exception as e:
            logger.error(f"Error updating config {task_name}: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def delete_config(self, task_name: str) -> Dict[str, Any]:
        """删除任务配置

        Args:
            task_name: 任务名称

        Returns:
            删除结果
        """
        try:
            success = self.repo.delete_task_config(task_name)
            if success:
                return {
                    'success': True,
                    'message': 'Task deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'message': f'Task {task_name} not found'
                }
        except Exception as e:
            logger.error(f"Error deleting config {task_name}: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def enable_config(self, task_name: str) -> Dict[str, Any]:
        """启用任务

        Args:
            task_name: 任务名称

        Returns:
            操作结果
        """
        try:
            success = self.repo.enable_task(task_name)
            if success:
                logger.info(f"Task {task_name} enabled")
                return {
                    'success': True,
                    'message': f'Task {task_name} enabled'
                }
            else:
                return {
                    'success': False,
                    'message': f'Task {task_name} not found'
                }
        except Exception as e:
            logger.error(f"Error enabling task {task_name}: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def disable_config(self, task_name: str) -> Dict[str, Any]:
        """禁用任务

        Args:
            task_name: 任务名称

        Returns:
            操作结果
        """
        try:
            success = self.repo.disable_task(task_name)
            if success:
                logger.info(f"Task {task_name} disabled")
                return {
                    'success': True,
                    'message': f'Task {task_name} disabled'
                }
            else:
                return {
                    'success': False,
                    'message': f'Task {task_name} not found'
                }
        except Exception as e:
            logger.error(f"Error disabling task {task_name}: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def get_enabled_tasks(self) -> List[Dict[str, Any]]:
        """获取所有启用的任务

        Returns:
            启用的任务列表
        """
        return self.list_configs(enabled_only=True)

    def get_tasks_by_command(self, command: str) -> List[Dict[str, Any]]:
        """根据命令获取任务

        Args:
            command: 命令名称

        Returns:
            任务列表
        """
        try:
            tasks = self.repo.get_tasks_by_command(command)
            return [task.to_dict() for task in tasks]
        except Exception as e:
            logger.error(f"Error getting tasks by command {command}: {e}")
            return []
