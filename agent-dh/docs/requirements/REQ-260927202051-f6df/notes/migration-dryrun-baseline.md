# v8→v9 迁移 · dry-run 投产基准（副本预演）

> **用途**：投产时手边有一份「预期输出」，可逐项对照。没有基准的 verify 只是"程序说它自己对了"。
> **本文件是副本预演产物**：活台账全程未被读写（见「未落盘证据」）。
> 机器可读版：[migration-dryrun-baseline.json](./migration-dryrun-baseline.json)

## 数据时点与来源

| 项 | 值 |
|---|---|
| 采集时点 | 2026-09-27T13:26:08.291Z（本地 2026-09-27 21:26，UTC+8） |
| 来源台账 | `/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json` |
| revision | 5776 |
| 文件大小 | 7914486 bytes |
| 采集时 md5 | `ae0a6823d5267d87df7b975b40a81a3a` |
| 编码形态 | 单行 compact JSON（`wc -l` = 0） |
| 源任务数 | 612 条（done 561 / in_progress 8 / todo 43） |
| 需求数 | 82 条（其中含任务 51 条） |
| 预演方式 | 活台账**副本** + `--root` 指向真实工作区根（路径与生产同形） |

## 生成命令（可直接复现）

```bash
cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
node --import tsx/esm scripts/migrate-ledger.ts \
  --file <活台账副本> \
  --root /Users/yunpeng/pi-investment/agent-dh \
  --dry-run            # 加 --json 得机器可读版
```

## 预期输出（人类可读，逐字）

```text
── v8 → v9 迁移报告（dry-run）──
台账：/tmp/mig-baseline2-HKjFnA/.dsh-data/dsh-reqboard.json
源 schemaVersion：8  需求 82 条  任务 612 条
分组：51 个需求有任务；orphan 0 条（不迁移）
队列文件：51 个（计划）
🆕 新建目录 REQ-48d896 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-48d896（9 任务）
白名单：3 条命中 / 白名单外 0 条
  · REQ-24e15d → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-24e15d/queue.json（6 任务，ready=0）
  · REQ-a458a6 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-a458a6/queue.json（7 任务，ready=0）
  · REQ-48d896 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-48d896/queue.json（9 任务，ready=0）
  · REQ-31e11f → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-31e11f/queue.json（9 任务，ready=0）
  · REQ-ff20ca → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-ff20ca/queue.json（8 任务，ready=0）
  · REQ-9f4a44 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-9f4a44/queue.json（6 任务，ready=0）
  · REQ-6f39b5 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-6f39b5/queue.json（20 任务，ready=2）
  · REQ-2e9473 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-2e9473/queue.json（19 任务，ready=0）
  · REQ-47939a → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-47939a/queue.json（14 任务，ready=0）
  · REQ-422af1 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-422af1/queue.json（12 任务，ready=0）
  · REQ-c9f899 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-c9f899/queue.json（12 任务，ready=0）
  · REQ-a33899 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-a33899/queue.json（17 任务，ready=0）
  · REQ-d3e61a → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-d3e61a/queue.json（18 任务，ready=0）
  · REQ-b63a7d → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-b63a7d/queue.json（7 任务，ready=0）
  · REQ-b545fe → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-b545fe/queue.json（7 任务，ready=0）
  · REQ-81aabd → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-81aabd/queue.json（5 任务，ready=0）
  · REQ-640a55 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-640a55/queue.json（5 任务，ready=0）
  · REQ-327bdf → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-327bdf/queue.json（9 任务，ready=0）
  · REQ-a8d582 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-a8d582/queue.json（5 任务，ready=0）
  · REQ-308b9a → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-308b9a/queue.json（8 任务，ready=0）
  · REQ-e3b6a0 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-e3b6a0/queue.json（10 任务，ready=0）
  · REQ-f0579a → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-f0579a/queue.json（5 任务，ready=0）
  · REQ-4842fe → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-4842fe/queue.json（12 任务，ready=0）
  · REQ-9494f9 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-9494f9/queue.json（4 任务，ready=0）
  · REQ-c48f99 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-c48f99/queue.json（7 任务，ready=0）
  · REQ-2d1c74 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-2d1c74/queue.json（7 任务，ready=0）
  · REQ-84bea5 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-84bea5/queue.json（5 任务，ready=0）
  · REQ-f6307c → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-f6307c/queue.json（4 任务，ready=0）
  · REQ-260922012924-2e29 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260922012924-2e29/queue.json（6 任务，ready=0）
  · REQ-260922133212-dd5b → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260922133212-dd5b/queue.json（2 任务，ready=0）
  · REQ-260922182505-0924 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260922182505-0924/queue.json（3 任务，ready=0）
  · REQ-260922182638-0777 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260922182638-0777/queue.json（6 任务，ready=0）
  · REQ-260922213356-4a45 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260922213356-4a45/queue.json（12 任务，ready=2）
  · REQ-260923134706-e72f → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260923134706-e72f/queue.json（8 任务，ready=0）
  · REQ-260923222557-d3b0 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260923222557-d3b0/queue.json（7 任务，ready=0）
  · REQ-260924002956-f37c → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260924002956-f37c/queue.json（4 任务，ready=0）
  · REQ-260924104605-ad0a → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260924104605-ad0a/queue.json（7 任务，ready=0）
  · REQ-260924213231-b1c4 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260924213231-b1c4/queue.json（65 任务，ready=0）
  · REQ-260925110957-552d → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260925110957-552d/queue.json（23 任务，ready=0）
  · REQ-260925172227-2d61 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260925172227-2d61/queue.json（11 任务，ready=0）
  · REQ-260925212722-96e7 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260925212722-96e7/queue.json（16 任务，ready=0）
  · REQ-260925234037-1503 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260925234037-1503/queue.json（8 任务，ready=0）
  · REQ-260926140539-457b → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260926140539-457b/queue.json（20 任务，ready=0）
  · REQ-260926215013-1568 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260926215013-1568/queue.json（7 任务，ready=0）
  · REQ-260926205654-163a → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260926205654-163a/queue.json（3 任务，ready=1）
  · REQ-202609262349-1518 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-202609262349-1518/queue.json（14 任务，ready=0）
  · REQ-260927100007-b8ba → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260927100007-b8ba/queue.json（16 任务，ready=0）
  · REQ-260927121324-abde → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260927121324-abde/queue.json（42 任务，ready=2）
  · REQ-260927123256-196b → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260927123256-196b/queue.json（10 任务，ready=0）
  · REQ-260927144541-0481 → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260927144541-0481/queue.json（40 任务，ready=0）
  · REQ-260927202051-f6df → /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260927202051-f6df/queue.json（25 任务，ready=2）
执行顺序（计划）：D-7 先写 51 份 queue.json → D-8 台账变换 → D-9 原子替换台账
✅ dry-run 完成：未落盘（台账 md5/mtime 不变，未生成任何 queue.json）
```

