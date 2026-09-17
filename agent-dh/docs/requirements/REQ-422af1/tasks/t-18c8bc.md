# t-18c8bc 实现节点边界同窗口 surface 替换执行模型

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
实现节点边界同窗口 surface 替换执行模型

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
tests/isolate-node-context.test.ts 全绿：①输入包文本等于路由结果 + 文档/台账投影，且不包含前序对话摘录 ②两端未配对（tool 调用无结果）时替换不发生并返回结构化错误 ③agent 忙碌时替换不发生、留痕、无未捕获异常 ④产物写入事件 seq 小于替换事件 seq（先落盘后遗弃）⑤触达失败时返回「请开新窗口 + 输入包文本」而非静默跳过。验证命令：npx vitest run tests/isolate-node-context.test.ts（在 packages/pages/dsh-pmboard 下）；不通过则本卡不完成。

## 实施方案（implementation）
新增 src/application/use-cases/IsolateNodeContext.ts（构造节点输入包 + 判定执行时机 + 调 surface 替换）；边界检查复用 @deepseek-ai/dsh-compaction 导出的 toolPairingBalancedBefore/After（不平衡即拒绝执行）；替换调用 session.append(user/message, …, { surfaceOp: { op: replace, startSeq, endSeq } })；触达能力探测失败走降级链（design/architecture.md §5 与 requirement.md D-12）。若实测（A）路线被框架不变量拒绝，按纪律回 planning 重提计划，不在本卡内私改设计。

## 上游产出摘要（dependsSummary）
- 实现注入留痕（ring buffer + 只读查询）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T15:07:38.845Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

同窗口 surface 整段替换执行模型落地：路线 A 可行但字面区间（0..N）被框架不变量硬拒（surface 节点 0=系统提示词），按 D-15 取合法区间「首个非 system 节点→末尾」，结果 [系统段, 输入包]；路线 B 同等受阻未采用。父窗口已复核。

### 完成项

- IsolateNodeContext.ts（377 行：端口 + 编排 + 时机/边界/先落盘后遗弃/D-12 降级链）
- node-input-package.ts（180 行：输入包与台账投影纯函数）
- NodeIsolationAdapter.ts（surface 原语 + tool 配对边界等价移植，注明来源与不可解析原因）
- tests/isolate-node-context.test.ts：T24-T28 全覆盖含失败路径，17/17（父窗口重跑通过）
- 框架拒绝点原文固化为断言（node 0 holds the system prompt）
- 父窗口复核：application 层行首锚定 import 命中 0、分层门禁绿、tsc 0 错误、全量 1 failed(既有) | 928 passed

### 改动文件

- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/application/use-cases/IsolateNodeContext.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/application/internal/node-input-package.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/src/adapters/NodeIsolationAdapter.ts`
- `/Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/tests/isolate-node-context.test.ts`

### 下一步

t10 接线：隔离动作移出 session/event 派发 + 注入端口/开关（默认关）

---
