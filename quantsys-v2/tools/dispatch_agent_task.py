"""Agent 任务派单入口（2026-10-20）。

为什么要有它
------------
「派活 → 执行 → 报告」是一次完整交付。2026-10-20 晚的积压清理暴露了两个坑：

1. 派单指令**没写报告要求**，agent 干完只在会话里说结论、写看板卡，用户的唯一入口
   飞书什么都没收到——第三段（报告）靠人肉补；
2. 派单是 ad-hoc 的 python -c，没有留痕：谁派的、几时派的、有没有要求报告，事后
   只能翻会话。

本脚本把「派单」固化成一条命令：统一任务信封 + 统一交付要求（飞书简报）+ 审计留痕。
需要复盘时查 `logs/agent-dispatch.jsonl`。

用法
----
    # 先把作业指导写成文件（推荐；可 review 可 diff）
    PYTHONPATH=. ./venv/bin/python tools/dispatch_agent_task.py \
        --title "盯盘积压清理（10-20 晚）" \
        --instruction-file /tmp/sweep.md \
        --event watch_backlog_sweep

    # 静默任务（如夜间哨兵：无异常就不该打扰）：--no-report
    ... --no-report

    # 只看最终指令，不派单
    ... --dry-run

口径（重要，别读反）
--------------------
* **需要报告的活**：默认行为，指令末尾自动附「交付要求」——完成后用 feishu_notify
  发简报（标题/四段：范围结果、关键结论、待拍板、未完成）。
* **静默任务**：`--no-report`。夜间哨兵、纯巡检这类"无异常即沉默"的任务必须用它，
  否则每次巡检都推一张"没事"的卡，报告本身变成噪音。
* 报告是**收件人可执行的要求**，不是脚本自己发卡：agent 手里有 feishu_notify，
  由它按实际结论写；脚本只负责下要求 + 留痕。
* 派单成功 ≠ 执行成功：`status=ok` 只代表 wake 通道收下了（详见 2026-10-20 的 v4
  source 事故——投递成功、回合 0 步）。真正的验收看回执与结果，不看这行 ok。
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LOG = ROOT / 'logs' / 'agent-dispatch.jsonl'

#: 统一交付要求（需要报告的活才附加）。
#: 四段结构来自 2026-10-20 晚的教训：只说"发个简报"会得到一段散文，用户仍然要问
#: "完了多少、还有什么要拍板"——把四段钉死，报告才可读、可核对。
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


def build_instruction(title: str, instruction: str, requires_report: bool = True,
                      urgency: str = 'normal') -> str:
    """拼最终派单指令（纯函数，便于离线 review 与单测）。"""
    body = (instruction or '').strip()
    text = f'【任务】{title}\n\n{body}\n'
    if requires_report:
        text += (REPORT_BLOCK_TEMPLATE
                 .replace('__TITLE__', title)
                 .replace('__URGENCY__', urgency))
    else:
        text += '\n【交付要求】本任务为静默任务：无异常/需处置项时不要发消息；有异常时按既有告警口径处理。\n'
    return text


def _append_audit(log_path: Path, record: dict) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as exc:  # noqa: BLE001 - 留痕失败不能打挂派单
        print(f'[warn] 派单留痕写入失败（不影响已发出的派单）: {exc}', file=sys.stderr)


def dispatch(*, title: str, instruction: str, event: str = 'agent_task',
             target: str = 'agent-dh', requires_report: bool = True,
             urgency: str = 'normal', dry_run: bool = False,
             log_path: Path = DEFAULT_LOG) -> dict:
    """派单并留痕。返回 {status, prompt_length, ...}。"""
    prompt = build_instruction(title, instruction, requires_report, urgency)
    digest = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:16]
    record = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'title': title,
        'event': event,
        'target': target,
        'requires_report': requires_report,
        'prompt_sha256_16': digest,
        'prompt_length': len(prompt),
    }
    if dry_run:
        record['status'] = 'dry_run'
        print(prompt)
        print(f'\n[dry-run] 未派单。event={event} target={target} sha={digest}')
        return record

    from qs_notification.application import get_notification_facade

    data = {
        'event': event,
        'task': title,
        'instruction': prompt,
        'requires_report': requires_report,
        'dispatched_at': record['ts'],
        'dispatched_by': 'tools/dispatch_agent_task.py',
    }
    status = get_notification_facade().wake_agent(event, data, target_agent=target)
    record['status'] = status
    _append_audit(Path(log_path), record)
    print(f'[dispatch] {title} → {target} (event={event}) status={status} sha={digest}')
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='把任务派给处置 agent（带报告要求与留痕）')
    parser.add_argument('--title', required=True, help='任务标题（也用于报告标题）')
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--instruction', help='作业指导文本')
    src.add_argument('--instruction-file', help='作业指导文件路径（推荐，便于 review）')
    parser.add_argument('--event', default='agent_task', help='事件名（默认 agent_task）')
    parser.add_argument('--target', default='agent-dh', help='处置 agent（默认 agent-dh）')
    parser.add_argument('--urgency', default='normal', choices=['normal', 'high', 'critical'])
    parser.add_argument('--no-report', action='store_true',
                        help='静默任务：不附加飞书报告要求（夜间哨兵/纯巡检用）')
    parser.add_argument('--dry-run', action='store_true', help='只打印最终指令，不派单')
    parser.add_argument('--log', default=str(DEFAULT_LOG), help='派单审计日志（JSONL）')
    args = parser.parse_args(argv)

    if args.instruction_file:
        instruction = Path(args.instruction_file).read_text(encoding='utf-8')
    else:
        instruction = args.instruction

    result = dispatch(
        title=args.title,
        instruction=instruction,
        event=args.event,
        target=args.target,
        requires_report=not args.no_report,
        urgency=args.urgency,
        dry_run=args.dry_run,
        log_path=Path(args.log),
    )
    if result.get('status') == 'dry_run':
        return 0
    return 0 if result.get('status') == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
