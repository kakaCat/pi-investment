# REQ-47939a 账本 v4 → v5 迁移报告（t10 交付物）

> 执行窗口：subagent（w-f6f6e723）· 发起窗口：w-41e7e4cd · 执行时间：2026-09-17
> 口径来源：全部数字为**本次实测**（命令与输出见 §4），非估算；数据来源标注遵循 R-013。
> 迁移脚本：`packages/pages/dsh-pmboard/scripts/migrate-ledger.ts`（经 tsx 运行，见 `design/migration.md` §3.1 D-8 裁定）
> 测试：`packages/pages/dsh-pmboard/tests/migration.test.ts`（9 passed）

## 1. 迁移前后口径（before = 当前真实台账的**副本**）

| 项 | before | after |
|----|--------|-------|
| 文件 | `$DSH_HOME/dsh-reqboard.json` 的副本（`/tmp/req47939a-live-copy.json`） | 同左（原地原子替换） |
| 源文件 | `/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json`（822,383 B） | **未改动**（见 §5） |
| 副本 md5 | `5e172c88b685e53810ea77c0e84f5589`（与真实台账 md5 逐字节一致） | — |
| `schemaVersion` | **4** | **5** |
| `revision` | 926 | 926（迁移不 bump；见 §3 白名单说明） |
| requirements | **34** | **34** |
| tasks | **97** | **97** |
| triages | **2** | **2** |

> **关于任务数 84 vs 97**：t10 卡面/需求文档写的是「34 需求 / 84 任务」，那是 2026-09-17 **需求期**的口径；
> 冻结样本（`tests/fixtures/ledger-v4-sample.json`）与当前真实台账均为 **34 / 97 / 2**（97 = 本需求实施过程中
> 新增任务后的事实计数，`design/migration.md` §1.1 已记录该修正）。本报告按**事实**记 97，不按卡面记 84。
> 「复核行」= 逐条核对（§1.1 需求/任务状态分布 + §3 逐项变更计数），不是抽样。

### 1.1 复核行：before 全量分布（34 需求 / 97 任务 / 2 待归类，逐条口径）

| 维度 | 分布 |
|------|------|
| 需求状态 | done 18 · archived 8 · planning 6 · decomposing 1 · implementing 1（合计 34） |
| 任务状态 | done 77 · in_progress 5 · todo 15（合计 97） |
| 待归类 | 2 |
| 含 `statusHistory` 的需求 | 34 / 34 |
| 含 `projectId` / `parentId` 的需求 | 0 |
| 字符串型 `verification.sheet.items[].source` | 20（全部属于 REQ-2e9473） |
| 缺 `task.scope` 的任务 | 0 |

迁移后上述 8 个口径逐一复核：需求/任务/待归类计数、状态分布**完全不变**；唯一的数据形态变化是 §3 的 C7（源判别联合）。

## 2. 白名单外差异数 = **0**

`--dry-run` 输出（原文）：

```
── 迁移报告（dry-run）──
before: schemaVersion=4 revision=926 requirements=34 tasks=97 triages=2
after : schemaVersion=5 revision=926 requirements=34 tasks=97 triages=2
差异路径 22 条；白名单内 22 条，**白名单外 0 条**
```

22 条差异路径的构成：`schemaVersion`（C1）1 条 + `migrations`（C2）1 条 +
`requirements[1].verification.sheet.items[*].source`（C7）20 条 —— 全部落在
`scripts/migrate-ledger.ts` 的 `WHITELIST`（对应 `design/migration.md` §4 的允许差异表）内。

## 3. 逐项变更计数（C1–C11，**不为 0 也要列**：没变化与没检查必须能区分）