## 投产时逐项对照清单

| # | 判据 | 本期基准（2026-09-27 21:26 现算） | 性质 |
|---|---|---|---|
| 1 | 退出码 | `0` | 不变量 |
| 2 | 源 `schemaVersion` | `8` | 不变量（未迁移态） |
| 3 | 任务总数 | `612`（现算，会随活台账增长） | **漂移项** |
| 4 | 有任务的需求数 | `51`（现算） | **漂移项** |
| 5 | `orphanTasks` | `[]` | 不变量 |
| 6 | `skipped` | `[]`（无环、无校验失败） | 不变量 |
| 7 | 计划队列文件数 | `51`（= 源台账中 `requirementId` 真实存在的去重需求数，现算） | **漂移项** |
| 8 | `createdDirs` | `[{REQ-48d896, 9 任务}]` | 条件不变量¹ |
| 9 | 白名单 | 命中 `3`（schemaVersion / tasks / migrations）、**外部 `0`** | 不变量 |
| 10 | `backupPath` / `manifestPath` / `unmigratedPath` | 均 `null`（dry-run 不备份、不建目录、不隔离） | 不变量 |
| 11 | 台账侧副作用 | md5 与 mtime **不变** | 不变量 |
| 12 | 新建 queue.json 数 | `0`（预演目录与真实工作区都是 0） | 不变量 |

¹ 若投产前有人把 `docs/requirements/REQ-48d896/` 建出来，`createdDirs` 会退化为 `[]`——不视为失败（该需求 9 条 archived 任务改走正常目录迁入）。

## 未落盘证据

| 证据 | 值 |
|---|---|
| 副本台账 md5（dry-run 前 → 后） | `ae0a6823d5267d87df7b975b40a81a3a` → `ae0a6823d5267d87df7b975b40a81a3a`（**一致**） |
| 副本台账 mtime（前 → 后） | `1790515567` → `1790515567`（**一致**） |
| 副本工作区 queue.json 数 | `0` |
| **真实工作区** queue.json 数 | `0` |
| 报告内 apply 路径字段 | `backupPath=null` / `manifestPath=null` / `unmigratedPath=null`（证明未走任何写路径） |
| 活台账（/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json） | 本流程只 `readFileSync` 复制副本，**未打开写句柄**；`--dry-run` 在写路径（D-2/D-7/D-8/D-9）之前即 return |

## 漂移提示（重要）

台账是**活文件**：本轮 587 → 612 条就是被后续拆分"喂"出来的。投产时的 dry-run 若与上表 count 类数字不同，**先看是否为正常增长**（对 `revision` 与任务数增量），不要把"数字变了"误判成"迁移坏了"。
真正必须逐项一致的是**结构类不变量**：`orphanTasks=[]`、`whitelist.bad=[]`、`skipped=[]`、`backupPath/manifestPath/unmigratedPath 全 null`、台账 md5/mtime 不变、queue.json 写入 0。

## 投产与回滚（摘要）

```bash
LED=/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json
cd /Users/yunpeng/pi-investment/agent-dh && ./scripts/stop.sh            # 必须：服务在跑会被守卫拒绝
cd packages/web/dsh-pmboard
cp "$LED" "$LED.pre-v9-manual-$(date +%s)"                                # 二次人工备份
node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --dry-run   # 与本基准对照
node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --apply
node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --verify; echo "verify exit=$?"
cd /Users/yunpeng/pi-investment/agent-dh && ./scripts/start.sh            # 起服务 → 看板实测
```

- **顺序**：D-7（先写全部 queue.json）→ D-8（台账变换就绪）→ D-9（原子替换台账）；报告含 `queueFilesWrittenBeforeLedger=true` 作为机器可核验位。
- **回滚前置**：`<ledger>.backup-<ts>` 与 `<ledger>.migrate-manifest-<ts>.json` **不要删**——`--rollback` 靠 manifest 里的 sha256 精确清理本次生成的队列；迁移后被运行期改过的 queue.json 会被**保留**并点名，不会误删。

