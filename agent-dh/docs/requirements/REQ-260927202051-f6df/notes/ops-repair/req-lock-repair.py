#!/usr/bin/env python3
"""
一次性运维修复 · REQ-260927202051-f6df / t-e77b06 解锁（2026-09-27）

做两件事（只这两件，幂等，可重放）：
  1) 清除该需求的**陈旧 advance 锁**：runId / lockAt
     —— owner 进程已被 23:26 的 quick_restart 杀掉，后台 job 已 not_found；
        锁只在 driveChain 的 finally 清理（AdvanceChain.ts:372），进程被 kill 则永不执行，
        且 :416 的 runId 检查不看过期时间，`reqboard_clear_pause` 只清 Dive ⇒ 无工具路径可清。
  2) 补回 **v8→v9 迁移留痕** migrations[{from:8,to:9,at,by}]
     —— 留痕被 22:58 修复前的旧构建进程写丢（现 dist 已含保留逻辑）；
        取值来源 = .dsh-data/dsh-reqboard.json.migrate-manifest-1790520911425.json。

写入方式对齐 src/adapters/JsonLedgerRepository.ts 的 persistAtomic：
同目录 dot 前缀临时文件 → write → fsync → os.replace（同文件系统内原子）。
格式对齐运行时 mutate 路径：compact JSON.stringify（单行、不转义非 ASCII）。

用法：req-lock-repair.py <ledger 路径> [requirementId]
退出码：0=已修复或无需修复；2=前置校验失败（绝不落盘）
"""
import json
import os
import random
import shutil
import string
import sys
import time

REQ_DEFAULT = "REQ-260927202051-f6df"
MIGRATION = {"from": 8, "to": 9, "at": 1790520911425, "by": "migrate-ledger.ts"}


def atomic_write(path: str, text: str) -> None:
    """对齐 persistAtomic：同目录 dot 临时文件 + fsync + rename。"""
    tmp = os.path.join(
        os.path.dirname(path),
        "." + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)) + ".tmp",
    )
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, text.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：req-lock-repair.py <ledger 路径> [requirementId]")
        return 2
    ledger_path = sys.argv[1]
    req_id = sys.argv[2] if len(sys.argv) > 2 else REQ_DEFAULT

    with open(ledger_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    # ---- 前置校验：不是 v9 台账 / 仍带 tasks / 目标需求缺失 → 拒绝落盘 ----
    problems = []
    if data.get("schemaVersion") != 9:
        problems.append("schemaVersion=%r（期望 9）" % data.get("schemaVersion"))
    if "tasks" in data:
        problems.append("台账仍带 tasks 字段（期望已移除）")
    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        problems.append("requirements 不是数组")
    target = None
    if isinstance(reqs, list):
        for r in reqs:
            if r.get("id") == req_id:
                target = r
                break
    if target is None:
        problems.append("未找到需求 %s" % req_id)
    if problems:
        print("❌ 前置校验失败，未落盘：")
        for p in problems:
            print("   - " + p)
        return 2

    changes = []   # 真实变更
    notes = []     # 事实说明（不触发写入）

    # ---- 1) 清陈旧锁 ----
    adv = target.get("advance")
    if isinstance(adv, dict):
        for key in ("runId", "lockAt"):
            if key in adv:
                changes.append("advance.%s=%s → 删除" % (key, adv[key]))
                del adv[key]
    else:
        notes.append("advance 不存在（无需清锁）")

    # ---- 2) 补迁移留痕 ----
    migs = data.get("migrations")
    if not isinstance(migs, list):
        migs = []
        data["migrations"] = migs
    if any(m.get("from") == 8 and m.get("to") == 9 for m in migs if isinstance(m, dict)):
        notes.append("migrations 已含 {8,9}（无需补）")
    else:
        migs.append(dict(MIGRATION))
        changes.append("migrations += {from:8,to:9,at:%d,by:%s}" % (MIGRATION["at"], MIGRATION["by"]))

    if not changes:
        print("ℹ️ 无需修复（幂等 no-op）")
        for n in notes:
            print("   · " + n)
        return 0

    # 写入前：备份 + 保留 requirements 条数 ----
    before_reqs = len(reqs)
    backup = "%s.pre-lock-repair-%d" % (ledger_path, int(time.time() * 1000))
    shutil.copy2(ledger_path, backup)

    atomic_write(ledger_path, json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    # 写后回读校验 ----
    with open(ledger_path, "r", encoding="utf-8") as fh:
        after = json.load(fh)
    ok = True
    if len(after.get("requirements", [])) != before_reqs:
        ok = False
    a_req = next((r for r in after["requirements"] if r["id"] == req_id), None)
    if a_req is None or "runId" in (a_req.get("advance") or {}) or "lockAt" in (a_req.get("advance") or {}):
        ok = False
    if not any(m.get("from") == 8 and m.get("to") == 9 for m in after.get("migrations", [])):
        ok = False

    print("备份：%s" % backup)
    for c in changes:
        print("   · " + c)
    print("回读校验：%s（requirements %d 条；advance.runId/lockAt 已清；migrations 末条=%s）" % (
        "✅ 通过" if ok else "❌ 失败",
        len(after.get("requirements", [])),
        json.dumps((after.get("migrations") or [{}])[-1], ensure_ascii=False),
    ))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
