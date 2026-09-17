# reqboard 流水线简化：验收即归档（REQ-9f4a44）

> 完成于 2026-09-17 · 类型 refactor · 窗口 w-24ded829

## 结论

流水线从「验收 → 完成(done) → 归档」收敛为「**验收 → 归档**」：

| 项 | 变更 |
|---|---|
| 状态机 | `accepting: ['archived','implementing','canceled']`；`done: []`（legacy 终态，不再进入）；`MAIN_REQ_STATUSES` 去 done、`ALL_REQ_STATUSES` 保留 done 供老台账载入 |
| 人工门 | 四道门：`accepting>archived`（verification）取代原 `accepting>done` + `done>archived`；归档不再是人工门 |
| 验收落点 | `handleVerifyDecision(pass=true)` → `status='archived'`（时间线 [accepting, archived]，无 done） |
| 归档补料 | `reqboard_archive_submit` 放宽为 archived 可用，写 `archivePath`（承担原"人点归档"落章）；`POST /req/archive` + `handleArchive` 删除 |
| 提示注入 | `stage-prompts` archived 段新增第 0 条："归档已自动完成，请补齐材料" |
| 看板 | archived 且无 archive 材料 → 「归档材料待补」；归档归入"已完成"区 |
| 流程图 | FLOW 7 格（立项→需求分析→技术设计→拆分→实施→验收→归档）；分类档案同步 |

## 验证

- 单测 24 文件 / 395 用例全绿
- 实测：验收通过 → archived **直达**（statusHistory 无 done）
- 历史兼容：重启后 18 条 legacy `done` 正常载入
- 门禁实测：decomposing→implementing 经 `ask_user_question` + `reqboard_confirm_artifact` 走通

## 关联

- 需求：[REQ-9f4a44](../../requirements/REQ-9f4a44/requirement.md)
- 前序（确认门工具化）：[REQ-ff20ca](../../requirements/REQ-ff20ca/requirement.md)
- 设计文档：[RFC 014 §10a/10b](../../rfcs/014-requirement-board.md)
