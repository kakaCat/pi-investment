# REQ-47939a 技术设计 · 账本迁移（v4 → v5）

> 上游：`../requirement.md` §6 迁移策略；用户裁定"破坏面放开 + 需迁移"（决策 D-2，未勾选"零迁移底线"）。

## 1. 现状数据（2026-09-17 实测）

| 项 | 值 |
|----|----|
| 文件 | `$DSH_HOME/dsh-reqboard.json`（`/Users/yunpeng/pi-investment/agent-dh/.dsh-data/dsh-reqboard.json`） |
| 大小 / revision | 736,686 B / 870 |
| `schemaVersion` | 4 |
| requirements | 34（archived 8 · done 18 · planning 6 · brainstorming 1 · decomposing 1） |
| tasks | 84 |
| triages | 2（legacy 待归类，保持原样） |
| 含 `artifacts` 的需求 | 17 |
| 含 `verification.sheet` 的需求 | 0（历史需求的验收单未落 ledger，落在 verification 记录内） |

## 2. v5 变更清单（每项都有理由与证据）

| # | 变更 | 理由 / 证据 |
|---|------|------------|
| C1 | `schemaVersion: 5` | 版本号单调递增；读路径按版本分派 |
| C2 | 台账新增 `migrations: { from, to, at, by }[]` | 迁移本身要留痕（可回答"这份台账何时被谁升到 v5"） |
| C3 | 应用并**删除** `LEGACY_REQ_STATUS_ALIASES` | 现读路径 5 处在做别名兜底（`protocol.ts:104/1136/1166/1177/1183`）。迁移一次性把历史状态名映射为现行名后，别名表可整块删除——这是"数据搬迁换代码删除"的净收益 |
| C4 | `requirement.statusHistory` 可选 → 必填 | `store.ts:100/104` 现靠 `backfillRequirementHistory/backfillTaskHistory` 在**每次读**时兜底。迁移固化后读路径可删兜底，使"时间线"成为不变量而非补丁 |
| C5 | `requirement.category` 可选 → 必填（缺省 `feature`） | 分类决定归档必填文档与流程画像（`ARCHIVE_DOC_RULES`）；缺省值必须是数据事实而不是运行期猜测 |
| C6 | 删除零引用预留字段 `projectId` / `parentId` | 全仓引用计数 0（实测 `grep -rn "\.projectId|\bprojectId[?]*:"` = 0，同理 parentId）。"预留但没人用"的字段只会让人以为功能存在 |
| C7 | `verification.sheet.items[].source` 由字符串改为判别联合 `{kind:'requirement'} | {kind:'task', taskId}` | 现状用字符串同时表达"需求级"与"任务 id"两种含义（`stage-panel` 要 `it.source === 'requirement'` 特判），是字符串型歧义 |
| C8 | `task.scope` 缺失时补 `{apis:[],tables:[],files:[]}` | 消除 `scope?` 的可选链分支（现多处 `t.scope?.files ?? []`） |
| C9 | `task.dependsOn` 去重 + **剔除悬空引用** | 现无校验：指向已删任务的依赖会让 DAG 渲染出幽灵节点。对齐 R-020「悬空引用必须可探测」 |
| C10 | `artifacts` 按 `(kind, path)` 去重，保留 `confirmedAt` 最早非空者 | 自动发现（`sync-artifacts`）与显式登记可能重复登记同一文件 |
| C11 | 迁移报告落盘 `docs/requirements/REQ-47939a/migration-report.md` | 验收 A4 需要可复核的证据文件 |

**明确不改**：`id` / `title` / `status` / `comments` / `version` / `createdAt` / `updatedAt` / `createdBy` / `updatedBy` / `archivePath` / `archive` / `plan` / `verification`（除 C7） / `statusHistory` 的内容与顺序 / `executions` / `lastReport` / `triages` 全部字段。

## 3. 迁移流程（5 步，失败即回滚）

