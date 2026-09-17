# t-ab11f4 实现阶段提示词钩子（插件内常量，不走 skill）

## 提示词

host/stage-prompts.ts 五份阶段纪律常量（跳过阶段不注入）；接线 capture.ts 组装注入+capture-hook 转移注入；implementing 提示词含读产物链而非会话历史

## 验收标准

状态转移后绑定会话下一回合收到对应阶段提示词；跳过阶段不注入；单测验证映射与触发

## 依赖

t-fb59e6

## 执行记录

- ✓ 完成 w-8913546f · 09-15 21:06 → 09-15 21:06 · 手动

  w-8913546f [状态] → in_progress：验收返工：台账补录——该任务实际已完成（subagent 已交付），补齐状态流转（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
  w-8913546f [状态] → integrating：验收返工：台账补录——该任务实际已完成（subagent 已交付），补齐状态流转（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
  w-8913546f [状态] → testing：验收返工：台账补录——任务实际已完成，补齐状态流转至 done（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
  w-8913546f [状态] → in_review：验收返工：台账补录——任务实际已完成，补齐状态流转至 done（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
  w-8913546f [状态] → done：验收返工：台账补录——任务实际已完成，补齐状态流转至 done（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
