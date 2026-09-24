# 接口说明（REQ-260924002956-f37c）

## 内部接口变更

| 接口 | 变更 | 说明 |
|------|------|------|
| `buildCaptureIntentQuestions(titleOptions)` | 新增 | 第 1 段：立项意愿 + 需求名称（含 ✖️ 不需要立项） |
| `buildCaptureDetailQuestions()` | 新增 | 第 2 段：类型 / 难度 / 文档位置 |
| `buildCaptureQuestions(titleOptions)` | 保留 | 兼容导出 = 两段拼接，内容与顺序逐字不变 |
| `captureRequirement` 用例编排 | 修改 | 第一段 ask 不带 gate；拒绝 → 写留痕 + 立即返回；第二段 ask 带 gate:'G0' |
| `h4-resume.ts` 负分支 | 修改 | 有 `from` 才写"节点仍在 {from}"；无 `from` 只写 "{gate} 未通过" |

## 外部契约

`reqboard_capture` 工具 schema 不变；返回值结构不变（`success` / `requirement_id` / `answers` / `defaults_used` / `note`）。
