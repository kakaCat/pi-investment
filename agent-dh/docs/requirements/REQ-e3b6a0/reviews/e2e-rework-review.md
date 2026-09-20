# REQ-e3b6a0 评审报告 · E2E 走查返工与流程正位

- 评审时间：2026-09-20
- 评审窗口：w-878da638（session-878da638-a076-4266-ae40-70a2390060f2）
- 评审对象：实施阶段收口前的 E2E 走查结果（AC-7.1 立项 / AC-11.2 G1）
- 结论：**实现层通过；流程承载错位已正位；线上走查移交 accepting 阶段由人确认**

## 1. 走查发现（事实）

对窗口 session-361c2879（15:18–15:30）的会话转录逐条核对：

| 环节 | 结果 |
|---|---|
| CaptureHook 登记 pending | OK —— 4 条用户消息全部登记 |
| pendingCapture 命中（key 一致） | OK |
| 针对性立项段注入 system prompt | OK —— turn 2/3/4 均含「检测到用户新输入」 |
| 文案已指向 pm 专有工具 | OK —— turn 2 起为 reqboard_capture 版 |
| 模型调用 reqboard_capture | **否 —— 0 次** |

工具调用侧：17 次 tool/call 全为 run_code；PTC 展开 35 次子调用仅 read(28) / grep(7)。

## 2. 根因（评审结论）

不是提示词缺失、也不是链路断线，而是**把"是否立项"的决定权完全交给模型的语义自由裁量**：
原文案「请先判断**可能**包含值得立项的新工作意图 / 只是闲聊则正常回复」是二元裁量，
且不弹框**零后果**（无拒绝、无留痕、无重试）。15:23:57「修复 FR-6 任务状态机…」这种
明确工作意图亦被判成"对当前审查的追问"。

## 3. 处置（已实施）

- capturePromptForMessage / captureGuidanceText 硬化：必须显式裁定（判不准按值得立项）；
  值得立项时**本回合第一个工具调用**即 reqboard_capture；不立项必须在回复首行写明理由。
- CaptureHook 的 turn/end 增消费留痕；注明 PTC 下无法从 toolTrace 判定工具名，故不做误判。
- capture.test.ts 增锁定用例（防再软化）。
- requirement.md：FR-7 增第 8 条 + 新增 §7.3.2。

## 4. 流程正位（2026-09-20 用户裁定）

需求级线上走查（AC-7.1 / AC-11.2）原被写入**实施卡的验收标准**，导致实施阶段无法自称完成
（本仓纪律：卡的验收标准未满足不得宣称完成），且 t-f33035 停在 integrating 进一步挡住需求
rollup。处置：两卡验收标准修订为"线上走查改由 accepting 阶段采集的 verification 证据"，
**验收义务不变**（AC 仍在需求文档、仍由人审）。

## 5. 遗留与风险

- 硬化仍是**模型层约束**，不保证 100% 弹框；若走查仍不弹，需人拍板上代码侧强制兜底
  （登记 pending 后由组合根主动投递催办 / 扩展 join point 到"待确认产物产生时"）。
- 走查后须把 .dsh-data/profiles/agent-dh/cordis.patch.yml 的 nodeIsolation 改回 {}（D1）。

## 6. 评审结论

- 实现层：**通过**（门禁见 tests/verification-evidence.md）。
- 验收层：**待人在 accepting 阶段走查确认**。
