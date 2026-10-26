# t-33cead notify_agent + agent_prompts

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
notify_agent + agent_prompts

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/v2/test_account_routing.py -q 退出码 0；账户A触发断言 owner=agent-A；两通道文件可 import 且互不 import 断言

## 实施方案（implementation）
新建 v2/notify_agent.py + v2/agent_prompts.py：send() 读提示词注册表（持仓×判定类型）→按 WATCH_ACCOUNT_AGENT_MAP 路由→发送；处理回写 process_state。验证：账户路由单测 + 互不 import 断言。

## 上游产出摘要（dependsSummary）
- 触发路由 10 次循环 + 每日重置

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
