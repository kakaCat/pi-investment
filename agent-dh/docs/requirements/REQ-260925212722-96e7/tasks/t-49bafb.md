# t-49bafb Decompose 工具增加 armed 检查

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
Decompose 工具增加 armed 检查

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
1. 代码包含 armed 检查：grep "dive?.activation === 'armed'" packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts
2. 错误提示正确：grep "不允许手动拆分"
3. E2E 测试：armed 时调用 reqboard_decompose → 被拒绝

## 实施方案（implementation）
修改 Decompose.ts：在执行前检查 req.dive?.activation === 'armed'，如果 armed 则抛出错误：dive 自动流程已启用，不允许手动拆分。提示使用 reqboard_clear_pause() 解除锁定。

## 上游产出摘要（dependsSummary）
- 扩展数据结构

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T15:00:19.749Z，窗口 session-4211950d-3f6f-40c3-90b8-7903a76208a8）

已完成 Decompose 工具增加 armed 检查：Dive 模式 armed 时拒绝手动拆分

### 完成项

- 在 Decompose.ts 添加 armed 检查
- 检查逻辑：target.dive?.activation === 'armed'
- 错误提示：Dive 自动流程已启用，不允许手动拆分
- 提示用户使用 reqboard_clear_pause() 解除锁定
- 错误码：REQBOARD_DIVE_ARMED
- 编译验证通过

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`

### 下一步

推进任务到 done 状态，提交检查点

---