| # | 变更 | 实测计数 | 说明 |
|---|------|---------|------|
| C1 | `schemaVersion: 4 → 5` | **1** | 同时把运行时常量 `REQBOARD_SCHEMA_VERSION` 提到 5（见 §6.3） |
| C2 | 新增 `migrations: {from,to,at,by}[]` | **1** | `{from:4,to:5,at:<epoch>,by:'migrate-ledger.ts'}` |
| C3 | legacy 状态名归一（reviewing → brainstorming） | **0** | 本台账状态分布全是现行名（无别名残留） |
| C4 | `statusHistory` 必填补齐（复用 backfill 算法） | **0** | 34/34 需求已有；本次快照任务 statusHistory 亦齐 |
| C5 | `category` 缺省补 `feature` | **0** | 无缺失 |
| C6 | 删除零引用预留字段 `projectId` / `parentId` | **0** | 0 条记录含这两个键（它们从未落过盘） |
| C7 | `sheet.items[].source` 字符串 → 判别联合 | **20** | 全部属 REQ-2e9473 的验收单（`'t-xxxxxx'` → `{kind:'task',taskId:'t-xxxxxx'}`） |
| C8 | `task.scope` 缺省补空结构 | **0** | 97/97 已有 |
| C9 | `dependsOn` 去重 + 剔除悬空/自指 | **0** | 无重复、无悬空 |
| C10 | `artifacts` 按 `(kind,path)` 去重 | **0** | 无重复登记 |
| C11 | 迁移报告落盘 | **1** | 即本文件 |

> 方法论点：真实数据上 8 项为空操作 —— **「空操作通过」≠「逻辑正确」**，故 `tests/migration.test.ts`
> 用**合成用例**逐项覆盖 C3/C4/C6/C7/C8/C9/C10 语义（9 passed），不以真实样本的全过当作正确性证据。

## 4. 流水线端到端验证（全部在**副本**上执行）

| 步骤 | 命令 | 结果 |
|------|------|------|
| 备份（自动） | `--apply` 内置 | 生成 `<file>.bak-req47939a-1789648539`（与源文件同字节） |
| ① dry-run | `node --import tsx/esm scripts/migrate-ledger.ts --file /tmp/req47939a-live-copy.json --dry-run` | exit 0，白名单外 0 条（§2） |
| ② apply | 同上 `--apply` | exit 0，原子替换成功，after = 34/97/2 且 schemaVersion=5 |
| ③ verify | 同上 `--verify` | exit 0：`✅ 已是 v5 且结构自洽` |
| ④ 幂等 | 再跑一次 `--apply` | exit 0：`✅ 已是 v5，--apply 幂等无操作`（未产生第二个备份） |
| ⑤ 损坏保护 | 对截断 JSON 跑 `--apply` | **exit 2** 拒绝；原文件 md5 前后一致（`132824883dc4f9320631b134335856fe`），**未生成备份、未落盘** |
| ⑥ 可回滚 | `mv <bak> <file>` 还原 | 还原后 `schemaVersion=4`、34/97/2 完好；此时 `--verify` 正确报 exit 1 并列出两项未达 v5（证明校验不是空转） |
| ⑦ 无残留 | `ls` 副本目录 | 无 `.tmp-req47939a-*` 残留（temp+rename 语义） |
| ⑧ 单元测试 | `npx vitest run tests/migration.test.ts` | **9 passed** |

## 5. ⚠️ 真实台账的迁移**待发起窗口执行**（本卡明确不做）

- 运行中的 DSH 实例（:13080）把 `$DSH_HOME/dsh-reqboard.json` **整份持在内存**里；本卡执行期间若迁移该文件，
  实例随后的任何台账写入都会用内存副本覆盖，迁移成果会被静默抹掉。故本卡**只对副本**跑全流水线。
- 实测证据（真实台账未被触碰）：`.dsh-data/dsh-reqboard.json` 迁移前后同为 **822,383 B / mtime 2026-09-17 20:26 /
  md5 `5e172c88b685e53810ea77c0e84f5589`**（与副本 md5 一致 = 副本确为当时真实快照）。
