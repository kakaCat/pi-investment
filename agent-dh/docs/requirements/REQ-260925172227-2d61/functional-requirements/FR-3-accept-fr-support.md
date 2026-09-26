# FR-3: reqboard_accept_sheet 支持逐 FR 验收

修改 `reqboard_accept_sheet` 工具，按 FR 文件组织验收项，支持逐个 FR 文件验收，记录裁决到 `acceptance_tracking`。

**核心改动**：验收时按 FR 分组（如先验收 FR-1 的 4 个项，再验收 FR-2 的 4 个项），而不是混在一起。

**验收标准**：
- A1: 弹框按 FR 分组展示验收项
- A2: 裁决结果写入 acceptance_tracking
- A3: 全部通过时触发自动归档
- A4: 部分失败时生成返工卡
