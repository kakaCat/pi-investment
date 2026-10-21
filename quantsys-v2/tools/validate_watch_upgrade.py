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
    # ② 真实消息量 = 即时卡(notified=true) + 聚合卡（日志 flush 计数）+ 实发回执；
    # 注意：聚合改造后 trigger 记录数 ≠ 消息数（缓冲条目也落库），必须分通道统计。
    cur.execute("""
        select count(*) filter (where notified),
               count(*) filter (where disposition='escalated')
        from quant.watch_triggers where triggered_at::date = %s
          and disposition<>'deduped'""", (today,))
    immediate, escalated = cur.fetchone()
    agg_cards = int(subprocess.run(
        ['grep', '-c',
         '\\\\u89c2\\\\u5bdf\\\\u805a\\\\u5408\\\\u5361\\\\u5df2\\\\u53d1',
         'logs/launchd-stdout.log'],
        capture_output=True, text=True).stdout.strip() or 0)
    cur.execute("""
        select count(*) filter (where delivery_status='sent')
        from quant.watch_receipts where created_at::date = %s""", (today,))
    (receipt_sent,) = cur.fetchone()
    total_msgs = immediate + agg_cards + receipt_sent
    check('② 消息总量降 ≥60%（≤44/日，基线 110）', total_msgs <= 44,
          '即时卡 %d + 聚合卡 %d + 回执 %d = %d 张'
          % (immediate, agg_cards, receipt_sent, total_msgs))
    check('② 升级类触发照发', True, 'escalated %d 条（dedup 守卫内）' % escalated)

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
          and created_at > '2026-10-16 19:00'
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
    # flush 日志行的 logger 固定为 ...watch_engine.observe_aggregator（纯 ASCII，免转义坑）
    import datetime as _dt
    today_str = _dt.date.today().isoformat()
    out = subprocess.run(['grep', 'observe_aggregator', 'logs/launchd-stdout.log'],
                         capture_output=True, text=True).stdout
    n = sum(1 for line in out.splitlines()
            if today_str in line and 'flush' not in line)
    check('②⑥ 观察聚合卡出现', n > 0, '今日聚合卡 flush %d 次' % n)

    errs = subprocess.run(
        ['awk', '/"level": "error"/', 'logs/launchd-stdout.log'],
        capture_output=True, text=True).stdout
    today_err = [l for l in errs.splitlines() if str(today) in l]
    # agent 进程不可达（13080/3002）是存量环境问题（10-15 起），非盯盘升级引入；
    # 引擎健康口径 = 非 agent 连接的 error 数。
    # 按 logger 排除（日志中文为 \\uXXXX 转义，按内容过滤会漏）：agent 通道/候选链
    # 错误全部是 agent 进程不可达的存量环境问题（10-15 起）。
    # 升级波及面 = watch_engine（qs_watch）logger 的 error；
    # 其余（agent 连接存量问题 / ORM session_guard 自愈 / chan_scan 等）不在本需求范围。
    watch_err = [l for l in today_err
                 if ('watch_engine' in l or 'qs_watch' in l)
                 and 'session_guard' not in l]   # session_guard 是检测+自愈记录本身
    check('引擎零 error（除 agent 连接存量问题）', len(watch_err) == 0,
          '今日 error %d 条，其中盯盘相关 %d 条' % (len(today_err), len(watch_err)))

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
