"""
模型类定时任务

包含：model_train（每日模型重训，M8 利润引擎环节）。
"""
import asyncio
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)

# 模型新鲜度阈值（REQ-a458a6 t3，2026-09-14 w-4db568de）
# 训练门控阈值是 6 天；这里用 10 天作**兜底**阈值——超过它就不是"还没到点"，
# 而是重训链路某一环没生效（job 没跑 / 门控误判 / 训练失败被吞）。
MODEL_FRESHNESS_MAX_AGE_DAYS = 10
MODEL_MIN_TEST_ACCURACY = 0.55


def _send_feishu(text: str) -> bool:
    """飞书告警（失败只记日志，不阻断任务流）。经 NotificationFacade 投递。"""
    try:
        from application.notification import get_notification_facade

        title, _, body = text.partition('\n')
        title = title.strip() or '模型新鲜度告警'
        return bool(get_notification_facade().send_card(
            title=title, content=(body.strip() or title), urgency='high'))
    except Exception as e:  # pragma: no cover - 告警失败不影响任务判定
        logger.error("model freshness alert send failed: %s", e)
        return False


def _model_freshness_alerts() -> Dict[str, Any]:
    """最新 lightgbm 模型的新鲜度/质量巡检（只读，异常不抛出）

    返回 {'alerts': [...], 'fatal': bool}；fatal=True 表示"链路没生效"，
    调用方应把 Job 判为失败（否则会以 status=success 掩盖问题）。
    """
    try:
        from adapters.shared.ml_helpers import _get_model_repo, _resolve_latest_version
        from application.services.scheduler_tasks import _model_age_days

        if not _resolve_latest_version('lightgbm'):
            return {'alerts': ['无可用 lightgbm 模型'], 'fatal': True}
        rec = _get_model_repo().get_by_type_version('lightgbm', 'latest')
    except Exception as e:
        logger.warning("model freshness query failed: %s", e)
        return {'alerts': [f'模型元数据读取失败：{e}'], 'fatal': False}

    if not rec:
        return {'alerts': ['quant.ml_models 无 lightgbm 记录（训练从未落库？）'], 'fatal': True}

    alerts: list = []
    fatal = False
    age = _model_age_days(rec.get('train_date'))
    if age is None:
        alerts.append(f"最新模型 {rec.get('version')} 缺 train_date，无法判定新鲜度")
    elif age > MODEL_FRESHNESS_MAX_AGE_DAYS:
        alerts.append(f"最新模型 {rec.get('version')} 已 {age:.1f} 天未更新"
                      f"（阈值 {MODEL_FRESHNESS_MAX_AGE_DAYS} 天）→ 重训链路未生效")
        fatal = True

    acc = rec.get('test_accuracy')
    if acc is not None and acc < MODEL_MIN_TEST_ACCURACY:
        alerts.append(f"最新模型 {rec.get('version')} test_accuracy={acc:.4f}"
                      f" < {MODEL_MIN_TEST_ACCURACY}")

    return {'alerts': alerts, 'fatal': fatal}


class ModelTrainDailyJob(Job):
    """每日模型重训任务

    2026-09-05 注册（w-8366e526，修复 M8 审计空洞：模型自 2026-08-20 停训 16 天）：
    此前不存在任何 model_train 的 JobRegistry 实现——真实训练器
    application.services.scheduler_tasks.handle_model_train_auto（lightgbm 全流程：
    样本 K线加载 → 特征工程 → 训练 → 保存 → 元数据落库 → 性能对比自动切换）从未被调度
    挂载；legacy 通道指向不存在的 infrastructure/scripts/train_ml.py（跳过），
    scheduler_tasks.handle_model_train 是"框架就绪"假实现（默认 xgboost）。
    本 Job 委托唯一真实实现，非 force 时受 _check_train_needed 门控（模型新鲜则跳过）。

    2026-09-14（REQ-a458a6 t2/t3，w-4db568de）：
      · 训练入口收敛到本 Job —— 系统 crontab 的两条训练条目（周一 03:00 与每月 1 号
        03:00）已撤除：它们不进 scheduler_runs、无告警、日志只落 /tmp（会被系统清理），
        实测因此有过 16 天停训无人发现。
      · 每次运行后复核模型新鲜度：skipped 与 success 都可能掩盖链路失效，模型超过
        10 天未更新即判 Job 失败并告警（见 _model_freshness_alerts）。
      · 跳过不再单发飞书（门控未到期时每周期有 6/7 天是 skipped，逐条推送等于噪声）。
    """

    @property
    def name(self) -> str:
        return "model_train"

    @property
    def description(self) -> str:
        return "每日模型重训（lightgbm 全流程，门控 + 自动切换 + 新鲜度复核）"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 500 只 × 350 日全流程，预留 1 小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from application.services.scheduler_tasks import handle_model_train_auto
            result = await asyncio.to_thread(handle_model_train_auto, params or {})
            status = result.get('status')

            # 训练后复核：训练成功则新模型即新鲜；跳过/失败时这条能抓到"链路未生效"
            fresh = _model_freshness_alerts()
            if fresh['alerts']:
                _send_feishu("🚨 模型新鲜度告警\n" + "\n".join(f"- {a}" for a in fresh['alerts'])
                             + "\n请检查每日模型重训（task 320）与训练日志")
                logger.warning("model freshness alerts: %s", fresh['alerts'])

            if status == 'failed':
                return JobResult.fail(
                    self.name,
                    result.get('error') or result.get('reason') or 'unknown error',
                )

            details = dict(result)
            details['freshness_alerts'] = fresh['alerts']
            if fresh['fatal']:
                return JobResult.fail(self.name, '；'.join(fresh['alerts']))

            # success 与 skipped（门控未到期）都算正常完成，skipped 在 details 中体现原因
            return JobResult.ok(
                self.name,
                message=f"模型训练任务完成: status={status}, "
                        f"model_type={result.get('model_type', '-')}",
                details=details,
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有模型类任务
MODEL_JOBS = [
    ModelTrainDailyJob(),
]