- **正确做法（待全部任务完成后由发起窗口执行）**：
  1. 停机：`launchctl bootout gui/$(id -u)/com.pi-investment.dsh`（**不可 kill**，KeepAlive 会拉起）；
  2. `node --import tsx/esm packages/pages/dsh-pmboard/scripts/migrate-ledger.ts --file "$DSH_HOME/dsh-reqboard.json" --dry-run`（确认白名单外 0 条）；
  3. `--apply` → `--verify`（应 `✅ 已是 v5 且结构自洽`）；
  4. 重启：`launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`；
  5. 回滚（若需）：`mv "$DSH_HOME/dsh-reqboard.json.bak-req47939a-<epoch>" "$DSH_HOME/dsh-reqboard.json"` 后重启。

## 6. 代码侧收口（t10 item 1：运行时读路径不再依赖 legacy 兼容）

### 6.1 删除 `LEGACY_REQ_STATUS_ALIASES` 及其引用

别名表与**其全部消费方**（`parseTransitionTarget` / `backfill*` / `migrateRequirementStatusNames`）整块移出
`src/shared/protocol.ts`，落到迁移专属模块 **`src/domain/legacy/LegacyStatus.ts`**：

- 引用清理前：`protocol.ts` 内有 5 处（定义 1 + 使用 4：反推时映射、允许集合、status 归一、statusHistory 归一）；
- 清理后：`grep -rn 'LEGACY_REQ_STATUS_ALIASES' src/shared/protocol.ts` = **0 处**（别名表只在 legacy 模块存在）。

### 6.2 删除 store/adapter 里的 backfill **读时兜底**

`src/adapters/JsonLedgerRepository.ts` 的 `load()` 原先做两件事：`migrateRequirementStatusNames(r)`（旧名归一）
与 `backfillRequirementHistory/backfillTaskHistory`（时间线反推回填）。t10 后**整段删除**，读路径只做结构可信度过滤。
反向守卫：`tests/timeline.test.ts` 用例「老台账装载不再回填时间线；写盘按当前契约版本（5）落盘」锁死新契约
（若有人把回填加回 load()，断言立即变红）。

### 6.3 契约版本常量 C1（`REQBOARD_SCHEMA_VERSION` 4 → 5）

必须同步改，否则**迁移成果会被静默抹掉**：`load()` 用该常量重建 `schemaVersion`，常量为 4 时会把文件里的 5
报告成 4、并在下一次写盘时写回 4（`migrations` 留痕还在，但版本回退，`--verify` 会判未达 v5）。
同批：`ReqboardLedger` 增补可选 `migrations` 字段（C2）；删除零引用预留字段类型声明 `projectId`/`parentId`（C6）。
既有断言随契约更新（4 → 5）：`tests/application/repository.test.ts`、`tests/timeline.test.ts`、
`tests/acceptance-criteria.test.ts`、`tests/application/use-cases.test.ts`（后者显式把 harness 视图标成 v4，
否则 4→5 迁移路径会变成 from>=5 的空转 —— **这是加强而非削弱**）。

### 6.4 数据卫生（R-020）

- 迁移只产生 `<file>.bak-req47939a-<epoch>` 与瞬时 `.tmp-req47939a-<pid>`（成功即 rename 消失）；
- 本次验证产物全部在 `/tmp`（`req47939a-live-copy.json` / `req47939a-corrupt.json` / 备份），**不属于仓内派生数据**；
  保留至发起窗口复核（可直接重跑 §4 命令），复核后即可删除；
- 真实台账的备份由发起窗口在正式迁移时生成并保留到复核通过。

## 7. 结论

1. 迁移在**真实台账副本**上端到端可用：白名单外 diff **0**、计数不变（34/97/2）、幂等、损坏输入零副作用、可从备份回滚；
2. 运行时读路径已不再依赖 legacy 兼容（别名表与 backfill 读时调用均删除，函数移入迁移专属模块）；
3. **真实台账仍未迁移** —— 由发起窗口在全部任务完成后按 §5 步骤执行；本报告即为该步的复核基准。
