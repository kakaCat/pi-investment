"""Agent 任务派发（应用层）：统一任务信封 + 交付要求 + 派发。

为什么在通知应用层：派发的物理通道是 wake 通道（`NotificationFacade.wake_agent`），
信封与报告要求的唯一实现放在这里，任何调用方（watch 引擎、调度任务、运维 CLI）都
走同一份，避免"这次记得带报告、下次忘了"。

口径（2026-10-20 晚事故的结论）：
  · 需要报告的活 → 指令末尾自动附四段式飞书简报要求（范围结果/关键结论/待拍板/未完成）；
  · 静默任务（夜间哨兵/纯巡检）→ requires_report=False，不推"没事"卡；
  · 报告由收件人 agent 用 feishu_notify 发——本层只下要求，不代发；
  · wake 返回 'ok' 只代表通道收下，**不代表执行**（见 docs/guides/agent-task-dispatch.md）。
"""
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from .notification_factory import get_notification_facade

logger = structlog.get_logger(__name__)

#: 需要报告的活的统一交付要求。四段结构来自 2026-10-20 晚的教训：
#: 只说"发个简报"会得到一段散文，用户仍然要问"完了多少、还有什么要拍板"。
REPORT_BLOCK_TEMPLATE = """
【交付要求·必须执行】任务结束（完成或确定无法完成）后，用 feishu_notify 发一条简报：
  · channel=watch_symbol，urgency=__URGENCY__
  · 标题：「__TITLE__｜完成」
  · 正文四段（每段一行，空的一律写"无"，不要省略）：
      ① 范围与结果：处理了多少、还剩多少（数字）
      ② 关键结论：不超过 3 条
      ③ 需人工拍板：明确列出需要用户决定的事项
      ④ 未完成/失败：没干完的部分与原因
  · 只在会话里写结论不算交付——用户的唯一入口是飞书。
"""

SILENT_BLOCK = """
【交付要求】本任务为静默任务：无异常/需处置项时不要发消息；有异常时按既有告警口径处理。
"""


def build_instruction(title: str, instruction: str, requires_report: bool = True,
                      urgency: str = 'normal') -> str:
    """拼最终派单指令（纯函数：不触网、不读环境，便于 review 与单测）。"""
    body = (instruction or '').strip()
    text = f'【任务】{title}\n\n{body}\n'
    if requires_report:
        text += (REPORT_BLOCK_TEMPLATE
                 .replace('__TITLE__', title)
                 .replace('__URGENCY__', urgency))
    else:
        text += SILENT_BLOCK
    return text


def dispatch_agent_task(
    *,
    title: str,
    instruction: str,
    event: str = 'agent_task',
    target: str = 'agent-dh',
    requires_report: bool = True,
    urgency: str = 'normal',
    facade: Optional[Any] = None,
) -> Dict[str, Any]:
    """把任务派给处置 agent，返回派发结果。

    Args:
        title: 任务标题（也用于报告标题）
        instruction: 作业指导正文
        event: 事件名（进 wake 载荷，便于下游区分来源）
        target: 处置 agent 键（agent-dh / agent-ts），None 入口不传时用默认
        requires_report: 是否需要收件人发飞书简报
        urgency: 报告紧急度 normal|high|critical
        facade: 注入用（单测传 fake；生产缺省=全局单例）

    返回:
        {status, title, event, target, requires_report, prompt_sha256_16, prompt_length}
        status 口径同 NotificationFacade.wake_agent：'ok' 才算通道收下。
    """
    import hashlib

    prompt = build_instruction(title, instruction, requires_report, urgency)
    digest = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]

    if facade is None:
        facade = get_notification_facade()

    data = {
        'event': event,
        'task': title,
        'instruction': prompt,
        'requires_report': requires_report,
        'dispatched_at': datetime.now().isoformat(timespec='seconds'),
        'dispatched_by': 'qs_notification.application.agent_task_dispatch',
    }
    status = facade.wake_agent(event, data, target_agent=target)

    logger.info('agent task dispatched', task=title, notify_event=event,
                target=target, requires_report=requires_report,
                prompt_sha256_16=digest, status=status)
    return {
        'status': status,
        'title': title,
        'event': event,
        'target': target,
        'requires_report': requires_report,
        'prompt_sha256_16': digest,
        'prompt_length': len(prompt),
    }
