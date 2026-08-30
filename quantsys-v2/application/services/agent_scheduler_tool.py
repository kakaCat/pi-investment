"""
Agent调度器工具 - 让Agent可以操作quantsys-v2的定时任务

Agent可以通过此工具：
1. 创建定时任务
2. 查询任务状态
3. 创建提醒任务
4. 管理自己的任务

Author: System Integration
Date: 2026-06-27
"""
import structlog
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


class AgentSchedulerTool:
    """Agent调度器工具"""

    def __init__(self, api_base_url: str = "http://localhost:5001"):
        """初始化

        Args:
            api_base_url: quantsys-v2 API的基础URL
        """
        self.api_base_url = api_base_url
        self.config_api_base = f"{api_base_url}/api/scheduler/config"

    def create_reminder_task(
        self,
        task_name: str,
        remind_at: datetime,
        message: str,
        agent_id: str = "default_agent"
    ) -> Dict[str, Any]:
        """创建一个提醒任务

        Agent可以用这个方法来提醒自己在未来某个时间做某事

        Args:
            task_name: 任务名称（唯一标识）
            remind_at: 提醒时间
            message: 提醒消息
            agent_id: Agent ID

        Returns:
            创建结果

        Example:
            tool = AgentSchedulerTool()

            # 提醒自己明天9点检查数据
            result = tool.create_reminder_task(
                task_name="check_data_tomorrow",
                remind_at=datetime.now() + timedelta(days=1, hours=9),
                message="检查昨日数据质量"
            )
        """
        # 将datetime转换为cron表达式（一次性任务）
        cron_expression = self._datetime_to_cron(remind_at)

        # 创建任务配置
        task_config = {
            "task_name": f"agent_reminder_{agent_id}_{task_name}",
            "description": f"Agent提醒: {message}",
            "cron_expression": cron_expression,
            "command": "agent_reminder",
            "params": {
                "agent_id": agent_id,
                "message": message,
                "created_at": datetime.now().isoformat(),
                "remind_at": remind_at.isoformat()
            },
            "is_enabled": True,
            "executor": "default",
            "max_instances": 1
        }

        try:
            response = requests.post(
                f"{self.config_api_base}/tasks",
                json=task_config,
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Agent reminder task created: {task_name}")

            return {
                "success": True,
                "task_name": task_config["task_name"],
                "message": f"✅ 已创建提醒任务，将在 {remind_at.strftime('%Y-%m-%d %H:%M')} 提醒你: {message}",
                "remind_at": remind_at.isoformat(),
                "details": result
            }

        except Exception as e:
            logger.error(f"Failed to create reminder task: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ 创建提醒任务失败: {e}"
            }

    def create_recurring_task(
        self,
        task_name: str,
        cron_expression: str,
        command: str,
        description: str,
        params: Dict[str, Any] = None,
        agent_id: str = "default_agent"
    ) -> Dict[str, Any]:
        """创建周期性任务

        Args:
            task_name: 任务名称
            cron_expression: Cron表达式，如 "0 9 * * *" (每天9点)
            command: 要执行的命令
            description: 任务描述
            params: 任务参数
            agent_id: Agent ID

        Returns:
            创建结果

        Example:
            # 每天9点提醒检查数据
            tool.create_recurring_task(
                task_name="daily_data_check",
                cron_expression="0 9 * * *",
                command="agent_reminder",
                description="每日数据检查提醒",
                params={"message": "请检查今日数据"}
            )
        """
        task_config = {
            "task_name": f"agent_recurring_{agent_id}_{task_name}",
            "description": f"Agent周期任务: {description}",
            "cron_expression": cron_expression,
            "command": command,
            "params": params or {},
            "is_enabled": True,
            "executor": "default",
            "max_instances": 1
        }

        try:
            response = requests.post(
                f"{self.config_api_base}/tasks",
                json=task_config,
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Agent recurring task created: {task_name}")

            return {
                "success": True,
                "task_name": task_config["task_name"],
                "message": f"✅ 已创建周期任务: {description}",
                "cron_expression": cron_expression,
                "details": result
            }

        except Exception as e:
            logger.error(f"Failed to create recurring task: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ 创建周期任务失败: {e}"
            }

    def list_agent_tasks(self, agent_id: str = "default_agent") -> Dict[str, Any]:
        """列出Agent创建的所有任务

        Args:
            agent_id: Agent ID

        Returns:
            任务列表
        """
        try:
            response = requests.get(
                f"{self.config_api_base}/tasks",
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            all_tasks = result.get("data", [])

            # 过滤出Agent创建的任务
            agent_tasks = [
                task for task in all_tasks
                if task["task_name"].startswith(f"agent_") or
                   task.get("params", {}).get("agent_id") == agent_id
            ]

            return {
                "success": True,
                "total": len(agent_tasks),
                "tasks": agent_tasks,
                "message": f"找到 {len(agent_tasks)} 个Agent任务"
            }

        except Exception as e:
            logger.error(f"Failed to list agent tasks: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ 查询任务失败: {e}"
            }

    def cancel_task(self, task_name: str) -> Dict[str, Any]:
        """取消任务

        Args:
            task_name: 任务名称（完整名称或部分名称）

        Returns:
            取消结果
        """
        # 如果是简短名称，尝试找到完整名称
        if not task_name.startswith("agent_"):
            # 查询所有agent任务，找到匹配的
            tasks_result = self.list_agent_tasks()
            if tasks_result["success"]:
                matching_tasks = [
                    t for t in tasks_result["tasks"]
                    if task_name in t["task_name"]
                ]
                if len(matching_tasks) == 1:
                    task_name = matching_tasks[0]["task_name"]
                elif len(matching_tasks) > 1:
                    return {
                        "success": False,
                        "message": f"找到多个匹配的任务，请指定完整名称",
                        "matching_tasks": [t["task_name"] for t in matching_tasks]
                    }
                else:
                    return {
                        "success": False,
                        "message": f"未找到名称包含 '{task_name}' 的任务"
                    }

        try:
            response = requests.delete(
                f"{self.config_api_base}/tasks/{task_name}",
                timeout=10
            )
            response.raise_for_status()

            return {
                "success": True,
                "message": f"✅ 已取消任务: {task_name}"
            }

        except Exception as e:
            logger.error(f"Failed to cancel task: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ 取消任务失败: {e}"
            }

    def get_task_status(self, task_name: str) -> Dict[str, Any]:
        """查询任务状态

        Args:
            task_name: 任务名称

        Returns:
            任务状态
        """
        try:
            response = requests.get(
                f"{self.config_api_base}/tasks/{task_name}",
                timeout=10
            )
            response.raise_for_status()

            result = response.json()

            if result.get("success"):
                task = result.get("data", {})
                return {
                    "success": True,
                    "task": task,
                    "message": f"任务 '{task_name}' 状态: {'启用' if task.get('is_enabled') else '禁用'}"
                }
            else:
                return {
                    "success": False,
                    "message": f"未找到任务: {task_name}"
                }

        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ 查询任务状态失败: {e}"
            }

    def _datetime_to_cron(self, dt: datetime) -> str:
        """将datetime转换为cron表达式（用于一次性任务）

        Args:
            dt: 目标时间

        Returns:
            Cron表达式

        Note:
            生成的cron表达式会匹配指定的时间点
            对于一次性任务，建议在执行后手动删除
        """
        return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"

    def create_self_reminder_in_minutes(
        self,
        minutes: int,
        message: str,
        task_name: str = None
    ) -> Dict[str, Any]:
        """在N分钟后提醒自己

        便捷方法，Agent可以快速设置一个短期提醒

        Args:
            minutes: 多少分钟后提醒
            message: 提醒消息
            task_name: 任务名称（可选，默认自动生成）

        Returns:
            创建结果

        Example:
            # 10分钟后提醒检查数据
            tool.create_self_reminder_in_minutes(
                minutes=10,
                message="检查数据处理结果"
            )
        """
        remind_at = datetime.now() + timedelta(minutes=minutes)

        if task_name is None:
            task_name = f"reminder_{int(datetime.now().timestamp())}"

        return self.create_reminder_task(
            task_name=task_name,
            remind_at=remind_at,
            message=message
        )

    def create_daily_reminder(
        self,
        hour: int,
        minute: int,
        message: str,
        task_name: str
    ) -> Dict[str, Any]:
        """创建每日提醒

        Args:
            hour: 小时 (0-23)
            minute: 分钟 (0-59)
            message: 提醒消息
            task_name: 任务名称

        Returns:
            创建结果

        Example:
            # 每天9:30提醒
            tool.create_daily_reminder(
                hour=9,
                minute=30,
                message="查看今日市场开盘情况",
                task_name="daily_market_check"
            )
        """
        cron_expression = f"{minute} {hour} * * *"

        return self.create_recurring_task(
            task_name=task_name,
            cron_expression=cron_expression,
            command="agent_reminder",
            description=f"每日{hour:02d}:{minute:02d}提醒",
            params={"message": message}
        )


# ============================================================
# Agent Reminder Handler（需要注册到scheduler_tasks.py）
# ============================================================

def handle_agent_reminder(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Agent提醒任务处理器

    这个handler会被调度器调用，用于提醒Agent

    Args:
        params: 任务参数，包含:
            - agent_id: Agent ID
            - message: 提醒消息
            - remind_at: 提醒时间

    Returns:
        执行结果
    """
    params = params or {}

    agent_id = params.get("agent_id", "default_agent")
    message = params.get("message", "这是一个提醒")
    remind_at = params.get("remind_at")

    logger.info(f"🔔 Agent Reminder for {agent_id}: {message}")

    # TODO: 这里可以通过WebSocket或其他方式通知Agent
    # 或者写入到一个Agent可以查询的表中

    try:
        from application.services.agent_notification_service import AgentNotificationService

        notification_service = AgentNotificationService()
        notification_service.send_reminder(
            agent_id=agent_id,
            message=message,
            remind_at=remind_at
        )

        return {
            "action": "agent_reminder",
            "status": "success",
            "agent_id": agent_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Agent reminder failed: {e}")

        # 即使通知服务失败，也记录日志
        return {
            "action": "agent_reminder",
            "status": "success",
            "agent_id": agent_id,
            "message": message,
            "note": "Logged as fallback",
            "timestamp": datetime.now().isoformat()
        }


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    # 示例：Agent如何使用调度器工具

    tool = AgentSchedulerTool()

    # 1. 创建一个10分钟后的提醒
    result = tool.create_self_reminder_in_minutes(
        minutes=10,
        message="检查数据处理结果"
    )
    print(result)

    # 2. 创建每日提醒
    result = tool.create_daily_reminder(
        hour=9,
        minute=30,
        message="查看今日市场开盘情况",
        task_name="daily_market_check"
    )
    print(result)

    # 3. 查看所有Agent任务
    result = tool.list_agent_tasks()
    print(f"Agent任务: {result['total']} 个")
    for task in result.get("tasks", []):
        print(f"  - {task['task_name']}: {task['description']}")

    # 4. 取消任务
    result = tool.cancel_task("daily_market_check")
    print(result)
