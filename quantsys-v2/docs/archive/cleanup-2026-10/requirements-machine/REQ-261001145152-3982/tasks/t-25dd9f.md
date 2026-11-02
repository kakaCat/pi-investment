# t-25dd9f 消 application 层 12 处顶层越层导入·测试

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
消 application 层 12 处顶层越层导入·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-01T11:13:46.405Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

测试段：四条验收全部达成——点名文件顶层越层导入归零、通知渠道顶层引用归零、通知测试 72 条全过、余量可复现地降到 44 处；纯净性断言与 app 均未受影响。

### 完成项

- 验收①（修订后口径）：点名文件 `application/notification/notification_factory.py` 顶层越层导入 **0 处**（原 4 处）；`application/services/scheduler.py` **已删除**（实测文件不存在）
- 验收②（卡片原文）：`grep -rn '^from infrastructure.notification.channels' application/` → **0 处**
- 验收③（卡片原文）：`pytest tests/notification -q` → **72 passed**
- 验收④（修订后口径，可复现）：application 层顶层越层导入 **44 处 / 34 文件**（基线 49 处），与验收记录逐字一致
- 附加回归：`app` 可导入（101 路由）；`pytest tests/test_layer_purity.py -q` = **1 passed / 1 skipped**（纯净性断言未变红）
- 口径说明（原验收不可执行的原因）：卡片原写"比对本卡开工前基线"，其中 `pnpm test` / `npx tsc --noEmit` 属 TS 工具链（本仓无 pnpm/tsc），而 `tools/analyze_layer_violations.py` 的"违规导入总数"用 AST 统计**含函数内导入**，不会因"下沉到函数内"下降——故按用户裁定改为 AST **顶层**口径衡量，并把余量如实登记

---
