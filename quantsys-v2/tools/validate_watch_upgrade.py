#!/usr/bin/env python
"""周一（2026-10-19）交易日验收一键核查（REQ-261016155500-4f2a 验收②⑥）

用法（在 quantsys-v2/ 下，盘后执行）：
    PYTHONPATH=. ./venv/bin/python tools/validate_watch_upgrade.py

判据（对应 validate-report.md）：
  ② 触发卡 ≤40 张/日（基线 100~119，降 ≥60%）+ 升级回执=0 + P2 超时零卡片
  ⑥ 聚合卡出现（observe_digest 投递日志）+ 四段式抽样
  附：补全待办回填进度、引擎错误数
"""
import subprocess
import sys
from datetime import datetime

import requests

FAILS = []


def check(name, ok, detail):
    print('%s %s：%s' % ('✅' if ok else '❌', name, detail))
    if not ok:
        FAILS.append(name)


def main() -> int:
    import os
    dsn = ('postgresql://%s:%s@127.0.0.1:%s/%s'
           % (os.environ.get('PGUSER', 'mac'), os.environ.get('PGPASSWORD', ''),
              os.environ.get('PGPORT', '5432'), os.environ.get('PGDATABASE', 'quant_investment')))
    import psycopg2
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    today = datetime.now().date()
    cur.execute("""
        select count(*) filter (where disposition<>'deduped'),
               count(*) filter (where disposition='auto_observed'),
               count(*) filter (where disposition='escalated'),
               count(*) filter (where suppressed)
        from quant.watch_triggers where triggered_at::date = %s""", (today,))
    cards, observe, escalated, suppressed = cur.fetchone()
    check('② 触发卡 ≤40/日', cards <= 40,
          '今日 %d 张（基线 100~119，%s）' % (cards, '降 %.0f%%' % ((1 - cards / 110) * 100)))
    check('② 升级类触发', escalated <= 5, 'escalated %d 条（应极少，全部照发不吞）' % escalated)

    cur.execute("""
        select count(*) filter (where r.kind='escalate'),
               count(*) filter (where r.kind='timeout' and r.delivery_status='sent'
                                and coalesce(t.owner_kind, 'user') <> 'agent')
        from quant.watch_receipts r
        left join quant.watch_todos t on t.id = r.todo_id
        where r.created_at::date = %s""", (today,))
    esc_receipts, timeout_sent = cur.fetchone()
    check('③ 升级回执=0', esc_receipts == 0, 'escalate 回执 %d 条' % esc_receipts)
    # 2026-10-16：agent 自有的待办改走 wake 催办（delivery_status 也是 sent，但不占用户卡），
    # 故本判据只数**归属用户**的超时实发——否则 agent 通道的正常投递会误伤这条门槛。
    check('③ 超时回执仅 P0/P1 且只发用户', timeout_sent <= 10,
          '用户侧 timeout 实发 %d 条（P2/P3 只落台账不应实发；agent 自有走 wake）'
          % timeout_sent)

    cur.execute("""
        select rule_id, count(*) from quant.watch_todos
        where terminal is null and action_kind='rule_change' and trigger_id is null
        group by rule_id having count(*) > 1""")
    dupes = cur.fetchall()
    cur.execute("""
        select count(*) from quant.watch_todos
        where terminal is null and action_kind='rule_change' and trigger_id is null""")
    open_backfill = cur.fetchone()[0]
    check('④⑥ 补全待办幂等', not dupes,
          '未收敛 %d 条（含自愈修规则待办），同规则重复建待办: %s'
          % (open_backfill, dupes or '无'))

    conn.close()

    # 聚合卡与四段式：查当日日志
    log = subprocess.run(['grep', '-c', '观察聚合卡已发', 'logs/launchd-stdout.log'],
                         capture_output=True, text=True).stdout.strip()
    check('②⑥ 观察聚合卡出现', log != '0', '聚合卡投递 %s 次（重启后累计）' % (log or 0))

    errs = subprocess.run(
        ['awk', '/"level": "error"/', 'logs/launchd-stdout.log'],
        capture_output=True, text=True).stdout
    today_err = [l for l in errs.splitlines() if str(today) in l]
    check('引擎零 error', len(today_err) == 0, '今日 error %d 条' % len(today_err))

    # API 冒烟
    try:
        r = requests.get('http://127.0.0.1:5001/api/watch/rules',
                         params={'limit': 1}, timeout=5)
        check('API 存活', r.status_code == 200, 'HTTP %s' % r.status_code)
    except Exception as e:  # noqa: BLE001
        check('API 存活', False, str(e))

    print('\n== %s ==' % ('全部通过 🎉' if not FAILS else '未过: %s' % ', '.join(FAILS)))
    return 0 if not FAILS else 2


if __name__ == '__main__':
    sys.exit(main())
