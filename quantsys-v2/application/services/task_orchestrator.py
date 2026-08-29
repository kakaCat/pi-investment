"""
任务编排器
管理任务依赖关系和执行顺序，支持并发执行
"""
import asyncio
import structlog
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = structlog.get_logger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务定义"""
    task_id: str
    task_func: callable
    params: Dict[str, Any]
    depends_on: List[str]
    priority: int = 5
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskOrchestrator:
    """任务编排器

    功能：
    1. 管理任务依赖关系
    2. 按拓扑顺序执行任务
    3. 支持并发执行（依赖满足后）
    4. 处理任务失败和跳过
    5. 生成执行计划
    """

    def __init__(self, max_concurrent: int = 3):
        self.tasks: Dict[str, Task] = {}
        self.max_concurrent = max_concurrent
        self.logger = structlog.get_logger(__name__)

    def add_task(
        self,
        task_id: str,
        task_func: callable,
        params: Dict = None,
        depends_on: List[str] = None,
        priority: int = 5
    ):
        """添加任务到编排器

        Args:
            task_id: 任务唯一标识
            task_func: 任务执行函数（可以是同步或异步）
            params: 任务参数
            depends_on: 依赖的任务ID列表
            priority: 优先级 1-10，数字越大优先级越高
        """
        task = Task(
            task_id=task_id,
            task_func=task_func,
            params=params or {},
            depends_on=depends_on or [],
            priority=priority
        )
        self.tasks[task_id] = task
        self.logger.info(f"Added task: {task_id}, depends_on={depends_on}, priority={priority}")

    def _validate_dependencies(self):
        """验证依赖关系（检测循环依赖）"""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks.get(task_id)
            if not task:
                return False

            for dep_id in task.depends_on:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if has_cycle(task_id):
                    raise ValueError(f"Circular dependency detected involving task: {task_id}")

    def _get_ready_tasks(self) -> List[Task]:
        """获取可以执行的任务（依赖已满足）

        Returns:
            按优先级排序的就绪任务列表
        """
        ready = []

        for task in self.tasks.values():
            # 只处理待执行的任务
            if task.status != TaskStatus.PENDING:
                continue

            # 检查依赖是否都完成
            deps_met = all(
                self.tasks.get(dep_id) and
                self.tasks[dep_id].status == TaskStatus.SUCCESS
                for dep_id in task.depends_on
            )

            if deps_met:
                ready.append(task)

        # 按优先级排序（高优先级在前）
        ready.sort(key=lambda t: t.priority, reverse=True)
        return ready

    async def _execute_task(self, task: Task):
        """执行单个任务

        Args:
            task: 任务对象
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.logger.info(f"Executing task: {task.task_id}")

        try:
            # 执行任务函数
            if asyncio.iscoroutinefunction(task.task_func):
                result = await task.task_func(**task.params)
            else:
                result = task.task_func(**task.params)

            task.result = result
            task.status = TaskStatus.SUCCESS
            task.completed_at = datetime.now()

            execution_time = (task.completed_at - task.started_at).total_seconds()
            self.logger.info(f"Task completed: {task.task_id} (time={execution_time:.2f}s)")

        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            self.logger.error(f"Task failed: {task.task_id} - {e}", exc_info=True)

    async def execute_all(self) -> Dict[str, Any]:
        """执行所有任务（支持并发）

        Returns:
            执行结果汇总
        """
        # 验证依赖关系
        self._validate_dependencies()

        running_tasks: Set[asyncio.Task] = set()
        task_to_asyncio_task: Dict[str, asyncio.Task] = {}

        while True:
            # 获取可执行的任务
            ready_tasks = self._get_ready_tasks()

            # 如果没有就绪任务且没有运行中任务，结束
            if not ready_tasks and not running_tasks:
                break

            # 启动新任务（不超过并发限制）
            while ready_tasks and len(running_tasks) < self.max_concurrent:
                task = ready_tasks.pop(0)
                asyncio_task = asyncio.create_task(self._execute_task(task))
                running_tasks.add(asyncio_task)
                task_to_asyncio_task[task.task_id] = asyncio_task

            # 等待至少一个任务完成
            if running_tasks:
                done, running_tasks = await asyncio.wait(
                    running_tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )

        # 汇总结果
        return self._generate_summary()

    def _generate_summary(self) -> Dict[str, Any]:
        """生成执行结果汇总"""
        summary = {
            'total': len(self.tasks),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'cancelled': 0,
            'tasks': {}
        }

        for task_id, task in self.tasks.items():
            summary['tasks'][task_id] = {
                'status': task.status.value,
                'result': task.result,
                'error': task.error,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'execution_time_ms': (
                    int((task.completed_at - task.started_at).total_seconds() * 1000)
                    if task.started_at and task.completed_at else None
                )
            }

            if task.status == TaskStatus.SUCCESS:
                summary['success'] += 1
            elif task.status == TaskStatus.FAILED:
                summary['failed'] += 1
            elif task.status == TaskStatus.SKIPPED:
                summary['skipped'] += 1
            elif task.status == TaskStatus.CANCELLED:
                summary['cancelled'] += 1

        return summary

    def get_execution_plan(self) -> List[List[str]]:
        """获取执行计划（按层级分组）

        Returns:
            层级列表，每层包含可以并发执行的任务ID
        """
        self._validate_dependencies()

        levels = []
        processed = set()

        while len(processed) < len(self.tasks):
            level = []

            for task_id, task in self.tasks.items():
                if task_id in processed:
                    continue

                # 依赖都已处理，加入当前层级
                if all(dep in processed for dep in task.depends_on):
                    level.append(task_id)

            if not level:
                # 检测到无法解决的依赖
                remaining = set(self.tasks.keys()) - processed
                raise ValueError(f"Unresolvable dependencies for tasks: {remaining}")

            levels.append(level)
            processed.update(level)

        return levels

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            'task_id': task_id,
            'status': task.status.value,
            'result': task.result,
            'error': task.error,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None
        }

    def visualize_plan(self) -> str:
        """可视化执行计划"""
        try:
            levels = self.get_execution_plan()
            output = ["Execution Plan:", "=" * 50]

            for i, level in enumerate(levels, 1):
                output.append(f"\nLevel {i} (can run concurrently):")
                for task_id in level:
                    task = self.tasks[task_id]
                    deps = ", ".join(task.depends_on) if task.depends_on else "None"
                    output.append(f"  - {task_id} (priority={task.priority}, depends_on=[{deps}])")

            return "\n".join(output)

        except ValueError as e:
            return f"Error: {e}"


