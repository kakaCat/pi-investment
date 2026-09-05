"""
模型类定时任务

包含：model_train（每日模型重训，M8 利润引擎环节）。
"""
import asyncio
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class ModelTrainDailyJob(Job):
    """每日模型重训任务

    2026-09-05 注册（w-8366e526，修复 M8 审计空洞：模型自 2026-08-20 停训 16 天）：
    此前不存在任何 model_train 的 JobRegistry 实现——真实训练器
    application.services.scheduler_tasks.handle_model_train_auto（lightgbm 全流程：
    样本 K线加载 → 特征工程 → 训练 → 保存 → 元数据落库 → 性能对比自动切换）从未被调度
    挂载；legacy 通道指向不存在的 infrastructure/scripts/train_ml.py（跳过），
    scheduler_tasks.handle_model_train 是"框架就绪"假实现（默认 xgboost）。
    本 Job 委托唯一真实实现，非 force 时受 _check_train_needed 性能门控（模型新鲜则跳过）。
    """

    @property
    def name(self) -> str:
        return "model_train"

    @property
    def description(self) -> str:
        return "每日模型重训（lightgbm 全流程，性能门控 + 自动切换）"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 500 只 × 350 日全流程，预留 1 小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from application.services.scheduler_tasks import handle_model_train_auto
            result = await asyncio.to_thread(handle_model_train_auto, params or {})
            status = result.get('status')
            if status == 'failed':
                return JobResult.fail(
                    self.name,
                    result.get('error') or result.get('reason') or 'unknown error',
                )
            # success 与 skipped（门控未到期）都算正常完成，skipped 在 details 中体现原因
            return JobResult.ok(
                self.name,
                message=f"模型训练任务完成: status={status}, "
                        f"model_type={result.get('model_type', '-')}",
                details=result,
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有模型类任务
MODEL_JOBS = [
    ModelTrainDailyJob(),
]
