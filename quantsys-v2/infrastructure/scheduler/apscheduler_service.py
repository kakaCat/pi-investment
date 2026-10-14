"""
APScheduler 封装服务

将手写调度器迁移到 APScheduler 框架，提供：
- 秒级精确调度（vs 原 30s 轮询）
- 分布式锁支持（PostgreSQL advisory lock）
- 成熟的 misfire 处理
- 延迟任务支持（DateTrigger）
- 间隔任务支持（IntervalTrigger）
- 社区维护，降低维护成本

Created: 2026-09-01
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

from infrastructure.scheduler.cron_compat import build_cron_trigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from domain.ports import ISchedulerRepository

logger = logging.getLogger(__name__)


def resolve_misfire_grace(seconds) -> "int | None":
    """把库里的 ``misfire_grace_time_seconds`` 翻成 APScheduler 的语义。

    REQ-261004154902-a7cd t5（FR-4 / FR-8）。

    - ``NULL``（None）→ 返回 ``None`` = **不判 misfire**（唤醒必补跑）。
      这是本仓 CLAUDE.md 早已写明的口径（「NULL=唤醒必补跑，显式值=超宽限跳过记 skipped」），
      但旧代码写成 ``task.get(...) or 300`` 把它抹成了 5 分钟 →
      2026-10-02 实证：进程 09:00 才起，当天 06:30 的 v13 排班**直接丢失且无人知**。
    - 显式正数 → 原样透传（超过该秒数即跳过，并被 ``_on_job_missed`` 记成 missed）。
    - 0 / 负数 / 脏数据 → 视同 NULL（宁可补跑，也不要「永远静默跳过」）。

    纯函数，便于单测锁住语义。
    """
    if seconds is None:
        return None
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        logger.warning("misfire_grace_time_seconds 取值非法（%r）→ 按 NULL 处理", seconds)
        return None
    return value if value > 0 else None


def parse_task_id_from_job_id(job_id) -> "int | None":
    """``task_249`` → ``249``；不认识则返回 None（纯函数，便于单测）。"""
    if not isinstance(job_id, str) or not job_id.startswith("task_"):
        return None
    suffix = job_id[len("task_"):]
    return int(suffix) if suffix.isdigit() else None


class APSchedulerService:
    """APScheduler 封装服务"""

    def __init__(self, db_url: str, repo: ISchedulerRepository):
        """
        初始化 APScheduler

        Args:
            db_url: 数据库连接 URL (用于 jobstore)
            repo: 调度器仓储（用于读取 scheduler_tasks）
        """
        self.repo = repo

        # 配置 jobstore（使用 PostgreSQL 存储调度状态）
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=db_url,
                tablename='apscheduler_jobs'
            )
        }

        # 配置执行器（线程池）
        executors = {
            'default': ThreadPoolExecutor(max_workers=10)
        }

        # 配置任务默认参数
        job_defaults = {
            'coalesce': False,        # 不合并多次 misfire（每次都执行）
            'max_instances': 1,       # 每个任务最多 1 个实例（防止并发）
            'misfire_grace_time': 300 # 5 分钟宽限期（超过则跳过）
        }

        # 创建调度器（使用 BackgroundScheduler，在后台线程运行）
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )

        # 「被跳过」必须留痕（REQ-261004154902-a7cd t5 / FR-8）：
        # APScheduler 对超宽限的 trigger 只打一行纯文本 warning 就跳过，库里查不到、
        # last_status 还停在前几天的 success（实证 2026-10-03/10-04 数据质量检查）。
        # 监听 MISSED 事件把它写成一条 scheduler_runs（status='missed'）。
        try:
            from apscheduler.events import EVENT_JOB_MISSED

            self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)
        except Exception as exc:  # noqa: BLE001 - 监听注册失败不许拦住调度器启动
            logger.error("注册 MISSED 事件监听失败（该跳过将只能靠日志发现）: %s", exc)

        logger.info("APSchedulerService initialized")

    def _on_job_missed(self, event) -> None:
        """APScheduler 跳过某次排班时调用：响亮日志 + 落一条 status='missed' 的 run。

        REQ-261004154902-a7cd t5（FR-8）。记账失败只记日志，绝不影响调度线程。
        """
        job_id = getattr(event, "job_id", None)
        scheduled = getattr(event, "scheduled_run_time", None)
        logger.error(
            "scheduler job missed: job_id=%s scheduled_run_time=%s —— 该次排班已被跳过（不补跑）",
            job_id, scheduled,
        )
        task_id = parse_task_id_from_job_id(job_id)
        if task_id is None:
            logger.error("missed 事件的 job_id 无法解析出 task_id: %r", job_id)
            return
        recorder = getattr(self.repo, "record_missed_run", None)
        if not callable(recorder):
            logger.error(
                "仓储未实现 record_missed_run（task_id=%s）→ 该跳过在库里不可见", task_id
            )
            return
        try:
            run_id = recorder(
                task_id,
                scheduled_run_time=scheduled,
                note=f"missed by {scheduled}（超出 misfire 宽限，APScheduler 已跳过）",
            )
            logger.error("已把该跳过记为 run_id=%s（status=missed, task_id=%s）", run_id, task_id)
        except Exception as exc:  # noqa: BLE001 - 记账失败不得击穿调度
            logger.error("记录 missed run 失败 task_id=%s: %s", task_id, exc)

    def load_tasks_from_db(self):
        """
        从 scheduler_tasks 表加载任务到 APScheduler

        跳过 cron_expression='managed_by_agent_os' 的任务（由 Agent OS 管理）
        支持任务类型：
        - cron: 定时任务（CronTrigger）
        - delay: 延迟任务（DateTrigger，一次性）
        - interval: 间隔任务（IntervalTrigger）
        - once: 一次性任务（DateTrigger）
        """
        tasks = self.repo.list_tasks(enabled_only=True)

        # 防御（2026-09-13 w-c8cae280 实证）：repo 层对读库异常是"静默 return []"。
        # 若照此继续，下游 reconcile 会把 jobstore 全量摘除——曾发生：reload 时读库瞬时失败
        # → remove_all_jobs + 0 条重载 → 27 个 job 全没，日志还打"✅ Tasks reloaded"，
        # 调度静默停摆直到下次进程重启。判据：DB 说有启用任务，却一条也没读出来。
        if not tasks:
            try:
                expected = self.repo.count_tasks(enabled_only=True)
            except Exception:
                expected = 0
            if expected > 0:
                logger.error(
                    f"❌ 任务列表加载为空但库中有 {expected} 个启用任务 → 判为读取异常："
                    f"本次不加载也不对账（jobstore 保持原样，避免误摘全部 job）"
                )
                return None

        loaded_count = 0
        skipped_count = 0
        desired_ids = set()  # 本次加载后"应当存在"的 job id 集合（供孤儿回收比对）

        for task in tasks:
            # 跳过由 Agent OS 管理的任务
            if task.get("cron_expression") == "managed_by_agent_os":
                logger.info(f"Skip Agent OS managed task: {task.get('name')}")
                skipped_count += 1
                continue

            try:
                # 根据 task_type 创建不同的 trigger
                task_type = task.get('task_type', 'cron')
                trigger = self._create_trigger(task_type, task)

                # 添加任务到 APScheduler
                # 注意：使用模块级函数避免序列化问题
                from infrastructure.scheduler.job_executor import execute_scheduled_job

                self.scheduler.add_job(
                    func=execute_scheduled_job,
                    trigger=trigger,
                    args=[task.get("id")],
                    id=f"task_{task.get("id")}",
                    name=task.get("name"),
                    replace_existing=True,
                    # REQ-261004154902-a7cd t5：NULL = 唤醒必补跑（不再被 `or 300` 抹成 5 分钟）；
                    # 显式值 = 超宽限跳过，并由 _on_job_missed 记为 missed。
                    misfire_grace_time=resolve_misfire_grace(
                        task.get("misfire_grace_time_seconds")
                    ),
                )

                desired_ids.add(f"task_{task.get('id')}")
                loaded_count += 1
                logger.info(
                    f"Loaded task: {task.get('name')} "
                    f"(id={task.get('id')}, type={task_type}, expr={task.get('cron_expression')})"
                )

            except Exception as e:
                logger.error(f"Failed to load task {task.get('name')}: {e}", exc_info=True)

        logger.info(
            f"Task loading complete: {loaded_count} loaded, "
            f"{skipped_count} skipped (Agent OS)"
        )

        # 孤儿回收：jobstore 是持久化的，add_job(replace_existing=True) 只增不删，
        # 任何"删除任务/停用任务/转为 Agent OS 托管"都不会摘掉已注册的 job。
        # 注意：调度器未启动时 get_jobs() 只返回本次会话 pending 的 job，看不到 jobstore
        # 里的历史 job —— 因此 start() 必须在 scheduler.start() 之后再对账一次
        # （见 start() 内注释与 2026-09-12 实证：task_250 禁用后仍跑了 15 天）。
        self.reconcile_jobs(desired_ids)
        return desired_ids

    def reconcile_jobs(self, desired_ids) -> int:
        """摘掉 jobstore 里不再有对应任务的"孤儿 job"，返回摘除数量。

        背景（2026-09-11 w-f4aa1f6a 实证）：任务 251 `realtime-signal-monitor`
        （cron 1-6 点每 5 分钟）的 scheduler_tasks 行早已删除，但 APScheduler
        jobstore（public.apscheduler_jobs，持久化）里的 task_251 一直在跑到 09-10
        02:00，每 5 分钟空跑一次并记一条 ERROR（raw 日志 373 条），
        Agent OS 侧收成 error_event「Task 251 not found in scheduler_tasks」。
        全仓库此前没有任何 remove_job 调用 → 缺失的正是这个对账。

        只做删除、不做新增：安全性上不触碰任何仍在册的任务（不动 next_run_time），
        因此可独立于 load 流程调用与验证。
        """
        # 空集护栏：desired_ids 为空说明"应存在集合"没有依据，绝不能据此清空 jobstore。
        if not desired_ids:
            logger.error("孤儿 job 对账已跳过：desired_ids 为空（疑似任务列表加载失败）")
            return 0

        removed = 0
        try:
            jobs = self.scheduler.get_jobs()
        except Exception as e:
            logger.warning(f"孤儿 job 对账跳过（get_jobs 失败）: {e}")
            return 0
        for job in jobs:
            job_id = str(getattr(job, "id", ""))
            if not job_id.startswith("task_"):
                continue  # 非本服务注册的 job，不动
            if job_id in desired_ids:
                continue
            try:
                self.scheduler.remove_job(job_id)
                removed += 1
                logger.warning(
                    f"🧹 孤儿调度任务已摘除: id={job_id} name={getattr(job, 'name', '')} "
                    f"（scheduler_tasks 中已无对应的启用任务）"
                )
            except Exception as e:
                logger.error(f"孤儿 job 摘除失败: id={job_id} error={e}")
        if removed:
            logger.warning(f"孤儿调度任务对账完成：摘除 {removed} 个，保留 {len(desired_ids)} 个")
        else:
            logger.info(f"孤儿调度任务对账：无孤儿（在册 {len(desired_ids)} 个）")
        return removed

    def _create_trigger(self, task_type: str, task):
        """
        根据任务类型创建 APScheduler 触发器

        Args:
            task_type: 任务类型 (cron/delay/interval/once)
            task: 任务配置（字典或对象）

        Returns:
            APScheduler Trigger 对象

        Raises:
            ValueError: 不支持的任务类型或配置错误
        """
        # 统一获取属性的方式（支持字典和对象）
        def get_attr(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        cron_expr = get_attr(task, 'cron_expression')
        params = get_attr(task, 'params', {})
        task_name = get_attr(task, 'name', 'Unknown')

        if task_type == 'cron':
            # 标准 Cron 任务：DOW 必须按标准 cron（0=周日）翻译后再交给 APScheduler。
            # APScheduler 的 from_crontab 用 0=周一，直接透传会让 Mon-Fri 实跑成 Tue-Sat，
            # 实证与口径见 infrastructure/scheduler/cron_compat.py。
            return build_cron_trigger(cron_expr, tz='Asia/Shanghai')

        elif task_type == 'delay':
            # 延迟任务：N 秒后执行一次
            delay_seconds = params.get('delay_seconds')
            if delay_seconds is None:
                # 尝试从 cron_expression 解析（格式：DELAY:300）
                if cron_expr and cron_expr.startswith('DELAY:'):
                    delay_seconds = int(cron_expr.split(':')[1])
                else:
                    raise ValueError(f"Delay task missing delay_seconds: {task_name}")

            run_at = datetime.now() + timedelta(seconds=delay_seconds)
            logger.info(f"Delay task {task_name} will run at {run_at}")
            return DateTrigger(run_date=run_at, timezone='Asia/Shanghai')

        elif task_type == 'interval':
            # 间隔任务：每 N 秒执行一次
            interval_seconds = params.get('interval_seconds')
            if interval_seconds is None:
                # 尝试从 cron_expression 解析（格式：INTERVAL:60）
                if cron_expr and cron_expr.startswith('INTERVAL:'):
                    interval_seconds = int(cron_expr.split(':')[1])
                else:
                    raise ValueError(f"Interval task missing interval_seconds: {task_name}")

            return IntervalTrigger(
                seconds=interval_seconds,
                timezone='Asia/Shanghai'
            )

        elif task_type == 'once':
            # 一次性任务：指定时间执行一次
            run_at_str = params.get('run_at') or cron_expr
            try:
                # 尝试解析 ISO 格式时间
                run_at = datetime.fromisoformat(run_at_str)
                logger.info(f"Once task {task_name} will run at {run_at}")
                return DateTrigger(run_date=run_at, timezone='Asia/Shanghai')
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid run_at format for once task {task_name}: {e}")

        else:
            raise ValueError(f"Unsupported task_type: {task_type}")

    def start(self):
        """启动调度器"""
        if self.scheduler.running:
            logger.warning("APScheduler already running")
            return

        # 先加载任务，再启动
        desired_ids = self.load_tasks_from_db()
        self.scheduler.start()

        # 启动后再对账一次（关键）：未启动的 BackgroundScheduler 上 get_jobs() 只返回
        # 本次会话 add_job 的 pending job，看不到持久化 jobstore 里的历史 job →
        # 已禁用/已删除/已转 Agent OS 的任务会长期残留在 jobstore 里继续触发。
        # 实证（2026-09-12 w-c8cae280）：任务 250 pre-market-scan 早已 is_enabled=false，
        # 仍每天 01:25 触发（近 30 天 15 次），三次进程重启都没摘掉，只有显式
        # POST /api/scheduler/reload（此时 scheduler 已 running）才摘得掉。
        if desired_ids is not None:
            self.reconcile_jobs(desired_ids)

        # 进程重启会打断 run 的收尾记账 → 启动时回收遗留的 running run
        self._recover_orphan_runs()

        logger.info("✅ APScheduler started")

    def _recover_orphan_runs(self) -> None:
        """回收上一进程遗留的 running run（防止僵尸 run 永久停留 running）。

        2026-09-11 w-23c70356：实例 run 3527（每日数据质量检查，2026-09-10 22:00
        启动）在进程重启后卡 running 1.9 小时，看门狗持续报僵尸。
        """
        try:
            recovered = self.repo.recover_orphan_runs()
            if recovered:
                logger.warning(f"♻️ 已回收孤儿 run {len(recovered)} 条（进程重启遗留）: {recovered}")
            else:
                logger.info("无孤儿 run 需要回收")
        except Exception as e:
            logger.error(f"回收孤儿 run 失败（不影响调度器启动）: {e}")

    def shutdown(self, wait: bool = True):
        """
        关闭调度器

        Args:
            wait: 是否等待正在执行的任务完成
        """
        if not self.scheduler.running:
            logger.warning("APScheduler not running")
            return

        self.scheduler.shutdown(wait=wait)
        logger.info("✅ APScheduler shutdown")

    def reload_tasks(self):
        """
        重新加载任务（用于动态更新）

        使用场景：
        - 用户在 scheduler_tasks 表中添加/修改/删除任务后
        - 调用此方法同步到 APScheduler
        """
        if not self.scheduler.running:
            logger.error("Cannot reload tasks: scheduler not running")
            return

        # 不再 remove_all_jobs()（2026-09-13 实证）：先清空再重建，一旦重建阶段读库失败
        # （repo 静默 return []）就会清空调度且报成功。改为纯增量对账——加载用
        # add_job(replace_existing=True) 覆盖同名 job，摘除交给 reconcile_jobs，
        # 并在"读库为空但库中有任务"时中止，任何一步失败都不会毁掉现有 jobstore。
        desired_ids = self.load_tasks_from_db()
        if desired_ids is None:
            logger.error("❌ Tasks reload aborted：任务列表读取异常，jobstore 保持原样")
            return

        logger.info(f"✅ Tasks reloaded（在册 {len(desired_ids)} 个）")

    def get_job_status(self, task_id: int) -> dict:
        """
        获取任务在 APScheduler 中的状态

        Args:
            task_id: scheduler_tasks 表的任务 ID

        Returns:
            任务状态字典，包含 next_run_time 等信息
        """
        job = self.scheduler.get_job(f"task_{task_id}")

        if job is None:
            return {"exists": False}

        return {
            "exists": True,
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }

    def trigger_task_now(self, task_id: int):
        """
        手动触发任务立即执行

        REQ-261006093620-a315 t6（FR-6）改造：**不再 `modify_job(next_run_time=now)`**。

        为什么必须改：`modify_job` 让**同一个 job** 立即触发，执行路径与"自动到点"逐字相同——
        执行期拿不到任何"这是人按的"信息，交易日门一旦落在执行期就会把人工触发一起挡掉（违反 FR-6）。
        另外它还会提前 `next_run_time`，可能把当天的正常排班吞掉。

        现在改为投递**一次性 job** 并显式带 `manual=True`：
        - 执行体不判门（人明确要求跑）；
        - cron job 的排期**不被扰动**；
        - 一次性 job 执行完由 APScheduler 自动摘除（DateTrigger 耗尽），jobstore 不留垃圾。

        Args:
            task_id: scheduler_tasks 表的任务 ID

        Raises:
            ValueError: 该任务在 APScheduler 里没有注册 job（既有语义，路由层靠它降级到 legacy 路径）
        """
        import time as _time

        from infrastructure.scheduler.job_executor import execute_scheduled_job

        job = self.scheduler.get_job(f"task_{task_id}")
        if job is None:
            raise ValueError(f"Task {task_id} not found in APScheduler")

        self.scheduler.add_job(
            func=execute_scheduled_job,
            trigger=DateTrigger(run_date=datetime.now()),
            args=[task_id],
            kwargs={'manual': True},
            id=f'manual_{task_id}_{int(_time.time())}',
            name=f'[manual] {job.name}',
            replace_existing=False,
            misfire_grace_time=None,
        )

        logger.info(f"Task {task_id} triggered manually (one-off manual job, gate bypassed)")
