# Genome 工具验证报告（2026-08-31）

**验证对象**: TOOLS_REFACTOR_TRACKER.md 中 #40-45 genome_* 6 个工具（此前标记 🔴 未暴露）
**验证方式**: Live SDK 直接调用实测（execute → schema 绑定校验 → 落盘副作用检查）
**验证人**: investor (w-9bbe3e64) | 2026-08-31 00:05-00:15

---

## 结论速览

| 工具 | SDK 挂载 | Live 实测 | 结论 |
|------|---------|-----------|------|
| genome_read | ✅ | ✅ 返回内容正确（version=number 通过） | 🟢 **可用** |
| genome_list | ✅ | ❌ 绑定拒绝：sections[].version 应为 string，实际返回 number | 🔴 **不可用** |
| genome_history | ✅ | ❌ 绑定拒绝：current_version 应为 string，实际返回 number；且线上无 history 快照目录 | 🔴 **不可用** |
| genome_update | ✅ | ❌ 绑定拒绝 old_version/new_version；**但已先写盘+git commit 后才报错** | 🔴 **不可用（危险副作用）** |
| genome_promote | ✅ | ❌ 绑定拒绝 old_version/new_version；**但已先写盘+git commit 后才报错** | 🔴 **不可用（危险副作用）** |
| genome_rollback | ✅ | ❌ 双层失败：① validate 要求 semver（拒绝整数 "5"）；② 即使传 "5.0.0"，history 目录不存在 → "版本 5.0.0 不存在于历史记录中" | 🔴 **不可用** |

**一句话结论**: SDK 已挂载（不再是"未暴露"），但 6 个工具中仅 genome_read 真正可用，其余 5 个在 schema 绑定层/数据层不可用，且 update/promote 存在"执行成功、调用报错"的危险副作用。

---

## 实测证据

### 1. 只读工具

- `genome_read({section:'constitution'})` → ✅ 返回完整宪法内容，version=1
- `genome_list({})` → ❌ `tool "genome_list" returned invalid output: "value.sections[0].version" must be a string`（4 个段全部命中）
- `genome_history({section:'lessons'})` → ❌ `"value.current_version" must be a string`

### 2. 写工具（均在备份后实测，随后恢复）

- `genome_promote({section:'lessons', increment:'patch', reason:'工具验证...'})`
  - 工具内部执行成功：genome.json 中 lessons v5→v6、git commit `98df172 genome: promote lessons to v6` 已生成
  - SDK 绑定层拒绝：`"value.old_version" must be a string; "value.new_version" must be a string`
- `genome_update({section:'lessons', content:<原内容+验证标记>, reason:'工具验证...'})`
  - 工具内部执行成功：lessons.md 被追加标记行、版本 v6→v7、git commit `d9c95a9 genome: update lessons` 已生成
  - SDK 绑定层拒绝：同样 old_version/new_version 类型错误
- `genome_rollback({section:'lessons', target_version:'5'})` → ❌ `无效的版本号格式: 5`（validate 层，正则要求 semver）
- `genome_rollback({section:'lessons', target_version:'5.0.0'})` → ❌ `版本 5.0.0 不存在于历史记录中`（execute 层，线上 `history/` 目录不存在）

### 3. 恢复校验（写测试后）

- 5 个文件 md5 与测试前备份完全一致（genome.json=e901e17d...、lessons.md=6def94d3...、principles.md=b3d35f77...、rules.md=4726f286...、constitution.md=24c30c5b...）
- git HEAD 复原至 `28a54c7`，两条测试 commit（98df172/d9c95a9）已清除
- `git status` 保留测试前既有的未提交改动（g16 条目 git_commit 回填），与验证前状态一致

---

## 根因分析

**版本模型不一致（schema vs 线上实现）**：

| 层 | 版本方案 | 证据 |
|----|---------|------|
| prompt.ts 输出 schema（重构后） | semver 字符串 "1.0.0" | GenomeListTool/prompt.ts: version: string；GenomePromoteTool/prompt.ts 示例 old_version: '1.5.3' |
| 单元测试 mock（重构时） | semver 字符串 | scripts/test-genome-tools.ts: version: '1.0.0'，mock bumpVersion 返回 semver |
| **线上真实插件（packages/genome/src/index.ts）** | **整数版本 1/6/7/5** | /Users/yunpeng/.dsh-agent-dh/genome/genome.json: sections.*.version 为数字；versionManager.bumpVersion 返回 oldVersion+1 |

- 单测 26/26 通过（本次复跑确认），但测试的是 semver mock 环境，**从未与线上整数版本方案对齐**——"假通过"。
- 线上数据模型（store.ts）明确用 `SectionMeta.version: number`，且历史记录存在 genome.json 的 history 数组（g1→g16 演进记录），**没有** history/<section>/<version>.md 快照文件；重构后的工具却按"文件快照"实现 history/rollback，两端脱节。
- 附带问题：genome_list 的 class 过滤枚举 core/domain/runtime 与线上 class（constitution/evolvable）不匹配；重构后的 update/promote 未实现线上原有的 candidate→promote 验证门（stage 字段）逻辑。

