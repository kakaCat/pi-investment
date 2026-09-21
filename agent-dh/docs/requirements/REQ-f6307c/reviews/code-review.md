# REQ-f6307c 代码评审报告

## 评审范围

本需求最终交付的代码改动（T3 修复 + T1 诊断保留）：

| 文件 | 改动 | 评审结论 |
|------|------|---------|
| `src/application/internal/diag-log.ts`（新增） | captureDiag 文件+控制台双写，512KB 轮转 | ✅ 通过 |
| `src/index.ts` | EARLY 初始化 + NODE-1 订阅日志切双写 | ✅ 通过 |
| `src/adapters/CaptureHook.ts` | NODE-2/NODE-3 事件日志切双写 | ✅ 通过 |
| `src/gate-wiring.ts` | NODE-4 组装日志切双写 | ✅ 通过 |
| `src/application/internal/capture-section.ts` | NODE-5 生成日志切双写（5 处分支） | ✅ 通过 |
| `scripts/verify-capture-chain.mts`（新增） | 集成链路验证脚本 | ✅ 通过 |
| `scripts/verify-t4-rounds.mts`（新增） | 连续 3 轮测试脚本 | ✅ 通过 |

## 评审要点

### 1. 正确性

- **未改动任何业务逻辑**：captureSectionText / shouldCaptureWindow / isWindowBound / handler 分支判断全部保持原样，改动仅限"日志输出方式"（console/logger 单写 → captureDiag 双写）。链路的判定语义零变化。
- **诊断通道容错**：captureDiag 每个 IO 操作（stat/rename/appendFile/console）都独立 try-catch 静默——诊断永不反向影响主流程，与 isolation-trace 的容错设计对齐。
- **轮转有界**：512KB 单文件 + 一代 .1 备份，磁盘占用上限约 1MB，无无限增长风险。

### 2. 兼容性

- 既有 logger.info/debug 调用保留（NODE-1 处 logger.info 与 captureDiag 并存），原日志通道行为不变。
- dist 重建后插件加载正常（EARLY/NODE-1 实录 SUCCESS），全部 reqboard 工具功能无损（本窗口全程使用验证）。
- bound 窗口 systemPrompt 零噪音不变（NODE-5 实录返回空串）。

### 3. 性能

- captureDiag 0.041ms/次（N=100 均值），分布在 systemPrompt 组装（每回合 1-2 次）与事件处理（每条消息 1 次）路径，对回合延迟的影响可忽略（<0.1ms vs 100ms 预算）。

### 4. 安全与边界

- 诊断文件只写窗口标识（前 16 字符）与消息长度/提示词长度，**不落消息原文全文**（NODE-3 仅 text.length），无敏感信息泄漏面。
- 文件权限跟随 state/ 目录默认（700 目录）。

## 遗留观察（非阻塞）

1. **长回合重复注入**：pending 在 turn/end 才清除，Agent 多步工具调用期间每个 step 的 systemPrompt 组装都会重复注入 1179 字提示词（实测 f65bdd85 窗口持续约 12 分钟）。这是设计内的 nag 策略（防 LLM 中途忘记），token 成本为已知权衡；若未来要优化，可改为"首次注入后即清除"。
2. **turn/end 清除日志**仍为 debug 级（未进 diag 文件）：清除动作本身靠 NODE-4 的 size 变化间接观测。如需直接观测可把该处也切 captureDiag——非必须。
3. **GUI 旧标签页 WebSocket 断连**：本次手动测试发现重启前打开的标签页消息发不出去（web-liveness 覆盖范围的边缘场景），与本文档无关但值得记录。

## 评审结论

**通过**。改动最小化、语义零变化、容错完备、性能可忽略；真实 E2E 与模拟连续测试证据齐全。

评审人：w-49bdb1dd（investor 窗口，实施者自评）
评审日期：2026-09-21