```
① 备份      cp dsh-reqboard.json dsh-reqboard.json.bak-req47939a-<epoch>
② dry-run   迁到内存 → 计算 diff → 报告（不写盘），退出码 0=可迁 / 1=有非白名单差异
③ 校验      diff 逐路径比对白名单（见 §4）；任一路径不在白名单 → 中止
④ 落盘      临时文件 + rename 原子替换（复用 store 的原子写路径，不以裸 writeFile 覆盖）
⑤ 复核      重新加载 → 断言 schemaVersion=5 且记录数 34/84/2 不变 → 写 migration-report.md
```

**脚本**：`packages/pages/dsh-pmboard/scripts/migrate-ledger.mjs`（Node 内置模块，不依赖 tsx，可在实例停机时执行）
```
node scripts/migrate-ledger.mjs --file <ledger> --dry-run     # 只报告
node scripts/migrate-ledger.mjs --file <ledger> --apply       # 备份 + 迁移 + 复核
node scripts/migrate-ledger.mjs --file <ledger> --verify      # 只核对现网台账是否已是 v5 且无损
```
脚本**幂等**：已是 v5 时 `--apply` 无操作并以 0 退出（可重跑）。

## 4. 校验口径（"无损"的可机械判定）

迁移前后各生成一份**规范化快照**（递归排序对象键、数组保序、忽略 `revision` 与 `updatedAt`——迁移会 bump），逐**路径**比较，只允许以下白名单差异：

| 路径模式 | 允许的差异 |
|----------|-----------|
| `schemaVersion` | 4 → 5 |
| `migrations` | 新增 |
| `requirements[*].statusHistory` | 由缺失/无 → 补齐（值须等于 backfill 推导结果） |
| `requirements[*].category` | 由缺失 → `"feature"` |
| `requirements[*].projectId` `parentId` | 删除 |
| `requirements[*].verification.sheet.items[*].source` | 字符串 → 判别联合（`"requirement"` → `{kind:"requirement"}`；任务 id → `{kind:"task",taskId}`） |
| `requirements[*].artifacts` | 去重（仅当存在重复项时才允许条数减少） |
| `tasks[*].scope` | 由缺失 → 默认空结构 |
| `tasks[*].dependsOn` | 去重或剔除悬空引用（仅当存在时才允许变化） |
| `revision` `updatedAt` | 忽略 |

报告须逐条列出白名单内的实际差异数量（如"悬空依赖剔除 3 条"），**不为 0 也要显示**——"没变化"和"没检查"必须能区分。

## 5. 兼容读策略

- 实例读路径：`schemaVersion < 5` 时**照旧可读**（保留 v4 归一化分支），首次写盘自动升 v5。即：不迁移也能跑，迁移只是为了拿到 C3/C4 的代码删除收益。
- 实例**不自动迁移**（避免服务启动时对 736KB 台账做大改）；迁移由 P0 交付时人工执行一次（脚本 + 报告），并在 `migration-report.md` 留证。
- 回滚：把备份文件 rename 回原位并重启（v5 读路径能读 v4，反之不行——所以回滚必须连文件一起回）。

## 6. 风险与对策

| 风险 | 对策 |
|------|------|
| 迁移期间实例正在写台账 | 迁移前先确认无写入（实例停机或 `--dry-run` 与 `--apply` 之间检查 `revision` 未变） |
| 别名映射错把"看起来像旧名"的新名改掉 | 白名单比对 + dry-run 报告逐条列出被映射的 id/原值/新值 |
| `statusHistory` 补齐与 backfill 结果不一致 | 直接复用 `backfillRequirementHistory` 的算法（同一实现，不重新写一遍）否则会造出第二套时间线语义 |
| 悬空依赖剔除误删合法依赖 | 只剔除 `dependsOn` 中指向**本需求内不存在**任务 id 的项，并在报告中列出被剔除项（可人工复核） |