---

## 修复建议（按优先级）

1. **P0 - 输出 schema 对齐整数版本**（5 个工具）：将 GenomeListTool / GenomeHistoryTool / GenomeUpdateTool / GenomeRollbackTool / GenomePromoteTool 的 prompt.ts 输出 schema 中所有版本字段改为 `type: 'number'`（与 genome_read 一致），并同步修改示例。
2. **P0 - 消除写路径副作用**：update/promote 当前"先落盘+git commit、后校验报错"。建议在 execute 前完成输出类型自检，或让绑定层校验前置；至少保证失败时不动盘。
3. **P1 - history/rollback 数据层二选一**：
   - 方案 A：工具改为读写 genome.json 的 history 数组（与 store.ts/versioning.ts 一致），rollback 从数组取目标版本内容（需在 history 数组或 git 中保存段内容快照）；
   - 方案 B：update/promote 时落盘 history/<section>/<version>.md 快照，rollback 读取快照。
4. **P1 - 单测补线上契约测试**：test-genome-tools.ts 增加"整数版本 + genome.json history 数组 + 无快照目录"场景（或直接以线上 genome.json 为 fixture），防止再次假通过。
5. **P2 - genome_list class 枚举**：与线上 class（constitution/evolvable）对齐或改为自由字符串。

## 附件

- 备份目录：/tmp/genome-verify-backup-20260831-000528（线上基因组测试前快照，保留 24h 后可清理）
---

# 修复完成验证（2026-08-31 00:45，investor w-a1484624）

## 修复落地（对应上节 1-5 建议）

1. **P0 schema 对齐**：5 个工具 prompt.ts 输出 schema 版本字段全部改为 number（整数线上模型），示例同步；class 枚举对齐 constitution/evolvable。
2. **P0 副作用消除**：update/promote/rollback 写路径改走 store/versioning（genome.json history 数组，无文件快照），写入前 guard 链全部通过才落盘 + git commit；失败路径（宪法段/乐观锁/花括号/大小/交易时段/金丝雀渲染）一律先还原盘面再抛错。新增 packages/genome/src/tools/host.ts（GenomeWriteHost：hotSwapSection + canaryRender），由 index.ts 注入宿主实现，渲染金丝雀失败自动还原。
3. **P1 数据层**：history/rollback 走 genome.json history 数组（方案 A）；rollback 支持 to_section_version 显式版本（git 取内容）+ 默认回退上一版本。
4. **P1 契约测试**：scripts/test-genome-tools.ts 重写为「真实临时目录 + 真实 git 仓库 + 整数版本 + 模拟绑定层校验（schema + lossless JSON）」，覆盖 guard 链/快照还原/回滚/转正/历史过滤；20/20 通过。tests/genome.unit.test.ts 19/19 通过；pnpm --filter @pi-investment/genome build 通过。
5. **P2 class 枚举**：过滤参数限定 constitution/evolvable；顺带修复过滤分支 B-4 缺陷（by_class: undefined 触发 not lossless JSON）。

## Live 实测结果（本次修复会话）

| 工具 | 结果 |
|---|---|
| genome_list（无过滤） | 绑定通过，4 段整数版本 |
| genome_read | 绑定通过 |
| genome_history（全部 + 按段过滤 + limit） | 绑定通过，无 undefined 字段 |
| genome_update | Live 真实升级 lessons v5→v6（g17，git commit c4b3edf，hot-swap + 金丝雀通过） |
| genome_promote（无 candidate） | 拒绝路径绑定通过，无副作用 |
| genome_rollback | 契约测试覆盖（prev + 显式版本）；Live 未写（避免多余版本推进） |

## 遗留事项

- **genome_list class 过滤修复需服务重启生效**：运行中 dsh 服务（PID 30345，--import tsx/esm）在本次最后两处补丁（GenomeHistoryTool 导出 + GenomeListTool by_class）之前启动，内存中仍是旧模块。schema 修复、update/history 等已在重启前生效。重启由用户决定（上次重启丢 session，本轮避免重蹈）。重启后建议快速复验：tools.genome_list({class: evolvable}) → total=3 且无 by_class 字段。
- 线上基因组 lessons v5→v6（g17）为真实经验进化，保留；如需要可 genome_rollback({section: lessons}) 回退（history 有 git_commit 依据）。备份：/tmp/genome-fix-backup-1788108255190。
- 契约测试脚本 scripts/test-genome-tools.ts 被 .gitignore 的 test-*.ts 规则忽略（本地验证脚本），不入库；核心防回归保障 = tests/genome.unit.test.ts + Live 实测记录。

