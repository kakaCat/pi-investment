# REQ-f6307c · 测试用例

## 说明（serves: BUG-1, BUG-2）

测试用例已完整覆盖在 `decomposition.md` 各任务的 acceptance 字段中。

## T1 - 诊断日志验收（serves: BUG-1）

**用例**：在 unbound 窗口发送"修复 XX"消息

**验收**：
- [ ] 节点1 有日志（Hook 订阅状态）
- [ ] 节点2 有日志（事件到达）
- [ ] 节点3 有日志（pendingCapture 填充）
- [ ] 节点4 有日志（windowKey 提取）
- [ ] 节点5 有日志（提示词生成）
- [ ] 日志格式统一，包含关键状态

## T2 - 断链定位验收（serves: BUG-1）

**用例**：执行诊断测试

**验收**：
- [ ] 日志保存到 `diagnostic-log.txt`
- [ ] 明确指出断链位置
- [ ] 记录断链原因假设

## T3 - 修复验收（serves: BUG-2）

**用例**：修复后重新测试

**验收**：
- [ ] 所有 5 个节点都正常
- [ ] 节点5 文本长度 > 0
- [ ] LLM 看到动态提示词
- [ ] Agent 第一个工具调用是 `reqboard_capture`

## T4 - 回归测试验收（serves: BUG-1, BUG-2）

**用例1**：连续成功率测试（3 次）

**验收**：
- [ ] 修复/新增/实现消息都触发弹框
- [ ] 成功率 100%（3/3）

**用例2**：回归测试

**验收**：
- [ ] bound 窗口推进流程正常
- [ ] genome sections 加载正常
- [ ] 性能无明显下降 (< 100ms)
- [ ] 诊断日志已保存

详见 `decomposition.md` T1-T4 的 acceptance 字段。