"""失败判定与飞书告警（拆分自 daily_jobs_bootstrap.py）

2026-10-01（REQ-261001145152-3982 t-686185）：由 daily_jobs_bootstrap.py 机械拆分而来
（原文件 1147 行）。函数体与签名**逐字未改**；原模块保留为转发壳，既有导入路径不受影响。

2026-10-05（REQ-261004154902-a7cd t-322d78 / FR-8、FR-9）三处增补（见各函数内注释）：
  ① `_job_failure_watch` 的扫描集合从「只有 JOBS 9 个 DailyJobs」扩到也含
     `quant.scheduler_tasks` 的启用任务（只读 SELECT）；
  ② `_send_feishu` 的返回值被**消费**（False/异常 → logger.error + 进程内留痕，
     由 ① 作为「告警投递失败」条目交回调用方）；
  ③ `_summarize_result` 补进 `auto_disabled` / `missed` / `stale` / 未覆盖 这类键，
     让「没做成的动作」进消息正文。
"""
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

# 失败判定口径唯一来源（含嵌套下钻）：与 APScheduler 路径共用，避免两套标准
from infrastructure.scheduler.job_executor import find_result_failure
from adapters.inbound.fastapi_app.daily_jobs.defs import logger  # noqa: F401

# ---------------- 告警投递失败留痕（t-322d78 ②，FR-9） ----------------
# 取证：`_send_feishu` 返回 bool，但调用方（runtime.py 3 处 / health.py 1 处 /
# pipeline.py 2 处）**全不看返回值** → 发送失败与成功在任务流里无法区分。
# 调用方不在本卡可改文件内，故在本模块内"消费"：
#   False/异常 → logger.error（带 title/reason）+ 记进进程内有界清单；
#   同一模块的 `_job_failure_watch` 把清单作为 `alert_delivery` 条目交回调用方
#   （pipeline 会把它拼进下一条告警正文 → 人就能看见"连告警都没发出去"）。
# ⚠️ 硬约束「只允许 SELECT」：此处**不写库**。设计文档 §9 提的
# `inprocess_job_runs.result` 落点需要改调用方文件（runtime.py），见交付报告偏离项。
ALERT_DELIVERY_JOB_ID = 'alert_delivery'
_ALERT_SEND_FAILURES: List[Dict[str, Any]] = []
_ALERT_SEND_FAILURES_MAX = 50
_alert_send_fail_lock = threading.Lock()


def _record_alert_send_failure(title: str, reason: str) -> None:
    """记一条「告警没发出去」（进程内、有界、不落库）。"""
    entry = {
        'job_id': ALERT_DELIVERY_JOB_ID,
        'run_date': datetime.now().strftime('%Y-%m-%d'),
        'error': f'{str(title)[:80]}: {str(reason)[:150]}',
        'source': 'alerting._send_feishu',
    }
    with _alert_send_fail_lock:
        _ALERT_SEND_FAILURES.append(entry)
        if len(_ALERT_SEND_FAILURES) > _ALERT_SEND_FAILURES_MAX:
            del _ALERT_SEND_FAILURES[:-_ALERT_SEND_FAILURES_MAX]


def drain_alert_send_failures() -> List[Dict[str, Any]]:
    """取走并清空「告警投递失败」清单。

    消费式（取走即清空）：同一失败只报一次，避免"发不出告警"这件事把告警刷爆。
    """
    with _alert_send_fail_lock:
        out = list(_ALERT_SEND_FAILURES)
        _ALERT_SEND_FAILURES.clear()
    return out


