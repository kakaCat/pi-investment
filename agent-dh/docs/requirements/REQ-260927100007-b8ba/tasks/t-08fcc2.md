# t-08fcc2 Dive 在人工门主动弹框（有边界重弹）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
Dive 在人工门主动弹框（有边界重弹）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/dive-gate-prompt.test.ts 通过：门已满足未推进时弹出推进确认框；同一次等待只弹 1 次；冷却内不弹、上限 2 次后停手并写 comment。

## 实施方案（implementation）
新增受信内部端口 GatePromptPort（仅 Dive 调用，绕过 idle 期 live-driver 认证）；driveIdle 计算门状态：(a) 产物未确认→弹确认框 (b) 已确认未推进→弹推进确认框；幂等按 (需求,门,产物指纹) 一次等待只弹一次，跨回合冷却≥5min、上限 2 次，到顶留痕停手；未装配端口→行为与改动前逐字一致。

## 上游产出摘要（dependsSummary）
- Dive 采集半停止直投 + 投递白名单

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T03:54:04.267Z，窗口 session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8）

人工门的兜底从"提醒 agent 去弹框"改成"Dive 自己弹框"：idle 跑批时算出门状态（产物已登记未确认 → 弹确认框；产物已确认但状态没动 → 弹推进确认框），并带边界地重弹（同一次等待只弹一次、跨回合冷却 5 分钟、上限 2 次，到顶写台账评论停手）。肯定项仍由人（actor=human）走同一条状态机，Dive 不替人做决定。

### 完成项

- 新增受信内部端口 GatePromptPort（design I-10 签名）+ application/dive/gate-prompt.ts：门状态投影 gatePromptFor、有边界重弹状态机 createGatePromptLoop、可投产的端口实现 createGatePromptPort（肯定项→applyConfirmDecision，G3 走 plan 门合并落库，FR-1 不被绕过）
- session-driver.driveIdle 末尾接 gatePromptLoop.tick；未注入端口 → 逐字零行为（不改变 FR-11 的采集半零投递）
- 组合根 pm-capture-root 透传 gatePrompt + onGatePromptExhausted（到顶写台账 comment）
- G4 验收门排除在自动弹框之外（归档要逐项裁决，不能被压成一个肯定项）
- 测试：tests/dive-gate-prompt.test.ts 9/9（TC-15 全量）＋ dive 相关 4 文件 44/44
- 交付边界（响亮报出）：端口已 plumb 但**未在生产组合根装配**——卡片明确允许"未装配端口→行为与改动前逐字一致"；激活还需在 index.ts 注入 createGatePromptPort 并给端口补 agent 解析（当前 questions.ask 不带 agent，idle 期路由语义未验证）。刻意不擅自打开，避免向人弹未经确认的框。

### 改动文件

- `packages/web/dsh-pmboard/src/application/dive/gate-prompt.ts`
- `packages/web/dsh-pmboard/src/application/dive/session-driver.ts`
- `packages/web/dsh-pmboard/src/application/ports.ts`
- `packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts`
- `packages/web/dsh-pmboard/tests/dive-gate-prompt.test.ts`

### 下一步

若需在生产激活：index.ts 装配 createGatePromptPort（并补 agent 解析），随后在真实窗口验证 idle 期能弹框。

---
