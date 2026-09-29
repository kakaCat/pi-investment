# 运维修复记录 · 陈旧 advance 锁 + v8→v9 迁移留痕（2026-09-27 23:3x）

> 触发方：REQ-260927202051-f6df / t-e77b06（看板实测回归）投递被拒。
> 用户裁定（ask_user_question，2026-09-27 23:31）：选 **A · 清陈旧锁 + 补迁移留痕，然后投递链**。
> 本目录留档修复脚本与编排脚本，供复核与重放。

---

## 1. 症状

`reqboard_task_run(task_id=t-e77b06)` 返回：

```
REQBOARD_DISPATCH_FAILED：该需求已有 run 在跑（runId=run-1790521730304-pbbp4df）
```

但同一 run 的自述状态自相矛盾：

| 证据 | 取值 | 来源 |
|---|---|---|
| `reqboard_run_status(run-1790521730304-pbbp4df)` | `jobStatus=not_found`、`nextReady=[t-c130ca]` | 工具实调，2026-09-27 23:31 |
| 台账 `advance.runId` / `advance.lockAt` | `run-1790521730304-pbbp4df` / 23:08:50 | `.dsh-data/dsh-reqboard.json` |
| 认领该 run 的进程 | 已被 23:26 的 quick_restart 杀死（新 pid 7931 / 现 8xxx） | `state/server.pid`、quick-restart.log |
| 链事件日志末条 | `15:12:43Z OPEN_PARENT t-e77b06`（落 4 张子卡后即断） | `advance-log.md` |

## 2. 根因：锁只有一条清理路径，且被 kill 绕过

- 锁的**唯一**清理点是 `AdvanceChain.ts:365-378` 的 `finally`（`advance.lockAt/runId = undefined`）。
  后台 job 所属进程被 quick_restart kill 掉 → `finally` 永不执行 → 锁永久残留。
- 重投递的判据 `AdvanceChain.ts:416` 是 `if (req0.advance?.runId !== undefined)` →
  **只看 runId 是否存在，不看过期时间**；上面 :411 的 `advanceLockStaleMs`（15 分钟）只用于
  提前返回 `locked`，**不对 runId 生效**。实测 lockAt 已陈旧 27 分钟仍不放行。
- 没有第二条路：`reqboard_clear_pause` 只清 `dive.activation/pausedReason`（`ClearPause.ts:53-70`）；
  `orphan-collector.ts:49` 仍是 `// TODO: 从 RequirementRecord.advance.runId 读取` 的桩；
  HTTP 只有 `POST /dashboard/api/reqboard/req/autorun` 会碰 `advance`，而它同样调
  `deps.advance()` → 撞同一个门。
- ⇒ **"失败即暂停，人工处置后再次调用本工具续跑" 这条恢复路径在进程被 kill 的场景下是死的**，
  必须人工清台账状态。（与需求明写的「不实现断点续传」边界相邻，但这是本需求自身推进的硬阻塞。）

## 3. 顺带发现：活台账丢了 v8→v9 迁移留痕

```
$ node --import tsx/esm scripts/migrate-ledger.ts --file .dsh-data/dsh-reqboard.json --root <root> --verify
❌ 校验未通过（3 项）：
  - migrations 末条不是 {from:8,to:9}：undefined        ← 本条
  - 队列与备份重放不一致（…）：…/REQ-260927202051-f6df/queue.json
  - 台账与备份重放不一致（除 migrations[].at 外）
[exit code: 1]
```

- 迁移在 22:55 执行（`dsh-reqboard.json.pre-v9-20260927-225507`），留痕本应在台账里。
- 但 22:58 才加上的保留逻辑（`JsonLedgerRepository.ts:150-168`）此前不存在：旧构建进程
  `load()` 只重建 4 个字段 → **第一次落盘就把 migrations 永久写丢**（落盘的是整册 draft）。
- 现 `dist/index.mjs` 已含保留逻辑（bundle 内可见 `...migrations !== void 0 ? { migrations } : {}`），
  故**补回去之后不会再丢**。
- 留痕真值仍在 `dsh-reqboard.json.migrate-manifest-1790520911425.json`
  （`{from:8,to:9,at:1790520911425,by:'migrate-ledger.ts'}`）；pre-v9 备份的 `migrations` 为 `null`，
  故补一条即可复现迁移脚本的写入结果。

## 4. 处置

脚本：[`req-lock-repair.py`](./req-lock-repair.py)（150 行，幂等）
编排：[`req-lock-repair-arm.sh`](./req-lock-repair-arm.sh)（等旧进程退出后再写）

只做两件事，且写入前先过前置校验（`schemaVersion!=9` / 仍带 `tasks` / 需求缺失 → 拒写 exit 2）：

1. 删除 `REQ-260927202051-f6df` 的 `advance.runId`、`advance.lockAt`；
2. `migrations += {from:8,to:9,at:1790520911425,by:'migrate-ledger.ts'}`。

写入方式对齐 `JsonLedgerRepository.ts:persistAtomic`：同目录 dot 临时文件 → `write` → `fsync`
→ `os.replace`；格式对齐运行时 `mutate` 路径（compact 单行、不转义非 ASCII）；写前自动备份为
`dsh-reqboard.json.pre-lock-repair-<ms>`；写后回读校验（requirements 条数不变 / 锁已清 / 留痕在位）。

**为什么必须卡在「旧进程已死、新进程未 `load()`」窗口**：台账是整册内存态落盘
（`mutate` → `JSON.stringify(draft)`），旧进程活着时改文件必被下一次写覆盖；而插件在 boot 时
**急切** load（`src/index.ts:132 void store.load()`），所以新进程起来后再改也没用。

### 第一次尝试为什么失败（已复现，勿重蹈）

第一版用 `nohup bash … &` 起等死作业，结果**作业与旧进程同组被一起回收**：日志只留 `armed` 一行，
没有 `pid gone`，也没有任何备份文件。→ 第二次改用 `python3 … start_new_session=True`（setsid 语义）
给作业独立进程组（实测 pgid 与外层 7775 不同），再重启。

## 5. 验证（修复后应看到）

- [ ] 台账 `advance.runId` / `advance.lockAt` 已无；`migrations` 末条 = `{from:8,to:9,…}`
- [ ] `--verify` 的 3 项问题降为 **2 项**，且剩余 2 项**全是迁移后运行期漂移**
      （本需求 queue.json 因链推进而变；台账因评论/autoRun/artifact 而变——脚本只归一化
      `migrations[].at`）。实测（`/tmp/vstage` 副本 + `backup-1790520911425` 重放）：
      退出码 1，问题列表 = 上述 2 项 ⇒ **`--verify` 退出码 0 只能在「apply 后未被运行期改动」的
      纯净副本上取证**，不能拿跑了 6 小时的活台账当判据。
- [ ] `reqboard_task_run(task_id=t-e77b06)` 返回 `status=dispatched`
