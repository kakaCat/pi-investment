# REQ-81aabd 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-1 | t1 | t-6e407e | 节点键改名 planning → design（状态机/协议/提示词分片/全仓字面量） | todo |
| FR-2 | t1 | t-6e407e | 节点键改名 planning → design（状态机/协议/提示词分片/全仓字面量） | todo |
| FR-6 | t1 | t-6e407e | 节点键改名 planning → design（状态机/协议/提示词分片/全仓字面量） | todo |
| FR-3 | t2 | t-d5263f | 设计文档种类建模与旧条目回填 | todo |
| FR-5 | t2 | t-d5263f | 设计文档种类建模与旧条目回填 | todo |
| FR-4 | t3 | t-114b49 | 设计节点逐份交付状态展示 | todo |
| FR-7 | t4 | t-d82522 | 台账 v6→v7 迁移脚本与实迁执行 | todo |
| FR-2 | t5 | t-4a85f8 | 文档同步、客户端重建与验收材料 | todo |
| FR-6 | t5 | t-4a85f8 | 文档同步、客户端重建与验收材料 | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-6e407e | 节点键改名 planning → design（状态机/协议/提示词分片/全仓字面量） | implement | fullstack | - | 在 packages/pages/dsh-pmboard 执行 `npx vitest run` 全绿（97 文件/1250 用例）；`grep -rn "planning" src` 命中 0（src/domain/legacy/LegacyStatus.ts 别名表除外）；`node scripts/check-prompt-fragments.mjs` 输出 OK。 |
| t2 | t-d5263f | 设计文档种类建模与旧条目回填 | implement | backend | - | `npx vitest run tests/domain/artifact.test.ts tests/sync-artifacts.test.ts` 全绿；用例包含：ALL_ARTIFACT_KINDS 含 design 而 STAGE_ARTIFACT_REQUIREMENTS/ARTIFACT_CONFIRM_GATES 均不含；二次同步返回 0 且不再改写。 |
| t3 | t-114b49 | 设计节点逐份交付状态展示 | implement | frontend | t-d5263f | `npx vitest run tests/stage-detail.test.ts tests/stage-panel.test.ts` 全绿；渲染输出含 data-design-doc="architecture.md" data-submitted="yes" 与 data-model.md 的 "no"。 |
| t4 | t-d82522 | 台账 v6→v7 迁移脚本与实迁执行 | implement | backend | t-6e407e, t-d5263f | `npx vitest run tests/migration.test.ts` 全绿；`node --import tsx/esm scripts/migrate-ledger.ts --file .dsh-data/dsh-reqboard.json --dry-run` 退出码 0 且白名单外差异为 0；`--apply` 后 `--verify` 输出 0 问题项且 schemaVersion=7；正文历史 planning 措辞仍在。 |
| t5 | t-4a85f8 | 文档同步、客户端重建与验收材料 | doc | doc | t-6e407e, t-d5263f, t-114b49, t-d82522 | `pnpm build:client && node scripts/verify-client-build.mjs` 输出 OK；`grep -c planning lib/client.js` 为 0；重启后看板设计节点显示四份 design 文档的 ✅/⬜ 与 docs/requirements/REQ-81aabd/design/ 实际文件一致。 |