def _send_feishu(text: str, webhook_url: Optional[str] = None) -> bool:
    """飞书告警（失败只记日志，不阻断任务流）

    2026-09-11（w-23c70356）：改为经 NotificationFacade 投递，并与其余系统通知统一为
    卡片样式（首行作标题、其余作正文）。此前直接调旧版 FeishuNotificationService
    .send_text 走裸 webhook：既绕过 DDD 通知域（违反 CLAUDE.md 通知架构铁律），
    也拿不到「Agent OS 优先、飞书降级」策略路由，所以在同一飞书群里与本 Agent 的
    卡片消息观感不一致。urgency：🚨/❌ 开头按 high，其余 normal。

    2026-10-05（t-322d78）：**返回值被消费**——通道返回 False 与异常一样
    `logger.error` + 记进 `_ALERT_SEND_FAILURES`（此前 False 一路静默 return）。

    2026-10-07：支持任务级自定义 webhook_url（用于任务结果分类投递）。
    传入 webhook_url 时直接用它（绕过 NotificationFacade），否则走默认通道。

    Args:
        text: 通知文本（首行作标题）
        webhook_url: 可选的自定义飞书 webhook URL（完整 URL）
    """
    title = (text or '').partition('\n')[0].strip() or '每日任务通知'
    urgency = 'high' if title.startswith(('🚨', '❌')) else 'normal'
    
    try:
        # 自定义 webhook：直接发送卡片消息
        if webhook_url:
            import requests
            _, _, body = (text or '').partition('\n')
            card_payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title
                        },
                        "template": "red" if urgency == 'high' else "blue"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "plain_text",
                                "content": body.strip() or title
                            }
                        }
                    ]
                }
            }
            response = requests.post(webhook_url, json=card_payload, timeout=10)
            delivered = response.status_code == 200
            if not delivered:
                logger.error("custom webhook send failed",
                             reason=f"HTTP {response.status_code}", title=title, webhook=webhook_url)
                _record_alert_send_failure(title, f'自定义webhook返回{response.status_code}')
            return delivered
        
        # 默认通道：走 NotificationFacade
        from application.notification import get_notification_facade

        _, _, body = (text or '').partition('\n')
        delivered = bool(get_notification_facade().send_card(
            title=title,
            content=(body.strip() or title),
            urgency=urgency
        ))
        if not delivered:
            logger.error("freshness/job alert feishu send failed",
                         reason="通道返回 False（未送达）", title=title)
            _record_alert_send_failure(title, '通道返回 False（未送达）')
        return delivered
    except Exception as e:
        logger.error("freshness/job alert feishu send failed", error=str(e), title=title)
        _record_alert_send_failure(title, str(e))
        return False


# ---------------- scheduler_tasks 参与失败巡检（t-322d78 ①，FR-8） ----------------

def _enabled_scheduler_tasks() -> List[Dict[str, Any]]:
    """`quant.scheduler_tasks` 里启用任务的只读行。

    取证：`_job_failure_watch` 原先只扫 JOBS（9 个 DailyJobs），**完全不含**
    `quant.scheduler_tasks` 里那 11 张卡 → task 251 连续 21 次失败没有任何人被告知。
    读失败返回 []（+ error 日志）：巡检少覆盖一段，不许多打挂整条告警链。
    """
    try:
        from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
        return list(SchedulerRepository().list_tasks(enabled_only=True) or [])
    except Exception as e:  # noqa: BLE001
        logger.error("读取 scheduler_tasks 启用任务失败（本次巡检不含库表任务）", error=str(e))
        return []


