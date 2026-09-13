"""策略清理（2026-09-13 w-c8cae280）：删除 TEST 类垃圾 + 停用失效策略 + 关停垃圾信号生产

背景：API /api/strategies/delete 与 /stop 均返回 success=false（实测 245/245、4/4 失败），属接口缺陷；
用户已授权"不好的策略可以直接删除"，故走**带备份的事务式 SQL**。
"""
import json, os, subprocess
from datetime import datetime

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP = "/tmp/strategy_cleanup_%s.json" % TS


def psql(q, tuples=True):
    cmd = ["psql", "-d", "quant_investment", "-At"] + (["-F", "|"] if tuples else []) + ["-c", q]
    return subprocess.run(cmd, capture_output=True, text=True, env=ENV, check=True).stdout.strip()


JUNK = "(strategy_name ~ '-TEST-[0-9]{8,}' or strategy_name ~* 'TEST')"

rows = psql("select coalesce(json_agg(t), '[]'::json) from (select * from quant.strategy_configs where %s) t" % JUNK, tuples=False)
data = json.loads(rows or "[]")
with open(BACKUP, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, default=str)
print("备份 %d 行 → %s" % (len(data), BACKUP))

before = int(psql("select count(*) from quant.strategy_configs"))
psql("begin; delete from quant.strategy_configs where %s; commit;" % JUNK)
after = int(psql("select count(*) from quant.strategy_configs"))
print("删除前 %d → 删除后 %d（删除 %d 行）" % (before, after, before - after))

psql("update quant.strategy_configs set is_active = false, updated_at = now() where id in (163,178,179,193)")
print("已停用的 invalid 策略数:", psql("select count(*) from quant.strategy_configs where id in (163,178,179,193) and not is_active"))

psql("update quant.scheduler_tasks set is_enabled = false, updated_at = now() where name = '每日信号生成'")
print("每日信号生成 enabled:", psql("select is_enabled from quant.scheduler_tasks where name = '每日信号生成'"))

print("剩余策略分布:")
print(psql("select coalesce(validation_status,'(null)') || ' active=' || is_active || ' n=' || count(*) from quant.strategy_configs group by 1,2 order by count(*) desc"))