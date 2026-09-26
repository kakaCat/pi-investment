# FR-5: reqboard_status 支持显示 FR 覆盖度和验收进度

修改 `reqboard_status` 工具，查询需求状态时，显示哪些 FR 已被任务接收（`task_coverage`），哪些 FR 已验收通过（`acceptance_tracking`）。

**核心改动**：返回结果增加 `fr_coverage` 和 `fr_acceptance_progress` 字段。

**验收标准**：
- A1: 返回 fr_coverage 列表（每个 FR 的接收状态）
- A2: 返回 fr_acceptance_progress（每个 FR 的验收进度）
- A3: 显示未接收的 FR（unreceived_clauses）
- A4: 显示验收未通过的 FR
