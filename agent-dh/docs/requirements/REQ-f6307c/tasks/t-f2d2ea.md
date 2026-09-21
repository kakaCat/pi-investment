# t-f2d2ea 根据诊断结果修复 Hook 注入链路

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
根据诊断结果修复 Hook 注入链路

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
修复后重新测试相同用例，日志显示所有 5 个节点都正常，节点5 文本长度>0，LLM 看到动态提示词，Agent 第一个工具调用是 reqboard_capture

## 实施方案（implementation）
根据 T2 诊断结果选择修复方向：A.windowKey提取失败(gate-wiring.ts)、B.snapshot状态不一致(CaptureHook.ts生命周期)、C.判断逻辑误判(window.ts shouldCaptureWindow)、D.事件订阅失败(index.ts订阅逻辑)。最小化改动，添加防御性检查，保留诊断日志

## 上游产出摘要（dependsSummary）
- 执行诊断测试，找到链路断链位置

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
