# FR-2: reqboard_submit 支持从 FR 文件生成验收单

修改 `reqboard_submit(kind=verification)` 工具，从 FR 文件提取验收标准（A1-A4），生成 `verification_sheet`，填充 `acceptance_tracking`。

**核心改动**：不再手动传 `evidence`，而是从 FR 文件的"验收标准"章节自动提取，生成验收单。

**验收标准**：
- A1: 成功从 FR 文件提取验收标准
- A2: 生成 verification_sheet 包含所有 FR-*-A* 项
- A3: 填充 acceptance_tracking 到 rtm.yaml
- A4: 需求状态推进到 accepting
