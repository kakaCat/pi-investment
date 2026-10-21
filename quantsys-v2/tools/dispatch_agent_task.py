"""派单运维入口（薄 CLI）——逻辑在 qs_notification.application.agent_task_dispatch。

为什么不把信封/报告要求写在这里：同一份话术必须被系统（服务/调度）和运维共用，
放在 CLI 里就只服务于"人记得敲命令"的那一次。本文件只做三件事：读参数、调服务、留痕。

用法：
    PYTHONPATH=. ./venv/bin/python tools/dispatch_agent_task.py \
        --title "盯盘积压清理（10-20 晚）" \
        --instruction-file /tmp/sweep.md \
        --event watch_backlog_sweep

    ... --no-report     # 静默任务（夜间哨兵/纯巡检）
    ... --dry-run       # 只看最终指令，不派单

口径见 docs/guides/agent-task-dispatch.md：status=ok 只代表通道收下，不代表执行。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LOG = ROOT / 'logs' / 'agent-dispatch.jsonl'


def append_audit(log_path: Path, record: dict) -> None:
    """运维留痕（服务端另有 structlog 记录；这里给"谁在什么时候派的"一份可 grep 的账）。"""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as exc:  # noqa: BLE001 - 留痕失败不打挂派单
        print(f'[warn] 派单留痕写入失败（不影响已发出的派单）: {exc}', file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='把任务派给处置 agent（信封/报告要求由服务层统一加）')
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

    from qs_notification.application import build_instruction, dispatch_agent_task

    instruction = (Path(args.instruction_file).read_text(encoding='utf-8')
                   if args.instruction_file else args.instruction)
    requires_report = not args.no_report

    if args.dry_run:
        print(build_instruction(args.title, instruction, requires_report, args.urgency))
        print(f'\n[dry-run] 未派单。event={args.event} target={args.target}')
        return 0

    try:
        result = dispatch_agent_task(
            title=args.title,
            instruction=instruction,
            event=args.event,
            target=args.target,
            requires_report=requires_report,
            urgency=args.urgency,
        )
    except Exception as exc:  # noqa: BLE001 - 运维入口要把失败说清楚
        print(f'[dispatch] 派单异常：{exc}', file=sys.stderr)
        return 2

    record = {'ts': datetime.now().isoformat(timespec='seconds'), **result, 'operator': 'cli'}
    append_audit(Path(args.log), record)
    print(f"[dispatch] {result['title']} → {result['target']} "
          f"(event={result['event']}) status={result['status']} sha={result['prompt_sha256_16']}")
    return 0 if result.get('status') == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