def _scheduler_run_failures(tasks: List[Dict[str, Any]], days: int = 3) -> List[Dict[str, Any]]:
    """近 N 天内仍 failed 的**库表调度任务** run（只读 SELECT）。

    库表任务的失败落在 `quant.scheduler_runs`（不是 `inprocess_job_runs`），故必须单独查。
    返回体沿用既有契约键（`job_id` = 任务名 / `run_date` / `error`），另加 `source`
    便于区分来源；既有消费方（pipeline 只读这三个键）不受影响。
    """
    by_id = {int(t['id']): str(t.get('name')) for t in tasks
             if isinstance(t, dict) and t.get('id') is not None and t.get('name')}
    if not by_id:
        return []
    try:
        from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        rows = SchedulerRepository().list_runs(statuses=['failed'], limit=200) or []
        out: List[Dict[str, Any]] = []
        for row in rows:
            task_id = row.get('task_id')
            name = by_id.get(int(task_id)) if task_id is not None else None
            if not name:
                continue                      # 非启用任务的历史失败残留不告警
            started = str(row.get('started_at') or '')
            if started[:10] < since:
                continue
            out.append({'job_id': name, 'run_date': started[:10],
                        'error': str(row.get('error') or '')[:200],
                        'source': 'scheduler_runs'})
        return out
    except Exception as e:  # noqa: BLE001
        logger.error("读取 scheduler_runs 失败记录出错", error=str(e))
        return []


def _job_failure_watch(engine) -> List[Dict[str, Any]]:
    """任务失败巡检：过去 3 个自然日（不含今天——今天失败仍在 2h 自动重试冷却期）仍 failed 的活跃任务

    补 K线/因子巡检的盲区：数据恰好未滞后但 job 本身失败（如 chip_distribution 失败但
    K线新鲜、financial_statements 周六失败周一才发现）。扫描集合 = JOBS 内活跃任务
    **+ `quant.scheduler_tasks` 的启用任务**（t-322d78，此前后者整段是盲区），
    已退役 job（如 morning_topup）的历史 failed 残留不告警。
    """
    # 惰性导入：registry 依赖各作业模块，模块级导入会成环
    from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
    # 取数收口到仓储（2026-09-14，w-32314d00，REQ-24e15d B4-c4）：
    # engine 参数保留（签名被 _job_freshness_guard 与既有测试按位置传参）。
    from adapters.outbound.repositories.job_run_repository import JobRunRepository

    scheduler_tasks = _enabled_scheduler_tasks()
    scheduler_names = [str(t.get('name')) for t in scheduler_tasks
                       if isinstance(t, dict) and t.get('name')]
    candidates = [j.job_id for j in JOBS] + scheduler_names

    failures: List[Dict[str, Any]] = list(
        JobRunRepository().list_recent_failures(candidates, days=3) or []
    )
    failures += _scheduler_run_failures(scheduler_tasks, days=3)
    # 「告警自己没发出去」也是失败事实：交回调用方（消费式，同一条只报一次）
    failures += drain_alert_send_failures()
    return failures


def _format_elapsed(seconds: Any) -> str:
    """耗时人读格式化（REQ-261005210015-1603 t-cda13d，FR-1）

    取证：2026-10-05 的 evolution_fitness 实跑 1.21 秒，而 `f"{elapsed/60:.1f} 分钟"`
    把它印成「0.0 分钟」——3 秒以内的任何任务都是 0.0，收消息的人分不清"真快"还是"没干活"。

    规则：60 秒以内用秒（1 位小数），否则用分钟（1 位小数）；负数（时钟回拨）按 0。
    **不做**"耗时过短即告警"——快是正常的（见 design/architecture.md R3）。
    """
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        s = 0.0
    if s < 0:
        s = 0.0
    if s < 60:
        return f"{s:.1f} 秒"
    return f"{s / 60:.1f} 分钟"


