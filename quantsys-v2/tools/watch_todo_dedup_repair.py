#!/usr/bin/env python
"""盯盘治理待办重复建：数据修复 + 结构性校验（2026-10-19 用户裁定）

## 背景

「同规则同时存在多条未收敛 rule_change 待办」的存量来源：
  · 9 月旧代码跨日重复建（规则 57/200，#40/#47、#53/#55）
  · 10-16 补全待办（P2）与自愈修规则待办（P1）同规则双开（规则 250/255，#67/#91、#72/#90）

幂等守卫已于 2026-10-16/19 上线（noise_self_heal_service._open_repair_todo +
GuidanceBackfillService.list_open_by_rule），但存量重复与"再次发生"的结构保证缺失。

## 本工具做两件事

1. **修复数据**：每组重复保留**最新一条**（id 最大），其余置 terminal='expired'
   （close_reason 记清理原因与保留的待办号；走 TodoService.close 不发回执卡——
   清理动作本身不该再打扰用户）。
2. **结构性校验**：创建部分唯一索引——同规则同时**只能有一条**未收敛的
   rule_change + trigger_id IS NULL 待办。索引是最后防线（代码守卫之外的硬约束）。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python tools/watch_todo_dedup_repair.py            # dry-run
    PYTHONPATH=. ./venv/bin/python tools/watch_todo_dedup_repair.py --apply
"""
import argparse
import os
from typing import Dict, List

import psycopg2

DDL_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_watch_todos_open_rulechange
ON quant.watch_todos (rule_id)
WHERE action_kind = 'rule_change' AND trigger_id IS NULL AND terminal IS NULL
"""


def _conn():
    return psycopg2.connect(
        'postgresql://%s:%s@127.0.0.1:%s/%s'
        % (os.environ.get('PGUSER', 'mac'), os.environ.get('PGPASSWORD', ''),
           os.environ.get('PGPORT', '5432'),
           os.environ.get('PGDATABASE', 'quant_investment')))


def plan_repairs(rows: List[Dict]) -> List[Dict]:
    """重复组 → 修复计划（纯函数，可单测）。

    rows: [{rule_id, id, level, created_at}]（仅重复组的全部成员，已按 id 升序）
    返回: [{'rule_id', 'keep': id, 'expire': [ids...]}]——每组保留 id 最大的一条。
    """
    groups: Dict[int, List[int]] = {}
    for r in rows:
        groups.setdefault(r['rule_id'], []).append(r['id'])
    return [{'rule_id': rid, 'keep': ids[-1], 'expire': ids[:-1]}
            for rid, ids in sorted(groups.items()) if len(ids) > 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        select rule_id, id, level, created_at
        from quant.watch_todos
        where terminal is null and action_kind='rule_change' and trigger_id is null
        order by rule_id, id""")
    rows = [{'rule_id': r[0], 'id': r[1], 'level': r[2], 'created_at': r[3]}
            for r in cur.fetchall()]
    plans = plan_repairs(rows)

    if not plans:
        print('✅ 无重复：同规则开放 rule_change 待办 ≤1 条')
    for p in plans:
        print('规则 #%d：保留 #%d，过期 %s' % (p['rule_id'], p['keep'], p['expire']))

    if args.apply and plans:
        for p in plans:
            for tid in p['expire']:
                cur.execute("""
                    update quant.watch_todos
                    set terminal='expired', closed_at=now(),
                        close_reason=%s, updated_at=now(),
                        decision_audit_id=%s
                    where id=%s and terminal is null""",
                    ('幂等清理：同规则存在更新的 rule_change 待办 #%d（保留）'
                     % p['keep'], 'todo-dedup-repair-20261019', tid))
        conn.commit()
        print('== 已过期 %d 条重复待办 ==' % sum(len(p['expire']) for p in plans))

    if args.apply:
        # 数据已净 → 建结构校验（唯一部分索引）
        cur.execute(DDL_INDEX)
        conn.commit()
        cur.execute("""
            select indexname from pg_indexes
            where schemaname='quant' and indexname='uq_watch_todos_open_rulechange'""")
        ok = cur.fetchone() is not None
        print('== 结构校验：uq_watch_todos_open_rulechange %s =='
              % ('已创建 ✅' if ok else '创建失败 ❌'))
        return 0 if ok else 2

    print('== DRY-RUN：加 --apply 执行修复 + 建索引 ==' if plans
          else '== DRY-RUN：加 --apply 仅建索引 ==')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
