# 数据模型（REQ-260924002956-f37c）

## 状态变更

| 实体 | 变更前 | 变更后 | 说明 |
|------|--------|--------|------|
| `state/capture-rejections.json` | 拒绝时写入 | 不变 | 拒绝留痕机制保持原样（FR-5 粘滞） |
| G0 闸门登记 | 只要 `answers.length > 0` 就 `enqueue` | 只有第二段（肯定分支）才 `enqueue` | 拒绝不再被当作闸门作答 |
| 弹框回执 `defaults_used` | 拒绝时带 `[category, difficulty, doc_location]`（未答三问被当默认） | 拒绝时不带（只反映真实作答） | 去噪，避免误读 |

## 新增/修改的接口

无新增接口。`reqboard_capture` 的入参/出参契约不变（`CaptureTool.ts` 是薄壳）。
