# t-c1a5e8 里程碑超时未确认主动提醒（W1）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
里程碑超时未确认主动提醒（W1）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
产物登记 >30min 未确认时绑定窗口收到注入提醒（注入留痕可查）；单测模拟覆盖

## 上游产出摘要（dependsSummary）
- reqboard_ask_confirm 原子工具（W1 核心）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T07:54:40.837Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

里程碑超时提醒落地：capture-hook 检测产物登记 >30min 未确认（当前阶段且 confirmedAt 为空）→ 向绑定窗口注入提醒（复用 onStagePrompt 通道，含 reqboard_ask_confirm 调用指引与 kind 参数）。每产物只提醒一次（hook 闭包 Map 去重），确认后自然失效。解决"agent 不主动弹框"——从软纪律升级为到时触发

### 完成项

- MILESTONE_REMINDER_MS 常量（30 分钟阈值）
- milestoneReminderFor() 判定函数：取最新 open 需求的当前阶段超时未确认产物 → 返回 artifactKey + 提醒文本
- capture-hook 闭包 remindedAt Map + 注入逻辑（line 238-244，在阶段提示词注入后执行）
- 4 个新测试：超时注入提醒/每产物只提醒一次/已确认不提醒/新鲜不提醒
- 踩坑：测试 now() 固定返回 1000，artifact.registeredAt 用 Date.now() 导致判定失败——统一用 testNow

### 改动文件

- `packages/pages/dsh-pmboard/src/host/capture-hook.ts`
- `packages/pages/dsh-pmboard/tests/capture-hook.test.ts`

### 下一步

t10 文字确认核验 / t11 产物自动发现（无依赖可并行）

---