# 示例使用
async def example_usage():
    """示例：如何使用 TaskOrchestrator"""
    orchestrator = TaskOrchestrator(max_concurrent=3)

    # 定义任务函数
    async def fetch_data(symbol: str):
        await asyncio.sleep(1)  # 模拟网络请求
        return f"data for {symbol}"

    def calculate_factor(data: str):
        return f"factor from {data}"

    async def generate_signal(factor: str):
        await asyncio.sleep(0.5)
        return f"signal from {factor}"

    # 添加任务（带依赖关系）
    orchestrator.add_task(
        "fetch_kline",
        fetch_data,
        {"symbol": "600000.SH"},
        depends_on=[],
        priority=10
    )

    orchestrator.add_task(
        "calculate_factor",
        calculate_factor,
        {"data": "kline_data"},
        depends_on=["fetch_kline"],
        priority=8
    )

    orchestrator.add_task(
        "generate_signal",
        generate_signal,
        {"factor": "factor_data"},
        depends_on=["calculate_factor"],
        priority=5
    )

    # 显示执行计划
    logger.info(orchestrator.visualize_plan())

    # 执行所有任务
    result = await orchestrator.execute_all()
    logger.info('\nExecution Result:')
    logger.info(result)


if __name__ == "__main__":
    asyncio.run(example_usage())
