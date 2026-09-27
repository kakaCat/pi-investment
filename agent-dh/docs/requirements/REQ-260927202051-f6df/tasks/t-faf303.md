# t-faf303 实现 v8→v9 迁移变换与 CLI

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 v8→v9 迁移变换与 CLI

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

① `--dry-run` 台账 md5/mtime **不变**且无 queue.json 生成（TC-6.1/6.2）；② `--apply` 后台账 `schemaVersion===9`、**顶层无 `tasks` 键**（判据：`node -e "console.log('tasks' in require('<ledger>'))"` → `false`；※ 不用 `grep '"tasks"'`——台账为单行 compact JSON 且 `requirements[].plan.tasks` 真实存在，该 grep 迁移前后恒为 1）、`migrations` 末条 `{8,9}`（TC-6.3/6.4）；③ `--verify` 无差异退出码 0（TC-6.6）；④ `--rollback` 还原 v8 并清理本次生成的 queue.json（TC-6.8）；⑤ **顺序断言**：日志/打点证明先写全部 queue.json 再改台账（D-7 先于 D-8）；⑥ **无任务遗留**：迁移报告 `unmigrated` 必须为 0，且报告列出每一个未迁移项与原因；⑦ 迁移报告须含「源台账现算」的条数与数据时点（不写死数字）。

## 实施方案（implementation）
在 scripts/migrate-ledger.ts 追加 v8→v9 变换 migrateV8toV9（纯函数，内部 structuredClone）与 CLI 四态：--dry-run（默认，报告不落盘）/--apply/--verify/--rollback。按 requirementId 分组 tasks → 构造 QueueFile（schemaVersion:9）→ computeLayers/Edges/Ready → validateQueueFile → 写各需求 queue.json（D-7）→ 再改台账：删 tasks、schemaVersion=9、migrations 追加留痕（D-8）→ 原子替换（D-9）。顺序固定，反序会产生双向丢失。

## 上游产出摘要（dependsSummary）
- 实现队列仓储与原子写入
- 台账 schema v9：移除 tasks

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T13:25:16.820Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

迁移工具落地：一条命令就能把台账里几百张任务卡按需求分片写进各自的队列文件，并且严格保证「先把所有队列写好、再动台账」——顺序反了会产生「台账已清空、队列还没生成」的双向丢失。另带三种安全态：只看不动的预演、核对无差异的校验、以及逐字节还原的回滚；还加了一道守卫，服务正在运行时拒绝执行，防止内存里的旧数据把新文件覆盖回去。

### 完成项

- migrateV8toV9 纯变换（structuredClone + 整对象展开 `{...task, layer}`，不重列字段）
- CLI 四态 --dry-run / --apply / --verify / --rollback 全部可用
- --verify 用「最近备份重放变换」与磁盘逐份比对（归一 generated_at/updated_at 与 migrations[].at）
- --rollback 逐字节还原备份，并按 manifest sha256 精确清理本次生成的队列（运行期被改过的文件保留不删）
- D-1~D-9 顺序打点：queueFilesWrittenBeforeLedger=true；lastIndexOf(D-7) < indexOf(D-8) < indexOf(D-9)
- 格式保真：compact 台账迁移后仍 compact（7.9MB 单行不重排）
- 新增服务运行守卫：state/server.pid 存活时拒绝 --apply/--rollback（防 DSH 内存态 v8 覆盖 v9），--force 才放行
- 真实副本实测（rev=5773 / 7,905,194 bytes / 612 tasks / 82 req）：dry-run md5 不变、0 个 queue.json；apply 后 schemaVersion=9、'tasks' in ledger===false、migrations 末条 {8,9}、台账 7,905,194→4,825,231 bytes；verify exit 0（51 份全过）；rollback 逐字节等于备份、tasks 恢复 612
- 上游接线：*Local 过渡实现全部删除，改为 import topology/validateQueue，并有断言 v9Defaults.validate === validateQueueFile 防第二套语义回流

### 改动文件

- `packages/web/dsh-pmboard/scripts/migrate-ledger.ts`
- `packages/web/dsh-pmboard/tests/migrate-ledger-v8v9.test.ts`
- `packages/web/dsh-pmboard/tests/migrate-contract.test.ts`

### 下一步

t-03254f 迁移安全：白名单、幂等与 orphan

---
