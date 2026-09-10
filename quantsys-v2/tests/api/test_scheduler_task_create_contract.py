"""调度任务创建链路契约测试（三层：路由 → 域服务 → 仓储端口/实现）。

实证缺陷（2026-09-11，w-8f2c4cc5）：
    POST /api/scheduler/tasks → 500
    "SchedulerService.add_task() got an unexpected keyword argument 'task_type'"
根因：路由 create_scheduler_task 按 schedule_kind 推导 task_type 并作关键字参数传入，
而域服务 infrastructure/scheduler/scheduler.py 的 add_task 未声明该参数（仓储实现
与端口此前也不一致）→ 所有任务创建 100% 失败，delay/once 类任务永远无法创建。

本测试用 AST 静态比对"路由实际传的关键字参数"与"域服务签名"，防止同类契约漂移。
新增：tests/api/test_scheduler_task_create_contract.py
"""
import ast
import inspect
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parents[2]
ROUTE_FILE = V2_ROOT / "adapters" / "inbound" / "fastapi_app" / "routes" / "scheduler_async.py"


def _call_kwargs(path: Path, method_name: str):
    """返回文件中对 <任意对象>.method_name(...) 的调用所使用的关键字参数名列表。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            attr = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if attr == method_name:
                found.append(sorted(kw.arg for kw in node.keywords if kw.arg))
    return found


def test_route_add_task_kwargs_accepted_by_service():
    from infrastructure.scheduler.scheduler import SchedulerService

    accepted = set(inspect.signature(SchedulerService.add_task).parameters)
    calls = [kw for kw in _call_kwargs(ROUTE_FILE, "add_task") if kw]
    assert calls, "未在路由中找到 add_task 调用，测试失去意义"

    for kwargs in calls:
        unknown = [k for k in kwargs if k not in accepted]
        assert not unknown, (
            f"路由传给 SchedulerService.add_task 的关键字参数 {unknown} 不在服务签名 "
            f"{sorted(accepted)} 中 → 运行期 TypeError(500)"
        )


def test_service_signature_accepts_task_type():
    from infrastructure.scheduler.scheduler import SchedulerService

    params = inspect.signature(SchedulerService.add_task).parameters
    assert "task_type" in params, "add_task 必须接受 task_type（路由按 schedule_kind 推导后传入）"
    assert params["task_type"].default == "cron"


def test_service_forwards_task_type_to_repository():
    from infrastructure.scheduler.scheduler import SchedulerService

    recorded = {}

    class _Repo:
        def add_task(self, name, cron_expression, command,
                     params=None, description=None, task_type="cron"):
            recorded.update({"name": name, "command": command, "task_type": task_type})
            return 4242

    svc = SchedulerService(repo=_Repo())
    task_id = svc.add_task(
        name="probe-interval", cron_expression="0 3 1 1 *",
        command="data_update", task_type="interval")

    assert task_id == 4242
    assert recorded["task_type"] == "interval", "task_type 必须透传到仓储，否则类型被静默降级为 cron"


def test_port_signature_is_subset_of_adapter_signature():
    """端口声明必须能被实现层满足（实现层可有额外可选参数，但端口参数不能被实现层拒绝）。"""
    from domain.ports import ISchedulerRepository
    from adapters.outbound.repositories.scheduler_repository import SchedulerRepository

    port_params = inspect.signature(ISchedulerRepository.add_task).parameters
    impl_params = inspect.signature(SchedulerRepository.add_task).parameters
    missing = [p for p in port_params if p not in impl_params]
    assert not missing, f"实现层 SchedulerRepository.add_task 缺少端口参数 {missing}"


def test_port_declares_task_type():
    from domain.ports import ISchedulerRepository

    params = inspect.signature(ISchedulerRepository.add_task).parameters
    assert "task_type" in params, "端口未声明 task_type → 实现层的 task_type 支持无法被类型契约看见"
