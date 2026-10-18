#!/usr/bin/env python
"""缺指引规则补全待办（REQ-261016155500-4f2a）

对「四要素全空」的启用规则（lint=missing_guidance）幂等建 P2 补全待办，交处置 agent
回填 action_params / intent / observation_criterion。重复执行不产生重复待办。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python tools/watch_backfill_todos.py            # dry-run（只列清单）
    PYTHONPATH=. ./venv/bin/python tools/watch_backfill_todos.py --apply    # 建待办
"""
import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='实际建待办（默认只列清单）')
    args = parser.parse_args()

    from application.services.watch_engine.guidance_backfill_service import (
        GuidanceBackfillService,
    )
    svc = GuidanceBackfillService.create_default()
    hits = svc.missing_guidance_rules()
    print('缺指引启用规则 %d 条：' % len(hits))
    for r in hits:
        print('  #%s %s' % (r.id, r.symbol))

    if not args.apply:
        print('== DRY-RUN: 加 --apply 建补全待办 ==')
        return 0

    result = svc.ensure_todos()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
