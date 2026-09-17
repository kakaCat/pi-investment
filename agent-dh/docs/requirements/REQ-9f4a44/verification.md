# REQ-9f4a44 验收材料

> 状态：待人工审核 · 类型：refactor · 绑定窗口：w-24ded829
> 上游：[requirement.md](./requirement.md) · [plan.md](./plan.md)

## 1. 交付结论

流水线从「验收 → 完成(done) → 归档」收敛为「**验收 → 归档**」：

- **done 节点移除**：状态机（MAIN_REQ_STATUSES / REQ_TRANSITIONS）与流程图（FLOW / STAGE_LABELS / StageRenderers / 分类档案）均不再有 done；
  历史 done 保留为 legacy 可读状态（老台账 18 条正常载入）。
- **验收通过即归档**：`accepting → archived`（人工验收门保留），落地在 `handleVerifyDecision(pass=true)`。
- **归档材料由 agent 补齐**：`reqboard_archive_submit` 前置放宽为 archived 可用，并承担原"人点归档"的落章（写 `archivePath`）；
  `stage-prompts` archived 段新增第 0 条提示"归档已自动完成，请补齐材料"。
- **看板可见性**：archived 且无 archive 材料 → 显示「归档材料待补」；归档归入"已完成"区。
- **死接口清理**：`POST /req/archive` 与 `handleArchive` 移除（归档自动化后必然失效）。

## 2. 证据清单

| # | 验收项 | 证据 | 结果 |
|---|---|---|---|
| 1 | 单测全绿 | `npx vitest run` → **Test Files 24 passed / Tests 395 passed** | ✅ |
| 2 | 历史 done 兼容 | 重启后 `/state`：31 条需求中 18 条 legacy `done` 正常载入、无丢失 | ✅ |
| 3 | 新门禁链路 | `decomposing→implementing` 未确认被拒 → `ask_user_question` 确认 → `confirm_artifact(via=session)` → 放行成功 | ✅ |
| 4 | 构建门禁 | `pnpm build:client` → `[verify-client] OK bundle=197454 bytes, 关键符号齐全` | ✅ |
| 5 | 状态机表 | `accepting: ['archived','implementing','canceled']`、`done: []`；四道门含 `accepting>archived: verification` | ✅（单测断言） |
| 6 | 流程图无 done | FLOW 7 格（立项→需求分析→技术设计→拆分→实施→验收→归档）；category stages 均无 done | ✅（单测断言） |
| 7 | 验收即归档 | 验收通过 → 状态直接 `archived`（无 done 中转），时间线 `['accepting','archived']` | ✅（单测 + 本轮实测） |
| 8 | 归档补料 | archived 下调 `archive_submit` 成功并写 `archivePath`；材料不合规仍被拒 | ✅（单测） |

## 3. 已知限制

1. **流程顺序修正**：实施任务时跳过了 `decomposing→implementing` 推进，事后补走（本轮实测了该门）。
2. **归档材料待补标记**为 UI 层（客户端 bundle），需刷新页面后可见。
3. **历史 done 需求**不再可转移到 archived（`done: []`）——如需归档需人工决策，本次未提供迁移路径（保留留痕优先）。