def _summarize_result(result: Any, max_len: int = 300) -> str:
    """任务结果摘要（完成通知用）：提取关键计数，截断防爆消息

    2026-10-05（t-322d78 ③）：补进 `auto_disabled` / `missed` / `stale` / 未覆盖 这类键。
    取证：`evening_pipeline` 的 K 线同步「成功 0 只 / 未覆盖 5271 只」却记 success，
    而原键列表里没有 stale/未覆盖 → **「没做成的动作」根本不进消息正文**，
    收消息的人只看到"✅ 每日任务完成"。

    2026-10-05（REQ-261005210015-1603 t-cda13d，FR-2）：**handler 自述摘要优先**——
    `result['summary']` 是非空字符串时以其为首段，且**不再** dump 子字典段
    （避免同一批数字说两遍）；**没有 summary 的任务（其余全部任务）输出逐字不变**。
    白名单另补 fitness 的状态分布键（computed_ok / insufficient_sample / no_trades / data_gap），
    以及 `no_output` 的可读形式「无有效产出=True」（兜底可见）。
    """
    if not isinstance(result, dict):
        return ''
    keys = ['symbols_updated', 'updated', 'computed', 'failed_count',
            'symbols_checked', 'status', 'expected', 'kline_coverage', 'kline_stale',
            'kline_oldest_stale', 'factor_latest',
            # t-322d78：没做成的动作（停用/跳过/未覆盖/失败）必须进正文
            'auto_disabled', 'marked_inactive', 'missed', 'stale', 'uncovered',
            '未覆盖', 'skipped', 'failed',
            # t-cda13d FR-2：fitness 状态分布（handler 忘了写 summary 时的兜底）
            'computed_ok', 'insufficient_sample', 'no_trades', 'data_gap']
    parts = [f"{k}={result[k]}" for k in keys if k in result]
    handler_summary = result.get('summary')
    if isinstance(handler_summary, str) and handler_summary.strip():
        # handler 自述摘要优先：它已经把"有没有产出"说清楚了，不再重复标注、也不 dump 子字典
        return '; '.join([handler_summary.strip()] + parts)[:max_len]
    if result.get('no_output') is True:
        # 兜底：handler 忘了写 summary 时，至少让"零有效产出"这件事在正文里看得见
        parts.append('无有效产出=True')
    # evening_pipeline 等链式任务：深入一层提取子任务摘要
    for sub_key, sub_val in result.items():
        if isinstance(sub_val, dict):
            sub_parts = [f"{k}={sub_val[k]}" for k in
                         ('updated', 'computed', 'status', 'stale', 'uncovered', '未覆盖',
                          'auto_disabled', 'missed')
                         if k in sub_val]
            if sub_parts:
                parts.append(f"{sub_key}[{', '.join(map(str, sub_parts[:4]))}]")
    text = '; '.join(parts)
    return text[:max_len]


def format_completion(job_id: str, description: str, elapsed: Any, result: Any,
                      *, manual: bool = False, warn_no_output: bool = False) -> str:
    """组装「每日任务完成」消息文本（REQ-261006165125-23a9 · FR-2/FR-6/FR-7）

    为什么抽出来：消息文本原先内联在 `runtime._run_job` 里（三行 f-string），
    而本需求给它加了两个新分支（人工触发回执、回滚态 ⚠️ 语气），再内联就会
    与"发不发"的判据（`notify_policy`）缠在一起。这里只负责**怎么排版**，
    "发不发"由调用方按 `notify_policy.should_send_completion` 决定。

    标题优先级（从上到下，见设计 interfaces.md §3）：
      ① `manual=True`        → 「✅ 每日任务完成（人工触发）：{job_id}」
      ② `warn_no_output=True`→ 「⚠️ 每日任务完成（无有效产出）：{job_id}」（旧口径，仅回滚态可达）
      ③ 否则                 → 「✅ 每日任务完成：{job_id}」

    正文：描述 + 耗时（`_format_elapsed`，秒级任务不再印成「0.0 分钟」）+ 非空摘要。
    `warn_no_output` 不在这里判断，由调用方算——避免本模块反向依赖 `notify_policy`。
    """
    if manual:
        title = f'✅ 每日任务完成（人工触发）：{job_id}'
    elif warn_no_output:
        title = f'⚠️ 每日任务完成（无有效产出）：{job_id}'
    else:
        title = f'✅ 每日任务完成：{job_id}'
    text = f"{title}\n{description}\n耗时: {_format_elapsed(elapsed)}"
    summary = _summarize_result(result)
    if summary:
        text += f'\n{summary}'
    return text
